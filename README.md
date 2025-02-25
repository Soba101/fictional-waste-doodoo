# Waste Detection System

This project consists of two main components:
1. A Raspberry Pi-based edge device for waste detection using computer vision
2. A central monitoring dashboard that aggregates data from multiple edge devices

## System Architecture

```
┌─────────────────┐         ┌─────────────────────┐
│  Raspberry Pi   │         │   Central Server    │
│  Edge Device    │◄────────┤   Dashboard         │
│  (waste detection)│        │   (data aggregation) │
└─────────────────┘         └─────────────────────┘
```

The system uses:
- Roboflow for computer vision-based waste detection
- Flask for the Pi's video streaming server
- Streamlit for the central dashboard UI
- TCP sockets for device-to-dashboard communication

## Raspberry Pi Edge Device

The edge device runs computer vision algorithms to detect waste items in camera feeds, then transmits the detection data to the central dashboard.

### Files
- `pi-wastedetect.py` - Main edge device application

### Setup Requirements

1. Hardware:
   - Raspberry Pi (3B+ or 4 recommended)
   - Camera module or USB webcam
   - (Optional) Gas sensor

2. Software Dependencies:
   ```
   pip install flask opencv-python roboflow inference
   ```

3. Configuration:
   - Update `DASHBOARD_IP` in `pi-wastedetect.py` to point to your laptop's IP address
     ```python
     # Line 20 in pi-wastedetect.py
     DASHBOARD_IP = "192.168.18.107"  # Change this to your dashboard computer's IP
     DASHBOARD_PORT = 5001  # Default port, change if needed
     ```
   - Set a unique `DEVICE_ID` for each Pi device
     ```python
     # Line 21 in pi-wastedetect.py
     DEVICE_ID = "RaspberryPi"  # Change to a unique name for each device
     ```
   - Ensure your Roboflow API key is valid
     ```python
     # Line 23 in pi-wastedetect.py
     ROBOFLOW_API_KEY = "NzQNgtFOFaIMRabyhRFM"  # Your Roboflow API key
     MODEL_ID = "yolo-waste-detection/1"  # Roboflow model
     ```

### Running the Edge Device

```bash
python pi-wastedetect.py
```

The Pi will:
- Start a Flask web server on port 8000
- Connect to Roboflow for waste detection
- Stream video feed with detected waste items highlighted
- Send detection data to the central dashboard
- Provide a status endpoint at `/status`

## Central Dashboard

The dashboard aggregates data from all connected edge devices, displays their locations, shows detection statistics, and allows viewing live video feeds.

### Files
- `main.py` - Entry point that loads configuration and starts the dashboard
- `dashboard_ui.py` - The Streamlit UI components and layout
- `data_receiver.py` - The `DataReceiver` class for handling device connections
- `state_manager.py` - Functions for managing session state and data processing
- `utils.py` - Utility functions (device discovery, status checking, etc.)
- `dashboard_uiv2-networking.py` - Alternative dashboard UI 
- `requirements.txt` - Required Python packages

### Setup Requirements

1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

2. Network Configuration:
   - Ensure the laptop and Pi are on the same network
   - The dashboard listens on port 5001 for device connections by default
   - The dashboard automatically binds to all network interfaces (0.0.0.0)
   - You can verify your laptop's IP address using:
     ```bash
     # On Windows
     ipconfig
     
     # On macOS/Linux
     ifconfig
     # or
     ip addr
     ```
   - The dashboard will display its IP addresses in the sidebar, which you should use to configure the Pi devices

### Running the Dashboard

```bash
streamlit run main.py
```

The dashboard will be available at `http://localhost:8501` by default.

## Features

### Edge Device (Pi)
- Real-time waste detection using computer vision
- Live video streaming with detection overlays
- Automatic reconnection to dashboard
- Status API endpoint
- Web UI at http://pi-ip:8000/

### Dashboard
- Real-time monitoring of waste detection from multiple devices
- Interactive map showing device locations and status
- Live video feeds from detection devices
- Historical data visualization
- Network device discovery
- System status monitoring
- Connection logging

## Network Configuration

### Connection Options

You can connect the Pi and dashboard computer in two main ways:

#### Option 1: Same Local Network
Connect both devices to the same WiFi or Ethernet network. This is the simplest option for multiple devices.

#### Option 2: Direct Ethernet Connection
You can directly connect the Pi to your laptop using an Ethernet cable. This creates a dedicated connection between the two devices:

1. Connect an Ethernet cable directly from the Pi to your laptop
2. Configure static IP addresses on both devices (described below)
3. No router or internet connection is required for this setup

### Finding Your IP Addresses

For the system to function properly, you need to correctly configure IP addresses:

1. **On the Dashboard Computer (Laptop):**
   
   The dashboard will display its IP addresses in the sidebar. Use one of these addresses to configure your Pi devices.
   
   If you need to manually find your IP:
   
   ```bash
   # Windows
   ipconfig
   
   # macOS/Linux
   ifconfig
   # or
   ip addr
   ```
   
   Look for the IP address on the same network as your Pi devices (usually starts with 192.168.x.x or 10.0.x.x)

