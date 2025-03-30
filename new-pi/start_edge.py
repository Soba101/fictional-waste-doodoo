#!/usr/bin/env python3
"""
Startup script for the edge device (Pi5).
Handles hardware checks and edge device startup.
"""
import subprocess
import time
import logging
import os
import sys
import socket
from pathlib import Path

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('edge-startup')

def is_root():
    """Check if the script is running with root privileges."""
    return os.geteuid() == 0

def get_venv_python():
    """Get the virtual environment's Python interpreter path."""
    return os.path.join(os.path.dirname(sys.executable), 'python')

def restart_with_sudo():
    """Restart the script with sudo privileges."""
    try:
        # Get the virtual environment's Python interpreter
        venv_python = get_venv_python()
        # Get the full path to this script
        script_path = os.path.abspath(__file__)
        # Get the virtual environment's path
        venv_path = os.path.dirname(os.path.dirname(sys.executable))
        # Get the user's home directory
        user_home = os.path.expanduser('~')
        # Set up environment variables to preserve virtual environment
        env = os.environ.copy()
        env['VIRTUAL_ENV'] = venv_path
        env['PATH'] = f"{os.path.join(venv_path, 'bin')}:{env.get('PATH', '')}"
        env['HOME'] = user_home  # Set HOME to user's home directory
        # Restart with sudo
        os.execvpe('sudo', ['sudo', '-E', '-H', venv_python, script_path], env)
    except Exception as e:
        logger.error(f"Failed to restart with sudo: {e}")
        sys.exit(1)

def check_network_connectivity(host, port, timeout=5):
    """Check if a host and port are accessible."""
    try:
        socket.create_connection((host, port), timeout=timeout)
        return True
    except (socket.timeout, ConnectionRefusedError):
        return False

def check_mqtt_broker():
    """Check if the MQTT broker is accessible."""
    from config import MQTT_BROKER, MQTT_PORT
    if not check_network_connectivity(MQTT_BROKER, MQTT_PORT):
        logger.error(f"Cannot connect to MQTT broker at {MQTT_BROKER}:{MQTT_PORT}")
        return False
    return True

def check_hardware():
    """Check if required hardware is available."""
    from config import GPS_ENABLED, GAS_ENABLED, GPS_PORT
    
    hardware_ok = True
    
    if GPS_ENABLED:
        if not os.path.exists(GPS_PORT):
            logger.warning(f"GPS module not found at {GPS_PORT}")
            hardware_ok = False
        else:
            # Check GPS permissions
            try:
                # Try to open the port for reading
                fd = os.open(GPS_PORT, os.O_RDONLY)
                # Close the file descriptor
                os.close(fd)
            except PermissionError:
                logger.error(f"No permission to access GPS port {GPS_PORT}")
                hardware_ok = False
            except Exception as e:
                logger.error(f"Error accessing GPS port {GPS_PORT}: {e}")
                hardware_ok = False
    
    if GAS_ENABLED:
        # Check if GPIO is accessible using gpiozero
        try:
            from gpiozero import DigitalInputDevice
            from gpiozero.pins.lgpio import LGPIOFactory
            # Test GPIO access with a temporary pin
            test_pin = DigitalInputDevice(17, pin_factory=LGPIOFactory())
            test_pin.close()
        except Exception as e:
            logger.error(f"Failed to access GPIO: {e}")
            hardware_ok = False
    
    return hardware_ok

def check_camera():
    """Check if the camera is available."""
    try:
        # Try to capture a test image
        subprocess.run(['libcamera-still', '-t', '1', '-o', '/dev/null'], 
                      capture_output=True, check=True)
        return True
    except subprocess.CalledProcessError:
        logger.error("Camera is not accessible")
        return False

def check_dependencies():
    """Check if all required Python packages are installed."""
    required_packages = [
        'numpy',
        'cv2',  # opencv-python
        'tflite_runtime',  # tflite-runtime
        'serial',  # pyserial
        'gpiozero'  # For GPIO access on Pi 5
    ]
    
    missing_packages = []
    for package in required_packages:
        try:
            if '.' in package:
                # Handle dotted imports (e.g., paho.mqtt.client)
                parts = package.split('.')
                module = __import__(parts[0])
                for part in parts[1:]:
                    module = getattr(module, part)
            else:
                __import__(package)
        except ImportError:
            # Convert internal names back to package names for display
            display_name = {
                'cv2': 'opencv-python',
                'tflite_runtime': 'tflite-runtime',
                'serial': 'pyserial',
                'paho.mqtt.client': 'paho-mqtt'
            }.get(package, package)
            missing_packages.append(display_name)
    
    # Special check for paho-mqtt
    try:
        import paho.mqtt.client as mqtt
    except ImportError:
        missing_packages.append('paho-mqtt')
    
    if missing_packages:
        logger.error(f"Missing required packages: {', '.join(missing_packages)}")
        return False
    return True

def check_disk_space():
    """Check if there's enough disk space available."""
    try:
        import shutil
        total, used, free = shutil.disk_usage("/")
        free_gb = free / (2**30)  # Convert to GB
        if free_gb < 1:  # Less than 1GB free
            logger.error(f"Low disk space: {free_gb:.1f}GB free")
            return False
        return True
    except Exception as e:
        logger.error(f"Failed to check disk space: {e}")
        return False

def start_edge_device():
    """Start the edge device."""
    try:
        logger.info("Starting edge device...")
        # Get the directory of this script
        script_dir = Path(__file__).parent
        # Change to the script directory
        os.chdir(script_dir)
        
        # Set environment variables for run.py
        os.environ['STARTED_BY_SCRIPT'] = 'true'
        
        # Get the virtual environment's Python interpreter
        venv_python = get_venv_python()
        
        # Start the device with the virtual environment's Python
        subprocess.run([venv_python, 'run.py'], check=True)
    except subprocess.CalledProcessError as e:
        logger.error(f"Edge device failed to start: {e}")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        sys.exit(1)

def main():
    """Main startup sequence."""
    try:
        # Check if we have root privileges
        if not is_root():
            logger.info("Restarting with sudo privileges...")
            restart_with_sudo()
            return
        
        # Check dependencies
        logger.info("Checking dependencies...")
        if not check_dependencies():
            logger.error("Missing required dependencies. Please install them first.")
            sys.exit(1)
        
        # Check disk space
        logger.info("Checking disk space...")
        if not check_disk_space():
            logger.error("Insufficient disk space. Please free up some space.")
            sys.exit(1)
        
        # Check network connectivity
        logger.info("Checking network connectivity...")
        if not check_mqtt_broker():
            logger.error("MQTT broker is not accessible. Please check your network connection.")
            sys.exit(1)
        
        # Check hardware
        logger.info("Checking hardware...")
        if not check_hardware():
            logger.error("Hardware check failed. Please check your connections.")
            sys.exit(1)
        
        # Check camera
        logger.info("Checking camera...")
        if not check_camera():
            logger.error("Camera check failed. Please check your camera connection.")
            sys.exit(1)
        
        # Start the edge device
        start_edge_device()
        
    except KeyboardInterrupt:
        logger.info("Shutting down...")
        sys.exit(0)
    except Exception as e:
        logger.error(f"Startup failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main() 