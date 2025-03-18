import streamlit as st
import logging
import os
from datetime import datetime
import time

from data_receiver import DataReceiver
from dashboard_ui import create_dashboard_ui
from state_manager import initialize_session_state, process_queues
from utils import add_connection_log

# Set up logging
def setup_logging():
    log_dir = "logs"
    os.makedirs(log_dir, exist_ok=True)
    log_file = os.path.join(log_dir, f"dashboard_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log")

    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file),
            logging.StreamHandler()
        ]
    )
    logger = logging.getLogger('waste-dashboard')

    logger.info("====== Dashboard Starting ======")
    logger.info(f"Logging to file: {log_file}")
    
    return logger, log_file

def create_dashboard_ui_with_debug(receiver, log_file):
    """Create the dashboard UI with debug mode option"""
    
    # Add a debug mode flag in query parameters
    query_params = st.query_params
    debug_mode = 'debug' in query_params and query_params['debug'][0].lower() == 'true'
    
    # Create regular dashboard UI
    create_dashboard_ui(receiver, log_file)
    
    # Add debug section if in debug mode
    if debug_mode:
        st.markdown("---")
        st.subheader("🔍 Debug Mode Enabled")
        
        debug_tab1, debug_tab2 = st.tabs(["Database Debug", "Session State"])
        
        with debug_tab1:
            from dashboard_ui import debug_database_connection
            debug_database_connection()
            
        with debug_tab2:
            st.write("Current Session State Variables:")
            
            # Show relevant session state variables
            debug_vars = {
                'devices': len(st.session_state.get('devices', {})),
                'device_ips': st.session_state.get('device_ips', {}),
                'detection_history': f"{len(st.session_state.get('detection_history', []))} entries",
                'receiver_status': {
                    k: v for k, v in st.session_state.get('receiver_status', {}).items() 
                    if k != 'active_devices' and k != 'last_connection_time'
                },
                'active_devices': list(st.session_state.get('receiver_status', {}).get('active_devices', [])),
            }
            
            st.json(debug_vars)

# Main function to run the dashboard
def main():
    # Set up logging
    logger, log_file = setup_logging()
    
    # Page configuration
    st.set_page_config(
        page_title="Waste Detection Dashboard",
        page_icon="♻️",
        layout="wide",
        initial_sidebar_state="expanded"
    )
    
    # Add custom CSS styling
    apply_custom_css()
    
    # Initialize session state
    initialize_session_state(logger)
    
    # Create or retrieve data receiver
    if 'data_receiver' not in st.session_state:
        logger.info("Creating new DataReceiver instance")
        st.session_state.data_receiver = DataReceiver()
        st.session_state.data_receiver.start()
    
    # Access the receiver from session state
    receiver = st.session_state.data_receiver
    
    # Process all queues - do this in the main thread
    process_queues()
    
    # Create the dashboard UI with debug option
    create_dashboard_ui_with_debug(receiver, log_file)
    
    # Register cleanup
    import atexit
    def cleanup():
        if 'data_receiver' in st.session_state:
            st.session_state.data_receiver.stop()
            logger.info("Dashboard shutting down, receiver stopped")
            
    atexit.register(cleanup)


# Custom CSS styling
def apply_custom_css():
    st.markdown("""
    <style>
    /* Container padding adjustments */
    [data-testid="block-container"] {
        padding-left: 2rem;
        padding-right: 2rem;
        padding-top: 1rem;
        padding-bottom: 0rem;
        margin-bottom: -7rem;
    }

    /* Remove extra horizontal padding in columns */
    [data-testid="stVerticalBlock"] {
        padding-left: 0rem;
        padding-right: 0rem;
    }

    /* Style for st.metric boxes */
    [data-testid="stMetric"] {
        background-color: #393939;
        text-align: center;
        padding: 15px 0;
        border-radius: 4px;
        margin-bottom: 1rem;
    }

    [data-testid="stMetricLabel"] {
        display: flex;
        justify-content: center;
        align-items: center;
    }

    /* Adjust the metric delta icon */
    [data-testid="stMetricDeltaIcon-Up"],
    [data-testid="stMetricDeltaIcon-Down"] {
        position: relative;
        left: 25%;
        transform: translateX(-50%);
    }

    /* Status indicators */
    .status-indicator {
        display: inline-block;
        width: 12px;
        height: 12px;
        border-radius: 50%;
        margin-right: 5px;
    }
    .status-green {
        background-color: #4CAF50;
    }
    .status-yellow {
        background-color: #FFC107;
    }
    .status-red {
        background-color: #F44336;
    }
    </style>
    """, unsafe_allow_html=True)

# Enable Altair dark theme
def enable_dark_theme():
    import altair as alt
    alt.themes.enable("dark")

if __name__ == "__main__":
    enable_dark_theme()
    main()