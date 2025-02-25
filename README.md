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
   - Ensure your Roboflow API key is valid

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
   - The dashboard listens on port 5001 for device connections

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
2. **Can't see video feed**: 
   - Verify the Pi's video server is running
   - Check if port 8000 on the Pi is accessible from your laptop

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
