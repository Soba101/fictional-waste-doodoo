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

The database consists of the following tables and views:

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
| image_data | MEDIUMBLOB | Binary image data (JPEG format) |
| image_format | VARCHAR(16) | Image format (jpg, png, etc.) |

### Materialized Views

#### `daily_detections`
Pre-calculated daily detection metrics for faster querying.

```sql
CREATE TABLE daily_detections (
    detection_date DATE PRIMARY KEY,
    detection_events INT,
    total_detections INT,
    avg_gas_value FLOAT,
    max_gas_value FLOAT,
    active_devices INT,
    INDEX idx_date (detection_date)
) ENGINE=InnoDB;

CREATE EVENT update_daily_detections
ON SCHEDULE EVERY 1 HOUR
DO
    INSERT INTO daily_detections
    SELECT 
        DATE(timestamp) AS detection_date,
        COUNT(DISTINCT detection_id) AS detection_events,
        SUM(num_detections) AS total_detections,
        AVG(gas_value) AS avg_gas_value,
        MAX(gas_value) AS max_gas_value,
        COUNT(DISTINCT device_id) AS active_devices
    FROM detections
    WHERE DATE(timestamp) >= DATE_SUB(CURDATE(), INTERVAL 90 DAY)
    GROUP BY DATE(timestamp)
    ON DUPLICATE KEY UPDATE
        detection_events = VALUES(detection_events),
        total_detections = VALUES(total_detections),
        avg_gas_value = VALUES(avg_gas_value),
        max_gas_value = VALUES(max_gas_value),
        active_devices = VALUES(active_devices);
```

#### `device_performance`
Pre-calculated device performance metrics.

```sql
CREATE TABLE device_performance (
    device_id VARCHAR(64) PRIMARY KEY,
    detection_events INT,
    total_detections INT,
    avg_gas_value FLOAT,
    active_days INT,
    last_active DATETIME,
    INDEX idx_last_active (last_active)
) ENGINE=InnoDB;

CREATE EVENT update_device_performance
ON SCHEDULE EVERY 1 HOUR
DO
    INSERT INTO device_performance
    SELECT 
        device_id,
        COUNT(DISTINCT detection_id) AS detection_events,
        SUM(num_detections) AS total_detections,
        AVG(gas_value) AS avg_gas_value,
        COUNT(DISTINCT DATE(timestamp)) AS active_days,
        MAX(timestamp) AS last_active
    FROM detections
    WHERE timestamp >= DATE_SUB(NOW(), INTERVAL 30 DAY)
    GROUP BY device_id
    ON DUPLICATE KEY UPDATE
        detection_events = VALUES(detection_events),
        total_detections = VALUES(total_detections),
        avg_gas_value = VALUES(avg_gas_value),
        active_days = VALUES(active_days),
        last_active = VALUES(last_active);
```

#### `waste_categories`
Pre-calculated waste category statistics.

```sql
CREATE TABLE waste_categories (
    class_name VARCHAR(32) PRIMARY KEY,
    total_count INT,
    avg_confidence FLOAT,
    last_updated DATETIME,
    INDEX idx_last_updated (last_updated)
) ENGINE=InnoDB;

CREATE EVENT update_waste_categories
ON SCHEDULE EVERY 1 HOUR
DO
    INSERT INTO waste_categories
    SELECT 
        di.class_name,
        COUNT(*) AS total_count,
        AVG(di.confidence) AS avg_confidence,
        NOW() AS last_updated
    FROM detections d
    JOIN detected_items di ON d.detection_id = di.detection_id
    WHERE d.timestamp >= DATE_SUB(NOW(), INTERVAL 30 DAY)
    GROUP BY di.class_name
    ON DUPLICATE KEY UPDATE
        total_count = VALUES(total_count),
        avg_confidence = VALUES(avg_confidence),
        last_updated = VALUES(last_updated);
```

## Setup Instructions

### Prerequisites
- MariaDB/MySQL server installed (version 10.5+ recommended)
- Root or administrative access to the database server
- Python 3.7+ with required packages (see requirements.txt)

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

### Performance Optimizations

For better performance, add the following indexes:

```sql
ALTER TABLE detections ADD INDEX idx_timestamp (timestamp);
ALTER TABLE detections ADD INDEX idx_device_id (device_id);
ALTER TABLE detected_items ADD INDEX idx_detection_id (detection_id);
ALTER TABLE detected_items ADD INDEX idx_class (class_name);
ALTER TABLE keyframes ADD INDEX idx_detection_id (detection_id);
```

