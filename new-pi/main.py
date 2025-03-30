#!/usr/bin/env python3
"""
Main entry point for the waste detection system.
Initializes and coordinates all modules.
"""
import logging
import os
import sys
import time
import signal
import threading
from datetime import datetime

# Add the project directory to the Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Import configuration
import config

# Import utility functions
from utils.helpers import setup_logging

# Create main logger
logger = logging.getLogger('waste-detection-system')
setup_logging(logger)

# Global module instances
gps_module = None
gas_sensor = None
detection_module = None
communication_module = None
camera_module = None
web_server = None

def handle_detection(frame, predictions):
    """
    Callback function for handling new detections.
    
    Args:
        frame: The image frame with detections
        predictions: List of prediction dictionaries
    """
    try:
        # Get gas and GPS data for visualization
        gas_data = None
        if gas_sensor and config.GAS_ENABLED:
            gas_data = gas_sensor.get_gas_data()
        
        gps_data = None
        if gps_module and config.GPS_ENABLED:
            gps_data = gps_module.get_position()
        
        # Process frame with predictions and sensor data
        processed_frame = detection_module.process_frame_with_predictions(
            frame, predictions, gas_data, gps_data
        )
        
        # Send data to dashboard and database
        if communication_module:
            communication_module.send_detection_to_dashboard(predictions)
            communication_module.send_detection_to_database(predictions, processed_frame)
        
        return processed_frame
    except Exception as e:
        logger.error(f"Error handling detection: {e}")
        return frame

def handle_new_frame(frame):
    """
    Callback function for handling new camera frames.
    
    Args:
        frame: The new camera frame
    """
    try:
        # Add frame to detection module's buffer
        if detection_module:
            detection_module.add_frame(frame)
        return frame
    except Exception as e:
        logger.error(f"Error handling new frame: {e}")
        return frame

def verify_gps_fix(gps_module, timeout=10):
    """
    Verify GPS fix with timeout.
    
    Args:
        gps_module: GPS module instance
        timeout: Maximum time to wait for fix in seconds
    
    Returns:
        bool: True if fix obtained, False otherwise
    """
    start_time = time.time()
    while time.time() - start_time < timeout:
        try:
            position = gps_module.get_position()
            if position['has_fix']:
                return True
            time.sleep(0.5)  # Reduced sleep time
        except Exception as e:
            logger.error(f"Error checking GPS fix: {e}")
            time.sleep(0.5)  # Reduced sleep time
    return False

def signal_handler(signum, frame):
    """Handle system signals for graceful shutdown."""
    logger.info(f"Received signal {signum}")
    cleanup()
    os._exit(0)

def initialize_modules():
    """Initialize all system modules."""
    global gps_module, gas_sensor, detection_module, communication_module, camera_module, web_server
    
    try:
        # First, ensure any existing GPIO resources are cleaned up
        try:
            if gas_sensor:
                gas_sensor.stop()
                time.sleep(1)
        except Exception as e:
            logger.warning(f"Error cleaning up existing gas sensor: {e}")
        
        # Initialize GPS module if enabled
        if config.GPS_ENABLED:
            try:
                from modules.gps_module import GPSModule
                logger.info("Initializing GPS module...")
                gps_module = GPSModule(port=config.GPS_PORT, logger=logger)
                if gps_module.start():
                    logger.info("GPS module started successfully")
                    # Verify GPS fix with shorter timeout
                    if verify_gps_fix(gps_module, timeout=10):
                        logger.info("GPS fix obtained successfully")
                    else:
                        logger.warning("GPS fix not obtained, using Singapore default coordinates")
                        # Set default Singapore coordinates
                        gps_module.set_default_position(
                            latitude=1.3521,  # Singapore latitude
                            longitude=103.8198  # Singapore longitude
                        )
                else:
                    logger.warning("Failed to start GPS module, using Singapore default coordinates")
                    # Set default Singapore coordinates
                    gps_module.set_default_position(
                        latitude=1.3521,  # Singapore latitude
                        longitude=103.8198  # Singapore longitude
                    )
            except Exception as e:
                logger.error(f"Error initializing GPS module: {e}")
                logger.warning("Continuing without GPS functionality")
        
        # Add delay before initializing gas sensor
        time.sleep(2)
        
        # Initialize gas sensor if enabled
        if config.GAS_ENABLED:
            try:
                from modules.gas_sensor_module import GasSensorModule
                logger.info("Initializing gas sensor module...")
                gas_sensor = GasSensorModule(pin=config.GAS_PIN, active_low=True, logger=logger)
                if gas_sensor.start():
                    logger.info("Gas sensor started successfully")
                    # Verify sensor reading
                    gas_data = gas_sensor.get_gas_data()
                    logger.info(f"Initial gas reading: {gas_data}")
                else:
                    logger.warning("Failed to start gas sensor")
            except Exception as e:
                logger.error(f"Error initializing gas sensor: {e}")
                logger.warning("Continuing without gas sensor functionality")
        
        # Add delay before initializing detection module
        time.sleep(1)
        
        # Initialize detection module
        try:
            from modules.detection_module import DetectionModule
            detection_module = DetectionModule(detection_callback=handle_detection)
            detection_module.start()  # Start the processing thread
            logger.info("Detection module initialized and started")
        except Exception as e:
            logger.error(f"Error initializing detection module: {e}")
            raise  # Detection module is critical, cannot continue without it
        
        # Add delay before initializing communication module
        time.sleep(1)
        
        # Initialize communication module
        try:
            from modules.communication import CommunicationModule
            logger.info("Initializing communication module...")
            communication_module = CommunicationModule(gps_module, gas_sensor)
            logger.info("Communication module initialized successfully")
        except Exception as e:
            logger.error(f"Error initializing communication module: {e}")
            raise  # Communication module is critical, cannot continue without it
        
        # Add delay before initializing camera module
        time.sleep(1)
        
        # Initialize camera module
        try:
            from modules.camera_module import CameraModule
            camera_module = CameraModule(frame_callback=handle_new_frame)
            camera_module.start()
            logger.info("Camera module initialized and started")
        except Exception as e:
            logger.error(f"Error initializing camera module: {e}")
            raise  # Camera module is critical, cannot continue without it
        
        # Add delay before initializing web server
        time.sleep(1)
        
        # Initialize and start web server
        try:
            from modules.web_server import WebServer
            web_server = WebServer(
                camera_module, 
                detection_module, 
                communication_module, 
                gps_module, 
                gas_sensor
            )
            logger.info("Web server module initialized")
        except Exception as e:
            logger.error(f"Error initializing web server: {e}")
            raise  # Web server is critical, cannot continue without it
        
        return True
        
    except Exception as e:
        logger.error(f"Error initializing modules: {e}")
        cleanup()
        return False

