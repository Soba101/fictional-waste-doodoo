#!/usr/bin/env python3
"""
Test script to simulate a Pi device sending MQTT messages to the database server.
"""
import paho.mqtt.client as mqtt
import json
import time
from datetime import datetime
import random
import logging
import requests
import config

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('mqtt-test')

# Simulated device ID
DEVICE_ID = "test_device_001"
API_BASE_URL = f"http://localhost:{config.DATABASE_PORT}"

def verify_database_connection():
    """Verify if the database server is running and accessible."""
    try:
        response = requests.get(f"{API_BASE_URL}/api/detections")
        if response.status_code == 200:
            logger.info("Database server is running and accessible")
            return True
        else:
            logger.error(f"Database server returned status code: {response.status_code}")
            return False
    except requests.exceptions.ConnectionError:
        logger.error("Could not connect to database server. Is it running?")
        return False

def on_connect(client, userdata, flags, rc):
    """Callback when connected to MQTT broker."""
    if rc == 0:
        logger.info("Connected to MQTT broker")
    else:
        logger.error(f"Failed to connect to MQTT broker with code: {rc}")

def on_publish(client, userdata, mid):
    """Callback when message is published."""
    logger.info(f"Message {mid} published")

def generate_test_data():
    """Generate simulated detection data."""
    return {
        "timestamp": datetime.now().isoformat(),
        "num_detections": random.randint(0, 5),
        "predictions": [
            {
                "class": random.choice(["plastic", "metal", "paper", "glass"]),
                "confidence": round(random.uniform(0.7, 0.99), 2),
                "bbox": [
                    round(random.uniform(0, 1), 2),
                    round(random.uniform(0, 1), 2),
                    round(random.uniform(0, 1), 2),
                    round(random.uniform(0, 1), 2)
                ]
            }
            for _ in range(random.randint(1, 3))
        ],
        "lat": round(random.uniform(51.5074, 51.5075), 6),
        "lon": round(random.uniform(-0.1278, -0.1277), 6),
        "has_gps_fix": True,
        "satellites": random.randint(4, 8),
        "altitude": round(random.uniform(0, 100), 2),
        "gas_value": round(random.uniform(0, 1000), 2),
        "gas_detected": random.choice([True, False])
    }

def verify_data_storage():
    """Verify that the test data was stored in the database."""
    try:
        # Get detections for our test device
        response = requests.get(f"{API_BASE_URL}/api/detections/{DEVICE_ID}")
        if response.status_code == 200:
            data = response.json()
            detections = data.get('detections', [])
            
            # Check if we have recent detections
            recent_detections = [
                d for d in detections 
                if (datetime.now() - datetime.fromisoformat(d['timestamp'])).total_seconds() < 60
            ]
            
            if recent_detections:
                logger.info(f"Found {len(recent_detections)} recent detections in database")
                return True
            else:
                logger.warning("No recent detections found in database")
                return False
        else:
            logger.error(f"Failed to retrieve detections: {response.status_code}")
            return False
    except Exception as e:
        logger.error(f"Error verifying data storage: {e}")
        return False

def main():
    """Main test function."""
    try:
        # First verify database server is running
        if not verify_database_connection():
            logger.error("Please start the database server first using 'python start_db.py'")
            return

        # Create MQTT client
        client = mqtt.Client(client_id=f"test_device_{DEVICE_ID}")
        client.on_connect = on_connect
        client.on_publish = on_publish

        # Connect to MQTT broker
        logger.info(f"Connecting to MQTT broker at {config.MQTT_BROKER}:{config.MQTT_PORT}")
        client.connect(config.MQTT_BROKER, config.MQTT_PORT, config.MQTT_KEEPALIVE)
        client.loop_start()

        # Wait for connection
        time.sleep(2)

        # Send test messages
        for i in range(5):  # Send 5 test messages
            # Generate test data
            data = generate_test_data()
            
            # Create topic
            topic = f"{config.MQTT_TOPIC_PREFIX}/{DEVICE_ID}/detections"
            
            # Publish message
            logger.info(f"Sending test message {i+1} to topic {topic}")
            client.publish(topic, json.dumps(data), qos=config.MQTT_QOS)
            
            # Wait between messages
            time.sleep(2)

        # Stop the loop and disconnect
        client.loop_stop()
        client.disconnect()
        
        # Wait a moment for messages to be processed
        time.sleep(2)
        
        # Verify data was stored
        if verify_data_storage():
            logger.info("Test completed successfully - data was stored in database")
        else:
            logger.warning("Test completed but data storage verification failed")

    except Exception as e:
        logger.error(f"Test failed: {e}")
        raise

if __name__ == "__main__":
    main() 