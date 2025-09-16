import asyncio
import logging
import time
import json
import random
import os
from collections import deque, defaultdict
from hypercorn.config import Config
from hypercorn.asyncio import serve
from quart import Quart, request, jsonify, Response, g, render_template
import asyncio
from typing import Dict, Tuple, Optional
import psutil
from datetime import datetime

from utils.enhanced_request_queue import EnhancedRequestQueue, QueuePriority
from utils.client_connection_manager import ClientConnectionManager
from utils.enhanced_profiling import ProfilerManager, EnhancedPhaseProfiler

class HTTP2Server:
    def __init__(self, host="localhost", port=8000, server_id="server_1", rate_limit_max_requests=100, rate_limit_window_seconds=60, queue_maxsize=1000, queue_workers=4, queue_enqueue_timeout=0.25, queue_processing_timeout=30.0):
        # Configure template and static folders relative to this file
        base_dir = os.path.dirname(__file__)
        template_dir = os.path.join(base_dir, 'templates')
        static_dir = os.path.join(base_dir, 'static')
        self.app = Quart(__name__, template_folder=template_dir, static_folder=static_dir)
        self.host = host
        self.port = port
        self.server_id = server_id
        self.request_count = 0
        self.connection_count = 0
        self.start_time = time.time()
        self._process = psutil.Process(os.getpid())
        
        # Rate limit configuration
        self.rate_limit_max_requests = int(rate_limit_max_requests)
        self.rate_limit_window_seconds = int(rate_limit_window_seconds)
        self._rate_limit_buckets: Dict[str, Tuple[int, int]] = {}
        self._rate_limit_lock = asyncio.Lock()
        
        # Enhanced queue system with client tracking
        self.enhanced_queue = EnhancedRequestQueue(
            maxsize=int(queue_maxsize),
            workers=int(queue_workers),
            enqueue_timeout=float(queue_enqueue_timeout),
            processing_timeout=float(queue_processing_timeout)
        )
        
        # Legacy compatibility - keep for metrics
        self.queue_maxsize = int(queue_maxsize)
        self.queue_workers = int(queue_workers)
        self.queue_enqueue_timeout = float(queue_enqueue_timeout)
        self.queue_processing_timeout = float(queue_processing_timeout)
        
        # Observability state (enhanced)
        self.recent_requests = deque(maxlen=50)
        self.endpoint_stats = defaultdict(lambda: {"count": 0, "avg_ms": 0.0, "max_ms": 0.0})
        self._request_timestamps = deque(maxlen=10000)
        
        # Client connection tracking
        self.active_connections = set()
        self.connection_events = deque(maxlen=1000)
        
        # Enhanced profiling system
        self.profiler_manager = ProfilerManager(
            connection_manager=self.enhanced_queue.connection_manager,
            request_queue=self.enhanced_queue
        )
        self.current_phase_profiler: Optional[EnhancedPhaseProfiler] = None
        
        # Server running state
        self.running = False
        
        self.setup_routes()
        self.setup_logging()
        self.setup_rate_limiter()
        self.setup_connection_handlers()
        self.setup_enhanced_logging()
        
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

        @self.app.route('/metrics')
        async def metrics():
            return await self.handle_metrics_request()

        @self.app.route('/dashboard')
        async def dashboard():
            return await self.handle_dashboard_request()
        
        @self.app.route('/api/queue-metrics')
        async def queue_metrics():
            """Get detailed queue metrics for analysis"""
            try:
                queue_metrics = await self.enhanced_queue.get_queue_metrics()
                return jsonify({
                    "status": "success",
                    "server_id": self.server_id,
                    "timestamp": datetime.now().isoformat(),
                    "queue_metrics": queue_metrics
                })
            except Exception as e:
                self.logger.error(f"Failed to get queue metrics: {e}")
                return jsonify({
                    "status": "error",
                    "error": "queue_metrics_failure",
                    "message": str(e)
                }), 500
        
        @self.app.route('/api/client-connections')
        async def client_connections():
            """Get detailed client connection information"""
            try:
                system_metrics = await self.enhanced_queue.connection_manager.get_system_metrics()
                return jsonify({
                    "status": "success",
                    "server_id": self.server_id,
                    "timestamp": datetime.now().isoformat(),
                    "connection_metrics": system_metrics,
                    "connection_events": list(self.connection_events)[-50:]  # Last 50 events
                })
            except Exception as e:
                self.logger.error(f"Failed to get connection metrics: {e}")
                return jsonify({
                    "status": "error",
                    "error": "connection_metrics_failure",
                    "message": str(e)
                }), 500
        
        @self.app.route('/api/profiling/start/<phase_name>', methods=['POST'])
        async def start_profiling(phase_name):
            """Start profiling a specific phase"""
            try:
                metadata = await request.get_json() if await request.get_data() else {}
                profiler = await self.profiler_manager.start_phase(phase_name, metadata)
                self.current_phase_profiler = profiler
                
                return jsonify({
                    "status": "success",
                    "message": f"Started profiling phase: {phase_name}",
                    "phase": phase_name,
                    "timestamp": datetime.now().isoformat()
                })
            except Exception as e:
                self.logger.error(f"Failed to start profiling: {e}")
                return jsonify({
                    "status": "error",
                    "error": "profiling_start_failure",
                    "message": str(e)
                }), 500
        
        @self.app.route('/api/profiling/stop/<phase_name>', methods=['POST'])
        async def stop_profiling(phase_name):
            """Stop profiling a specific phase"""
            try:
                await self.profiler_manager.stop_phase(phase_name)
                if self.current_phase_profiler and self.current_phase_profiler.phase_name == phase_name:
                    self.current_phase_profiler = None
                
                return jsonify({
                    "status": "success",
                    "message": f"Stopped profiling phase: {phase_name}",
                    "phase": phase_name,
                    "timestamp": datetime.now().isoformat()
                })
            except Exception as e:
                self.logger.error(f"Failed to stop profiling: {e}")
                return jsonify({
                    "status": "error",
                    "error": "profiling_stop_failure",
                    "message": str(e)
                }), 500

    def setup_connection_handlers(self):
        @self.app.before_serving
        async def start_enhanced_queue():
            await self.enhanced_queue.start()
            self.logger.info("Enhanced queue system started")

        @self.app.after_serving
        async def stop_enhanced_queue():
            await self.enhanced_queue.stop()
            self.logger.info("Enhanced queue system stopped")
        
        @self.app.before_request
        async def track_client_connection():
            try:
                # Register client connection
                client_ip = request.remote_addr or "unknown"
                user_agent = request.headers.get('User-Agent', 'unknown')
                
                client_id = await self.enhanced_queue.connection_manager.register_client(
                    client_ip, user_agent
                )
                
                # Store client ID in request context
                g.client_id = client_id
                
                # Track connection if new
                connection_key = f"{client_ip}:{user_agent[:50]}"
                if connection_key not in self.active_connections:
                    self.active_connections.add(connection_key)
                    self.connection_count += 1
                    
                    self.connection_events.append({
                        "timestamp": datetime.now().isoformat(),
                        "event": "connection_start",
                        "client_id": client_id,
                        "client_ip": client_ip,
                        "user_agent": user_agent[:100]
                    })
            except Exception as e:
                self.logger.error(f"Client connection tracking failed: {e}")
                # Provide fallback client ID
                g.client_id = f"fallback_{int(time.time())}"
        
        @self.app.after_request
        async def track_response_delivery(response):
            # This helps track if responses are being delivered
            client_id = getattr(g, 'client_id', None)
            if client_id:
                # We assume successful delivery if we reach here
                # In a real scenario, we'd need more sophisticated tracking
                pass
            return response

    async def handle_client_disconnection(self, client_id: str):
        """Handle client disconnection event"""
        await self.enhanced_queue.connection_manager.mark_client_disconnected(client_id)
        
        # Log disconnection
        self.connection_events.append({
            "timestamp": datetime.now().isoformat(),
            "event": "connection_end",
            "client_id": client_id
        })
        
        self.logger.info(f"Client {client_id} disconnected")
    
    def setup_enhanced_logging(self):
        """Setup comprehensive logging for all endpoints and queue states"""
        
        @self.app.before_request
        async def log_request_start():
            """Log detailed request start information"""
            client_id = getattr(g, 'client_id', 'unknown')
            
            request_log = {
                "event": "request_start",
                "timestamp": datetime.now().isoformat(),
                "server_id": self.server_id,
                "client_id": client_id,
                "method": request.method,
                "path": request.path,
                "query_string": request.query_string.decode() if request.query_string else "",
                "headers": dict(request.headers),
                "remote_addr": request.remote_addr,
                "user_agent": request.headers.get('User-Agent', 'unknown')
            }
            
            # Store in request context for later use
            g.request_start_log = request_log
            
            self.logger.info(json.dumps(request_log))
        
        @self.app.after_request
        async def log_request_complete(response):
            """Log detailed request completion information"""
            client_id = getattr(g, 'client_id', 'unknown')
            request_log = getattr(g, 'request_start_log', {})
            
            completion_log = {
                "event": "request_complete",
                "timestamp": datetime.now().isoformat(),
                "server_id": self.server_id,
                "client_id": client_id,
                "method": request.method,
                "path": request.path,
                "status_code": response.status_code,
                "response_headers": dict(response.headers),
                "content_length": response.headers.get('Content-Length', 'unknown')
            }
            
            # Add timing if available
            if request_log and 'timestamp' in request_log:
                try:
                    start_time = datetime.fromisoformat(request_log['timestamp'].replace('Z', '+00:00'))
                    end_time = datetime.now()
                    completion_log['total_response_time_ms'] = (end_time - start_time.replace(tzinfo=None)).total_seconds() * 1000
                except:
                    pass
            
            self.logger.info(json.dumps(completion_log))
            
            return response
        
        @self.app.teardown_request
        async def log_queue_state(exception):
            """Log queue state after each request"""
            try:
                if hasattr(self, 'running') and getattr(self, 'running', False):
                    queue_metrics = await self.enhanced_queue.get_queue_metrics()
                    
                    queue_log = {
                        "event": "queue_state",
                        "timestamp": datetime.now().isoformat(),
                        "server_id": self.server_id,
                        "queue_size": queue_metrics["queue"]["total_size"],
                        "queue_utilization": queue_metrics["queue"]["utilization_percent"],
                        "active_requests": queue_metrics["metrics"]["active_requests"],
                        "abandoned_requests": queue_metrics["metrics"]["total_abandoned"],
                        "worker_busy_count": sum(1 for w in queue_metrics["workers"] if w["busy"])
                    }
                    
                    # Only log if queue has significant activity
                    if queue_log["queue_size"] > 0 or queue_log["abandoned_requests"] > 0:
                        self.logger.debug(json.dumps(queue_log))
            except Exception as e:
                # Don't let logging errors break the request
                self.logger.debug(f"Queue state logging error: {e}")

    async def _process_request(self, method, path, extra_data=None):
        start_time = time.time()
        # Simulate realistic processing time
        processing_delay = random.uniform(0.01, 0.1)
        if "heavy" in path:
            processing_delay = random.uniform(0.5, 2.0)
        await asyncio.sleep(processing_delay)
        response_time = (time.time() - start_time) * 1000
        now_epoch = time.time()
        # Update in-memory observability statistics
        try:
            stats = self.endpoint_stats[path]
            stats["count"] += 1
            # Incremental average
            stats["avg_ms"] += (response_time - stats["avg_ms"]) / stats["count"]
            if response_time > stats["max_ms"]:
                stats["max_ms"] = response_time
            # Track recent requests
            self.recent_requests.append({
                "timestamp": datetime.now().isoformat(timespec='seconds'),
                "method": method,
                "path": path,
                "response_time_ms": round(response_time, 2),
            })
            # Track request timestamps for RPS
            self._request_timestamps.append(now_epoch)
        except Exception:
            pass
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
        return {
            "status": "success",
            "server_id": self.server_id,
            "timestamp": datetime.now().isoformat(),
            "processing_time": response_time,
            "data": extra_data or {"message": f"Response from {path}"}
        }

    def setup_rate_limiter(self):
        @self.app.before_request
        async def apply_rate_limit():
            client_ip = request.remote_addr or "unknown"
            # Fixed-window key per client IP (can be extended to include path)
            key = f"ip:{client_ip}"
            now = int(time.time())
            window_size = self.rate_limit_window_seconds
            window_start = now - (now % window_size)
            window_reset_epoch = window_start + window_size

            async with self._rate_limit_lock:
                bucket = self._rate_limit_buckets.get(key)
                if not bucket or bucket[0] != window_start:
                    # Start a new window
                    bucket = (window_start, 0)
                current_count = bucket[1]

                if current_count >= self.rate_limit_max_requests:
                    remaining = 0
                    retry_after = max(0, window_reset_epoch - now)
                    # Stash values for after_request header population
                    g.rate_limit_limit = self.rate_limit_max_requests
                    g.rate_limit_remaining = remaining
                    g.rate_limit_reset = window_reset_epoch
                    response = jsonify({
                        "status": "error",
                        "error": "rate_limited",
                        "message": "Too many requests",
                        "server_id": self.server_id
                    })
                    response.status_code = 429
                    response.headers["Retry-After"] = str(retry_after)
                    response.headers["X-RateLimit-Limit"] = str(self.rate_limit_max_requests)
                    response.headers["X-RateLimit-Remaining"] = str(remaining)
                    response.headers["X-RateLimit-Reset"] = str(window_reset_epoch)
                    return response

                # Allow request and increment
                current_count += 1
                self._rate_limit_buckets[key] = (window_start, current_count)
                g.rate_limit_limit = self.rate_limit_max_requests
                g.rate_limit_remaining = max(0, self.rate_limit_max_requests - current_count)
                g.rate_limit_reset = window_reset_epoch

        @self.app.after_request
        async def add_rate_limit_headers(response):
            # Add headers if available in context
            limit = getattr(g, "rate_limit_limit", None)
            remaining = getattr(g, "rate_limit_remaining", None)
            reset_epoch = getattr(g, "rate_limit_reset", None)
            if limit is not None and remaining is not None and reset_epoch is not None:
                response.headers["X-RateLimit-Limit"] = str(limit)
                response.headers["X-RateLimit-Remaining"] = str(remaining)
                response.headers["X-RateLimit-Reset"] = str(reset_epoch)
            return response
        
    async def handle_request(self, method, path, extra_data=None, priority: QueuePriority = QueuePriority.NORMAL):
        """Enhanced request handling with client tracking"""
        self.request_count += 1
        
        # Get client ID from request context
        client_id = getattr(g, 'client_id', None)
        if not client_id:
            # Fallback client registration
            client_ip = request.remote_addr or "unknown"
            user_agent = request.headers.get('User-Agent', 'unknown')
            client_id = await self.enhanced_queue.connection_manager.register_client(
                client_ip, user_agent
            )
        
        # Determine priority based on path
        if "heavy" in path:
            priority = QueuePriority.LOW
        elif "api" in path:
            priority = QueuePriority.HIGH
        elif path in ["/metrics", "/dashboard"]:
            priority = QueuePriority.CRITICAL
        
        try:
            # Enqueue with enhanced tracking
            future = await self.enhanced_queue.enqueue_request(
                client_id=client_id,
                method=method,
                path=path,
                extra_data=extra_data,
                priority=priority
            )
            
            # Wait for processing with timeout
            payload = await asyncio.wait_for(future, timeout=self.queue_processing_timeout)
            
            # Update metrics
            if payload.get("status") == "success":
                processing_time = payload.get("processing_time_ms", 0)
                self._update_endpoint_stats(path, processing_time)
                
                self.recent_requests.append({
                    "timestamp": datetime.now().isoformat(timespec='seconds'),
                    "method": method,
                    "path": path,
                    "response_time_ms": round(processing_time, 2),
                    "client_id": client_id
                })
                
                self._request_timestamps.append(time.time())
            
            return jsonify(payload)
            
        except asyncio.TimeoutError:
            response = jsonify({
                "status": "error",
                "error": "processing_timeout",
                "message": "Request timed out while waiting in queue.",
                "server_id": self.server_id,
                "client_id": client_id
            })
            response.status_code = 504
            return response
        
        except Exception as e:
            self.logger.error(f"Request handling failed: {e}")
            response = jsonify({
                "status": "error",
                "error": "request_failed",
                "message": str(e),
                "server_id": self.server_id,
                "client_id": client_id
            })
            response.status_code = 500
            return response
    
    def _update_endpoint_stats(self, path: str, processing_time: float):
        """Update endpoint statistics"""
        stats = self.endpoint_stats[path]
        stats["count"] += 1
        stats["avg_ms"] += (processing_time - stats["avg_ms"]) / stats["count"]
        if processing_time > stats["max_ms"]:
            stats["max_ms"] = processing_time
    
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

    async def handle_metrics_request(self):
        """Enhanced metrics including queue and client tracking"""
        try:
            # Get enhanced metrics
            queue_metrics = await self.enhanced_queue.get_queue_metrics()
            system_metrics = self._collect_system_metrics()
            
            # Combine all metrics
            combined_metrics = {
                **system_metrics,
                "enhanced_queue": queue_metrics,
                "connections": {
                    "active_connections": len(self.active_connections),
                    "total_connections": self.connection_count,
                    "recent_events": list(self.connection_events)[-10:]  # Last 10 events
                }
            }
            
            response = jsonify({
                "status": "success",
                "server_id": self.server_id,
                "timestamp": datetime.now().isoformat(),
                "metrics": combined_metrics,
            })
            response.status_code = 200
            return response
        except Exception as e:
            self.logger.error(f"Failed to collect enhanced metrics: {e}")
            response = jsonify({
                "status": "error",
                "error": "metrics_failure",
                "message": str(e),
                "server_id": self.server_id,
            })
            response.status_code = 500
            return response

    def _collect_system_metrics(self):
        # System-wide
        cpu_percent = psutil.cpu_percent(interval=None)
        vm = psutil.virtual_memory()
        load_avg = None
        try:
            load_avg = os.getloadavg()
        except Exception:
            load_avg = None

        # Per-process
        with self._process.oneshot():
            proc_cpu = self._process.cpu_percent(interval=None)
            proc_mem_info = self._process.memory_info()
            proc_mem_percent = self._process.memory_percent()

        # Request rates
        now_ts = time.time()
        # Drop timestamps older than 60s
        try:
            while self._request_timestamps and self._request_timestamps[0] < now_ts - 60:
                self._request_timestamps.popleft()
        except Exception:
            pass
        rps_60s = len(self._request_timestamps) / 60.0 if self._request_timestamps else 0.0
        rps_1s = sum(1 for t in self._request_timestamps if t >= now_ts - 1)

        # Rate limiter summary
        active_clients = len(self._rate_limit_buckets)
        total_in_window = 0
        try:
            for _, (_, count) in self._rate_limit_buckets.items():
                total_in_window += count
        except Exception:
            pass

        # Enhanced queue worker information is now provided by queue_metrics
        # This is handled in handle_metrics_request
        workers = []

        # Endpoint stats snapshot (top 10 by count)
        endpoints = []
        try:
            for path, s in sorted(self.endpoint_stats.items(), key=lambda kv: kv[1]["count"], reverse=True)[:10]:
                endpoints.append({
                    "path": path,
                    "count": s["count"],
                    "avg_ms": round(s["avg_ms"], 2),
                    "max_ms": round(s["max_ms"], 2),
                })
        except Exception:
            pass

        return {
            "system": {
                "cpu_percent": cpu_percent,
                "memory_percent": vm.percent,
                "memory": {
                    "total_mb": round(vm.total / (1024 * 1024), 2),
                    "available_mb": round(vm.available / (1024 * 1024), 2),
                    "used_mb": round(vm.used / (1024 * 1024), 2),
                    "free_mb": round(vm.free / (1024 * 1024), 2),
                },
                "load_avg": load_avg,
                "uptime_seconds": int(time.time() - self.start_time),
            },
            "process": {
                "cpu_percent": proc_cpu,
                "memory_percent": proc_mem_percent,
                "memory_rss_mb": round(proc_mem_info.rss / (1024 * 1024), 2),
                "memory_vms_mb": round(proc_mem_info.vms / (1024 * 1024), 2),
                "num_threads": self._process.num_threads(),
            },
            "server": {
                "queue_maxsize": self.queue_maxsize,
                "endpoints": endpoints,
                "recent_requests": list(self.recent_requests),
                "rps_1s": rps_1s,
                "rps_60s": round(rps_60s, 2),
                "rate_limit": {
                    "active_clients": active_clients,
                    "limit": self.rate_limit_max_requests,
                    "window_seconds": self.rate_limit_window_seconds,
                    "approx_total_in_window": total_in_window,
                },
                "connections": {
                    "active": len(self.active_connections),
                    "total": self.connection_count
                }
            },
        }

    async def handle_dashboard_request(self):
        try:
            return await render_template('dashboard.html', server_id=self.server_id)
        except Exception as e:
            self.logger.error(f"Failed to render dashboard: {e}")
            response = jsonify({
                "status": "error",
                "error": "dashboard_failure",
                "message": str(e),
                "server_id": self.server_id,
            })
            response.status_code = 500
            return response
    
    async def run(self):
        config = Config()
        config.bind = [f"{self.host}:{self.port}"]
        # Enable HTTP/2 when running over plaintext (h2c) and HTTP/1.1 fallback
        config.h2c = True
        config.alpn_protocols = ['h2', 'http/1.1']
        
        # Mark server as running for logging
        self.running = True
        
        self.logger.info(f"Starting enhanced HTTP/2 server on {self.host}:{self.port}")
        self.logger.info(f"Queue system: {self.queue_maxsize} max size, {self.queue_workers} workers")
        self.logger.info(f"Rate limiting: {self.rate_limit_max_requests} requests per {self.rate_limit_window_seconds}s")
        
        try:
            await serve(self.app, config)
        finally:
            self.running = False
            # Stop all profiling on server shutdown
            await self.profiler_manager.stop_all()
