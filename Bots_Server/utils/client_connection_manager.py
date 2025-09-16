import asyncio
import time
import uuid
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set
from enum import Enum
from collections import defaultdict, deque
import logging
import json
from datetime import datetime

class ConnectionState(Enum):
    CONNECTED = "connected"
    DISCONNECTED = "disconnected"
    RECONNECTING = "reconnecting"
    ABANDONED = "abandoned"

@dataclass
class RequestMetadata:
    """Metadata for tracking individual requests"""
    request_id: str
    client_id: str
    method: str
    path: str
    timestamp: float
    queued_at: float
    processed_at: Optional[float] = None
    response_sent_at: Optional[float] = None
    response_delivered: bool = False
    abandoned: bool = False
    error: Optional[str] = None
    processing_time_ms: float = 0.0
    queue_wait_time_ms: float = 0.0

@dataclass
class ClientConnection:
    """Tracks individual client connection state"""
    client_id: str
    ip_address: str
    user_agent: str
    connection_start: float
    last_seen: float
    state: ConnectionState = ConnectionState.CONNECTED
    total_requests: int = 0
    successful_responses: int = 0
    failed_responses: int = 0
    abandoned_requests: int = 0
    pending_requests: Set[str] = field(default_factory=set)
    request_history: List[RequestMetadata] = field(default_factory=list)
    reset_timer: Optional[float] = None
    reconnection_count: int = 0

