import asyncio
from hypercorn.config import Config
from hypercorn.asyncio import serve
from flask import Flask, request, jsonify
import logging
from datetime import datetime
import time

# Configure detailed logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('http2_server.log'),
        logging.StreamHandler()
    ]
)

app = Flask(__name__)
logger = logging.getLogger(__name__)

request_count = 0
connection_count = 0

@app.before_request
def log_request():
    global request_count
    request_count += 1
    
    # Log detailed request information
    logger.info(f"REQUEST #{request_count}")
    logger.info(f"  Method: {request.method}")
    logger.info(f"  Path: {request.path}")
    logger.info(f"  Headers: {dict(request.headers)}")
    logger.info(f"  Remote Address: {request.remote_addr}")
    
@app.route('/')
def home():
    return jsonify({
        "message": "HTTP/2 Test Server Running",
        "timestamp": datetime.now().isoformat(),
        "total_requests": request_count
    })

@app.route('/api/data')
def api_data():
    time.sleep(0.1)  # Simulate processing
    return jsonify({
        "data": f"Response to request #{request_count}",
        "timestamp": datetime.now().isoformat()
    })

async def main():
    config = Config()
    config.bind = ["127.0.0.1:8443"]
    config.certfile = "cert.pem"  # We'll create this
    config.keyfile = "key.pem"   # We'll create this
    config.alpn_protocols = ["h2", "http/1.1"]
    config.accesslog = logger
    config.errorlog = logger
    
    logger.info("Starting HTTP/2 server on https://127.0.0.1:8443")
    await serve(app, config)

if __name__ == '__main__':
    asyncio.run(main())
