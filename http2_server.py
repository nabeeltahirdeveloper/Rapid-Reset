from flask import Flask, request, jsonify
import logging
import time
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('server.log'),
        logging.StreamHandler()
    ]
)

app = Flask(__name__)
logger = logging.getLogger(__name__)

# Counter for requests
request_count = 0

@app.before_request
def log_request():
    global request_count
    request_count += 1
    logger.info(f"Request #{request_count} - {request.method} {request.path} - "
                f"Protocol: {request.environ.get('SERVER_PROTOCOL', 'Unknown')} - "
                f"User-Agent: {request.headers.get('User-Agent', 'Unknown')}")

@app.route('/')
def home():
    return jsonify({
        "message": "HTTP/2 Test Server",
        "timestamp": datetime.now().isoformat(),
        "request_count": request_count
    })

@app.route('/test')
def test():
    # Simulate some processing time
    time.sleep(0.1)
    return jsonify({"status": "ok", "data": "test response"})

@app.route('/heavy')
def heavy():
    # Simulate heavier processing
    time.sleep(0.5)
    return jsonify({"status": "heavy processing complete"})

if __name__ == '__main__':
    logger.info("Starting HTTP/2 server...")
    # Note: Flask's built-in server doesn't support HTTP/2
    # We'll use hypercorn for HTTP/2 support
    app.run(host='127.0.0.1', port=5000, debug=True)
