# Waste Detection Dashboard

A real-time Streamlit dashboard for monitoring waste detection from edge devices in Singapore. This system integrates with networked cameras and sensors to provide a comprehensive waste monitoring solution.

## Overview

The Waste Detection Dashboard is the central visualization and monitoring component of the waste detection system that:

1. Receives real-time data from edge devices running waste detection
2. Displays device locations and status on an interactive map
3. Shows live video feeds from connected devices
4. Visualizes detection statistics and historical trends
5. Monitors gas sensor readings for environmental alerts
6. Stores detection data in a MariaDB database

## System Requirements

- Python 3.7+
- MariaDB/MySQL database
- Network connectivity to edge devices
- Minimum 2GB RAM (4GB+ recommended)
- Storage space for detection data and images

## Installation

### 1. Clone the Repository

```bash
git clone https://github.com/your-username/waste-detection-system.git
cd waste-detection-system/waste-dashboard
```

### 2. Set Up Python Environment

```bash
# Create a virtual environment
python -m venv venv

# Activate the environment
# On Windows:
venv\Scripts\activate
# On Linux/Mac:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 3. Set Up Database

Ensure you have MariaDB installed and running. See the [Database Setup Guide](../waste-db/db-README.md) for detailed instructions.

## Configuration

The dashboard configuration can be found in several files:

### Dashboard UI Configuration (`dashboard_ui.py`)

```python
# Database connection details
DB_HOST = "192.168.18.113"  # Change to your database host
DB_USER = "waste_user"
DB_PASSWORD = "password"  # Change in production!
DB_NAME = "waste_detection"
```

### Data Receiver Configuration (`data_receiver.py`)

```python
# Network configuration
self.host = host  # Default: '0.0.0.0' (all interfaces)
self.port = port  # Default: 5001
```

Update these values to match your network and database configuration.

## Running the Dashboard

### Start the Dashboard

```bash
streamlit run main.py
```

The dashboard will be available at `http://localhost:8501` by default.

### Debug Mode

For advanced debugging and database diagnostics, use:

```
http://localhost:8501/?debug=true
```

### Run on a Different Port

```bash
streamlit run main.py --server.port 8502
```

## Dashboard Features

### Map View
- Interactive map showing device locations
- Color-coded markers indicating device status
- Click on markers to view device details and access live feed

### Live Feed
- Real-time video stream from edge devices
- Detection overlays showing waste items
- Toggle between map and live feed views

### Metrics Panel
- Total waste detections counter
- Gas alert monitoring
- Active device count
- Connection status indicators

### Detection History
- Time-series visualization of detection data
- Filtering by date range
- Detailed device-specific statistics
- Waste type distribution analysis

### Device Management
- Automatic device discovery
- Connection status monitoring
- IP address tracking
- Device activity history

### Connection Log
- Real-time logging of device connections
- Error and status message tracking
- Debug information for troubleshooting

## Architecture

### Component Structure

The dashboard consists of several modular components:

- `main.py` - Entry point for the application
- `dashboard_ui.py` - Streamlit UI components and layout
- `data_receiver.py` - Socket server for receiving edge device data
- `state_manager.py` - Manages dashboard state and processes incoming data
- `utils.py` - Utility functions for device discovery and status checking

### Data Flow

1. **Edge Devices** capture waste detection data
2. Data is sent to the **Data Receiver** component via TCP sockets (port 5001)
3. The **State Manager** processes incoming data and updates the dashboard
4. The **Dashboard UI** displays the information in real-time
5. Detection data is stored in the **MariaDB Database** for historical analysis

## Network Requirements

- The dashboard server must be accessible by all edge devices
- Edge devices need network access to:
  - Dashboard server on port 5001 (for sending detection data)
  - Database server on port 5002 (for sending detection data with images)
- Dashboard needs access to:
  - Edge devices on port 8000 (for viewing live video feeds)
  - Database server on port 3306 (MariaDB)

## Dashboard Customization

### Map Configuration

The default map is centered on Singapore. To change this location:

1. Locate the `create_map` function in `dashboard_ui.py`
2. Change the coordinates in `m = folium.Map(location=[1.3521, 103.8198], zoom_start=12)`

### Interface Styling

Custom CSS styling can be modified in the `apply_custom_css` function in `main.py`.

### Chart Appearance

Chart configurations can be customized in `create_bottom_section_plotly` function in `dashboard_ui.py`.

## Troubleshooting

### Connection Issues

1. **No devices connecting**:
   - Verify network connectivity between dashboard and devices
   - Check that the correct IP and port are configured on edge devices
   - Use the "Discover Devices" button to scan the network
   - Check logs for connection errors

2. **Database connection errors**:
   - Verify database server is running
   - Check connection credentials in `dashboard_ui.py`
   - Enable debug mode for detailed database diagnostics

3. **Live video feed not showing**:
   - Ensure the edge device web server is running
   - Check network connectivity to the device's port 8000
   - Verify the device's IP address is correctly detected

### Dashboard Performance

If the dashboard becomes slow:

1. Reduce the retention period for detection history
2. Optimize database queries (add indexes)
3. Consider running the dashboard on a more powerful machine
4. Increase the StreamingResponse chunk size for smoother video

## Logs

Dashboard logs are stored in the `logs` directory with timestamp-based filenames:
```
logs/dashboard_YYYYMMDD_HHMMSS.log
```

View logs with:
```bash
tail -f logs/dashboard_*.log
```

## Security Recommendations

1. Change default database passwords
2. Use HTTPS for production deployments
3. Restrict network access to the dashboard
4. Implement user authentication for the dashboard
5. Keep all components updated regularly

## Running in Production

For production deployments:

1. **Use a reverse proxy**:
   ```bash
   # Example with nginx
   sudo apt install nginx
   # Configure nginx to proxy requests to Streamlit
   ```

2. **Set up as a service**:
   ```bash
   # Create a systemd service file
   sudo nano /etc/systemd/system/waste-dashboard.service
   
   # Service file content:
   [Unit]
   Description=Waste Detection Dashboard
   After=network.target
   
   [Service]
   User=your_user
   WorkingDirectory=/path/to/waste-detection-dashboard
   ExecStart=/path/to/waste-detection-dashboard/venv/bin/streamlit run main.py
   Restart=always
   RestartSec=10
   
   [Install]
   WantedBy=multi-user.target
   
   # Enable and start the service
   sudo systemctl enable waste-dashboard.service
   sudo systemctl start waste-dashboard.service
   ```

3. **Optimize database** for production loads

## Future Enhancements

Potential improvements for the dashboard:

1. User authentication system
2. Mobile application integration
3. Notification system for critical alerts
4. Advanced analytics and prediction features
5. Integration with waste management systems
6. Report generation and export functionality