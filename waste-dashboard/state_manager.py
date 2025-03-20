import streamlit as st
import logging
import numpy as np
from datetime import datetime, timedelta
from data_receiver import data_queue, log_queue
from utils import add_connection_log

# Setup logger
logger = logging.getLogger('waste-dashboard.state-manager')

def initialize_session_state(logger):
    """Initialize all session state variables before starting any threads"""
    if "devices" not in st.session_state:
        logger.info("Initializing devices dictionary")
        st.session_state.devices = {}
        
    if "detection_history" not in st.session_state:
        logger.info("Initializing detection history")
        st.session_state.detection_history = []
        
    if "hourly_stats" not in st.session_state:
        logger.info("Initializing hourly stats")
        # Store hourly detection counts and gas alerts for delta calculations
        st.session_state.hourly_stats = {
            "previous_detections": 0,
            "current_detections": 0,
            "previous_gas_alerts": 0,
            "current_gas_alerts": 0,
            "last_update": datetime.now()
        }
        
    if "last_processed_data" not in st.session_state:
        st.session_state.last_processed_data = datetime.now() - timedelta(minutes=5)

    if "device_ips" not in st.session_state:
        logger.info("Initializing device IPs dictionary")
        st.session_state.device_ips = {}

    if "connection_log" not in st.session_state:
        logger.info("Initializing connection log")
        st.session_state.connection_log = []

    if "receiver_status" not in st.session_state:
        st.session_state.receiver_status = {
            "running": False,
            "connection_status": "Not started",
            "connection_attempts": 0,
            "successful_connections": 0,
            "failed_connections": 0,
            "active_devices": set(),
            "last_connection_time": {}
        }

def process_queues():
    """Process all queues for thread communication - called from main thread"""
    # Process log queue first
    try:
        while not log_queue.empty():
            log_item = log_queue.get_nowait()
            
            # Handle different log types
            if log_item[0] == "STATUS_UPDATE":
                # Update receiver status in session state
                st.session_state.receiver_status = log_item[1]
            elif log_item[0] == "DEVICE_IP_UPDATE":
                # Update device IP in session state
                device_data = log_item[1]
                st.session_state.device_ips[device_data["device_id"]] = device_data["ip"]
            else:
                # Regular log message
                if len(log_item) == 2:
                    add_connection_log(log_item[0], log_item[1])
                elif len(log_item) == 3:
                    add_connection_log(log_item[0], log_item[1], log_item[2])
    except Exception as e:
        logger.error(f"Error processing log queue: {e}")
    
    # Now process data queue
    process_queue_data()

