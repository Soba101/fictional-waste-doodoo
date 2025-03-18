# MariaDB Setup for Waste Detection System

This document provides information about the MariaDB database setup used in the Waste Detection Dashboard system.

## Database Overview

The database serves as the persistent storage layer for the waste detection system, storing information about:
- Edge devices running detection software
- Detection events and their metadata
- Individual waste items detected
- Keyframe images of detections

## Connection Details

- **Host**: localhost (default) or 192.168.18.113 (configured in the dashboard)
- **Port**: 3306 (default MariaDB port)
- **Database Name**: waste_detection
- **Username**: waste_user
- **Password**: password (change this in production environments)
- **Connection String**: `mysql+pymysql://waste_user:password@192.168.18.113/waste_detection`

## Database Schema

The database consists of the following tables:

### `devices`
Stores information about edge devices sending detection data.

| Column | Type | Description |
|--------|------|-------------|
| device_id | VARCHAR(64) | Primary key - unique identifier for the device |
| ip_address | VARCHAR(15) | Device's IP address |
| location_lat | FLOAT | Latitude of device's location |
| location_lon | FLOAT | Longitude of device's location |
| last_active | DATETIME | Timestamp of last activity from this device |

### `detections`
Stores information about detection events.

| Column | Type | Description |
|--------|------|-------------|
| detection_id | INT | Primary key - unique identifier for the detection event |
| device_id | VARCHAR(64) | Foreign key reference to devices table |
| timestamp | DATETIME | When the detection occurred |
| num_detections | INT | Number of waste items detected |
| gas_value | FLOAT | Gas sensor reading (if applicable) |

### `detected_items`
Stores information about individual items detected within a detection event.

| Column | Type | Description |
|--------|------|-------------|
| item_id | INT | Primary key - unique identifier for the detected item |
| detection_id | INT | Foreign key reference to detections table |
| class_name | VARCHAR(32) | Type of waste detected (plastic, paper, glass, etc.) |
| confidence | FLOAT | Detection confidence (0.0-1.0) |
| x_coord | FLOAT | X coordinate of item center in the image |
| y_coord | FLOAT | Y coordinate of item center in the image |
| width | FLOAT | Width of the bounding box |
| height | FLOAT | Height of the bounding box |

### `keyframes`
Stores image data for detections.

| Column | Type | Description |
|--------|------|-------------|
| keyframe_id | INT | Primary key - unique identifier for the keyframe |
| detection_id | INT | Foreign key reference to detections table |
| image_data | BLOB | Binary image data |
| image_format | VARCHAR(16) | Image format (jpg, png, etc.) |

## Setup Instructions

### Prerequisites
- MariaDB/MySQL server installed
- Root or administrative access to the database server

### Database Creation

1. Connect to MariaDB as root:
   ```
   mysql -u root -p
   ```

2. Create the database:
   ```sql
   CREATE DATABASE waste_detection;
   ```

3. Create a dedicated user:
   ```sql
   CREATE USER 'waste_user'@'%' IDENTIFIED BY 'password';
   GRANT ALL PRIVILEGES ON waste_detection.* TO 'waste_user'@'%';
   FLUSH PRIVILEGES;
   ```
   Note: The `'%'` allows connections from any host. For production, limit this to specific hosts.

4. Create the database schema:
   ```sql
   USE waste_detection;

   CREATE TABLE devices (
     device_id VARCHAR(64) PRIMARY KEY,
     ip_address VARCHAR(15),
     location_lat FLOAT,
     location_lon FLOAT,
     last_active DATETIME
   );

   CREATE TABLE detections (
     detection_id INT AUTO_INCREMENT PRIMARY KEY,
     device_id VARCHAR(64),
     timestamp DATETIME,
     num_detections INT,
     gas_value FLOAT,
     FOREIGN KEY (device_id) REFERENCES devices(device_id)
   );

   CREATE TABLE detected_items (
     item_id INT AUTO_INCREMENT PRIMARY KEY,
     detection_id INT,
     class_name VARCHAR(32),
     confidence FLOAT,
     x_coord FLOAT,
     y_coord FLOAT,
     width FLOAT,
     height FLOAT,
     FOREIGN KEY (detection_id) REFERENCES detections(detection_id)
   );

   CREATE TABLE keyframes (
     keyframe_id INT AUTO_INCREMENT PRIMARY KEY,
     detection_id INT,
     image_data MEDIUMBLOB,
     image_format VARCHAR(16),
     FOREIGN KEY (detection_id) REFERENCES detections(detection_id)
   );
   ```

