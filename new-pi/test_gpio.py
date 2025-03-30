#!/usr/bin/env python3
import time
from gpiozero import DigitalInputDevice
from gpiozero.pins.lgpio import LGPIOFactory

def test_gpio():
    print("Testing GPIO 17...")
    try:
        # Create factory
        factory = LGPIOFactory()
        print("Created LGPIO factory")
        
        # Create input device
        sensor = DigitalInputDevice(17, pin_factory=factory)
        print("Created DigitalInputDevice on GPIO 17")
        
        # Read value
        value = sensor.value
        print(f"Current value: {value}")
        
        # Clean up
        sensor.close()
        factory.close()
        print("Cleanup completed")
        
    except Exception as e:
        print(f"Error: {e}")
    finally:
        print("Test completed")

if __name__ == "__main__":
    test_gpio() 