import asyncio
import httpx
import logging
from datetime import datetime
import json

class StreamingBot:
    def __init__(self, bot_id, target_servers):
        self.bot_id = bot_id
        self.target_servers = target_servers
        self.running = False
        self.setup_logging()
        
    def setup_logging(self):
        self.logger = logging.getLogger(f'streaming_bot_{self.bot_id}')
        handler = logging.FileHandler(f'logs/bot_logs/streaming_{self.bot_id}.log')
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        handler.setFormatter(formatter)
        self.logger.addHandler(handler)
    
    async def simulate_streaming_session(self, server_url):
        """Simulate long-running streaming connection"""
        async with httpx.AsyncClient(http2=True) as client:
            try:
                start_time = datetime.now()
                
                # Start streaming connection
                async with client.stream('GET', f"{server_url}/streaming", timeout=300) as response:
                    chunk_count = 0
                    async for chunk in response.aiter_bytes():
                        chunk_count += 1
                        
                        if chunk_count % 10 == 0:  # Log every 10th chunk
                            log_data = {
                                "bot_id": self.bot_id,
                                "bot_type": "streaming",
                                "timestamp": datetime.now().isoformat(),
                                "url": f"{server_url}/streaming",
                                "chunks_received": chunk_count,
                                "session_duration": (datetime.now() - start_time).total_seconds(),
                                "chunk_size": len(chunk)
                            }
                            self.logger.info(json.dumps(log_data))
                        
                        if not self.running:
                            break
                            
            except Exception as e:
                self.logger.error(f"Streaming session failed: {e}")
    
    async def run(self, duration=3600):
        self.running = True
        self.logger.info(f"Starting streaming bot {self.bot_id}")
        
        # Multiple concurrent streaming sessions
        tasks = []
        for _ in range(3):  # 3 concurrent streams
            server = random.choice(self.target_servers)
            task = asyncio.create_task(self.simulate_streaming_session(server))
            tasks.append(task)
        
        await asyncio.sleep(duration)
        self.running = False
        
        # Cancel all tasks
        for task in tasks:
            task.cancel()
        
        await asyncio.gather(*tasks, return_exceptions=True)
