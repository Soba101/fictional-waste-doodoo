# Raspberry Pi Waste Detection Edge Device

This document provides setup and configuration instructions for the Raspberry Pi-based edge devices in the Waste Detection System.

## Overview

The Raspberry Pi edge device serves as the detection and sensing component of the waste detection system, with the following capabilities:

1. Waste detection using YOLO model with GPU acceleration
2. Live video streaming to the dashboard
3. GPS location tracking (optional)
4. Gas detection with MQ-2 sensor (optional)
5. Communication with the central dashboard and database

## Detection Performance

The waste detection system has been evaluated on various waste types, showing strong performance metrics:

### Model Performance
- High precision and recall across different waste categories
- Robust detection in various lighting conditions
- Efficient inference time on Raspberry Pi 5 with GPU acceleration

### Performance Metrics
The system's detection performance is visualized in the following plots (available in the `docs` directory):

1. **Precision-Recall Curve** ([PR_curve.png](../docs/PR_curve.png))
   - Shows the trade-off between precision and recall
   - Demonstrates the model's ability to maintain high precision while increasing recall

2. **Precision Curve** ([P_curve.png](../docs/P_curve.png))
   - Illustrates precision across different confidence thresholds
   - Helps in selecting optimal confidence threshold for deployment

3. **Recall Curve** ([R_curve.png](../docs/R_curve.png))
   - Shows recall performance across confidence thresholds
   - Useful for understanding detection sensitivity

4. **F1 Score** ([F1_curve.png](../docs/F1_curve.png))
   - Harmonic mean of precision and recall
   - Indicates overall model performance

5. **Overall Results** ([results.png](../docs/results.png))
   - Comprehensive visualization of model performance
   - Includes per-class performance metrics

### Real-world Performance
- Average inference time: < 100ms per frame on Raspberry Pi 5
- Detection accuracy: > 90% for common waste types
- Robust to varying environmental conditions
- Minimal false positives in real-world scenarios

**Note:** Real-world performance may vary depending on:
- Environmental conditions (lighting, weather, camera placement)
- Hardware configuration and system load
- Network conditions and latency
- Quality and condition of the camera
- Specific waste types and their presentation
- Model quantization and optimization settings

## Hardware Setup

**⚠️ Important:** For detailed hardware wiring instructions, GPIO pinout, and component connections, please refer to the [HARDWARE.md](/new-pi/HARDWARE.md) document. This file provides comprehensive information about:

- Complete wiring diagrams
- Raspberry Pi 5 GPIO layout
- Specific connection details for the camera, GPS module, and gas sensor
- Testing procedures for all hardware components
- Troubleshooting hardware issues

## Software Prerequisites

- Raspberry Pi OS (Bullseye or newer, 64-bit recommended)
- Python 3.7+
- Required Python packages (see `requirements.txt`)
- System dependencies (installed via `setup.sh`)

## Installation

### 1. Set Up Raspberry Pi OS

1. Install Raspberry Pi OS using the Raspberry Pi Imager
2. Enable required interfaces:
   ```bash
   sudo raspi-config
   ```
   Navigate to "Interface Options" and enable:
   - Camera
   - SSH
   - I2C (if using gas sensor)
   - Serial (for GPS module)

3. Update the system:
   ```bash
   sudo apt update
   sudo apt upgrade -y
   ```

### 2. Install Software Dependencies

1. Clone the repository:
   ```bash
   git clone https://github.com/your-username/waste-detection-system.git
   cd waste-detection-system/new-pi
   ```

2. Make the setup script executable and run it:
   ```bash
   chmod +x setup.sh
   ./setup.sh
   ```

3. Download the YOLO model:
   - Download the quantized YOLO model from [YOUR_MODEL_DOWNLOAD_URL]
   - Place it in the `models` directory as `best_integer_quant.tflite`
   - The model should be in TFLite format for optimal performance

### 3. Configure the Device

Edit the configuration file `config.py` to set up your device:

```python
# Set your device ID (must be unique for each device)
DEVICE_ID = "RaspberryPi5"

# Configure dashboard and database server addresses
DASHBOARD_IP = "192.168.18.107"  # Dashboard server IP
DASHBOARD_PORT = 5001             # Dashboard server port
DATABASE_IP = "192.168.18.113"    # Database server IP 
DATABASE_PORT = 5002              # Database server port
VIDEO_PORT = 8000                 # Local video streaming port

# Enable or disable hardware components
GPS_ENABLED = True    # Set to False if no GPS module
GAS_ENABLED = True    # Set to False if no gas sensor

# Hardware configuration
GPS_PORT = '/dev/ttyAMA0'  # Port for GPS module
GAS_PIN = 23               # GPIO pin for MQ-2 DO (Digital Output)

# Default location (Singapore) when GPS is unavailable
DEFAULT_LAT = 1.3521
DEFAULT_LON = 103.8198

# Camera settings
CAMERA_WIDTH = 640
CAMERA_HEIGHT = 480
CAMERA_FPS = 15  # Frames per second for waste detection

# Temporary directory for camera captures
TEMP_DIR = "/tmp/pi_captures"  # Directory for temporary camera captures

# Heartbeat configuration
HEARTBEAT_INTERVAL = 15  # seconds between heartbeats to dashboard
```

