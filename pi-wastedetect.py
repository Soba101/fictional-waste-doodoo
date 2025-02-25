# pi-waste-detection.py - Integrating Roboflow waste detection
from flask import Flask, Response, request
import cv2
import threading
import time
import socket
import json
import os
import logging
from datetime import datetime
import numpy as np

# Import Roboflow inference components
try:
    from inference import InferencePipeline
    ROBOFLOW_AVAILABLE = True
except ImportError:
    ROBOFLOW_AVAILABLE = False
    print("WARNING: Roboflow inference package not available. Falling back to dummy detection.")

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
DASHBOARD_IP = "192.168.18.107"  # Update with your dashboard IP
DASHBOARD_PORT = 5001
DEVICE_ID = "RaspberryPi"
VIDEO_PORT = 8000
ROBOFLOW_API_KEY = "apikey"  # Your Roboflow API key
MODEL_ID = "yolo-waste-detection/1"  # Roboflow model

# Global variables for frame sharing
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

#######################
# Roboflow Prediction Handler
#######################

def handle_prediction(predictions, frame):
    """Robust handler for predictions from Roboflow with fixed frame handling"""
    global latest_frame, latest_predictions
    
    # Extract the actual image from the VideoFrame object
    if hasattr(frame, 'image'):
        # VideoFrame object - extract the numpy array
        frame_image = frame.image
    else:
        # Already a numpy array
        frame_image = frame
    
    # Get predictions from the model
    cleaned_predictions = []
    
    # Check if predictions is a dictionary with 'predictions' key
    if isinstance(predictions, dict) and 'predictions' in predictions:
        # Extract the predictions list
        predictions_list = predictions['predictions']
        
        # Get image dimensions if available
        if 'image' in predictions and 'width' in predictions['image'] and 'height' in predictions['image']:
            img_width = predictions['image']['width']
            img_height = predictions['image']['height']
        else:
            img_width = frame_image.shape[1]
            img_height = frame_image.shape[0]
            
        # Process each prediction
        for prediction in predictions_list:
            # Extract coordinates and other data
            x = prediction.get('x', 0)
            y = prediction.get('y', 0)
            width = prediction.get('width', 0)
            height = prediction.get('height', 0)
            
            # Convert to relative coordinates (0-1)
            x_rel = x / img_width
            y_rel = y / img_height
            width_rel = width / img_width
            height_rel = height / img_height
            
            # Create clean prediction object
            cleaned_prediction = {
                'class': prediction.get('class', 'unknown'),
                'confidence': prediction.get('confidence', 0),
                'x': x_rel,
                'y': y_rel,
                'width': width_rel,
                'height': height_rel
            }
            cleaned_predictions.append(cleaned_prediction)
    
    # Create a copy of the frame for drawing
    processed_frame = frame_image.copy()
    
    # Add timestamp to the frame for display
    timestamp = datetime.now().strftime("%H:%M:%S")
    cv2.putText(processed_frame, timestamp, (10, 30), 
              cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
    
    # Mark this as a detection device by adding text
    cv2.putText(processed_frame, "WASTE DETECTION PI", (10, 70), 
              cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 0, 0), 2)
    
    # Draw boxes for visualization
    for pred in cleaned_predictions:
        # Convert relative coordinates back to absolute for drawing
        x = int(pred['x'] * processed_frame.shape[1])
        y = int(pred['y'] * processed_frame.shape[0])
        w = int(pred['width'] * processed_frame.shape[1])
        h = int(pred['height'] * processed_frame.shape[0])
        
        # Draw bounding box
        cv2.rectangle(processed_frame, (x - w//2, y - h//2), (x + w//2, y + h//2), (0, 255, 0), 2)
        
        # Add label
        label = f"{pred['class']} {pred['confidence']:.2f}"
        cv2.putText(processed_frame, label, (x - w//2, y - h//2 - 10), 
                  cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
    
    # Update global variables with thread safety
    with frame_lock:
        latest_frame = processed_frame
    
    with prediction_lock:
        latest_predictions = cleaned_predictions
    
    # If there are predictions, send them to the dashboard
    if cleaned_predictions:
        send_detection_to_dashboard(cleaned_predictions)
    
    # Return the frame with annotations
    return processed_frame

#######################
# Video Server Functions
#######################

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
                blank_frame = create_status_frame("Camera not initialized")
                _, buffer = cv2.imencode('.jpg', blank_frame)
                frame_bytes = buffer.tobytes()
                
                yield (b'--frame\r\n'
                       b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
        time.sleep(0.033)  # ~30 FPS

def create_status_frame(message):
    """Create a status frame with a message"""
    # Create blank image
    frame = np.ones((480, 640, 3), dtype=np.uint8) * 255
    # Convert to BGR (OpenCV format)
    frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
    # Add text
    cv2.putText(frame, message, (50, 240), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)
    cv2.putText(frame, f"Time: {datetime.now().strftime('%H:%M:%S')}", (50, 280), 
                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 0), 2)
    return frame

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
    
    # CRITICAL: This exact format is what the dashboard needs to validate the device
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
    interfaces = []
    try:
        # Try to get hostname and primary IP
        import socket
        hostname = socket.gethostname()
        primary_ip = socket.gethostbyname(hostname)
        interfaces.append(primary_ip)
        
        # Try alternative method
        import subprocess
        cmd = "hostname -I"
        output = subprocess.check_output(cmd.split()).decode('utf-8').strip()
        for ip in output.split():
            if ip not in interfaces:
                interfaces.append(ip)
    except Exception as e:
        logger.error(f"Error getting network interfaces: {e}")
        # Return at least one interface so we don't return an empty list
        interfaces = ["192.168.18.113"]  # Fallback to known IP
    
    return interfaces

#######################
# Dashboard Communication
#######################

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
            
            # Prepare heartbeat data
            heartbeat_data = {
                'device_id': DEVICE_ID,
                'timestamp': datetime.now().isoformat(),
                'predictions': [],  # Empty predictions for heartbeat
                'num_detections': 0,
                'lat': 1.3521,
                'lon': 103.8198,
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
    """Send detection data to dashboard"""
    global connection_attempts, successful_connections
    
    try:
        # Create data payload
        data = {
            'device_id': DEVICE_ID,
            'timestamp': datetime.now().isoformat(),
            'predictions': predictions,
            'num_detections': len(predictions),
            'lat': 1.3521,
            'lon': 103.8198,
            'gas_value': 0  # Placeholder for gas sensor value
        }
        
        # Log detection information
        logger.info(f"Sending {len(predictions)} detections to dashboard")
        
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

#######################
# Roboflow Inference Setup
#######################

def start_inference_pipeline():
    """Initialize and start the Roboflow inference pipeline"""
    logger.info("Starting Roboflow inference pipeline...")
    
    if not ROBOFLOW_AVAILABLE:
        logger.error("Roboflow inference package not available")
        camera_loop()
        return
    
    try:
        # Initialize the pipeline
        pipeline = InferencePipeline.init(
            api_key=ROBOFLOW_API_KEY,
            model_id=MODEL_ID,
            video_reference=0,  # Use default camera
            on_prediction=handle_prediction  # Use our custom handler
        )
        
        # Start the pipeline
        pipeline.start()
        logger.info("Roboflow inference pipeline started successfully")
        
        # Join the pipeline (this will block the thread)
        pipeline.join()
        
    except Exception as e:
        logger.error(f"Error in Roboflow inference pipeline: {e}")
        # Fall back to the dummy camera mode
        logger.info("Falling back to dummy camera mode")
        camera_loop()

#######################
# Camera Fallback Functions
#######################

def camera_loop():
    """Fallback camera loop if Roboflow inference fails"""
    global latest_frame
    
    logger.info("Starting fallback camera mode...")
    camera_device = None
    
    # Test camera 0
    try:
        cap = cv2.VideoCapture(0)
        if cap.isOpened():
            ret, frame = cap.read()
            if ret:
                logger.info("Camera 0 working!")
                camera_device = 0
            cap.release()
        else:
            logger.warning("Camera 0 not available")
    except Exception as e:
        logger.error(f"Error testing camera 0: {e}")
    
    # If no camera is working, create a dummy pattern for testing
    if camera_device is None:
        logger.error("No working camera found! Using dummy pattern.")
        
        # Create a dummy test pattern that changes to show it's active
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
                
            time.sleep(0.1)
        return
    
    # Start the camera loop with the working camera
    logger.info(f"Starting camera loop with device {camera_device}")
    cap = cv2.VideoCapture(camera_device)
    
    # Try to set resolution
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
    
    while True:
        try:
            ret, frame = cap.read()
            if ret:
                # Add a timestamp to show it's live
                timestamp = datetime.now().strftime("%H:%M:%S")
                cv2.putText(frame, timestamp, (10, 30), 
                          cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
                
                # Mark this as a real device by adding text
                cv2.putText(frame, "WASTE DETECTION PI", (10, 70), 
                          cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 0, 0), 2)
                
                # Update the latest frame
                with frame_lock:
                    latest_frame = frame
            else:
                logger.warning("Failed to read frame")
                time.sleep(1)  # Wait a bit before retrying
        except Exception as e:
            logger.error(f"Camera error: {e}")
            time.sleep(1)
            
            # Try to reconnect
            try:
                cap.release()
                cap = cv2.VideoCapture(camera_device)
            except:
                pass
                
        # Small delay to control frame rate
        time.sleep(0.033)  # ~30 FPS

#######################
# Main Program
#######################

if __name__ == "__main__":
    try:
        # Print banner
        print("=" * 50)
        print("WASTE DETECTION PI")
        print("=" * 50)
        print(f"Dashboard IP: {DASHBOARD_IP}")
        print(f"Dashboard Port: {DASHBOARD_PORT}")
        print(f"Video Server Port: {VIDEO_PORT}")
        print(f"Roboflow Available: {ROBOFLOW_AVAILABLE}")
        if ROBOFLOW_AVAILABLE:
            print(f"Roboflow Model: {MODEL_ID}")
        print(f"Log File: {log_file}")
        print("=" * 50)
        
        # Start Roboflow inference in a separate thread
        inference_thread = threading.Thread(target=start_inference_pipeline, daemon=True)
        inference_thread.start()
        logger.info("Inference thread started")
        
        # Start heartbeat thread
        heartbeat_thread = threading.Thread(target=send_heartbeat, daemon=True)
        heartbeat_thread.start()
        logger.info("Heartbeat thread started")
        
        # Start video server in main thread
        logger.info("Starting video server...")
        app.run(host='0.0.0.0', port=VIDEO_PORT, threaded=True)
        
    except KeyboardInterrupt:
        logger.info("Application stopped by user")
    except Exception as e:
        logger.error(f"Application error: {e}")
