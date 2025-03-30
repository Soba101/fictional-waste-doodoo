import streamlit as st
import logging
import numpy as np
from datetime import datetime, timedelta
from utils import add_connection_log
import config

# Setup logger
logger = logging.getLogger('waste-dashboard.state')

def initialize_session_state():
    """Initialize session state variables if they don't exist"""
    # Initialize device tracking variables if they don't exist
    if "devices" not in st.session_state:
        st.session_state.devices = {}
    if "device_ips" not in st.session_state:
        st.session_state.device_ips = {}
    if "detection_history" not in st.session_state:
        st.session_state.detection_history = []
    if "connection_log" not in st.session_state:
        st.session_state.connection_log = []
    if "last_processed_data" not in st.session_state:
        st.session_state.last_processed_data = datetime.now()
    if "show_live_feed" not in st.session_state:
        st.session_state.show_live_feed = False
    if "show_connection_log" not in st.session_state:
        st.session_state.show_connection_log = False
    
    # Initialize receiver status if it doesn't exist
    if "receiver_status" not in st.session_state:
        st.session_state.receiver_status = {
            "connection_status": "Not started",
            "connection_attempts": 0,
            "successful_connections": 0,
            "failed_connections": 0,
            "active_devices": set(),
            "running": False
        }
    
    # Initialize memory management settings if they don't exist
    if "max_history_items" not in st.session_state:
        st.session_state.max_history_items = 1000  # Maximum items in detection history
    if "max_log_entries" not in st.session_state:
        st.session_state.max_log_entries = 100    # Maximum connection log entries
    if "cleanup_interval" not in st.session_state:
        st.session_state.cleanup_interval = 3600  # Cleanup old data every hour
    if "last_cleanup" not in st.session_state:
        st.session_state.last_cleanup = datetime.now()
    
    # Run cleanup
    cleanup_old_data()
    
    logger.info("Session state initialized")

def cleanup_old_data():
    """Clean up old data to prevent memory growth"""
    try:
        current_time = datetime.now()
        
        # Run cleanup more frequently for device status
        if (current_time - st.session_state.last_cleanup).total_seconds() < 5:  # Check every 5 seconds
            return
            
        # Trim detection history
        if len(st.session_state.detection_history) > st.session_state.max_history_items:
            st.session_state.detection_history = st.session_state.detection_history[-st.session_state.max_history_items:]
            
        # Trim connection log
        if len(st.session_state.connection_log) > st.session_state.max_log_entries:
            st.session_state.connection_log = st.session_state.connection_log[-st.session_state.max_log_entries:]
            
        # Remove old device data
        timeout = current_time - timedelta(seconds=config.HEARTBEAT_TIMEOUT)
        devices_to_remove = []
        
        # First clear the active devices set
        st.session_state.receiver_status["active_devices"] = set()
        
        # Check each device's status
        for device_id in st.session_state.devices:
            device = st.session_state.devices[device_id]
            last_updated = device.get('last_updated', datetime.min)
            if isinstance(last_updated, str):
                try:
                    last_updated = datetime.fromisoformat(last_updated)
                except:
                    last_updated = datetime.min
            
            # If device hasn't sent a heartbeat recently, mark for removal
            if last_updated < timeout:
                devices_to_remove.append(device_id)
                logger.info(f"Marking device {device_id} for removal (last seen: {last_updated})")
            else:
                # If device is active, add it to the active devices set
                st.session_state.receiver_status["active_devices"].add(device_id)
        
        # Remove the inactive devices
        for device_id in devices_to_remove:
            if device_id in st.session_state.devices:
                del st.session_state.devices[device_id]
            if device_id in st.session_state.device_ips:
                del st.session_state.device_ips[device_id]
            add_connection_log("Device removed", f"Inactive device removed", device_id)
            
        # Update cleanup timestamp
        st.session_state.last_cleanup = current_time
        if devices_to_remove:
            logger.info(f"Removed {len(devices_to_remove)} inactive devices")
        
    except Exception as e:
        logger.error(f"Error during data cleanup: {e}")