class ClientConnectionManager:
    """Manages client connections and tracks request lifecycle"""
    
    def __init__(self, reset_timeout=3.0, max_history_per_client=1000):
        self.reset_timeout = reset_timeout
        self.max_history_per_client = max_history_per_client
        self.clients: Dict[str, ClientConnection] = {}
        self.pending_requests: Dict[str, RequestMetadata] = {}
        self.abandoned_requests: deque = deque(maxlen=10000)
        self.lock = asyncio.Lock()
        
        # Metrics
        self.total_connections = 0
        self.total_reconnections = 0
        self.total_abandonments = 0
        
        self.setup_logging()
        
    def setup_logging(self):
        self.logger = logging.getLogger('client_connection_manager')
        handler = logging.FileHandler('logs/client_connections.log')
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        handler.setFormatter(formatter)
        self.logger.addHandler(handler)
        self.logger.setLevel(logging.INFO)
    
    def generate_client_id(self, ip_address: str, user_agent: str) -> str:
        """Generate unique client ID based on IP and User-Agent"""
        return f"{ip_address}_{hash(user_agent) % 10000}_{int(time.time() * 1000) % 10000}"
    
    async def register_client(self, ip_address: str, user_agent: str = "unknown") -> str:
        """Register a new client connection"""
        async with self.lock:
            client_id = self.generate_client_id(ip_address, user_agent)
            now = time.time()
            
            # Check if this is a reconnection
            existing_client = None
            for cid, client in self.clients.items():
                if (client.ip_address == ip_address and 
                    client.user_agent == user_agent and 
                    client.state in [ConnectionState.DISCONNECTED, ConnectionState.RECONNECTING]):
                    existing_client = client
                    break
            
            if existing_client:
                # This is a reconnection
                existing_client.state = ConnectionState.CONNECTED
                existing_client.last_seen = now
                existing_client.reconnection_count += 1
                self.total_reconnections += 1
                client_id = existing_client.client_id
                
                self.logger.info(json.dumps({
                    "event": "client_reconnection",
                    "client_id": client_id,
                    "ip_address": ip_address,
                    "reconnection_count": existing_client.reconnection_count,
                    "pending_requests": len(existing_client.pending_requests),
                    "timestamp": datetime.now().isoformat()
                }))
            else:
                # New client
                client = ClientConnection(
                    client_id=client_id,
                    ip_address=ip_address,
                    user_agent=user_agent,
                    connection_start=now,
                    last_seen=now
                )
                self.clients[client_id] = client
                self.total_connections += 1
                
                self.logger.info(json.dumps({
                    "event": "new_client_connection",
                    "client_id": client_id,
                    "ip_address": ip_address,
                    "user_agent": user_agent,
                    "timestamp": datetime.now().isoformat()
                }))
            
            return client_id
    
    async def register_request(self, client_id: str, method: str, path: str) -> str:
        """Register a new request from a client"""
        request_id = str(uuid.uuid4())
        now = time.time()
        
        async with self.lock:
            if client_id not in self.clients:
                # Create temporary client for unknown connections
                await self.register_client("unknown", "unknown")
            
            client = self.clients[client_id]
            client.last_seen = now
            client.total_requests += 1
            
            request_metadata = RequestMetadata(
                request_id=request_id,
                client_id=client_id,
                method=method,
                path=path,
                timestamp=now,
                queued_at=now
            )
            
            client.pending_requests.add(request_id)
            self.pending_requests[request_id] = request_metadata
            
            # Limit history size
            client.request_history.append(request_metadata)
            if len(client.request_history) > self.max_history_per_client:
                client.request_history.pop(0)
        
        return request_id
    
    async def mark_request_processing(self, request_id: str):
        """Mark request as being processed"""
        now = time.time()
        async with self.lock:
            if request_id in self.pending_requests:
                request = self.pending_requests[request_id]
                request.processed_at = now
                request.queue_wait_time_ms = (now - request.queued_at) * 1000
    
    async def mark_request_completed(self, request_id: str, success: bool = True, error: str = None):
        """Mark request as completed and response sent"""
        now = time.time()
        async with self.lock:
            if request_id not in self.pending_requests:
                return
            
            request = self.pending_requests[request_id]
            client = self.clients.get(request.client_id)
            
            if not client:
                return
            
            request.response_sent_at = now
            if request.processed_at:
                request.processing_time_ms = (now - request.processed_at) * 1000
            
            if success:
                client.successful_responses += 1
                request.response_delivered = True
            else:
                client.failed_responses += 1
                request.error = error
            
            # Remove from pending
            client.pending_requests.discard(request_id)
            del self.pending_requests[request_id]
            
            self.logger.info(json.dumps({
                "event": "request_completed",
                "request_id": request_id,
                "client_id": request.client_id,
                "method": request.method,
                "path": request.path,
                "success": success,
                "processing_time_ms": request.processing_time_ms,
                "queue_wait_time_ms": request.queue_wait_time_ms,
                "timestamp": datetime.now().isoformat()
            }))
    
    async def mark_client_disconnected(self, client_id: str):
        """Mark client as disconnected and start reset timer"""
        now = time.time()
        async with self.lock:
            if client_id not in self.clients:
                return
            
            client = self.clients[client_id]
            client.state = ConnectionState.DISCONNECTED
            client.last_seen = now
            client.reset_timer = now + self.reset_timeout
            
            # Mark pending requests as potentially abandoned
            abandoned_count = len(client.pending_requests)
            for request_id in client.pending_requests.copy():
                if request_id in self.pending_requests:
                    request = self.pending_requests[request_id]
                    self.abandoned_requests.append(request)
                    client.abandoned_requests += 1
                    self.total_abandonments += 1
            
            self.logger.info(json.dumps({
                "event": "client_disconnected",
                "client_id": client_id,
                "ip_address": client.ip_address,
                "pending_requests_abandoned": abandoned_count,
                "reset_timer_expires": client.reset_timer,
                "timestamp": datetime.now().isoformat()
            }))
    
    async def cleanup_expired_clients(self):
        """Clean up clients whose reset timer has expired"""
        now = time.time()
        expired_clients = []
        
        async with self.lock:
            for client_id, client in self.clients.items():
                if (client.state == ConnectionState.DISCONNECTED and 
                    client.reset_timer and 
                    now > client.reset_timer):
                    client.state = ConnectionState.ABANDONED
                    expired_clients.append(client_id)
            
            for client_id in expired_clients:
                client = self.clients[client_id]
                self.logger.info(json.dumps({
                    "event": "client_abandoned",
                    "client_id": client_id,
                    "ip_address": client.ip_address,
                    "total_requests": client.total_requests,
                    "abandoned_requests": client.abandoned_requests,
                    "connection_duration": now - client.connection_start,
                    "timestamp": datetime.now().isoformat()
                }))
    
    async def get_client_stats(self, client_id: str) -> Optional[Dict]:
        """Get detailed statistics for a specific client"""
        async with self.lock:
            if client_id not in self.clients:
                return None
            
            client = self.clients[client_id]
            return {
                "client_id": client.client_id,
                "ip_address": client.ip_address,
                "state": client.state.value,
                "connection_start": client.connection_start,
                "last_seen": client.last_seen,
                "total_requests": client.total_requests,
                "successful_responses": client.successful_responses,
                "failed_responses": client.failed_responses,
                "abandoned_requests": client.abandoned_requests,
                "pending_requests_count": len(client.pending_requests),
                "reconnection_count": client.reconnection_count,
                "success_rate": client.successful_responses / max(1, client.total_requests)
            }
    
    async def get_system_metrics(self) -> Dict:
        """Get overall system metrics"""
        async with self.lock:
            active_clients = sum(1 for c in self.clients.values() if c.state == ConnectionState.CONNECTED)
            disconnected_clients = sum(1 for c in self.clients.values() if c.state == ConnectionState.DISCONNECTED)
            abandoned_clients = sum(1 for c in self.clients.values() if c.state == ConnectionState.ABANDONED)
            total_pending = len(self.pending_requests)
            total_abandoned = len(self.abandoned_requests)
            
            return {
                "total_connections": self.total_connections,
                "active_clients": active_clients,
                "disconnected_clients": disconnected_clients,
                "abandoned_clients": abandoned_clients,
                "total_reconnections": self.total_reconnections,
                "total_abandonments": self.total_abandonments,
                "pending_requests": total_pending,
                "abandoned_requests": total_abandoned,
                "clients_with_pending_requests": sum(1 for c in self.clients.values() if c.pending_requests)
            }