#!/usr/bin/env python3
"""
Comprehensive Test Script for Enhanced HTTP/2 Rapid Reset Attack Analysis System

This script validates:
1. Enhanced queue system with client connection tracking
2. Request abandonment detection and reset timers
3. Multiple attack patterns (rapid reset, heavy computation, connection exhaustion)
4. Profiling system with abandoned request tracking
5. Dashboard functionality and real-time monitoring
"""

import asyncio
import aiohttp
import logging
import json
import time
from datetime import datetime
from typing import List, Dict, Any
import sys
import signal
import os

# Add project root to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from bots.attack_bots.enhanced_rapid_reset_bot import EnhancedRapidResetBot, AttackPattern
from bots.attack_bots.heavy_computation_bot import HeavyComputationBot
from bots.attack_bots.connection_exhaustion_bot import ConnectionExhaustionBot
from bots.normal_traffic_bots.web_browser_bot import WebBrowserBot

class EnhancedSystemTester:
    def __init__(self, server_urls: List[str]):
        self.server_urls = server_urls
        self.test_results = {}
        self.running = False
        self.setup_logging()
    
    def setup_logging(self):
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler('logs/system_test.log'),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger('enhanced_system_tester')
    
    async def test_server_health(self) -> bool:
        """Test basic server health and enhanced endpoints"""
        self.logger.info("🔍 Testing server health and enhanced endpoints...")
        
        try:
            async with aiohttp.ClientSession() as session:
                for server_url in self.server_urls:
                    # Test basic endpoints
                    endpoints = [
                        "/",
                        "/api/data",
                        "/heavy-task?n=25",
                        "/metrics",
                        "/api/queue-metrics", 
                        "/api/client-connections",
                        "/dashboard"
                    ]
                    
                    for endpoint in endpoints:
                        url = f"{server_url}{endpoint}"
                        try:
                            async with session.get(url, timeout=10) as response:
                                if response.status == 200:
                                    self.logger.info(f"✅ {endpoint} - OK")
                                else:
                                    self.logger.warning(f"⚠️ {endpoint} - Status: {response.status}")
                        except Exception as e:
                            self.logger.error(f"❌ {endpoint} - Error: {e}")
                            return False
            
            self.test_results["server_health"] = True
            return True
            
        except Exception as e:
            self.logger.error(f"Server health check failed: {e}")
            self.test_results["server_health"] = False
            return False
    
    async def test_enhanced_queue_metrics(self) -> bool:
        """Test enhanced queue metrics endpoint"""
        self.logger.info("📊 Testing enhanced queue metrics...")
        
        try:
            async with aiohttp.ClientSession() as session:
                url = f"{self.server_urls[0]}/api/queue-metrics"
                async with session.get(url) as response:
                    if response.status == 200:
                        data = await response.json()
                        
                        # Validate queue metrics structure
                        required_fields = [
                            "queue_metrics.queue.total_size",
                            "queue_metrics.queue.utilization_percent",
                            "queue_metrics.metrics.active_requests",
                            "queue_metrics.metrics.total_abandoned",
                            "queue_metrics.workers",
                            "queue_metrics.clients"
                        ]
                        
                        for field in required_fields:
                            if not self._check_nested_field(data, field):
                                self.logger.error(f"❌ Missing field: {field}")
                                return False
                        
                        self.logger.info("✅ Queue metrics endpoint working correctly")
                        self.test_results["queue_metrics"] = True
                        return True
                    else:
                        self.logger.error(f"❌ Queue metrics endpoint failed: {response.status}")
                        return False
                        
        except Exception as e:
            self.logger.error(f"Queue metrics test failed: {e}")
            self.test_results["queue_metrics"] = False
            return False
    
    async def test_client_connection_tracking(self) -> bool:
        """Test client connection tracking"""
        self.logger.info("🔗 Testing client connection tracking...")
        
        try:
            async with aiohttp.ClientSession() as session:
                # Make several requests to establish connection tracking
                for i in range(5):
                    url = f"{self.server_urls[0]}/api/data"
                    headers = {
                        "User-Agent": f"TestClient-{i}",
                        "X-Test-Connection": f"tracking-test-{i}"
                    }
                    async with session.get(url, headers=headers) as response:
                        await response.read()
                
                # Check connection metrics
                url = f"{self.server_urls[0]}/api/client-connections"
                async with session.get(url) as response:
                    if response.status == 200:
                        data = await response.json()
                        
                        if data.get("connection_metrics", {}).get("active_clients", 0) > 0:
                            self.logger.info("✅ Client connection tracking working")
                            self.test_results["connection_tracking"] = True
                            return True
                        else:
                            self.logger.warning("⚠️ No active clients detected")
                            return False
                    else:
                        self.logger.error(f"❌ Connection metrics failed: {response.status}")
                        return False
                        
        except Exception as e:
            self.logger.error(f"Connection tracking test failed: {e}")
            self.test_results["connection_tracking"] = False
            return False
    
    async def test_profiling_system(self) -> bool:
        """Test the enhanced profiling system"""
        self.logger.info("📈 Testing enhanced profiling system...")
        
        try:
            async with aiohttp.ClientSession() as session:
                # Start profiling
                start_url = f"{self.server_urls[0]}/api/profiling/start/test_phase"
                async with session.post(start_url, json={"test": "profiling_validation"}) as response:
                    if response.status == 200:
                        self.logger.info("✅ Profiling started successfully")
                    else:
                        self.logger.error(f"❌ Failed to start profiling: {response.status}")
                        return False
                
                # Wait a moment
                await asyncio.sleep(2)
                
                # Stop profiling
                stop_url = f"{self.server_urls[0]}/api/profiling/stop/test_phase"
                async with session.post(stop_url) as response:
                    if response.status == 200:
                        self.logger.info("✅ Profiling stopped successfully")
                        self.test_results["profiling"] = True
                        return True
                    else:
                        self.logger.error(f"❌ Failed to stop profiling: {response.status}")
                        return False
                        
        except Exception as e:
            self.logger.error(f"Profiling test failed: {e}")
            self.test_results["profiling"] = False
            return False
    
    async def test_rapid_reset_attack_scenario(self) -> bool:
        """Test enhanced rapid reset attack scenario"""
        self.logger.info("🚨 Testing enhanced rapid reset attack scenario...")
        
        try:
            # Create enhanced rapid reset bot
            bot = EnhancedRapidResetBot(
                bot_id="test_rapid_reset",
                target_servers=self.server_urls,
                attack_pattern=AttackPattern.BURST_AND_ABANDON,
                intensity="medium"
            )
            
            # Start profiling for attack
            async with aiohttp.ClientSession() as session:
                start_url = f"{self.server_urls[0]}/api/profiling/start/attack"
                await session.post(start_url, json={"scenario": "rapid_reset_test"})
            
            # Run attack for 10 seconds
            self.logger.info("🔥 Starting rapid reset attack...")
            attack_task = asyncio.create_task(bot.run(duration=10))
            
            # Monitor metrics during attack
            monitoring_task = asyncio.create_task(self._monitor_attack_metrics(10))
            
            # Wait for both to complete
            await asyncio.gather(attack_task, monitoring_task, return_exceptions=True)
            
            # Stop profiling
            async with aiohttp.ClientSession() as session:
                stop_url = f"{self.server_urls[0]}/api/profiling/stop/attack"
                await session.post(stop_url)
            
            # Validate attack results
            if bot.total_requests_sent > 0 and bot.total_connections_abandoned > 0:
                self.logger.info(f"✅ Rapid reset attack completed:")
                self.logger.info(f"   - Requests sent: {bot.total_requests_sent}")
                self.logger.info(f"   - Connections abandoned: {bot.total_connections_abandoned}")
                self.logger.info(f"   - Abandonment rate: {(bot.total_connections_abandoned/max(1,bot.total_connections_made))*100:.1f}%")
                
                self.test_results["rapid_reset_attack"] = {
                    "success": True,
                    "requests_sent": bot.total_requests_sent,
                    "connections_abandoned": bot.total_connections_abandoned,
                    "abandonment_rate": (bot.total_connections_abandoned/max(1,bot.total_connections_made))*100
                }
                return True
            else:
                self.logger.error("❌ Rapid reset attack failed to generate expected traffic")
                return False
                
        except Exception as e:
            self.logger.error(f"Rapid reset attack test failed: {e}")
            self.test_results["rapid_reset_attack"] = {"success": False, "error": str(e)}
            return False
    
    async def test_heavy_computation_attack_scenario(self) -> bool:
        """Test heavy computation attack scenario"""
        self.logger.info("🧮 Testing heavy computation attack scenario...")
        
        try:
            # Create heavy computation bot
            bot = HeavyComputationBot(
                bot_id="test_heavy_comp",
                target_servers=self.server_urls,
                intensity="medium",
                computation_complexity="high"
            )
            
            # Run attack for 15 seconds
            self.logger.info("🔥 Starting heavy computation attack...")
            await bot.run(duration=15)
            
            # Validate results
            if bot.total_computation_requests > 0:
                completion_rate = (bot.total_completed_computations / bot.total_computation_requests) * 100
                
                self.logger.info(f"✅ Heavy computation attack completed:")
                self.logger.info(f"   - Computation requests: {bot.total_computation_requests}")
                self.logger.info(f"   - Completed: {bot.total_completed_computations}")
                self.logger.info(f"   - Abandoned: {bot.total_abandoned_computations}")
                self.logger.info(f"   - Server overloads: {bot.total_server_overloads}")
                self.logger.info(f"   - Completion rate: {completion_rate:.1f}%")
                
                self.test_results["heavy_computation_attack"] = {
                    "success": True,
                    "computation_requests": bot.total_computation_requests,
                    "completed": bot.total_completed_computations,
                    "abandoned": bot.total_abandoned_computations,
                    "server_overloads": bot.total_server_overloads,
                    "completion_rate": completion_rate
                }
                return True
            else:
                self.logger.error("❌ Heavy computation attack failed")
                return False
                
        except Exception as e:
            self.logger.error(f"Heavy computation attack test failed: {e}")
            self.test_results["heavy_computation_attack"] = {"success": False, "error": str(e)}
            return False
    
    async def test_connection_exhaustion_scenario(self) -> bool:
        """Test connection exhaustion attack scenario"""
        self.logger.info("🔌 Testing connection exhaustion scenario...")
        
        try:
            # Create connection exhaustion bot
            bot = ConnectionExhaustionBot(
                bot_id="test_conn_exhaust",
                target_servers=self.server_urls,
                intensity="medium",
                exhaustion_strategy="rapid_open_close"
            )
            
            # Run attack for 10 seconds
            self.logger.info("🔥 Starting connection exhaustion attack...")
            await bot.run(duration=10)
            
            # Validate results
            if bot.total_connections_attempted > 0:
                success_rate = (bot.total_connections_established / bot.total_connections_attempted) * 100
                
                self.logger.info(f"✅ Connection exhaustion attack completed:")
                self.logger.info(f"   - Connections attempted: {bot.total_connections_attempted}")
                self.logger.info(f"   - Connections established: {bot.total_connections_established}")
                self.logger.info(f"   - Connections refused: {bot.total_connections_refused}")
                self.logger.info(f"   - Success rate: {success_rate:.1f}%")
                self.logger.info(f"   - Server exhaustion detected: {bot.server_exhaustion_detected}")
                
                self.test_results["connection_exhaustion_attack"] = {
                    "success": True,
                    "attempted": bot.total_connections_attempted,
                    "established": bot.total_connections_established,
                    "refused": bot.total_connections_refused,
                    "success_rate": success_rate,
                    "exhaustion_detected": bot.server_exhaustion_detected
                }
                return True
            else:
                self.logger.error("❌ Connection exhaustion attack failed")
                return False
                
        except Exception as e:
            self.logger.error(f"Connection exhaustion attack test failed: {e}")
            self.test_results["connection_exhaustion_attack"] = {"success": False, "error": str(e)}
            return False
    
    async def test_mixed_attack_scenario(self) -> bool:
        """Test mixed attack scenario with normal traffic"""
        self.logger.info("🌪️ Testing mixed attack scenario...")
        
        try:
            # Create mixed bots
            normal_bot = WebBrowserBot(
                bot_id="test_normal",
                target_servers=self.server_urls,
                request_rate=2.0
            )
            
            rapid_reset_bot = EnhancedRapidResetBot(
                bot_id="test_mixed_rapid",
                target_servers=self.server_urls,
                attack_pattern=AttackPattern.INTERMITTENT_SPIKES,
                intensity="low"
            )
            
            # Start profiling
            async with aiohttp.ClientSession() as session:
                await session.post(f"{self.server_urls[0]}/api/profiling/start/mixed_scenario",
                                 json={"scenario": "mixed_attack_test"})
            
            # Run mixed scenario
            self.logger.info("🔥 Starting mixed attack scenario...")
            tasks = [
                asyncio.create_task(normal_bot.run(duration=20)),
                asyncio.create_task(rapid_reset_bot.run(duration=15)),
                asyncio.create_task(self._monitor_mixed_scenario_metrics(20))
            ]
            
            await asyncio.gather(*tasks, return_exceptions=True)
            
            # Stop profiling
            async with aiohttp.ClientSession() as session:
                await session.post(f"{self.server_urls[0]}/api/profiling/stop/mixed_scenario")
            
            self.logger.info("✅ Mixed attack scenario completed")
            self.test_results["mixed_attack_scenario"] = {
                "success": True,
                "normal_requests": normal_bot.total_requests,
                "attack_requests": rapid_reset_bot.total_requests_sent,
                "attack_abandonments": rapid_reset_bot.total_connections_abandoned
            }
            return True
            
        except Exception as e:
            self.logger.error(f"Mixed attack scenario test failed: {e}")
            self.test_results["mixed_attack_scenario"] = {"success": False, "error": str(e)}
            return False
    
    async def _monitor_attack_metrics(self, duration: int):
        """Monitor server metrics during attack"""
        end_time = time.time() + duration
        metrics_history = []
        
        async with aiohttp.ClientSession() as session:
            while time.time() < end_time:
                try:
                    # Get enhanced metrics
                    async with session.get(f"{self.server_urls[0]}/api/queue-metrics") as response:
                        if response.status == 200:
                            data = await response.json()
                            metrics_history.append({
                                "timestamp": time.time(),
                                "queue_size": data.get("queue_metrics", {}).get("queue", {}).get("total_size", 0),
                                "abandoned_requests": data.get("queue_metrics", {}).get("metrics", {}).get("total_abandoned", 0),
                                "utilization": data.get("queue_metrics", {}).get("queue", {}).get("utilization_percent", 0)
                            })
                except:
                    pass
                
                await asyncio.sleep(1)
        
        # Log peak metrics
        if metrics_history:
            peak_queue = max(m["queue_size"] for m in metrics_history)
            peak_abandoned = max(m["abandoned_requests"] for m in metrics_history)
            peak_utilization = max(m["utilization"] for m in metrics_history)
            
            self.logger.info(f"📊 Attack metrics - Peak queue: {peak_queue}, Peak abandoned: {peak_abandoned}, Peak util: {peak_utilization:.1f}%")
    
    async def _monitor_mixed_scenario_metrics(self, duration: int):
        """Monitor metrics during mixed scenario"""
        await self._monitor_attack_metrics(duration)
    
    def _check_nested_field(self, data: Dict, field_path: str) -> bool:
        """Check if nested field exists in data"""
        keys = field_path.split('.')
        current = data
        
        for key in keys:
            if isinstance(current, dict) and key in current:
                current = current[key]
            else:
                return False
        
        return True
    
    async def run_comprehensive_test(self) -> bool:
        """Run comprehensive test suite"""
        self.running = True
        
        self.logger.info("🚀 Starting comprehensive enhanced system test...")
        self.logger.info("=" * 80)
        
        test_functions = [
            ("Server Health Check", self.test_server_health),
            ("Enhanced Queue Metrics", self.test_enhanced_queue_metrics),
            ("Client Connection Tracking", self.test_client_connection_tracking),
            ("Profiling System", self.test_profiling_system),
            ("Rapid Reset Attack", self.test_rapid_reset_attack_scenario),
            ("Heavy Computation Attack", self.test_heavy_computation_attack_scenario),
            ("Connection Exhaustion Attack", self.test_connection_exhaustion_scenario),
            ("Mixed Attack Scenario", self.test_mixed_attack_scenario)
        ]
        
        passed_tests = 0
        total_tests = len(test_functions)
        
        for test_name, test_func in test_functions:
            self.logger.info(f"\n{'='*20} {test_name} {'='*20}")
            
            try:
                if await test_func():
                    passed_tests += 1
                    self.logger.info(f"✅ {test_name} PASSED")
                else:
                    self.logger.error(f"❌ {test_name} FAILED")
            except Exception as e:
                self.logger.error(f"💥 {test_name} CRASHED: {e}")
        
        # Generate final report
        self.logger.info("\n" + "=" * 80)
        self.logger.info("📊 COMPREHENSIVE TEST RESULTS")
        self.logger.info("=" * 80)
        self.logger.info(f"Tests Passed: {passed_tests}/{total_tests}")
        self.logger.info(f"Success Rate: {(passed_tests/total_tests)*100:.1f}%")
        
        if passed_tests == total_tests:
            self.logger.info("🎉 ALL TESTS PASSED! Enhanced system is working correctly.")
            return True
        else:
            self.logger.warning(f"⚠️ {total_tests - passed_tests} tests failed. Review the issues above.")
            return False
    
    def save_test_report(self):
        """Save detailed test report"""
        report = {
            "test_timestamp": datetime.now().isoformat(),
            "server_urls": self.server_urls,
            "test_results": self.test_results,
            "summary": {
                "total_tests": len(self.test_results),
                "passed_tests": sum(1 for r in self.test_results.values() 
                                   if (isinstance(r, dict) and r.get("success")) or (isinstance(r, bool) and r)),
                "success_rate": 0
            }
        }
        
        report["summary"]["success_rate"] = (report["summary"]["passed_tests"] / report["summary"]["total_tests"]) * 100
        
        with open('logs/comprehensive_test_report.json', 'w') as f:
            json.dump(report, f, indent=2)
        
        self.logger.info("📄 Test report saved to logs/comprehensive_test_report.json")

async def main():
    # Configuration
    server_urls = [
        "http://localhost:8000",
        "http://localhost:8001", 
        "http://localhost:8002"
    ]
    
    # Create logs directory
    os.makedirs('logs', exist_ok=True)
    os.makedirs('logs/attack_logs', exist_ok=True)
    os.makedirs('logs/bot_logs', exist_ok=True)
    os.makedirs('logs/phase_profiles', exist_ok=True)
    
    # Initialize tester
    tester = EnhancedSystemTester(server_urls)
    
    # Handle graceful shutdown
    def signal_handler(signum, frame):
        tester.logger.info("\n🛑 Test interrupted by user")
        tester.running = False
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    try:
        # Run comprehensive test
        success = await tester.run_comprehensive_test()
        
        # Save report
        tester.save_test_report()
        
        if success:
            print("\n🎉 Comprehensive test completed successfully!")
            sys.exit(0)
        else:
            print("\n⚠️ Some tests failed. Check the logs for details.")
            sys.exit(1)
            
    except Exception as e:
        tester.logger.error(f"💥 Test suite crashed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())