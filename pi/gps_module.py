import serial
import threading
import time
import logging
from datetime import datetime

# Try to import pynmea2 for parsing NMEA sentences
try:
    import pynmea2
    PYNMEA_AVAILABLE = True
except ImportError:
    PYNMEA_AVAILABLE = False
    print("Warning: pynmea2 not installed, GPS parsing will be limited")
    print("Install with: pip install pynmea2")

class GPSModule:
    """GPS Module for NEO-6M GPS receiver"""
    
    def __init__(self, port='/dev/ttyAMA0', baudrate=9600, logger=None):
        """Initialize the GPS module
        
        Args:
            port (str): Serial port name
            baudrate (int): Baud rate for serial communication
            logger: Optional logger object
        """
        # Configuration
        self.port = port
        self.baudrate = baudrate
        self.serial = None
        self.thread = None
        self.running = False
        
        # Set up logger
        if logger:
            self.logger = logger
        else:
            self.logger = logging.getLogger('gps-module')
            handler = logging.StreamHandler()
            formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)
            self.logger.setLevel(logging.INFO)
        
        # Initialize GPS data with default values
        self.data = {
            # Position data (defaults to Singapore)
            'latitude': 1.3521,
            'longitude': 103.8198,
            'altitude': 0.0,
            'speed': 0.0,
            'course': 0.0,
            
            # Status flags
            'has_fix': False,
            'satellites': 0,
            'fix_quality': 0,
            'hdop': 99.9,  # Horizontal dilution of precision
            
            # Timestamps
            'timestamp': None,
            'datestamp': None,
            'last_update': None,
            'last_fix': None
        }
        
        # Statistics
        self.stats = {
            'sentences_received': 0,
            'valid_fixes': 0,
            'errors': 0,
            'start_time': None
        }
    
    def start(self):
        """Start the GPS module
        
        Returns:
            bool: True if started successfully, False otherwise
        """
        if self.running:
            self.logger.warning("GPS module already running")
            return True
        
        # Initialize statistics
        self.stats['start_time'] = time.time()
        
        # Try to open serial port
        try:
            self.logger.info(f"Opening serial port {self.port} at {self.baudrate} baud")
            self.serial = serial.Serial(
                port=self.port,
                baudrate=self.baudrate,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE,
                bytesize=serial.EIGHTBITS,
                timeout=1
            )
            self.logger.info(f"Connected to GPS on {self.serial.portstr}")
        except Exception as e:
            self.logger.error(f"Failed to open serial port: {e}")
            return False
        
        # Start GPS reading thread
        self.running = True
        self.thread = threading.Thread(target=self._read_gps_data, daemon=True)
        self.thread.start()
        self.logger.info("GPS reading thread started")
        return True
    
    def _read_gps_data(self):
        """Background thread to read and parse GPS data"""
        while self.running and self.serial:
            try:
                # Read a line from GPS
                line = self.serial.readline()
                if not line:
                    continue
                
                # Update statistics
                self.stats['sentences_received'] += 1
                self.data['last_update'] = datetime.now()
                
                # Try to decode and parse
                try:
                    decoded = line.decode('ascii', errors='replace').strip()
                    if not decoded:
                        continue
                    
                    # Parse NMEA sentence if pynmea2 is available
                    if PYNMEA_AVAILABLE and decoded.startswith('$'):
                        try:
                            msg = pynmea2.parse(decoded)
                            
                            # Process different sentence types
                            if decoded.startswith('$GPRMC') or decoded.startswith('$GNRMC'):
                                self._process_rmc(msg)
                            elif decoded.startswith('$GPGGA') or decoded.startswith('$GNGGA'):
                                self._process_gga(msg)
                            elif decoded.startswith('$GPGSA') or decoded.startswith('$GNGSA'):
                                self._process_gsa(msg)
                        except Exception as e:
                            # Silently ignore parse errors
                            pass
                
                except Exception as e:
                    # Ignore decoding errors
                    pass
                    
            except Exception as e:
                self.logger.error(f"Error reading GPS data: {e}")
                self.stats['errors'] += 1
                time.sleep(1)  # Prevent tight loop if persistent errors
        
        self.logger.info("GPS reading thread stopped")
    
    def _process_rmc(self, msg):
        """Process RMC (Recommended Minimum) sentence"""
        if hasattr(msg, 'status') and msg.status == 'A':  # 'A' means valid
            # Update position
            self.data['latitude'] = msg.latitude
            self.data['longitude'] = msg.longitude
            self.data['has_fix'] = True
            self.data['last_fix'] = datetime.now()
            self.stats['valid_fixes'] += 1
            
            # Update speed and course if available
            if hasattr(msg, 'spd_over_grnd'):
                self.data['speed'] = msg.spd_over_grnd
            if hasattr(msg, 'true_course') and msg.true_course:
                self.data['course'] = msg.true_course
                
            # Update timestamp and datestamp
            self.data['timestamp'] = msg.timestamp
            self.data['datestamp'] = msg.datestamp
            
            # Log position occasionally (every 30 fixes)
            if self.stats['valid_fixes'] % 30 == 0:
                self.logger.info(f"Position: {self.data['latitude']:.6f}, {self.data['longitude']:.6f}")
    
    def _process_gga(self, msg):
        """Process GGA (Global Positioning System Fix Data) sentence"""
        # Update fix quality
        if hasattr(msg, 'gps_qual'):
            self.data['fix_quality'] = msg.gps_qual
            
        # Update satellite count
        if hasattr(msg, 'num_sats'):
            self.data['satellites'] = int(msg.num_sats) if msg.num_sats else 0
            
        # Update altitude
        if hasattr(msg, 'altitude'):
            self.data['altitude'] = float(msg.altitude) if msg.altitude else 0.0
            
        # Update HDOP (Horizontal Dilution of Precision)
        if hasattr(msg, 'horizontal_dil'):
            self.data['hdop'] = float(msg.horizontal_dil) if msg.horizontal_dil else 99.9
    
    def _process_gsa(self, msg):
        """Process GSA (GNSS DOP and Active Satellites) sentence"""
        # This is mainly for additional precision data, not implementing for basic functionality
        pass
    
    def get_position(self):
        """Get the current GPS position
        
        Returns:
            dict: Dictionary containing position and status information
        """
        # Return a copy of the data so it won't be changed by the thread while in use
        return self.data.copy()
    
    def get_status(self):
        """Get GPS module status
        
        Returns:
            dict: Dictionary containing status and statistics
        """
        runtime = 0
        if self.stats['start_time']:
            runtime = time.time() - self.stats['start_time']
            
        status = {
            'running': self.running,
            'port': self.port, 
            'sentences_received': self.stats['sentences_received'],
            'valid_fixes': self.stats['valid_fixes'],
            'errors': self.stats['errors'],
            'runtime_seconds': runtime
        }
        return status
    
    def stop(self):
        """Stop the GPS module"""
        self.running = False
        if self.serial:
            try:
                self.serial.close()
            except Exception as e:
                self.logger.error(f"Error closing serial port: {e}")
            self.serial = None
        self.logger.info("GPS module stopped")


# Example usage when run directly
if __name__ == "__main__":
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Create and start GPS module
    gps = GPSModule()
    if gps.start():
        try:
            print("GPS module started. Press Ctrl+C to stop.")
            print("Current data will be displayed every 2 seconds.")
            
            while True:
                position = gps.get_position()
                status = gps.get_status()
                
                print("\n----- GPS Data -----")
                print(f"Fix: {'YES' if position['has_fix'] else 'NO'}")
                print(f"Satellites: {position['satellites']}")
                print(f"Position: {position['latitude']:.6f}, {position['longitude']:.6f}")
                print(f"Altitude: {position['altitude']} meters")
                print(f"Speed: {position['speed']} knots")
                print(f"Course: {position['course']}°")
                print(f"Fix Quality: {position['fix_quality']}")
                print(f"HDOP: {position['hdop']}")
                print(f"Sentences received: {status['sentences_received']}")
                print(f"Valid fixes: {status['valid_fixes']}")
                
                # Wait before next update
                time.sleep(2)
                
        except KeyboardInterrupt:
            print("\nStopping GPS module...")
            gps.stop()
            print("GPS module stopped")
    else:
        print("Failed to start GPS module. Check connections and port settings.")
