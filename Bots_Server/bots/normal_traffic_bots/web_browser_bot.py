import asyncio
import random
import httpx
import logging
from datetime import datetime
import json

class WebBrowserBot:
    def __init__(self, bot_id, target_servers, request_rate=1.0):
        self.bot_id = bot_id
        self.target_servers = target_servers
        self.request_rate = request_rate  # requests per second
        self.running = False
        self.total_requests = 0
        self.setup_logging()
        
    def setup_logging(self):
        logging.basicConfig(level=logging.INFO)
        self.logger = logging.getLogger(f'web_browser_bot_{self.bot_id}')
        handler = logging.FileHandler(f'logs/bot_logs/web_browser_{self.bot_id}.log')
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        handler.setFormatter(formatter)
        self.logger.addHandler(handler)
    
    async def simulate_user_session(self, server_url):
        """Simulate realistic user browsing behavior"""
        user_agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36"
        ]
        
        session_requests = [
            "/",
            "/api/data",
            "/static/styles.css",
            "/static/script.js",
            "/api/user/profile",
            "/api/notifications"
        ]
        
        async with httpx.AsyncClient(http2=True) as client:
            # Simulate user session
            session_duration = random.uniform(30, 180)  # 30s to 3min
            session_start = asyncio.get_event_loop().time()
            
            headers = {"User-Agent": random.choice(user_agents)}
            
            while (asyncio.get_event_loop().time() - session_start) < session_duration and self.running:
                try:
                    # Random page request
                    endpoint = random.choice(session_requests)
                    url = f"{server_url}{endpoint}"
                    
                    start_time = datetime.now()
                    response = await client.get(url, headers=headers, timeout=10.0)
                    end_time = datetime.now()
                    
                    self.total_requests += 1
                    
                    # Log request details
                    log_data = {
                        "bot_id": self.bot_id,
                        "bot_type": "web_browser",
                        "timestamp": start_time.isoformat(),
                        "url": url,
                        "status_code": response.status_code,
                        "response_time_ms": (end_time - start_time).total_seconds() * 1000,
                        "request_number": self.total_requests,
                        "session_time": asyncio.get_event_loop().time() - session_start
                    }
                    
                    self.logger.info(json.dumps(log_data))
                    
                    # Realistic wait between requests
                    await asyncio.sleep(random.uniform(1, 5))
                    
                except Exception as e:
                    self.logger.error(f"Request failed: {e}")
                    await asyncio.sleep(1)
    
    async def run(self, duration=3600):
        """Run bot for specified duration"""
        self.running = True
        self.logger.info(f"Starting web browser bot {self.bot_id}")
        
        end_time = asyncio.get_event_loop().time() + duration
        
        while asyncio.get_event_loop().time() < end_time and self.running:
            # Select random server
            server = random.choice(self.target_servers)
            
            # Start user session
            await self.simulate_user_session(server)
            
            # Wait between sessions
            await asyncio.sleep(random.uniform(10, 30))
        
        self.logger.info(f"Web browser bot {self.bot_id} completed. Total requests: {self.total_requests}")
    
    def stop(self):
        self.running = False