## Connectivity

### From Python Applications
The dashboard and database receiver connect to the database using PyMySQL:

```python
import pymysql

# Database connection details
DB_HOST = "your_db_ip"
DB_USER = "waste_user"
DB_PASSWORD = "password"
DB_NAME = "waste_detection"

# Create connection
connection = pymysql.connect(
    host=DB_HOST,
    user=DB_USER,
    password=DB_PASSWORD,
    database=DB_NAME,
    charset='utf8mb4'
)
```

For SQLAlchemy-based connections (used in the dashboard):

```python
from sqlalchemy import create_engine

# Database connection string
DB_URI = f"mysql+pymysql://waste_user:password@192.168.18.113/waste_detection"
engine = create_engine(DB_URI)
```

### Data Flow

1. Edge devices (Raspberry Pi) capture waste detection data
2. Data is sent to the database receiver on port 5002
3. The database receiver processes and saves data in the MariaDB database
4. The dashboard queries the database to display detection data

## Backup and Maintenance

### Backup
To back up the database:

```bash
mysqldump -u waste_user -p waste_detection > waste_detection_backup_$(date +%Y%m%d).sql
```

### Restore
To restore from a backup:

```bash
mysql -u waste_user -p waste_detection < waste_detection_backup_file.sql
```

### Optimizing Performance
For better performance:

1. Add indexes on frequently queried columns:
   ```sql
   ALTER TABLE detections ADD INDEX idx_timestamp (timestamp);
   ALTER TABLE detections ADD INDEX idx_device_id (device_id);
   ALTER TABLE detected_items ADD INDEX idx_class (class_name);
   ```

2. Configure MariaDB for better performance with blob storage if storing many images:
   ```
   innodb_buffer_pool_size = 256M
   innodb_log_file_size = 64M
   ```

## Troubleshooting

### Common Issues

1. **Connection refused**:
   - Verify MariaDB is running: `systemctl status mariadb`
   - Check bind-address in `/etc/mysql/mariadb.conf.d/50-server.cnf`
   - Ensure firewall allows connections to port 3306

2. **Access denied**:
   - Verify credentials in the application configuration
   - Check user permissions: `SHOW GRANTS FOR 'waste_user'@'%';`

3. **Slow queries**:
   - Analyze slow queries: `SHOW PROCESSLIST;`
   - Add appropriate indexes
   - Consider optimizing large JOIN operations

## Security Recommendations

1. Change the default password to a strong, unique password
2. Limit user privileges to only what's necessary
3. Restrict database access to specific IP addresses
4. Enable SSL for database connections
5. Regularly update MariaDB to the latest version
6. Consider encrypting sensitive data in the database

## Database Receiver

The `modified-db-receiver.py` script acts as a bridge between the edge devices and the database. It:
- Listens on port 5002 for incoming TCP connections
- Processes JSON data from edge devices
- Saves detection data, including images, to the MariaDB database

To run the database receiver:
```bash
python3 modified-db-receiver.py
```

## Dashboard Database Access

The dashboard application (`dashboard_ui.py`) connects to the database to:
- Fetch detection counts for visualization
- Retrieve detection details for display
- Generate reports on waste types detected
- Access keyframe images for visual confirmation

## Additional Resources

- [MariaDB Documentation](https://mariadb.com/kb/en/documentation/)
- [PyMySQL Documentation](https://pymysql.readthedocs.io/)
- [SQLAlchemy Documentation](https://docs.sqlalchemy.org/)
