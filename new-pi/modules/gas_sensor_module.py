#!/usr/bin/env python3
# gas_sensor_module.py - MQ-2 Gas Sensor module for Raspberry Pi 5
import time
import logging
import threading
from datetime import datetime

# Import gpiozero with LGPIO factory for Pi 5
try:
    from gpiozero import DigitalInputDevice
    from gpiozero.pins.lgpio import LGPIOFactory
    GPIOZERO_AVAILABLE = True
except ImportError:
    GPIOZERO_AVAILABLE = False

class GasSensor:
    """MQ-2 Gas Sensor interface for Raspberry Pi 5 using gpiozero with LGPIO"""
    
    def __init__(self, pin=17, active_low=True, logger=None):
        """Initialize the Gas Sensor module
        
        Args:
            pin (int): GPIO pin connected to DO (Digital Output)
            active_low (bool): Set to True if LOW means gas detected (default for MQ-2)
            logger: Optional logger object
        """
        # Configuration
        self.pin = pin
        self.active_low = active_low
        self.thread = None
        self.running = False
        
        # Check if required libraries are available
        if not GPIOZERO_AVAILABLE:
            raise ImportError("gpiozero and lgpio libraries are required. Install with: sudo apt install python3-gpiozero python3-lgpio")
        
        # Set up logger
        if logger:
            self.logger = logger
        else:
            self.logger = logging.getLogger('gas-sensor')
            handler = logging.StreamHandler()
            formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)
            self.logger.setLevel(logging.INFO)
        
        # Initialize sensor data with default values
        self.data = {
            'gas_detected': False,
            'gas_value': 0,        # Simulated value (0-1000)
            'last_detection': None,
            'last_update': None,
            'detection_count': 0
        }
        
        # Statistics
        self.stats = {
            'readings': 0,
            'detections': 0,
            'start_time': None
        }
    
    def start(self):
        """Start the gas sensor monitoring
        
        Returns:
            bool: True if started successfully, False otherwise
        """
        if self.running:
            self.logger.warning("Gas sensor already running")
            return True
        
        try:
            # Create LGPIO factory for Pi 5 compatibility
            factory = LGPIOFactory()
            self.logger.info("Created LGPIO factory for Pi 5 compatibility")
            
            # Create the sensor object
            self.sensor = DigitalInputDevice(self.pin, pin_factory=factory)
            self.logger.info(f"Gas sensor initialized on GPIO {self.pin}")
            
            # Initialize statistics
            self.stats['start_time'] = time.time()
            
            # Start monitoring thread
            self.running = True
            self.thread = threading.Thread(target=self._monitor_thread, daemon=True)
            self.thread.start()
            self.logger.info("Gas sensor monitoring thread started")
            
            # Check initial state
            self._check_sensor_state()
            
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to start gas sensor: {e}")
            return False
    
    def _check_sensor_state(self):
        """Read the sensor state and update data"""
        try:
            # Read current value
            raw_value = self.sensor.value  # 1 or 0
            
            # Determine if gas is detected based on value and active_low setting
            if self.active_low:
                is_gas_detected = not raw_value  # If active_low, then LOW (0) means gas detected
            else:
                is_gas_detected = bool(raw_value)  # If active_high, then HIGH (1) means gas detected
            
            # Update timestamp
            now = datetime.now()
            self.data['last_update'] = now
            
            # Check if state changed
            if is_gas_detected != self.data['gas_detected']:
                if is_gas_detected:
                    self.logger.warning("Gas detected!")
                    self.data['detection_count'] += 1
                    self.data['last_detection'] = now
                    self.stats['detections'] += 1
                else:
                    self.logger.info("Gas no longer detected")
            
            # Update state
            self.data['gas_detected'] = is_gas_detected
            
            # Set simulated gas value based on detection
            # In reality, this would come from an analog reading if AO was connected
            if is_gas_detected:
                self.data['gas_value'] = 800  # Above threshold
            else:
                self.data['gas_value'] = 100  # Below threshold
                
            return is_gas_detected
            
        except Exception as e:
            self.logger.error(f"Error reading sensor: {e}")
            return False
    
    def _monitor_thread(self):
        """Background thread for monitoring gas sensor"""
        while self.running:
            try:
                # Update statistics
                self.stats['readings'] += 1
                
                # Check sensor state
                self._check_sensor_state()
                
                # Log status occasionally
                if self.stats['readings'] % 60 == 0:  # Log every 60 seconds
                    status = "DETECTED" if self.data['gas_detected'] else "not detected"
                    self.logger.info(f"Gas status: {status}, total detections: {self.data['detection_count']}")
                
                # Sleep for a second
                time.sleep(1)
                
            except Exception as e:
                self.logger.error(f"Error in monitoring thread: {e}")
                time.sleep(1)
                
        self.logger.info("Gas sensor monitoring thread stopped")
    
    def get_gas_data(self):
        """Get the current gas sensor data
        
        Returns:
            dict: Dictionary containing gas status information
        """
        # Force a fresh reading
        self._check_sensor_state()
        
        # Return a copy of the data
        return self.data.copy()
    
    def get_status(self):
        """Get gas sensor module status
        
        Returns:
            dict: Dictionary containing status and statistics
        """
        runtime = 0
        if self.stats['start_time']:
            runtime = time.time() - self.stats['start_time']
            
        status = {
            'running': self.running,
            'pin': self.pin, 
            'readings': self.stats['readings'],
            'detections': self.stats['detections'],
            'runtime_seconds': runtime,
            'active_low': self.active_low
        }
        return status
    
    def stop(self):
        """Stop the gas sensor monitoring"""
        self.running = False
        if hasattr(self, 'sensor'):
            # Resources are automatically cleaned up by gpiozero
            pass
        self.logger.info("Gas sensor monitoring stopped")


# Example usage when run directly
if __name__ == "__main__":
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    print("MQ-2 Gas Sensor Module for Raspberry Pi 5")
    print("========================================")
    print("Reading from DO pin connected to GPIO 17")
    print("Press Ctrl+C to exit\n")
    
    try:
        # Create and start gas sensor
        sensor = GasSensor(pin=17, active_low=True)  # active_low=True means LOW signal indicates gas detected
        
        if sensor.start():
            print("Gas sensor started successfully!")
            print("Current data will be displayed every 2 seconds.")
            print("If you need to adjust sensitivity, turn the potentiometer on the sensor.")
            print("Try placing a butane lighter (unlit) near the sensor to test.\n")
            
            while True:
                gas_data = sensor.get_gas_data()
                status = sensor.get_status()
                
                print("\n----- Gas Sensor Data -----")
                print(f"Gas Detected: {'YES' if gas_data['gas_detected'] else 'NO'}")
                print(f"Gas Value: {gas_data['gas_value']}")
                print(f"Detection Count: {gas_data['detection_count']}")
                if gas_data['last_detection']:
                    last_detect = gas_data['last_detection'].strftime("%H:%M:%S")
                    print(f"Last Detection: {last_detect}")
                print(f"Running for: {status['runtime_seconds']:.1f} seconds")
                
                # Wait before next update
                time.sleep(2)
                
        else:
            print("Failed to start gas sensor.")
            
    except KeyboardInterrupt:
        print("\nStopping gas sensor...")
        if 'sensor' in locals():
            sensor.stop()
        print("Gas sensor stopped")
    except Exception as e:
        print(f"Error: {e}")