# YOLOv8 Waste Detection Model

This directory contains the YOLOv8-based waste detection model implementation for this project. The model is designed to detect and classify different types of waste materials, particularly focusing on recyclable items.

## Overview

The waste detection system uses YOLOv8 (nano model) for real-time object detection and classification. It's optimized for edge deployment and can detect various types of recyclable materials including plastic bottles, cans, paper products, and more.

## Components

- `app.py`: Streamlit web application for real-time waste detection
- `train.py`: Training script for the YOLOv8 model
- `helper.py`: Utility functions for image processing and model operations
- `settings.py`: Configuration settings for the model
- `yolov8n.pt`: Pre-trained YOLOv8 nano model
- `weights/`: Directory containing trained model weights
- `pi5_optimized/`: Optimized version for Raspberry Pi 5 deployment

## Dependencies

The project requires the following main dependencies:
- streamlit==1.26.0
- opencv-python-headless==4.8.1.78
- torch==2.0.1
- torchvision==0.15.2
- ultralytics==8.0.173
- urllib3==1.26.6
- onnx==1.15.0

## Integration with Main Project

This model is integrated with the main Fictional Waste Doodoo project through the following components:

1. **Web Interface**: The Streamlit app (`app.py`) provides a user-friendly interface for waste detection
2. **Model Integration**: The trained model can be used by the main application for waste classification
3. **API Endpoints**: The model's predictions can be accessed through the main project's API

## Usage

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Run the Streamlit app:
```bash
streamlit run app.py
```

3. For training the model on custom data:
```bash
python train.py
```

## Model Training

The model is trained on the TACO dataset with the following configurations:
- Epochs: 200
- Image size: 640x640
- Batch size: 8
- Optimizer: AdamW
- Learning rate: 0.0005
- Various augmentations including mosaic, mixup, and copy-paste

## Performance Optimization

The model is optimized for:
- Edge deployment (Raspberry Pi 5)
- Real-time inference
- Resource-constrained environments

## Related Components

- [Main Project](../README.md)
- [Frontend](../frontend/README.md)
- [Backend](../backend/README.md)
- [Database](../database/README.md)

## License

This component is part of this project. See the main project's LICENSE file for details. 