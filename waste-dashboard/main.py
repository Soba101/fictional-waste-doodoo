import logging
import os
from datetime import datetime

# Configure logging BEFORE any other imports
# Set root logger to INFO for more detailed logs
logging.getLogger().setLevel(logging.INFO)

# Configure basic logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# Set specific loggers to INFO
logging.getLogger('waste-dashboard').setLevel(logging.INFO)
logging.getLogger('data-receiver').setLevel(logging.INFO)
logging.getLogger('state-manager').setLevel(logging.INFO)

# Set SQLAlchemy logging to WARNING to hide SQL queries
logging.getLogger('sqlalchemy').setLevel(logging.WARNING)
logging.getLogger('sqlalchemy.engine').setLevel(logging.WARNING)
logging.getLogger('sqlalchemy.pool').setLevel(logging.WARNING)
logging.getLogger('sqlalchemy.dialects').setLevel(logging.WARNING)
logging.getLogger('sqlalchemy.orm').setLevel(logging.WARNING)
logging.getLogger('sqlalchemy.engine.Engine').setLevel(logging.WARNING)
logging.getLogger('sqlalchemy.engine.Connection').setLevel(logging.WARNING)

# Disable echo mode for SQLAlchemy
os.environ['SQLALCHEMY_ECHO'] = 'false'

# Now import other modules
import streamlit as st
import time
import atexit
import config

# Set page config to wide mode and other options
st.set_page_config(
    page_title=config.DASHBOARD_TITLE,
    page_icon=config.DASHBOARD_ICON,
    layout="wide",
    initial_sidebar_state="expanded",
    menu_items={
        'Get Help': None,
        'Report a bug': None,
        'About': None
    }
)

from data_receiver import DataReceiver
from dashboard_ui import create_dashboard_ui
from state_manager import initialize_session_state, process_queues
from utils import add_connection_log

# Set up logging
def setup_logging():
    # Only set up logging if it hasn't been done yet
    if not hasattr(st.session_state, 'logging_initialized'):
        log_dir = "logs"
        os.makedirs(log_dir, exist_ok=True)
        log_file = os.path.join(log_dir, f"dashboard_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log")

        # Add file handler
        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(logging.WARNING)
        
        # Get the root logger
        logger = logging.getLogger('waste-dashboard')
        logger.setLevel(logging.WARNING)
        
        # Add the file handler to the logger
        logger.addHandler(file_handler)
        
        # Log startup message only once
        logger.warning("====== Dashboard Starting ======")
        logger.warning(f"Logging to file: {log_file}")
        
        # Mark logging as initialized
        st.session_state.logging_initialized = True
        st.session_state.log_file = log_file
    
    return st.session_state.log_file

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
        
        debug_tab1, debug_tab2 = st.tabs(["MQTT Debug", "Session State"])
        
        with debug_tab1:
            st.write("MQTT Connection Status:", receiver.is_connected())
            st.write("MQTT Broker:", f"{config.MQTT_BROKER}:{config.MQTT_PORT}")
            
        with debug_tab2:
            st.write("Session State:", st.session_state)

def main():
    # Set up logging
    log_file = setup_logging()
    
    # Initialize session state only if not already initialized
    if 'devices' not in st.session_state:
        initialize_session_state()
    
    # Create data receiver if not already created
    if 'receiver' not in st.session_state:
        receiver = DataReceiver()
        st.session_state.receiver = receiver
        
        # Initialize MQTT client in session state
        st.session_state.mqtt_client = receiver.client
        
        # Set up cleanup function
        def cleanup():
            logger = logging.getLogger('waste-dashboard')
            logger.info("Cleaning up...")
            receiver.stop()
            logger.info("Cleanup complete")
        
        # Register cleanup function with atexit
        atexit.register(cleanup)
    else:
        receiver = st.session_state.receiver
    
    # Apply custom CSS
    apply_custom_css()
    
    # Enable dark theme
    enable_dark_theme()
    
    # Process any pending messages
    process_queues(receiver)
    
    # Create dashboard UI
    create_dashboard_ui_with_debug(receiver, log_file)

def apply_custom_css():
    """Apply custom CSS to the dashboard."""
    st.markdown("""
        <style>
        .stButton>button {
            width: 100%;
            margin-top: 10px;
        }
        .stTextInput>div>div>input {
            background-color: #2b2b2b;
            color: white;
        }
        </style>
    """, unsafe_allow_html=True)

def enable_dark_theme():
    """Enable dark theme for the dashboard."""
    st.markdown("""
        <style>
        .stApp {
            background-color: #1e1e1e;
            color: white;
        }
        .stMarkdown {
            color: white;
        }
        .stText {
            color: white;
        }
        </style>
    """, unsafe_allow_html=True)

if __name__ == "__main__":
    main()