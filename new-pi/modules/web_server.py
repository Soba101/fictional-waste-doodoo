"""
Web server module using Flask for video streaming and status reporting.
"""
import logging
import time
from datetime import datetime
from flask import Flask, Response, request, render_template_string
import json

import config
from utils.helpers import get_network_interfaces

logger = logging.getLogger('web-server-module')

class WebServerModule:
    def __init__(self, camera_module, detection_module, communication_module, gps_module=None, gas_module=None):
        """
        Initialize the web server module.
        
        Args:
            camera_module: Camera module instance for frames
            detection_module: Detection module instance for predictions
            communication_module: Communication module for connection stats
            gps_module: Optional GPS module for location data
            gas_module: Optional gas module for gas sensor data
        """
        self.camera_module = camera_module
        self.detection_module = detection_module
        self.communication_module = communication_module
        self.gps_module = gps_module
        self.gas_module = gas_module
        self.app = Flask(__name__)
        self.start_time = time.time()
        
        # Register routes
        self._register_routes()
    
    def _register_routes(self):
        """Register the web server routes."""
        
        @self.app.route('/')
        def index():
            # Get current detection count
            predictions = self.detection_module.get_latest_predictions()
            detection_count = len(predictions)
            
            # Get connection stats
            connection_stats = self.communication_module.get_connection_stats()
            
            # Get gas sensor status
            gas_status = "Disabled"
            gas_value = 0
            if self.gas_module:
                gas_data = self.gas_module.get_gas_data()
                gas_status = "DETECTED!" if gas_data['gas_detected'] else "Normal"
                gas_value = gas_data['gas_value']
            
            # Get GPS status
            gps_status = "Disabled"
            if self.gps_module:
                position = self.gps_module.get_position()
                if position['has_fix']:
                    gps_status = f"Active ({position['satellites']} satellites)"
                else:
                    gps_status = "No fix"
            
            # Return HTML template
            return render_template_string('''
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
                    .gas-alert {
                        background-color: #ffcccc;
                        color: #cc0000;
                        font-weight: bold;
                        padding: 5px;
                        border-radius: 3px;
                        margin-top: 5px;
                    }
                    .gas-normal {
                        background-color: #ccffcc;
                        color: #006600;
                        padding: 5px;
                        border-radius: 3px;
                        margin-top: 5px;
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
                    <p>Connection Status: Connected to dashboard at {{ dashboard_ip }}:{{ dashboard_port }}</p>
                    <p>Video server running at port {{ video_port }}</p>
                    <p>Current Detections: {{ detection_count }}</p>
                    <p>Successful Connections: {{ successful_connections }}</p>
                    <p>Failed Connections: {{ failed_connections }}</p>
                    <p>Camera: Raspberry Pi Camera Module</p>
                    <p>Detection Method: Simple Color Detection</p>
                    <p>GPS Status: {{ gps_status }}</p>
                    <p>Gas Sensor Status: 
                        <span class="{{ 'gas-alert' if gas_status == 'DETECTED!' else 'gas-normal' }}">
                            {{ gas_status }} (Value: {{ gas_value }})
                        </span>
                    </p>
                    <p>Uptime: {{ uptime }} seconds</p>
                </div>
            </body>
            </html>
            ''', 
            dashboard_ip=config.DASHBOARD_IP,
            dashboard_port=config.DASHBOARD_PORT,
            video_port=config.VIDEO_PORT,
            detection_count=detection_count,
            successful_connections=connection_stats['successful_connections'],
            failed_connections=connection_stats['failed_connections'],
            gas_status=gas_status,
            gas_value=gas_value,
            gps_status=gps_status,
            uptime=int(connection_stats['uptime'])
            )
        
        @self.app.route('/video_feed')
        def video_feed():
            # Route for video streaming
            return Response(self._generate_frames(),
                           mimetype='multipart/x-mixed-replace; boundary=frame')
        
        @self.app.route('/status')
        def status():
            # Status endpoint that matches what the dashboard expects
            client_ip = request.remote_addr
            logger.info(f"Status request from: {client_ip}")
            
            # Get current detection count
            predictions = self.detection_module.get_latest_predictions()
            
            # Get connection stats
            connection_stats = self.communication_module.get_connection_stats()
            
            # Get gas sensor status if available
            gas_value = 0
            gas_detected = False
            if self.gas_module:
                gas_data = self.gas_module.get_gas_data()
                gas_value = gas_data['gas_value']
                gas_detected = gas_data['gas_detected']
            
            # Get GPS coordinates if available
            lat = config.DEFAULT_LAT
            lon = config.DEFAULT_LON
            if self.gps_module:
                position = self.gps_module.get_position()
                if position['has_fix']:
                    lat = position['latitude']
                    lon = position['longitude']
            
            # Status data for dashboard
            status_data = {
                "device_id": config.DEVICE_ID,
                "timestamp": datetime.now().isoformat(),
                "uptime": connection_stats['uptime'],
                "connection": {
                    "success_count": connection_stats['successful_connections'],
                    "failure_count": connection_stats['failed_connections'],
                    "last_status": "Active",
                    "last_attempt": datetime.now().isoformat()
                },
                "coordinates": {
                    "lat": lat,
                    "lon": lon
                },
                "sensors": {
                    "gas_value": gas_value,
                    "gas_detected": gas_detected
                },
                "network_interfaces": get_network_interfaces()
            }
            
            return json.dumps(status_data)
    
    def _generate_frames(self):
        """Generate video frames for streaming."""
        while True:
            # Get the latest frame from the camera module
            frame = self.camera_module.get_latest_frame()
            
            # Encode frame to JPEG
            try:
                import cv2
                _, buffer = cv2.imencode('.jpg', frame)
                frame_bytes = buffer.tobytes()
                
                # Yield the frame in MJPEG format
                yield (b'--frame\r\n'
                       b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
            except Exception as e:
                logger.error(f"Error encoding frame: {e}")
                # Wait a bit before trying again
                time.sleep(0.1)
                continue
                
            # Control the frame rate
            time.sleep(0.033)  # ~30 FPS
    
    def start(self):
        """Start the web server."""
        logger.info(f"Starting web server on port {config.VIDEO_PORT}")
        self.app.run(host='0.0.0.0', port=config.VIDEO_PORT, threaded=True)
