import asyncio
import logging
import time
import json
import random
from hypercorn.config import Config
from hypercorn.asyncio import serve
from quart import Quart, request, jsonify, Response
import psutil
from datetime import datetime

class HTTP2Server:
    def __init__(self, host="localhost", port=8000, server_id="server_1"):
        self.app = Quart(__name__)
        self.host = host
        self.port = port
        self.server_id = server_id
        self.request_count = 0
        self.connection_count = 0
        self.start_time = time.time()
        self.setup_routes()
        self.setup_logging()
        
    def setup_logging(self):
        logging.basicConfig(
            level=logging.INFO,
            format=f'[{self.server_id}] %(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(f'logs/server_logs/{self.server_id}.log'),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(f'server_{self.server_id}')
    
    def setup_routes(self):
        @self.app.route('/')
        async def home():
            return await self.handle_request("GET", "/")
        
        @self.app.route('/api/data')
        async def api_data():
            return await self.handle_request("GET", "/api/data")
        
        @self.app.route('/heavy-task')
        async def heavy_task():
            # Simulate CPU intensive task
            result = await self.fibonacci_task(request.args.get('n', 30, type=int))
            return await self.handle_request("GET", "/heavy-task", {"result": result})
        
        @self.app.route('/streaming')
        async def streaming():
            return await self.handle_streaming_request()
        
        @self.app.route('/upload', methods=['POST'])
        async def upload():
            return await self.handle_request("POST", "/upload")
        
    async def handle_request(self, method, path, extra_data=None):
        self.request_count += 1
        start_time = time.time()
        
        # Simulate realistic processing time
        processing_delay = random.uniform(0.01, 0.1)
        if "heavy" in path:
            processing_delay = random.uniform(0.5, 2.0)
        
        await asyncio.sleep(processing_delay)
        
        response_time = (time.time() - start_time) * 1000
        
        # Log detailed request information
        log_data = {
            "timestamp": datetime.now().isoformat(),
            "server_id": self.server_id,
            "method": method,
            "path": path,
            "response_time_ms": response_time,
            "request_count": self.request_count,
            "connection_count": self.connection_count,
            "cpu_percent": psutil.cpu_percent(),
            "memory_percent": psutil.virtual_memory().percent,
            "client_ip": request.remote_addr if hasattr(request, 'remote_addr') else "unknown"
        }
        
        if extra_data:
            log_data.update(extra_data)
            
        self.logger.info(json.dumps(log_data))
        
        return jsonify({
            "status": "success",
            "server_id": self.server_id,
            "timestamp": datetime.now().isoformat(),
            "processing_time": response_time,
            "data": extra_data or {"message": f"Response from {path}"}
        })
    
    async def handle_streaming_request(self):
        async def generate_stream():
            for i in range(100):
                data = f"data chunk {i}\n"
                yield data.encode()
                await asyncio.sleep(0.1)
        
        return Response(generate_stream(), mimetype='text/plain')
    
    async def fibonacci_task(self, n):
        # Simulate recursive computation
        if n <= 1:
            return n
        return await self.fibonacci_task(n-1) + await self.fibonacci_task(n-2) if n < 35 else n
    
    async def run(self):
        config = Config()
        config.bind = [f"{self.host}:{self.port}"]
        config.alpn_protocols = ['h2', 'http/1.1']
        
        self.logger.info(f"Starting HTTP/2 server on {self.host}:{self.port}")
        await serve(self.app, config)
