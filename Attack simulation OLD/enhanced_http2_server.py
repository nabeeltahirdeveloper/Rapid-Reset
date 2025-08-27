from flask import Flask, request, jsonify
import logging
import time
import json
import uuid
from datetime import datetime
import threading
from collections import defaultdict, deque
import psutil
import os

# Enhanced logging configuration
def setup_logging():
    """Setup comprehensive logging system"""
    
    # Create formatters for different log types
    detailed_formatter = logging.Formatter(
        '%(asctime)s.%(msecs)03d|%(levelname)s|%(name)s|%(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    json_formatter = logging.Formatter('%(message)s')
    
    # Setup main application logger
    app_logger = logging.getLogger('http2_server')
    app_logger.setLevel(logging.DEBUG)
    
    # Setup JSON structured logger for ML training
    ml_logger = logging.getLogger('ml_data')
    ml_logger.setLevel(logging.INFO)
    
    # File handlers
    app_handler = logging.FileHandler('logs/detailed_server.log')
    app_handler.setFormatter(detailed_formatter)
    app_logger.addHandler(app_handler)
    
    ml_handler = logging.FileHandler('logs/ml_training_data.jsonl')
    ml_handler.setFormatter(json_formatter)
    ml_logger.addHandler(ml_handler)
    
    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(detailed_formatter)
    app_logger.addHandler(console_handler)
    
    return app_logger, ml_logger

# Create logs directory
os.makedirs('logs', exist_ok=True)
app_logger, ml_logger = setup_logging()

app = Flask(__name__)

# Global tracking variables
class ServerMetrics:
    def __init__(self):
        self.request_count = 0
        self.connection_count = 0
        self.active_connections = set()
        self.request_times = deque(maxlen=1000)
        self.request_sizes = deque(maxlen=1000)
        self.client_ips = defaultdict(int)
        self.user_agents = defaultdict(int)
        self.error_count = 0
        self.reset_count = 0
        self.concurrent_requests = 0
        self.start_time = time.time()
        
    def add_request(self, client_ip, user_agent, request_size, response_time):
        self.request_count += 1
        self.request_times.append(response_time)
        self.request_sizes.append(request_size)
        self.client_ips[client_ip] += 1
        self.user_agents[user_agent] += 1
        
    def get_metrics_dict(self):
        current_time = time.time()
        uptime = current_time - self.start_time
        
        # Calculate rates
        recent_requests = [t for t in self.request_times if current_time - t < 60]
        requests_per_minute = len(recent_requests)
        
        # System metrics
        cpu_percent = psutil.cpu_percent()
        memory_info = psutil.virtual_memory()
        
        return {
            'timestamp': datetime.now().isoformat(),
            'uptime_seconds': uptime,
            'total_requests': self.request_count,
            'requests_per_minute': requests_per_minute,
            'active_connections': len(self.active_connections),
            'total_connections': self.connection_count,
            'error_count': self.error_count,
            'reset_count': self.reset_count,
            'concurrent_requests': self.concurrent_requests,
            'unique_clients': len(self.client_ips),
            'unique_user_agents': len(self.user_agents),
            'avg_response_time': sum(self.request_times) / len(self.request_times) if self.request_times else 0,
            'cpu_percent': cpu_percent,
            'memory_percent': memory_info.percent,
            'memory_used_mb': memory_info.used / 1024 / 1024
        }

metrics = ServerMetrics()

@app.before_request
def before_request():
    """Enhanced request logging and tracking"""
    request.start_time = time.time()
    request.request_id = str(uuid.uuid4())[:8]
    
    # Track concurrent requests
    metrics.concurrent_requests += 1
    
    # Extract detailed request information
    client_ip = request.environ.get('HTTP_X_FORWARDED_FOR', request.remote_addr)
    user_agent = request.headers.get('User-Agent', 'Unknown')
    method = request.method
    path = request.path
    query_string = request.query_string.decode('utf-8')
    content_length = request.content_length or 0
    
    # Protocol information
    protocol = request.environ.get('SERVER_PROTOCOL', 'Unknown')
    connection_header = request.headers.get('Connection', '')
    
    # Enhanced logging
    app_logger.info(f"REQUEST_START|{request.request_id}|{client_ip}|{method}|{path}|{user_agent}")
    
    # JSON structured log for ML training
    request_data = {
        'event_type': 'request_start',
        'timestamp': datetime.now().isoformat(),
        'request_id': request.request_id,
        'client_ip': client_ip,
        'method': method,
        'path': path,
        'query_string': query_string,
        'user_agent': user_agent,
        'protocol': protocol,
        'content_length': content_length,
        'connection_header': connection_header,
        'headers': dict(request.headers),
        'concurrent_requests': metrics.concurrent_requests,
        'client_request_count': metrics.client_ips[client_ip]
    }
    
    ml_logger.info(json.dumps(request_data))

@app.after_request
def after_request(response):
    """Enhanced response logging and metrics"""
    try:
        end_time = time.time()
        response_time = end_time - request.start_time
        
        # Update metrics
        client_ip = request.environ.get('HTTP_X_FORWARDED_FOR', request.remote_addr)
        user_agent = request.headers.get('User-Agent', 'Unknown')
        request_size = request.content_length or 0
        
        metrics.add_request(client_ip, user_agent, request_size, response_time)
        metrics.concurrent_requests -= 1
        
        # Enhanced response logging
        app_logger.info(f"REQUEST_END|{request.request_id}|{response.status_code}|{response_time:.3f}s")
        
        # JSON structured log for ML training
        response_data = {
            'event_type': 'request_end',
            'timestamp': datetime.now().isoformat(),
            'request_id': request.request_id,
            'status_code': response.status_code,
            'response_time_ms': response_time * 1000,
            'response_size': len(response.get_data()),
            'content_type': response.content_type,
            'server_metrics': metrics.get_metrics_dict()
        }
        
        ml_logger.info(json.dumps(response_data))
        
    except Exception as e:
        app_logger.error(f"Error in after_request: {e}")
    
    return response

# Routes for different response patterns
@app.route('/')
def home():
    return jsonify({
        "service": "HTTP/2 Enhanced Logging Server",
        "timestamp": datetime.now().isoformat(),
        "metrics": metrics.get_metrics_dict()
    })

@app.route('/api/fast')
def fast_endpoint():
    """Fast response endpoint"""
    return jsonify({"data": "fast response", "timestamp": datetime.now().isoformat()})

@app.route('/api/medium')
def medium_endpoint():
    """Medium response time endpoint"""
    time.sleep(0.1)
    return jsonify({"data": "medium response", "timestamp": datetime.now().isoformat()})

@app.route('/api/slow')
def slow_endpoint():
    """Slow response endpoint"""
    time.sleep(0.5)
    return jsonify({"data": "slow response", "timestamp": datetime.now().isoformat()})

@app.route('/api/heavy')
def heavy_endpoint():
    """CPU intensive endpoint"""
    # Simulate heavy computation
    result = sum(i**2 for i in range(10000))
    return jsonify({"data": f"heavy computation result: {result}", "timestamp": datetime.now().isoformat()})

@app.route('/api/data/<int:size>')
def variable_data(size):
    """Return variable sized data"""
    data = "x" * min(size, 10000)  # Cap at 10KB
    return jsonify({"data": data, "size": len(data), "timestamp": datetime.now().isoformat()})

@app.errorhandler(Exception)
def handle_exception(e):
    """Enhanced error handling and logging"""
    metrics.error_count += 1
    app_logger.error(f"ERROR|{getattr(request, 'request_id', 'unknown')}|{str(e)}")
    
    error_data = {
        'event_type': 'error',
        'timestamp': datetime.now().isoformat(),
        'request_id': getattr(request, 'request_id', 'unknown'),
        'error_message': str(e),
        'error_type': type(e).__name__,
        'path': request.path if request else 'unknown'
    }
    
    ml_logger.info(json.dumps(error_data))
    
    return jsonify({"error": "Internal server error"}), 500

if __name__ == '__main__':
    app_logger.info("Starting Enhanced HTTP/2 Server with detailed logging...")
    app.run(host='127.0.0.1', port=5000, debug=False, threaded=True)
