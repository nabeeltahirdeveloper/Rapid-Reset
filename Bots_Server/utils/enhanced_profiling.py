import asyncio
import time
import json
import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Set
from collections import defaultdict, deque
from datetime import datetime
import statistics
from enum import Enum

from .client_connection_manager import ClientConnectionManager, ConnectionState
from .enhanced_request_queue import EnhancedRequestQueue

class ProfilePhase(Enum):
    BASELINE = "baseline"
    NORMAL_TRAFFIC = "normal_traffic"
    ATTACK = "attack"
    RECOVERY = "recovery"

@dataclass
class AttackMetrics:
    """Metrics specific to attack analysis"""
    attack_start_time: float
    attack_duration: float
    peak_requests_per_second: float
    total_attack_requests: int
    total_reset_connections: int
    abandoned_requests_count: int
    server_recovery_time: float
    queue_overflow_count: int
    average_queue_size_during_attack: float
    max_queue_size_during_attack: int
    client_reconnection_attempts: int

@dataclass
class ClientBehaviorProfile:
    """Profile of individual client behavior during attacks"""
    client_id: str
    ip_address: str
    requests_before_disconnect: int
    abandonment_pattern: str  # "immediate", "delayed", "persistent"
    reconnection_attempts: int
    requests_after_reconnection: int
    total_queue_time_ms: float
    success_rate_before_attack: float
    success_rate_after_attack: float

