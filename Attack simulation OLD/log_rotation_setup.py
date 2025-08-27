import os
import logging.handlers
import json
import time
from datetime import datetime
import shutil
import gzip
import glob

class LogRotationManager:
    def __init__(self, base_log_dir='logs'):
        self.base_log_dir = base_log_dir
        self.archive_dir = os.path.join(base_log_dir, 'archives')
        os.makedirs(self.archive_dir, exist_ok=True)
        
    def setup_rotating_logger(self, name, filename, max_bytes=50*1024*1024, backup_count=10):
        """Setup rotating file handler for a logger"""
        logger = logging.getLogger(name)
        logger.setLevel(logging.INFO)
        
        # Remove existing handlers
        for handler in logger.handlers[:]:
            logger.removeHandler(handler)
        
        # Create rotating file handler
        handler = logging.handlers.RotatingFileHandler(
            filename=os.path.join(self.base_log_dir, filename),
            maxBytes=max_bytes,  # 50MB
            backupCount=backup_count
        )
        
        formatter = logging.Formatter(
            '%(asctime)s.%(msecs)03d|%(levelname)s|%(name)s|%(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        
        return logger
    
    def compress_old_logs(self):
        """Compress old log files to save space"""
        log_files = glob.glob(os.path.join(self.base_log_dir, '*.log.*'))
        
        for log_file in log_files:
            if not log_file.endswith('.gz'):
                compressed_name = f"{log_file}.gz"
                
                with open(log_file, 'rb') as f_in:
                    with gzip.open(compressed_name, 'wb') as f_out:
                        shutil.copyfileobj(f_in, f_out)
                
                os.remove(log_file)
                print(f"Compressed: {log_file} -> {compressed_name}")
    
    def archive_daily_logs(self):
        """Archive logs daily with date stamps"""
        today = datetime.now().strftime('%Y-%m-%d')
        daily_archive_dir = os.path.join(self.archive_dir, today)
        os.makedirs(daily_archive_dir, exist_ok=True)
        
        # Move compressed logs to daily archive
        compressed_logs = glob.glob(os.path.join(self.base_log_dir, '*.log.*.gz'))
        
        for log_file in compressed_logs:
            filename = os.path.basename(log_file)
            archive_path = os.path.join(daily_archive_dir, filename)
            shutil.move(log_file, archive_path)
            print(f"Archived: {log_file} -> {archive_path}")
    
    def create_log_summary(self):
        """Create daily summary statistics"""
        summary = {
            'date': datetime.now().isoformat(),
            'log_files': [],
            'total_size_mb': 0,
            'request_counts': {},
            'error_counts': {}
        }
        
        # Analyze current logs
        for log_file in glob.glob(os.path.join(self.base_log_dir, '*.log')):
            file_size = os.path.getsize(log_file) / (1024 * 1024)  # MB
            summary['log_files'].append({
                'filename': os.path.basename(log_file),
                'size_mb': round(file_size, 2)
            })
            summary['total_size_mb'] += file_size
        
        summary['total_size_mb'] = round(summary['total_size_mb'], 2)
        
        # Save summary
        summary_file = os.path.join(self.base_log_dir, 'daily_summary.json')
        with open(summary_file, 'w') as f:
            json.dump(summary, f, indent=2)
        
        print(f"Log summary saved: {summary_file}")
        return summary

def setup_automated_rotation():
    """Setup automated log rotation"""
    manager = LogRotationManager()
    
    # Setup rotating loggers for different components
    loggers = {
        'server': manager.setup_rotating_logger('http2_server', 'detailed_server.log'),
        'ml_data': manager.setup_rotating_logger('ml_data', 'ml_training_data.jsonl'),
        'attacks': manager.setup_rotating_logger('attacks', 'attack_simulation.log'),
        'normal_traffic': manager.setup_rotating_logger('normal_traffic', 'normal_traffic.log')
    }
    
    print("Automated log rotation setup complete")
    return manager, loggers

# Cron-style automation script
def daily_maintenance():
    """Run daily log maintenance tasks"""
    manager = LogRotationManager()
    
    print(f"Starting daily maintenance: {datetime.now()}")
    
    # Compress old logs
    manager.compress_old_logs()
    
    # Archive daily logs
    manager.archive_daily_logs()
    
    # Create summary
    summary = manager.create_log_summary()
    print(f"Daily maintenance completed. Total log size: {summary['total_size_mb']} MB")

if __name__ == '__main__':
    # Setup rotation
    setup_automated_rotation()
    
    # Run maintenance
    daily_maintenance()
