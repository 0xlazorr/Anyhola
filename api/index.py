from flask import Flask, jsonify

app = Flask(__name__)

# The route must match what the frontend calls
@app.route('/api/download', methods=['POST', 'GET'])
def handle_request():
    # This function simply returns a success message
    return jsonify({'message': 'Success! The backend is working!'})