# Hardware Setup Guide

This document provides detailed hardware setup instructions for the Raspberry Pi 5 edge devices used in the Waste Detection System.

## Components Required

### Required Hardware
- Raspberry Pi 5 (2GB RAM or better recommended)
- Raspberry Pi Camera Module (v2 or v3)
- MicroSD Card (minimum 16GB, Class 10 recommended)
- Power Supply (USB-C, 5V/3A minimum)
- Network connection (WiFi or Ethernet)

### Optional Sensors
- NEO-6M GPS Module
- MQ-2 Gas Sensor (with DO digital output pin)
- Jumper wires (female-to-female and male-to-female)
- Breadboard (for prototyping)

## Raspberry Pi 5 GPIO Layout

The Raspberry Pi 5 has 40 GPIO pins that provide power, ground, and programmable input/output. The following diagram shows the pin layout:

![Raspberry Pi 5 GPIO Pinout](/docs/Raspberry-Pi-5-Pinout.jpg)

## Wiring Connections

### Camera Module Connection
Connect the Camera Module to the dedicated camera port on the Raspberry Pi. Be sure to:
1. Ensure the Raspberry Pi is powered off
2. Gently pull up the black clip on the camera port
3. Insert the camera ribbon cable with the blue side facing the Ethernet port
4. Press down the black clip to secure the connection

### GPS Module (NEO-6M) Connection
The NEO-6M GPS module communicates with the Raspberry Pi via UART:

| NEO-6M Pin | Raspberry Pi Pin | Description |
|------------|-----------------|-------------|
| VCC        | Pin 4 (5V)      | Power supply |
| GND        | Pin 6 (Ground)  | Ground |
| TXD        | Pin 10 (GPIO 15/RXD) | GPS TX → Pi RX |
| RXD        | Pin 8 (GPIO 14/TXD)  | GPS RX → Pi TX |

Note: The connections may seem reversed (TX→RX, RX→TX) because it's a crossover connection—the transmitter of one device connects to the receiver of the other.

### MQ-2 Gas Sensor Connection
The MQ-2 Gas Sensor typically has 4 pins (VCC, GND, AO, DO):

| MQ-2 Pin | Raspberry Pi Pin | Description |
|----------|-----------------|-------------|
| VCC      | Pin 2 (5V)      | Power supply |
| GND      | Any Ground pin (e.g., Pin 39) | Ground |
| DO       | Pin 11 (GPIO 17) | Digital output (gas detection) |
| AO       | Not connected   | Analog output (not used) |

Note: The Raspberry Pi doesn't have analog inputs, so we're only using the digital output pin (DO) of the gas sensor. The sensor has a potentiometer that you can adjust to set the threshold for gas detection.

## Hardware Diagram

```
                         +-------------------+
                         |   Raspberry Pi 5  |
                         +-------------------+
                         |                   |
+-------------+          |                   |
| Camera      +----------+ Camera Port       |
| Module      |          |                   |
+-------------+          |                   |
                         |                   |
+-------------+          |  5V (Pin 2)       |
|             +----------+                   |
|  MQ-2       |          |  GPIO17 (Pin 11)  |
|  Gas Sensor +----------+                   |
|             |          |  GND (Pin 39)     |
+-------------+----------+                   |
                         |                   |
                         |  5V (Pin 4)       |
+-------------+          |                   |
|             +----------+  TXD (Pin 8)      |
|  NEO-6M     |          |                   |
|  GPS Module +----------+  RXD (Pin 10)     |
|             |          |                   |
|             +----------+  GND (Pin 6)      |
+-------------+          |                   |
                         +-------------------+
```

## Setup Instructions

### 1. Enable Required Interfaces

Before connecting hardware, you need to enable the necessary interfaces on your Raspberry Pi:

```bash
sudo raspi-config
```

Navigate to "Interface Options" and enable:
- Camera
- Serial Port (for GPS)
  - Answer "No" to "Would you like a login shell to be accessible over serial?"
  - Answer "Yes" to "Would you like the serial port hardware to be enabled?"
- I2C (if using additional I2C sensors)

### 2. Connect Hardware Components

