from ultralytics import YOLO
import onnx
import subprocess
import os

def main():
    model = YOLO('yolov8n.pt')  # Using nano model for edge deployment
    path = 'TACO-dataset-2/data.yaml'
    results = model.train(
        epochs=200,  # Increased epochs for better convergence
        imgsz=640,   # Increased image size for better detection
        batch=8,     # Reduced batch size for better generalization
        optimizer='AdamW',
        lr0=0.0005,  # Reduced initial learning rate
        lrf=0.01,    # Learning rate final
        momentum=0.937,  # Added momentum
        weight_decay=0.0005,  # Added weight decay
        warmup_epochs=3,  # Added warmup epochs
        warmup_momentum=0.8,  # Added warmup momentum
        warmup_bias_lr=0.1,  # Added warmup bias learning rate
        box=7.5,     # Box loss gain
        cls=0.5,     # Class loss gain
        dfl=1.5,     # DFL loss gain
        amp=True,    # Mixed precision training
        mosaic=0.7,  # Increased mosaic probability
        mixup=0.1,   # Added mixup augmentation
        copy_paste=0.1,  # Added copy-paste augmentation
        hsv_h=0.015,
        hsv_s=0.7,
        hsv_v=0.4,
        degrees=10,
        translate=0.1,
        scale=0.5,
        shear=2,
        flipud=0.5,
        fliplr=0.5,
        patience=50,  # Increased early stopping patience
        save=True,    # Save best model
        device='0',   # Use GPU if available
        workers=4,    # Reduced workers for Pi 5
        project='pi5_optimized',  # New project name
        name='waste_detection',   # Run name
        exist_ok=True,  # Overwrite existing experiment
        pretrained=True,  # Use pretrained weights
        verbose=True,  # Print verbose output
        seed=42,  # Set random seed for reproducibility
        deterministic=True,  # Enable deterministic training
        rect=False,  # Disable rectangular training
        cos_lr=True,  # Use cosine learning rate scheduler
        close_mosaic=10,  # Disable mosaic augmentation in final epochs
        resume=False,  # Don't resume from last checkpoint
        overlap_mask=True,  # Enable mask overlap
        mask_ratio=4,  # Mask downsample ratio
        single_cls=False,  # Train as multi-class dataset
        nbs=64,  # Nominal batch size
        val=True,  # Validate during training
        save_json=False,  # Save results to JSON
        save_hybrid=False,  # Save hybrid version of labels
        conf=0.001,  # Confidence threshold
        iou=0.6,  # NMS IoU threshold
        max_det=300,  # Maximum number of detections per image
        half=False,  # Use FP16 half-precision inference
        dnn=False,  # Use OpenCV DNN for ONNX inference
        plots=True,  # Save plots
    )
    results = model.val()
    
    # Get the latest run directory
    try:
        run_dirs = sorted([d for d in os.listdir('pi5_optimized') if d.startswith('waste_detection')])
        latest_run = run_dirs[-1]
        best_pt_path = f'pi5_optimized/{latest_run}/weights/best.pt'
        
        # Load the best model for export
        if os.path.exists(best_pt_path):
            export_model = YOLO(best_pt_path)
            print(f"Using best model from {best_pt_path} for export")
        else:
            export_model = model
            print("Best model not found, using current model for export")
        
        # Method 1: Direct TFLite export (most reliable)
        print("Attempting direct TFLite export...")
        success = export_model.export(
            format='tflite',
            int8=True,
            nms=True,
            agnostic_nms=True,
            simplify=True,
            dynamic=False,
            imgsz=640,
            data=path,  # Pass dataset info for proper scaling
            verbose=True
        )
        print(f'Direct TFLite Export success: {success}')
        
        # Method 2: Try ONNX intermediate format if the first method fails
        if not success:
            print("Direct export failed. Trying ONNX intermediate approach...")
            # First export to ONNX with static dimensions
            success_onnx = export_model.export(
                format='onnx',
                simplify=True,
                dynamic=False,
                imgsz=640,
                data=path,
                verbose=True
            )
            print(f'ONNX Export success: {success_onnx}')
            
            if success_onnx:
                onnx_path = f'pi5_optimized/{latest_run}/weights/best.onnx'
                
                # Check if onnx2tflite is available
                try:
                    result = subprocess.run(['onnx2tflite', '--help'], check=True, capture_output=True, text=True)
                    print('onnx2tflite tool is available. Proceeding with conversion...')
                except FileNotFoundError:
                    print("onnx2tflite tool not found. Please ensure it is installed and added to your PATH.")
                    print("Skipping onnx2tflite conversion step.")
                    return

                # Try using onnx2tflite conversion
                try:
                    print("Trying onnx2tflite conversion...")
                    cmd = [
                        'onnx2tflite',
                        '-i', onnx_path,
                        '-o', f'pi5_optimized/{latest_run}/weights/best.tflite',
                        '-nuo', '-oiqt', '-qt', 'per-tensor',
                        '-b', '1', '-ois', '-kat', '-onwdt',
                    ]
                    result = subprocess.run(cmd, check=True, capture_output=True, text=True)
                    print('TFLite conversion output:', result.stdout)
                    print('TFLite conversion success')
                except subprocess.CalledProcessError as e:
                    print(f'TFLite conversion failed with error code {e.returncode}')
                    print(f'Error output: {e.stderr}')
                    
                    # Try using TensorFlow's converter as a fallback
                    try:
                        print("Trying TensorFlow's converter as fallback...")
                        import tensorflow as tf
                        
                        # Convert ONNX to TF SavedModel first
                        import onnx_tf
                        saved_model_dir = f'pi5_optimized/{latest_run}/weights/saved_model'
                        os.makedirs(saved_model_dir, exist_ok=True)
                        onnx_model = onnx.load(onnx_path)
                        tf_rep = onnx_tf.backend.prepare(onnx_model)
                        tf_rep.export_graph(saved_model_dir)
                        
                        # Convert SavedModel to TFLite
                        converter = tf.lite.TFLiteConverter.from_saved_model(saved_model_dir)
                        converter.optimizations = [tf.lite.Optimize.DEFAULT]
                        converter.target_spec.supported_ops = [
                            tf.lite.OpsSet.TFLITE_BUILTINS,
                            tf.lite.OpsSet.SELECT_TF_OPS
                        ]
                        tflite_model = converter.convert()
                        
                        with open(f'pi5_optimized/{latest_run}/weights/best_tf.tflite', 'wb') as f:
                            f.write(tflite_model)
                        print('TensorFlow fallback conversion successful')
                    except ImportError as ie:
                        print(f"TensorFlow fallback failed: {ie}")
                        print("Please install TensorFlow with: pip install tensorflow onnx-tf")
                    except Exception as ex:
                        print(f"TensorFlow fallback conversion failed: {ex}")
    except Exception as e:
        print(f"Export error: {e}")

if __name__ == '__main__':
    from multiprocessing import freeze_support
    freeze_support()
    main()