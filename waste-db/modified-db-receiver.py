#!/usr/bin/env python3
# database_receiver_modified.py - Works with your existing database schema
import socket
import threading
import json
import logging
import os
import base64
import cv2
import numpy as np
import pymysql
from datetime import datetime

# Set up logging
log_dir = "logs"
os.makedirs(log_dir, exist_ok=True)
log_file = os.path.join(log_dir, f"db_receiver_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log")

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_file),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger('db-receiver')

# Configuration
HOST = '0.0.0.0'  # Listen on all interfaces
PORT = 5002       # Port to listen on

# Database configuration
DB_HOST = 'localhost'  # MariaDB server hosted on the same Pi
DB_USER = 'waste_user'   # Update if your username is different
DB_PASSWORD = 'password' # Use your actual password
DB_NAME = 'waste_detection'

def save_detection_to_db(data):
    """Save detection data to database"""
    try:
        # Extract data from payload
        device_id = data.get('device_id', 'Unknown')
        ip_address = data.get('ip_address', '0.0.0.0')
        timestamp = data.get('timestamp')
        num_detections = data.get('num_detections', 0)
        gas_value = data.get('gas_value', 0)
        lat = data.get('lat', 0.0)
        lon = data.get('lon', 0.0)
        predictions = data.get('predictions', [])
        
        # Convert timestamp string to datetime
        detection_time = datetime.fromisoformat(timestamp)
        
        # Connect to database
        connection = pymysql.connect(
            host=DB_HOST,
            user=DB_USER,
            password=DB_PASSWORD,
            database=DB_NAME,
            charset='utf8mb4'
        )
        
        # Insert detection data
        with connection.cursor() as cursor:
            # First, update or insert device record using the device_id
            # Check if device exists first
            cursor.execute("SELECT device_id FROM devices WHERE device_id = %s", (device_id,))
            device_exists = cursor.fetchone()
            
            if device_exists:
                # Update the existing device record
                cursor.execute("""
                UPDATE devices 
                SET ip_address = %s, location_lat = %s, location_lon = %s, last_active = NOW()
                WHERE device_id = %s
                """, (ip_address, lat, lon, device_id))
            else:
                # Insert a new device record
                cursor.execute("""
                INSERT INTO devices (device_id, ip_address, location_lat, location_lon, last_active)
                VALUES (%s, %s, %s, %s, NOW())
                """, (device_id, ip_address, lat, lon))
            
            # Insert into detections table
            cursor.execute("""
            INSERT INTO detections (device_id, timestamp, num_detections, gas_value)
            VALUES (%s, %s, %s, %s)
            """, (device_id, detection_time, num_detections, gas_value))
            
            # Get the detection_id of the inserted record
            detection_id = connection.insert_id()
            
            # Insert each prediction into detected_items table
            for pred in predictions:
                cursor.execute("""
                INSERT INTO detected_items (detection_id, class_name, confidence, x_coord, y_coord, width, height)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                """, (
                    detection_id,
                    pred.get('class', 'unknown'),
                    pred.get('confidence', 0.0),
                    pred.get('x', 0.0) * 640,  # Scale to pixel coordinates assuming 640x480 image
                    pred.get('y', 0.0) * 480,
                    pred.get('width', 0.0) * 640,
                    pred.get('height', 0.0) * 480
                ))
            
            # Check for a frame and save it as a keyframe
            if 'frame' in data and data['frame']:
                try:
                    # Decode base64 image
                    img_bytes = base64.b64decode(data['frame'])
                    
                    # Store directly in the database
                    cursor.execute("""
                    INSERT INTO keyframes (detection_id, image_data, image_format)
                    VALUES (%s, %s, %s)
                    """, (detection_id, img_bytes, 'jpg'))
                    
                    logger.info(f"Saved keyframe for detection {detection_id}")
                except Exception as img_error:
                    logger.error(f"Error saving keyframe: {img_error}")
        
        # Commit changes
        connection.commit()
        logger.info(f"Successfully saved detection {detection_id} with {num_detections} items")
        return True
        
    except Exception as e:
        logger.error(f"Error saving to database: {e}")
        return False
    finally:
        if connection:
            connection.close()

def handle_client(client_socket, client_address):
    """Handle incoming client connection"""
    logger.info(f"Connection from {client_address}")
    
    try:
        # Receive data
        data = b""
        while True:
            chunk = client_socket.recv(4096)
            if not chunk:
                break
            data += chunk
        
        # Process received data
        if data:
            try:
                # Parse JSON data
                json_data = json.loads(data.decode('utf-8'))
                logger.info(f"Received data from {client_address}, device: {json_data.get('device_id', 'Unknown')}")
                
                # Save to database
                save_detection_to_db(json_data)
                
            except json.JSONDecodeError as e:
                logger.error(f"Invalid JSON received from {client_address}: {e}")
        else:
            logger.warning(f"Empty data received from {client_address}")
    
    except Exception as e:
        logger.error(f"Error handling client {client_address}: {e}")
    
    finally:
        # Close the client socket
        client_socket.close()
        logger.info(f"Connection closed from {client_address}")

def start_server():
    """Start the socket server to listen for incoming connections"""
    try:
        # Create server socket
        server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        
        # Bind socket to address and port
        server_socket.bind((HOST, PORT))
        
        # Listen for connections
        server_socket.listen(5)
        logger.info(f"Server listening on {HOST}:{PORT}")
        
        while True:
            # Accept incoming connection
            client_socket, client_address = server_socket.accept()
            
            # Handle client in a new thread
            client_thread = threading.Thread(
                target=handle_client,
                args=(client_socket, client_address),
                daemon=True
            )
            client_thread.start()
            
    except KeyboardInterrupt:
        logger.info("Server stopping due to keyboard interrupt")
    except Exception as e:
        logger.error(f"Server error: {e}")
    finally:
        if 'server_socket' in locals() and server_socket:
            server_socket.close()
            logger.info("Server socket closed")

if __name__ == "__main__":
    # Print banner
    print("=" * 50)
    print("WASTE DETECTION DATABASE RECEIVER")
    print("=" * 50)
    print(f"Host: {HOST}")
    print(f"Port: {PORT}")
    print(f"Database: {DB_NAME} @ {DB_HOST}")
    print(f"Log File: {log_file}")
    print("=" * 50)
    
    # Start server
    start_server()