class EnhancedPhaseProfiler:
    """Enhanced profiling system with focus on rapid reset attack analysis"""
    
    def __init__(self, 
                 phase_name: str,
                 connection_manager: ClientConnectionManager,
                 request_queue: EnhancedRequestQueue,
                 extra_metadata: Dict = None):
        
        self.phase_name = phase_name
        self.connection_manager = connection_manager
        self.request_queue = request_queue
        self.extra_metadata = extra_metadata or {}
        
        # Profiling state
        self.start_time: Optional[float] = None
        self.end_time: Optional[float] = None
        self.running = False
        
        # Metrics collection
        self.metrics_samples = deque(maxlen=10000)
        self.client_profiles: Dict[str, ClientBehaviorProfile] = {}
        self.attack_metrics: Optional[AttackMetrics] = None
        
        # Queue behavior tracking
        self.queue_size_samples = deque(maxlen=1000)
        self.abandoned_requests_timeline = deque(maxlen=1000)
        self.reconnection_events = deque(maxlen=1000)
        
        # Attack pattern detection
        self.request_rate_samples = deque(maxlen=100)
        self.connection_burst_detector = deque(maxlen=50)
        
        # Background task
        self.profiling_task: Optional[asyncio.Task] = None
        self.sampling_interval = 1.0  # seconds
        
        self.setup_logging()
    
    def setup_logging(self):
        self.logger = logging.getLogger(f'enhanced_profiler_{self.phase_name}')
        handler = logging.FileHandler(f'logs/phase_profiles/enhanced_{self.phase_name}_{int(time.time())}.jsonl')
        formatter = logging.Formatter('%(message)s')  # JSON only
        handler.setFormatter(formatter)
        self.logger.addHandler(handler)
        self.logger.setLevel(logging.INFO)
    
    async def start(self):
        """Start enhanced profiling"""
        if self.running:
            return
        
        self.start_time = time.time()
        self.running = True
        
        # Initialize baseline metrics
        await self._capture_baseline_metrics()
        
        # Start background profiling task
        self.profiling_task = asyncio.create_task(self._profiling_loop())
        
        self.logger.info(json.dumps({
            "event": "profiling_started",
            "phase": self.phase_name,
            "timestamp": datetime.now().isoformat(),
            "metadata": self.extra_metadata
        }))
    
    async def stop(self):
        """Stop enhanced profiling and generate report"""
        if not self.running:
            return
        
        self.running = False
        self.end_time = time.time()
        
        # Cancel background task
        if self.profiling_task:
            self.profiling_task.cancel()
            try:
                await self.profiling_task
            except asyncio.CancelledError:
                pass
        
        # Generate final report
        await self._generate_final_report()
        
        self.logger.info(json.dumps({
            "event": "profiling_stopped",
            "phase": self.phase_name,
            "timestamp": datetime.now().isoformat(),
            "duration": self.end_time - self.start_time,
            "total_samples": len(self.metrics_samples)
        }))
    
    async def _profiling_loop(self):
        """Background profiling loop"""
        try:
            while self.running:
                await self._capture_metrics_sample()
                await self._analyze_attack_patterns()
                await self._update_client_profiles()
                await asyncio.sleep(self.sampling_interval)
        except asyncio.CancelledError:
            pass
    
    async def _capture_baseline_metrics(self):
        """Capture baseline system state"""
        system_metrics = await self.connection_manager.get_system_metrics()
        queue_metrics = await self.request_queue.get_queue_metrics()
        
        baseline = {
            "timestamp": time.time(),
            "type": "baseline",
            "system": system_metrics,
            "queue": queue_metrics
        }
        
        self.metrics_samples.append(baseline)
        self.logger.info(json.dumps(baseline))
    
    async def _capture_metrics_sample(self):
        """Capture detailed metrics sample"""
        now = time.time()
        
        # Get system and queue metrics
        system_metrics = await self.connection_manager.get_system_metrics()
        queue_metrics = await self.request_queue.get_queue_metrics()
        
        # Calculate request rate
        current_rps = self._calculate_current_rps()
        self.request_rate_samples.append(current_rps)
        
        # Track queue size
        total_queue_size = queue_metrics["queue"]["total_size"]
        self.queue_size_samples.append({
            "timestamp": now,
            "size": total_queue_size,
            "utilization": queue_metrics["queue"]["utilization_percent"]
        })
        
        # Sample data
        sample = {
            "timestamp": now,
            "type": "sample",
            "phase": self.phase_name,
            "system": system_metrics,
            "queue": queue_metrics,
            "request_rate": current_rps,
            "abandoned_requests": len(self.request_queue.abandoned_requests),
            "active_connections": system_metrics["active_clients"]
        }
        
        self.metrics_samples.append(sample)
        self.logger.info(json.dumps(sample))
    
    def _calculate_current_rps(self) -> float:
        """Calculate current requests per second"""
        if len(self.request_rate_samples) < 2:
            return 0.0
        
        # Use last few samples to calculate RPS
        recent_samples = list(self.request_rate_samples)[-10:]
        if len(recent_samples) < 2:
            return 0.0
        
        # This is a simplified calculation - in practice you'd need more sophisticated RPS tracking
        return len(recent_samples)
    
    async def _analyze_attack_patterns(self):
        """Detect and analyze rapid reset attack patterns"""
        if len(self.request_rate_samples) < 10:
            return
        
        current_rps = self.request_rate_samples[-1]
        avg_rps = statistics.mean(list(self.request_rate_samples)[-10:])
        
        # Detect attack burst (RPS spike)
        if current_rps > avg_rps * 2 and current_rps > 50:
            burst_event = {
                "timestamp": time.time(),
                "type": "attack_burst_detected",
                "current_rps": current_rps,
                "average_rps": avg_rps,
                "burst_ratio": current_rps / max(1, avg_rps)
            }
            self.connection_burst_detector.append(burst_event)
            self.logger.info(json.dumps(burst_event))
        
        # Track queue overflow conditions
        queue_metrics = await self.request_queue.get_queue_metrics()
        if queue_metrics["queue"]["utilization_percent"] > 90:
            overflow_event = {
                "timestamp": time.time(),
                "type": "queue_overflow_risk",
                "utilization": queue_metrics["queue"]["utilization_percent"],
                "abandoned_requests": queue_metrics["metrics"]["total_abandoned"]
            }
            self.logger.info(json.dumps(overflow_event))
    
    async def _update_client_profiles(self):
        """Update client behavior profiles"""
        system_metrics = await self.connection_manager.get_system_metrics()
        
        # Track abandoned requests from disconnected clients
        for request in list(self.request_queue.abandoned_requests):
            if hasattr(request, 'client_id'):
                self.abandoned_requests_timeline.append({
                    "timestamp": time.time(),
                    "client_id": request.client_id,
                    "path": getattr(request, 'path', 'unknown'),
                    "queue_time_ms": (time.time() - getattr(request, 'queued_at', time.time())) * 1000
                })
        
        # Track reconnection events
        # This would be enhanced with actual connection event monitoring
        if system_metrics["total_reconnections"] > 0:
            self.reconnection_events.append({
                "timestamp": time.time(),
                "total_reconnections": system_metrics["total_reconnections"],
                "abandoned_clients": system_metrics["abandoned_clients"]
            })
    
    async def _generate_final_report(self):
        """Generate comprehensive final report"""
        if not self.start_time or not self.end_time:
            return
        
        duration = self.end_time - self.start_time
        
        # Calculate attack metrics if this was an attack phase
        if self.phase_name == "attack":
            await self._calculate_attack_metrics(duration)
        
        # Generate client behavior analysis
        await self._analyze_client_behavior()
        
        # Calculate queue performance metrics
        queue_performance = self._analyze_queue_performance()
        
        # Generate abandonment analysis
        abandonment_analysis = self._analyze_request_abandonment()
        
        # Generate comprehensive report
        final_report = {
            "timestamp": self.end_time,
            "type": "final_report",
            "phase": self.phase_name,
            "duration": duration,
            "total_samples": len(self.metrics_samples),
            "metadata": self.extra_metadata,
            "attack_metrics": self.attack_metrics.__dict__ if self.attack_metrics else None,
            "queue_performance": queue_performance,
            "abandonment_analysis": abandonment_analysis,
            "client_behavior_summary": self._summarize_client_behavior(),
            "key_insights": self._generate_key_insights()
        }
        
        self.logger.info(json.dumps(final_report))
        
        # Also write to separate report file
        report_file = f'logs/phase_profiles/report_{self.phase_name}_{int(self.start_time)}.json'
        with open(report_file, 'w') as f:
            json.dump(final_report, f, indent=2)
    
    async def _calculate_attack_metrics(self, duration: float):
        """Calculate detailed attack metrics"""
        if not self.metrics_samples:
            return
        
        # Find peak RPS
        peak_rps = max(self.request_rate_samples) if self.request_rate_samples else 0
        
        # Calculate queue metrics during attack
        queue_sizes = [sample["size"] for sample in self.queue_size_samples if sample["size"] > 0]
        avg_queue_size = statistics.mean(queue_sizes) if queue_sizes else 0
        max_queue_size = max(queue_sizes) if queue_sizes else 0
        
        # Count abandoned requests during this phase
        abandoned_count = len([req for req in self.abandoned_requests_timeline 
                             if req["timestamp"] >= self.start_time])
        
        self.attack_metrics = AttackMetrics(
            attack_start_time=self.start_time,
            attack_duration=duration,
            peak_requests_per_second=peak_rps,
            total_attack_requests=len(self.metrics_samples),
            total_reset_connections=len(self.connection_burst_detector),
            abandoned_requests_count=abandoned_count,
            server_recovery_time=0,  # Would be calculated based on queue recovery
            queue_overflow_count=len([s for s in self.queue_size_samples if s.get("utilization", 0) > 95]),
            average_queue_size_during_attack=avg_queue_size,
            max_queue_size_during_attack=max_queue_size,
            client_reconnection_attempts=len(self.reconnection_events)
        )
    
    async def _analyze_client_behavior(self):
        """Analyze individual client behavior patterns"""
        # This would be enhanced with actual client tracking
        # For now, provide framework for analysis
        pass
    
    def _analyze_queue_performance(self) -> Dict[str, Any]:
        """Analyze queue performance during the phase"""
        if not self.queue_size_samples:
            return {}
        
        sizes = [s["size"] for s in self.queue_size_samples]
        utilizations = [s["utilization"] for s in self.queue_size_samples]
        
        return {
            "average_queue_size": statistics.mean(sizes) if sizes else 0,
            "max_queue_size": max(sizes) if sizes else 0,
            "average_utilization": statistics.mean(utilizations) if utilizations else 0,
            "max_utilization": max(utilizations) if utilizations else 0,
            "queue_overflow_events": len([u for u in utilizations if u > 95]),
            "queue_stability": statistics.stdev(sizes) if len(sizes) > 1 else 0
        }
    
    def _analyze_request_abandonment(self) -> Dict[str, Any]:
        """Analyze request abandonment patterns"""
        if not self.abandoned_requests_timeline:
            return {}
        
        abandonment_times = [req["queue_time_ms"] for req in self.abandoned_requests_timeline]
        
        return {
            "total_abandoned": len(self.abandoned_requests_timeline),
            "average_queue_time_before_abandonment": statistics.mean(abandonment_times) if abandonment_times else 0,
            "max_queue_time_before_abandonment": max(abandonment_times) if abandonment_times else 0,
            "abandonment_rate_per_minute": len(self.abandoned_requests_timeline) / max(1, (self.end_time - self.start_time) / 60),
            "clients_with_abandoned_requests": len(set(req["client_id"] for req in self.abandoned_requests_timeline))
        }
    
    def _summarize_client_behavior(self) -> Dict[str, Any]:
        """Summarize client behavior patterns"""
        return {
            "total_clients_tracked": len(self.client_profiles),
            "reconnection_attempts": len(self.reconnection_events),
            "connection_bursts_detected": len(self.connection_burst_detector)
        }
    
    def _generate_key_insights(self) -> List[str]:
        """Generate key insights from the profiling data"""
        insights = []
        
        if self.attack_metrics:
            insights.append(f"Peak attack intensity: {self.attack_metrics.peak_requests_per_second:.1f} RPS")
            insights.append(f"Queue overflow events: {self.attack_metrics.queue_overflow_count}")
            insights.append(f"Requests abandoned: {self.attack_metrics.abandoned_requests_count}")
        
        if self.queue_size_samples:
            max_util = max(s["utilization"] for s in self.queue_size_samples)
            insights.append(f"Maximum queue utilization: {max_util:.1f}%")
        
        if self.abandoned_requests_timeline:
            abandonment_rate = len(self.abandoned_requests_timeline) / max(1, (self.end_time - self.start_time) / 60)
            insights.append(f"Request abandonment rate: {abandonment_rate:.1f} per minute")
        
        return insights