## Running the Waste Detection System

### Manual Start

Start the application manually:

```bash
python3 main.py
```

The application will:
1. Initialize all hardware components
2. Start the YOLO detection algorithm with GPU acceleration
3. Begin sending data to the dashboard and database
4. Start a web server for live video streaming on port 8000

### Automatic Start on Boot

To make the application start automatically when the Raspberry Pi boots:

1. Create a systemd service file:
   ```bash
   sudo nano /etc/systemd/system/waste-detection.service
   ```

2. Add the following content:
   ```
   [Unit]
   Description=Waste Detection Service
   After=network.target

   [Service]
   User=pi
   WorkingDirectory=/home/pi/waste-detection-system/new-pi
   ExecStart=/usr/bin/python3 /home/pi/waste-detection-system/new-pi/main.py
   Restart=always
   RestartSec=10

   [Install]
   WantedBy=multi-user.target
   ```

3. Enable and start the service:
   ```bash
   sudo systemctl enable waste-detection.service
   sudo systemctl start waste-detection.service
   ```

4. Check the status:
   ```bash
   sudo systemctl status waste-detection.service
   ```

## Module Overview

The edge device consists of the following modules:

1. **Camera Module** (`camera_module.py`)
   - Uses libcamera-vid for efficient video capture
   - Provides MJPEG streaming
   - Falls back to dummy frames if camera fails

2. **Detection Module** (`detection_module.py`)
   - Uses YOLO model with GPU acceleration
   - Optimized for Raspberry Pi 5
   - Falls back to CPU if GPU unavailable

3. **Communication Module** (`communication.py`)
   - Sends detection data to the dashboard
   - Sends detection data with images to the database
   - Maintains heartbeat with the dashboard

4. **Web Server Module** (`web_server.py`)
   - Serves live video feed on port 8000
   - Provides status endpoint for device discovery
   - Displays simple web interface for local monitoring

5. **GPS Module** (`gps_module.py`, optional)
   - Reads location data from NEO-6M GPS module
   - Provides latitude, longitude, and other positioning data
   - Falls back to default coordinates if GPS not available

6. **Gas Sensor Module** (`gas_sensor_module.py`, optional)
   - Monitors MQ-2 gas sensor for gas detection
   - Provides gas level readings
   - Triggers alerts when gas levels exceed threshold

## Local Web Interface

The edge device runs a web server that provides:

1. Live video feed: `http://<device-ip>:8000/video_feed`
2. Status information: `http://<device-ip>:8000/status`
3. Simple web interface: `http://<device-ip>:8000/`

You can access these from any browser on the same network.

## Logs

Logs are stored in the `logs` directory with timestamp-based filenames:
```
logs/pi_YYYYMMDD_HHMMSS.log
```

View logs with:
```bash
tail -f logs/pi_*.log
```

## Troubleshooting

If you encounter issues with the software components, check these common problems:

### Application Startup Issues
1. Verify Python dependencies are installed: `pip list`
2. Check logs for specific error messages: `cat logs/pi_*.log`
3. Test each module individually (see testing scripts in `test/` directory)
4. Verify configuration in `config.py` matches your network setup

### Network Communication Issues
1. Verify connectivity to dashboard: `ping <DASHBOARD_IP>`
2. Check firewall settings: `sudo iptables -L`
3. Verify correct IP addresses in `config.py`
4. Ensure the dashboard and database servers are running

### Camera and Detection Issues
1. Verify camera is working: `libcamera-still -o test.jpg`
2. Check GPU acceleration: `vcgencmd get_mem gpu`
3. Verify model file exists: `ls -l models/best_integer_quant.tflite`
4. Test detection on a sample image

**For hardware-specific troubleshooting**, see [HARDWARE.md](../HARDWARE.md).

## Power Management

For reliable 24/7 operation:
1. Use a stable power supply (minimum 3A)
2. Consider a UPS for uninterrupted operation
3. Monitor system temperature: `vcgencmd measure_temp`
4. Check GPU memory: `vcgencmd get_mem gpu`

## Security Considerations

1. Change default credentials (username, password)
2. Use a unique device ID for each Raspberry Pi
3. Consider using encrypted communications (TLS/SSL)
4. Restrict access to the web server with authentication
5. Keep system and packages updated