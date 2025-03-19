import serial
import time
import os

# Try to import pynmea2 for parsing
try:
    import pynmea2
    PYNMEA_AVAILABLE = True
except ImportError:
    PYNMEA_AVAILABLE = False
    print("pynmea2 not installed. Install with:")
    print("pip install pynmea2")
    print("Continuing with basic functionality...\n")

# Configuration - change this based on what worked in the simple test
GPS_PORT = '/dev/ttyAMA0'  # Change this to the port that worked
BAUDRATE = 9600
TEST_DURATION = 120  # Test for 2 minutes by default

def clear_screen():
    """Clear the terminal screen"""
    os.system('clear' if os.name == 'posix' else 'cls')

def main():
    """Main function to test GPS module"""
    print("=== NEO-6M GPS Module Advanced Test ===")
    print(f"Port: {GPS_PORT}, Baudrate: {BAUDRATE}")
    print(f"Testing for {TEST_DURATION} seconds...")
    
    if not PYNMEA_AVAILABLE:
        print("Warning: pynmea2 not installed. NMEA sentence parsing will not be available.")
    
    try:
        # Open serial port
        ser = serial.Serial(
            port=GPS_PORT,
            baudrate=BAUDRATE,
            timeout=1.0
        )
        
        print(f"Successfully opened {GPS_PORT}")
        
        # Statistics
        stats = {
            'total_lines': 0,
            'nmea_sentences': 0,
            'valid_positions': 0,
            'start_time': time.time(),
            'last_position': None,
            'satellites': 0,
            'fix_quality': 0,
            'altitude': None,
            'speed': None,
            'course': None
        }
        
        # Main loop
        end_time = time.time() + TEST_DURATION
        while time.time() < end_time:
            try:
                # Read a line
                line = ser.readline()
                if not line:
                    continue
                
                stats['total_lines'] += 1
                
                # Decode the line
                try:
                    decoded = line.decode('ascii', errors='replace').strip()
                    if not decoded:
                        continue
                    
                    # Count valid NMEA sentences
                    if decoded.startswith('$'):
                        stats['nmea_sentences'] += 1
                    
                    # Parse with pynmea2 if available
                    if PYNMEA_AVAILABLE and decoded.startswith('$'):
                        try:
                            msg = pynmea2.parse(decoded)
                            
                            # RMC sentences contain position, speed, and course
                            if decoded.startswith('$GPRMC') or decoded.startswith('$GNRMC'):
                                if hasattr(msg, 'status') and msg.status == 'A':  # A = valid position
                                    stats['valid_positions'] += 1
                                    stats['last_position'] = (msg.latitude, msg.longitude)
                                    
                                    if hasattr(msg, 'spd_over_grnd'):
                                        stats['speed'] = msg.spd_over_grnd
                                    
                                    if hasattr(msg, 'true_course'):
                                        stats['course'] = msg.true_course
                            
                            # GGA sentences contain altitude and fix quality
                            elif decoded.startswith('$GPGGA') or decoded.startswith('$GNGGA'):
                                if hasattr(msg, 'num_sats'):
                                    stats['satellites'] = msg.num_sats
                                
                                if hasattr(msg, 'gps_qual'):
                                    stats['fix_quality'] = msg.gps_qual
                                
                                if hasattr(msg, 'altitude'):
                                    stats['altitude'] = msg.altitude
                        
                        except pynmea2.ParseError:
                            # Ignore parsing errors - some sentences might be incomplete
                            pass
                
                except UnicodeDecodeError:
                    # Ignore decode errors
                    pass
                
                # Update display every second
                if int(time.time()) % 1 == 0:
                    clear_screen()
                    
                    # Calculate runtime
                    runtime = time.time() - stats['start_time']
                    remaining = end_time - time.time()
                    
                    # Display status
                    print("=== GPS Module Status ===")
                    print(f"Runtime: {int(runtime)} seconds (Test ends in {int(remaining)} seconds)")
                    print(f"Total lines received: {stats['total_lines']}")
                    print(f"NMEA sentences: {stats['nmea_sentences']}")
                    print(f"Valid position fixes: {stats['valid_positions']}")
                    
                    # Show current position if available
                    print("\n=== Current Position ===")
                    if stats['last_position']:
                        print(f"Latitude: {stats['last_position'][0]}")
                        print(f"Longitude: {stats['last_position'][1]}")
                    else:
                        print("No valid position fix yet")
                    
                    print(f"Satellites: {stats['satellites']}")
                    print(f"Fix Quality: {stats['fix_quality']} ({fix_quality_str(stats['fix_quality'])})")
                    
                    if stats['altitude'] is not None:
                        print(f"Altitude: {stats['altitude']} meters")
                    
                    if stats['speed'] is not None:
                        print(f"Speed: {stats['speed']} knots")
                    
                    if stats['course'] is not None:
                        print(f"Course: {stats['course']}°")
                    
                    # Show most recent NMEA sentence
                    print("\n=== Latest NMEA Data ===")
                    print(decoded)
                    
                    # Show connection rate
                    if runtime > 0:
                        print(f"\nAverage reception rate: {stats['total_lines'] / runtime:.1f} lines/second")
                    
                    # Show instructions
                    print("\nPress Ctrl+C to exit early")
            
            except KeyboardInterrupt:
                break
        
        # Test complete
        runtime = time.time() - stats['start_time']
        
        clear_screen()
        print("=== GPS Test Complete ===")
        print(f"Runtime: {int(runtime)} seconds")
        print(f"Total lines received: {stats['total_lines']}")
        print(f"NMEA sentences: {stats['nmea_sentences']}")
        print(f"Valid position fixes: {stats['valid_positions']}")
        
        if stats['total_lines'] == 0:
            print("\n❌ No data received from GPS module!")
            print("Please check connections and try again.")
        elif stats['valid_positions'] == 0:
            print("\n⚠️ Received data but no valid position fixes!")
            print("This is normal if you're indoors or the module hasn't acquired satellites yet.")
            print("Take the module outside with a clear view of the sky and try again.")
        else:
            print("\n✅ GPS module is working correctly!")
            print(f"Last known position: {stats['last_position']}")
        
        # Close serial port
        ser.close()
        print("\nSerial port closed")
    
    except Exception as e:
        print(f"Error: {e}")
        print("Make sure the GPS module is connected properly and the port is correct.")

def fix_quality_str(quality):
    """Convert fix quality number to descriptive string"""
    qualities = {
        0: "Invalid",
        1: "GPS fix",
        2: "DGPS fix",
        3: "PPS fix",
        4: "RTK",
        5: "Float RTK",
        6: "Estimated",
        7: "Manual input",
        8: "Simulation"
    }
    return qualities.get(quality, "Unknown")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nTest interrupted by user")
