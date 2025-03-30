#!/usr/bin/env python3
"""
Startup script for the database server on Pi400.
Handles MQTT broker initialization and database server startup.
"""
import subprocess
import time
import logging
import os
import sys
from pathlib import Path

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('db-startup')

def check_mosquitto():
    """Check if Mosquitto service is running and start it if needed."""
    try:
        result = subprocess.run(['systemctl', 'is-active', 'mosquitto'], 
                              capture_output=True, text=True)
        if result.stdout.strip() != 'active':
            logger.info("Starting Mosquitto MQTT broker...")
            subprocess.run(['sudo', 'systemctl', 'start', 'mosquitto'], check=True)
            logger.info("Mosquitto started successfully")
    except subprocess.CalledProcessError as e:
        logger.error(f"Failed to start Mosquitto: {e}")
        sys.exit(1)

def wait_for_mosquitto():
    """Wait for Mosquitto to be ready."""
    logger.info("Waiting for MQTT broker to be ready...")
    time.sleep(5)  # Give Mosquitto time to start

def start_database_server():
    """Start the database server."""
    try:
        logger.info("Starting database server...")
        # Get the directory of this script
        script_dir = Path(__file__).parent
        # Change to the script directory
        os.chdir(script_dir)
        # Start the server
        subprocess.run([sys.executable, 'server.py'], check=True)
    except subprocess.CalledProcessError as e:
        logger.error(f"Database server failed to start: {e}")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        sys.exit(1)

def main():
    """Main startup sequence."""
    try:
        # Check and start Mosquitto if needed
        check_mosquitto()
        
        # Wait for Mosquitto to be ready
        wait_for_mosquitto()
        
        # Start the database server
        start_database_server()
        
    except KeyboardInterrupt:
        logger.info("Shutting down...")
        sys.exit(0)
    except Exception as e:
        logger.error(f"Startup failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main() 