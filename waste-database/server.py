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
        logging.StreamHandler(),
        logging.FileHandler('waste-database.log')
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
mqtt_client = mqtt.Client(client_id="database_server", clean_session=True)
mqtt_client.reconnect_delay_set(min_delay=1, max_delay=60)  # Set reconnect delay between 1 and 60 seconds

def on_mqtt_disconnect(client, userdata, rc):
    """Callback when disconnected from MQTT broker."""
    if rc != 0:
        logger.error(f"Unexpected disconnection from MQTT broker with code: {rc}")
    else:
        logger.info("Disconnected from MQTT broker")

def on_mqtt_connect(client, userdata, flags, rc):
    """Callback when connected to MQTT broker."""
    if rc == 0:
        logger.info("Connected to MQTT broker")
        
        # Subscribe to all device topics
        topics = [
            f"{config.MQTT_TOPIC_PREFIX}/+/detections",
            f"{config.MQTT_TOPIC_PREFIX}/+/status",
            f"{config.MQTT_TOPIC_PREFIX}/+/heartbeat"
        ]
        
        for topic in topics:
            try:
                client.subscribe(topic)
                logger.info(f"Subscribed to topic: {topic}")
            except Exception as e:
                logger.error(f"Failed to subscribe to {topic}: {e}")
    else:
        logger.error(f"Failed to connect to MQTT broker with code: {rc}")

def on_mqtt_message(client, userdata, msg):
    """Callback when message is received from MQTT broker."""
    try:
        # Parse topic to get device ID and message type
        topic_parts = msg.topic.split('/')
        if len(topic_parts) != 3:
            logger.error(f"Invalid topic format: {msg.topic}")
            return
            
        device_id = topic_parts[1]
        message_type = topic_parts[2]
        
        # Parse message data
        try:
            data = json.loads(msg.payload.decode())
            logger.info(f"Received message data: {data}")
        except json.JSONDecodeError as e:
            logger.error(f"Failed to decode JSON message: {e}")
            return
            
        # Log all messages
        logger.info(f"Received {message_type} message from device {device_id}")
        
        # Handle different message types
        if message_type == 'detections':
            # Validate required fields for detections
            required_fields = ['timestamp', 'num_detections', 'predictions', 'lat', 'lon', 
                             'has_gps_fix', 'satellites', 'altitude', 'gas_value', 'gas_detected']
            missing_fields = [field for field in required_fields if field not in data]
            if missing_fields:
                logger.error(f"Missing required fields in detection message: {missing_fields}")
                return
            
            # Store detection data in database using Flask application context
            with app.app_context():
                try:
                    logger.info(f"Creating detection object with data: {data}")
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
                    
                    logger.info("Adding detection to database session")
                    db.session.add(detection)
                    
                    logger.info("Committing detection to database")
                    db.session.commit()
                    
                    logger.info(f"Successfully stored detection from device {device_id}")
                    
                except SQLAlchemyError as e:
                    logger.error(f"Database error while storing detection: {e}")
                    db.session.rollback()
                except Exception as e:
                    logger.error(f"Unexpected error while storing detection: {e}")
                    db.session.rollback()
        elif message_type == 'status':
            # Store status data in database
            with app.app_context():
                try:
                    status = DeviceStatus(
                        device_id=device_id,
                        timestamp=datetime.fromisoformat(data['timestamp']),
                        status=data.get('status', 'unknown'),
                        sender_ip=data.get('sender_ip'),
                        lat=data.get('lat'),
                        lon=data.get('lon'),
                        has_gps_fix=data.get('has_gps_fix'),
                        satellites=data.get('satellites'),
                        altitude=data.get('altitude'),
                        gas_value=data.get('gas_value'),
                        gas_detected=data.get('gas_detected'),
                        uptime=data.get('uptime'),
                        connection_stats=json.dumps(data.get('connection_stats', {}))
                    )
                    
                    db.session.add(status)
                    db.session.commit()
                    
                    logger.info(f"Stored status from device {device_id}")
                    
                except SQLAlchemyError as e:
                    logger.error(f"Database error while storing status: {e}")
                    db.session.rollback()
        elif message_type == 'heartbeat':
            # Store heartbeat data in database
            with app.app_context():
                try:
                    heartbeat = DeviceHeartbeat(
                        device_id=device_id,
                        timestamp=datetime.fromisoformat(data['timestamp']),
                        sender_ip=data.get('sender_ip'),
                        lat=data.get('lat'),
                        lon=data.get('lon'),
                        has_gps_fix=data.get('has_gps_fix'),
                        satellites=data.get('satellites'),
                        altitude=data.get('altitude'),
                        gas_value=data.get('gas_value'),
                        gas_detected=data.get('gas_detected'),
                        uptime=data.get('uptime'),
                        connection_stats=json.dumps(data.get('connection_stats', {}))
                    )
                    
                    db.session.add(heartbeat)
                    db.session.commit()
                    
                    logger.info(f"Stored heartbeat from device {device_id}")
                    
                except SQLAlchemyError as e:
                    logger.error(f"Database error while storing heartbeat: {e}")
                    db.session.rollback()
            
    except Exception as e:
        logger.error(f"Error processing MQTT message: {e}")

