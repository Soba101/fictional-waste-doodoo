from ultralytics import YOLO
import time
import streamlit as st
import cv2
import settings
import threading
import numpy as np
from streamlit.runtime.scriptrunner.script_run_context import add_script_run_ctx

def sleep_and_clear_success():
    time.sleep(3)
    st.session_state["clear_placeholders"] = True

def load_model(model_path):
    """
    Load a model from a given path.
    Handles different model formats including TFLite.
    """
    try:
        # Explicitly specify task="detect" to avoid warnings
        model = YOLO(model_path, task='detect')
        print(f"Loaded model from {model_path}")
        return model
    except Exception as e:
        print(f"Error loading model: {e}")
        raise e

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
        # Check if boxes exist and boxes.cls is not None or empty
        if not result.boxes or result.boxes.cls is None or len(result.boxes.cls) == 0:
            continue
        try:
            new_classes = set([names[int(c)] for c in result.boxes.cls])
        except Exception as e:
            # Skip if unable to process detections from this result
            continue
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

def threaded_play_webcam(model):
    import time
    source_webcam = settings.WEBCAM_PATH
    vid_cap = cv2.VideoCapture(source_webcam)
    # Create two columns: raw feed on the left, detection overlay on the right.
    cols = st.columns(2)
    raw_feed = cols[0].empty()
    detection_feed = cols[1].empty()
    fps_placeholder = st.sidebar.empty()
    inference_time_placeholder = st.sidebar.empty()
    while vid_cap.isOpened() and st.session_state.get("detection_running", True):
        success, image = vid_cap.read()
        if not success:
            break
        # Display raw video feed in left column
        raw_feed.image(cv2.cvtColor(image, cv2.COLOR_BGR2RGB), channels="RGB")
        # Run detections and show overlay in right column
        _display_detected_frames(model, detection_feed, image, fps_placeholder, inference_time_placeholder)
        time.sleep(0.03)  # slight delay to reduce CPU usage
    vid_cap.release()

def play_webcam(model):
    # Initialize required session state keys if not already set
    if 'unique_classes' not in st.session_state:
        st.session_state['unique_classes'] = set()
    if 'recyclable_placeholder' not in st.session_state:
        st.session_state['recyclable_placeholder'] = st.sidebar.empty()
    if 'non_recyclable_placeholder' not in st.session_state:
        st.session_state['non_recyclable_placeholder'] = st.sidebar.empty()
    if 'hazardous_placeholder' not in st.session_state:
        st.session_state['hazardous_placeholder'] = st.sidebar.empty()
    if "detection_running" not in st.session_state:
        st.session_state["detection_running"] = False

    # Toggle button: show "Show Live Feed" when not running, "Stop Detection" when running.
    if st.session_state["detection_running"]:
        if st.button("Stop Detection"):
            st.session_state["detection_running"] = False
    else:
        if st.button("Show Live Feed"):
            st.session_state["detection_running"] = True
            import threading
            thread = threading.Thread(target=threaded_play_webcam, args=(model,), daemon=True)
            add_script_run_ctx(thread)  # Attach the context to the thread
            thread.start()
