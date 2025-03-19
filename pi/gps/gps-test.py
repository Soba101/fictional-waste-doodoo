import serial
import time

# List of possible serial ports to try
ports_to_try = [
    '/dev/ttyAMA0',    # Primary hardware UART
    '/dev/serial0',    # Symlink on your system
    '/dev/ttyAMA10'    # What serial0 points to on your system
]

# Settings for the NEO-6M GPS module
baudrate = 9600

def test_gps(port):
    """Test if a GPS is connected to the specified port"""
    print(f"Trying port: {port}")
    
    try:
        # Open the serial port
        ser = serial.Serial(
            port=port,
            baudrate=baudrate,
            timeout=1
        )
        
        print(f"Successfully opened {port}")
        
        # Read data for 10 seconds
        print("Reading data for 10 seconds. You should see NMEA sentences if the GPS is working.")
        print("If you don't see any data, the GPS might not be connected properly.")
        
        end_time = time.time() + 10
        count = 0
        
        while time.time() < end_time:
            # Read a line from the GPS
            line = ser.readline()
            
            if line:
                count += 1
                try:
                    # Try to decode as ASCII text
                    decoded = line.decode('ascii', errors='replace').strip()
                    print(f"Data: {decoded}")
                except:
                    # If decoding fails, print the raw bytes
                    print(f"Raw data: {line}")
        
        ser.close()
        
        if count > 0:
            print(f"✅ Received {count} lines from {port}. GPS appears to be working!")
            return True
        else:
            print(f"❌ No data received from {port} after 10 seconds.")
            return False
            
    except Exception as e:
        print(f"❌ Error with {port}: {e}")
        return False

def main():
    """Try each port until we find one that works"""
    print("=== NEO-6M GPS Module Test ===")
    print("This script will try to connect to your GPS module")
    print("and read NMEA sentences to verify it's working.")
    
    for port in ports_to_try:
        if test_gps(port):
            print(f"\n✅ SUCCESS! The GPS module is working on {port}")
            return
        print("\nTrying next port...\n")
    
    print("\n❌ Could not establish communication with the GPS module.")
    print("Please check the following:")
    print("1. The GPS module is properly connected to the Raspberry Pi")
    print("2. TXD on GPS is connected to RXD on Pi (GPIO 15)")
    print("3. RXD on GPS is connected to TXD on Pi (GPIO 14)")
    print("4. The GPS module is powered (red LED should be on)")
    print("5. UART is enabled in raspi-config")

if __name__ == "__main__":
    main()