from bson import json_util
import json
from flask import Flask, request, jsonify
from pymongo.mongo_client import MongoClient
from pymongo.server_api import ServerApi
from dotenv import load_dotenv
import os

app = Flask(__name__)

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

if __name__ == '__main__':
    app.run(debug=True)
