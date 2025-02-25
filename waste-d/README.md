# Waste Detection Dashboard

A Streamlit dashboard for monitoring waste detection from edge devices.

## Project Structure

The project has been organized into multiple modules:

- `main.py` - Entry point that loads configuration and starts the dashboard
- `data_receiver.py` - The `DataReceiver` class and related functionality
- `dashboard_ui.py` - The Streamlit UI components and layout
- `utils.py` - Utility functions (device discovery, status checking, etc.)
- `state_manager.py` - Functions for managing session state and data processing

## Setup and Running

### Prerequisites

- Python 3.7+
- Required libraries (install with `pip install -r requirements.txt`):
  - streamlit
  - pandas
  - numpy
  - folium
  - streamlit-folium
  - altair
  - requests

### Starting the Dashboard

```bash
cd waste-d
streamlit run main.py
```

The dashboard will be available at `http://localhost:8501` by default.

## Features

- Real-time monitoring of waste detection devices
- Interactive map showing device locations and status
- Live video feed from detection devices
- Historical data visualization
- Network device discovery
- System status monitoring

## Configuration

The dashboard is configured to:
- Listen on all interfaces (0.0.0.0) on port 5001 for device connections
- Automatically discover devices on the local network
- Save logs to the `logs/` directory

## Edge Device Integration

Edge devices should:
1. Connect to the dashboard's IP address on port 5001
2. Send JSON-formatted data with:
   - `device_id`: Unique identifier for the device
   - `timestamp`: ISO-formatted timestamp
   - `predictions`: Array of detection results
   - `lat`/`lon`: Device location (optional)
   - `gas_value`: Gas sensor reading (optional)

## License

MIT
