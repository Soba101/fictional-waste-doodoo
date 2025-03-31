"""
Helper utility functions for the waste detection system.
"""
import socket
import subprocess
import logging
import config

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
    """Set up logging configuration."""
    try:
        # Create file handler
        fh = logging.FileHandler(config.LOG_FILE)
        fh.setLevel(logging.DEBUG)  # Set to DEBUG for file logging
        
        # Create console handler
        ch = logging.StreamHandler()
        ch.setLevel(logging.INFO)  # Set to INFO for console logging
        
        # Create formatter
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        fh.setFormatter(formatter)
        ch.setFormatter(formatter)
        
        # Remove any existing handlers
        logger.handlers = []
        
        # Add handlers to logger
        logger.addHandler(fh)
        logger.addHandler(ch)
        
        # Set overall logger level to DEBUG
        logger.setLevel(logging.DEBUG)
        
        # Log successful setup
        logger.info("Logging system initialized")
        
    except Exception as e:
        print(f"Error setting up logging: {e}")
        # Set up basic logging as fallback
        logging.basicConfig(
            level=logging.DEBUG,  # Set to DEBUG for maximum visibility
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
