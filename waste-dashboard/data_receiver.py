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

import config

logger = logging.getLogger('data-receiver')

class DataReceiver:
    def __init__(self):
        """Initialize the data receiver with MQTT client"""
        self.client = mqtt.Client(client_id="dashboard_receiver")
        self.client.on_connect = self._on_connect
        self.client.on_message = self._on_message
        
        # Initialize queues for different types of data
        self.status_queue = Queue()
        self.heartbeat_queue = Queue()
        self.detection_queue = Queue()
        self.frame_queue = Queue()
        
        # Internal state tracking
        self._connection_status = "Not started"
        self._connection_attempts = 0
        self._successful_connections = 0
        self._failed_connections = 0
        self._active_devices = set()
        self._is_connected = False
        self._is_running = False
        
        # Initialize session state if not exists
        if 'receiver_status' not in st.session_state:
            st.session_state.receiver_status = {
                'connection_status': 'Disconnected',
                'connection_attempts': 0,
                'successful_connections': 0,
                'failed_connections': 0,
                'active_devices': set(),
                'last_connection_time': None
            }
        
        # Start MQTT client
        self.start()
    
    def start(self):
        """Start the MQTT client"""
        if self._is_running:
            logger.warning("Data receiver already running")
            return True
            
        try:
            logger.info("Starting data receiver")
            self._is_running = True
            self._connection_attempts += 1
            self.client.connect(config.MQTT_BROKER, config.MQTT_PORT, keepalive=config.MQTT_KEEPALIVE)
            self.client.loop_start()
            return True
        except Exception as e:
            logger.error(f"Failed to start data receiver: {e}")
            self._connection_status = f"Failed to connect: {e}"
            self._failed_connections += 1
            self._is_running = False
            return False
    
    def stop(self):
        """Stop the MQTT client"""
        if not self._is_running:
            return True
            
        try:
            self._is_running = False
            self.client.loop_stop()
            self.client.disconnect()
            logger.info("Data receiver stopped")
            self._connection_status = "Stopped"
            self._is_connected = False
            return True
        except Exception as e:
            logger.error(f"Error stopping data receiver: {e}")
            return False
    
    def _on_connect(self, client, userdata, flags, rc):
        """Callback when connected to MQTT broker"""
        if rc == 0:
            if not self._is_connected:
                logger.info("Connected to MQTT broker")
                self._connection_status = "Connected"
                self._successful_connections += 1
                self._is_connected = True
                
                # Subscribe to all device topics
                client.subscribe(f"{config.MQTT_TOPIC_PREFIX}/+/status")
                client.subscribe(f"{config.MQTT_TOPIC_PREFIX}/+/heartbeat")
                client.subscribe(f"{config.MQTT_TOPIC_PREFIX}/+/detections")
                client.subscribe(f"{config.MQTT_TOPIC_PREFIX}/+/frames")
        else:
            logger.error(f"Failed to connect to MQTT broker with code: {rc}")
            self._connection_status = f"Connection failed: {rc}"
            self._failed_connections += 1
            self._is_connected = False
    
    def _on_message(self, client, userdata, msg):
        """Handle incoming MQTT messages"""
        try:
            # Parse topic to get device ID and message type
            topic_parts = msg.topic.split('/')
            if len(topic_parts) != 3:
                logger.warning(f"Invalid topic format: {msg.topic}")
                return
                
            device_id = topic_parts[1]
            msg_type = topic_parts[2]
            
            # Parse message payload
            try:
                payload = json.loads(msg.payload.decode())
            except json.JSONDecodeError:
                logger.warning(f"Invalid JSON in message from {device_id}")
                return
            
            # Add timestamp to payload
            payload['timestamp'] = datetime.now()
            
            # Extract IP address from payload if available
            if 'sender_ip' in payload:
                if 'device_ips' not in st.session_state:
                    st.session_state.device_ips = {}
                if payload['sender_ip'] != st.session_state.device_ips.get(device_id):
                    st.session_state.device_ips[device_id] = payload['sender_ip']
                    logger.info(f"Updated IP for {device_id} to {payload['sender_ip']} from {msg_type}")
            
            # Route message to appropriate queue
            if msg_type == 'status':
                self.status_queue.put((device_id, payload))
            elif msg_type == 'heartbeat':
                self._active_devices.add(device_id)
                self.heartbeat_queue.put(device_id)
            elif msg_type == 'detections':
                self.detection_queue.put((device_id, payload))
            elif msg_type == 'frames':
                self.frame_queue.put((device_id, payload))
            
        except Exception as e:
            logger.error(f"Error processing message: {e}")
    
    def get_status(self):
        """Get current receiver status"""
        return {
            "connection_status": self._connection_status,
            "connection_attempts": self._connection_attempts,
            "successful_connections": self._successful_connections,
            "failed_connections": self._failed_connections,
            "active_devices": self._active_devices,
            "running": self._is_running and self._is_connected
        }
    
    def update_session_state(self, session_state):
        """Update session state with current receiver status - call from main thread only"""
        status = self.get_status()
        session_state.receiver_status.update(status)