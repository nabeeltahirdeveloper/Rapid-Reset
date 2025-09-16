import asyncio
import yaml
import logging
from datetime import datetime
import random
from utils.profiling import AsyncPhaseProfiler

from bots.normal_traffic_bots.web_browser_bot import WebBrowserBot
from bots.normal_traffic_bots.streaming_bot import StreamingBot
from bots.attack_bots.rapid_reset_bot import RapidResetBot
from bots.attack_bots.enhanced_rapid_reset_bot import EnhancedRapidResetBot, AttackPattern
from bots.attack_bots.heavy_computation_bot import HeavyComputationBot
from bots.attack_bots.connection_exhaustion_bot import ConnectionExhaustionBot

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
        
        # Create legacy rapid reset attack bots
        for i, intensity in enumerate(self.config['attack_bots']['rapid_reset']['intensities']):
            for j in range(self.config['attack_bots']['rapid_reset']['count_per_intensity']):
                bot = RapidResetBot(
                    bot_id=f"legacy_attack_{intensity}_{j}",
                    target_host="localhost",
                    target_port=8000,
                    attack_intensity=intensity,
                    use_tls=False
                )
                self.bots.append(bot)
        
        # Create enhanced rapid reset attack bots
        attack_patterns = [AttackPattern.BURST_AND_ABANDON, AttackPattern.SUSTAINED_FLOOD,
                          AttackPattern.MULTI_ENDPOINT_CHAOS, AttackPattern.INTERMITTENT_SPIKES]
        
        for i, intensity in enumerate(['low', 'medium', 'high']):
            for j, pattern in enumerate(attack_patterns):
                bot = EnhancedRapidResetBot(
                    bot_id=f"enhanced_attack_{intensity}_{pattern.value}_{j}",
                    target_servers=servers,
                    attack_pattern=pattern,
                    intensity=intensity
                )
                self.bots.append(bot)
        
        # Create heavy computation attack bots
        computation_complexities = ['medium', 'high', 'extreme']
        for i, complexity in enumerate(computation_complexities):
            for j in range(2):  # 2 bots per complexity level
                bot = HeavyComputationBot(
                    bot_id=f"heavy_comp_{complexity}_{j}",
                    target_servers=servers,
                    intensity='high',
                    computation_complexity=complexity
                )
                self.bots.append(bot)
        
        # Create connection exhaustion attack bots
        exhaustion_strategies = ['connection_pool', 'rapid_open_close', 'keep_alive_abuse', 'file_descriptor']
        for i, strategy in enumerate(exhaustion_strategies):
            bot = ConnectionExhaustionBot(
                bot_id=f"conn_exhaust_{strategy}_{i}",
                target_servers=servers,
                intensity='high',
                exhaustion_strategy=strategy
            )
            self.bots.append(bot)
        
        self.logger.info(f"Created {len(self.bots)} bots total:")
        self.logger.info(f"- Web browsers: {self.config['normal_bots']['web_browser_count']}")
        self.logger.info(f"- Streaming: {self.config['normal_bots']['streaming_count']}")
        self.logger.info(f"- Legacy rapid reset: {len([b for b in self.bots if 'legacy_attack' in b.bot_id])}")
        self.logger.info(f"- Enhanced rapid reset: {len([b for b in self.bots if 'enhanced_attack' in b.bot_id])}")
        self.logger.info(f"- Heavy computation: {len([b for b in self.bots if 'heavy_comp' in b.bot_id])}")
        self.logger.info(f"- Connection exhaustion: {len([b for b in self.bots if 'conn_exhaust' in b.bot_id])}")
    
    async def run_scenario(self, scenario_name, duration=3600):
        """Run specific scenario"""
        scenario = self.config['scenarios'][scenario_name]
        self.logger.info(f"Starting scenario: {scenario_name}")
        
        tasks = []
        phase_tasks = []

        async def _auto_stop(profiler: AsyncPhaseProfiler, seconds: float):
            try:
                await asyncio.sleep(seconds)
            finally:
                await profiler.stop()
        
        # Normal traffic phase
        if scenario.get('normal_traffic_duration', 0) > 0:
            self.logger.info("Starting normal traffic phase")
            normal_profiler = AsyncPhaseProfiler(
                phase_name="normal_traffic",
                extra_metadata={"scenario": scenario_name}
            )
            await normal_profiler.start()
            phase_tasks.append(asyncio.create_task(_auto_stop(normal_profiler, scenario['normal_traffic_duration'])))
            for bot in self.bots:
                if self._is_normal_traffic_bot(bot):
                    task = asyncio.create_task(
                        bot.run(duration=scenario['normal_traffic_duration'])
                    )
                    tasks.append(task)
        
        # Wait for normal traffic to establish baseline
        if scenario.get('baseline_duration', 0) > 0:
            baseline_profiler = AsyncPhaseProfiler(
                phase_name="baseline",
                extra_metadata={"scenario": scenario_name}
            )
            await baseline_profiler.start()
            phase_tasks.append(asyncio.create_task(_auto_stop(baseline_profiler, scenario['baseline_duration'])))
            await asyncio.sleep(scenario['baseline_duration'])
        
        # Attack phase
        if scenario.get('attack_duration', 0) > 0:
            self.logger.info("Starting attack phase")
            attack_profiler = AsyncPhaseProfiler(
                phase_name="attack",
                extra_metadata={"scenario": scenario_name}
            )
            await attack_profiler.start()
            phase_tasks.append(asyncio.create_task(_auto_stop(attack_profiler, scenario['attack_duration'])))
            for bot in self.bots:
                if self._is_attack_bot(bot):
                    task = asyncio.create_task(
                        bot.run(duration=scenario['attack_duration'])
                    )
                    tasks.append(task)
        
        # Wait for all tasks to complete
        await asyncio.gather(*tasks, *phase_tasks, return_exceptions=True)
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
    
    def _is_normal_traffic_bot(self, bot) -> bool:
        """Check if bot is a normal traffic bot"""
        normal_bot_types = ['WebBrowserBot', 'StreamingBot']
        return bot.__class__.__name__ in normal_bot_types
    
    def _is_attack_bot(self, bot) -> bool:
        """Check if bot is an attack bot"""
        attack_bot_types = ['RapidResetBot', 'EnhancedRapidResetBot', 'HeavyComputationBot', 'ConnectionExhaustionBot']
        return bot.__class__.__name__ in attack_bot_types
    
    async def run_enhanced_attack_scenario(self, scenario_name: str, duration: float = 600):
        """Run enhanced attack scenario with profiling"""
        from utils.enhanced_profiling import ProfilerManager
        
        scenario = self.config['scenarios'][scenario_name]
        self.logger.info(f"Starting enhanced attack scenario: {scenario_name}")
        
        # Initialize profiling
        profiler_manager = ProfilerManager(None, None)  # Will be set by server
        
        tasks = []
        
        try:
            # Phase 1: Normal traffic with baseline profiling
            if scenario.get('normal_traffic_duration', 0) > 0:
                baseline_profiler = await profiler_manager.start_phase(
                    "baseline",
                    {"scenario": scenario_name, "phase": "normal_traffic"}
                )
                
                self.logger.info("Starting normal traffic phase")
                for bot in self.bots:
                    if self._is_normal_traffic_bot(bot):
                        task = asyncio.create_task(
                            bot.run(duration=scenario['normal_traffic_duration'])
                        )
                        tasks.append(task)
                
                await asyncio.sleep(scenario['normal_traffic_duration'])
                await profiler_manager.stop_phase("baseline")
            
            # Phase 2: Attack phase with attack profiling
            if scenario.get('attack_duration', 0) > 0:
                attack_profiler = await profiler_manager.start_phase(
                    "attack",
                    {"scenario": scenario_name, "phase": "attack"}
                )
                
                self.logger.info("Starting enhanced attack phase")
                
                # Select subset of attack bots for realistic scenario
                attack_bots = [bot for bot in self.bots if self._is_attack_bot(bot)]
                selected_attack_bots = self._select_attack_bots_for_scenario(scenario_name, attack_bots)
                
                for bot in selected_attack_bots:
                    task = asyncio.create_task(
                        bot.run(duration=scenario['attack_duration'])
                    )
                    tasks.append(task)
                
                await asyncio.sleep(scenario['attack_duration'])
                await profiler_manager.stop_phase("attack")
            
            # Phase 3: Recovery phase
            recovery_profiler = await profiler_manager.start_phase(
                "recovery",
                {"scenario": scenario_name, "phase": "recovery"}
            )
            
            self.logger.info("Starting recovery phase")
            await asyncio.sleep(60)  # 1 minute recovery observation
            await profiler_manager.stop_phase("recovery")
            
            # Wait for all tasks to complete
            await asyncio.gather(*tasks, return_exceptions=True)
            
        except Exception as e:
            self.logger.error(f"Enhanced attack scenario failed: {e}")
        finally:
            await profiler_manager.stop_all()
        
        self.logger.info(f"Enhanced attack scenario {scenario_name} completed")
    
    def _select_attack_bots_for_scenario(self, scenario_name: str, attack_bots: list) -> list:
        """Select appropriate attack bots for the scenario"""
        if scenario_name == "light_attack":
            # Use fewer, less intense bots
            return [
                bot for bot in attack_bots
                if ('enhanced_attack_low' in bot.bot_id or
                    'heavy_comp_medium' in bot.bot_id)
            ][:3]
        
        elif scenario_name == "heavy_attack":
            # Use more intense bots
            return [
                bot for bot in attack_bots
                if ('enhanced_attack_high' in bot.bot_id or
                    'heavy_comp_high' in bot.bot_id or
                    'conn_exhaust' in bot.bot_id)
            ][:6]
        
        elif scenario_name == "mixed_scenario":
            # Use variety of attack bots
            return [
                bot for bot in attack_bots
                if ('enhanced_attack' in bot.bot_id or
                    'heavy_comp' in bot.bot_id or
                    'conn_exhaust' in bot.bot_id)
            ][:8]
        
        else:
            # Default selection
            return attack_bots[:4]
