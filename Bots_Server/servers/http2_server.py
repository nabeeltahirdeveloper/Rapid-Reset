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
from typing import Dict, Tuple
import psutil
from datetime import datetime

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
        # Queue configuration
        self.queue_maxsize = int(queue_maxsize)
        self.queue_workers = int(queue_workers)
        self.queue_enqueue_timeout = float(queue_enqueue_timeout)
        self.queue_processing_timeout = float(queue_processing_timeout)
        self.request_queue: asyncio.Queue = asyncio.Queue(maxsize=self.queue_maxsize)
        self.worker_tasks = []
        # Observability state
        self.recent_requests = deque(maxlen=50)
        self.worker_status = {}
        self.endpoint_stats = defaultdict(lambda: {"count": 0, "avg_ms": 0.0, "max_ms": 0.0})
        self._request_timestamps = deque(maxlen=10000)
        self.setup_routes()
        self.setup_logging()
        self.setup_rate_limiter()
        self.setup_queue_workers()
        
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

    def setup_queue_workers(self):
        @self.app.before_serving
        async def start_workers():
            for i in range(self.queue_workers):
                self.worker_status[i] = {
                    "worker_id": i,
                    "busy": False,
                    "last_path": None,
                    "last_started_at": None,
                    "last_finished_at": None,
                }
                task = asyncio.create_task(self._worker_loop(i))
                self.worker_tasks.append(task)

        @self.app.after_serving
        async def stop_workers():
            for task in self.worker_tasks:
                task.cancel()
            await asyncio.gather(*self.worker_tasks, return_exceptions=True)

    async def _worker_loop(self, worker_id: int):
        try:
            while True:
                job = await self.request_queue.get()
                method = job.get("method")
                path = job.get("path")
                extra_data = job.get("extra_data")
                future: asyncio.Future = job.get("future")
                try:
                    # Mark worker busy
                    status = self.worker_status.get(worker_id)
                    if status is not None:
                        status["busy"] = True
                        status["last_path"] = path
                        status["last_started_at"] = time.time()
                    result_payload = await self._process_request(method, path, extra_data)
                    if not future.done():
                        future.set_result(result_payload)
                except Exception as e:
                    if not future.done():
                        future.set_result({
                            "status": "error",
                            "error": "processing_failed",
                            "message": str(e),
                            "server_id": self.server_id
                        })
                finally:
                    # Mark worker idle
                    status = self.worker_status.get(worker_id)
                    if status is not None:
                        status["busy"] = False
                        status["last_finished_at"] = time.time()
                    self.request_queue.task_done()
        except asyncio.CancelledError:
            return

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
        
    async def handle_request(self, method, path, extra_data=None):
        self.request_count += 1
        future: asyncio.Future = asyncio.get_event_loop().create_future()
        job = {"method": method, "path": path, "extra_data": extra_data, "future": future}
        try:
            await asyncio.wait_for(self.request_queue.put(job), timeout=self.queue_enqueue_timeout)
        except asyncio.TimeoutError:
            response = jsonify({
                "status": "error",
                "error": "queue_full",
                "message": "Server is busy. Please retry later.",
                "server_id": self.server_id
            })
            response.status_code = 503
            response.headers["Retry-After"] = "1"
            return response
        
        try:
            payload = await asyncio.wait_for(future, timeout=self.queue_processing_timeout)
        except asyncio.TimeoutError:
            response = jsonify({
                "status": "error",
                "error": "processing_timeout",
                "message": "Request timed out while waiting in queue.",
                "server_id": self.server_id
            })
            response.status_code = 504
            return response
        
        return jsonify(payload)
    
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
        try:
            system_metrics = self._collect_system_metrics()
            response = jsonify({
                "status": "success",
                "server_id": self.server_id,
                "timestamp": datetime.now().isoformat(),
                "metrics": system_metrics,
            })
            response.status_code = 200
            return response
        except Exception as e:
            self.logger.error(f"Failed to collect metrics: {e}")
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

        # Workers snapshot
        workers = []
        for wid in sorted(self.worker_status.keys()):
            st = self.worker_status[wid]
            workers.append({
                "worker_id": wid,
                "busy": bool(st.get("busy")),
                "last_path": st.get("last_path"),
                "last_started_at": st.get("last_started_at"),
                "last_finished_at": st.get("last_finished_at"),
            })

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
                "queue_size": self.request_queue.qsize(),
                "queue_maxsize": self.queue_maxsize,
                "workers": workers,
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
        
        self.logger.info(f"Starting HTTP/2 server on {self.host}:{self.port}")
        await serve(self.app, config)
