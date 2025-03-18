# Waste Detection System

A distributed system for detecting, monitoring, and analyzing waste using computer vision and IoT technologies.

## System Overview

The Waste Detection System is an integrated solution that uses edge devices with cameras to detect waste items, stores detection data in a central database, and provides real-time monitoring through an interactive dashboard.

![System Architecture Diagram](docs/system-architecture.png)

## Key Components

The system consists of three main components, each in their own directory:

1. **Edge Devices (`/pi`)** - Raspberry Pi cameras that capture and analyze waste
2. **Database (`/waste-db`)** - Central database for persistent storage of detection data
3. **Dashboard (`/waste-dashboard`)** - Real-time monitoring interface for visualization

## Repository Structure

```
waste-detection-system/
├── README.md                 # This main README file
├── docs/                     # Documentation and diagrams
│   └── system-architecture.png
│
├── pi/                       # Edge device code
│   ├── README.md             # Pi-specific documentation
│   ├── pi-capture-detect.py  # Main detection script
│   └── requirements.txt      # Pi dependencies
│
├── waste-db/                 # Database component
│   ├── README.md             # Database documentation
│   ├── schema.sql            # Database schema
│   └── modified-db-receiver.py # Database receiver script
│
└── waste-dashboard/          # Dashboard application
    ├── README.md             # Dashboard documentation
    ├── main.py               # Dashboard entry point
    ├── dashboard_ui.py       # Dashboard UI components
    ├── data_receiver.py      # Data receiver for dashboard
    ├── state_manager.py      # State management
    ├── utils.py              # Utility functions
    └── requirements.txt      # Dashboard dependencies
```

## System Architecture

### Data Flow

1. **Capture & Detection**:
   - Edge devices (Raspberry Pi) capture images using camera modules
   - On-device processing detects waste items using computer vision
   - Detection results include waste type, location, and confidence scores

2. **Data Transmission**:
   - Edge devices send detection data to both the dashboard (for real-time display) and database (for storage)
   - Detection data is transmitted via TCP sockets in JSON format
   - Image data for detections is base64-encoded and sent to the database

3. **Visualization & Analytics**:
   - Dashboard displays real-time device status and detection data
   - Historical data is retrieved from the database for trend analysis
   - Live video feeds can be viewed directly from edge devices

4. **Storage & Persistence**:
   - MariaDB database stores all detection data, device information, and detection images
   - Data is organized for efficient querying and historical analysis

### Communication Protocols

| Connection | Protocol | Port | Data Format |
|------------|----------|------|------------|
| Edge Device → Dashboard | TCP Socket | 5001 | JSON |
| Edge Device → Database | TCP Socket | 5002 | JSON + base64 images |
| Dashboard → Database | SQL | 3306 | SQL queries |
| User → Edge Device | HTTP | 8000 | HTML/MJPEG |
| User → Dashboard | HTTP | 8501 | HTML/Streamlit |

### Network Requirements

- All components must be on the same network or have appropriate routing
- Firewall rules must allow the specified ports
- Edge devices require stable network connections
- The dashboard server should have a static IP for edge devices to connect reliably

## Component Details

### Edge Devices (Raspberry Pi)

Each Raspberry Pi runs detection software that:
- Captures images using the Pi Camera Module
- Performs waste detection using color-based computer vision
- Provides a web interface for viewing the live feed
- Transmits detection data to the central system

**Key Files:**
- `pi-capture-detect.py` - The main detection script

See the [Pi README](/pi/README.md) for detailed setup and configuration instructions.

### Database

The MariaDB database is the central storage component that:
- Receives and stores detection data from edge devices
- Saves detection images for verification and analysis
- Provides historical data for dashboard visualization
- Tracks device status and network information

**Key Files:**
- `modified-db-receiver.py` - Receives data from edge devices
- `schema.sql` - Database schema definition

See the [Database README](/waste-db/README.md) for detailed setup and configuration instructions.

### Dashboard

The Streamlit dashboard is the user interface that:
- Displays real-time detection information
- Shows device locations on an interactive map
- Provides access to live video feeds
- Visualizes historical data and trends
- Monitors system health and connectivity

