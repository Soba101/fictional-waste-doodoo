import streamlit as st
import logging
import socket
import threading
import requests
from datetime import datetime, timedelta

# Setup logger
logger = logging.getLogger('waste-dashboard.utils')

def add_connection_log(event, details=None, device_id=None):
    """Add an entry to the connection log - ONLY CALL FROM MAIN THREAD"""
    if "connection_log" not in st.session_state:
        st.session_state.connection_log = []
        
    log_entry = {
        "timestamp": datetime.now(),
        "event": event
    }
    if details:
        log_entry["details"] = details
    if device_id:
        log_entry["device_id"] = device_id
    
    # Log to file
    if device_id:
        logger.info(f"[{device_id}] {event}: {details}")
    else:
        logger.info(f"{event}: {details}")
        
    # Now it's safe to append to session state from the main thread
    st.session_state.connection_log.append(log_entry)
    
    # Keep only the last 100 entries
    if len(st.session_state.connection_log) > 100:
        st.session_state.connection_log = st.session_state.connection_log[-100:]

def check_device_status(device_id, ip=None):
    """Try to connect to a device's status endpoint"""
    if ip is None and device_id in st.session_state.device_ips:
        ip = st.session_state.device_ips[device_id]
    
    if not ip:
        logger.warning(f"No IP available for device {device_id}")
        return False
        
    try:
        logger.info(f"Checking status of {device_id} at http://{ip}:8000/status")
        r = requests.get(f"http://{ip}:8000/status", timeout=2)
        if r.status_code == 200:
            status_data = r.json()
            logger.info(f"Status response from {device_id}: {status_data}")
            return status_data
        logger.warning(f"Status check failed for {device_id} with status code {r.status_code}")
        return False
    except Exception as e:
        logger.error(f"Error checking device status for {device_id} at {ip}: {e}")
        return False

def discover_devices():
    """Actively scan the network for edge devices using MQTT heartbeats"""
    logger.info("Starting device discovery via MQTT")
    add_connection_log("Discovery scan", "Scanning for devices via MQTT")
    
    # Get MQTT client from session state
    if 'mqtt_client' not in st.session_state:
        logger.error("MQTT client not initialized")
        return
        
    # Subscribe to heartbeat topics if not already subscribed
    mqtt_client = st.session_state.mqtt_client
    if not mqtt_client.is_connected():
        logger.error("MQTT client not connected")
        return
        
    # The MQTT client's message handler will update device_ips
    # when it receives heartbeat messages
    logger.info("Device discovery via MQTT is active")
    add_connection_log("Discovery active", "Listening for device heartbeats via MQTT")
    
    # Don't clear existing devices, just wait for new heartbeats
    return True