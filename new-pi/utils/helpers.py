"""
Helper utility functions for the waste detection system.
"""
import socket
import subprocess
import logging

logger = logging.getLogger('utils.helpers')

def get_local_ip():
    """
    Get the device's local IP address.
    
    Returns:
        str: Local IP address or "Unknown" if it cannot be determined
    """
    try:
        # Create a temporary socket to determine the outgoing IP address
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))  # Connect to Google DNS
        local_ip = s.getsockname()[0]
        s.close()
        return local_ip
    except Exception as e:
        logger.error(f"Error getting local IP: {e}")
        return "Unknown"

def get_network_interfaces():
    """
    Get a dictionary of all network interfaces and their IP addresses.
    
    Returns:
        dict: Dictionary of interface names and IP addresses
    """
    interfaces = {}
    try:
        # Try to get hostname and primary IP
        hostname = socket.gethostname()
        primary_ip = socket.gethostbyname(hostname)
        interfaces['primary'] = primary_ip
        
        # Try alternative method using 'hostname -I' command on Linux
        try:
            cmd = "hostname -I"
            output = subprocess.check_output(cmd.split()).decode('utf-8').strip()
            for ip in output.split():
                if ip not in interfaces.values():
                    interfaces[f"iface_{len(interfaces)}"] = ip
        except:
            pass
            
    except Exception as e:
        logger.error(f"Error getting network interfaces: {e}")
        # Return at least one interface so we don't return an empty dictionary
        interfaces = {"unknown": "127.0.0.1"}  # Fallback to localhost
    
    return interfaces

def setup_logging(logger):
    """
    Set up logging configuration.
    
    Args:
        logger: Logger instance to configure
    """
    import logging
    import config
    
    # Create handler for file logging
    file_handler = logging.FileHandler(config.LOG_FILE)
    file_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    file_handler.setFormatter(file_formatter)
    
    # Create handler for console logging
    console_handler = logging.StreamHandler()
    console_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    console_handler.setFormatter(console_formatter)
    
    # Add both handlers to the logger
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    logger.setLevel(logging.INFO)