1. **Power off the Raspberry Pi**:
   ```bash
   sudo shutdown -h now
   ```

2. **Connect the Camera Module** as described above

3. **Connect the GPS Module** to pins 4, 6, 8, and 10

4. **Connect the Gas Sensor** to pins 2, 11, and any ground pin

5. **Power on the Raspberry Pi** and check if components are recognized:
   ```bash
   # Check if camera is detected
   vcgencmd get_camera
   
   # Check if serial port is available
   ls -l /dev/ttyAMA0
   
   # Check GPIO status
   gpio readall  # You may need to install wiringpi
   ```

### 3. Configure Serial Port for GPS

By default, the Raspberry Pi's UART might be used by the system. Modify the `/boot/config.txt` file:

```bash
sudo nano /boot/config.txt
```

Add these lines at the end:
```
# Disable Bluetooth and restore UART0/ttyAMA0 to GPIO pins 14 & 15
dtoverlay=disable-bt
enable_uart=1
```

Then disable the serial getty service:
```bash
sudo systemctl disable hciuart
sudo systemctl disable serial-getty@ttyAMA0.service
```

Reboot the Raspberry Pi:
```bash
sudo reboot
```

## Testing Components

### Test Camera
```bash
# Take a still image
libcamera-still -o test.jpg

# Preview video for 5 seconds
libcamera-vid -t 5000 --preview
```

### Test GPS Module
```bash
# Install GPS tools
sudo apt install gpsd gpsd-clients

# Configure gpsd
sudo systemctl stop gpsd.socket
sudo systemctl disable gpsd.socket
sudo gpsd /dev/ttyAMA0 -F /var/run/gpsd.sock

# Test GPS reception
gpsmon
# or
cgps -s
```

### Test Gas Sensor
```bash
# Create a simple Python script
cat > test_gas.py << EOF
import RPi.GPIO as GPIO
import time

# Set GPIO mode
GPIO.setmode(GPIO.BCM)
GAS_PIN = 17
GPIO.setup(GAS_PIN, GPIO.IN)

try:
    print("Gas sensor testing. Press Ctrl+C to exit")
    while True:
        gas_detected = not GPIO.input(GAS_PIN)  # Invert if active-low
        print(f"Gas detected: {gas_detected}")
        time.sleep(1)
except KeyboardInterrupt:
    print("Test finished")
finally:
    GPIO.cleanup()
EOF

# Run the test
python3 test_gas.py
```

## Troubleshooting

### Camera Issues
- Ensure the ribbon cable is properly inserted (blue side facing Ethernet port)
- Check if camera is enabled in `raspi-config`
- Try `vcgencmd get_camera` to see if camera is detected

### GPS Issues
- Check physical connections
- Ensure GPS module has clear view of the sky
- Check if serial port is properly configured
- Use `cat /dev/ttyAMA0` to see raw NMEA data

### Gas Sensor Issues
- Adjust potentiometer to calibrate sensitivity
- Check GPIO pin number in code matches wiring
- Allow proper warm-up time (2-3 minutes)
- Test with a known gas source (e.g., lighter without flame)

## Power Considerations

The Raspberry Pi 5 requires a 5V/3A USB-C power supply. When connecting multiple sensors, power requirements increase:

- Raspberry Pi 5: ~2.5A under load
- Camera Module: ~250mA
- GPS Module: ~50mA
- MQ-2 Gas Sensor: ~150mA (higher during warm-up)

For outdoor or mobile deployments, consider:
- A mobile power bank with at least 3A output
- Solar power solutions with adequate battery storage
- Power management scripts to reduce consumption when idle

## References

- [Raspberry Pi 5 Hardware Documentation](https://www.raspberrypi.com/documentation/computers/raspberry-pi-5.html)
- [Raspberry Pi GPIO Pinout](https://pinout.xyz/)
- [NEO-6M GPS Module Datasheet](https://www.u-blox.com/sites/default/files/products/documents/NEO-6_DataSheet_(GPS.G6-HW-09005).pdf)
- [MQ-2 Gas Sensor Datasheet](https://www.pololu.com/file/0J309/MQ2.pdf)