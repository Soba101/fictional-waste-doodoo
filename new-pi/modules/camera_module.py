"""
Camera module for capturing images from the Raspberry Pi camera.
"""
import cv2
import numpy as np
import subprocess
import threading
import time
import logging
import os
from datetime import datetime

import config

logger = logging.getLogger('camera-module')

class CameraModule:
    def __init__(self, frame_callback=None):
        """
        Initialize the camera module.
        
        Args:
            frame_callback: Function to call with each new frame
        """
        self.frame_callback = frame_callback
        self.latest_frame = None
        self.frame_lock = threading.Lock()
        self.running = False
        self.thread = None
        
    def get_latest_frame(self):
        """Get the most recent camera frame."""
        with self.frame_lock:
            if self.latest_frame is not None:
                return self.latest_frame.copy()
            else:
                # Return a blank frame if no camera frame is available
                blank_frame = np.ones((config.CAMERA_HEIGHT, config.CAMERA_WIDTH, 3), dtype=np.uint8) * 255
                cv2.putText(blank_frame, "Camera initializing...", (50, 240), 
                          cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)
                return blank_frame
    
    def start(self):
        """Start the camera capture thread."""
        if self.running:
            logger.warning("Camera is already running")
            return
            
        self.running = True
        self.thread = threading.Thread(target=self._capture_thread, daemon=True)
        self.thread.start()
        logger.info("Camera capture thread started")
        
    def stop(self):
        """Stop the camera capture thread."""
        self.running = False
        if self.thread:
            self.thread.join(timeout=1.0)
            logger.info("Camera capture thread stopped")
    
    def _capture_thread(self):
        """Thread function for capturing frames from the camera."""
        logger.info("Starting camera capture with libcamera-still")
        
        try:
            # Main capture loop
            counter = 0
            while self.running:
                try:
                    # Capture frame with libcamera-still
                    capture_path = f"{config.TEMP_DIR}/capture_{counter % 10}.jpg"
                    counter += 1
                    
                    # Use libcamera-still to capture an image
                    subprocess.run([
                        "libcamera-still", 
                        "-n",  # No preview
                        "--immediate",  # Capture immediately
                        "-o", capture_path,
                        "--width", str(config.CAMERA_WIDTH), 
                        "--height", str(config.CAMERA_HEIGHT),
                        "-t", "1"  # Minimize timeout
                    ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    
                    # Load the captured image
                    frame = cv2.imread(capture_path)
                    
                    if frame is not None:
                        # Update the latest frame
                        with self.frame_lock:
                            self.latest_frame = frame
                            
                        # Call the callback function if provided
                        if self.frame_callback:
                            self.frame_callback(frame)
                    else:
                        logger.warning("Failed to read captured frame")
                    
                    # Control capture rate
                    time.sleep(1.0 / config.CAMERA_FPS)
                    
                except Exception as e:
                    logger.error(f"Error in camera capture: {e}")
                    time.sleep(1)
                    
        except Exception as e:
            logger.error(f"Fatal camera error: {e}")
            self._generate_dummy_frames()
    
    def _generate_dummy_frames(self):
        """Generate dummy frames when the camera fails."""
        logger.info("Switching to dummy pattern generator")
        
        while self.running:
            # Create a checkerboard pattern
            pattern = np.zeros((config.CAMERA_HEIGHT, config.CAMERA_WIDTH, 3), dtype=np.uint8)
            square_size = 40
            now = datetime.now()
            
            # Make pattern change based on current time
            offset = now.second % square_size
            
            # Draw pattern
            for i in range(0, config.CAMERA_WIDTH + square_size, square_size):
                for j in range(0, config.CAMERA_HEIGHT + square_size, square_size):
                    if ((i+offset)//square_size + (j+offset)//square_size) % 2 == 0:
                        x1 = max(0, i-offset)
                        y1 = max(0, j-offset)
                        x2 = min(config.CAMERA_WIDTH, i+square_size-offset)
                        y2 = min(config.CAMERA_HEIGHT, j+square_size-offset)
                        pattern[y1:y2, x1:x2] = [0, 255, 0]  # Green color
            
            # Add text with timestamp
            timestamp = now.strftime("%H:%M:%S")
            cv2.putText(pattern, "TEST PATTERN - NO CAMERA", (50, 50), 
                      cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)
            cv2.putText(pattern, timestamp, (50, 100), 
                      cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)
            
            # Update the latest frame
            with self.frame_lock:
                self.latest_frame = pattern
                
            # Call the callback function if provided
            if self.frame_callback:
                self.frame_callback(pattern)
                
            time.sleep(0.1)
