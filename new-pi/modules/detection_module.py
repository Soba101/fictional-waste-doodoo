"""
Detection module for waste detection using computer vision.
"""
import cv2
import numpy as np
import logging
import threading
from datetime import datetime

logger = logging.getLogger('detection-module')

class DetectionModule:
    def __init__(self, detection_callback=None):
        """
        Initialize the detection module.
        
        Args:
            detection_callback: Function to call with detection results
        """
        self.detection_callback = detection_callback
        self.latest_predictions = []
        self.prediction_lock = threading.Lock()
        
    def get_latest_predictions(self):
        """Get the most recent detection predictions."""
        with self.prediction_lock:
            return self.latest_predictions.copy()
        
    def detect_waste(self, frame):
        """
        Detect waste in the provided frame using color thresholding.
        
        Args:
            frame: The image frame to process
            
        Returns:
            List of prediction dictionaries
        """
        try:
            # Convert to HSV for better color detection
            hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
            
            # Define ranges for different colors that might indicate waste items
            # Blue items (like plastic bottles)
            lower_blue = np.array([90, 50, 50])
            upper_blue = np.array([130, 255, 255])
            blue_mask = cv2.inRange(hsv, lower_blue, upper_blue)
            
            # Green items (like glass bottles)
            lower_green = np.array([40, 50, 50])
            upper_green = np.array([80, 255, 255])
            green_mask = cv2.inRange(hsv, lower_green, upper_green)
            
            # Brown/yellow items (like cardboard/paper)
            lower_brown = np.array([20, 50, 50])
            upper_brown = np.array([40, 255, 255])
            brown_mask = cv2.inRange(hsv, lower_brown, upper_brown)
            
            # Combined mask
            combined_mask = blue_mask | green_mask | brown_mask
            
            # Find contours
            contours, _ = cv2.findContours(combined_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            
            # Process contours
            predictions = []
            for contour in contours:
                area = cv2.contourArea(contour)
                
                # Filter by size
                if area > 1000:  # Minimum area to consider
                    x, y, w, h = cv2.boundingRect(contour)
                    
                    # Calculate center
                    center_x = x + w/2
                    center_y = y + h/2
                    
                    # Get normalized coordinates
                    img_height, img_width = frame.shape[:2]
                    x_rel = center_x / img_width
                    y_rel = center_y / img_height
                    width_rel = w / img_width
                    height_rel = h / img_height
                    
                    # Determine waste class based on color
                    roi = frame[y:y+h, x:x+w]
                    hsv_roi = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
                    blue_count = cv2.countNonZero(cv2.inRange(hsv_roi, lower_blue, upper_blue))
                    green_count = cv2.countNonZero(cv2.inRange(hsv_roi, lower_green, upper_green))
                    brown_count = cv2.countNonZero(cv2.inRange(hsv_roi, lower_brown, upper_brown))
                    
                    # Determine class based on dominant color
                    if blue_count > green_count and blue_count > brown_count:
                        waste_class = "plastic"
                    elif green_count > blue_count and green_count > brown_count:
                        waste_class = "glass"
                    else:
                        waste_class = "paper"
                    
                    # Create prediction object
                    prediction = {
                        'class': waste_class,
                        'confidence': min(0.5 + area/50000, 0.95),  # Simple confidence based on size
                        'x': x_rel,
                        'y': y_rel,
                        'width': width_rel,
                        'height': height_rel
                    }
                    predictions.append(prediction)
            
            # Update latest predictions
            with self.prediction_lock:
                self.latest_predictions = predictions
                
            # Call the callback function if provided
            if self.detection_callback and predictions:
                self.detection_callback(frame, predictions)
                
            return predictions
            
        except Exception as e:
            logger.error(f"Error in waste detection: {e}")
            return []
    
    def process_frame_with_predictions(self, frame, predictions, gas_data=None, gps_data=None):
        """
        Visualize predictions on the frame.
        
        Args:
            frame: The original image frame
            predictions: List of prediction dictionaries
            gas_data: Optional gas sensor data to display
            gps_data: Optional GPS data to display
            
        Returns:
            Processed frame with visualizations
        """
        processed_frame = frame.copy()
        
        # Add timestamp
        timestamp = datetime.now().strftime("%H:%M:%S")
        cv2.putText(processed_frame, timestamp, (10, 30), 
                  cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
        
        # Add device label
        cv2.putText(processed_frame, "WASTE DETECTION PI", (10, 70), 
                  cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 0, 0), 2)
        
        # Add gas sensor status if available
        if gas_data:
            gas_status = "GAS DETECTED!" if gas_data.get('gas_detected', False) else "Gas Normal"
            gas_color = (0, 0, 255) if gas_data.get('gas_detected', False) else (0, 255, 0)
            cv2.putText(processed_frame, gas_status, (10, 110), 
                      cv2.FONT_HERSHEY_SIMPLEX, 1, gas_color, 2)
        
        # Draw predictions
        for pred in predictions:
            # Extract coordinates
            x_rel = pred['x']
            y_rel = pred['y']
            width_rel = pred['width']
            height_rel = pred['height']
            
            # Convert to absolute coordinates
            img_height, img_width = processed_frame.shape[:2]
            x = int(x_rel * img_width)
            y = int(y_rel * img_height)
            w = int(width_rel * img_width)
            h = int(height_rel * img_height)
            
            # Draw bounding box
            cv2.rectangle(processed_frame, (x - w//2, y - h//2), (x + w//2, y + h//2), (0, 255, 0), 2)
            
            # Add label
            class_name = pred['class']
            confidence = pred['confidence']
            label = f"{class_name} {confidence:.2f}"
            cv2.putText(processed_frame, label, (x - w//2, y - h//2 - 10), 
                      cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
        
        return processed_frame
