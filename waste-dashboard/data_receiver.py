"""
Data receiver module for the dashboard using MQTT.
"""
import json
import logging
import threading
import time
from datetime import datetime
import paho.mqtt.client as mqtt
from queue import Queue
import streamlit as st
import socket
import uuid

import config

logger = logging.getLogger('data-receiver')

class DataReceiver:
    def __init__(self):
        """Initialize the data receiver with MQTT client"""
        # Log MQTT configuration
        logger.info(f"Initializing MQTT client with broker: {config.MQTT_BROKER}:{config.MQTT_PORT}")
        
        # Generate unique client ID
        client_id = f"dashboard_receiver_{uuid.uuid4().hex[:8]}"
        logger.info(f"Using client ID: {client_id}")
        
        # Test broker connection
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(2)
            result = sock.connect_ex((config.MQTT_BROKER, config.MQTT_PORT))
            if result == 0:
                logger.info(f"MQTT broker port {config.MQTT_PORT} is open on {config.MQTT_BROKER}")
            else:
                logger.warning(f"MQTT broker port {config.MQTT_PORT} is closed on {config.MQTT_BROKER}")
            sock.close()
        except Exception as e:
            logger.error(f"Error checking MQTT broker: {e}")
        
        # Initialize MQTT client with clean session
        self.client = mqtt.Client(client_id=client_id, clean_session=True)
        self.client.on_connect = self._on_connect
        self.client.on_message = self._on_message
        self.client.on_disconnect = self._on_disconnect
        
        # Set last will and testament
        will_topic = f"{config.MQTT_TOPIC_PREFIX}/dashboard/{client_id}/status"
        will_payload = json.dumps({"status": "disconnected", "timestamp": datetime.now().isoformat()})
        self.client.will_set(will_topic, will_payload, qos=1, retain=False)
        
        # Initialize queues for different types of data
        self.status_queue = Queue()
        self.heartbeat_queue = Queue()
        self.detection_queue = Queue()
        self.frame_queue = Queue()
        self.session_state_queue = Queue()  # New queue for session state updates
        
        # Internal state tracking
        self._connection_status = "Not started"
        self._connection_attempts = 0
        self._successful_connections = 0
        self._failed_connections = 0
        self._active_devices = set()
        self._is_connected = False
        self._is_running = False
        self._last_connection_time = None
        self._client_id = client_id
        
        # Initialize session state if not exists
        if 'receiver_status' not in st.session_state:
            st.session_state.receiver_status = {
                'connection_status': 'Disconnected',
                'connection_attempts': 0,
                'successful_connections': 0,
                'failed_connections': 0,
                'active_devices': set(),
                'last_connection_time': None,
                'running': False,
                'client_id': client_id
            }
        
        # Start MQTT client
        self.start()
    
    def start(self):
        """Start the MQTT client"""
        if self._is_running:
            logger.warning("Data receiver already running")
            return True
            
        try:
            logger.info(f"Starting data receiver - Connecting to {config.MQTT_BROKER}:{config.MQTT_PORT}")
            self._is_running = True
            self._connection_attempts += 1
            self._last_connection_time = datetime.now()
            
            # Set keepalive and connection timeout
            self.client.connect(
                config.MQTT_BROKER, 
                config.MQTT_PORT, 
                keepalive=config.MQTT_KEEPALIVE
            )
            self.client.loop_start()
            logger.info("MQTT client loop started")
            return True
        except Exception as e:
            logger.error(f"Failed to start data receiver: {e}")
            self._connection_status = f"Failed to connect: {e}"
            self._failed_connections += 1
            self._is_running = False
            return False
    
    def _on_disconnect(self, client, userdata, rc):
        """Callback when disconnected from MQTT broker"""
        logger.warning(f"Disconnected from MQTT broker with code: {rc}")
        self._is_connected = False
        self._connection_status = "Disconnected"
        
        # Attempt to reconnect if we were previously connected
        if self._is_running and rc != 0:
            logger.info("Attempting to reconnect...")
            self.client.reconnect()
    
    def _on_connect(self, client, userdata, flags, rc):
        """Callback when connected to MQTT broker"""
        if rc == 0:
            if not self._is_connected:
                logger.info("Connected to MQTT broker")
                self._connection_status = "Connected"
                self._successful_connections += 1
                self._is_connected = True
                self._last_connection_time = datetime.now()
                
                # Subscribe to all device topics
                topics = [
                    f"{config.MQTT_TOPIC_PREFIX}/+/status",
                    f"{config.MQTT_TOPIC_PREFIX}/+/heartbeat",
                    f"{config.MQTT_TOPIC_PREFIX}/+/detections",
                    f"{config.MQTT_TOPIC_PREFIX}/+/frames"
                ]
                
                for topic in topics:
                    try:
                        client.subscribe(topic)
                        logger.info(f"Subscribed to topic: {topic}")
                    except Exception as e:
                        logger.error(f"Failed to subscribe to {topic}: {e}")
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
            self._connection_status = f"Connection failed: {error_msg}"
            self._failed_connections += 1
            self._is_connected = False
    
    def _on_message(self, client, userdata, message):
        """Handle incoming MQTT messages."""
        try:
            topic = message.topic
            payload = json.loads(message.payload.decode())
            
            # Extract device ID from topic
            device_id = topic.split('/')[1]
            
            # Log message details
            logger.info(f"Received message on topic {topic} from device {device_id}")
            
            # Queue the message for processing in the main thread
            if 'heartbeat' in topic:
                self.heartbeat_queue.put((device_id, payload))
                # Queue session state update
                self.session_state_queue.put(('update_active_device', device_id))
                logger.info(f"Received heartbeat from {device_id}")
                
            elif 'status' in topic:
                self.status_queue.put((device_id, payload))
                logger.info(f"Received status from {device_id}")
                
            elif 'detections' in topic:
                self.detection_queue.put((device_id, payload))
                logger.info(f"Received detection from {device_id}")
                
            elif 'frames' in topic:
                self.frame_queue.put((device_id, payload))
                logger.info(f"Received frame from {device_id}")
                
            # Queue IP update if available
            if 'sender_ip' in payload:
                self.session_state_queue.put(('update_device_ip', device_id, payload['sender_ip']))
                logger.info(f"Device {device_id} IP: {payload['sender_ip']}")
                
        except Exception as e:
            logger.error(f"Error processing message: {e}")
            logger.exception("Full traceback:")
    
    def get_status(self):
        """Get current receiver status"""
        return {
            "connection_status": self._connection_status,
            "connection_attempts": self._connection_attempts,
            "successful_connections": self._successful_connections,
            "failed_connections": self._failed_connections,
            "active_devices": self._active_devices,
            "running": self._is_running and self._is_connected,
            "last_connection_time": self._last_connection_time
        }
    
    def update_session_state(self, session_state):
        """Update session state with current receiver status - call from main thread only"""
        # Process any pending session state updates
        while not self.session_state_queue.empty():
            try:
                update_type = self.session_state_queue.get_nowait()
                if update_type[0] == 'update_active_device':
                    device_id = update_type[1]
                    if 'active_devices' not in session_state.receiver_status:
                        session_state.receiver_status['active_devices'] = set()
                    session_state.receiver_status['active_devices'].add(device_id)
                    logger.info(f"Added device {device_id} to active devices")
                elif update_type[0] == 'update_device_ip':
                    device_id, ip = update_type[1], update_type[2]
                    if 'device_ips' not in session_state:
                        session_state.device_ips = {}
                    session_state.device_ips[device_id] = ip
                    logger.info(f"Updated IP for device {device_id}: {ip}")
            except Exception as e:
                logger.error(f"Error processing session state update: {e}")
        
        # Update receiver status
        status = self.get_status()
        session_state.receiver_status.update(status)

    def stop(self):
        """Stop the MQTT client and clean up resources"""
        try:
            logger.info("Stopping data receiver...")
            self._is_running = False
            
            # Stop the MQTT client loop
            if hasattr(self, 'client'):
                self.client.loop_stop()
                self.client.disconnect()
                logger.info("MQTT client disconnected")
            
            # Clear queues
            while not self.status_queue.empty():
                try:
                    self.status_queue.get_nowait()
                except:
                    pass
            while not self.heartbeat_queue.empty():
                try:
                    self.heartbeat_queue.get_nowait()
                except:
                    pass
            while not self.detection_queue.empty():
                try:
                    self.detection_queue.get_nowait()
                except:
                    pass
            while not self.frame_queue.empty():
                try:
                    self.frame_queue.get_nowait()
                except:
                    pass
            while not self.session_state_queue.empty():
                try:
                    self.session_state_queue.get_nowait()
                except:
                    pass
            
            logger.info("Data receiver stopped successfully")
        except Exception as e:
            logger.error(f"Error stopping data receiver: {e}")
            logger.exception("Full traceback:")