def cleanup():
    """Clean up resources before exiting."""
    logger.info("Cleaning up resources...")
    
    # Stop web server first
    try:
        if web_server:
            logger.info("Stopping web server...")
            web_server.stop()
    except Exception as e:
        logger.error(f"Error stopping web server: {e}")
    
    # Stop camera module
    try:
        if camera_module:
            logger.info("Stopping camera module...")
            camera_module.stop()
    except Exception as e:
        logger.error(f"Error stopping camera module: {e}")
    
    # Stop detection module
    try:
        if detection_module:
            logger.info("Stopping detection module...")
            detection_module.stop()
    except Exception as e:
        logger.error(f"Error stopping detection module: {e}")
    
    # Stop communication module
    try:
        if communication_module:
            logger.info("Stopping communication module...")
            communication_module.stop()
            # Wait for any pending messages to be sent
            time.sleep(1)
    except Exception as e:
        logger.error(f"Error stopping communication module: {e}")
    
    # Stop GPS module
    try:
        if gps_module:
            logger.info("Stopping GPS module...")
            gps_module.stop()
    except Exception as e:
        logger.error(f"Error stopping GPS module: {e}")
    
    # Stop gas sensor
    try:
        if gas_sensor:
            logger.info("Stopping gas sensor...")
            gas_sensor.stop()
    except Exception as e:
        logger.error(f"Error stopping gas sensor: {e}")
    
    logger.info("Cleanup completed")

def main():
    """Main function to initialize and start all modules."""
    try:
        # Set up signal handlers
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
        
        logger.info("=" * 50)
        logger.info("WASTE DETECTION SYSTEM STARTING")
        logger.info("=" * 50)
        logger.info(f"Dashboard IP: {config.DASHBOARD_IP}")
        logger.info(f"Dashboard Port: {config.DASHBOARD_PORT}")
        logger.info(f"GPS Enabled: {config.GPS_ENABLED}")
        logger.info(f"Gas Sensor Enabled: {config.GAS_ENABLED}")
        logger.info(f"Log File: {config.LOG_FILE}")
        logger.info("=" * 50)
        
        # Initialize all modules
        if not initialize_modules():
            logger.error("Failed to initialize modules")
            return
        
        # Start web server in a separate thread
        web_server_thread = threading.Thread(target=web_server.start, daemon=True)
        web_server_thread.start()
        
        # Keep the main thread alive
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            logger.info("Application stopped by user")
            cleanup()
            os._exit(0)
        
    except Exception as e:
        logger.error(f"Application error: {e}")
        logger.exception("Full traceback:")
        cleanup()
        os._exit(1)

if __name__ == "__main__":
    main()
