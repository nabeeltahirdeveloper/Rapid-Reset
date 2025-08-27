import asyncio
import yaml
import logging
from datetime import datetime
import random

from bots.normal_traffic_bots.web_browser_bot import WebBrowserBot
from bots.normal_traffic_bots.streaming_bot import StreamingBot
from bots.attack_bots.rapid_reset_bot import RapidResetBot

class BotController:
    def __init__(self, config_file="config/bot_configs.yaml"):
        with open(config_file, 'r') as f:
            self.config = yaml.safe_load(f)
        
        self.bots = []
        self.running = False
        self.setup_logging()
    
    def setup_logging(self):
        logging.basicConfig(level=logging.INFO)
        self.logger = logging.getLogger('bot_controller')
        handler = logging.FileHandler('logs/bot_controller.log')
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        handler.setFormatter(formatter)
        self.logger.addHandler(handler)
    
    def create_bots(self):
        """Create all bots based on configuration"""
        servers = self.config['servers']
        
        # Create normal traffic bots
        for i in range(self.config['normal_bots']['web_browser_count']):
            bot = WebBrowserBot(
                bot_id=f"web_{i}",
                target_servers=servers,
                request_rate=random.uniform(0.5, 2.0)
            )
            self.bots.append(bot)
        
        for i in range(self.config['normal_bots']['streaming_count']):
            bot = StreamingBot(
                bot_id=f"stream_{i}",
                target_servers=servers
            )
            self.bots.append(bot)
        
        # Create attack bots
        for i, intensity in enumerate(self.config['attack_bots']['rapid_reset']['intensities']):
            for j in range(self.config['attack_bots']['rapid_reset']['count_per_intensity']):
                bot = RapidResetBot(
                    bot_id=f"attack_{intensity}_{j}",
                    target_host="localhost",  # Adjust based on your setup
                    target_port=8000,
                    attack_intensity=intensity
                )
                self.bots.append(bot)
    
    async def run_scenario(self, scenario_name, duration=3600):
        """Run specific scenario"""
        scenario = self.config['scenarios'][scenario_name]
        self.logger.info(f"Starting scenario: {scenario_name}")
        
        tasks = []
        
        # Normal traffic phase
        if scenario.get('normal_traffic_duration', 0) > 0:
            self.logger.info("Starting normal traffic phase")
            for bot in self.bots:
                if 'attack' not in bot.__class__.__name__.lower():
                    task = asyncio.create_task(
                        bot.run(duration=scenario['normal_traffic_duration'])
                    )
                    tasks.append(task)
        
        # Wait for normal traffic to establish baseline
        if scenario.get('baseline_duration', 0) > 0:
            await asyncio.sleep(scenario['baseline_duration'])
        
        # Attack phase
        if scenario.get('attack_duration', 0) > 0:
            self.logger.info("Starting attack phase")
            for bot in self.bots:
                if 'attack' in bot.__class__.__name__.lower():
                    task = asyncio.create_task(
                        bot.run(duration=scenario['attack_duration'])
                    )
                    tasks.append(task)
        
        # Wait for all tasks to complete
        await asyncio.gather(*tasks, return_exceptions=True)
        self.logger.info(f"Scenario {scenario_name} completed")
    
    async def run_continuous_simulation(self, duration=3600):
        """Run continuous mixed simulation"""
        self.running = True
        end_time = asyncio.get_event_loop().time() + duration
        
        while asyncio.get_event_loop().time() < end_time and self.running:
            # Randomly select scenario
            scenario_name = random.choice(list(self.config['scenarios'].keys()))
            scenario_duration = random.uniform(300, 900)  # 5-15 minutes
            
            await self.run_scenario(scenario_name, scenario_duration)
            
            # Brief pause between scenarios
            await asyncio.sleep(random.uniform(10, 60))
    
    def stop_all_bots(self):
        """Stop all running bots"""
        self.running = False
        for bot in self.bots:
            if hasattr(bot, 'stop'):
                bot.stop()
