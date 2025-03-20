# Raspberry Pi Waste Detection Edge Device

This document provides setup and configuration instructions for the Raspberry Pi-based edge devices in the Waste Detection System.

## Overview

The Raspberry Pi edge device serves as the detection and sensing component of the waste detection system, with the following capabilities:

1. Waste detection using computer vision
2. Live video streaming to the dashboard
3. GPS location tracking (optional)
4. Gas detection with MQ-2 sensor (optional)
5. Communication with the central dashboard and database

## Hardware Requirements

### Required Components
- Raspberry Pi 4 or 5
- Raspberry Pi Camera Module (v2 or v3)
- MicroSD Card (minimum 16GB, Class 10 recommended)
- Power supply (3A recommended for Pi 4/5)
- Network connectivity (WiFi or Ethernet)

### Optional Components
- NEO-6M GPS module
- MQ-2 Gas Sensor
- Weatherproof case for outdoor deployment

## Software Prerequisites

- Raspberry Pi OS (Bullseye or newer, 64-bit recommended)
- Python 3.7+
- Required Python packages (see `requirements.txt`)

## Installation

### 1. Set Up Raspberry Pi OS

1. Install Raspberry Pi OS using the Raspberry Pi Imager
2. Enable SSH and camera interface:
   ```bash
   sudo raspi-config
   ```
   Navigate to "Interface Options" and enable:
   - Camera
   - SSH
   - I2C (if using additional sensors)
   - Serial (for GPS module)

3. Update the system:
   ```bash
   sudo apt update
   sudo apt upgrade -y
   ```

### 2. Install Required Dependencies

```bash
# Install system dependencies
sudo apt install -y python3-opencv python3-picamera2 python3-gpiozero python3-lgpio python3-serial

# Clone the repository
git clone https://github.com/your-username/waste-detection-system.git
cd waste-detection-system/new-pi

# Create virtual environment (optional but recommended)
python3 -m venv venv
source venv/bin/activate

# Install Python dependencies
pip install -r requirements.txt
```

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

# Enable or disable hardware components
GPS_ENABLED = True    # Set to False if no GPS module
GAS_ENABLED = True    # Set to False if no gas sensor
```

### 4. Hardware Connections

#### Camera Module
Connect the camera module to the Raspberry Pi's camera port.

#### GPS Module (Optional)
Connect the NEO-6M GPS module:
- VCC to 3.3V or 5V (check your module's specification)
- GND to Ground
- TX to GPIO15 (RX pin)
- RX to GPIO14 (TX pin)

#### MQ-2 Gas Sensor (Optional)
Connect the MQ-2 gas sensor:
- VCC to 5V
- GND to Ground
- DO (Digital Output) to GPIO17 (configurable in `config.py`)
- AO (Analog Output) not used in this setup (digital only)

## Running the Waste Detection System

### Manual Start

Start the application manually:

```bash
python3 main.py
```

The application will:
1. Initialize all hardware components
2. Start the detection algorithm
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
   - Handles camera initialization and frame capture
   - Provides frames to the detection module
   - Falls back to a test pattern if camera fails

2. **Detection Module** (`detection_module.py`)
   - Implements waste detection algorithm
   - Classifies detected items (plastic, paper, glass)
   - Provides confidence scores and bounding boxes

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

### Camera Issues
1. Check camera connection
2. Verify camera is enabled: `sudo raspi-config`
3. Test camera with: `libcamera-still -o test.jpg`
4. Check camera module output in logs

### Network Connectivity
1. Verify IP configuration with: `ip addr show`
2. Test connection to dashboard: `ping <DASHBOARD_IP>`
3. Test connection to database: `ping <DATABASE_IP>`
4. Check firewall settings: `sudo iptables -L`

### GPS Module
1. Check serial connection: `ls -l /dev/ttyAMA0`
2. Disable serial console if needed: `sudo raspi-config`
3. Test GPS module with: `cat /dev/ttyAMA0`
4. Ensure GPS has a clear view of the sky

### Gas Sensor
1. Check GPIO connections
2. Verify GPIO pin in config.py matches wiring
3. Test GPIO connectivity: `gpiotest`
4. Adjust the sensor potentiometer to calibrate sensitivity

## Maintenance

### Software Updates
```bash
# Update code from repository
cd waste-detection-system
git pull

# Update Python dependencies
pip install -r requirements.txt
```

### System Monitoring
Check system health with:
```bash
# CPU temperature
vcgencmd measure_temp

# CPU and memory usage
htop

# Disk usage
df -h
```

### Power Management
For reliable 24/7 operation:
1. Use a stable power supply (minimum 3A)
2. Consider a UPS for uninterrupted operation
3. Enable watchdog timer for automatic recovery:
   ```bash
   sudo nano /boot/config.txt
   # Add line: dtparam=watchdog=on
   sudo reboot
   ```

## Energy Efficiency

For battery-powered or solar deployments:
1. Reduce frame rate: Set `CAMERA_FPS` to a lower value in `config.py`
2. Disable optional components: Set `GPS_ENABLED = False` and/or `GAS_ENABLED = False`
3. Reduce heartbeat frequency: Increase `HEARTBEAT_INTERVAL` in `config.py`
4. Consider power-saving schedulers like `cron` to only run during specific times

## Customization

### Detection Tuning
Adjust detection parameters in `detection_module.py`:
- Modify color thresholds for different lighting conditions
- Adjust minimum area for detection (default: 1000)
- Change confidence calculation for different sensitivity

### Adding New Sensors
The modular design allows adding new sensors:
1. Create a new module file (e.g., `humidity_sensor_module.py`)
2. Implement the sensor interface with `start()`, `stop()`, and data retrieval methods
3. Initialize in `main.py`
4. Update the communication module to include new sensor data

## Security Considerations

1. Change default credentials (username, password)
2. Use a unique device ID for each Raspberry Pi
3. Consider using encrypted communications (TLS/SSL)
4. Restrict access to the web server with authentication
5. Keep system and packages updated