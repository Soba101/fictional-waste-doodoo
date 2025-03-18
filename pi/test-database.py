#!/usr/bin/env python3
# test_database_logging.py - Test logging detections to the existing database
import socket
import json
import time
import base64
import cv2
import numpy as np
from datetime import datetime
import argparse

# Configuration
DATABASE_IP = "192.168.18.113"  # Change to your MariaDB Pi's IP
DATABASE_PORT = 5002
DEVICE_ID = "TestDevice"

def create_test_image():
    """Create a test image with timestamp and pattern"""
    img = np.zeros((480, 640, 3), dtype=np.uint8)
    
    # Add a colored rectangle
    cv2.rectangle(img, (100, 100), (540, 380), (0, 255, 0), -1)
    
    # Add timestamp
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cv2.putText(img, f"Test Image", (150, 200), 
                cv2.FONT_HERSHEY_SIMPLEX, 1.5, (255, 255, 255), 2)
    cv2.putText(img, timestamp, (150, 250), 
                cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)
    cv2.putText(img, f"From: {DEVICE_ID}", (150, 300), 
                cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)
    
    return img

def create_waste_detections(num_detections=2):
    """Create sample waste detection predictions"""
    waste_classes = ['plastic', 'paper', 'glass', 'metal', 'cardboard', 'organic']
    predictions = []
    
    for i in range(num_detections):
        # Generate random detection in normalized coordinates
        x = np.random.uniform(0.2, 0.8)
        y = np.random.uniform(0.2, 0.8)
        width = np.random.uniform(0.1, 0.3)
        height = np.random.uniform(0.1, 0.3)
        confidence = np.random.uniform(0.7, 0.95)
        waste_class = waste_classes[np.random.randint(0, len(waste_classes))]
        
        predictions.append({
            'class': waste_class,
            'confidence': float(confidence),
            'x': float(x),
            'y': float(y),
            'width': float(width),
            'height': float(height)
        })
    
    return predictions

def send_test_detection(include_image=True, num_detections=None):
    """Send test detection data to the database server"""
    try:
        # Create a test image
        img = create_test_image()
        
        # Create sample predictions
        if num_detections is None:
            num_detections = np.random.randint(1, 5)  # Random number of detections
        
        predictions = create_waste_detections(num_detections)
        
        # Draw detections on the image
        for pred in predictions:
            x = int(pred['x'] * 640)
            y = int(pred['y'] * 480)
            w = int(pred['width'] * 640) 
            h = int(pred['height'] * 480)
            
            cv2.rectangle(img, (x-w//2, y-h//2), (x+w//2, y+h//2), (0, 0, 255), 2)
            cv2.putText(img, f"{pred['class']} {pred['confidence']:.2f}", 
                      (x-w//2, y-h//2-5), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 1)
        
        # Create data payload
        data = {
            'device_id': DEVICE_ID,
            'ip_address': socket.gethostbyname(socket.gethostname()),
            'timestamp': datetime.now().isoformat(),
            'predictions': predictions,
            'num_detections': len(predictions),
            'lat': 1.3521,
            'lon': 103.8198,
            'gas_value': np.random.randint(0, 100)  # Random gas value
        }
        
        # Add frame to payload if requested
        if include_image:
            # Convert to JPEG format
            _, buffer = cv2.imencode('.jpg', img, [cv2.IMWRITE_JPEG_QUALITY, 85])
            
            # Encode as base64 string
            frame_base64 = base64.b64encode(buffer).decode('utf-8')
            
            # Add to data payload
            data['frame'] = frame_base64
        
        print(f"Connecting to database at {DATABASE_IP}:{DATABASE_PORT}...")
        
        # Send the data
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(5)
            sock.connect((DATABASE_IP, DATABASE_PORT))
            
            print(f"Connected! Sending detection with {len(predictions)} items...")
            data_json = json.dumps(data)
            sock.sendall(data_json.encode('utf-8'))
            
            print(f"Successfully sent test detection!")
            
            if include_image:
                print("Image included in detection data")
            else:
                print("No image included")
                
            return True
            
    except Exception as e:
        print(f"Error sending test detection: {e}")
        return False

if __name__ == "__main__":
    # Parse command line arguments
    parser = argparse.ArgumentParser(description="Test database logging for waste detection")
    parser.add_argument("-n", "--num", type=int, help="Number of detections to send")
    parser.add_argument("--no-image", action="store_true", help="Don't include an image")
    args = parser.parse_args()
    
    # Print banner
    print("=" * 50)
    print("WASTE DETECTION DATABASE TEST")
    print("=" * 50)
    print(f"Target: {DATABASE_IP}:{DATABASE_PORT}")
    print(f"Device ID: {DEVICE_ID}")
    
    num_detections = args.num if args.num is not None else None
    include_image = not args.no_image
    
    # Display test settings
    if num_detections is not None:
        print(f"Sending exactly {num_detections} detections")
    else:
        print("Sending random number of detections (1-4)")
        
    if include_image:
        print("Including keyframe image")
    else:
        print("No keyframe image included")
    
    # Try to send test data
    success = send_test_detection(include_image, num_detections)
    
    if success:
        print("\nSUCCESS! The detection data was sent to the database.")
        print("Check your database to verify the data was stored correctly.")
    else:
        print("\nFAILED! Could not connect to the database server.")
        print("Make sure:")
        print("1. The database_receiver.py script is running on the database Pi")
        print("2. The IP address and port configurations are correct")
        print("3. There are no firewall issues blocking the connection")
    
    print("=" * 50)
