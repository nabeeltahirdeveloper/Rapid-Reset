import subprocess
import time
import signal
import sys
import os
from datetime import datetime

class LogCollectionOrchestrator:
    def __init__(self):
        self.processes = []
        self.running = False
        
    def start_server(self):
        """Start the enhanced HTTP/2 server"""
        print("Starting enhanced HTTP/2 server...")
        process = subprocess.Popen([
            'python3', 'enhanced_http2_server.py'
        ])
        self.processes.append(('server', process))
        time.sleep(5)  # Wait for server to start
        return process
    
    def start_normal_traffic(self):
        """Start normal traffic generation"""
        print("Starting normal traffic generation (24+ hours)...")
        process = subprocess.Popen([
            'python3', 'normal_traffic_generator.py'
        ])
        self.processes.append(('normal_traffic', process))
        return process
    
    def run_attack_simulations(self):
        """Run all attack simulations"""
        print("Starting attack simulations...")
        process = subprocess.Popen([
            'python3', 'attack_simulation.py'
        ])
        self.processes.append(('attacks', process))
        return process
    
    def setup_log_rotation(self):
        """Setup log rotation"""
        print("Setting up log rotation...")
        subprocess.run(['python3', 'log_rotation_setup.py'])
    
    def monitor_processes(self):
        """Monitor all running processes"""
        while self.running:
            for name, process in self.processes:
                if process.poll() is not None:
                    print(f"Process {name} has terminated")
            
            time.sleep(60)  # Check every minute
    
    def cleanup(self, signum=None, frame=None):
        """Clean shutdown of all processes"""
        print("\nShutting down all processes...")
        self.running = False
        
        for name, process in self.processes:
            if process.poll() is None:
                print(f"Terminating {name}...")
                process.terminate()
                time.sleep(2)
                if process.poll() is None:
                    process.kill()
        
        print("Cleanup complete")
        sys.exit(0)
    
    def run_full_collection(self):
        """Run the complete log collection setup"""
        # Setup signal handlers
        signal.signal(signal.SIGINT, self.cleanup)
        signal.signal(signal.SIGTERM, self.cleanup)
        
        print(f"Starting full log collection at {datetime.now()}")
        
        # Create logs directory
        os.makedirs('logs', exist_ok=True)
        
        # Setup log rotation
        self.setup_log_rotation()
        
        # Start server
        self.start_server()
        
        # Start normal traffic (runs for 24+ hours)
        self.start_normal_traffic()
        
        # Wait a bit for normal traffic to establish baseline
        print("Waiting 10 minutes for baseline traffic...")
        time.sleep(600)
        
        # Run attack simulations
        self.run_attack_simulations()
        
        self.running = True
        
        print("All processes started. Monitoring...")
        print("Press Ctrl+C to stop all processes")
        
        try:
            self.monitor_processes()
        except KeyboardInterrupt:
            self.cleanup()

if __name__ == '__main__':
    orchestrator = LogCollectionOrchestrator()
    orchestrator.run_full_collection()