def process_queues(receiver):
    """Process data from all queues and update session state"""
    try:
        # Clean up old data first
        cleanup_old_data()
        
        # Update receiver status first
        receiver.update_session_state(st.session_state)
        
        # Process status messages
        try:
            while not receiver.status_queue.empty():
                device_id, status = receiver.status_queue.get_nowait()
                update_device_status(device_id, status)
        except Exception as e:
            logger.error(f"Error processing status queue: {e}")
                
        # Process heartbeats
        try:
            while not receiver.heartbeat_queue.empty():
                device_id, heartbeat_data = receiver.heartbeat_queue.get_nowait()
                if device_id not in st.session_state.devices:
                    st.session_state.devices[device_id] = {
                        "id": device_id,
                        "detections": 0,
                        "gas_alerts": 0,
                        "last_updated": datetime.now(),
                        "waste_categories": {}
                    }
                # Update device data
                device = st.session_state.devices[device_id]
                device.update(heartbeat_data)
                device["last_updated"] = datetime.now()
                # Ensure device is marked as active in receiver status
                if 'receiver_status' in st.session_state:
                    if 'active_devices' not in st.session_state.receiver_status:
                        st.session_state.receiver_status['active_devices'] = set()
                    st.session_state.receiver_status['active_devices'].add(device_id)
                logger.info(f"Updated heartbeat for device {device_id}")
        except Exception as e:
            logger.error(f"Error processing heartbeat queue: {e}")
            logger.exception("Full traceback:")
                
        # Process detections
        try:
            while not receiver.detection_queue.empty():
                device_id, detection = receiver.detection_queue.get_nowait()
                update_device_detections(device_id, detection)
        except Exception as e:
            logger.error(f"Error processing detection queue: {e}")
                
        # Process frames
        try:
            while not receiver.frame_queue.empty():
                device_id, frame = receiver.frame_queue.get_nowait()
                update_device_frame(device_id, frame)
        except Exception as e:
            logger.error(f"Error processing frame queue: {e}")
                
        # Update last processed time
        st.session_state.last_processed_data = datetime.now()
        
    except Exception as e:
        logger.error(f"Error in process_queues: {e}")
        logger.exception("Full traceback:")

def update_device_status(device_id, status):
    """Update device status in session state"""
    if device_id not in st.session_state.devices:
        st.session_state.devices[device_id] = {
            "id": device_id,
            "detections": 0,
            "gas_alerts": 0,
            "last_updated": datetime.now(),
            "lat": status.get('lat', config.MAP_DEFAULT_CENTER[0]),
            "lon": status.get('lon', config.MAP_DEFAULT_CENTER[1])
        }
    
    device = st.session_state.devices[device_id]
    
    # Update GPS coordinates if available
    if 'lat' in status and 'lon' in status:
        device['lat'] = status['lat']
        device['lon'] = status['lon']
    
    # Update IP address if available (check both ip_address and sender_ip fields)
    ip_address = status.get('ip_address') or status.get('sender_ip')
    if ip_address:
        if "device_ips" not in st.session_state:
            st.session_state.device_ips = {}
        if ip_address != st.session_state.device_ips.get(device_id):
            st.session_state.device_ips[device_id] = ip_address
            logger.info(f"Updated IP address for {device_id}: {ip_address}")
            add_connection_log("IP Updated", f"New IP: {ip_address}", device_id)
    
    device.update(status)
    device["last_updated"] = datetime.now()

def update_device_heartbeat(device_id):
    """Update device heartbeat timestamp"""
    if device_id in st.session_state.devices:
        st.session_state.devices[device_id]["last_updated"] = datetime.now()

