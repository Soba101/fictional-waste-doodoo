# pi-capture-detect.py using pi camera 2.0
# This script captures images from the Raspberry Pi camera module and performs waste detection using simple color thresholding.
from flask import Flask, Response, request
import cv2
import threading
import time
import socket
import json
import os
import logging
import subprocess
import numpy as np
from datetime import datetime
import base64
from gps_module import GPSModule

GPS_ENABLED = True  # Set to False to disable GPS
GPS_PORT = '/dev/ttyAMA0'  # Port that worked in testing

# Set up logging
log_dir = "logs"
os.makedirs(log_dir, exist_ok=True)
log_file = os.path.join(log_dir, f"pi_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log")

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_file),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger('pi-waste-detection')

# Configuration
DASHBOARD_IP = "192.168.18.107"  # Change to your dashboard IP
DASHBOARD_PORT = 5001
DATABASE_IP = "192.168.18.113"  # Change to your database IP
DATABASE_PORT = 5002
DEVICE_ID = "RaspberryPi5"
VIDEO_PORT = 8000

# Global variables
latest_frame = None
latest_predictions = []
frame_lock = threading.Lock()
prediction_lock = threading.Lock()

# Global tracking variables
start_time = time.time()
connection_attempts = 0
successful_connections = 0

# Initialize Flask app
app = Flask(__name__)