**Key Files:**
- `main.py` - Dashboard entry point
- `dashboard_ui.py` - UI components and layout
- `data_receiver.py` - Receives data from edge devices

See the [Dashboard README](/waste-dashboard/README.md) for detailed setup and configuration instructions.

## Installation

Each component has its own installation instructions in its respective README file. For a complete system setup, follow these steps:

1. Set up the database server first
2. Set up the dashboard server
3. Configure and deploy edge devices

## Initial Setup

### 1. Database Setup

```bash
cd waste-db
# Follow instructions in the database README
```

### 2. Dashboard Setup

```bash
cd waste-dashboard
# Follow instructions in the dashboard README
```

### 3. Edge Device Setup

```bash
cd pi
# Follow instructions in the Pi README
```

## Configuration

Each component needs to be configured to communicate with the others:

1. **Edge Devices** must be configured with:
   - Dashboard server IP address and port
   - Database server IP address and port
   - Unique device identifier

2. **Database Receiver** must be configured with:
   - Database connection details
   - Listening port for data from edge devices

3. **Dashboard** must be configured with:
   - Database connection details
   - Listening port for data from edge devices

See each component's README for specific configuration instructions.

## Deployment Scenarios

### Small-Scale Deployment

For monitoring a small area with 1-3 edge devices:
- Run the database and dashboard on the same server
- Deploy Raspberry Pi devices at key monitoring points
- Use standard WiFi for connectivity

### Medium-Scale Deployment

For monitoring multiple areas with 5-10 edge devices:
- Run the database and dashboard on separate servers
- Use wired connections for critical edge devices
- Consider database optimization for increased data volume

### Large-Scale Deployment

For monitoring large areas with 10+ edge devices:
- Implement load balancing for the dashboard
- Use database clustering for high availability
- Consider edge device redundancy at critical points
- Implement message queuing for more robust data transmission
- Set up monitoring for system health

## Troubleshooting

### System-Wide Issues

1. **Communication Failures**:
   - Verify network connectivity between all components
   - Check IP addresses and port configurations
   - Ensure firewalls allow required connections

2. **Data Inconsistencies**:
   - Check timestamps across different system components
   - Verify data transmission from edge devices to both dashboard and database

3. **Performance Issues**:
   - Monitor resource usage on all components
   - Consider scaling up hardware for bottlenecked components
   - Optimize database queries and indexes

See each component's README for component-specific troubleshooting.

## System Maintenance

### Regular Maintenance Tasks

1. **Database Backup**:
   ```bash
   # Backup the database (from waste-db directory)
   ./backup-database.sh
   ```

2. **Log Rotation**:
   - All components use dated log files
   - Set up log rotation to prevent disk space issues:
   ```bash
   sudo logrotate -f /etc/logrotate.d/waste-detection
   ```

3. **Updates**:
   - Keep all components and dependencies updated
   - Test updates in staging environment before production

### Scaling and Expansion

To add more edge devices:
1. Set up new Raspberry Pi hardware
2. Install the edge device software
3. Configure with unique device IDs
4. Update dashboard map coordinates if needed

## Security Considerations

1. **Authentication**: Implement proper authentication for all user interfaces
2. **Encryption**: Use SSL/TLS for all communications
3. **Access Control**: Limit network access to required ports and services
4. **Secure Passwords**: Use strong passwords for database and system accounts
5. **Updates**: Keep all components updated with security patches

## Future Enhancements

Potential improvements to the system:

1. **Advanced Detection**:
   - Implement machine learning models for more accurate waste classification
   - Add object tracking for moving waste items

2. **System Integration**:
   - Integration with waste collection scheduling systems
   - Alerting and notification systems for critical detections

3. **Analytics Expansion**:
   - Predictive analytics for waste hotspots
   - Seasonal trend analysis

4. **Hardware Enhancements**:
   - Support for additional sensors (pollution, sound, etc.)
   - Integration with autonomous collection vehicles

## Contributing

Contributions to the Waste Detection System are welcome. Please follow these steps:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add some amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## License
MIT

