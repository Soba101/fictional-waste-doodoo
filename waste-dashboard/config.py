"""
Configuration settings for the dashboard.
"""
import os
from datetime import datetime

# Logging configuration
LOG_DIR = "logs"
os.makedirs(LOG_DIR, exist_ok=True)
LOG_FILE = os.path.join(LOG_DIR, f"dashboard_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log")

# MQTT Configuration
MQTT_BROKER = "192.168.18.113"  # Pi400 IP address
MQTT_PORT = 1883
MQTT_KEEPALIVE = 60
MQTT_QOS = 1
MQTT_TOPIC_PREFIX = "devices"  # Match edge device configuration

# Database configuration
DATABASE_HOST = "192.168.18.113"  # Pi400 IP address
DATABASE_PORT = 3306  # Standard MariaDB port
DATABASE_USER = "waste_user"
DATABASE_PASSWORD = "password"
DATABASE_NAME = "waste_detection"
DATABASE_POOL_SIZE = 5
DATABASE_MAX_OVERFLOW = 10
DATABASE_POOL_TIMEOUT = 30  # Standard timeout
DATABASE_POOL_RECYCLE = 1800

# Device configuration
HEARTBEAT_TIMEOUT = 30  # seconds before considering a device disconnected

# Dashboard customization
DASHBOARD_TITLE = "Waste Detection Dashboard"
DASHBOARD_ICON = "🗑️"
MAP_DEFAULT_CENTER = [1.3521, 103.8198]  # Singapore
MAP_DEFAULT_ZOOM = 13

# Data retention
MAX_CONNECTION_LOG_ENTRIES = 100
METRICS_UPDATE_INTERVAL = 10  # seconds

# Cache Configuration
CACHE_TTL_METRICS = 60  # Cache time for metrics calculations (seconds)
CACHE_TTL_DETECTION_DATA = 300  # Cache time for detection data (seconds)
CACHE_TTL_MAPS = 60  # Cache time for maps (seconds)
CACHE_TTL_CHARTS = 300  # Cache time for charts (seconds)
CACHE_TTL_DB_ENGINE = 3600  # Cache time for database engine (seconds)

# Memory Management
MAX_HISTORY_ITEMS = 1000  # Maximum number of detection history items to keep
MAX_LOG_ENTRIES = 1000  # Maximum number of connection log entries to keep
CLEANUP_INTERVAL = 300  # Interval for cleaning up old data (seconds)
DEVICE_TIMEOUT = 300  # Time after which a device is considered inactive (seconds)

# Dashboard Configuration
DASHBOARD_REFRESH_RATE = 5  # Dashboard refresh rate in seconds
CHART_MAX_POINTS = 100       # Maximum points to show in charts
DEVICE_STATUS_REFRESH = 5    # Device status refresh rate in seconds

# Logging Configuration
LOG_LEVEL = "INFO"
MAX_LOG_FILES = 5
MAX_LOG_SIZE = 10 * 1024 * 1024  # 10MB 