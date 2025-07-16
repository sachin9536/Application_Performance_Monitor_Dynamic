import requests
import json
import time
import threading
from datetime import datetime
from typing import Dict, Any, List

class AppVitalLogShipper:
    def __init__(self, options: Dict[str, Any] = None):
        if options is None:
            options = {}
        
        self.api_url = options.get('api_url', 'http://localhost:8000')
        self.service_name = options.get('service_name', 'unknown_service')
        self.batch_size = options.get('batch_size', 10)
        self.flush_interval = options.get('flush_interval', 5)  # seconds
        self.log_buffer = []
        self.flush_timer = None
        self.running = True
        
        # Start flush timer in a separate thread
        self.flush_thread = threading.Thread(target=self._flush_timer_loop, daemon=True)
        self.flush_thread.start()
    
    def log(self, level: str, message: str, metadata: Dict[str, Any] = None):
        """Add a log entry to the buffer"""
        if metadata is None:
            metadata = {}
        
        log_entry = {
            'service': self.service_name,
            'level': level.upper(),
            'message': message,
            'timestamp': datetime.utcnow().isoformat() + 'Z',
            'metadata': metadata
        }
        
        self.log_buffer.append(log_entry)
        
        # Flush immediately if buffer is full
        if len(self.log_buffer) >= self.batch_size:
            self.flush()
    
    def info(self, message: str, metadata: Dict[str, Any] = None):
        """Log an info message"""
        self.log('INFO', message, metadata)
    
    def warn(self, message: str, metadata: Dict[str, Any] = None):
        """Log a warning message"""
        self.log('WARN', message, metadata)
    
    def error(self, message: str, metadata: Dict[str, Any] = None):
        """Log an error message"""
        self.log('ERROR', message, metadata)
    
    def debug(self, message: str, metadata: Dict[str, Any] = None):
        """Log a debug message"""
        self.log('DEBUG', message, metadata)
    
    def flush(self):
        """Flush logs to the API"""
        if not self.log_buffer:
            return
        
        logs_to_send = self.log_buffer.copy()
        self.log_buffer.clear()
        
        try:
            response = requests.post(
                f'{self.api_url}/api/ingest_log',
                json={'logs': logs_to_send},
                timeout=5,
                headers={'Content-Type': 'application/json'}
            )
            
            if response.status_code == 200:
                data = response.json()
                if data.get('status') == 'success':
                    print(f'[AppVital] Successfully sent {len(logs_to_send)} logs')
                else:
                    print(f'[AppVital] Failed to send logs: {data}')
            else:
                print(f'[AppVital] HTTP error {response.status_code}: {response.text}')
                
        except Exception as e:
            print(f'[AppVital] Error sending logs: {e}')
            # Optionally, you could add failed logs back to the buffer
            # self.log_buffer.extend(logs_to_send)
    
    def _flush_timer_loop(self):
        """Background thread for periodic flushing"""
        while self.running:
            time.sleep(self.flush_interval)
            if self.running:
                self.flush()
    
    def stop(self):
        """Stop the shipper"""
        self.running = False
        # Flush any remaining logs
        self.flush()

# Example usage:
"""
from log_shipper import AppVitalLogShipper

# Initialize the logger
logger = AppVitalLogShipper({
    'api_url': 'http://localhost:8000',
    'service_name': 'my_python_service',
    'batch_size': 5,
    'flush_interval': 3
})

# Use the logger
logger.info('User logged in', {'user_id': '123', 'ip': '192.168.1.1'})
logger.error('Database connection failed', {'error': 'Connection timeout'})
logger.warn('High memory usage', {'memory_usage': '85%'})

# Don't forget to stop when shutting down
import signal
def signal_handler(sig, frame):
    logger.stop()
    exit(0)

signal.signal(signal.SIGINT, signal_handler)
""" 