# Database models
class Detection(db.Model):
    """Model for storing detection data."""
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

class DeviceStatus(db.Model):
    """Model for storing device status information."""
    id = db.Column(db.Integer, primary_key=True)
    device_id = db.Column(db.String(50), nullable=False)
    timestamp = db.Column(db.DateTime, nullable=False)
    status = db.Column(db.String(20), nullable=False)
    sender_ip = db.Column(db.String(50))
    lat = db.Column(db.Float)
    lon = db.Column(db.Float)
    has_gps_fix = db.Column(db.Boolean)
    satellites = db.Column(db.Integer)
    altitude = db.Column(db.Float)
    gas_value = db.Column(db.Float)
    gas_detected = db.Column(db.Boolean)
    uptime = db.Column(db.Float)
    connection_stats = db.Column(db.Text)

class DeviceHeartbeat(db.Model):
    """Model for storing device heartbeat information."""
    id = db.Column(db.Integer, primary_key=True)
    device_id = db.Column(db.String(50), nullable=False)
    timestamp = db.Column(db.DateTime, nullable=False)
    sender_ip = db.Column(db.String(50))
    lat = db.Column(db.Float)
    lon = db.Column(db.Float)
    has_gps_fix = db.Column(db.Boolean)
    satellites = db.Column(db.Integer)
    altitude = db.Column(db.Float)
    gas_value = db.Column(db.Float)
    gas_detected = db.Column(db.Boolean)
    uptime = db.Column(db.Float)
    connection_stats = db.Column(db.Text)

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

@app.route('/api/device_status/<device_id>')
def get_device_status(device_id):
    """Get the latest status for a specific device."""
    try:
        # Get the most recent status entry for the device
        status = DeviceStatus.query.filter_by(device_id=device_id)\
            .order_by(DeviceStatus.timestamp.desc())\
            .first()
        
        if status:
            return jsonify({
                'device_id': status.device_id,
                'timestamp': status.timestamp.isoformat(),
                'status': status.status,
                'sender_ip': status.sender_ip,
                'lat': status.lat,
                'lon': status.lon,
                'has_gps_fix': status.has_gps_fix,
                'satellites': status.satellites,
                'altitude': status.altitude,
                'gas_value': status.gas_value,
                'gas_detected': status.gas_detected,
                'uptime': status.uptime,
                'connection_stats': json.loads(status.connection_stats) if status.connection_stats else {}
            })
        else:
            return jsonify({'error': 'No status found for device'}), 404
            
    except Exception as e:
        logger.error(f"Error retrieving device status: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/device_heartbeat/<device_id>')
def get_device_heartbeat(device_id):
    """Get the latest heartbeat for a specific device."""
    try:
        # Get the most recent heartbeat entry for the device
        heartbeat = DeviceHeartbeat.query.filter_by(device_id=device_id)\
            .order_by(DeviceHeartbeat.timestamp.desc())\
            .first()
        
        if heartbeat:
            return jsonify({
                'device_id': heartbeat.device_id,
                'timestamp': heartbeat.timestamp.isoformat(),
                'sender_ip': heartbeat.sender_ip,
                'lat': heartbeat.lat,
                'lon': heartbeat.lon,
                'has_gps_fix': heartbeat.has_gps_fix,
                'satellites': heartbeat.satellites,
                'altitude': heartbeat.altitude,
                'gas_value': heartbeat.gas_value,
                'gas_detected': heartbeat.gas_detected,
                'uptime': heartbeat.uptime,
                'connection_stats': json.loads(heartbeat.connection_stats) if heartbeat.connection_stats else {}
            })
        else:
            return jsonify({'error': 'No heartbeat found for device'}), 404
            
    except Exception as e:
        logger.error(f"Error retrieving device heartbeat: {e}")
        return jsonify({'error': str(e)}), 500

def start_mqtt_client():
    """Start the MQTT client."""
    mqtt_client.on_connect = on_mqtt_connect
    mqtt_client.on_message = on_mqtt_message
    mqtt_client.on_disconnect = on_mqtt_disconnect
    
    try:
        # Set up message handlers before connecting
        mqtt_client.connect(config.MQTT_BROKER, config.MQTT_PORT, keepalive=60)
        mqtt_client.loop_start()
        logger.info("MQTT client started")
    except Exception as e:
        logger.error(f"Failed to start MQTT client: {e}")
        raise  # Re-raise the exception to handle it in the main function

def stop_mqtt_client():
    """Stop the MQTT client."""
    mqtt_client.loop_stop()
    mqtt_client.disconnect()
    logger.info("MQTT client stopped")

def init_db():
    """Initialize the database tables."""
    with app.app_context():
        try:
            db.create_all()
            logger.info("Database tables created successfully")
        except Exception as e:
            logger.error(f"Error creating database tables: {e}")
            raise

if __name__ == '__main__':
    try:
        # Initialize database tables
        init_db()
        
        # Start MQTT client
        start_mqtt_client()
        
        # Start Flask server
        app.run(host='0.0.0.0', port=config.DATABASE_PORT)
    except Exception as e:
        logger.error(f"Failed to start server: {e}")
        stop_mqtt_client()  # Ensure MQTT client is stopped on error 