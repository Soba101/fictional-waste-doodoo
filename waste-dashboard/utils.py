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
    """Actively scan the network for edge devices"""
    logger.info("Starting device discovery scan")
    add_connection_log("Discovery scan", "Scanning network for devices")
    
    # Get all local IP addresses to determine network range
    local_ips = []
    try:
        hostname = socket.gethostname()
        ip_info = socket.getaddrinfo(hostname, None)
        for item in ip_info:
            ip = item[4][0]
            if ip not in local_ips and not ip.startswith('127.') and ':' not in ip:  # Skip loopback and IPv6
                local_ips.append(ip)
    except Exception as e:
        logger.error(f"Error getting local IPs: {e}")
        return
    
    # For each local IP, scan that subnet
    for local_ip in local_ips:
        logger.info(f"Scanning subnet for {local_ip}")
        
        ip_parts = local_ip.split('.')
        if len(ip_parts) != 4:
            continue
            
        # Only scan /24 subnet (last octet)
        subnet_base = '.'.join(ip_parts[:3])
        
        def scan_subnet(subnet):
            devices_found = 0
            discovered_devices = {}
            
            for i in range(1, 255):
                test_ip = f"{subnet}.{i}"
                if test_ip == local_ip:
                    continue  # Skip our own IP
                    
                try:
                    # Try to connect to the status endpoint
                    r = requests.get(f"http://{test_ip}:8000/status", timeout=0.5)
                    if r.status_code == 200:
                        try:
                            device_data = r.json()
                            device_id = device_data.get('device_id', 'Unknown')
                            logger.info(f"Discovered device: {device_id} at {test_ip}")
                            
                            # Store discovered device
                            discovered_devices[device_id] = test_ip
                            devices_found += 1
                            
                            # Log the discovery
                            add_connection_log("Device discovered", f"IP: {test_ip}", device_id)
                        except:
                            logger.warning(f"Found web server at {test_ip} but not a valid device")
                except:
                    pass  # Expected for most IPs
            
            # Log the result when complete
            logger.info(f"Subnet scan complete for {subnet}.0/24: Found {devices_found} devices")
            add_connection_log("Subnet scan complete", f"Found {devices_found} devices on {subnet}.0/24")
            
            # Update session state using Streamlit's rerun mechanism
            if discovered_devices:
                if "device_ips" not in st.session_state:
                    st.session_state.device_ips = {}
                st.session_state.device_ips.update(discovered_devices)
                st.rerun()
                
            return devices_found
                
        # Start scan in a separate thread
        scan_thread = threading.Thread(
            target=scan_subnet, 
            args=(subnet_base,), 
            daemon=True
        )
        scan_thread.start()
        logger.info(f"Started scan thread for subnet {subnet_base}")