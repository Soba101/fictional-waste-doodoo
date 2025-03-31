"""
Global configuration settings for the waste detection system.
"""
import os
from datetime import datetime

# Feature flags
GPS_ENABLED = True    # Set to False to disable GPS
GAS_ENABLED = True    # Set to False to disable gas sensor

# Hardware configuration
GPS_PORT = '/dev/ttyAMA0'  # Port for GPS module
GAS_PIN = 23               # GPIO pin for MQ-2 DO (Digital Output)

# Network configuration
DASHBOARD_IP = "192.168.18.107"  # Dashboard server IP
DASHBOARD_PORT = 5001             # Dashboard server port
DATABASE_IP = "192.168.18.113"    # Database server IP
DATABASE_PORT = 5002              # Database server port
DEVICE_ID = "RaspberryPi5"        # Unique device identifier
VIDEO_PORT = 8000                 # Local video streaming port

# Default location (Singapore) when GPS is unavailable
DEFAULT_LAT = 1.3521
DEFAULT_LON = 103.8198

# Logging configuration
LOG_DIR = "logs"
os.makedirs(LOG_DIR, exist_ok=True)
LOG_FILE = os.path.join(LOG_DIR, f"pi_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log")

# Camera configuration
CAMERA_WIDTH = 640
CAMERA_HEIGHT = 480
CAMERA_FPS = 15  # Frames per second for waste detection

# Temporary directory for camera captures
TEMP_DIR = "/tmp/pi_captures"
os.makedirs(TEMP_DIR, exist_ok=True)

# Heartbeat configuration
HEARTBEAT_INTERVAL = 15  # seconds between heartbeats
