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
        self.max_predictions = 50  # Reduced from 100 to save memory
        self.frame_buffer_size = 3  # Reduced from 10 to minimize latency
        self.frame_buffer = []
        self.frame_buffer_lock = threading.Lock()
        self.processing_thread = None
        self.running = False
        self.interpreter = None
        self.input_details = None
        self.output_details = None
        self.processing_event = threading.Event()
        self.confidence_threshold = 0.5  # Increased from 0.3 for better performance
        self.frame_skip = 2  # Process every 2nd frame
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
            
            # Configure GPU acceleration if available
            if GPU_ENABLED:
                try:
                    logger.info("Attempting to enable GPU acceleration for Pi 5...")
                    
                    # Configure delegate options for Pi's GPU
                    delegate_options = {
                        'num_threads': 4,
                        'max_delegation': 1,  # Ensure we use GPU when possible
                        'allow_fp16': True,   # Enable FP16 for better performance
                        'experimental_flags': [],
                        'max_partitions': 3,
                    }
                    
                    # Try to load the VideoCore delegate
                    try:
                        from tflite_runtime.interpreter import load_delegate
                        gpu_delegate = load_delegate('libvx_delegate.so')
                        logger.info("VideoCore GPU delegate loaded successfully")
                    except Exception as delegate_error:
                        logger.warning(f"Could not load VideoCore delegate: {delegate_error}")
                        logger.info("Trying alternative GPU delegate...")
                        try:
                            gpu_delegate = load_delegate('libOpenVX.so')
                            logger.info("OpenVX delegate loaded successfully")
                        except Exception as openvx_error:
                            logger.warning(f"Could not load OpenVX delegate: {openvx_error}")
                            raise Exception("No GPU delegate available")
                    
                    # Create interpreter with GPU delegate
                    self.interpreter = tflite.Interpreter(
                        model_path=model_path,
                        experimental_delegates=[gpu_delegate],
                        num_threads=4  # Use all cores on Pi 5
                    )
                    logger.info("GPU acceleration enabled with Pi-optimized settings")
                    
                except Exception as e:
                    logger.warning(f"Failed to enable Pi GPU acceleration: {e}")
                    logger.info("Falling back to optimized CPU inference")
                    # Try multi-threaded CPU inference with NEON
                    self.interpreter = tflite.Interpreter(
                        model_path=model_path,
                        num_threads=4  # Use all cores
                    )
                    logger.info("CPU acceleration enabled with multi-threading")
            else:
                logger.info("GPU acceleration disabled, using CPU inference with threading")
                self.interpreter = tflite.Interpreter(
                    model_path=model_path,
                    num_threads=4
                )
            
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
                
                # Process frame
                start_time = time.time()
                
                # Preprocess
                preprocess_start = time.time()
                input_data = self._preprocess(frame)
                preprocess_time = time.time() - preprocess_start
                
                # Inference
                inference_start = time.time()
                self.interpreter.set_tensor(self.input_details[0]['index'], input_data)
                self.interpreter.invoke()
                output_data = self.interpreter.get_tensor(self.output_details[0]['index'])
                inference_time = time.time() - inference_start
                
                # Postprocess
                postprocess_start = time.time()
                detections = self._postprocess(output_data, frame.shape)
                postprocess_time = time.time() - postprocess_start
                
                # Calculate total time
                total_time = time.time() - start_time
                
                # Log timing and results
                if detections:
                    logger.info(f"0: 640x640 {len(detections)} {' '.join(d['class'] for d in detections)}, {inference_time*1000:.1f}ms")
                else:
                    logger.info(f"0: 640x640 (no detections), {inference_time*1000:.1f}ms")
                    
                logger.info(f"Speed: {preprocess_time*1000:.1f}ms preprocess, {inference_time*1000:.1f}ms inference, {postprocess_time*1000:.1f}ms postprocess per image at shape (1, 3, 640, 640)")
                
                # Call detection callback if any detections found
                if detections and self.detection_callback:
                    try:
                        # Create a copy of the frame for the callback
                        callback_frame = frame.copy() if frame is not None else None
                        self.detection_callback(callback_frame, predictions=detections)
                    except TypeError:
                        # If the callback doesn't accept predictions parameter, try without it
                        self.detection_callback(detections)
                    except Exception as e:
                        logger.error(f"Error in detection callback: {e}")
                        logger.exception("Full traceback:")
                
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
        """Map YOLO class ID to waste category."""
        logger.info(f"Mapping class ID {class_id} with confidence {confidence:.3f}")
        for waste_class, class_ids in WASTE_CLASSES.items():
            if class_id in class_ids:
                logger.info(f"Mapped class ID {class_id} to waste class '{waste_class}'")
                return waste_class
        logger.info(f"No waste class mapping found for class ID {class_id}")
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
                total_start_time = time.time()
                
                # Log frame info
                logger.info(f"Processing frame: shape={frame.shape}, dtype={frame.dtype}")
                
                # Preprocess image
                preprocess_start = time.time()
                input_size = (640, 640)
                img = cv2.resize(frame, input_size)
                img = img.astype(np.float32)
                img = img / 255.0  # Normalize to [0,1]
                img = np.expand_dims(img, axis=0)
                preprocess_time = (time.time() - preprocess_start) * 1000  # Convert to ms
                logger.info(f"Preprocessed image: shape={img.shape}, dtype={img.dtype}, range=[{np.min(img):.3f}, {np.max(img):.3f}]")
                
                # Check input shape matches model's expected input
                expected_shape = self.input_details[0]['shape']
                if img.shape != tuple(expected_shape):
                    logger.error(f"Input shape mismatch. Expected {expected_shape}, got {img.shape}")
                    img = img.reshape(expected_shape)
                
                # Run inference
                self.interpreter.set_tensor(self.input_details[0]['index'], img)
                logger.info("Starting model inference")
                inference_start = time.time()
                self.interpreter.invoke()
                inference_time = (time.time() - inference_start) * 1000  # Convert to ms
                
                # Get output
                output = self.interpreter.get_tensor(self.output_details[0]['index'])
                
                # Process predictions
                postprocess_start = time.time()
                predictions = []
                img_height, img_width = frame.shape[:2]
                
                # Log raw output for debugging
                logger.info(f"Number of raw detections: {len(output[0])}")
                
                # YOLO output format: [x, y, w, h, confidence, class_scores...]
                for detection in output[0]:
                    confidence = detection[4]
                    logger.info(f"Raw detection confidence: {confidence:.3f}")
                    
                    # Filter low confidence detections
                    if confidence < 0.3:  # Confidence threshold
                        logger.debug(f"Skipping detection with low confidence: {confidence:.3f}")
                        continue
                    
                    # Get class ID and confidence
                    class_id = np.argmax(detection[5:])
                    class_confidence = detection[5 + class_id]
                    logger.info(f"Found detection - Class ID: {class_id}, Confidence: {confidence:.3f}, Class Confidence: {class_confidence:.3f}")
                    
                    # Map to waste class
                    waste_class = self._map_to_waste_class(class_id, confidence)
                    if not waste_class:
                        logger.info(f"Class ID {class_id} not mapped to any waste class")
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
                
                postprocess_time = (time.time() - postprocess_start) * 1000  # Convert to ms
                total_time = (time.time() - total_start_time) * 1000  # Convert to ms
                
                # Log timing information
                logger.info(f"Speed: {preprocess_time:.1f}ms preprocess, {inference_time:.1f}ms inference, {postprocess_time:.1f}ms postprocess per image at shape {img.shape}")
                logger.info(f"Total processing time: {total_time:.1f}ms")
                logger.info(f"Detections: {len(predictions)} objects found")
                
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
        """Preprocess frame for model input using GPU acceleration when possible."""
        try:
            start_time = time.time()
            
            # Use GPU for image preprocessing if available
            if GPU_ENABLED:
                try:
                    # Move image to GPU memory
                    gpu_frame = cv2.cuda_GpuMat()
                    gpu_frame.upload(frame)
                    
                    # Resize on GPU
                    gpu_resized = cv2.cuda.resize(gpu_frame, (640, 640))
                    
                    # Convert to float32 on GPU
                    gpu_float = gpu_resized.convertTo(cv2.CV_32F, 1.0/255.0)
                    
                    # Download result back to CPU
                    preprocessed = gpu_float.download()
                    
                    # Add batch dimension
                    preprocessed = np.expand_dims(preprocessed, axis=0)
                    
                    logger.info("Preprocessing completed on GPU")
                except Exception as e:
                    logger.warning(f"GPU preprocessing failed, falling back to CPU: {e}")
                    # Fallback to CPU processing
                    resized = cv2.resize(frame, (640, 640), interpolation=cv2.INTER_LINEAR)
                    preprocessed = resized.astype(np.float32) / 255.0
                    preprocessed = np.expand_dims(preprocessed, axis=0)
            else:
                # CPU processing
                resized = cv2.resize(frame, (640, 640), interpolation=cv2.INTER_LINEAR)
                preprocessed = resized.astype(np.float32) / 255.0
                preprocessed = np.expand_dims(preprocessed, axis=0)
            
            # Log timing
            process_time = time.time() - start_time
            logger.info(f"Speed: {process_time*1000:.1f}ms preprocess")
            
            return preprocessed
            
        except Exception as e:
            logger.error(f"Preprocessing error: {str(e)}")
            raise

    def _postprocess(self, output_data, frame_shape):
        """Postprocess model output using GPU acceleration when possible."""
        try:
            # Get output shape
            batch_size, num_classes, num_boxes = output_data.shape
            
            # Move data to GPU if available
            if GPU_ENABLED:
                try:
                    import cupy as cp
                    # Transfer data to GPU
                    output_gpu = cp.asarray(output_data[0].T)
                    
                    # Get class scores and indices on GPU
                    class_scores_gpu = output_gpu[:, 4:]
                    class_indices_gpu = cp.argmax(class_scores_gpu, axis=1)
                    class_confidences_gpu = cp.max(class_scores_gpu, axis=1)
                    
                    # Filter by confidence threshold on GPU
                    mask_gpu = class_confidences_gpu > self.confidence_threshold
                    if not cp.any(mask_gpu):
                        return []
                    
                    # Get filtered boxes and scores
                    boxes_gpu = output_gpu[mask_gpu.get(), :4]
                    confidences_gpu = class_confidences_gpu[mask_gpu.get()]
                    indices_gpu = class_indices_gpu[mask_gpu.get()]
                    
                    # Convert to numpy for further processing
                    boxes = cp.asnumpy(boxes_gpu)
                    confidences = cp.asnumpy(confidences_gpu)
                    indices = cp.asnumpy(indices_gpu)
                    
                    logger.info("Postprocessing completed on GPU")
                except Exception as e:
                    logger.warning(f"GPU postprocessing failed, falling back to CPU: {e}")
                    # Fallback to CPU processing
                    output = output_data[0].T
                    class_scores = output[:, 4:]
                    class_indices = np.argmax(class_scores, axis=1)
                    class_confidences = np.max(class_scores, axis=1)
                    mask = class_confidences > self.confidence_threshold
                    if not np.any(mask):
                        return []
                    boxes = output[mask, :4]
                    confidences = class_confidences[mask]
                    indices = class_indices[mask]
            else:
                # CPU processing
                output = output_data[0].T
                class_scores = output[:, 4:]
                class_indices = np.argmax(class_scores, axis=1)
                class_confidences = np.max(class_scores, axis=1)
                mask = class_confidences > self.confidence_threshold
                if not np.any(mask):
                    return []
                boxes = output[mask, :4]
                confidences = class_confidences[mask]
                indices = class_indices[mask]
            
            # Convert boxes to image coordinates
            boxes = self._convert_boxes_to_image_coords(boxes, frame_shape)
            
            # Apply NMS
            keep_indices = self._apply_nms(boxes, confidences)
            if not keep_indices:
                return []
            
            # Create detection objects
            detections = []
            for idx in keep_indices:
                # Convert box coordinates to normalized format
                img_height, img_width = frame_shape[:2]
                bbox = boxes[idx]
                x = (bbox[0] + bbox[2]) / (2 * img_width)  # Center x
                y = (bbox[1] + bbox[3]) / (2 * img_height)  # Center y
                w = (bbox[2] - bbox[0]) / img_width  # Width
                h = (bbox[3] - bbox[1]) / img_height  # Height
                
                detections.append({
                    'class': self.class_names[indices[idx]],
                    'confidence': float(confidences[idx]),
                    'x': float(x),
                    'y': float(y),
                    'width': float(w),
                    'height': float(h)
                })
            
            return detections
            
        except Exception as e:
            logger.error(f"Postprocessing error: {str(e)}")
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

    def _apply_nms(self, boxes, confidences, iou_threshold=0.45):
        """Apply Non-Maximum Suppression to filter overlapping boxes."""
        try:
            if len(boxes) == 0:
                return []
                
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
            
            return keep_indices
            
        except Exception as e:
            logger.error(f"Error applying NMS: {str(e)}")
            return list(range(len(boxes)))  # Return all indices if NMS fails
