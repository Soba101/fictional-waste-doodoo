# Waste Detection Dashboard

A real-time Streamlit dashboard for monitoring waste detection from edge devices in Singapore. This system integrates with networked cameras and sensors to provide a comprehensive waste monitoring solution.

## Overview

The Waste Detection Dashboard is designed to:
- Receive and process data from edge devices running waste detection models
- Display real-time waste detection information on an interactive map
- Show live video feeds from connected devices
- Track detection statistics and gas sensor alerts
- Maintain historical data for trend analysis
- Discover and monitor edge devices on the network

## Project Structure

The project is modular and organized into several components:

- `main.py` - Entry point that initializes the dashboard, sets up logging, and applies styling
- `data_receiver.py` - Contains the `DataReceiver` class that handles socket connections from edge devices
- `dashboard_ui.py` - Defines the Streamlit UI components, layouts, and visualizations
- `utils.py` - Utility functions for device discovery, status checking, and logging
- `state_manager.py` - Manages Streamlit session state and processes incoming data
- `__init__.py` - Makes the directory a proper Python package

## Features

### Real-time Monitoring
- Socket-based communication with edge devices
- Thread-safe data processing with queues
- Real-time metrics and status updates

### Interactive Map
- Folium-based map showing device locations
- Color-coded markers based on device status
- Clickable markers to access device details

### Live Video Feed
- Stream integration from device cameras
- Toggle between map and live feed views
- Error handling for connectivity issues

### Data Visualization
- Detection history charts with Plotly
- Waste type distribution analysis
- Time-series charts for historical trends

### Network Management
- Automatic device discovery on local network
- IP tracking and connection management
- Device status monitoring and alerts

### Database Integration
- MariaDB/MySQL integration for persistent data storage
- Historical data retrieval and analysis
- Detection event tracking and reporting

### Debugging Tools
- Debug mode for system diagnostics
- Database connection debugging
- Query testing and custom SQL execution

## Setup and Installation

### Prerequisites

- Python 3.7+
- MariaDB or MySQL database server
- Network connectivity to edge devices

### Database Setup

1. Install and configure MariaDB/MySQL server
2. Create a database named `waste_detection`
3. Create a user with appropriate permissions
4. Update the database connection details in `dashboard_ui.py`:
   ```python
   DB_HOST = "your_database_host"
   DB_USER = "waste_user"
   DB_PASSWORD = "your_password"
   DB_NAME = "waste_detection"
   ```

### Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/your-username/waste-detection-dashboard.git
   cd waste-detection-dashboard
   ```

2. Create a virtual environment (recommended):
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. Install required dependencies:
   ```bash
   pip install -r requirements.txt
   ```

### Starting the Dashboard

```bash
streamlit run main.py
```

The dashboard will be available at `http://localhost:8501` by default.

To enable debug mode, append `?debug=true` to the URL:
```
http://localhost:8501/?debug=true
```

## Edge Device Integration

### Communication Protocol

Edge devices should connect to the dashboard via TCP socket on port 5001 and send JSON-formatted data with the following structure:

```json
{
  "device_id": "waste-device-01",
  "timestamp": "2025-03-19T14:30:00",
  "lat": 1.3521,
  "lon": 103.8198,
  "predictions": [
    {
      "class": "plastic_bottle",
      "confidence": 0.92,
      "x": 100,
      "y": 150,
      "width": 50,
      "height": 120
    }
  ],
  "gas_value": 320
}
```

### Required Fields:
- `device_id`: Unique identifier for the device
- `timestamp`: ISO-formatted timestamp
- `predictions`: Array of detection results including class, confidence, and coordinates

### Optional Fields:
- `lat`/`lon`: Device location coordinates
- `gas_value`: Gas sensor reading (for detecting methane or other gases)

### Device Web Server

Edge devices should run a web server on port 8000 with the following endpoints:
- `/video_feed` - MJPEG stream for live video
- `/status` - JSON endpoint returning device status information

## Database Schema

The system requires the following tables:

### `detections`
- `detection_id` - Unique ID for each detection event
- `device_id` - ID of the detecting device
- `timestamp` - When the detection occurred
- `num_detections` - Number of items detected
- `gas_value` - Gas sensor reading

### `detected_items`
- `item_id` - Unique ID for each detected item
- `detection_id` - Reference to parent detection event
- `class_name` - Type of waste detected
- `confidence` - Detection confidence score
- `x_coord`, `y_coord`, `width`, `height` - Bounding box coordinates

### `keyframes`
- `keyframe_id` - Unique ID for image
- `detection_id` - Reference to detection event
- `image_data` - Binary image data

## Configuration Options

The dashboard can be configured by modifying the following:

- **Socket Binding**: To change the listening port, modify the `port` parameter in `data_receiver.py`
- **Database Connection**: Update database parameters in `dashboard_ui.py`
- **Map Center**: Default map location is set to Singapore (1.3521, 103.8198)
- **Gas Alert Threshold**: Default is 500, adjust in `state_manager.py`
- **Device Timeout**: Devices are considered inactive after 5 minutes without data

## Troubleshooting

### Common Issues

1. **No Devices Connecting**
   - Verify network connectivity between dashboard and devices
   - Check firewall settings to ensure port 5001 is open
   - Use the "Discover Devices" button to scan the network

2. **Database Connection Errors**
   - Confirm database server is running
   - Verify connection credentials
   - Check network accessibility to database server
   - Enable debug mode for detailed database diagnostics

3. **Missing Live Video Feed**
   - Ensure device web server is running on port 8000
   - Verify network path between dashboard and device
   - Check browser security settings for mixed content

### Logs

Detailed logs are stored in the `logs/` directory with timestamp-based filenames.

## Performance Considerations

- The dashboard is designed to handle multiple edge devices
- For large deployments, consider database indexing and optimization
- Socket timeouts are set to prevent blocking operations
- Thread safety is implemented with queues for communication

## Future Enhancements

- User authentication system
- Device configuration management
- Alarm and notification system
- Mobile application integration
- AI-based trend analysis
- Integration with waste management systems

## License

MIT

## Contributors

- Your Name
- Team Members

## Acknowledgments

- Singapore Waste Management Initiative
- Streamlit Community
- Open Source Contributors
