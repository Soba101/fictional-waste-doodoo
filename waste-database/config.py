"""
Configuration settings for the database server.
"""
import os
from datetime import datetime

# Server configuration
DATABASE_PORT = 5002
LOG_DIR = "logs"
os.makedirs(LOG_DIR, exist_ok=True)
LOG_FILE = os.path.join(LOG_DIR, f"database_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log")

# Database configuration
DATABASE_HOST = "localhost"
DATABASE_USER = "waste_user"
DATABASE_PASSWORD = "password"
DATABASE_NAME = "waste_detection"
DATABASE_URL = f"mariadb+pymysql://{DATABASE_USER}:{DATABASE_PASSWORD}@{DATABASE_HOST}/{DATABASE_NAME}"

# Database Pool Settings
DATABASE_POOL_SIZE = 5
DATABASE_MAX_OVERFLOW = 10
DATABASE_POOL_TIMEOUT = 30
DATABASE_POOL_RECYCLE = 1800

# MQTT Configuration
MQTT_BROKER = "0.0.0.0"  # Listen on all interfaces since this is the broker host
MQTT_PORT = 1883         # MQTT broker port
MQTT_KEEPALIVE = 60      # Keepalive interval in seconds
MQTT_QOS = 1            # Default Quality of Service level
MQTT_TOPIC_PREFIX = "devices"  # Topic prefix for all device messages 