2. **On the Raspberry Pi:**
   
   Update the `DASHBOARD_IP` variable in `pi-wastedetect.py`:
   
   ```python
   # Configuration
   DASHBOARD_IP = "192.168.18.107"  # Change to your laptop's IP address
   ```
   
   To find the Pi's IP address (useful for viewing the video feed):
   
   ```bash
   hostname -I
   ```

### Setting Up Direct Ethernet Connection

For a direct Ethernet connection between laptop and Pi (no router):

1. **On the Raspberry Pi:**
   
   Edit the network configuration:
   ```bash
   sudo nano /etc/dhcpcd.conf
   ```
   
   Add these lines at the end of the file:
   ```
   interface eth0
   static ip_address=192.168.4.2/24
   ```
   
   Then restart the networking service:
   ```bash
   sudo service dhcpcd restart
   ```

2. **On your laptop:**
   
   - **Windows:**
     - Open Network and Sharing Center
     - Click on the Ethernet connection
     - Click Properties
     - Select Internet Protocol Version 4 (TCP/IPv4)
     - Click Properties
     - Select "Use the following IP address"
     - Set IP address: 192.168.4.1
     - Set Subnet mask: 255.255.255.0
     - Leave default gateway empty
     - Click OK
   
   - **macOS:**
     - Open System Preferences > Network
     - Select Ethernet connection
     - Set Configure IPv4: Manually
     - Set IP Address: 192.168.4.1
     - Set Subnet Mask: 255.255.255.0
     - Leave Router field empty
     - Click Apply
   
   - **Linux:**
     ```bash
     sudo ip addr add 192.168.4.1/24 dev eth0
     ```

3. **Update `pi-wastedetect.py`:**
   
   Change the `DASHBOARD_IP` to match your laptop's static IP:
   ```python
   DASHBOARD_IP = "192.168.4.1"
   ```

4. **Test the connection:**
   
   On the laptop:
   ```bash
   ping 192.168.4.2
   ```
   
   On the Pi:
   ```bash
   ping 192.168.4.1
   ```

### Port Configuration

- The dashboard listens on **port 5001** for incoming device connections
- The Pi runs a web server on **port 8000** for the video feed
- The Streamlit dashboard interface runs on **port 8501** by default

If you need to change these ports:

1. For the dashboard receiver port:
   ```python
   # In data_receiver.py
   def __init__(self, host='0.0.0.0', port=5001):  # Change port here
   ```

2. For the Pi's video server port:
   ```python
   # In pi-wastedetect.py
   VIDEO_PORT = 8000  # Change port here
   ```

## Troubleshooting

### Edge Device Issues
1. **Camera not found**: Check if the camera is properly connected and if the correct camera index is used (default: 0)
2. **Cannot connect to dashboard**: Verify the `DASHBOARD_IP` is correct and the dashboard is running
3. **Roboflow errors**: Ensure your API key is valid and you have access to the specified model

### Dashboard Issues
1. **No devices showing up**: 
   - Check that your Pi is running and configured with the correct dashboard IP
   - Use the "Discover Devices" button in the sidebar
   - Check firewall settings to ensure port 5001 is open
   - Verify network connectivity between Pi and laptop with ping:
     ```bash
     # From Pi to laptop
     ping 192.168.x.x  # your laptop IP
     
     # From laptop to Pi
     ping 192.168.x.x  # your Pi IP
     ```
   - Check that both devices are on the same subnet (typically the first three numbers of the IP address should match)

2. **Can't see video feed**: 
   - Verify the Pi's video server is running
   - Check if port 8000 on the Pi is accessible from your laptop
   - Try accessing the Pi's web interface directly in a browser:
     ```
     http://PI_IP_ADDRESS:8000/
     ```
   - If using Windows, check Windows Defender Firewall settings for blocking
   - On Linux/macOS, check if any firewall is blocking with:
     ```bash
     sudo iptables -L
     ```

3. **IP address configuration errors**:
   - The dashboard shows its detected IP addresses in the sidebar
   - If your network uses multiple adapters, ensure you're using the correct IP from the same network as the Pi
   - If using a VPN, try disconnecting as it can interfere with local network discovery
   - For testing on the same machine, you can use `127.0.0.1` as the `DASHBOARD_IP` in Pi code

4. **Direct Ethernet connection issues**:
   - If using a direct Ethernet connection, make sure both IP addresses are on the same subnet (e.g., 192.168.4.x)
   - Some laptops may disable the Ethernet port when no DHCP server is detected - you'll need to manually set a static IP
   - Check if the Ethernet interface is actually up with:
     ```bash
     # On Pi
     ifconfig eth0
     
     # On Linux/macOS
     ifconfig eth0
     
     # On Windows
     ipconfig
     ```
   - Try restarting the network interface on the Pi:
     ```bash
     sudo ifdown eth0 && sudo ifup eth0
     ```
   - Make sure you're not using the same IP address on both devices
   - If the direct connection works but the software doesn't detect devices, try manually adding the IP in the dashboard sidebar

## Development and Extension

### Adding New Edge Devices
1. Clone the Pi setup to a new device
2. Update the `DEVICE_ID` in `pi-wastedetect.py`
3. The dashboard will automatically detect and add the new device

### Customizing the Dashboard
- Modify `dashboard_ui.py` to change the layout or add new visualizations
- Update `state_manager.py` to process additional data from edge devices

## License

MIT
