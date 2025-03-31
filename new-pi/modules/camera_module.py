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
        self.process = None
        self.stderr_thread = None
        self.retry_count = 0
        self.max_retries = 3
        self.retry_delay = 1  # Start with 1 second delay
        
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
        
        # Verify frame callback is set
        if self.frame_callback is None:
            logger.warning("No frame callback set - frames will not be processed by detection module")
        else:
            logger.info("Frame callback is set - frames will be sent to detection module")
        
    def stop(self):
        """Stop the camera capture thread."""
        self.running = False
        
        # Stop stderr logging thread
        if self.stderr_thread:
            self.stderr_thread.join(timeout=1.0)
        
        # Stop camera process
        if self.process:
            try:
                self.process.terminate()
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.kill()
                try:
                    self.process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    logger.error("Failed to kill camera process")
            except Exception as e:
                logger.error(f"Error stopping camera process: {e}")
            finally:
                self.process = None
        
        # Stop capture thread
        if self.thread:
            self.thread.join(timeout=2.0)
            if self.thread.is_alive():
                logger.warning("Camera capture thread did not stop cleanly")
            logger.info("Camera capture thread stopped")
        
        # Reset state
        self.retry_count = 0
        self.retry_delay = 1
    
    def _capture_thread(self):
        """Thread function for capturing frames from the camera."""
        logger.info("Starting camera capture with libcamera-vid")
        
        while self.running:
            try:
                # First check if we can access the camera
                test_cmd = ["libcamera-still", "--list-cameras"]
                try:
                    result = subprocess.run(test_cmd, capture_output=True, text=True)
                    logger.info(f"Available cameras: {result.stdout}")
                except Exception as e:
                    logger.error(f"Error checking camera availability: {e}")
                    self._generate_dummy_frames()
                    return

                # Start libcamera-vid process with more robust error handling
                cmd = [
                    "libcamera-vid",
                    "-n",                                    # No preview
                    "--codec", "mjpeg",                      # Use MJPEG codec
                    "--width", str(config.CAMERA_WIDTH),     # Frame width
                    "--height", str(config.CAMERA_HEIGHT),   # Frame height
                    "--framerate", str(config.CAMERA_FPS),   # Use configured framerate
                    "--timeout", "0",                        # No timeout
                    "--segment", "1",                        # Output in segments
                    "--inline",                             # Headers inline
                    "--output", "-"                         # Output to stdout
                ]
                
                logger.info(f"Starting camera with command: {' '.join(cmd)}")
                
                self.process = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    bufsize=0  # Unbuffered output
                )
                
                # Start a thread to log stderr
                self.stderr_thread = threading.Thread(target=self._log_stderr, daemon=True)
                self.stderr_thread.start()
                
                # Reset retry counters on successful start
                self.retry_count = 0
                self.retry_delay = 1
                
                # Read frames from the process output
                self._read_frames()
                
            except Exception as e:
                logger.error(f"Fatal camera error: {e}")
                self.retry_count += 1
                
                if self.retry_count >= self.max_retries:
                    logger.error("Max retries reached, switching to dummy frames")
                    self._generate_dummy_frames()
                    return
                    
                logger.info(f"Retrying camera start in {self.retry_delay} seconds...")
                time.sleep(self.retry_delay)
                self.retry_delay = min(self.retry_delay * 2, 30)  # Exponential backoff
                
            finally:
                if self.process:
                    logger.info("Stopping camera process")
                    self.process.terminate()
                    try:
                        self.process.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        self.process.kill()
                        self.process.wait()
                    self.process = None
    
    def _log_stderr(self):
        """Log stderr output from the camera process."""
        try:
            for line in self.process.stderr:
                if self.running:  # Only log if still running
                    logger.error(f"Camera stderr: {line.decode().strip()}")
        except Exception as e:
            logger.error(f"Error in stderr logging thread: {e}")
    
    def _read_frames(self):
        """Read and process frames from the camera process."""
        frame_count = 0
        last_frame_time = time.time()
        target_frame_interval = 1.0 / config.CAMERA_FPS  # Calculate target interval between frames
        
        while self.running:
            try:
                # Read until we find JPEG start marker (0xFF 0xD8)
                while True:
                    b = self.process.stdout.read(1)
                    if not b:
                        logger.error("Camera process stopped outputting frames")
                        return
                    if b[0] == 0xFF:
                        b2 = self.process.stdout.read(1)
                        if not b2:
                            return
                        if b2[0] == 0xD8:
                            # Found JPEG start, now read until end marker
                            jpeg_data = b + b2
                            break
                
                # Read until we find JPEG end marker (0xFF 0xD9)
                while True:
                    b = self.process.stdout.read(1)
                    if not b:
                        return
                    jpeg_data += b
                    if b[0] == 0xFF:
                        b2 = self.process.stdout.read(1)
                        if not b2:
                            return
                        jpeg_data += b2
                        if b2[0] == 0xD9:
                            break
                
                # Decode JPEG data to frame
                frame = cv2.imdecode(np.frombuffer(jpeg_data, dtype=np.uint8), cv2.IMREAD_COLOR)
                if frame is None:
                    logger.error("Failed to decode frame")
                    continue
                
                frame_count += 1
                
                # Control frame rate
                current_time = time.time()
                elapsed = current_time - last_frame_time
                if elapsed < target_frame_interval:
                    time.sleep(target_frame_interval - elapsed)
                    continue
                
                last_frame_time = current_time
                
                # Update latest frame
                with self.frame_lock:
                    self.latest_frame = frame
                
                # Send frame to detection module if callback exists
                if self.frame_callback:
                    try:
                        self.frame_callback(frame)
                    except Exception as e:
                        logger.error(f"Error sending frame to detection module: {e}")
                
            except Exception as e:
                logger.error(f"Error reading frame: {e}")
                logger.exception("Full traceback:")
                time.sleep(0.1)  # Avoid tight loop on errors
    
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
            cv2.putText(pattern, "TEST PATTERN - NO CAMERA", (50, 50), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)
            cv2.putText(pattern, timestamp, (50, 100), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)
            
            # Update the latest frame
            with self.frame_lock:
                self.latest_frame = pattern
                
            # Call the callback function if provided
            if self.frame_callback:
                self.frame_callback(pattern)
                
            time.sleep(0.1)
