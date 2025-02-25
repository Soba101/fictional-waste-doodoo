import socket
import threading
import json
import logging
import queue
from datetime import datetime, timedelta

# Setup logger
logger = logging.getLogger('waste-dashboard.data-receiver')

# Global queues for thread-safe communication
data_queue = queue.Queue()
log_queue = queue.Queue()

class DataReceiver:
    def __init__(self, host='0.0.0.0', port=5001):
        """
        Initialize data receiver with configurable host/port
        Using 0.0.0.0 to bind to all network interfaces
        """
        self.host = host
        self.port = port
        self.running = False
        self.socket = None
        self.thread = None
        
        # Instead of accessing session state directly, we'll use local
        # variables and queues
        self.connected_devices = set()
        self.last_connection_time = {}
        self.connection_status = "Not started"
        self.connection_attempts = 0
        self.successful_connections = 0
        self.failed_connections = 0
        
    def initialize_socket(self):
        """Initialize and configure socket"""
        try:
            if self.socket:
                try:
                    self.socket.close()
                except:
                    pass
                    
            logger.info(f"Initializing socket on {self.host}:{self.port}")
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            
            try:
                self.socket.bind((self.host, self.port))
                self.socket.listen(5)  # Allow up to 5 queued connections
                self.socket.settimeout(1.0)  # 1 second timeout for accept()
                self.connection_status = f"Listening on {self.host}:{self.port}"
                logger.info(f"Server socket bound successfully to {self.host}:{self.port}")
                # Use queue instead of directly accessing session state
                log_queue.put(("Socket bound", f"Listening on {self.host}:{self.port}"))
                return True
            except Exception as bind_error:
                logger.error(f"Socket bind error: {bind_error}")
                log_queue.put(("Socket bind error", str(bind_error)))
                if self.socket:
                    self.socket.close()
                    self.socket = None
                return False
                
        except Exception as e:
            self.connection_status = f"Socket error: {str(e)}"
            logger.error(f"Failed to initialize socket: {e}")
            log_queue.put(("Socket initialization error", str(e)))
            if self.socket:
                self.socket.close()
                self.socket = None
            return False
    
    def start(self):
        """Start the receiver thread if not already running"""
        if self.running:
            logger.info("Receiver already running, not starting again")
            return
            
        self.running = True
        if not self.initialize_socket():
            logger.error("Failed to initialize socket, cannot start receiver")
            self.running = False
            return False
            
        def receive_loop():
            logger.info("Receiver loop starting")
            log_queue.put(("Receiver started", "Waiting for connections"))
            
            while self.running:
                try:
                    # Accept connection with timeout
                    client_socket, address = self.socket.accept()
                    client_ip = address[0]
                    logger.info(f"Connection from {client_ip}:{address[1]}")
                    self.connection_attempts += 1
                    
                    # Set timeout for receiving data
                    client_socket.settimeout(2.0)
                    
                    # Receive data
                    data = b""
                    try:
                        chunk = client_socket.recv(4096)
                        while chunk:
                            data += chunk
                            try:
                                # Try to receive more data, but don't block for too long
                                client_socket.settimeout(0.1)
                                chunk = client_socket.recv(4096)
                            except socket.timeout:
                                # No more data available right now
                                break
                    except socket.timeout:
                        logger.warning(f"Timeout receiving data from {client_ip}")
                        log_queue.put(("Receive timeout", f"From {client_ip}"))
                        self.failed_connections += 1
                        client_socket.close()
                        continue
                    
                    # Process received data
                    if data:
                        try:
                            json_data = json.loads(data.decode('utf-8'))
                            device_id = json_data.get('device_id', 'Unknown Device')
                            
                            # *** IMPORTANT FIX: Associate the sender IP with the data ***
                            # Add a special attribute to track where this data came from
                            json_data['_sender_ip'] = client_ip
                            
                            # Mark this device as active in our local tracking
                            self.connected_devices.add(device_id)
                            self.last_connection_time[device_id] = datetime.now()
                            
                            # Queue device IP update instead of directly updating session state
                            device_ip_data = {"device_id": device_id, "ip": client_ip}
                            log_queue.put(("DEVICE_IP_UPDATE", device_ip_data))
                            
                            # Log prediction info
                            predictions = json_data.get('predictions', [])
                            if predictions:
                                logger.info(f"Received {len(predictions)} predictions from {device_id}")
                                classes = [p.get('class', 'unknown') for p in predictions]
                                logger.info(f"Detected classes: {', '.join(classes)}")
                            
                            # Add to queue for main thread processing
                            data_queue.put(json_data)
                            self.connection_status = f"Last data: {datetime.now().strftime('%H:%M:%S')} from {device_id}"
                            self.successful_connections += 1
                            
                            # Add a log entry for the new connection
                            log_queue.put(("New data received", f"From {client_ip}", device_id))
                            
                        except json.JSONDecodeError as e:
                            logger.error(f"Invalid JSON received from {client_ip}: {e}")
                            logger.error(f"Raw data: {data[:100]}...")  # Log first 100 bytes
                            log_queue.put(("JSON parse error", f"From {client_ip}: {e}"))
                            self.connection_status = f"JSON error from {client_ip}: {str(e)}"
                            self.failed_connections += 1
                            
                            # *** IMPORTANT: Still mark receiver as running even on JSON errors ***
                            log_queue.put(("STATUS_UPDATE", {
                                "running": True,
                                "connection_status": self.connection_status,
                                "connection_attempts": self.connection_attempts,
                                "successful_connections": self.successful_connections, 
                                "failed_connections": self.failed_connections,
                                "active_devices": self.connected_devices.copy(),
                                "last_connection_time": self.last_connection_time.copy()
                            }))
                    else:
                        logger.warning(f"Empty data received from {client_ip}")
                        log_queue.put(("Empty data", f"From {client_ip}"))
                        self.failed_connections += 1
                    
                    # Close the client socket
                    client_socket.close()
                    
                except socket.timeout:
                    # This is expected with the accept timeout, just continue
                    pass
                except Exception as e:
                    if self.running:  # Only log if we're still supposed to be running
                        logger.error(f"Connection error: {e}")
                        log_queue.put(("Connection error", str(e)))
                        self.connection_status = f"Connection error: {str(e)}"
                        self.failed_connections += 1
                        
                        # Try to reinitialize if there was a serious error
                        if "Bad file descriptor" in str(e):
                            logger.info("Attempting to reinitialize socket after error")
                            self.initialize_socket()
                
                # Update status periodically
                if self.running:
                    self.update_status()
            
            logger.info("Receiver loop ending")
        
        # Start the receiver thread
        self.thread = threading.Thread(target=receive_loop, daemon=True)
        self.thread.start()
        logger.info(f"Started receiver thread: {self.thread.name}")
        return True
    
    def update_status(self):
        """Update session state with current status via queue"""
        # This method updates our status data to be picked up by the main thread
        status_update = {
            "running": self.running,
            "connection_status": self.connection_status,
            "connection_attempts": self.connection_attempts,
            "successful_connections": self.successful_connections,
            "failed_connections": self.failed_connections,
            "active_devices": self.connected_devices.copy(),
            "last_connection_time": self.last_connection_time.copy()
        }
        # Use a special queue message type for status updates
        log_queue.put(("STATUS_UPDATE", status_update))
    
    def stop(self):
        """Stop the receiver"""
        logger.info("Stopping receiver")
        self.running = False
        if self.socket:
            try:
                self.socket.close()
            except:
                pass
            self.socket = None
        self.connection_status = "Stopped"
        log_queue.put(("Receiver stopped", None))
        
    def is_running(self):
        """Check if receiver is running"""
        return self.running and self.thread is not None and self.thread.is_alive()
    
    def get_active_devices(self):
        """Return list of devices that have connected recently (last 5 minutes)"""
        active_devices = []
        now = datetime.now()
        for device_id, last_time in self.last_connection_time.items():
            if now - last_time < timedelta(minutes=5):
                active_devices.append(device_id)
        return active_devices