## Database Receiver

The database receiver (`modified-db-receiver.py`) acts as a bridge between edge devices and the MariaDB database. It:

- Listens on port 5002 for incoming TCP connections
- Processes JSON data from edge devices
- Saves detection data, including JPEG images, to the database

### Running the Database Receiver

1. Ensure you have installed the required dependencies:
   ```bash
   pip install -r requirements.txt
   ```

2. Configure the database connection in `modified-db-receiver.py`:
   ```python
   # Database configuration
   DB_HOST = 'localhost'  # Change to your MariaDB server address if needed
   DB_USER = 'waste_user'   # Update if your username is different
   DB_PASSWORD = 'password' # Use your actual password
   DB_NAME = 'waste_detection'
   ```

3. Run the receiver:
   ```bash
   python3 modified-db-receiver.py
   ```

4. The receiver will create a log file in the `logs` directory.

### Expected JSON Format

The database receiver expects JSON data in the following format:

```json
{
  "device_id": "RaspberryPi5",
  "ip_address": "192.168.1.100",
  "timestamp": "2025-03-20T15:30:45.123456",
  "num_detections": 3,
  "gas_value": 120.5,
  "lat": 1.3521,
  "lon": 103.8198,
  "predictions": [
    {
      "class": "plastic",
      "confidence": 0.85,
      "x": 0.4,
      "y": 0.6,
      "width": 0.2,
      "height": 0.15
    },
    {
      "class": "paper",
      "confidence": 0.75,
      "x": 0.7,
      "y": 0.3,
      "width": 0.15,
      "height": 0.2
    }
  ],
  "frame": "base64_encoded_jpeg_image_data"
}
```

- The `frame` field is optional and contains a base64-encoded JPEG image
- Coordinates (x, y, width, height) are normalized to the range 0.0-1.0
- The receiver scales these to pixel coordinates assuming 640x480 images

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

For automated backups, create a cron job:

```bash
# Add to crontab (run 'crontab -e')
# Daily backup at 2:00 AM
0 2 * * * mysqldump -u waste_user -p'password' waste_detection > /path/to/backups/waste_detection_$(date +\%Y\%m\%d).sql
```

### Restore
To restore from a backup:

```bash
mysql -u waste_user -p waste_detection < waste_detection_backup_file.sql
```

### Database Maintenance

#### Optimizing Performance

1. Configure MariaDB for better performance with blob storage:
   ```
   # Add to /etc/mysql/mariadb.conf.d/50-server.cnf
   innodb_buffer_pool_size = 256M
   innodb_log_file_size = 64M
   max_allowed_packet = 64M
   ```

2. Regularly optimize tables:
   ```sql
   OPTIMIZE TABLE devices, detections, detected_items, keyframes;
   ```

## Troubleshooting

### Common Issues

1. **Connection refused**:
   - Verify MariaDB is running: `systemctl status mariadb`
   - Check bind-address in `/etc/mysql/mariadb.conf.d/50-server.cnf`
   - Ensure firewall allows connections to port 3306: `sudo ufw allow 3306/tcp`

2. **Access denied**:
   - Verify credentials in the application configuration
   - Check user permissions: `SHOW GRANTS FOR 'waste_user'@'%';`
   - Reset user password if necessary: 
     ```sql
     ALTER USER 'waste_user'@'%' IDENTIFIED BY 'new_password';
     FLUSH PRIVILEGES;
     ```

3. **Slow queries**:
   - Analyze slow queries: `SHOW PROCESSLIST;`
   - Check query execution plan: `EXPLAIN SELECT * FROM detections WHERE...;`
   - Add appropriate indexes
   - Consider optimizing large JOIN operations

4. **Database receiver not receiving data**:
   - Check that the receiver is running: `ps aux | grep modified-db-receiver.py`
   - Verify network connectivity: `telnet [db_server_ip] 5002`
   - Check log files in the `logs` directory
   - Restart the receiver: `python3 modified-db-receiver.py`

## Security Recommendations

1. Change the default password to a strong, unique password
2. Limit user privileges to only what's necessary
3. Restrict database access to specific IP addresses
4. Enable SSL for database connections
5. Encrypt sensitive data in the database
6. Implement regular security updates

## Additional Resources

- [MariaDB Documentation](https://mariadb.com/kb/en/documentation/)
- [PyMySQL Documentation](https://pymysql.readthedocs.io/)
- [SQLAlchemy Documentation](https://docs.sqlalchemy.org/)