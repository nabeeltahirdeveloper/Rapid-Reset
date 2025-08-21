import asyncio
import aiohttp
import random
import time
import json
import logging
from datetime import datetime
from typing import List

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - NORMAL_TRAFFIC - %(message)s',
    handlers=[
        logging.FileHandler('logs/normal_traffic.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class NormalTrafficGenerator:
    def __init__(self, target_url='http://127.0.0.1:5000'):
        self.target_url = target_url
        self.user_agents = [
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36',
            'Mozilla/5.0 (iPhone; CPU iPhone OS 14_7_1 like Mac OS X)',
            'Mozilla/5.0 (Android 11; Mobile; rv:91.0) Gecko/91.0'
        ]
        
        self.endpoints = [
            '/',
            '/api/fast',
            '/api/medium',
            '/api/slow',
            '/api/data/100',
            '/api/data/500'
        ]
        
        # Realistic usage patterns
        self.endpoint_weights = [0.3, 0.25, 0.2, 0.1, 0.1, 0.05]
        
    def generate_realistic_timing(self):
        """Generate realistic intervals between requests"""
        # Most requests have longer intervals (normal browsing)
        base_interval = random.uniform(1, 10)
        
        # Occasional bursts (user clicking multiple things)
        if random.random() < 0.1:  # 10% chance of burst
            return random.uniform(0.1, 0.5)
        
        # Normal browsing pattern
        return base_interval
    
    async def send_normal_request(self, session, request_id: int):
        """Send a normal, realistic HTTP request"""
        endpoint = random.choices(self.endpoints, weights=self.endpoint_weights)[0]
        user_agent = random.choice(self.user_agents)
        url = f"{self.target_url}{endpoint}"
        
        headers = {
            'User-Agent': user_agent,
            'Accept': 'application/json,text/html,application/xhtml+xml',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
            'Cache-Control': 'max-age=0'
        }
        
        try:
            logger.debug(f"Normal request {request_id}: {endpoint}")
            
            async with session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=30)) as response:
                await response.text()
                
                # Log successful normal request
                normal_request_log = {
                    'event_type': 'normal_request',
                    'timestamp': datetime.now().isoformat(),
                    'request_id': request_id,
                    'endpoint': endpoint,
                    'status_code': response.status,
                    'response_time_ms': 0,  # Would need to measure this
                    'user_agent': user_agent
                }
                
                with open('logs/ml_training_data.jsonl', 'a') as f:
                    f.write(json.dumps(normal_request_log) + '\n')
                
                logger.debug(f"Request {request_id} completed: {response.status}")
                
        except Exception as e:
            logger.warning(f"Normal request {request_id} failed: {e}")
    
    async def generate_traffic_pattern(self, duration_hours: float = 1.0):
        """Generate realistic traffic pattern"""
        logger.info(f"Starting normal traffic generation for {duration_hours} hours")
        
        # Log traffic generation start
        traffic_start = {
            'event_type': 'normal_traffic_start',
            'timestamp': datetime.now().isoformat(),
            'duration_hours': duration_hours
        }
        
        with open('logs/ml_training_data.jsonl', 'a') as f:
            f.write(json.dumps(traffic_start) + '\n')
        
        connector = aiohttp.TCPConnector(limit=10, limit_per_host=10)
        timeout = aiohttp.ClientTimeout(total=30)
        
        async with aiohttp.ClientSession(
            connector=connector,
            timeout=timeout
        ) as session:
            
            start_time = time.time()
            end_time = start_time + (duration_hours * 3600)
            request_count = 0
            
            while time.time() < end_time:
                # Send normal request
                request_count += 1
                await self.send_normal_request(session, request_count)
                
                # Wait realistic interval before next request
                interval = self.generate_realistic_timing()
                await asyncio.sleep(interval)
                
                # Log progress
                if request_count % 50 == 0:
                    elapsed_hours = (time.time() - start_time) / 3600
                    rate = request_count / (elapsed_hours * 3600) if elapsed_hours > 0 else 0
                    logger.info(f"Normal requests: {request_count}, Rate: {rate:.2f} req/s, Elapsed: {elapsed_hours:.2f}h")
        
        # Log traffic generation end
        total_duration = time.time() - start_time
        traffic_end = {
            'event_type': 'normal_traffic_end',
            'timestamp': datetime.now().isoformat(),
            'total_requests': request_count,
            'duration_seconds': total_duration,
            'average_rps': request_count / total_duration
        }
        
        with open('logs/ml_training_data.jsonl', 'a') as f:
            f.write(json.dumps(traffic_end) + '\n')
        
        logger.info(f"Normal traffic completed: {request_count} requests in {total_duration/3600:.2f} hours")

async def run_24_hour_baseline():
    """Run 24+ hours of baseline normal traffic"""
    generator = NormalTrafficGenerator()
    
    # Run for 25 hours to get a full day plus buffer
    await generator.generate_traffic_pattern(duration_hours=25.0)

if __name__ == '__main__':
    logger.info("Starting 24-hour normal traffic generation...")
    asyncio.run(run_24_hour_baseline())
