#!/usr/bin/env python3
"""
Main entry point for the waste detection system.
Initializes and coordinates all modules.
"""
import logging
import os
import sys
import time
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

def handle_detection(frame, predictions):
    """
    Callback function for handling new detections.
    
    Args:
        frame: The image frame with detections
        predictions: List of prediction dictionaries
    """
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
    communication_module.send_detection_to_dashboard(predictions)
    communication_module.send_detection_to_database(predictions, processed_frame)
    
    return processed_frame

def handle_new_frame(frame):
    """
    Callback function for handling new camera frames.
    
    Args:
        frame: The new camera frame
    """
    # Run detection on the frame
    predictions = detection_module.detect(frame)
    
    # If there are predictions, they will be handled by the detection callback
    return frame

def main():
    """Main function to initialize and start all modules."""
    try:
        logger.info("=" * 50)
        logger.info("WASTE DETECTION SYSTEM STARTING")
        logger.info("=" * 50)
        logger.info(f"Dashboard IP: {config.DASHBOARD_IP}")
        logger.info(f"Dashboard Port: {config.DASHBOARD_PORT}")
        logger.info(f"GPS Enabled: {config.GPS_ENABLED}")
        logger.info(f"Gas Sensor Enabled: {config.GAS_ENABLED}")
        logger.info(f"Log File: {config.LOG_FILE}")
        logger.info("=" * 50)
        
        # Initialize GPS module if enabled
        global gps_module
        gps_module = None
        if config.GPS_ENABLED:
            try:
                from modules.gps_module import GPSModule
                logger.info("Initializing GPS module...")
                gps_module = GPSModule(port=config.GPS_PORT, logger=logger)
                if gps_module.start():
                    logger.info("GPS module started successfully")
                else:
                    logger.warning("Failed to start GPS module, using default coordinates")
            except Exception as e:
                logger.error(f"Error initializing GPS module: {e}")
                logger.warning("Continuing without GPS functionality")
        
        # Initialize gas sensor if enabled
        global gas_sensor
        gas_sensor = None
        if config.GAS_ENABLED:
            try:
                from modules.gas_sensor_module import GasSensor
                logger.info("Initializing gas sensor module...")
                gas_sensor = GasSensor(pin=config.GAS_PIN, active_low=True, logger=logger)
                if gas_sensor.start():
                    logger.info("Gas sensor started successfully")
                else:
                    logger.warning("Failed to start gas sensor")
            except Exception as e:
                logger.error(f"Error initializing gas sensor: {e}")
                logger.warning("Continuing without gas sensor functionality")
        
        # Initialize detection module
        global detection_module
        from modules.detection_module import DetectionModule
        detection_module = DetectionModule(detection_callback=handle_detection)
        logger.info("Detection module initialized")
        
        # Initialize communication module
        global communication_module
        from modules.communication import CommunicationModule
        communication_module = CommunicationModule(gps_module, gas_sensor)
        communication_module.start_heartbeat_sender()
        logger.info("Communication module initialized and heartbeat sender started")
        
        # Initialize camera module
        from modules.camera_module import CameraModule
        camera_module = CameraModule(frame_callback=handle_new_frame)
        camera_module.start()
        logger.info("Camera module initialized and started")
        
        # Initialize and start web server
        from modules.web_server import WebServerModule
        web_server = WebServerModule(
            camera_module, 
            detection_module, 
            communication_module, 
            gps_module, 
            gas_sensor
        )
        logger.info("Web server module initialized")
        
        # Start web server (this will block until terminated)
        web_server.start()
        
    except KeyboardInterrupt:
        logger.info("Application stopped by user")
        cleanup()
    except Exception as e:
        logger.error(f"Application error: {e}")
        cleanup()

def cleanup():
    """Clean up resources before exiting."""
    logger.info("Cleaning up resources...")
    
    # Stop communication module
    try:
        if 'communication_module' in globals():
            communication_module.stop()
    except Exception as e:
        logger.error(f"Error stopping communication module: {e}")
    
    # Stop GPS module
    try:
        if 'gps_module' in globals() and gps_module:
            gps_module.stop()
    except Exception as e:
        logger.error(f"Error stopping GPS module: {e}")
    
    # Stop gas sensor
    try:
        if 'gas_sensor' in globals() and gas_sensor:
            gas_sensor.stop()
    except Exception as e:
        logger.error(f"Error stopping gas sensor: {e}")
    
    logger.info("Cleanup complete")

if __name__ == "__main__":
    main()
