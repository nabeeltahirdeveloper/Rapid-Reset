import asyncio
import time
import json
import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Callable, Any
from collections import defaultdict, deque
from datetime import datetime
from enum import Enum

from .client_connection_manager import ClientConnectionManager

class QueuePriority(Enum):
    LOW = 1
    NORMAL = 2
    HIGH = 3
    CRITICAL = 4

@dataclass
class QueuedRequest:
    """Enhanced request object with tracking capabilities"""
    request_id: str
    client_id: str
    method: str
    path: str
    extra_data: Optional[Dict] = None
    future: Optional[asyncio.Future] = None
    priority: QueuePriority = QueuePriority.NORMAL
    queued_at: float = field(default_factory=time.time)
    attempts: int = 0
    max_attempts: int = 3
    timeout: float = 30.0
    abandoned: bool = False

@dataclass
class WorkerMetrics:
    """Enhanced worker metrics"""
    worker_id: int
    busy: bool = False
    current_request_id: Optional[str] = None
    last_path: Optional[str] = None
    last_started_at: Optional[float] = None
    last_finished_at: Optional[float] = None
    total_processed: int = 0
    total_abandoned: int = 0
    total_errors: int = 0
    avg_processing_time_ms: float = 0.0

class EnhancedRequestQueue:
    """Enhanced request queue with client tracking and abandonment detection"""
    
    def __init__(self, 
                 maxsize: int = 1000,
                 workers: int = 4,
                 enqueue_timeout: float = 0.25,
                 processing_timeout: float = 30.0,
                 cleanup_interval: float = 5.0):
        
        self.maxsize = maxsize
        self.workers = workers
        self.enqueue_timeout = enqueue_timeout
        self.processing_timeout = processing_timeout
        self.cleanup_interval = cleanup_interval
        
        # Separate queues by priority
        self.priority_queues = {
            QueuePriority.CRITICAL: asyncio.Queue(maxsize=maxsize // 4),
            QueuePriority.HIGH: asyncio.Queue(maxsize=maxsize // 4),
            QueuePriority.NORMAL: asyncio.Queue(maxsize=maxsize // 2),
            QueuePriority.LOW: asyncio.Queue(maxsize=maxsize // 4)
        }
        
        # Worker management
        self.worker_tasks: List[asyncio.Task] = []
        self.worker_metrics: Dict[int, WorkerMetrics] = {}
        
        # Client connection manager
        self.connection_manager = ClientConnectionManager()
        
        # Queue metrics
        self.total_enqueued = 0
        self.total_processed = 0
        self.total_abandoned = 0
        self.total_errors = 0
        self.total_timeouts = 0
        
        # Request tracking
        self.active_requests: Dict[str, QueuedRequest] = {}
        self.abandoned_requests: deque = deque(maxlen=10000)
        self.processing_times: deque = deque(maxlen=1000)
        
        # Background tasks
        self.cleanup_task: Optional[asyncio.Task] = None
        self.running = False
        
        self.setup_logging()
    
    def setup_logging(self):
        self.logger = logging.getLogger('enhanced_request_queue')
        handler = logging.FileHandler('logs/queue_metrics.log')
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        handler.setFormatter(formatter)
        self.logger.addHandler(handler)
        self.logger.setLevel(logging.INFO)
    
    async def start(self):
        """Start the queue system and workers"""
        if self.running:
            return
        
        self.running = True
        
        # Initialize worker metrics
        for i in range(self.workers):
            self.worker_metrics[i] = WorkerMetrics(worker_id=i)
        
        # Start worker tasks
        for i in range(self.workers):
            task = asyncio.create_task(self._worker_loop(i))
            self.worker_tasks.append(task)
        
        # Start cleanup task
        self.cleanup_task = asyncio.create_task(self._cleanup_loop())
        
        self.logger.info(f"Enhanced queue system started with {self.workers} workers")
    
    async def stop(self):
        """Stop the queue system"""
        if not self.running:
            return
        
        self.running = False
        
        # Cancel cleanup task
        if self.cleanup_task:
            self.cleanup_task.cancel()
            try:
                await self.cleanup_task
            except asyncio.CancelledError:
                pass
        
        # Cancel worker tasks
        for task in self.worker_tasks:
            task.cancel()
        
        await asyncio.gather(*self.worker_tasks, return_exceptions=True)
        self.worker_tasks.clear()
        
        self.logger.info("Enhanced queue system stopped")
    
    def _select_queue_by_priority(self) -> Optional[asyncio.Queue]:
        """Select next queue based on priority"""
        for priority in [QueuePriority.CRITICAL, QueuePriority.HIGH, 
                        QueuePriority.NORMAL, QueuePriority.LOW]:
            queue = self.priority_queues[priority]
            if not queue.empty():
                return queue
        return None
    
    async def _worker_loop(self, worker_id: int):
        """Enhanced worker loop with client tracking"""
        worker = self.worker_metrics[worker_id]
        
        try:
            while self.running:
                # Select queue by priority
                selected_queue = self._select_queue_by_priority()
                if not selected_queue:
                    await asyncio.sleep(0.01)  # Brief wait if no requests
                    continue
                
                try:
                    # Get request with timeout
                    queued_request: QueuedRequest = await asyncio.wait_for(
                        selected_queue.get(), timeout=1.0
                    )
                except asyncio.TimeoutError:
                    continue
                
                # Update worker state
                worker.busy = True
                worker.current_request_id = queued_request.request_id
                worker.last_path = queued_request.path
                worker.last_started_at = time.time()
                
                # Check if client is still connected
                client_stats = await self.connection_manager.get_client_stats(queued_request.client_id)
                if not client_stats or client_stats["state"] != "connected":
                    # Client disconnected, mark as abandoned
                    await self._handle_abandoned_request(queued_request, worker)
                    continue
                
                # Mark request as processing
                await self.connection_manager.mark_request_processing(queued_request.request_id)
                
                try:
                    # Process the request
                    result = await self._process_request(queued_request)
                    
                    # Check if future is still valid (client hasn't disconnected)
                    if queued_request.future and not queued_request.future.done():
                        queued_request.future.set_result(result)
                        await self.connection_manager.mark_request_completed(
                            queued_request.request_id, success=True
                        )
                    else:
                        # Future was cancelled (client disconnected)
                        await self._handle_abandoned_request(queued_request, worker)
                        continue
                
                except Exception as e:
                    self.logger.error(f"Request processing failed: {e}")
                    worker.total_errors += 1
                    self.total_errors += 1
                    
                    error_result = {
                        "status": "error",
                        "error": "processing_failed",
                        "message": str(e)
                    }
                    
                    if queued_request.future and not queued_request.future.done():
                        queued_request.future.set_result(error_result)
                        await self.connection_manager.mark_request_completed(
                            queued_request.request_id, success=False, error=str(e)
                        )
                    else:
                        await self._handle_abandoned_request(queued_request, worker)
                        continue
                
                # Update worker metrics
                processing_time = time.time() - worker.last_started_at
                worker.total_processed += 1
                worker.avg_processing_time_ms = (
                    (worker.avg_processing_time_ms * (worker.total_processed - 1) + 
                     processing_time * 1000) / worker.total_processed
                )
                self.processing_times.append(processing_time * 1000)
                self.total_processed += 1
                
                # Clean up
                self.active_requests.pop(queued_request.request_id, None)
                worker.busy = False
                worker.current_request_id = None
                worker.last_finished_at = time.time()
                
                # Mark queue task as done
                selected_queue.task_done()
                
        except asyncio.CancelledError:
            worker.busy = False
            worker.current_request_id = None
    
    async def _handle_abandoned_request(self, queued_request: QueuedRequest, worker: WorkerMetrics):
        """Handle abandoned request"""
        queued_request.abandoned = True
        self.abandoned_requests.append(queued_request)
        worker.total_abandoned += 1
        self.total_abandoned += 1
        
        # Clean up
        self.active_requests.pop(queued_request.request_id, None)
        worker.busy = False
        worker.current_request_id = None
        worker.last_finished_at = time.time()
        
        self.logger.info(json.dumps({
            "event": "request_abandoned",
            "request_id": queued_request.request_id,
            "client_id": queued_request.client_id,
            "path": queued_request.path,
            "queue_time_ms": (time.time() - queued_request.queued_at) * 1000,
            "timestamp": datetime.now().isoformat()
        }))
    
    async def _process_request(self, queued_request: QueuedRequest) -> Dict[str, Any]:
        """Process individual request (simulated processing)"""
        import random
        
        # Simulate processing time based on endpoint
        if "heavy" in queued_request.path:
            processing_delay = random.uniform(0.5, 2.0)
        else:
            processing_delay = random.uniform(0.01, 0.1)
        
        await asyncio.sleep(processing_delay)
        
        return {
            "status": "success",
            "request_id": queued_request.request_id,
            "client_id": queued_request.client_id,
            "timestamp": datetime.now().isoformat(),
            "processing_time_ms": processing_delay * 1000,
            "data": queued_request.extra_data or {"message": f"Response from {queued_request.path}"}
        }
    
    async def _cleanup_loop(self):
        """Background cleanup of expired requests and clients"""
        try:
            while self.running:
                await asyncio.sleep(self.cleanup_interval)
                
                # Clean up expired clients
                await self.connection_manager.cleanup_expired_clients()
                
                # Check for timed out requests
                now = time.time()
                timed_out_requests = []
                
                for request_id, request in self.active_requests.items():
                    if now - request.queued_at > request.timeout:
                        timed_out_requests.append(request_id)
                
                for request_id in timed_out_requests:
                    request = self.active_requests.get(request_id)
                    if request:
                        if request.future and not request.future.done():
                            timeout_result = {
                                "status": "error",
                                "error": "queue_timeout",
                                "message": "Request timed out in queue"
                            }
                            request.future.set_result(timeout_result)
                        
                        await self._handle_abandoned_request(request, 
                                                           WorkerMetrics(worker_id=-1))
                        self.total_timeouts += 1
                
        except asyncio.CancelledError:
            pass
    
    async def enqueue_request(self, 
                            client_id: str, 
                            method: str, 
                            path: str, 
                            extra_data: Optional[Dict] = None,
                            priority: QueuePriority = QueuePriority.NORMAL) -> asyncio.Future:
        """Enqueue a request with client tracking"""
        
        # Register request with connection manager
        request_id = await self.connection_manager.register_request(client_id, method, path)
        
        # Create future for response
        future = asyncio.get_event_loop().create_future()
        
        # Create queued request
        queued_request = QueuedRequest(
            request_id=request_id,
            client_id=client_id,
            method=method,
            path=path,
            extra_data=extra_data,
            future=future,
            priority=priority
        )
        
        # Add to active requests
        self.active_requests[request_id] = queued_request
        
        try:
            # Select appropriate queue
            queue = self.priority_queues[priority]
            await asyncio.wait_for(queue.put(queued_request), timeout=self.enqueue_timeout)
            
            self.total_enqueued += 1
            
            self.logger.debug(json.dumps({
                "event": "request_enqueued",
                "request_id": request_id,
                "client_id": client_id,
                "method": method,
                "path": path,
                "priority": priority.name,
                "queue_size": queue.qsize(),
                "timestamp": datetime.now().isoformat()
            }))
            
            return future
            
        except asyncio.TimeoutError:
            # Queue is full
            self.active_requests.pop(request_id, None)
            future.set_result({
                "status": "error",
                "error": "queue_full",
                "message": "Server is busy. Please retry later."
            })
            return future
    
    async def get_queue_metrics(self) -> Dict[str, Any]:
        """Get comprehensive queue metrics"""
        queue_sizes = {
            priority.name: queue.qsize() 
            for priority, queue in self.priority_queues.items()
        }
        
        total_queue_size = sum(queue_sizes.values())
        
        # Worker status
        workers = [
            {
                "worker_id": worker.worker_id,
                "busy": worker.busy,
                "current_request_id": worker.current_request_id,
                "last_path": worker.last_path,
                "last_started_at": worker.last_started_at,
                "last_finished_at": worker.last_finished_at,
                "total_processed": worker.total_processed,
                "total_abandoned": worker.total_abandoned,
                "total_errors": worker.total_errors,
                "avg_processing_time_ms": round(worker.avg_processing_time_ms, 2)
            }
            for worker in self.worker_metrics.values()
        ]
        
        # System metrics
        system_metrics = await self.connection_manager.get_system_metrics()
        
        return {
            "queue": {
                "total_size": total_queue_size,
                "max_size": self.maxsize,
                "by_priority": queue_sizes,
                "utilization_percent": (total_queue_size / self.maxsize) * 100
            },
            "workers": workers,
            "metrics": {
                "total_enqueued": self.total_enqueued,
                "total_processed": self.total_processed,
                "total_abandoned": self.total_abandoned,
                "total_errors": self.total_errors,
                "total_timeouts": self.total_timeouts,
                "active_requests": len(self.active_requests),
                "abandonment_rate": (self.total_abandoned / max(1, self.total_enqueued)) * 100,
                "error_rate": (self.total_errors / max(1, self.total_processed)) * 100,
                "avg_processing_time_ms": sum(self.processing_times) / max(1, len(self.processing_times))
            },
            "clients": system_metrics
        }