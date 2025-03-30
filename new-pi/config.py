"""
Global configuration settings for the waste detection system.
"""
import os
import logging
from datetime import datetime
from pathlib import Path

# Feature flags
GPS_ENABLED = True    # Set to False to disable GPS
GAS_ENABLED = True    # Set to False to disable gas sensor

# Hardware configuration
GPS_PORT = '/dev/ttyAMA0'  # Port for GPS module
GAS_PIN = 27               # GPIO pin for MQ-2 DO (Digital Output)

# Network configuration
DASHBOARD_IP = os.getenv('DASHBOARD_IP', "192.168.18.107")  # Dashboard server IP (Mac)
DASHBOARD_PORT = int(os.getenv('DASHBOARD_PORT', "5001"))    # Dashboard server port
MQTT_BROKER = os.getenv('MQTT_BROKER', "192.168.18.113")    # MQTT broker IP (Pi400)
MQTT_PORT = int(os.getenv('MQTT_PORT', "1883"))             # MQTT broker port
MQTT_KEEPALIVE = 60      # Keepalive interval in seconds
MQTT_QOS = 1            # Default Quality of Service level
MQTT_TOPIC_PREFIX = "devices"  # Topic prefix for all device messages

# Add MQTT connection timeout
MQTT_CONNECT_TIMEOUT = 10  # seconds to wait for connection
MQTT_RETRY_DELAY = 5      # seconds between retry attempts
MQTT_MAX_RETRIES = 3      # maximum number of connection retries

# Add network verification settings
NETWORK_CHECK_INTERVAL = 30  # seconds between network checks
NETWORK_TIMEOUT = 5         # seconds to wait for network response

# Device identification
DEVICE_ID = os.getenv('DEVICE_ID', "RaspberryPi5")  # Unique device identifier
VIDEO_PORT = int(os.getenv('VIDEO_PORT', "8000"))   # Local video streaming port

# Default location (Singapore) when GPS is unavailable
DEFAULT_LAT = float(os.getenv('DEFAULT_LAT', "1.3521"))
DEFAULT_LON = float(os.getenv('DEFAULT_LON', "103.8198"))

# Logging configuration
LOG_DIR = "logs"
try:
    os.makedirs(LOG_DIR, exist_ok=True)
    LOG_FILE = os.path.join(LOG_DIR, f"pi_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log")
except Exception as e:
    logging.error(f"Failed to create log directory: {e}")
    LOG_FILE = f"pi_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"

# Camera configuration
CAMERA_WIDTH = int(os.getenv('CAMERA_WIDTH', "640"))
CAMERA_HEIGHT = int(os.getenv('CAMERA_HEIGHT', "480"))
CAMERA_FPS = int(os.getenv('CAMERA_FPS', "30"))  # FPS for real-time detection

# Temporary directory for camera captures
TEMP_DIR = "/tmp/pi_captures"
try:
    os.makedirs(TEMP_DIR, exist_ok=True)
except Exception as e:
    logging.error(f"Failed to create temp directory: {e}")
    TEMP_DIR = "/tmp"

# Heartbeat configuration
HEARTBEAT_INTERVAL = 15  # Interval between heartbeat messages in seconds

# Model configuration
MODEL_PATH = os.path.join(Path(__file__).parent, "models", "best_integer_quant.tflite")
if not os.path.exists(MODEL_PATH):
    logging.error(f"Model file not found at {MODEL_PATH}")
    raise FileNotFoundError(f"Model file not found at {MODEL_PATH}")

# Validate configuration
def validate_config():
    """Validate configuration settings."""
    if not os.path.exists(GPS_PORT) and GPS_ENABLED:
        logging.warning(f"GPS port {GPS_PORT} not found but GPS is enabled")
    
    if not os.path.exists(TEMP_DIR):
        logging.error(f"Temporary directory {TEMP_DIR} does not exist")
        return False
    
    if not os.path.exists(LOG_DIR):
        logging.error(f"Log directory {LOG_DIR} does not exist")
        return False
    
    return True

# Validate configuration on import
validate_config()