def process_queue_data():
    """Process all available data in the queue and update state"""
    updates = 0
    current_time = datetime.now()
    
    # If an hour has passed, reset the hourly stats
    if current_time - st.session_state.hourly_stats["last_update"] > timedelta(hours=1):
        logger.info("Hourly stats reset")
        st.session_state.hourly_stats["previous_detections"] = st.session_state.hourly_stats["current_detections"]
        st.session_state.hourly_stats["previous_gas_alerts"] = st.session_state.hourly_stats["current_gas_alerts"]
        st.session_state.hourly_stats["current_detections"] = 0
        st.session_state.hourly_stats["current_gas_alerts"] = 0
        st.session_state.hourly_stats["last_update"] = current_time
    
    try:
        while not data_queue.empty():
            data = data_queue.get_nowait()
            
            # Extract device info
            device_id = data.get('device_id', 'Unknown Device')
            timestamp = data.get('timestamp', datetime.now().isoformat())
            
            # *** IMPORTANT FIX: Explicitly mark this device as active ***
            if 'receiver_status' in st.session_state:
                if 'active_devices' not in st.session_state.receiver_status:
                    st.session_state.receiver_status['active_devices'] = set()
                # Add the device to active_devices set
                st.session_state.receiver_status['active_devices'].add(device_id)
                logger.info(f"Explicitly marked device {device_id} as active")
            
            # Add device to devices dict if not exists
            if device_id not in st.session_state.devices:
                # Use location from data if provided
                lat = data.get('lat', 1.3521 + np.random.uniform(-0.01, 0.01))
                lon = data.get('lon', 103.8198 + np.random.uniform(-0.01, 0.01))
                
                # Create URL based on device's IP
                device_ip = st.session_state.device_ips.get(device_id, "127.0.0.1")
                stream_url = f"http://{device_ip}:8000/video_feed"
                
                logger.info(f"Adding new device: {device_id} at {device_ip}")
                st.session_state.devices[device_id] = {
                    "id": device_id,
                    "lat": lat,
                    "lon": lon,
                    "detections": 0,
                    "gas_alerts": 0,
                    "stream_url": stream_url,
                    "last_updated": timestamp
                }
                add_connection_log("New device added", f"Location: {lat}, {lon}", device_id)
                
                        # Update device location if provided in new data
            if device_id in st.session_state.devices:
                # Update GPS coordinates if provided and device has a GPS fix
                if 'lat' in data and 'lon' in data:
                    has_fix = data.get('has_gps_fix', False)
                    if has_fix:  # Only update if GPS has a fix
                        logger.info(f"Updating GPS for {device_id}: {data['lat']}, {data['lon']}")
                        st.session_state.devices[device_id]["lat"] = data['lat']
                        st.session_state.devices[device_id]["lon"] = data['lon']
            
            # *** IMPORTANT FIX: Always update the device IP when receiving data ***
            if 'device_ips' not in st.session_state:
                st.session_state.device_ips = {}
                
            # Get sender's IP address from the connection itself
            client_ip = None
            try:
                # Try to get the sender's IP from the data (your pi might be sending this)
                if 'sender_ip' in data:
                    client_ip = data['sender_ip']
                
                # If we have the IP in the queue data (from the socket)
                if client_ip is None and '_sender_ip' in data:
                    client_ip = data['_sender_ip']
                    
                # Update the device IP if we have one
                if client_ip:
                    st.session_state.device_ips[device_id] = client_ip
                    # Update the stream URL too
                    if device_id in st.session_state.devices:
                        st.session_state.devices[device_id]["stream_url"] = f"http://{client_ip}:8000/video_feed"
                    logger.info(f"Updated IP for {device_id} to {client_ip}")
            except Exception as e:
                logger.error(f"Error updating device IP: {e}")
                
            # Update detection count
            predictions = data.get('predictions', [])
            detection_count = len(predictions)
            
            if detection_count > 0:
                logger.info(f"Received {detection_count} detections from {device_id}")
                st.session_state.devices[device_id]["detections"] += detection_count
                st.session_state.hourly_stats["current_detections"] += detection_count
                
                # Add to detection history for graph
                detection_entry = {
                    "time": datetime.fromisoformat(timestamp) if isinstance(timestamp, str) else timestamp,
                    "device": device_id,
                    "count": detection_count,
                    "classes": [p.get('class', 'unknown') for p in predictions]
                }
                st.session_state.detection_history.append(detection_entry)
                
                # Trim history to last 1000 entries
                if len(st.session_state.detection_history) > 1000:
                    st.session_state.detection_history = st.session_state.detection_history[-1000:]
            
            # Check for gas alerts if included in data
            gas_value = data.get('gas_value', 0)
            gas_threshold = 500  # Default threshold
            if gas_value > gas_threshold:
                logger.info(f"Gas alert from {device_id}: {gas_value}")
                st.session_state.devices[device_id]["gas_alerts"] += 1
                st.session_state.hourly_stats["current_gas_alerts"] += 1
                add_connection_log("Gas alert", f"Value: {gas_value}", device_id)
            
            # Update last update time
            st.session_state.devices[device_id]["last_updated"] = timestamp
            updates += 1
            
            # Updated last processed time
            st.session_state.last_processed_data = current_time
            
    except Exception as e:
        st.error(f"Error processing data: {e}")
        logger.error(f"Error processing data: {e}")
    
    return updates

# Calculate metrics for dashboard
def calculate_metrics():
    total_detections = sum(device["detections"] for device in st.session_state.devices.values())
    total_gas_alerts = sum(device.get("gas_alerts", 0) for device in st.session_state.devices.values())
    
    # Use receiver_status for active devices count
    active_devices = len(st.session_state.receiver_status.get("active_devices", set()))
    
    # Calculate deltas
    detection_delta = st.session_state.hourly_stats["current_detections"] - st.session_state.hourly_stats["previous_detections"]
    gas_delta = st.session_state.hourly_stats["current_gas_alerts"] - st.session_state.hourly_stats["previous_gas_alerts"]
    
    return {
        "total_detections": total_detections,
        "total_gas_alerts": total_gas_alerts,
        "active_devices": active_devices,
        "detection_delta": detection_delta,
        "gas_delta": gas_delta
    }