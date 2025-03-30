"""
Communication module using MQTT for sending data to dashboard and database servers.
"""
import json
import logging
import threading
import time
from datetime import datetime
import paho.mqtt.client as mqtt

import config
from utils.helpers import get_local_ip

logger = logging.getLogger('communication-module')

class CommunicationModule:
    def __init__(self, gps_module=None, gas_module=None):
        """
        Initialize the communication module.
        
        Args:
            gps_module: GPS module instance for location data
            gas_module: Gas sensor module instance for gas sensor data
        """
        logger.info("Starting communication module initialization...")
        self.gps_module = gps_module
        self.gas_module = gas_module
        self.connection_attempts = 0
        self.successful_connections = 0
        self.failed_connections = 0
        self.start_time = time.time()
        self.running = False
        self.max_retries = 5
        self.retry_delay = 5  # seconds
        self.last_heartbeat = time.time()  # Initialize to current time
        self.heartbeat_timeout = 30  # seconds
        self.reconnect_delay = 1  # Start with 1 second delay
        
        # Frame buffer settings
        self.frame_buffer = []
        self.frame_buffer_lock = threading.Lock()
        self.max_buffer_size = 10  # Maximum number of frames to buffer
        self.target_fps = 15  # Target frames per second
        self.frame_interval = 1.0 / self.target_fps  # Time between frames
        self.last_frame_time = 0
        
        # MQTT client for dashboard communication
        logger.info(f"Initializing MQTT client with ID: pi_{config.DEVICE_ID}")
        logger.info(f"MQTT Broker: {config.MQTT_BROKER}:{config.MQTT_PORT}")
        self.client = mqtt.Client(client_id=f"pi_{config.DEVICE_ID}")
        
        # Set up MQTT callbacks
        logger.info("Setting up MQTT callbacks...")
        self.client.on_connect = self._on_connect
        self.client.on_disconnect = self._on_disconnect
        self.client.on_publish = self._on_publish
        self.client.on_message = self._on_message
        
        # Set up Last Will and Testament (LWT)
        logger.info("Setting up Last Will and Testament...")
        will_data = {
            "device_id": config.DEVICE_ID,
            "timestamp": datetime.now().isoformat(),
            "status": "disconnected"
        }
        self.client.will_set(
            f"devices/{config.DEVICE_ID}/status",
            json.dumps(will_data),
            qos=1,
            retain=True
        )
        
        # Start MQTT connection with retry
        logger.info("Starting MQTT connection...")
        if not self._connect_with_retry():
            logger.error("Failed to establish initial MQTT connection")
            raise Exception("Failed to establish MQTT connection")
        
        # Wait for connection to be fully established
        time.sleep(2)
        
        # Start heartbeat sender first
        logger.info("Starting heartbeat sender...")
        self.start_heartbeat_sender()
        
        # Start frame sender thread
        logger.info("Starting frame sender thread...")
        self.frame_sender_thread = threading.Thread(target=self._frame_sender_loop, daemon=True)
        self.frame_sender_thread.start()
        
        logger.info("Communication module initialization completed")
    
    def _connect_with_retry(self):
        """Attempt to connect to MQTT broker with retry logic."""
        while self.connection_attempts < config.MQTT_MAX_RETRIES:
            try:
                # First verify network connectivity
                if not self._verify_network_connectivity():
                    logger.error("Network connectivity check failed")
                    time.sleep(config.MQTT_RETRY_DELAY)
                    continue
                
                logger.info(f"Attempting to connect to MQTT broker at {config.MQTT_BROKER}:{config.MQTT_PORT}")
                logger.info(f"Connection attempt {self.connection_attempts + 1}/{config.MQTT_MAX_RETRIES}")
                
                # Stop any existing loop
                try:
                    self.client.loop_stop()
                except:
                    pass
                
                # Disconnect if already connected
                try:
                    self.client.disconnect()
                except:
                    pass
                
                # Set connection timeout
                logger.info("Calling MQTT connect...")
                self.client.connect(
                    config.MQTT_BROKER,
                    config.MQTT_PORT,
                    keepalive=config.MQTT_KEEPALIVE
                )
                
                # Start the loop in a separate thread
                logger.info("Starting MQTT loop...")
                self.client.loop_start()
                
                # Wait for connection to be established
                time.sleep(2)
                if self.client.is_connected():
                    logger.info(f"Successfully connected to MQTT broker at {config.MQTT_BROKER}:{config.MQTT_PORT}")
                    self.connection_attempts = 0
                    self.reconnect_delay = 1  # Reset delay on success
                    return True
                else:
                    raise Exception("Connection not established")
                    
            except Exception as e:
                self.connection_attempts += 1
                self.failed_connections += 1
                logger.error(f"Failed to connect to MQTT broker: {e}")
                logger.error(f"Connection details:")
                logger.error(f"- Broker IP: {config.MQTT_BROKER}")
                logger.error(f"- Port: {config.MQTT_PORT}")
                logger.error(f"- Keepalive: {config.MQTT_KEEPALIVE}")
                logger.error(f"Please verify that:")
                logger.error(f"1. MQTT broker is running on {config.MQTT_BROKER}:{config.MQTT_PORT}")
                logger.error(f"2. Firewall allows connections to port {config.MQTT_PORT}")
                logger.error(f"3. Network connectivity to {config.MQTT_BROKER} is working")
                
                if self.connection_attempts < config.MQTT_MAX_RETRIES:
                    logger.info(f"Retrying in {config.MQTT_RETRY_DELAY} seconds...")
                    time.sleep(config.MQTT_RETRY_DELAY)
                else:
                    logger.error("Max connection attempts reached")
                    return False
        
        return False

    def _verify_network_connectivity(self):
        """Verify network connectivity to the MQTT broker."""
        import socket
        try:
            # Try to resolve the hostname first
            logger.info(f"Resolving hostname: {config.MQTT_BROKER}")
            ip = socket.gethostbyname(config.MQTT_BROKER)
            logger.info(f"Resolved to IP: {ip}")
            
            # Try to connect to the port
            logger.info(f"Testing port {config.MQTT_PORT} on {ip}")
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(config.NETWORK_TIMEOUT)
            result = sock.connect_ex((config.MQTT_BROKER, config.MQTT_PORT))
            sock.close()
            
            if result == 0:
                logger.info(f"Network connectivity to {config.MQTT_BROKER}:{config.MQTT_PORT} verified")
                return True
            else:
                logger.error(f"Port {config.MQTT_PORT} is not open on {config.MQTT_BROKER} (error code: {result})")
                return False
                
        except socket.gaierror:
            logger.error(f"Cannot resolve hostname: {config.MQTT_BROKER}")
            return False
        except Exception as e:
            logger.error(f"Network verification failed: {e}")
            return False
    
    def _on_connect(self, client, userdata, flags, rc):
        """Callback when connected to MQTT broker."""
        logger.info(f"MQTT connection callback received with result code: {rc}")
        logger.info(f"Connection flags: {flags}")
        
        if rc == 0:
            logger.info("Successfully connected to MQTT broker")
            self.successful_connections += 1
            self.connection_attempts = 0  # Reset connection attempts on success
            self.reconnect_delay = 1  # Reset delay on success
            
            # Subscribe to control topics
            try:
                self.client.subscribe(f"devices/{config.DEVICE_ID}/control/#", qos=1)
                logger.info(f"Subscribed to control topics: devices/{config.DEVICE_ID}/control/#")
            except Exception as e:
                logger.error(f"Failed to subscribe to control topics: {e}")
            
            # Publish online status
            try:
                status_data = {
                    "device_id": config.DEVICE_ID,
                    "timestamp": datetime.now().isoformat(),
                    "status": "connected"
                }
                self.client.publish(
                    f"devices/{config.DEVICE_ID}/status",
                    json.dumps(status_data),
                    qos=1,
                    retain=True
                )
                logger.info("Published online status")
            except Exception as e:
                logger.error(f"Failed to publish online status: {e}")
        else:
            error_messages = {
                1: "Connection refused - incorrect protocol version",
                2: "Connection refused - invalid client identifier",
                3: "Connection refused - server unavailable",
                4: "Connection refused - bad username or password",
                5: "Connection refused - not authorised"
            }
            error_msg = error_messages.get(rc, f"Unknown error code: {rc}")
            logger.error(f"Failed to connect to MQTT broker: {error_msg}")
            self.failed_connections += 1
            if not self.client.is_connected():
                self._connect_with_retry()
    
    def _on_disconnect(self, client, userdata, rc):
        """Callback when disconnected from MQTT broker."""
        logger.info(f"MQTT disconnection callback received with result code: {rc}")
        if rc != 0:
            logger.warning("Unexpected disconnection from MQTT broker")
            self.failed_connections += 1
            if not self.client.is_connected():
                self._connect_with_retry()
        else:
            logger.info("Clean disconnection from MQTT broker")
    
    def _on_publish(self, client, userdata, mid):
        """Callback when message is published."""
        logger.debug(f"Message {mid} published successfully")
    
    def _on_message(self, client, userdata, message):
        """Callback when message is received."""
        try:
            topic = message.topic
            payload = json.loads(message.payload.decode())
            
            # Handle control messages
            if topic.startswith(f"devices/{config.DEVICE_ID}/control/"):
                command = topic.split('/')[-1]
                self._handle_control_command(command, payload)
                
        except Exception as e:
            logger.error(f"Error handling message: {e}")
    
    def _handle_control_command(self, command, payload):
        """Handle control commands from the dashboard."""
        try:
            if command == "restart":
                logger.info("Received restart command")
                # Implement restart logic here
                pass
            elif command == "config":
                logger.info("Received config update")
                # Implement config update logic here
                pass
            else:
                logger.warning(f"Unknown command received: {command}")
                
        except Exception as e:
            logger.error(f"Error handling control command: {e}")
    
    def start_heartbeat_sender(self):
        """Start the heartbeat sender thread."""
        if self.running:
            logger.warning("Heartbeat sender already running")
            return
            
        self.running = True
        self.heartbeat_thread = threading.Thread(target=self._heartbeat_loop, daemon=True)
        self.heartbeat_thread.start()
        logger.info("Heartbeat sender thread started")
    
    def stop(self):
        """Stop the communication module."""
        self.running = False
        
        # Wait for threads to finish
        if hasattr(self, 'heartbeat_thread'):
            self.heartbeat_thread.join(timeout=2.0)
            if self.heartbeat_thread.is_alive():
                logger.warning("Heartbeat thread did not stop cleanly")
            
        if hasattr(self, 'frame_sender_thread'):
            self.frame_sender_thread.join(timeout=2.0)
            if self.frame_sender_thread.is_alive():
                logger.warning("Frame sender thread did not stop cleanly")
        
        # Clear frame buffer
        with self.frame_buffer_lock:
            self.frame_buffer.clear()
        
        # Publish offline status before disconnecting
        try:
            status_data = {
                "device_id": config.DEVICE_ID,
                "timestamp": datetime.now().isoformat(),
                "status": "disconnected"
            }
            self.client.publish(
                f"devices/{config.DEVICE_ID}/status",
                json.dumps(status_data),
                qos=1,
                retain=True
            )
        except Exception as e:
            logger.error(f"Error publishing offline status: {e}")
        
        # Stop MQTT client
        try:
            self.client.loop_stop()
            self.client.disconnect()
        except Exception as e:
            logger.error(f"Error disconnecting MQTT client: {e}")
        
        logger.info("Communication module stopped")
    
    def _get_status_data(self):
        """Get current status data for heartbeat."""
        # Get own IP address
        own_ip = get_local_ip()
        
        # Get GPS position if available
        if self.gps_module:
            position = self.gps_module.get_position()
            lat = position['latitude']
            lon = position['longitude']
            has_fix = position['has_fix']
            satellites = position['satellites']
            altitude = position['altitude']
        else:
            lat = config.DEFAULT_LAT
            lon = config.DEFAULT_LON
            has_fix = False
            satellites = 0
            altitude = 0
        
        # Get gas sensor data if available
        if self.gas_module:
            gas_data = self.gas_module.get_gas_data()
            gas_value = gas_data['gas_value']
            gas_detected = gas_data['gas_detected']
        else:
            gas_value = 0
            gas_detected = False
        
        # Prepare status data
        status_data = {
            'device_id': config.DEVICE_ID,
            'timestamp': datetime.now().isoformat(),
            'predictions': [],  # Empty predictions for heartbeat
            'num_detections': 0,
            'lat': lat,
            'lon': lon,
            'has_gps_fix': has_fix,
            'satellites': satellites,
            'altitude': altitude,
            'gas_value': gas_value,
            'gas_detected': gas_detected,
            'heartbeat': True,
            'sender_ip': own_ip,
            'uptime': time.time() - self.start_time,
            'connection_stats': self.get_connection_stats()
        }
        
        return status_data
    
    def _heartbeat_loop(self):
        """Thread function for sending regular heartbeats."""
        while self.running:
            try:
                current_time = time.time()
                
                # Check if we need to reconnect
                if current_time - self.last_heartbeat > self.heartbeat_timeout:
                    logger.warning("Heartbeat timeout, attempting to reconnect")
                    if not self.client.is_connected():
                        self._connect_with_retry()
                
                # Get current status
                status_data = self._get_status_data()
                
                # Publish heartbeat
                self.client.publish(
                    f"devices/{config.DEVICE_ID}/heartbeat",
                    json.dumps(status_data),
                    qos=1
                )
                
                self.last_heartbeat = current_time
                
            except Exception as e:
                logger.error(f"Error in heartbeat sender: {e}")
                
            # Wait before sending next heartbeat
            time.sleep(config.HEARTBEAT_INTERVAL)
    
    def _frame_sender_loop(self):
        """Thread function for sending buffered frames at controlled rate."""
        while self.running:
            try:
                current_time = time.time()
                time_since_last_frame = current_time - self.last_frame_time
                
                # Check if it's time to send the next frame
                if time_since_last_frame >= self.frame_interval:
                    with self.frame_buffer_lock:
                        if self.frame_buffer:
                            # Get the oldest frame from the buffer
                            frame_data = self.frame_buffer.pop(0)
                            
                            # Publish frame data
                            self.client.publish(
                                f"devices/{config.DEVICE_ID}/frames",
                                json.dumps(frame_data),
                                qos=0
                            )
                            
                            self.last_frame_time = current_time
                            logger.debug(f"Sent frame from buffer. Buffer size: {len(self.frame_buffer)}")
                
                # Small sleep to prevent CPU overuse
                time.sleep(0.01)
                
            except Exception as e:
                logger.error(f"Error in frame sender loop: {e}")
                time.sleep(0.1)  # Longer sleep on error
    
    def send_detection_to_dashboard(self, predictions, frame=None):
        """Send detection data to the dashboard.
        
        Args:
            predictions: List of prediction dictionaries
            frame: Optional frame image data
        """
        try:
            # Get current status data
            status_data = self._get_status_data()
            
            # Add predictions
            status_data['predictions'] = predictions
            status_data['num_detections'] = len(predictions)
            status_data['heartbeat'] = False
            
            # Publish detection data
            self.client.publish(
                f"devices/{config.DEVICE_ID}/detections",
                json.dumps(status_data),
                qos=1
            )
            
            # If frame is provided, add it to the buffer
            if frame is not None:
                import cv2
                import base64
                
                # Resize frame to reduce size
                resized_frame = cv2.resize(frame, (640, 480))
                
                # Convert to JPEG format
                _, buffer = cv2.imencode('.jpg', resized_frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
                
                # Encode as base64 string
                frame_base64 = base64.b64encode(buffer).decode('utf-8')
                
                # Create frame data
                frame_data = {
                    'device_id': config.DEVICE_ID,
                    'timestamp': datetime.now().isoformat(),
                    'frame': frame_base64
                }
                
                # Add frame to buffer with thread safety
                with self.frame_buffer_lock:
                    # If buffer is full, remove oldest frame
                    if len(self.frame_buffer) >= self.max_buffer_size:
                        self.frame_buffer.pop(0)
                        logger.debug("Buffer full, removed oldest frame")
                    
                    self.frame_buffer.append(frame_data)
                    logger.debug(f"Added frame to buffer. Buffer size: {len(self.frame_buffer)}")
            
            logger.info(f"Published {len(predictions)} detections")
            
        except Exception as e:
            logger.error(f"Error sending detection to dashboard: {e}")
    
    def get_connection_stats(self):
        """Get connection statistics."""
        return {
            'connection_attempts': self.connection_attempts,
            'successful_connections': self.successful_connections,
            'failed_connections': self.failed_connections,
            'uptime': time.time() - self.start_time
        }