import tflite_runtime.interpreter as tflite
import numpy as np
import time
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_gpu_acceleration():
    try:
        # Create a dummy model path
        model_path = "models/best_integer_quant.tflite"
        
        # Try to load the GPU delegate
        try:
            from tflite_runtime.interpreter import load_delegate
            gpu_delegate = load_delegate('libedgetpu.so.1.0')
            logger.info("Successfully loaded GPU delegate")
        except Exception as e:
            logger.error(f"Failed to load GPU delegate: {e}")
            return False
            
        # Create interpreter with GPU delegate
        interpreter = tflite.Interpreter(
            model_path=model_path,
            experimental_delegates=[gpu_delegate]
        )
        
        # Allocate tensors
        interpreter.allocate_tensors()
        
        # Get input and output details
        input_details = interpreter.get_input_details()
        output_details = interpreter.get_output_details()
        
        logger.info("GPU acceleration test successful")
        logger.info(f"Input details: {input_details}")
        logger.info(f"Output details: {output_details}")
        
        return True
        
    except Exception as e:
        logger.error(f"Error during GPU acceleration test: {e}")
        return False

if __name__ == "__main__":
    test_gpu_acceleration() 