def detect_waste_simple(frame):
    """Simple waste detection based on color thresholding"""
    try:
        # Convert to HSV for better color detection
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        
        # Define ranges for different colors that might indicate waste items
        # Blue items (like plastic bottles)
        lower_blue = np.array([90, 50, 50])
        upper_blue = np.array([130, 255, 255])
        blue_mask = cv2.inRange(hsv, lower_blue, upper_blue)
        
        # Green items (like glass bottles)
        lower_green = np.array([40, 50, 50])
        upper_green = np.array([80, 255, 255])
        green_mask = cv2.inRange(hsv, lower_green, upper_green)
        
        # Brown/yellow items (like cardboard/paper)
        lower_brown = np.array([20, 50, 50])
        upper_brown = np.array([40, 255, 255])
        brown_mask = cv2.inRange(hsv, lower_brown, upper_brown)
        
        # Combined mask
        combined_mask = blue_mask | green_mask | brown_mask
        
        # Find contours
        contours, _ = cv2.findContours(combined_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        # Process contours
        predictions = []
        for contour in contours:
            area = cv2.contourArea(contour)
            
            # Filter by size
            if area > 1000:  # Minimum area to consider
                x, y, w, h = cv2.boundingRect(contour)
                
                # Calculate center
                center_x = x + w/2
                center_y = y + h/2
                
                # Get normalized coordinates
                img_height, img_width = frame.shape[:2]
                x_rel = center_x / img_width
                y_rel = center_y / img_height
                width_rel = w / img_width
                height_rel = h / img_height
                
                # Determine waste class based on color
                roi = frame[y:y+h, x:x+w]
                hsv_roi = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
                blue_count = cv2.countNonZero(cv2.inRange(hsv_roi, lower_blue, upper_blue))
                green_count = cv2.countNonZero(cv2.inRange(hsv_roi, lower_green, upper_green))
                brown_count = cv2.countNonZero(cv2.inRange(hsv_roi, lower_brown, upper_brown))
                
                # Determine class based on dominant color
                if blue_count > green_count and blue_count > brown_count:
                    waste_class = "plastic"
                elif green_count > blue_count and green_count > brown_count:
                    waste_class = "glass"
                else:
                    waste_class = "paper"
                
                # Create prediction object
                prediction = {
                    'class': waste_class,
                    'confidence': min(0.5 + area/50000, 0.95),  # Simple confidence based on size
                    'x': x_rel,
                    'y': y_rel,
                    'width': width_rel,
                    'height': height_rel
                }
                predictions.append(prediction)
        
        return predictions
    except Exception as e:
        logger.error(f"Error in simple waste detection: {e}")
        return []

def send_heartbeat():
    """Send regular heartbeats to ensure dashboard shows us as connected"""
    global connection_attempts, successful_connections
    
    while True:
        try:
            # Get own IP address
            own_ip = "Unknown"
            try:
                s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                s.connect(("8.8.8.8", 80))
                own_ip = s.getsockname()[0]
                s.close()
            except:
                pass
            
            # Get GPS position if available
            if GPS_ENABLED and 'gps_module' in globals() and gps_module:
                position = gps_module.get_position()
                lat = position['latitude']
                lon = position['longitude']
                has_fix = position['has_fix']
                satellites = position['satellites']
                altitude = position['altitude']
            else:
                # Default values if GPS not available
                lat = 1.3521  # Default to Singapore
                lon = 103.8198
                has_fix = False
                satellites = 0
                altitude = 0
            
            # Prepare heartbeat data
            heartbeat_data = {
                'device_id': DEVICE_ID,
                'timestamp': datetime.now().isoformat(),
                'predictions': [],  # Empty predictions for heartbeat
                'num_detections': 0,
                'lat': lat,
                'lon': lon,
                'has_gps_fix': has_fix,
                'satellites': satellites,
                'altitude': altitude,
                'heartbeat': True,
                'sender_ip': own_ip
            }
            
            # Send the heartbeat
            connection_attempts += 1
            
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                sock.settimeout(2)
                sock.connect((DASHBOARD_IP, DASHBOARD_PORT))
                data_json = json.dumps(heartbeat_data)
                sock.sendall(data_json.encode('utf-8'))
            
            successful_connections += 1
            logger.info("Sent heartbeat to dashboard")
            
        except Exception as e:
            logger.error(f"Error in heartbeat sender: {e}")
            
        # Wait before sending next heartbeat
        time.sleep(15)  # Send heartbeat every 15 seconds

def send_detection_to_dashboard(predictions):
    """Send detection data to dashboard with GPS data if available"""
    global connection_attempts, successful_connections
    
    try:
        # Get GPS position if available
        if GPS_ENABLED and 'gps_module' in globals() and gps_module:
            position = gps_module.get_position()
            lat = position['latitude']
            lon = position['longitude']
            has_fix = position['has_fix']
            satellites = position['satellites']
            altitude = position['altitude']
        else:
            # Default values if GPS not available
            lat = 1.3521  # Default to Singapore
            lon = 103.8198
            has_fix = False
            satellites = 0
            altitude = 0
        
        # Create data payload with GPS data
        data = {
            'device_id': DEVICE_ID,
            'timestamp': datetime.now().isoformat(),
            'predictions': predictions,
            'num_detections': len(predictions),
            'lat': lat,
            'lon': lon,
            'has_gps_fix': has_fix,
            'satellites': satellites,
            'altitude': altitude,
            'gas_value': 0  # Placeholder for gas sensor value
        }
        
        # Log detection information
        logger.info(f"Sending {len(predictions)} detections to dashboard with GPS: {lat}, {lon}")
        
        # Send the data
        connection_attempts += 1
        
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(2)
            sock.connect((DASHBOARD_IP, DASHBOARD_PORT))
            data_json = json.dumps(data)
            sock.sendall(data_json.encode('utf-8'))
        
        successful_connections += 1
        logger.info(f"Successfully sent detections to dashboard")
        
    except Exception as e:
        logger.error(f"Failed to send detections: {str(e)}")

def send_detection_to_database(predictions, frame=None):
    """Send detection data and keyframe to database server with GPS data"""
    try:
        # Get device IP address
        local_ip = None
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            local_ip = s.getsockname()[0]
            s.close()
        except:
            logger.warning("Could not determine local IP address")
        
        # Get GPS position if available
        if GPS_ENABLED and 'gps_module' in globals() and gps_module:
            position = gps_module.get_position()
            lat = position['latitude']
            lon = position['longitude']
            has_fix = position['has_fix']
            satellites = position['satellites']
            altitude = position['altitude']
        else:
            # Default values if GPS not available
            lat = 1.3521  # Default to Singapore
            lon = 103.8198
            has_fix = False
            satellites = 0
            altitude = 0
        
        # Create data payload
        data = {
            'device_id': DEVICE_ID,
            'ip_address': local_ip,
            'timestamp': datetime.now().isoformat(),
            'predictions': predictions,
            'num_detections': len(predictions),
            'lat': lat,
            'lon': lon, 
            'has_gps_fix': has_fix,
            'satellites': satellites,
            'altitude': altitude,
            'gas_value': 0  # Placeholder for gas sensor value
        }
        
        # Add frame to payload if provided
        if frame is not None:
            # Resize frame to reduce size (adjust dimensions as needed)
            resized_frame = cv2.resize(frame, (640, 480))
            
            # Convert to JPEG format (better compression)
            _, buffer = cv2.imencode('.jpg', resized_frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
            
            # Encode as base64 string
            frame_base64 = base64.b64encode(buffer).decode('utf-8')
            
            # Add to data payload
            data['frame'] = frame_base64
        
        # Log sending information
        logger.info(f"Sending {len(predictions)} detections to database server with GPS: {lat}, {lon}")
        
        # Send the data
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(3)
            sock.connect((DATABASE_IP, DATABASE_PORT))
            data_json = json.dumps(data)
            sock.sendall(data_json.encode('utf-8'))
        
        logger.info(f"Successfully sent detections to database server")
        
    except Exception as e:
        logger.error(f"Failed to send detections to database: {str(e)}")


# Web server routes
@app.route('/video_feed')
def video_feed():
    """Route for video streaming"""
    return Response(generate_frames(),
                    mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/')
def index():
    """Simple index page"""
    # Get current detection count for display
    with prediction_lock:
        detection_count = len(latest_predictions)
    
    return """
    <html>
    <head>
        <title>Waste Detection Pi</title>
        <style>
            body { 
                background-color: #f0f0f0; 
                font-family: Arial, sans-serif;
                text-align: center;
                margin: 20px;
            }
            h1 { color: #006699; }
            .video-container {
                max-width: 640px;
                margin: 0 auto;
                border: 2px solid #333;
                overflow: hidden;
            }
            img { 
                width: 100%;
                height: auto;
            }
            .status {
                margin-top: 20px;
                padding: 10px;
                background-color: #ddd;
                border-radius: 5px;
            }
        </style>
        <meta http-equiv="refresh" content="10">
    </head>
    <body>
        <h1>Waste Detection Dashboard</h1>
        <div class="video-container">
            <img src="/video_feed">
        </div>
        <div class="status">
            <p>Connection Status: Connected to dashboard at """ + DASHBOARD_IP + ":" + str(DASHBOARD_PORT) + """</p>
            <p>Video server running at port """ + str(VIDEO_PORT) + """</p>
            <p>Current Detections: """ + str(detection_count) + """</p>
            <p>Successful Connections: """ + str(successful_connections) + """</p>
            <p>Failed Connections: """ + str(connection_attempts - successful_connections) + """</p>
            <p>Camera: Raspberry Pi Camera Module</p>
            <p>Detection Method: Simple Color Detection</p>
        </div>
    </body>
    </html>
    """

@app.route('/status')
def status():
    """Status endpoint that EXACTLY matches what the dashboard expects"""
    # Get the requesting IP
    client_ip = request.remote_addr
    logger.info(f"Status request from: {client_ip}")
    
    # Get current detection count
    with prediction_lock:
        current_detections = len(latest_predictions)
    
    # Status data for dashboard
    status_data = {
        "device_id": DEVICE_ID,
        "timestamp": datetime.now().isoformat(),
        "uptime": time.time() - start_time,
        "connection": {
            "success_count": successful_connections,
            "failure_count": connection_attempts - successful_connections,
            "last_status": "Active",
            "last_attempt": datetime.now().isoformat()
        },
        "coordinates": {
            "lat": 1.3521,
            "lon": 103.8198
        },
        "network_interfaces": get_network_interfaces()
    }
    
    return json.dumps(status_data)

def get_network_interfaces():
    """Get all network interfaces for the device"""
    interfaces = {}
    try:
        # Try to get hostname and primary IP
        hostname = socket.gethostname()
        primary_ip = socket.gethostbyname(hostname)
        interfaces['primary'] = primary_ip
        
        # Try alternative method
        import subprocess
        cmd = "hostname -I"
        output = subprocess.check_output(cmd.split()).decode('utf-8').strip()
        for ip in output.split():
            if ip not in interfaces:
                interfaces[ip] = ip
    except Exception as e:
        logger.error(f"Error getting network interfaces: {e}")
        # Return at least one interface so we don't return an empty list
        interfaces = {"192.168.18.113": "192.168.18.113"}  # Fallback to known IP
    
    return interfaces

def generate_frames():
    """Generate video frames for streaming"""
    global latest_frame
    while True:
        with frame_lock:
            if latest_frame is not None:
                # Encode frame to JPEG
                _, buffer = cv2.imencode('.jpg', latest_frame)
                frame_bytes = buffer.tobytes()
                
                # Yield the frame in MJPEG format
                yield (b'--frame\r\n'
                       b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
            else:
                # Generate a blank frame with text
                blank_frame = np.ones((480, 640, 3), dtype=np.uint8) * 255
                cv2.putText(blank_frame, "Camera initializing...", (50, 240), 
                          cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)
                _, buffer = cv2.imencode('.jpg', blank_frame)
                frame_bytes = buffer.tobytes()
                
                yield (b'--frame\r\n'
                       b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
        time.sleep(0.033)  # ~30 FPS

def process_predictions(frame, predictions):
    """Process and visualize predictions on frame"""
    global latest_predictions

    processed_frame = frame.copy()
    
    # Add timestamp
    timestamp = datetime.now().strftime("%H:%M:%S")
    cv2.putText(processed_frame, timestamp, (10, 30), 
              cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
    
    # Add device label
    cv2.putText(processed_frame, "WASTE DETECTION PI", (10, 70), 
              cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 0, 0), 2)
    
    # Draw predictions
    for pred in predictions:
        # Extract coordinates
        x_rel = pred['x']
        y_rel = pred['y']
        width_rel = pred['width']
        height_rel = pred['height']
        
        # Convert to absolute coordinates
        img_height, img_width = processed_frame.shape[:2]
        x = int(x_rel * img_width)
        y = int(y_rel * img_height)
        w = int(width_rel * img_width)
        h = int(height_rel * img_height)
        
        # Draw bounding box
        cv2.rectangle(processed_frame, (x - w//2, y - h//2), (x + w//2, y + h//2), (0, 255, 0), 2)
        
        # Add label
        class_name = pred['class']
        confidence = pred['confidence']
        label = f"{class_name} {confidence:.2f}"
        cv2.putText(processed_frame, label, (x - w//2, y - h//2 - 10), 
                  cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
    
    # Update global predictions
    with prediction_lock:
        latest_predictions = predictions
    
    # If there are predictions, send them to dashboard/database
    if predictions:
        send_detection_to_dashboard(predictions)
        send_detection_to_database(predictions, processed_frame)
    
    return processed_frame

def dummy_pattern_generator():
    """Generate a moving test pattern when no camera is available"""
    while True:
        # Create a checkerboard pattern
        pattern = np.zeros((480, 640, 3), dtype=np.uint8)
        square_size = 40
        now = datetime.now()
        
        # Make pattern change based on current time
        offset = now.second % square_size
        
        # Draw pattern
        for i in range(0, 640+square_size, square_size):
            for j in range(0, 480+square_size, square_size):
                if ((i+offset)//square_size + (j+offset)//square_size) % 2 == 0:
                    x1 = max(0, i-offset)
                    y1 = max(0, j-offset)
                    x2 = min(640, i+square_size-offset)
                    y2 = min(480, j+square_size-offset)
                    pattern[y1:y2, x1:x2] = [0, 255, 0]  # Green color
        
        # Add text with timestamp
        timestamp = now.strftime("%H:%M:%S")
        cv2.putText(pattern, "TEST PATTERN - NO CAMERA", (50, 50), 
                  cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)
        cv2.putText(pattern, timestamp, (50, 100), 
                  cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)
        
        # Update the latest frame
        with frame_lock:
            latest_frame = pattern
            
        # Run waste detection on this pattern occasionally (for testing)
        if now.second % 5 == 0:  # Every 5 seconds
            predictions = detect_waste_simple(pattern)
            if predictions:
                processed_frame = process_predictions(pattern, predictions)
                with frame_lock:
                    latest_frame = processed_frame
        
        time.sleep(0.1)

def run_libcamera_capture():
    """Captures camera frames using libcamera-still and processes them"""
    global latest_frame
    
    logger.info("Starting camera capture with libcamera-still")
    
    try:
        # Create a temporary directory for captures
        temp_dir = "/tmp/pi_captures"
        os.makedirs(temp_dir, exist_ok=True)
        
        # Main capture loop
        counter = 0
        while True:
            try:
                # Capture frame with libcamera-still
                capture_path = f"{temp_dir}/capture_{counter % 10}.jpg"
                counter += 1
                
                # Use libcamera-still to capture an image
                subprocess.run([
                    "libcamera-still", 
                    "-n",  # No preview
                    "--immediate",  # Capture immediately
                    "-o", capture_path,
                    "--width", "640", 
                    "--height", "480",
                    "-t", "1"  # Minimize timeout
                ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                
                # Load the captured image
                frame = cv2.imread(capture_path)
                
                if frame is not None:
                    # Process frame for waste detection
                    predictions = detect_waste_simple(frame)
                    processed_frame = process_predictions(frame, predictions)
                    
                    # Update the latest frame
                    with frame_lock:
                        latest_frame = processed_frame
                else:
                    logger.warning("Failed to read captured frame")
                
                # Control capture rate
                time.sleep(0.5)  # 2 FPS is enough for waste detection
                
            except Exception as e:
                logger.error(f"Error in camera capture: {e}")
                time.sleep(1)
                
    except Exception as e:
        logger.error(f"Fatal camera error: {e}")
        # Fall back to dummy pattern generator
        dummy_pattern_generator()

if __name__ == "__main__":
    try:
        # Print banner
        print("=" * 50)
        print("WASTE DETECTION PI - WITH GPS TRACKING")
        print("=" * 50)
        print(f"Dashboard IP: {DASHBOARD_IP}")
        print(f"Dashboard Port: {DASHBOARD_PORT}")
        print(f"Video Server Port: {VIDEO_PORT}")
        print(f"GPS Enabled: {GPS_ENABLED}")
        print(f"Log File: {log_file}")
        print("=" * 50)
        
        # Initialize GPS module if enabled
        gps_module = None
        if GPS_ENABLED:
            logger.info("Initializing GPS module...")
            gps_module = GPSModule(port=GPS_PORT, logger=logger)
            if gps_module.start():
                logger.info("GPS module started successfully")
            else:
                logger.warning("Failed to start GPS module, using default coordinates")
        
        # Start camera capture in a separate thread
        camera_thread = threading.Thread(target=run_libcamera_capture, daemon=True)
        camera_thread.start()
        logger.info("Camera thread started")
        
        # Start heartbeat thread
        heartbeat_thread = threading.Thread(target=send_heartbeat, daemon=True)
        heartbeat_thread.start()
        logger.info("Heartbeat thread started")
        
        # Start web server in main thread
        logger.info("Starting video server...")
        app.run(host='0.0.0.0', port=VIDEO_PORT, threaded=True)
        
    except KeyboardInterrupt:
        logger.info("Application stopped by user")
        if GPS_ENABLED and gps_module is not None:
            gps_module.stop()
    except Exception as e:
        logger.error(f"Application error: {e}")