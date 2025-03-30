"""
Database server using MQTT for receiving data from edge devices.
"""
import json
import logging
import threading
import time
from datetime import datetime
import paho.mqtt.client as mqtt
from flask import Flask, jsonify, request
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.exc import SQLAlchemyError

import config

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(config.LOG_FILE),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger('database-server')

# Initialize Flask app
app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = config.DATABASE_URL
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
    'pool_pre_ping': True,  # Enable connection health checks
    'pool_recycle': 3600,   # Recycle connections after 1 hour
    'pool_size': 10,        # Maximum number of connections
    'max_overflow': 20      # Maximum number of connections that can be created beyond pool_size
}
db = SQLAlchemy(app)

# MQTT client for receiving data
mqtt_client = mqtt.Client(client_id="database_server")

def on_mqtt_connect(client, userdata, flags, rc):
    """Callback when connected to MQTT broker."""
    if rc == 0:
        logger.info("Connected to MQTT broker")
        
        # Subscribe to detection topics
        client.subscribe(f"{config.MQTT_TOPIC_PREFIX}/+/detections")
    else:
        logger.error(f"Failed to connect to MQTT broker with code: {rc}")

def on_mqtt_message(client, userdata, msg):
    """Callback when message is received from MQTT broker."""
    try:
        # Parse topic to get device ID
        topic_parts = msg.topic.split('/')
        if len(topic_parts) != 3:
            logger.error(f"Invalid topic format: {msg.topic}")
            return
            
        device_id = topic_parts[1]
        
        # Parse message data
        try:
            data = json.loads(msg.payload.decode())
        except json.JSONDecodeError as e:
            logger.error(f"Failed to decode JSON message: {e}")
            return
            
        # Validate required fields
        required_fields = ['timestamp', 'num_detections', 'predictions', 'lat', 'lon', 
                         'has_gps_fix', 'satellites', 'altitude', 'gas_value', 'gas_detected']
        missing_fields = [field for field in required_fields if field not in data]
        if missing_fields:
            logger.error(f"Missing required fields in message: {missing_fields}")
            return
        
        # Store detection data in database using Flask application context
        with app.app_context():
            try:
                detection = Detection(
                    device_id=device_id,
                    timestamp=datetime.fromisoformat(data['timestamp']),
                    num_detections=data['num_detections'],
                    predictions=json.dumps(data['predictions']),
                    lat=data['lat'],
                    lon=data['lon'],
                    has_gps_fix=data['has_gps_fix'],
                    satellites=data['satellites'],
                    altitude=data['altitude'],
                    gas_value=data['gas_value'],
                    gas_detected=data['gas_detected']
                )
                
                db.session.add(detection)
                db.session.commit()
                
                logger.info(f"Stored detection from device {device_id}")
                
            except SQLAlchemyError as e:
                logger.error(f"Database error while storing detection: {e}")
                db.session.rollback()
            
    except Exception as e:
        logger.error(f"Error processing MQTT message: {e}")

