# Raspberry Pi Waste Detection Camera

This document provides instructions and information for setting up and running the Pi Waste Detection Camera system, which captures images, performs waste detection, and transmits data to the central dashboard and database servers.

## Overview

The Pi Waste Detection Camera is an edge device component of the Waste Detection System that:

1. Captures images using the Raspberry Pi camera module
2. Performs real-time waste detection using computer vision
3. Streams live video feed via a web interface
4. Transmits detection data to the central dashboard
5. Sends detection data and images to the database server

## Hardware Requirements

- Raspberry Pi (3 or 4 recommended)
- Raspberry Pi Camera Module
- (Optional) Gas sensor for additional environmental monitoring
- Power supply
- Network connectivity (Ethernet or WiFi)

## Software Dependencies

- Python 3.6+
- Flask
- OpenCV
- NumPy
- Requests
- libcamera-tools (for Raspberry Pi OS Bullseye and newer)

## Installation

### 1. Setup Raspberry Pi OS

Ensure your Raspberry Pi is running the latest Raspberry Pi OS (Bullseye or newer recommended).

### 2. Enable Camera

```bash
sudo raspi-config
```
Navigate to "Interface Options" > "Camera" and enable the camera.

### 3. Install Dependencies

```bash
# Update system packages
sudo apt update
sudo apt upgrade -y

# Install required packages
sudo apt install -y python3-pip python3-opencv libopencv-dev python3-picamera2 libcamera-apps

# Install Python libraries
pip3 install flask numpy requests
```

### 4. Download the Script

Create a directory for the project:

```bash
mkdir -p ~/waste-detection
cd ~/waste-detection
```

Copy the `pi-capture-detect.py` script to this directory.

### 5. Create Log Directory

```bash
mkdir -p logs
```

## Configuration

Before running the script, edit the following parameters in `pi-capture-detect.py`:

```python
# Configuration
DASHBOARD_IP = "192.168.18.107"  # Change to your dashboard IP
DASHBOARD_PORT = 5001
DATABASE_IP = "192.168.18.113"  # Change to your database IP
DATABASE_PORT = 5002
DEVICE_ID = "RaspberryPi"  # Set a unique device ID
VIDEO_PORT = 8000  # Web server port for video streaming
```

Update these values to match your network configuration:
- `DASHBOARD_IP`: The IP address of the server running the waste detection dashboard
- `DATABASE_IP`: The IP address of the server running the database receiver
- `DEVICE_ID`: A unique identifier for this Pi camera (especially important if you have multiple cameras)

## Running the Application

### Start the Detection Script

```bash
cd ~/waste-detection
python3 pi-capture-detect.py
```

### Run as a Service (recommended)

For reliable operation, set up the script to run as a system service:

1. Create a service file:

```bash
sudo nano /etc/systemd/system/waste-detection.service
```

2. Add the following content:

```
[Unit]
Description=Waste Detection Camera Service
After=network.target

[Service]
User=pi
WorkingDirectory=/home/pi/waste-detection
ExecStart=/usr/bin/python3 /home/pi/waste-detection/pi-capture-detect.py
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

4. Check status:

```bash
sudo systemctl status waste-detection.service
```

## Web Interface

The Raspberry Pi hosts a web interface that displays:
- Live video feed with detection overlays
- Connection status
- Detection statistics

Access the web interface by entering the Raspberry Pi's IP address and port in a web browser:

```
http://[PI_IP_ADDRESS]:8000
```

## Status API

The Pi exposes a status API endpoint that provides information about its operation:

```
http://[PI_IP_ADDRESS]:8000/status
```

This returns a JSON object with:
- Device ID
- Uptime
- Connection statistics
- Network information

## How It Works

### Image Capture

The system uses `libcamera-still` to capture images from the Raspberry Pi Camera Module. For systems without a camera, it falls back to a test pattern generator.

### Waste Detection

The waste detection uses a simple color-based algorithm:
- Converts image to HSV color space
- Applies color thresholds to identify potential waste items:
  - Blue range for plastic items
  - Green range for glass items
  - Brown/yellow range for paper/cardboard
- Applies size filtering to reduce false positives
- Calculates confidence based on area and color match

### Data Transmission

1. **Dashboard Communication**:
   - Sends detection data to the central dashboard via TCP socket
   - Includes device ID, timestamp, coordinates, and detection results
   - Sends periodic heartbeats to maintain connection status

2. **Database Communication**:
   - Sends detection data and captured images to the database server
   - Images are encoded as base64 strings for transmission
   - Additional metadata like coordinates and gas sensor readings are included

### Video Streaming

- Implements MJPEG streaming using Flask
- Overlays detection information on video frames
- Displays device ID and timestamp

## Detection Classes

The system can detect the following waste types:
- **Plastic**: Identified by blue color ranges
- **Glass**: Identified by green color ranges
- **Paper**: Identified by brown/yellow color ranges

## Troubleshooting

### Camera Not Working

1. Check if the camera is enabled:
   ```bash
   vcgencmd get_camera
   ```
   Should return `supported=1 detected=1`

2. Try restarting the camera service:
   ```bash
   sudo systemctl restart waste-detection.service
   ```

3. Check the logs:
   ```bash
   cat logs/pi_*.log | tail -100
   ```

### Connection Issues

1. Verify the dashboard and database IPs are correct in the configuration

2. Check network connectivity:
   ```bash
   ping 192.168.18.107  # Dashboard IP
   ping 192.168.18.113  # Database IP
   ```

3. Verify ports are open:
   ```bash
   nc -zv 192.168.18.107 5001
   nc -zv 192.168.18.113 5002
   ```

4. Check firewall settings:
   ```bash
   sudo iptables -L
   ```

### Web Interface Not Accessible

1. Check if the Flask web server is running:
   ```bash
   ps aux | grep pi-capture-detect
   ```

2. Verify the port is open:
   ```bash
   sudo netstat -tulpn | grep 8000
   ```

## Performance Optimization

For better performance on Raspberry Pi:

1. Reduce resolution in the capture configuration (currently set to 640x480)
2. Decrease the framerate (currently captures at approximately 2 FPS)
3. Consider overclocking your Raspberry Pi (for advanced users)
4. Add a heatsink or fan to prevent thermal throttling

## Connection Activity and Logs

Logs are stored in the `logs` directory with timestamp-based filenames:
```
logs/pi_YYYYMMDD_HHMMSS.log
```

View logs with:
```bash
tail -f logs/pi_*.log
```

## Security Considerations

1. Change default passwords on your Raspberry Pi
2. Consider using encrypted communication (HTTPS/SSL)
3. Restrict network access to the video stream if deployed in public areas
4. Update your Raspberry Pi OS and dependencies regularly

## Future Improvements

Potential enhancements for the system:

1. Implement more sophisticated detection algorithms (e.g., TensorFlow Lite models)
2. Add authentication to the web interface
3. Implement encrypted communication for data transmission
4. Add support for multiple camera modules
5. Integrate additional environmental sensors (temperature, humidity, etc.)

## License and Credits

This software is part of the Waste Detection System.

## Support

For issues or questions, check the logs first, then consult the main project documentation.
