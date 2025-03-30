#!/usr/bin/env python3
# gas_sensor_module.py - MQ-2 Gas Sensor module for Raspberry Pi 5
import time
import logging
import threading
from datetime import datetime
import config

# Import gpiozero
try:
    from gpiozero import DigitalInputDevice
    GPIOZERO_AVAILABLE = True
except ImportError as e:
    GPIOZERO_AVAILABLE = False
    print(f"Import error: {e}")

class GasSensorModule:
    """MQ-2 Gas Sensor interface for Raspberry Pi 5"""
    
    def __init__(self, pin=config.GAS_PIN, active_low=True, logger=None):
        """Initialize the Gas Sensor module
        
        Args:
            pin (int): GPIO pin connected to DO (Digital Output), defaults to config.GAS_PIN
            active_low (bool): Set to True if LOW means gas detected (default for MQ-2)
            logger: Optional logger object
        """
        # Configuration
        self.pin = pin
        self.active_low = active_low
        self.thread = None
        self.running = False
        self.sensor = None
        
        # Check if required libraries are available
        if not GPIOZERO_AVAILABLE:
            raise ImportError("gpiozero library is required. Install with: sudo apt install python3-gpiozero")
        
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
            # Clean up any existing resources
            self.stop()
            
            # Wait a bit to ensure GPIO is released
            time.sleep(1)
            
            # Try to identify what's using the GPIO
            try:
                import subprocess
                gpio_status = subprocess.check_output(['gpioinfo', 'gpiochip0'], text=True)
                self.logger.debug("GPIO status:\n%s", gpio_status)
            except Exception as e:
                self.logger.warning(f"Could not get GPIO status: {e}")
            
            # Create the sensor object
            try:
                self.sensor = DigitalInputDevice(self.pin)
                self.logger.info(f"Gas sensor initialized on GPIO {self.pin}")
                
                # Test the sensor
                test_value = self.sensor.value
                self.logger.debug(f"Initial sensor value: {test_value}")
                
            except Exception as e:
                self.logger.error(f"Failed to create sensor: {e}")
                self.stop()
                return False
            
            # Initialize statistics
            self.stats['start_time'] = time.time()
            
            # Start monitoring thread
            self.running = True
            self.thread = threading.Thread(target=self._monitor_thread, daemon=True)
            self.thread.start()
            
            # Check initial state
            self._check_sensor_state()
            
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to start gas sensor: {e}")
            self.stop()  # Clean up on failure
            return False
    
    def _check_sensor_state(self):
        """Read the sensor state and update data"""
        try:
            # Read current value
            raw_value = self.sensor.value  # 1 or 0
            
            # Determine if gas is detected based on value and active_low setting
            if self.active_low:
                is_gas_detected = not bool(raw_value)  # If active_low, then LOW (0) means gas detected
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
                    self.logger.info("Gas level returned to normal")
            
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
                    status = "DETECTED" if self.data['gas_detected'] else "Normal"
                    self.logger.debug(f"Gas status: {status}, detections: {self.data['detection_count']}")
                
                # Sleep for a second
                time.sleep(1)
                
            except Exception as e:
                self.logger.error(f"Error in monitoring thread: {e}")
                time.sleep(1)
                
        self.logger.debug("Gas sensor monitoring stopped")
    
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
        
        # Stop the monitoring thread
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=1)
        
        # Clean up GPIO resources
        if self.sensor:
            try:
                self.sensor.close()
            except Exception as e:
                self.logger.error(f"Error closing sensor: {e}")
            finally:
                self.sensor = None
            
        self.logger.debug("Gas sensor resources cleaned up")
        
        # Add a small delay to ensure resources are released
        time.sleep(0.5)

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
        sensor = GasSensorModule(pin=17, active_low=True)  # active_low=True means LOW signal indicates gas detected
        
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