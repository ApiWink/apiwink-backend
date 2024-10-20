from bson import json_util, ObjectId
import json
from flask import Flask, request, jsonify
from flask_cors import CORS
from pymongo.mongo_client import MongoClient
from pymongo.server_api import ServerApi
from dotenv import load_dotenv
import os

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})


load_dotenv()

DB_USERNAME = os.getenv('DB_USERNAME')
DB_PASSWORD = os.getenv('DB_PASSWORD')
uri = f"mongodb+srv://{DB_USERNAME}:{DB_PASSWORD}@apiwink.rhat6.mongodb.net/?retryWrites=true&w=majority&appName=APIWink"
client = MongoClient(uri, server_api=ServerApi('1'))
db = client['APIWink']

@app.route('/add_key', methods=['POST'])
def add_key():
    data = request.json
    walletid = data.get('walletid')
    serviceid = data.get('serviceid')
    reqs = data.get('reqs')
    api_key = data.get('api_key')
    print(walletid)
    print(serviceid)
    print(reqs)
    print(api_key)

    if not all([walletid, serviceid, reqs, api_key]):
        return jsonify({"success": False, "message": "Missing required fields"}), 400

    collection = db['Keys']
    result = collection.insert_one({
        "walletid": walletid,
        "serviceid": serviceid,
        "reqs": int(reqs),
        "api_key": api_key
    })

    return jsonify({
        "success": result.acknowledged,
        "message": "Key added successfully" if result.acknowledged else "Failed to add key"
    })

@app.route('/sub_request', methods=['POST'])
def sub_request():
    data = request.json
    api_key = data.get('api_key')

    if not api_key:
        return jsonify({"success": False, "message": "Missing API key"}), 400

    collection = db['Keys']
    result = collection.find_one({"api_key": api_key})

    if result is None:
        return jsonify({"success": False, "message": "API key not found"}), 404

    if int(result["reqs"]) == 0:
        return jsonify({"success": False, "message": "Cannot go lower than 0 requests"}), 500
    new_reqs = int(result["reqs"]) - 1
    update = collection.find_one_and_update(
        {"api_key": api_key},
        {"$set": {"reqs": new_reqs}},
        return_document=True
    )

    if update:
        return jsonify({
            "success": True,
            "message": "Update successful",
            "remaining_requests": new_reqs
        })
    else:
        return jsonify({"success": False, "message": "Update failed"}), 500


@app.route('/fetch_data', methods=['POST'])
def fetch_data():
    data = request.json
    api_key = data.get('api_key')

    if not api_key:
        return jsonify({"success": False, "message": "Missing API key"}), 400

    collection = db['Keys']
    result = collection.find_one({"api_key": api_key})

    if result is None:
        return jsonify({"success": False, "message": "API key not found"}), 404

    # Remove the _id field as it's not JSON serializable
    result.pop('_id', None)

    return jsonify({
        "success": True,
        "data": result
    })


@app.route('/update_requests', methods=['POST'])
def update_requests():
    data = request.json
    api_key = data.get('api_key')
    add_reqs = data.get('add_reqs')

    if not api_key or add_reqs is None:
        return jsonify({"success": False, "message": "Missing API key or request count"}), 400

    try:
        add_reqs = int(add_reqs)
    except ValueError:
        return jsonify({"success": False, "message": "Invalid request count, must be an integer"}), 400

    collection = db['Keys']
    result = collection.find_one_and_update(
        {"api_key": api_key},
        {"$inc": {"reqs": add_reqs}},
        return_document=True
    )

    if result:
        return jsonify({
            "success": True,
            "message": "Requests updated successfully",
            "api_key": api_key,
            "reqs": result["reqs"]
        })
    else:
        return jsonify({"success": False, "message": "API key not found"}), 404


@app.route('/services', methods=['GET'])
def get_services():
    try:
        collection = db['Services']
        services = list(collection.find())

        # Convert ObjectId to string for JSON serialization
        for service in services:
            service['_id'] = str(service['_id'])

        return jsonify({
            "success": True,
            "data": json.loads(json_util.dumps(services))
        }), 200
    except Exception as e:
        return jsonify({
            "success": False,
            "message": f"An error occurred: {str(e)}"
        }), 500


@app.route('/client_service_details', methods=['GET'])
def get_client_service_details():
    data = request.json
    client_id = data.get('clientid')
    if not client_id:
        return jsonify({"success": False, "message": "Missing client ID"}), 400

    try:
        client_services_collection = db['Keys']
        services_collection = db['Services']

        # Fetch service IDs for the client
        client_services = list(client_services_collection.find({"walletid": client_id}, {"serviceid": 1}))
        service_ids = [service['serviceid'] for service in client_services]

        # Fetch service details
        services = list(services_collection.find({"_id": {"$in": [ObjectId(sid) for sid in service_ids]}}))

        # Convert ObjectId to string for JSON serialization
        for service in services:
            service['_id'] = str(service['_id'])

        return jsonify({
            "success": True,
            "data": {
                "clientId": client_id,
                "services": services
            }
        }), 200
    except Exception as e:
        return jsonify({
            "success": False,
            "message": f"An error occurred: {str(e)}"
        }), 500


@app.route('/service/<service_id>', methods=['GET'])
def get_service(service_id):
    try:
        object_id = ObjectId(service_id)
        service = db.Services.find_one({"_id": object_id})
        if service:
            service['_id'] = str(service['_id'])  # Convert ObjectId to string
            return jsonify(service), 200
        else:
            return jsonify({"message": "Service not found"}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/create_service', methods=['POST'])
def create_service():
    data = request.json
    
    # Extract data from the request
    service_name = data.get('apiName')
    company_name = data.get('developerName')
    description = data.get('apiDescription')
    tags = data.get('apiTags')
    version = data.get('version')
    response_preview = data.get('responsePreview')
    price_pairs = data.get('pricePairs')

    pricing = [{str(pair['calls']): str(pair['price'])} for pair in price_pairs]

    service_object = {
        "serviceName": service_name,
        "companyName": company_name,
        "description": description,
        "tags": tags,
        "pricing": pricing,
        "responsePreview": response_preview,
        "version": version
    }

    print("###")
    print(service_object)

    # Insert into Services collection
    collection = db['Services']
    result = collection.insert_one(service_object)

    if result.acknowledged:
        return jsonify({
            "success": True,
            "message": "Service created successfully",
            "service_id": str(result.inserted_id)
        })
    return jsonify({
        "success": False,
        "message": "Failed to create service"
    })

if __name__ == '__main__':
    app.run()