class ProfilerManager:
    """Manager for coordinating multiple profiling phases"""
    
    def __init__(self, connection_manager: ClientConnectionManager, request_queue: EnhancedRequestQueue):
        self.connection_manager = connection_manager
        self.request_queue = request_queue
        self.active_profilers: Dict[str, EnhancedPhaseProfiler] = {}
        self.profiling_history: List[Dict] = []
    
    async def start_phase(self, phase_name: str, extra_metadata: Dict = None) -> EnhancedPhaseProfiler:
        """Start profiling a new phase"""
        if phase_name in self.active_profilers:
            await self.stop_phase(phase_name)
        
        profiler = EnhancedPhaseProfiler(
            phase_name=phase_name,
            connection_manager=self.connection_manager,
            request_queue=self.request_queue,
            extra_metadata=extra_metadata
        )
        
        await profiler.start()
        self.active_profilers[phase_name] = profiler
        
        return profiler
    
    async def stop_phase(self, phase_name: str):
        """Stop profiling a phase"""
        if phase_name in self.active_profilers:
            profiler = self.active_profilers[phase_name]
            await profiler.stop()
            
            # Archive profiler results
            self.profiling_history.append({
                "phase_name": phase_name,
                "start_time": profiler.start_time,
                "end_time": profiler.end_time,
                "samples_collected": len(profiler.metrics_samples)
            })
            
            del self.active_profilers[phase_name]
    
    async def stop_all(self):
        """Stop all active profilers"""
        for phase_name in list(self.active_profilers.keys()):
            await self.stop_phase(phase_name)