def update_device_detections(device_id, detection):
    """Update device detection counts and history"""
    if device_id not in st.session_state.devices:
        st.session_state.devices[device_id] = {
            "id": device_id,
            "detections": 0,
            "gas_alerts": 0,
            "last_updated": datetime.now(),
            "waste_categories": {}  # Initialize waste categories
        }
    
    device = st.session_state.devices[device_id]
    
    # Update detection count
    num_detections = detection.get("num_detections", 0)
    device["detections"] += num_detections
    
    # Update gas alerts if present
    if "gas_value" in detection and detection["gas_value"] > 100:
        device["gas_alerts"] += 1
    
    # Update location if present
    if "lat" in detection and "lon" in detection:
        device["lat"] = detection["lat"]
        device["lon"] = detection["lon"]
    
    # Update waste categories
    if "detected_items" in detection:
        if "waste_categories" not in device:
            device["waste_categories"] = {}
            
        for item in detection["detected_items"]:
            category = item.get("class_name", "unknown")
            confidence = item.get("confidence", 0)
            if confidence >= 0.5:  # Only count detections with confidence >= 50%
                device["waste_categories"][category] = device["waste_categories"].get(category, 0) + 1
    
    # Add to detection history
    st.session_state.detection_history.append({
        "device": device_id,
        "count": num_detections,
        "categories": detection.get("detected_items", []),
        "time": datetime.now()
    })
    
    # Keep only last 100 detections
    if len(st.session_state.detection_history) > 100:
        st.session_state.detection_history = st.session_state.detection_history[-100:]
    
    device["last_updated"] = datetime.now()
    
    # Log detection for debugging
    logger.info(f"Updated detection for {device_id}: {num_detections} items, categories: {device['waste_categories']}")

def update_device_frame(device_id, frame):
    """Update device frame data"""
    if device_id in st.session_state.devices:
        st.session_state.devices[device_id]["last_frame"] = frame
        st.session_state.devices[device_id]["last_updated"] = datetime.now()

def calculate_metrics():
    """Calculate current metrics from session state"""
    metrics = {
        "total_detections": 0,
        "detection_rate": 0,
        "total_gas_alerts": 0,
        "gas_delta": 0,
        "active_devices": 0,
        "waste_categories": {},
        "waste_percentages": {}
    }
    
    # Check for active devices (within timeout period)
    current_time = datetime.now()
    timeout = current_time - timedelta(seconds=config.HEARTBEAT_TIMEOUT)
    active_devices = set()
    
    # Clear old devices from receiver status
    st.session_state.receiver_status["active_devices"] = set()
    
    # First pass: identify active devices
    for device_id, device in st.session_state.devices.items():
        last_updated = device.get('last_updated', datetime.min)
        if isinstance(last_updated, str):
            try:
                last_updated = datetime.fromisoformat(last_updated)
            except:
                last_updated = datetime.min
                
        # Only count device as active if it's been updated recently
        if last_updated > timeout:
            active_devices.add(device_id)
            metrics["total_detections"] += device.get("detections", 0)
            metrics["total_gas_alerts"] += device.get("gas_alerts", 0)
    
    # Update active devices count and receiver status
    metrics["active_devices"] = len(active_devices)
    st.session_state.receiver_status["active_devices"] = active_devices
    
    # Second pass: calculate metrics only for active devices
    total_items = 0
    for device_id in active_devices:
        if device_id in st.session_state.devices:
            device = st.session_state.devices[device_id]
            if "waste_categories" in device:
                for category, count in device["waste_categories"].items():
                    metrics["waste_categories"][category] = metrics["waste_categories"].get(category, 0) + count
                    total_items += count
    
    # Calculate percentages
    if total_items > 0:
        for category, count in metrics["waste_categories"].items():
            metrics["waste_percentages"][category] = (count / total_items) * 100
    
    # Calculate detection rate (per hour)
    if st.session_state.detection_history:
        recent_detections = [d for d in st.session_state.detection_history 
                           if d["time"] > current_time - timedelta(hours=1)]
        metrics["detection_rate"] = sum(d["count"] for d in recent_detections)
    
    # Calculate gas alert delta
    if st.session_state.detection_history:
        recent_alerts = sum(1 for device_id in active_devices
                          if device_id in st.session_state.devices
                          and st.session_state.devices[device_id].get("gas_alerts", 0) > 0)
        metrics["gas_delta"] = recent_alerts
    
    # Log metrics for debugging
    logger.info(f"Metrics calculated: Active devices={metrics['active_devices']}, "
               f"Total detections={metrics['total_detections']}, "
               f"Detection rate={metrics['detection_rate']}/hour")
    
    return metrics

def is_mqtt_connected():
    """Check if MQTT connection is active"""
    return (st.session_state.receiver_status.get("running", False) and 
            len(st.session_state.receiver_status.get("active_devices", set())) > 0)