from ultralytics import YOLO
import time
import streamlit as st
import cv2
import settings
import threading
import numpy as np

def sleep_and_clear_success():
    time.sleep(3)
    st.session_state["clear_placeholders"] = True

def load_model(model_path):
    model = YOLO(model_path)
    return model

def classify_waste_type(detected_items):
    recyclable_items = set(detected_items) & set(settings.RECYCLABLE)
    non_recyclable_items = set(detected_items) & set(settings.NON_RECYCLABLE)
    hazardous_items = set(detected_items) & set(settings.HAZARDOUS)
    
    return recyclable_items, non_recyclable_items, hazardous_items

def remove_dash_from_class_name(class_name):
    return class_name.replace("_", " ")

def _display_detected_frames(model, st_frame, image, fps_placeholder=None, inference_time_placeholder=None):
    start_time = time.time()
    
    # Preprocess frame for Pi 5 optimization
    image = cv2.resize(image, (416, 416))  # Match training size
    image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
    
    if st.session_state.get("clear_placeholders", False):
        st.session_state["recyclable_placeholder"].markdown("")
        st.session_state["non_recyclable_placeholder"].markdown("")
        st.session_state["hazardous_placeholder"].markdown("")
        st.session_state["clear_placeholders"] = False
    
    if 'unique_classes' not in st.session_state:
        st.session_state['unique_classes'] = set()

    if 'recyclable_placeholder' not in st.session_state:
        st.session_state['recyclable_placeholder'] = st.sidebar.empty()
    if 'non_recyclable_placeholder' not in st.session_state:
        st.session_state['non_recyclable_placeholder'] = st.sidebar.empty()
    if 'hazardous_placeholder' not in st.session_state:
        st.session_state['hazardous_placeholder'] = st.sidebar.empty()

    if 'last_detection_time' not in st.session_state:
        st.session_state['last_detection_time'] = 0

    # Run inference with optimized settings
    res = model.predict(image, conf=0.25, iou=0.45)  # Optimized thresholds for Pi 5
    names = model.names
    detected_items = set()

    for result in res:
        new_classes = set([names[int(c)] for c in result.boxes.cls])
        if new_classes != st.session_state['unique_classes']:
            st.session_state['unique_classes'] = new_classes
            st.session_state['recyclable_placeholder'].markdown('')
            st.session_state['non_recyclable_placeholder'].markdown('')
            st.session_state['hazardous_placeholder'].markdown('')
            detected_items.update(st.session_state['unique_classes'])

            recyclable_items, non_recyclable_items, hazardous_items = classify_waste_type(detected_items)

            if recyclable_items:
                detected_items_str = "\n- ".join(remove_dash_from_class_name(item) for item in recyclable_items)
                st.session_state['recyclable_placeholder'].markdown(
                    f"<div class='stRecyclable'>Recyclable items:\n\n- {detected_items_str}</div>",
                    unsafe_allow_html=True
                )
            if non_recyclable_items:
                detected_items_str = "\n- ".join(remove_dash_from_class_name(item) for item in non_recyclable_items)
                st.session_state['non_recyclable_placeholder'].markdown(
                    f"<div class='stNonRecyclable'>Non-Recyclable items:\n\n- {detected_items_str}</div>",
                    unsafe_allow_html=True
                )
            if hazardous_items:
                detected_items_str = "\n- ".join(remove_dash_from_class_name(item) for item in hazardous_items)
                st.session_state['hazardous_placeholder'].markdown(
                    f"<div class='stHazardous'>Hazardous items:\n\n- {detected_items_str}</div>",
                    unsafe_allow_html=True
                )

            threading.Thread(target=sleep_and_clear_success).start()
            st.session_state['last_detection_time'] = time.time()

    # Calculate and display performance metrics
    inference_time = time.time() - start_time
    if fps_placeholder and inference_time_placeholder:
        fps = 1.0 / inference_time
        fps_placeholder.text(f"FPS: {fps:.2f}")
        inference_time_placeholder.text(f"Inference Time: {inference_time*1000:.2f}ms")

    res_plotted = res[0].plot()
    st_frame.image(res_plotted, channels="RGB")

def play_webcam(model):
    source_webcam = settings.WEBCAM_PATH
    if st.button('Detect Objects'):
        try:
            vid_cap = cv2.VideoCapture(source_webcam)
            st_frame = st.empty()
            fps_placeholder = st.sidebar.empty()
            inference_time_placeholder = st.sidebar.empty()
            
            while (vid_cap.isOpened()):
                success, image = vid_cap.read()
                if success:
                    _display_detected_frames(model, st_frame, image, fps_placeholder, inference_time_placeholder)
                else:
                    vid_cap.release()
                    break
        except Exception as e:
            st.sidebar.error("Error loading video: " + str(e))
