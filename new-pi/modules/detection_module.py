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
import platform
import os
from tflite_runtime.interpreter import load_delegate
import torch

# Configure logger
logger = logging.getLogger('detection-module')
logger.setLevel(logging.DEBUG)  # Set to DEBUG for maximum visibility

# Add a handler if none exists
if not logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)

# Check if running on Raspberry Pi
IS_RASPBERRY_PI = platform.machine().startswith('arm')

# GPU acceleration settings
GPU_ENABLED = IS_RASPBERRY_PI and os.getenv('USE_GPU', '1') == '1'

# Log system information
logger.info(f"Running on Raspberry Pi: {IS_RASPBERRY_PI}")
logger.info(f"GPU acceleration enabled: {GPU_ENABLED}")

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
        self.max_predictions = 300  # Matches max_det from training
        self.frame_buffer_size = 3  # Reduced from 10 to minimize latency
        self.frame_buffer = []
        self.frame_buffer_lock = threading.Lock()
        self.processing_thread = None
        self.running = False
        self.interpreter = None
        self.input_details = None
        self.output_details = None
        self.processing_event = threading.Event()
        self.input_size = (640, 640)  # YOLOv8 default input size
        self.max_detections = 300  # Maximum number of detections to process
        
        # Class-specific confidence thresholds
        self.confidence_thresholds = {
            'plastic': 0.10,    # Lower threshold for better recall
            'glass': 0.10,      # Lower threshold for better recall
            'paper': 0.10,      # Lower threshold for better recall
            'metal': 0.10,      # Lower threshold for better recall
            'organic': 0.10     # Lower threshold for better recall
        }
        self.default_confidence_threshold = 0.10  # Lower general threshold
        self.iou_threshold = 0.6  # Matches training IoU threshold
        self.frame_skip = 3  # Process every 3rd frame at 15 FPS
        self.frame_counter = 0
        
        # Define class names for YOLO model
        self.class_names = [
            'person', 'bicycle', 'car', 'motorcycle', 'airplane', 'bus', 'train', 'truck', 'boat',
            'traffic light', 'fire hydrant', 'stop sign', 'parking meter', 'bench', 'bird', 'cat', 'dog',
            'horse', 'sheep', 'cow', 'elephant', 'bear', 'zebra', 'giraffe', 'backpack', 'umbrella',
            'handbag', 'tie', 'suitcase', 'frisbee', 'skis', 'snowboard', 'sports ball', 'kite',
            'baseball bat', 'baseball glove', 'skateboard', 'surfboard', 'tennis racket', 'bottle',
            'wine glass', 'cup', 'fork', 'knife', 'spoon', 'bowl', 'banana', 'apple', 'sandwich',
            'orange', 'broccoli', 'carrot', 'hot dog', 'pizza', 'donut', 'cake', 'chair', 'couch',
            'potted plant', 'bed', 'dining table', 'toilet', 'tv', 'laptop', 'mouse', 'remote',
            'keyboard', 'cell phone', 'microwave', 'oven', 'toaster', 'sink', 'refrigerator', 'book',
            'clock', 'vase', 'scissors', 'teddy bear', 'hair drier', 'toothbrush'
        ]
        
        # Initialize TFLite model
        try:
            import os
            current_dir = os.path.dirname(os.path.abspath(__file__))
            model_path = os.path.join(current_dir, '..', 'models', 'best_integer_quant.tflite')
            logger.info(f"Current directory: {current_dir}")
            logger.info(f"Attempting to load model from: {model_path}")
            
            if not os.path.exists(model_path):
                raise FileNotFoundError(f"Model file not found at: {model_path}")
            
            logger.info("Model file found, checking file size...")
            model_size = os.path.getsize(model_path)
            logger.info(f"Model file size: {model_size / (1024*1024):.2f} MB")
            
            # Configure acceleration for Pi 5
            try:
                logger.info("Attempting to enable XNNPACK acceleration for Pi 5...")
                
                # Configure XNNPACK delegate options
                delegate_options = {
                    'num_threads': 4,  # Use all cores on Pi 5
                    'enable_fp16': True  # Enable FP16 for better performance
                }
                
                # Create interpreter with XNNPACK delegate
                xnnpack_delegate = load_delegate('libxnnpack.so')
                self.interpreter = tflite.Interpreter(
                    model_path=model_path,
                    experimental_delegates=[xnnpack_delegate],
                    num_threads=4  # Use all cores
                )
                logger.info("XNNPACK acceleration enabled with Pi-optimized settings")
                
            except Exception as e:
                logger.warning(f"Failed to enable Pi acceleration: {e}")
                logger.info("Falling back to default CPU inference")
                self.interpreter = tflite.Interpreter(
                    model_path=model_path,
                    num_threads=4  # Use all cores
                )
                logger.info("CPU acceleration enabled with multi-threading")
            
            logger.info("Allocating tensors...")
            # Allocate tensors
            self.interpreter.allocate_tensors()
            
            # Get input and output details
            self.input_details = self.interpreter.get_input_details()
            self.output_details = self.interpreter.get_output_details()
            
            # Log detailed model information
            logger.info("Model loaded successfully")
            logger.info(f"Input details:")
            for detail in self.input_details:
                logger.info(f"  - Name: {detail['name']}")
                logger.info(f"  - Shape: {detail['shape']}")
                logger.info(f"  - Type: {detail['dtype']}")
                logger.info(f"  - Quantization: {detail.get('quantization', 'None')}")
            
            logger.info(f"Output details:")
            for detail in self.output_details:
                logger.info(f"  - Name: {detail['name']}")
                logger.info(f"  - Shape: {detail['shape']}")
                logger.info(f"  - Type: {detail['dtype']}")
                logger.info(f"  - Quantization: {detail.get('quantization', 'None')}")
            
            # Test inference with dummy data
            logger.info("Testing model inference with dummy data...")
            dummy_input = np.zeros((1, 640, 640, 3), dtype=np.float32)
            self.interpreter.set_tensor(self.input_details[0]['index'], dummy_input)
            self.interpreter.invoke()
            logger.info("Dummy inference test successful")
            
        except Exception as e:
            logger.error(f"Error loading TFLite model: {e}")
            logger.exception("Full traceback:")
            raise

    def start(self):
        """Start the detection processing thread."""
        if self.running:
            logger.warning("Detection module is already running")
            return
        
        logger.info("Starting detection processing thread...")
        self.running = True
        self.processing_thread = threading.Thread(target=self._process_frames, daemon=True)
        self.processing_thread.start()
        logger.info("Detection processing thread started")
        
        # Verify thread is running
        time.sleep(0.1)  # Give it a moment to start
        if self.processing_thread.is_alive():
            logger.info("Detection processing thread is running")
        else:
            logger.error("Detection processing thread failed to start")

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
        """
        Add a new frame to the processing buffer.
        
        Args:
            frame: The new frame to process
        """
        try:
            # Implement frame skipping
            self.frame_counter += 1
            if self.frame_counter % self.frame_skip != 0:
                return

            # Check buffer size
            with self.frame_buffer_lock:
                if len(self.frame_buffer) >= self.frame_buffer_size:
                    # Drop oldest frame
                    self.frame_buffer.pop(0)
                    logger.debug("Dropped oldest frame due to buffer overflow")
                
                # Add new frame
                self.frame_buffer.append(frame)
                buffer_size = len(self.frame_buffer)
                
            # Set processing event to wake up processing thread
            self.processing_event.set()
                
        except Exception as e:
            logger.error(f"Error adding frame to buffer: {e}")
            logger.exception("Full traceback:")

    def _process_frames(self):
        """Process frames from the buffer."""
        logger.info("Detection processing thread started")
        
        while self.running:
            try:
                # Wait for new frames
                self.processing_event.wait()
                if not self.running:
                    break
                    
                # Get frame from buffer
                with self.frame_buffer_lock:
                    if not self.frame_buffer:
                        continue
                    frame = self.frame_buffer.pop(0)
                    remaining = len(self.frame_buffer)
                
                # Process frame using detect method
                detections = self.detect(frame)
                
                # Clear processing event
                self.processing_event.clear()
                
            except Exception as e:
                logger.error(f"Error processing frame: {str(e)}")
                self.processing_event.clear()
                continue

    def get_latest_predictions(self):
        """Get the most recent detection predictions."""
        with self.prediction_lock:
            return self.latest_predictions.copy()
    
    def _map_to_waste_class(self, class_id, confidence):
        """
        Map a detected class ID to a waste category.
        
        Args:
            class_id: The detected class ID
            confidence: The detection confidence
            
        Returns:
            tuple: (waste_category, confidence) or (None, None) if no mapping found
        """
        # Only process classes that are in our waste mapping
        if class_id not in [id for ids in WASTE_CLASSES.values() for id in ids]:
            return None, None
            
        # Map class ID to waste category
        for category, class_ids in WASTE_CLASSES.items():
            if class_id in class_ids:
                # Check if confidence meets category-specific threshold
                threshold = self.confidence_thresholds.get(category, self.default_confidence_threshold)
                if confidence >= threshold:
                    return category, confidence
                else:
                    return None, None
                    
        return None, None
    
    def detect(self, image):
        """Detect waste in image."""
        try:
            # Preprocess image
            logger.info("Preprocessing image...")
            preprocessed = self._preprocess(image)
            logger.info(f"Preprocessed image shape: {preprocessed.shape}")
            
            # Get model output
            logger.info("Running model inference...")
            self.interpreter.set_tensor(self.input_details[0]['index'], preprocessed)
            self.interpreter.invoke()
            output_data = self.interpreter.get_tensor(self.output_details[0]['index'])
            logger.info(f"Raw model output shape: {output_data.shape}")
            
            # Process detections
            logger.info("Processing detections...")
            detections = self._process_detections(output_data, image.shape)
            
            # Store latest predictions
            with self.prediction_lock:
                self.latest_predictions = detections
            
            # Log final results
            logger.info(f"Detection complete. Found {len(detections)} valid detections")
            for det in detections:
                logger.info(f"Detection: class={det['class']}, confidence={det['confidence']:.3f}")
            
            # Call detection callback if any detections found
            if detections and self.detection_callback:
                try:
                    # Create a copy of the frame for the callback
                    callback_frame = image.copy() if image is not None else None
                    self.detection_callback(callback_frame, predictions=detections)
                except TypeError:
                    # If the callback doesn't accept predictions parameter, try without it
                    self.detection_callback(detections)
                except Exception as e:
                    logger.error(f"Error in detection callback: {e}")
                    logger.exception("Full traceback:")
            
            return detections
            
        except Exception as e:
            logger.error(f"Error in detect: {str(e)}")
            logger.error(f"Error type: {type(e)}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
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
        if frame is None or frame.size == 0:
            logger.warning("Invalid frame received for processing")
            return None
            
        try:
            processed_frame = frame.copy()
            
            # Log frame processing
            logger.info(f"Processing frame with {len(predictions)} predictions")
            
            # Add timestamp
            timestamp = datetime.now().strftime("%H:%M:%S")
            cv2.putText(processed_frame, timestamp, (10, 30), 
                      cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
            
            # Add device label
            cv2.putText(processed_frame, "WASTE DETECTION PI", (10, 70), 
                      cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 0, 0), 2)
            
            # Add detection count
            cv2.putText(processed_frame, f"Detections: {len(predictions)}", (10, 110), 
                      cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 255), 2)
            
            # Add gas sensor status if available
            if gas_data:
                gas_status = "GAS DETECTED!" if gas_data.get('gas_detected', False) else "Gas Normal"
                gas_color = (0, 0, 255) if gas_data.get('gas_detected', False) else (0, 255, 0)
                cv2.putText(processed_frame, gas_status, (10, 150), 
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
                
                # Log detection visualization
                logger.info(f"Drawing detection: {pred['class']} at ({x}, {y}) with confidence {pred['confidence']:.2f}")
                
                # Draw bounding box with different colors for different classes
                color = {
                    'plastic': (0, 255, 0),    # Green
                    'glass': (255, 0, 0),      # Blue
                    'paper': (0, 0, 255),      # Red
                    'metal': (255, 255, 0),    # Yellow
                    'organic': (255, 0, 255)   # Magenta
                }.get(pred['class'], (0, 255, 0))  # Default to green
                
                # Draw thicker bounding box
                cv2.rectangle(processed_frame, 
                            (x - w//2, y - h//2), 
                            (x + w//2, y + h//2), 
                            color, 3)  # Increased thickness to 3
                
                # Add label with larger font and better visibility
                class_name = pred['class'].upper()  # Make class name uppercase
                confidence = pred['confidence']
                label = f"{class_name} {confidence:.2f}"
                
                # Calculate label position
                label_x = x - w//2
                label_y = y - h//2 - 10
                
                # Draw label background with class-specific color
                (label_w, label_h), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 2)
                cv2.rectangle(processed_frame, 
                            (label_x, label_y - label_h - 5),
                            (label_x + label_w, label_y + 5),
                            color, -1)  # Filled rectangle with class color
                
                # Draw label text in white for better contrast
                cv2.putText(processed_frame, label, (label_x, label_y), 
                          cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
            
            # Log final frame info
            logger.info(f"Processed frame shape: {processed_frame.shape}")
            return processed_frame
            
        except Exception as e:
            logger.error(f"Error processing frame: {e}")
            logger.exception("Full traceback:")
            return None
        finally:
            # Clean up memory
            if 'processed_frame' in locals() and processed_frame is not frame:
                del processed_frame

    def _preprocess(self, frame):
        """Preprocess frame for model input."""
        try:
            start_time = time.time()
            
            # Log input frame details
            logger.info(f"Input frame shape: {frame.shape}, dtype: {frame.dtype}")
            logger.info(f"Input frame range: [{np.min(frame)}, {np.max(frame)}]")
            
            # Ensure frame is in BGR format (OpenCV default)
            if len(frame.shape) != 3 or frame.shape[2] != 3:
                logger.error(f"Invalid frame format: {frame.shape}")
                raise ValueError("Frame must be BGR with 3 channels")
            
            # Get model's expected input shape
            input_shape = self.input_details[0]['shape']
            logger.info(f"Model expected input shape: {input_shape}")
            
            # Convert BGR to RGB (YOLOv8 expects RGB)
            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            
            # Calculate letterbox padding
            input_height, input_width = input_shape[1:3]
            frame_height, frame_width = frame.shape[:2]
            
            # Calculate scaling factor to maintain aspect ratio
            scale = min(input_width/frame_width, input_height/frame_height)
            new_width = int(frame_width * scale)
            new_height = int(frame_height * scale)
            
            # Calculate padding
            pad_w = (input_width - new_width) // 2
            pad_h = (input_height - new_height) // 2
            
            # Create letterboxed image
            # First resize maintaining aspect ratio
            resized = cv2.resize(frame_rgb, (new_width, new_height), interpolation=cv2.INTER_LINEAR)
            
            # Create padded image with gray padding (114 is YOLOv8's default)
            padded = np.full((input_height, input_width, 3), 114, dtype=np.uint8)
            padded[pad_h:pad_h+new_height, pad_w:pad_w+new_width] = resized
            
            logger.info(f"Resized shape: {padded.shape}")
            
            # Get quantization parameters
            input_type = self.input_details[0]['dtype']
            quant_params = self.input_details[0].get('quantization_parameters', None)
            
            logger.info(f"Input type: {input_type}")
            if quant_params:
                logger.info(f"Quantization parameters: {quant_params}")
            
            # Handle quantization based on input type
            if input_type == np.uint8:  # Quantized model
                if quant_params and 'scales' in quant_params and 'zero_points' in quant_params:
                    scale = quant_params['scales'][0]
                    zero_point = quant_params['zero_points'][0]
                    logger.info(f"Applying quantization: scale={scale}, zero_point={zero_point}")
                    
                    # Normalize to [0, 1]
                    preprocessed = padded.astype(np.float32) / 255.0
                    # Quantize
                    preprocessed = preprocessed / scale + zero_point
                    # Convert to uint8
                    preprocessed = np.clip(preprocessed, 0, 255).astype(np.uint8)
                else:
                    logger.warning("Model expects uint8 input but quantization parameters are missing")
                    preprocessed = padded.astype(np.uint8)
            else:  # Float model
                # Normalize to [0, 1]
                preprocessed = padded.astype(np.float32) / 255.0
            
            # Add batch dimension
            preprocessed = np.expand_dims(preprocessed, axis=0)
            logger.info(f"Final preprocessed shape: {preprocessed.shape}")
            logger.info(f"Final preprocessed dtype: {preprocessed.dtype}")
            logger.info(f"Final preprocessed range: [{np.min(preprocessed)}, {np.max(preprocessed)}]")
            
            process_time = time.time() - start_time
            logger.info(f"Preprocessing time: {process_time*1000:.1f}ms")
            
            return preprocessed
            
        except Exception as e:
            logger.error(f"Preprocessing error: {str(e)}")
            logger.exception("Full traceback:")
            raise

    def _postprocess(self, output_data, frame_shape):
        """Postprocess model output using GPU acceleration when possible."""
        try:
            # Get output shape and validate
            if len(output_data.shape) != 3:
                logger.error(f"Invalid output shape: {output_data.shape}")
                return []
                
            batch_size, num_classes, num_boxes = output_data.shape
            logger.info(f"Processing output tensor with shape: {output_data.shape}")
            logger.info(f"Number of raw detections: {num_boxes}")
            logger.info(f"Detection data range: [{np.min(output_data)}, {np.max(output_data)}]")
            
            # YOLOv8 output format: [xywh, conf, class_scores]
            # First 4 values are box coordinates (x,y,w,h)
            boxes = output_data[0, :4, :].T  # [num_boxes, 4]
            # 5th value is objectness score
            confidences = output_data[0, 4, :]  # [num_boxes]
            # Remaining values are class scores
            class_scores = output_data[0, 5:, :]  # [num_classes-5, num_boxes]
            
            # Get class indices and confidences
            class_indices = np.argmax(class_scores, axis=0)
            class_confidences = np.max(class_scores, axis=0)
            
            # Combine objectness and class confidence
            final_confidences = confidences * class_confidences
            
            # Filter detections by confidence
            detections = []
            for idx in range(num_boxes):
                confidence = float(final_confidences[idx])
                class_id = int(class_indices[idx])
                
                # Map to waste class and check confidence threshold
                waste_class, waste_confidence = self._map_to_waste_class(class_id, confidence)
                if waste_class:
                    # Get box coordinates (already normalized)
                    x, y, w, h = boxes[idx]
                    
                    # Validate coordinates
                    if not all(0 <= val <= 1 for val in [x, y, w, h]):
                        logger.warning(f"Invalid coordinates: x={x}, y={y}, w={w}, h={h}")
                        continue
                    
                    # Create detection object
                    detection = {
                        'class': waste_class,
                        'confidence': waste_confidence,
                        'x': float(x),
                        'y': float(y),
                        'width': float(w),
                        'height': float(h)
                    }
                    detections.append(detection)
                    logger.info(f"Added detection: {detection}")
            
            # Apply NMS if we have multiple detections
            if len(detections) > 1:
                boxes_for_nms = np.array([[d['x'], d['y'], d['width'], d['height']] for d in detections])
                confidences_for_nms = np.array([d['confidence'] for d in detections])
                keep_indices = self._apply_nms(boxes_for_nms, confidences_for_nms)
                detections = [detections[i] for i in keep_indices]
            
            logger.info(f"Total predictions found: {len(detections)}")
            return detections
            
        except Exception as e:
            logger.error(f"Postprocessing error: {str(e)}")
            logger.exception("Full traceback:")
            return []

    def _convert_boxes_to_image_coords(self, boxes, frame_shape):
        """Convert normalized box coordinates to image coordinates."""
        try:
            img_height, img_width = frame_shape[:2]
            converted_boxes = boxes.copy()
            
            # Convert from [x, y, w, h] to [x1, y1, x2, y2]
            converted_boxes[:, 0] = (boxes[:, 0] - boxes[:, 2] / 2) * img_width  # x1
            converted_boxes[:, 1] = (boxes[:, 1] - boxes[:, 3] / 2) * img_height  # y1
            converted_boxes[:, 2] = (boxes[:, 0] + boxes[:, 2] / 2) * img_width  # x2
            converted_boxes[:, 3] = (boxes[:, 1] + boxes[:, 3] / 2) * img_height  # y2
            
            return converted_boxes
            
        except Exception as e:
            logger.error(f"Error converting box coordinates: {str(e)}")
            return boxes

    def _apply_nms(self, boxes, confidences, iou_threshold=None):
        """Apply Non-Maximum Suppression to filter overlapping boxes."""
        try:
            if len(boxes) == 0:
                return []
            
            # Use instance iou_threshold if none provided
            if iou_threshold is None:
                iou_threshold = self.iou_threshold
                
            # Convert boxes to [x1, y1, x2, y2] format if not already
            x1 = boxes[:, 0]
            y1 = boxes[:, 1]
            x2 = boxes[:, 2]
            y2 = boxes[:, 3]
            
            # Calculate areas
            areas = (x2 - x1) * (y2 - y1)
            
            # Sort by confidence
            indices = np.argsort(confidences)[::-1]
            
            keep_indices = []
            while len(indices) > 0:
                # Pick the box with highest confidence
                current = indices[0]
                keep_indices.append(current)
                
                if len(indices) == 1:
                    break
                    
                # Calculate IoU with remaining boxes
                xx1 = np.maximum(x1[current], x1[indices[1:]])
                yy1 = np.maximum(y1[current], y1[indices[1:]])
                xx2 = np.minimum(x2[current], x2[indices[1:]])
                yy2 = np.minimum(y2[current], y2[indices[1:]])
                
                w = np.maximum(0, xx2 - xx1)
                h = np.maximum(0, yy2 - yy1)
                intersection = w * h
                
                union = areas[current] + areas[indices[1:]] - intersection
                iou = intersection / union
                
                # Keep boxes with IoU less than threshold
                mask = iou <= iou_threshold
                indices = indices[1:][mask]
            
            # Limit to max_predictions
            if len(keep_indices) > self.max_predictions:
                keep_indices = keep_indices[:self.max_predictions]
            
            return keep_indices
            
        except Exception as e:
            logger.error(f"Error applying NMS: {str(e)}")
            return list(range(min(len(boxes), self.max_predictions)))  # Return limited indices if NMS fails

    def _process_detections(self, output, image_shape):
        """Process model output into detections."""
        try:
            # Get output shape and validate
            if len(output.shape) != 3:
                logger.error(f"Invalid output shape: {output.shape}")
                return []
                
            batch_size, num_classes, num_boxes = output.shape
            logger.info(f"Processing output tensor with shape: {output.shape}")
            logger.info(f"Number of raw detections: {num_boxes}")
            logger.info(f"Detection data range: [{np.min(output)}, {np.max(output)}]")
            
            # YOLOv8 output format: [xywh, conf, class_scores]
            # First 4 values are box coordinates (x,y,w,h)
            boxes = output[0, :4, :].T  # [num_boxes, 4]
            # 5th value is objectness score
            confidences = output[0, 4, :]  # [num_boxes]
            # Remaining values are class scores
            class_scores = output[0, 5:, :]  # [num_classes-5, num_boxes]
            
            # Log raw confidence ranges
            logger.info(f"Objectness confidence range: [{np.min(confidences):.3f}, {np.max(confidences):.3f}]")
            logger.info(f"Class scores range: [{np.min(class_scores):.3f}, {np.max(class_scores):.3f}]")
            
            # Get class indices and confidences
            class_indices = np.argmax(class_scores, axis=0)
            class_confidences = np.max(class_scores, axis=0)
            
            # For YOLOv8, we should use class confidence directly
            # The objectness score is already incorporated into the class scores
            final_confidences = class_confidences
            
            # Get all valid waste class IDs
            valid_waste_ids = [id for ids in WASTE_CLASSES.values() for id in ids]
            
            # Log only waste-related detections
            logger.info("Top 5 waste-related detections:")
            waste_detections = []
            for idx in range(num_boxes):
                class_id = int(class_indices[idx])
                if class_id in valid_waste_ids:
                    class_name = self.class_names[class_id]
                    confidence = float(final_confidences[idx])
                    waste_detections.append((idx, class_name, confidence))
            
            # Sort by confidence and take top 5
            waste_detections.sort(key=lambda x: x[2], reverse=True)
            for idx, class_name, confidence in waste_detections[:5]:
                logger.info(f"  Class: {class_name} (ID: {class_indices[idx]})")
                logger.info(f"    Objectness: {confidences[idx]:.3f}")
                logger.info(f"    Class confidence: {class_confidences[idx]:.3f}")
                logger.info(f"    Final confidence: {confidence:.3f}")
            
            # Filter detections by confidence and waste class
            detections = []
            for idx in range(num_boxes):
                confidence = float(final_confidences[idx])
                class_id = int(class_indices[idx])
                
                # Only process waste classes
                if class_id not in valid_waste_ids:
                    continue
                
                # Only process if confidence is above minimum threshold
                if confidence < 0.01:  # Minimum threshold to avoid processing noise
                    continue
                
                # Map to waste class and check confidence threshold
                waste_class, waste_confidence = self._map_to_waste_class(class_id, confidence)
                if waste_class:
                    # Get box coordinates (already normalized)
                    x, y, w, h = boxes[idx]
                    
                    # Validate coordinates
                    if not all(0 <= val <= 1 for val in [x, y, w, h]):
                        logger.warning(f"Invalid coordinates: x={x}, y={y}, w={w}, h={h}")
                        continue
                    
                    # Create detection object
                    detection = {
                        'class': waste_class,
                        'confidence': waste_confidence,
                        'x': float(x),
                        'y': float(y),
                        'width': float(w),
                        'height': float(h)
                    }
                    detections.append(detection)
                    logger.info(f"Added waste detection: {detection}")
            
            # Apply NMS if we have multiple detections
            if len(detections) > 1:
                boxes_for_nms = np.array([[d['x'], d['y'], d['width'], d['height']] for d in detections])
                confidences_for_nms = np.array([d['confidence'] for d in detections])
                keep_indices = self._apply_nms(boxes_for_nms, confidences_for_nms)
                detections = [detections[i] for i in keep_indices]
            
            logger.info(f"Total waste predictions found: {len(detections)}")
            return detections
            
        except Exception as e:
            logger.error(f"Error processing detections: {str(e)}")
            logger.exception("Full traceback:")
            return []
