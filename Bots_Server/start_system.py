#!/usr/bin/env python3
"""
Enhanced HTTP/2 Rapid Reset Attack Analysis System Startup Script

This script helps you start the system correctly to avoid connection errors.
"""

import asyncio
import subprocess
import sys
import time
import os
import signal
from pathlib import Path

class SystemStarter:
    def __init__(self):
        self.server_processes = []
        self.bot_process = None
        
    def create_directories(self):
        """Create necessary log directories"""
        directories = [
            "logs",
            "logs/server_logs", 
            "logs/attack_logs",
            "logs/bot_logs",
            "logs/phase_profiles"
        ]
        
        for directory in directories:
            Path(directory).mkdir(parents=True, exist_ok=True)
            print(f"✅ Created directory: {directory}")
    
    def check_dependencies(self):
        """Check if required dependencies are installed"""
        required_packages = [
            "httpx", "asyncio", "aiohttp", "hypercorn", 
            "quart", "h2", "psutil"
        ]
        
        print("🔍 Checking dependencies...")
        missing_packages = []
        
        for package in required_packages:
            try:
                __import__(package)
                print(f"✅ {package} - OK")
            except ImportError:
                missing_packages.append(package)
                print(f"❌ {package} - MISSING")
        
        if missing_packages:
            print(f"\n⚠️ Missing packages: {', '.join(missing_packages)}")
            print("Please install with: pip install " + " ".join(missing_packages))
            return False
        
        return True
    
    def start_servers(self):
        """Start the HTTP/2 servers"""
        print("\n🚀 Starting HTTP/2 servers...")
        
        try:
            # Start servers in background
            process = subprocess.Popen([
                sys.executable, "main.py", "servers"
            ], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            
            self.server_processes.append(process)
            print("✅ Servers starting in background...")
            
            # Wait for servers to start up
            print("⏳ Waiting for servers to initialize...")
            time.sleep(8)  # Give servers more time to start
            
            # Check if servers are still running
            if process.poll() is None:
                print("✅ Servers are running!")
                print("   - Server 1: http://localhost:8000")
                print("   - Server 2: http://localhost:8001") 
                print("   - Server 3: http://localhost:8002")
                print("   - Dashboards available at /dashboard")
                return True
            else:
                print("❌ Servers failed to start")
                stdout, stderr = process.communicate()
                if stderr:
                    print(f"Error: {stderr.decode()}")
                return False
                
        except Exception as e:
            print(f"❌ Failed to start servers: {e}")
            return False
    
    def test_server_connectivity(self):
        """Test if servers are responding"""
        import requests
        
        print("\n🔍 Testing server connectivity...")
        servers = [
            "http://localhost:8000",
            "http://localhost:8001", 
            "http://localhost:8002"
        ]
        
        all_good = True
        for server in servers:
            try:
                response = requests.get(f"{server}/", timeout=5)
                if response.status_code == 200:
                    print(f"✅ {server} - OK")
                else:
                    print(f"⚠️ {server} - Status: {response.status_code}")
            except Exception as e:
                print(f"❌ {server} - Error: {e}")
                all_good = False
        
        return all_good
    
    def start_attack_bots(self):
        """Start the attack bots"""
        print("\n🤖 Starting attack bots...")
        
        try:
            process = subprocess.Popen([
                sys.executable, "main.py", "bots"
            ])
            
            self.bot_process = process
            print("✅ Attack bots started!")
            print("📊 Monitor the attack in real-time:")
            print("   - Dashboard: http://localhost:8000/dashboard")
            print("   - Queue Metrics: http://localhost:8000/api/queue-metrics")
            print("   - Connection Metrics: http://localhost:8000/api/client-connections")
            
            return True
            
        except Exception as e:
            print(f"❌ Failed to start bots: {e}")
            return False
    
    def run_comprehensive_test(self):
        """Run the comprehensive test suite"""
        print("\n🧪 Running comprehensive test suite...")
        
        try:
            result = subprocess.run([
                sys.executable, "test_enhanced_system.py"
            ], capture_output=True, text=True)
            
            print(result.stdout)
            if result.stderr:
                print("Errors:", result.stderr)
            
            return result.returncode == 0
            
        except Exception as e:
            print(f"❌ Test failed: {e}")
            return False
    
    def cleanup(self):
        """Clean up running processes"""
        print("\n🛑 Shutting down system...")
        
        if self.bot_process:
            self.bot_process.terminate()
            self.bot_process.wait()
            print("✅ Bots stopped")
        
        for process in self.server_processes:
            process.terminate()
            process.wait()
            print("✅ Servers stopped")
    
    def signal_handler(self, signum, frame):
        """Handle shutdown signals"""
        print(f"\n🛑 Received signal {signum}, shutting down...")
        self.cleanup()
        sys.exit(0)

def main():
    print("=" * 80)
    print("🚨 Enhanced HTTP/2 Rapid Reset Attack Analysis System")
    print("=" * 80)
    
    starter = SystemStarter()
    
    # Setup signal handlers
    signal.signal(signal.SIGINT, starter.signal_handler)
    signal.signal(signal.SIGTERM, starter.signal_handler)
    
    try:
        # Step 1: Setup
        print("\n📁 Step 1: Setting up directories...")
        starter.create_directories()
        
        # Step 2: Check dependencies
        print("\n📦 Step 2: Checking dependencies...")
        if not starter.check_dependencies():
            print("❌ Please install missing dependencies first!")
            sys.exit(1)
        
        # Step 3: Start servers
        print("\n🖥️ Step 3: Starting servers...")
        if not starter.start_servers():
            print("❌ Failed to start servers!")
            sys.exit(1)
        
        # Step 4: Test connectivity
        print("\n🔗 Step 4: Testing connectivity...")
        if not starter.test_server_connectivity():
            print("⚠️ Some servers may not be responding properly")
            print("Continuing anyway...")
        
        # Ask user what to do next
        print("\n" + "=" * 80)
        print("✅ Servers are ready! What would you like to do?")
        print("=" * 80)
        print("1. Start attack bots (for live testing)")
        print("2. Run comprehensive test suite")
        print("3. Keep servers running (manual testing)")
        print("4. Exit")
        
        while True:
            try:
                choice = input("\nEnter your choice (1-4): ").strip()
                
                if choice == "1":
                    if starter.start_attack_bots():
                        print("\n🎯 Attack simulation running!")
                        print("Press Ctrl+C to stop...")
                        try:
                            starter.bot_process.wait()
                        except KeyboardInterrupt:
                            pass
                    break
                    
                elif choice == "2":
                    starter.run_comprehensive_test()
                    break
                    
                elif choice == "3":
                    print("\n📊 Servers running! Access dashboards at:")
                    print("   - http://localhost:8000/dashboard")
                    print("   - http://localhost:8001/dashboard")
                    print("   - http://localhost:8002/dashboard")
                    print("\nPress Ctrl+C to stop...")
                    try:
                        while True:
                            time.sleep(1)
                    except KeyboardInterrupt:
                        pass
                    break
                    
                elif choice == "4":
                    break
                    
                else:
                    print("❌ Invalid choice. Please enter 1-4.")
                    
            except KeyboardInterrupt:
                break
    
    except Exception as e:
        print(f"💥 System startup failed: {e}")
        sys.exit(1)
    
    finally:
        starter.cleanup()
        print("🎉 System shutdown complete!")

if __name__ == "__main__":
    main()