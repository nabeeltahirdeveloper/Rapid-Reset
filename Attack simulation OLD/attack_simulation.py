import asyncio
import aiohttp
import ssl
import time
import random
import json
import logging
from datetime import datetime
from dataclasses import dataclass
from typing import List

@dataclass
class AttackConfig:
    name: str
    concurrent_streams: int
    request_rate: int  # requests per second
    duration_seconds: int
    reset_probability: float  # 0.0 to 1.0
    endpoints: List[str]
    user_agents: List[str]

# Define different attack intensities
ATTACK_CONFIGS = {
    'light': AttackConfig(
        name='Light Rapid Reset',
        concurrent_streams=20,
        request_rate=50,
        duration_seconds=30,
        reset_probability=0.8,
        endpoints=['/api/fast', '/api/medium'],
        user_agents=['LightAttacker/1.0', 'TestBot/1.0']
    ),
    'medium': AttackConfig(
        name='Medium Rapid Reset',
        concurrent_streams=50,
        request_rate=150,
        duration_seconds=60,
        reset_probability=0.9,
        endpoints=['/api/fast', '/api/medium', '/api/slow'],
        user_agents=['MediumAttacker/1.0', 'LoadTester/2.0']
    ),
    'heavy': AttackConfig(
        name='Heavy Rapid Reset',
        concurrent_streams=100,
        request_rate=300,
        duration_seconds=45,
        reset_probability=0.95,
        endpoints=['/api/fast', '/api/medium', '/api/slow', '/api/heavy'],
        user_agents=['HeavyAttacker/1.0', 'StressBot/3.0']
    ),
    'extreme': AttackConfig(
        name='Extreme Rapid Reset',
        concurrent_streams=200,
        request_rate=500,
        duration_seconds=30,
        reset_probability=0.98,
        endpoints=['/api/fast', '/api/medium', '/api/slow', '/api/heavy', '/api/data/1000'],
        user_agents=['ExtremeAttacker/1.0', 'MaxStress/4.0']
    )
}

# Setup attack logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/attack_simulation.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class RapidResetSimulator:
    def __init__(self, target_url='http://127.0.0.1:5000'):
        self.target_url = target_url
        self.ssl_context = ssl.create_default_context()
        self.ssl_context.check_hostname = False
        self.ssl_context.verify_mode = ssl.CERT_NONE
        
    async def simulate_request(self, session, config: AttackConfig, stream_id: int):
        """Simulate a single request with potential reset"""
        endpoint = random.choice(config.endpoints)
        user_agent = random.choice(config.user_agents)
        url = f"{self.target_url}{endpoint}"
        
        headers = {
            'User-Agent': user_agent,
            'Accept': 'application/json',
            'Connection': 'keep-alive'
        }
        
        try:
            # Decide if this request should be reset
            should_reset = random.random() < config.reset_probability
            timeout_duration = 0.05 if should_reset else 5.0
            
            timeout = aiohttp.ClientTimeout(total=timeout_duration)
            
            logger.debug(f"Stream {stream_id}: {'RESET' if should_reset else 'NORMAL'} -> {url}")
            
            async with session.get(url, headers=headers, timeout=timeout) as response:
                if not should_reset:
                    await response.text()
                    logger.debug(f"Stream {stream_id}: Completed normally")
                    
        except asyncio.TimeoutError:
            logger.debug(f"Stream {stream_id}: Timed out (reset simulation)")
        except Exception as e:
            logger.debug(f"Stream {stream_id}: Error - {e}")
    
    async def run_attack(self, config: AttackConfig):
        """Run attack simulation with specified configuration"""
        logger.info(f"Starting {config.name}")
        logger.info(f"Config: {config.concurrent_streams} streams, {config.request_rate} req/s, {config.duration_seconds}s")
        
        # Log attack start for ML training
        attack_start = {
            'event_type': 'attack_start',
            'timestamp': datetime.now().isoformat(),
            'attack_name': config.name,
            'config': config.__dict__
        }
        
        with open('logs/ml_training_data.jsonl', 'a') as f:
            f.write(json.dumps(attack_start) + '\n')
        
        connector = aiohttp.TCPConnector(
            limit=config.concurrent_streams * 2,
            limit_per_host=config.concurrent_streams * 2,
            ssl=self.ssl_context
        )
        
        timeout = aiohttp.ClientTimeout(total=30)
        
        async with aiohttp.ClientSession(
            connector=connector,
            timeout=timeout
        ) as session:
            
            start_time = time.time()
            stream_counter = 0
            total_requests = 0
            
            while time.time() - start_time < config.duration_seconds:
                batch_start = time.time()
                
                # Calculate how many requests to send in this batch
                requests_in_batch = min(config.concurrent_streams, config.request_rate)
                
                # Create batch of concurrent requests
                tasks = []
                for i in range(requests_in_batch):
                    stream_counter += 1
                    total_requests += 1
                    task = asyncio.create_task(
                        self.simulate_request(session, config, stream_counter)
                    )
                    tasks.append(task)
                
                # Wait for batch to complete
                await asyncio.gather(*tasks, return_exceptions=True)
                
                # Rate limiting - ensure we don't exceed target RPS
                batch_duration = time.time() - batch_start
                target_batch_duration = requests_in_batch / config.request_rate
                
                if batch_duration < target_batch_duration:
                    await asyncio.sleep(target_batch_duration - batch_duration)
                
                if stream_counter % 100 == 0:
                    elapsed = time.time() - start_time
                    current_rps = stream_counter / elapsed
                    logger.info(f"Streams: {stream_counter}, Rate: {current_rps:.1f} req/s")
        
        # Log attack end
        attack_end = {
            'event_type': 'attack_end',
            'timestamp': datetime.now().isoformat(),
            'attack_name': config.name,
            'total_requests': total_requests,
            'duration_seconds': time.time() - start_time
        }
        
        with open('logs/ml_training_data.jsonl', 'a') as f:
            f.write(json.dumps(attack_end) + '\n')
        
        logger.info(f"Attack completed: {total_requests} total requests")

async def run_attack_sequence():
    """Run sequence of different attack intensities"""
    simulator = RapidResetSimulator()
    
    for attack_name, config in ATTACK_CONFIGS.items():
        logger.info(f"\n{'='*50}")
        logger.info(f"STARTING: {config.name}")
        logger.info(f"{'='*50}")
        
        await simulator.run_attack(config)
        
        # Wait between attacks
        logger.info("Waiting 30 seconds before next attack...")
        await asyncio.sleep(30)
    
    logger.info("All attacks completed!")

if __name__ == '__main__':
    asyncio.run(run_attack_sequence())
