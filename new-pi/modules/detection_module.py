"""
Detection module for waste detection using YOLO model.
"""
import cv2
import numpy as np
import logging
import threading
from datetime import datetime
import tflite_runtime.interpreter as tflite
import time

logger = logging.getLogger('detection-module')

# Waste classification mapping
WASTE_CLASSES = {
    # Recyclable Plastics
    'plastic': [39, 41, 45],  # bottle, cup, bowl
    # Glass
    'glass': [40, 75],  # wine glass, vase
    # Paper/Cardboard
    'paper': [73],  # book
    # Metal
    'metal': [43, 44],  # knife, spoon
    # Organic Waste
    'organic': [46, 47, 49, 50, 51]  # banana, apple, orange, broccoli, carrot
}

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
        self.processing_lock = threading.Lock()
        self.max_predictions = 100  # Limit number of stored predictions
        self.frame_buffer_size = 10  # Limit frame buffer size
        self.frame_buffer = []
        self.frame_buffer_lock = threading.Lock()
        self.processing_thread = None
        self.running = False
        self.interpreter = None
        self.input_details = None
        self.output_details = None
        
        # Initialize TFLite model
        try:
            import os
            model_path = os.path.join(os.path.dirname(__file__), '..', 'models', 'best_integer_quant.tflite')
            logger.info(f"Loading model from: {model_path}")
            self.interpreter = tflite.Interpreter(model_path=model_path)
            self.interpreter.allocate_tensors()
            self.input_details = self.interpreter.get_input_details()
            self.output_details = self.interpreter.get_output_details()
            logger.info(f"Model input details: {self.input_details}")
            logger.info(f"Model output details: {self.output_details}")
            logger.info("TFLite model loaded successfully")
        except Exception as e:
            logger.error(f"Error loading TFLite model: {e}")
            raise

    def start(self):
        """Start the detection processing thread."""
        if self.running:
            logger.warning("Detection module is already running")
            return
        
        self.running = True
        self.processing_thread = threading.Thread(target=self._process_frames, daemon=True)
        self.processing_thread.start()
        logger.info("Detection processing thread started")

    def stop(self):
        """Clean up resources when stopping the module."""
        self.running = False
        
        # Wait for processing thread to finish
        if self.processing_thread:
            self.processing_thread.join(timeout=2.0)
            if self.processing_thread.is_alive():
                logger.warning("Detection processing thread did not stop cleanly")
        
        # Clear predictions
        with self.prediction_lock:
            self.latest_predictions = []
        
        # Clear frame buffer
        with self.frame_buffer_lock:
            self.frame_buffer.clear()
        
        # Clear interpreter
        if self.interpreter:
            try:
                self.interpreter = None
            except Exception as e:
                logger.error(f"Error clearing interpreter: {e}")
        
        logger.info("Detection module stopped")

    def add_frame(self, frame):
        """Add a frame to the processing buffer."""
        if frame is None or frame.size == 0:
            logger.warning("Invalid frame received")
            return
        
        with self.frame_buffer_lock:
            # Add new frame
            self.frame_buffer.append(frame)
            
            # Remove oldest frame if buffer is full
            if len(self.frame_buffer) > self.frame_buffer_size:
                self.frame_buffer.pop(0)

    def _process_frames(self):
        """Process frames from the buffer in a separate thread."""
        while self.running:
            try:
                # Get next frame from buffer
                with self.frame_buffer_lock:
                    if not self.frame_buffer:
                        time.sleep(0.1)  # Avoid tight loop
                        continue
                    frame = self.frame_buffer.pop(0)
                
                # Process frame
                predictions = self.detect_waste(frame)
                
                # Update latest predictions
                with self.prediction_lock:
                    self.latest_predictions = predictions[:self.max_predictions]
                
                # Call callback if predictions found
                if self.detection_callback and predictions:
                    self.detection_callback(frame, predictions)
                
            except Exception as e:
                logger.error(f"Error in frame processing thread: {e}")
                logger.exception("Full traceback:")
                time.sleep(0.1)  # Avoid tight loop on errors

    def get_latest_predictions(self):
        """Get the most recent detection predictions."""
        with self.prediction_lock:
            return self.latest_predictions.copy()
    
    def _map_to_waste_class(self, class_id, confidence):
        """Map YOLO class ID to waste category."""
        for waste_class, class_ids in WASTE_CLASSES.items():
            if class_id in class_ids:
                return waste_class
        return None
    
    def detect_waste(self, frame):
        """
        Detect waste in the provided frame using YOLO model.
        
        Args:
            frame: The image frame to process
            
        Returns:
            List of prediction dictionaries
        """
        if frame is None or frame.size == 0:
            logger.warning("Invalid frame received")
            return []
            
        try:
            with self.processing_lock:
                # Log frame info
                logger.debug(f"Input frame shape: {frame.shape}")
                
                # Preprocess image
                input_size = (640, 640)
                img = cv2.resize(frame, input_size)
                img = img.astype(np.float32)
                img = img / 255.0  # Normalize to [0,1]
                img = np.expand_dims(img, axis=0)
                logger.debug(f"Preprocessed image shape: {img.shape}")
                
                # Check input shape matches model's expected input
                expected_shape = self.input_details[0]['shape']
                if img.shape != tuple(expected_shape):
                    logger.error(f"Input shape mismatch. Expected {expected_shape}, got {img.shape}")
                    img = img.reshape(expected_shape)
                
                # Run inference
                self.interpreter.set_tensor(self.input_details[0]['index'], img)
                logger.debug("Starting model inference")
                self.interpreter.invoke()
                logger.debug("Model inference completed")
                
                # Get output
                output = self.interpreter.get_tensor(self.output_details[0]['index'])
                logger.debug(f"Model output shape: {output.shape}")
                
                # Process predictions
                predictions = []
                img_height, img_width = frame.shape[:2]
                
                # YOLO output format: [x, y, w, h, confidence, class_scores...]
                for detection in output[0]:
                    confidence = detection[4]
                    
                    # Filter low confidence detections
                    if confidence < 0.5:  # Confidence threshold
                        continue
                    
                    # Get class ID
                    class_id = np.argmax(detection[5:])
                    class_confidence = detection[5 + class_id]
                    logger.debug(f"Found detection - Class ID: {class_id}, Confidence: {confidence:.2f}, Class Confidence: {class_confidence:.2f}")
                    
                    # Map to waste class
                    waste_class = self._map_to_waste_class(class_id, confidence)
                    if not waste_class:
                        continue
                    
                    # Get normalized coordinates
                    x, y, w, h = detection[0:4]
                    
                    # Create prediction object
                    prediction = {
                        'class': waste_class,
                        'confidence': float(confidence),
                        'x': float(x),
                        'y': float(y),
                        'width': float(w),
                        'height': float(h)
                    }
                    predictions.append(prediction)
                    logger.info(f"Added prediction: {prediction}")
                
                return predictions
                
        except Exception as e:
            logger.error(f"Error in waste detection: {e}")
            logger.exception("Full traceback:")
            return []
        finally:
            # Clean up memory
            if 'img' in locals():
                del img
            if 'output' in locals():
                del output
    
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
        if frame is None or frame.size == 0:
            logger.warning("Invalid frame received for processing")
            return None
            
        try:
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
            
        except Exception as e:
            logger.error(f"Error processing frame: {e}")
            logger.exception("Full traceback:")
            return None
        finally:
            # Clean up memory
            if 'processed_frame' in locals() and processed_frame is not frame:
                del processed_frame
