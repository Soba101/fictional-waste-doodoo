"""
Communication module for sending data to dashboard and database servers.
"""
import socket
import json
import logging
import threading
import time
import base64
import cv2
from datetime import datetime

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
        self.gps_module = gps_module
        self.gas_module = gas_module
        self.connection_attempts = 0
        self.successful_connections = 0
        self.failed_connections = 0
        self.start_time = time.time()
        self.heartbeat_thread = None
        self.running = False
        
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
        """Stop the heartbeat sender thread."""
        self.running = False
        if self.heartbeat_thread:
            self.heartbeat_thread.join(timeout=1.0)
            logger.info("Heartbeat sender thread stopped")
    
    def _heartbeat_loop(self):
        """Thread function for sending regular heartbeats."""
        while self.running:
            try:
                self.send_heartbeat()
            except Exception as e:
                logger.error(f"Error in heartbeat sender: {e}")
                
            # Wait before sending next heartbeat
            time.sleep(config.HEARTBEAT_INTERVAL)
    
    def send_heartbeat(self):
        """Send a heartbeat message to the dashboard server."""
        try:
            # Get own IP address
            own_ip = get_local_ip()
            
            # Get GPS position if available
            if self.gps_module:
                position = self.gps_module.get_position()
                # Use GPS coordinates directly without checking for fix (matches original behavior)
                lat = position['latitude']
                lon = position['longitude']
                has_fix = position['has_fix']
                satellites = position['satellites']
                altitude = position['altitude']
                logger.info(f"Using GPS coordinates: {lat}, {lon} (has_fix={has_fix}, satellites={satellites})")
            else:
                # Default values if GPS module not available
                logger.warning("No GPS module available, using default coordinates")
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
            
            # Prepare heartbeat data
            heartbeat_data = {
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
                'sender_ip': own_ip
            }
            
            # Send the heartbeat
            self.connection_attempts += 1
            
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                sock.settimeout(2)
                sock.connect((config.DASHBOARD_IP, config.DASHBOARD_PORT))
                data_json = json.dumps(heartbeat_data)
                sock.sendall(data_json.encode('utf-8'))
            
            self.successful_connections += 1
            logger.info("Sent heartbeat to dashboard")
            
        except Exception as e:
            self.failed_connections += 1
            logger.error(f"Error sending heartbeat: {e}")
    
    def send_detection_to_dashboard(self, predictions):
        """
        Send detection data to the dashboard server.
        
        Args:
            predictions: List of prediction dictionaries
        """
        try:
            # Get GPS position if available
            if self.gps_module:
                position = self.gps_module.get_position()
                lat = position['latitude']
                lon = position['longitude']
                has_fix = position['has_fix']
                satellites = position['satellites']
                altitude = position['altitude']
            else:
                # Default values if GPS not available
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
            
            # Create data payload with GPS and gas data
            data = {
                'device_id': config.DEVICE_ID,
                'timestamp': datetime.now().isoformat(),
                'predictions': predictions,
                'num_detections': len(predictions),
                'lat': lat,
                'lon': lon,
                'has_gps_fix': has_fix,
                'satellites': satellites,
                'altitude': altitude,
                'gas_value': gas_value,
                'gas_detected': gas_detected
            }
            
            # Log detection information
            logger.info(f"Sending {len(predictions)} detections to dashboard with GPS: {lat}, {lon}")
            
            # Send the data
            self.connection_attempts += 1
            
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                sock.settimeout(2)
                sock.connect((config.DASHBOARD_IP, config.DASHBOARD_PORT))
                data_json = json.dumps(data)
                sock.sendall(data_json.encode('utf-8'))
            
            self.successful_connections += 1
            logger.info(f"Successfully sent detections to dashboard")
            
        except Exception as e:
            self.failed_connections += 1
            logger.error(f"Failed to send detections to dashboard: {str(e)}")
    
    def send_detection_to_database(self, predictions, frame=None):
        """
        Send detection data and keyframe to the database server.
        
        Args:
            predictions: List of prediction dictionaries
            frame: Optional image frame to include
        """
        try:
            # Get device IP address
            local_ip = get_local_ip()
            
            # Get GPS position if available
            if self.gps_module:
                position = self.gps_module.get_position()
                lat = position['latitude']
                lon = position['longitude']
                has_fix = position['has_fix']
                satellites = position['satellites']
                altitude = position['altitude']
            else:
                # Default values if GPS not available
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
            
            # Create data payload
            data = {
                'device_id': config.DEVICE_ID,
                'ip_address': local_ip,
                'timestamp': datetime.now().isoformat(),
                'predictions': predictions,
                'num_detections': len(predictions),
                'lat': lat,
                'lon': lon, 
                'has_gps_fix': has_fix,
                'satellites': satellites,
                'altitude': altitude,
                'gas_value': gas_value,
                'gas_detected': gas_detected
            }
            
            # Add frame to payload if provided
            if frame is not None:
                # Resize frame to reduce size (adjust dimensions as needed)
                resized_frame = cv2.resize(frame, (640, 480))
                
                # Convert to JPEG format (better compression)
                _, buffer = cv2.imencode('.jpg', resized_frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
                
                # Encode as base64 string
                frame_base64 = base64.b64encode(buffer).decode('utf-8')
                
                # Add to data payload
                data['frame'] = frame_base64
            
            # Log sending information
            logger.info(f"Sending {len(predictions)} detections to database server with GPS: {lat}, {lon}")
            
            # Send the data
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                sock.settimeout(3)
                sock.connect((config.DATABASE_IP, config.DATABASE_PORT))
                data_json = json.dumps(data)
                sock.sendall(data_json.encode('utf-8'))
            
            logger.info(f"Successfully sent detections to database server")
            
        except Exception as e:
            logger.error(f"Failed to send detections to database: {str(e)}")
    
    def get_connection_stats(self):
        """Get connection statistics."""
        return {
            'connection_attempts': self.connection_attempts,
            'successful_connections': self.successful_connections,
            'failed_connections': self.failed_connections,
            'uptime': time.time() - self.start_time
        }