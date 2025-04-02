from pathlib import Path
import streamlit as st
import helper
import settings
import cv2
import numpy as np
from PIL import Image
import time

st.set_page_config(page_title="Waste Detection")

# Add performance monitoring
st.sidebar.title("Performance Metrics")
fps_placeholder = st.sidebar.empty()
inference_time_placeholder = st.sidebar.empty()

st.title("Intelligent waste segregation system")
st.write(
    "Start detecting objects in the webcam stream by clicking the button below. "
    "To stop the detection, click stop button in the top right corner of the webcam stream."
)

# ==== CLASS DEFINITIONS ====
RECYCLABLE = [
    'Aluminium foil', 'Clear plastic bottle', 'Corrugated carton', 'Drink can', 'Drink carton',
    'Egg carton', 'Food Can', 'Glass bottle', 'Glass jar', 'Magazine paper', 'Metal bottle cap',
    'Metal lid', 'Normal paper', 'Other plastic bottle', 'Other plastic container',
    'Paper bag', 'Paper cup', 'Pizza box', 'Plastic bottle cap', 'Plastic lid', 'Plastic straw',
    'Plastic utensils', 'Pop tab', 'Scrap metal', 'Toilet tube', 'Tupperware', 'Wrapping paper'
]

HAZARDOUS = [
    'Battery', 'Aerosol', 'Broken glass', 'Cigarette', 'Glass cup', 'Plastic glooves',
    'Shoe', 'Single-use carrier bag'
]

ALL_CLASSES = [
    'Aerosol', 'Aluminium blister pack', 'Aluminium foil', 'Battery', 'Broken glass',
    'Carded blister pack', 'Cigarette', 'Clear plastic bottle', 'Corrugated carton', 'Crisp packet',
    'Disposable food container', 'Disposable plastic cup', 'Drink can', 'Drink carton', 'Egg carton',
    'Foam cup', 'Foam food container', 'Food Can', 'Food waste', 'Garbage bag', 'Glass bottle',
    'Glass cup', 'Glass jar', 'Magazine paper', 'Meal carton', 'Metal bottle cap', 'Metal lid',
    'Normal paper', 'Other carton', 'Other plastic bottle', 'Other plastic container',
    'Other plastic cup', 'Other plastic wrapper', 'Other plastic', 'Paper bag', 'Paper cup',
    'Paper straw', 'Pizza box', 'Plastic bottle cap', 'Plastic film', 'Plastic glooves',
    'Plastic lid', 'Plastic straw', 'Plastic utensils', 'Polypropylene bag', 'Pop tab',
    'Rope - strings', 'Scrap metal', 'Shoe', 'Single-use carrier bag', 'Six pack rings',
    'Spread tub', 'Squeezable tube', 'Styrofoam piece', 'Tissues', 'Toilet tube',
    'Tupperware', 'Unlabeled litter', 'Wrapping paper'
]

# Dynamically assign remaining to "General"
GENERAL = sorted(list(set(ALL_CLASSES) - set(RECYCLABLE) - set(HAZARDOUS)))

# ==== SIDEBAR CLASS DISPLAY ====
st.sidebar.subheader("♻️ Recyclable")
for item in sorted(RECYCLABLE):
    st.sidebar.markdown(f'<div class="stRecyclable">{item}</div>', unsafe_allow_html=True)

st.sidebar.subheader("☣️ Hazardous")
for item in sorted(HAZARDOUS):
    st.sidebar.markdown(f'<div class="stHazardous">{item}</div>', unsafe_allow_html=True)

st.sidebar.subheader("🗑 General Waste")
for item in sorted(GENERAL):
    st.sidebar.markdown(f'<div class="stNonRecyclable">{item}</div>', unsafe_allow_html=True)

# ==== CUSTOM STYLES ====
st.markdown(
"""
<style>
    .stRecyclable {
        background-color: rgba(233,192,78,255);
        padding: 0.4rem 0.75rem;
        margin-bottom: 0.5rem;
        border-radius: 0.5rem;
        font-size:15px;
    }
    .stNonRecyclable {
        background-color: rgba(94,128,173,255);
        padding: 0.4rem 0.75rem;
        margin-bottom: 0.5rem;
        border-radius: 0.5rem;
        font-size:15px;
    }
    .stHazardous {
        background-color: rgba(194,84,85,255);
        padding: 0.4rem 0.75rem;
        margin-bottom: 0.5rem;
        border-radius: 0.5rem;
        font-size:15px;
    }
</style>
""",
unsafe_allow_html=True
)

# ==== OPTIMIZATION SETTINGS ====
st.sidebar.subheader("⚙️ Performance Settings")
confidence_threshold = st.sidebar.slider("Confidence Threshold", 0.0, 1.0, 0.25, 0.05)
nms_threshold = st.sidebar.slider("NMS Threshold", 0.0, 1.0, 0.45, 0.05)
use_gpu = st.sidebar.checkbox("Use GPU (if available)", value=True)

# ==== LOAD MODEL ====
try:
    model = helper.load_model("pi5_optimized/waste_detection9/weights/best.pt")
    st.success("Model loaded successfully!")
except Exception as ex:
    st.error(f"Error loading model: {ex}")
    st.stop()

# ==== START DETECTION ====
helper.play_webcam(model)

# Add system information
st.sidebar.markdown("---")
st.sidebar.subheader("ℹ️ System Information")
st.sidebar.markdown("""
- Model: YOLOv8n (Optimized for Pi 5)
- Input Size: 416x416
- Quantization: INT8
- Device: Raspberry Pi 5
""")

st.sidebar.markdown("This is a demo of the waste detection model with 59 waste categories.", unsafe_allow_html=True)