# Database models
class Detection(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    device_id = db.Column(db.String(50), nullable=False)
    timestamp = db.Column(db.DateTime, nullable=False)
    num_detections = db.Column(db.Integer, nullable=False)
    predictions = db.Column(db.Text, nullable=False)
    lat = db.Column(db.Float, nullable=False)
    lon = db.Column(db.Float, nullable=False)
    has_gps_fix = db.Column(db.Boolean, nullable=False)
    satellites = db.Column(db.Integer, nullable=False)
    altitude = db.Column(db.Float, nullable=False)
    gas_value = db.Column(db.Float, nullable=False)
    gas_detected = db.Column(db.Boolean, nullable=False)
    
    def __repr__(self):
        return f"<Detection {self.id} from {self.device_id} at {self.timestamp}>"

@app.route('/api/detections')
def get_detections():
    """Get list of detections."""
    try:
        detections = Detection.query.order_by(Detection.timestamp.desc()).limit(100)
        return jsonify({
            'detections': [
                {
                    'id': d.id,
                    'device_id': d.device_id,
                    'timestamp': d.timestamp.isoformat(),
                    'num_detections': d.num_detections,
                    'predictions': json.loads(d.predictions),
                    'lat': d.lat,
                    'lon': d.lon,
                    'has_gps_fix': d.has_gps_fix,
                    'satellites': d.satellites,
                    'altitude': d.altitude,
                    'gas_value': d.gas_value,
                    'gas_detected': d.gas_detected
                }
                for d in detections
            ]
        })
    except Exception as e:
        logger.error(f"Error retrieving detections: {e}")
        return jsonify({'error': 'Failed to retrieve detections'}), 500

@app.route('/api/detections/<device_id>')
def get_device_detections(device_id):
    """Get detections for a specific device."""
    try:
        detections = Detection.query.filter_by(device_id=device_id)\
            .order_by(Detection.timestamp.desc())\
            .limit(100)
        return jsonify({
            'detections': [
                {
                    'id': d.id,
                    'device_id': d.device_id,
                    'timestamp': d.timestamp.isoformat(),
                    'num_detections': d.num_detections,
                    'predictions': json.loads(d.predictions),
                    'lat': d.lat,
                    'lon': d.lon,
                    'has_gps_fix': d.has_gps_fix,
                    'satellites': d.satellites,
                    'altitude': d.altitude,
                    'gas_value': d.gas_value,
                    'gas_detected': d.gas_detected
                }
                for d in detections
            ]
        })
    except Exception as e:
        logger.error(f"Error retrieving detections for device {device_id}: {e}")
        return jsonify({'error': 'Failed to retrieve detections'}), 500

@app.route('/api/detections/stats')
def get_detection_stats():
    """Get detection statistics."""
    try:
        total_detections = Detection.query.count()
        devices = db.session.query(Detection.device_id, db.func.count(Detection.id))\
            .group_by(Detection.device_id)\
            .all()
        
        return jsonify({
            'total_detections': total_detections,
            'detections_by_device': {
                device_id: count for device_id, count in devices
            }
        })
    except Exception as e:
        logger.error(f"Error retrieving detection stats: {e}")
        return jsonify({'error': 'Failed to retrieve statistics'}), 500

@app.route('/api/detections/search')
def search_detections():
    """Search detections with filters."""
    try:
        query = Detection.query
        
        # Get filter parameters
        device_id = request.args.get('device_id')
        start_time = request.args.get('start_time')
        end_time = request.args.get('end_time')
        min_detections = request.args.get('min_detections')
        has_gas = request.args.get('has_gas')
        
        # Apply filters
        if device_id:
            query = query.filter_by(device_id=device_id)
        if start_time:
            query = query.filter(Detection.timestamp >= datetime.fromisoformat(start_time))
        if end_time:
            query = query.filter(Detection.timestamp <= datetime.fromisoformat(end_time))
        if min_detections:
            query = query.filter(Detection.num_detections >= int(min_detections))
        if has_gas == 'true':
            query = query.filter_by(gas_detected=True)
        
        # Get results
        detections = query.order_by(Detection.timestamp.desc()).limit(100)
        
        return jsonify({
            'detections': [
                {
                    'id': d.id,
                    'device_id': d.device_id,
                    'timestamp': d.timestamp.isoformat(),
                    'num_detections': d.num_detections,
                    'predictions': json.loads(d.predictions),
                    'lat': d.lat,
                    'lon': d.lon,
                    'has_gps_fix': d.has_gps_fix,
                    'satellites': d.satellites,
                    'altitude': d.altitude,
                    'gas_value': d.gas_value,
                    'gas_detected': d.gas_detected
                }
                for d in detections
            ]
        })
    except Exception as e:
        logger.error(f"Error searching detections: {e}")
        return jsonify({'error': 'Failed to search detections'}), 500

def start_mqtt_client():
    """Start the MQTT client."""
    mqtt_client.on_connect = on_mqtt_connect
    mqtt_client.on_message = on_mqtt_message
    
    try:
        mqtt_client.connect(config.MQTT_BROKER, config.MQTT_PORT, keepalive=60)
        mqtt_client.loop_start()
        logger.info("MQTT client started")
    except Exception as e:
        logger.error(f"Failed to start MQTT client: {e}")

def stop_mqtt_client():
    """Stop the MQTT client."""
    mqtt_client.loop_stop()
    mqtt_client.disconnect()
    logger.info("MQTT client stopped")

if __name__ == '__main__':
    # Create database tables
    with app.app_context():
        try:
            db.create_all()
            logger.info("Database tables created successfully")
        except Exception as e:
            logger.error(f"Failed to create database tables: {e}")
            exit(1)
    
    # Start MQTT client
    start_mqtt_client()
    
    # Start Flask server
    app.run(host='0.0.0.0', port=config.DATABASE_PORT) 