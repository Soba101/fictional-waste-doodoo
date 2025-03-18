import streamlit as st
import pandas as pd
import numpy as np
import folium
from streamlit_folium import st_folium
import altair as alt
import socket
import time
import logging
from datetime import datetime, timedelta
import requests
import io
from PIL import Image
import pymysql
from sqlalchemy import create_engine
import plotly.express as px
from streamlit_plotly_events import plotly_events  # New import for Plotly events
import plotly.graph_objects as go
import matplotlib.pyplot as plt

from utils import check_device_status, discover_devices, add_connection_log
from state_manager import calculate_metrics, process_queues
 
# Database connection details
DB_HOST = "192.168.18.113" # need to add a alt for hotspot
DB_USER = "waste_user"
DB_PASSWORD = "password"
DB_NAME = "waste_detection"
 
# Create SQLAlchemy engine
DB_URI = f"mysql+pymysql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}/{DB_NAME}"
engine = create_engine(DB_URI)

def fetch_detection_data():
    """Fetch daily detection counts from MariaDB using SQLAlchemy."""
    try:
        # Improved query with better date handling and error checking
        query = """
        SELECT 
            DATE(timestamp) AS detection_date, 
            SUM(num_detections) AS detection_count
        FROM detections
        WHERE 
            timestamp IS NOT NULL AND
            num_detections > 0
        GROUP BY detection_date
        ORDER BY detection_date ASC;
        """
        
        # Execute the query and log the result
        logger.info("Executing detection data query")
        df = pd.read_sql(query, engine)
        
        # Log the shape and preview of the result for debugging
        if not df.empty:
            logger.info(f"Fetched {len(df)} detection date records")
            logger.info(f"Date range: {df['detection_date'].min()} to {df['detection_date'].max()}")
            logger.info(f"Total detections: {df['detection_count'].sum()}")
        else:
            logger.warning("No detection data returned from query")
            
        return df
    except Exception as e:
        logger.error(f"Database connection error in fetch_detection_data: {str(e)}")
        st.error(f"Database connection error: {e}")
        return pd.DataFrame(columns=["detection_date", "detection_count"])

# Setup logger
logger = logging.getLogger('waste-dashboard.ui')

def create_dashboard_ui(receiver, log_file):
    """Create the dashboard UI using Streamlit components"""
    
    #######################
    # Sidebar
    create_sidebar(receiver)
    
    #######################
    # Main Title
    st.title("Singapore Waste Detection Dashboard")
    
    #######################
    # Retrieve user location from query params
    user_location = get_user_location()
    
    #######################
    # Layout with columns
    col = st.columns((1.5, 4.5, 2), gap='medium')
    
    # Calculate metrics
    metrics = calculate_metrics()
    
    ## -- LEFT COLUMN: Metrics and device status
    with col[0]:
        create_left_column(metrics)
    
    ## -- MIDDLE COLUMN: Map or live feed
    with col[1]:
        create_middle_column(user_location)
    
    ## -- RIGHT COLUMN: Quick stats / summary
    with col[2]:
        create_right_column(metrics)
    
    #######################
    # Bottom Section: Historical Chart (Plotly Version)
    create_bottom_section_plotly()
    
    #######################
    # Footer
    st.markdown("---")
    st.markdown(f"**Dashboard Status:** Running since {datetime.now().strftime('%H:%M:%S')}")
    st.markdown(f"**Log File:** {log_file}")

def create_sidebar(receiver):
    """Create the sidebar with controls and status info"""
    st.sidebar.title("Dashboard Controls")
    st.sidebar.markdown("Use these controls to manage the dashboard.")
    
    # Network configuration and discovery
    st.sidebar.subheader("Network Configuration")
    
    # Show the machine's IP addresses that Pi should connect to
    try:
        hostname = socket.gethostname()
        local_ip = socket.gethostbyname(hostname)
        st.sidebar.write(f"Dashboard IP: **{local_ip}**")
        
        # Get all IPs for this machine
        all_ips = []
        for iface_addr in socket.getaddrinfo(hostname, None):
            ip = iface_addr[4][0]
            if ip not in all_ips and not ip.startswith('127.') and ':' not in ip:  # Skip loopback and IPv6
                all_ips.append(ip)
                
        if len(all_ips) > 1:
            st.sidebar.write("Alternative IPs:")
            for ip in all_ips:
                if ip != local_ip:
                    st.sidebar.write(f"- **{ip}**")
                    
        logger.info(f"Dashboard IPs: {', '.join(all_ips)}")
    except Exception as e:
        st.sidebar.error(f"Could not determine local IP: {e}")
        logger.error(f"Error getting local IP: {e}")
    
    # Display receiver status from the actual DataReceiver object
    receiver_status = st.session_state.receiver_status
    active_devices_count = len(receiver_status.get("active_devices", set()))
    connection_status = "🟢 Connected" if active_devices_count > 0 else "🔴 Disconnected"
    st.sidebar.write(f"Status: {connection_status}")
    st.sidebar.write(f"Details: {receiver_status['connection_status']}")
    st.sidebar.write(f"Connection attempts: {receiver_status['connection_attempts']}")
    st.sidebar.write(f"Successful: {receiver_status['successful_connections']}")
    st.sidebar.write(f"Failed: {receiver_status['failed_connections']}")
    st.sidebar.write(f"Active devices: {active_devices_count}")
    
    # Control buttons
    col1, col2 = st.sidebar.columns(2)
    with col1:
        if st.button("Restart Receiver"):
            receiver.stop()
            time.sleep(1)
            receiver.start()
            st.sidebar.success("Receiver restarted!")
            add_connection_log("Receiver restarted")
    
    with col2:
        if st.button("Discover Devices"):
            discover_devices()
            st.sidebar.success("Discovery started!")
    
    # Live feed toggle
    st.session_state.show_live_feed = st.sidebar.checkbox("Show Live Feed", 
                                                        value=st.session_state.get('show_live_feed', False))
    
    # Device selection for live feed
    if st.session_state.device_ips and st.session_state.show_live_feed:
        device_options = list(st.session_state.device_ips.keys())
        if device_options:
            selected_device = st.sidebar.selectbox(
                "Select Device", 
                device_options,
                index=0
            )
            if selected_device:
                st.session_state.show_device_feed = selected_device
    
    # Connection log display
    st.session_state.show_connection_log = st.sidebar.checkbox("Show Connection Log", 
                                                              value=st.session_state.get('show_connection_log', False))

def get_user_location():
    """Retrieve user location from query params"""
    user_location = None
    query_params = st.query_params
    if "lat" in query_params and "lon" in query_params:
        try:
            lat = float(query_params["lat"][0])
            lon = float(query_params["lon"][0])
            user_location = (lat, lon)
            logger.info(f"User location from query params: {lat}, {lon}")
        except ValueError:
            st.error("Invalid coordinates received.")
            logger.error("Invalid coordinates in query params")
    return user_location

def create_left_column(metrics):
    """Create the left column with metrics and device status"""
    st.markdown("#### Metrics")
    st.metric(label="Total Detections", value=str(metrics["total_detections"]), 
              delta=f"{metrics['detection_delta']} from last hour")
    st.metric(label="Gas Alerts", value=str(metrics["total_gas_alerts"]), 
              delta=f"{metrics['gas_delta']} from last hour")
    st.metric(label="Active Edge Devices", value=str(metrics["active_devices"]), delta="")
    
    st.markdown("#### Device Status")
    
    # Convert devices dictionary to dataframe
    device_list = []
    for device_id, device_data in st.session_state.devices.items():
        # Check if device is active based on receiver status
        is_active = device_id in st.session_state.receiver_status.get("active_devices", set())
        
        # Generate status indicator HTML
        status_indicator = "🟢" if is_active else "🔴"
        
        # Check when we last heard from this device
        last_update_str = "Unknown"
        if 'last_updated' in device_data:
            try:
                last_updated = device_data['last_updated']
                if isinstance(last_updated, str):
                    last_updated = datetime.fromisoformat(last_updated)
                last_update_str = last_updated.strftime("%H:%M:%S")
            except:
                pass
        
        device_list.append({
            "Device": device_id,
            "Status": f"{status_indicator} {is_active and 'Active' or 'Inactive'}",
            "Detections": device_data["detections"],
            "Last Update": last_update_str
        })
    
    if device_list:
        df_devices = pd.DataFrame(device_list)
        st.dataframe(df_devices, use_container_width=True, hide_index=True)
    else:
        st.info("No devices connected yet. Waiting for connections...")

def create_map(devices, user_loc, _last_update=None):
    """Create a folium map with device markers"""
    m = folium.Map(location=[1.3521, 103.8198], zoom_start=12, tiles="CartoDB dark_matter")
    
    # Add user location if available
    if user_loc:
        folium.Marker(
            location=user_loc,
            popup="You are here",
            icon=folium.Icon(color="blue", icon="user")
        ).add_to(m)
    
    # Add markers for each device
    for device_id, device_data in devices.items():
        # Create tooltip with device info
        tooltip = f"""
        <div style="width:200px">
            <b>{device_data['id']}</b><br>
            Detections: {device_data['detections']}<br>
            Gas Alerts: {device_data.get('gas_alerts', 0)}<br>
        </div>
        """
        
        # Determine icon color based on recency
        icon_color = "red"
        now = datetime.now()
        try:
            last_updated = device_data['last_updated']
            if isinstance(last_updated, str):
                last_updated = datetime.fromisoformat(last_updated)
            time_diff = now - last_updated
            if time_diff < timedelta(minutes=5):
                icon_color = "green"  # Active recently
            elif time_diff < timedelta(minutes=30):
                icon_color = "orange"  # Active within 30 min
        except:
            pass
            
        # Add marker
        folium.Marker(
            location=[device_data["lat"], device_data["lon"]],
            popup=tooltip,
            tooltip=device_data['id'],
            icon=folium.Icon(color=icon_color, icon="info-sign")
        ).add_to(m)
        
    return m

def create_middle_column(user_location):
    """Create the middle column with map or live feed"""
    # Cache the map creation with last update time for refreshing
    @st.cache_resource(ttl=10)  # Cache for 10 seconds max
    def get_cached_map(devices, user_loc, _last_update=None):
        return create_map(devices, user_loc, _last_update)
    
    # Get the last update time for the map refresh
    last_update_time = st.session_state.last_processed_data
    
    # Create map with the current state
    cached_map = get_cached_map(st.session_state.devices, user_location, _last_update=last_update_time)
    
    if not st.session_state.get('show_live_feed', False):
        st.markdown("#### Map of Current Device Locations")
        map_data = st_folium(cached_map, width=700, height=500)
        
        # Handle map click to select device
        if map_data["last_object_clicked"] is not None:
            clicked_lat = map_data["last_object_clicked"].get("lat")
            clicked_lng = map_data["last_object_clicked"].get("lng")
            
            if clicked_lat and clicked_lng:
                # Find device near clicked coordinates
                selected_device = None
                for device_id, device_data in st.session_state.devices.items():
                    # Use small threshold for coordinate matching
                    if (abs(device_data["lat"] - clicked_lat) < 0.01 and 
                        abs(device_data["lon"] - clicked_lng) < 0.01):
                        selected_device = device_data
                        break
                
                if selected_device:
                    st.write(f"**Device:** {selected_device['id']}")
                    
                    # Check last activity time
                    try:
                        last_updated = selected_device['last_updated']
                        if isinstance(last_updated, str):
                            last_updated = datetime.fromisoformat(last_updated)
                        time_diff = datetime.now() - last_updated
                        status = "🟢 Active" if time_diff < timedelta(minutes=5) else "🟠 Inactive"
                        st.write(f"**Status:** {status} (Last seen: {last_updated.strftime('%H:%M:%S')})")
                    except:
                        st.write("**Status:** Unknown")
                    
                    st.write(f"**Total Detections:** {selected_device['detections']}")
                    st.write(f"**Gas Alerts:** {selected_device.get('gas_alerts', 0)}")
                    
                    # Device IP
                    device_id = selected_device['id']
                    device_ip = st.session_state.device_ips.get(device_id, "Unknown")
                    st.write(f"**IP Address:** {device_ip}")
                    
                    # Option to view the device's live feed
                    if st.button(f"View Live Feed for {selected_device['id']}"):
                        st.session_state.show_device_feed = selected_device['id']
                        st.session_state.show_live_feed = True
                        st.rerun()
    else:
        st.markdown("#### Live Detection Feed")
        # Display which device we're viewing
        if "show_device_feed" in st.session_state and st.session_state.show_device_feed in st.session_state.devices:
            selected_device = st.session_state.show_device_feed
            device_data = st.session_state.devices[selected_device]
            st.write(f"Viewing feed from: **{selected_device}**")
            
            # Get the device IP
            device_ip = st.session_state.device_ips.get(selected_device)
            if device_ip:
                stream_url = f"http://{device_ip}:8000/video_feed"
                
                # First check if the device is reachable
                connection_status_container = st.empty()
                connection_status_container.write(f"**Connection:** Connecting to {device_ip}:8000")
                
                try:
                    # Check if the device is reachable by pinging the status endpoint
                    device_status = check_device_status(selected_device, device_ip)
                    
                    if device_status:
                        # Device is reachable, update the connection status
                        connection_status_container.write(f"**Connection:** Successfully connected to {device_ip}:8000")
                        
                        # Create a container for the video feed
                        video_container = st.container()
                        
                        # Display the video feed using HTML with a unique ID for the image
                        video_container.markdown(
                            f"""
                            <div style="text-align: center;">
                                <img id="video-feed" src="{stream_url}" style="width:100%; max-width:800px; border:2px solid #444;" 
                                    onload="document.getElementById('connection-status').style.display='none';"
                                    onerror="document.getElementById('connection-status').style.display='block';" />
                                <div id="connection-status" style="display:none; color:#F55; padding:10px; margin-top:10px; border:1px solid #F55;">
                                    Video feed unavailable. Check that your device is running and streaming properly.
                                </div>
                            </div>
                            <script>
                                // Check if the video feed is actually loading
                                const imgElement = document.getElementById('video-feed');
                                // Hide the connection error by default
                                const statusElement = document.getElementById('connection-status');
                                if (statusElement) statusElement.style.display = 'none';
                                
                                // Add event listeners to handle load and error
                                if (imgElement) {{
                                    imgElement.onload = function() {{
                                        if (statusElement) statusElement.style.display = 'none';
                                    }};
                                    imgElement.onerror = function() {{
                                        if (statusElement) statusElement.style.display = 'block';
                                    }};
                                }}
                            </script>
                            """,
                            unsafe_allow_html=True
                        )
                        
                        # Display device status information
                        st.write("**Device Status:**")
                        
                        uptime = device_status.get('uptime', 0)
                        uptime_str = f"{uptime:.1f} seconds" if uptime < 60 else f"{uptime/60:.1f} minutes"
                        st.write(f"- Uptime: {uptime_str}")
                        
                        # Display connection stats
                        conn_stats = device_status.get('connection', {})
                        if conn_stats:
                            st.write("**Connection Statistics:**")
                            st.write(f"- Successes: {conn_stats.get('success_count', 0)}")
                            st.write(f"- Failures: {conn_stats.get('failure_count', 0)}")
                            st.write(f"- Status: {conn_stats.get('last_status', 'Unknown')}")
                    else:
                        # Device isn't reachable but still attempt to show the stream
                        # (sometimes status endpoint is down but video still works)
                        connection_status_container.warning(f"**Warning:** Could not reach status endpoint at {device_ip}:8000/status, but attempting to show video feed")
                        
                        # Display the video feed with appropriate error handling
                        st.markdown(
                            f"""
                            <div style="text-align: center;">
                                <img src="{stream_url}" style="width:100%; max-width:800px; border:2px solid #444;"
                                     onload="this.style.border='2px solid #4CAF50'; document.getElementById('feed-status').innerHTML='Feed active';"
                                     onerror="this.style.border='2px solid #F44336'; this.src='data:image/svg+xml;utf8,<svg xmlns=\"http://www.w3.org/2000/svg\" width=\"800\" height=\"600\" viewBox=\"0 0 800 600\"><rect width=\"800\" height=\"600\" fill=\"#222\"/><text x=\"400\" y=\"300\" font-family=\"Arial\" font-size=\"24\" fill=\"white\" text-anchor=\"middle\">Video feed unavailable</text></svg>'; document.getElementById('feed-status').innerHTML='Feed unavailable';" />
                                <div id="feed-status" style="margin-top:10px; font-style:italic;">Connecting...</div>
                            </div>
                            """,
                            unsafe_allow_html=True
                        )
                except Exception as e:
                    logger.error(f"Error with video feed display: {e}")
                    connection_status_container.error(f"Error connecting to {device_ip}:8000: {e}")
                    
                    # Still try to display the video feed as a fallback
                    st.markdown(
                        f"""
                        <div style="text-align: center;">
                            <img src="{stream_url}" style="width:100%; max-width:800px; border:2px solid #444;"
                                 onload="document.getElementById('error-message').style.display='none';"
                                 onerror="document.getElementById('error-message').style.display='block';" />
                            <div id="error-message" style="color:#F55; padding:10px; margin-top:10px; border:1px solid #F55;">
                                Connection error: Video feed unavailable
                            </div>
                        </div>
                        """,
                        unsafe_allow_html=True
                    )
            else:
                st.error(f"Cannot determine IP address for {selected_device}")
                logger.error(f"No IP address for {selected_device}")
                
            # Button to go back to map
            if st.button("Back to Map"):
                st.session_state.show_live_feed = False
                if "show_device_feed" in st.session_state:
                    del st.session_state.show_device_feed
                st.rerun()
        else:
            st.error("No device selected or device not available")
            if st.button("Back to Map"):
                st.session_state.show_live_feed = False
                st.rerun()

def create_right_column(metrics):
    """Create the right column with quick stats and system status"""
    # Connection log (if enabled)
    if st.session_state.get('show_connection_log', False):
        st.markdown("#### Connection Log")
        if st.session_state.connection_log:
            for entry in reversed(st.session_state.connection_log[-10:]):
                timestamp = entry["timestamp"].strftime("%H:%M:%S")
                device = entry.get("device_id", "")
                event = entry["event"]
                details = entry.get("details", "")
                
                if device:
                    st.write(f"**{timestamp}** [{device}] {event}")
                else:
                    st.write(f"**{timestamp}** {event}")
                    
                if details:
                    st.write(f"<span style='margin-left:20px; color: #999;'>{details}</span>", unsafe_allow_html=True)
        else:
            st.info("No connection events recorded yet")
    else:
        st.markdown("#### Detection Summary")
        
        # Show latest detections
        if st.session_state.detection_history:
            st.write("**Recent Detections:**")
            recent_detections = sorted(
                st.session_state.detection_history[-10:],
                key=lambda x: x["time"], 
                reverse=True
            )
            
            for i, detection in enumerate(recent_detections[:5]):
                detection_time = detection["time"].strftime("%H:%M:%S")
                st.write(f"- {detection_time}: {detection['count']} items on {detection['device']}")
    
    st.markdown("#### System Status")
    total_devices = len(st.session_state.devices)
    
    # Calculate average detections per active device
    active_devices = metrics["active_devices"]
    total_detections = metrics["total_detections"]
    if active_devices > 0:
        avg_detections = total_detections / active_devices
    else:
        avg_detections = 0
        
    st.write(f"**Total Devices:** {total_devices}")
    st.write(f"**Active Devices:** {active_devices}")
    st.write(f"**Avg. Detections/Device:** {avg_detections:.1f}")

    # Connection details section
    st.markdown("#### Connection Details")
    if st.session_state.device_ips:
        for device_id, ip in st.session_state.device_ips.items():
            # Check if this device is active
            is_active = device_id in st.session_state.receiver_status.get("active_devices", set())
            status_indicator = "🟢" if is_active else "🔴"
            
            st.write(f"{status_indicator} **{device_id}:** {ip}")
            
            # Try to check device status
            status = check_device_status(device_id, ip)
            if status:
                uptime = status.get('uptime', 0)
                uptime_str = f"{uptime:.1f}s" if uptime < 60 else f"{uptime/60:.1f}m"
                st.write(f"<span style='margin-left:20px;'>Uptime: {uptime_str}</span>", unsafe_allow_html=True)
    else:
        st.info("No device connections detected yet")
        
    # About section
    with st.expander("About", expanded=True):
        st.write("""
        - This dashboard connects to edge devices running waste detection.
        - The system receives data from devices via TCP socket connection.
        - Toggle 'Show Live Feed' in sidebar to view live detection feed.
        - Click on a device marker on the map for more details.
        - Check the connection log for detailed network activity.
        """)

def create_bottom_section_plotly():
    """
    Create the bottom section with a basic Plotly chart.
    """
    st.markdown("---")
    st.markdown("### Detection History")
    
    # Date range controls
    col1, col2 = st.columns([3, 2])
    
    with col1:
        # Dropdown for preset date ranges
        date_ranges = get_date_range_options()
        selected_range = st.selectbox(
            "Date Range",
            options=range(len(date_ranges)),
            format_func=lambda i: date_ranges[i]["label"],
            index=3  # Changed from 2 to 3 to default to "Year to date"
        )
        days_to_display = date_ranges[selected_range]["days"]
    
    with col2:
        # Refresh button that clears the cache to force data reload
        refresh = st.button("Refresh Data")
        
        # Chart type options
        chart_type = st.radio(
            "Chart Type",
            options=["Line", "Bar"],
            horizontal=True
        )
        
    # Force refresh on button click by clearing cache
    if refresh:
        st.cache_data.clear()
        st.rerun()
    
    # Calculate date range
    end_date = datetime.now().date()
    start_date = end_date - timedelta(days=days_to_display)
    
    # Simple direct database query
    try:
        logger.info(f"Querying detection data from {start_date} to {end_date}")
        
        # Basic query for detection counts
        date_query = """
        SELECT 
            DATE(timestamp) AS detection_date, 
            COUNT(DISTINCT detection_id) AS detection_events,
            SUM(num_detections) AS detection_count
        FROM detections
        WHERE timestamp BETWEEN %s AND %s
        GROUP BY detection_date
        ORDER BY detection_date ASC
        """
        
        # Execute query with parameters
        df = pd.read_sql(
            date_query, 
            engine, 
            params=(start_date.strftime('%Y-%m-%d'), end_date.strftime('%Y-%m-%d')),
            parse_dates=['detection_date']
        )
        
        logger.info(f"Query returned {len(df)} rows")
    except Exception as e:
        logger.error(f"Error in detection query: {e}")
        st.error(f"Error fetching detection data: {e}")
        df = pd.DataFrame(columns=["detection_date", "detection_events", "detection_count"])
    
    # If the dataframe is empty, show a message
    if df.empty:
        st.warning("No detection data available for the selected date range.")
        return
    
    # Create a metric selector for the chart
    metric = st.radio(
        "Chart Metric", 
        options=["Total Items Detected", "Detection Events"],
        horizontal=True,
        index=0
    )
    
    # Set the y-axis based on metric selection
    y_column = "detection_count" if metric == "Total Items Detected" else "detection_events"
    
    # VERY BASIC CHART - just use Plotly Express directly with minimal settings
    try:
        # Create the basic chart with proper markers for visibility
        if chart_type == "Line":
            fig = px.line(
                df,
                x="detection_date",
                y=y_column,
                title=f"Daily {metric}"
            )
            # Add markers explicitly to make points more visible
            fig.update_traces(mode='lines+markers', marker=dict(size=8))
        else:  # Bar chart
            fig = px.bar(
                df,
                x="detection_date",
                y=y_column,
                title=f"Daily {metric}"
            )
        
        # Improve appearance with grid lines
        fig.update_layout(
            xaxis=dict(
                showgrid=True,
                gridcolor='rgba(255,255,255,0.1)',
                tickformat='%b %d'
            ),
            yaxis=dict(
                showgrid=True,
                gridcolor='rgba(255,255,255,0.1)',
                title=y_column
            ),
            plot_bgcolor='#1e1e1e',
            paper_bgcolor='#1e1e1e',
            font=dict(color='white'),
            height=450  # Fixed height to ensure consistency
        )
        
        # Use ONLY plain st.plotly_chart - no interactivity for stability
        st.plotly_chart(fig, use_container_width=True)
        
        # Show summary
        st.markdown(f"**Total {metric}:** {int(df[y_column].sum())}")
        
        # Select date manually via dropdown instead of clicking
        date_options = df['detection_date'].dt.strftime('%Y-%m-%d').tolist()
        if date_options:
            selected_date = st.selectbox("Select a date to view details:", 
                                       options=date_options,
                                       format_func=lambda x: pd.to_datetime(x).strftime('%B %d, %Y'))
            
            if selected_date:
                # Display detailed data for the selected date
                display_detailed_detection_data(selected_date)
                
    except Exception as e:
        st.error(f"Error creating chart: {e}")
        logger.error(f"Chart error: {e}")

def display_detailed_detection_data(selected_date):
    """Fetch and display detection details for a selected date"""
    st.markdown("---")
    st.markdown(f"### Historical Waste Detection Data for {selected_date}")

    try:
        # First get summary information for this date
        summary_query = """
        SELECT 
            COUNT(DISTINCT device_id) AS devices_count,
            SUM(num_detections) AS total_detections,
            COUNT(DISTINCT detection_id) AS detection_events,
            AVG(gas_value) AS avg_gas_value
        FROM detections
        WHERE DATE(timestamp) = %s
        """
        df_summary = pd.read_sql(summary_query, engine, params=(selected_date,))
        
        if not df_summary.empty and df_summary['total_detections'].iloc[0] > 0:
            # Display summary information
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("Detection Events", df_summary['detection_events'].iloc[0])
            with col2:
                st.metric("Total Items Detected", df_summary['total_detections'].iloc[0])
            with col3:
                st.metric("Active Devices", df_summary['devices_count'].iloc[0])
            with col4:
                st.metric("Avg Gas Value", f"{df_summary['avg_gas_value'].iloc[0]:.2f}")
            
            # Get waste type distribution for this date
            waste_query = """
            SELECT 
                di.class_name, 
                COUNT(*) AS count,
                AVG(di.confidence) AS avg_confidence
            FROM detections d
            JOIN detected_items di ON d.detection_id = di.detection_id
            WHERE DATE(d.timestamp) = %s
            GROUP BY di.class_name
            ORDER BY count DESC
            """
            df_waste = pd.read_sql(waste_query, engine, params=(selected_date,))
            
            if not df_waste.empty:
                st.subheader("Waste Type Distribution")
                
                # Create two columns layout
                col1, col2 = st.columns([3, 2])
                
                with col1:
                    # Create a bar chart for waste types
                    fig = px.bar(
                        df_waste,
                        x='count', 
                        y='class_name',
                        orientation='h',
                        labels={'count': 'Number of Items', 'class_name': 'Waste Type'},
                        color='avg_confidence',
                        color_continuous_scale='RdYlGn',
                        range_color=[0.5, 1.0],
                        title="Waste Types Detected"
                    )
                    
                    fig.update_layout(
                        plot_bgcolor="#1e1e1e",
                        paper_bgcolor="#1e1e1e",
                        font=dict(color="#ffffff"),
                        height=400
                    )
                    
                    st.plotly_chart(fig, use_container_width=True)
                
                with col2:
                    # Display the data table
                    df_waste['avg_confidence'] = df_waste['avg_confidence'].round(2)
                    st.dataframe(df_waste, use_container_width=True)
            
            # Use parameterized query for detailed data (with LIMIT to prevent overloading)
            query = """
            SELECT 
                d.detection_id, 
                d.device_id, 
                d.timestamp, 
                d.num_detections, 
                d.gas_value,
                di.class_name, 
                di.confidence, 
                di.x_coord, 
                di.y_coord, 
                di.width, 
                di.height,
                k.keyframe_id
            FROM detections d
            LEFT JOIN detected_items di ON d.detection_id = di.detection_id
            LEFT JOIN keyframes k ON d.detection_id = k.detection_id
            WHERE DATE(d.timestamp) = %s
            ORDER BY d.timestamp ASC, d.detection_id ASC
            LIMIT 100;
            """
            
            df_details = pd.read_sql(query, engine, params=(selected_date,))
            
            if not df_details.empty:
                st.subheader("Detection Details")
                
                # Format the timestamp for better readability
                if 'timestamp' in df_details.columns:
                    df_details['timestamp'] = pd.to_datetime(df_details['timestamp']).dt.strftime('%H:%M:%S')
                
                # Round confidence values
                if 'confidence' in df_details.columns:
                    df_details['confidence'] = df_details['confidence'].round(2)
                
                # Show the details table
                st.dataframe(df_details, use_container_width=True)
                
                # If we have keyframes, show a gallery of sample images
                if 'keyframe_id' in df_details.columns and df_details['keyframe_id'].notna().any():
                    st.subheader("Sample Keyframes")
                    st.info("Click on an image to view full size")
                    
                    # Limit to at most 5 keyframes to display
                    keyframe_ids = df_details['keyframe_id'].dropna().unique()[:5]
                    
                    # Create a grid of images
                    cols = st.columns(min(len(keyframe_ids), 5))
                    
                    for i, keyframe_id in enumerate(keyframe_ids):
                        with cols[i % len(cols)]:
                            try:
                                # In a real implementation, you would fetch and display the actual image
                                # Here we're just showing a placeholder since the sample data has dummy image data
                                st.image("https://via.placeholder.com/300x200?text=Keyframe+ID+%s" % keyframe_id, 
                                         caption=f"Keyframe {int(keyframe_id)}", use_container_width=True)
                            except Exception as e:
                                st.warning(f"Error loading keyframe {int(keyframe_id)}: {e}")
            else:
                st.info("No detailed data available for this date.")
        else:
            st.warning("No detection data found for the selected date.")
            
    except Exception as e:
        st.error(f"Error fetching detailed detection data: {e}")
        logger.error(f"Error in display_detailed_detection_data: {str(e)}")

def get_date_range_options():
    """Get preset date range options for the chart"""
    today = datetime.now().date()
    
    return [
        {"label": "Last 7 days", "days": 7},
        {"label": "Last 30 days", "days": 30},
        {"label": "Last 90 days", "days": 90},
        {"label": "Year to date", "days": (today - datetime(today.year, 1, 1).date()).days},
        {"label": "All time", "days": 9999}  # A large number to ensure all data is included
    ]

def filter_date_range(df, days=30):
    """Filter dataframe to only include dates within the specified number of days"""
    if df.empty or days >= 9999:
        return df
        
    end_date = datetime.now().date()
    start_date = end_date - timedelta(days=days)
    
    # Convert detection_date to datetime if it's not already
    if not pd.api.types.is_datetime64_any_dtype(df["detection_date"]):
        df["detection_date"] = pd.to_datetime(df["detection_date"])
    
    # Filter to the date range
    mask = (df["detection_date"].dt.date >= start_date) & (df["detection_date"].dt.date <= end_date)
    return df[mask].copy()

def fill_missing_dates(df, days=30):
    """Fill in missing dates in the dataframe with zero counts"""
    if df.empty:
        return df
        
    # Ensure detection_date is datetime
    if not pd.api.types.is_datetime64_any_dtype(df["detection_date"]):
        df["detection_date"] = pd.to_datetime(df["detection_date"])
    
    # Get the date range
    if days >= 9999:
        # Use the min/max from the data
        start_date = df["detection_date"].min().date()
        end_date = df["detection_date"].max().date()
    else:
        # Use the specified number of days
        end_date = datetime.now().date()
        start_date = end_date - timedelta(days=days)
    
    # Create a continuous date range
    date_range = pd.date_range(start=start_date, end=end_date, freq='D')
    
    # Create a dataframe with all dates
    all_dates = pd.DataFrame({"detection_date": date_range})
    
    # Convert df dates to date only (no time component) for proper merging
    df_dates = df.copy()
    df_dates["detection_date"] = df_dates["detection_date"].dt.date
    df_dates["detection_date"] = pd.to_datetime(df_dates["detection_date"])
    
    # Merge with the original data
    merged = pd.merge(all_dates, df_dates, on="detection_date", how="left")
    
    # Fill missing values with zeros
    merged["detection_count"] = merged["detection_count"].fillna(0)
    
    return merged.sort_values("detection_date")

def debug_database_connection():
    """Function to debug database connection and data"""
    st.markdown("---")
    st.markdown("### Database Connection Debugger")
    
    # Add a call to our new debug function
    debug_detection_chart_data()
    
    # Button to test the daily detection counts query specifically
    if st.button("🔍 Test Detection Counts Query"):
        st.subheader("Detection Counts Query Test")
        
        try:
            # Test the exact query used in the chart
            query = """
            SELECT DATE(timestamp) AS detection_date, 
                   SUM(num_detections) AS detection_count
            FROM detections
            GROUP BY detection_date
            ORDER BY detection_date ASC;
            """
            
            df = pd.read_sql(query, engine)
            
            if not df.empty:
                st.success(f"✅ Query successful! Found {len(df)} dates with detection data.")
                
                # Convert dates for display
                if not pd.api.types.is_datetime64_any_dtype(df["detection_date"]):
                    df["detection_date"] = pd.to_datetime(df["detection_date"])
                
                # Show summary statistics
                st.write(f"Date range: {df['detection_date'].min().date()} to {df['detection_date'].max().date()}")
                st.write(f"Total detections: {int(df['detection_count'].sum())}")
                
                # Check for date gaps
                all_dates = pd.date_range(start=df['detection_date'].min(), end=df['detection_date'].max())
                missing_dates = [d for d in all_dates if d not in df['detection_date'].values]
                
                if missing_dates:
                    st.warning(f"⚠️ Found {len(missing_dates)} gaps in the date sequence.")
                    if len(missing_dates) < 10:
                        st.write("Missing dates:", [d.date() for d in missing_dates])
                    else:
                        st.write("First few missing dates:", [d.date() for d in missing_dates[:5]])
                else:
                    st.success("✅ No gaps in the date sequence.")
                
                # Display the data
                st.dataframe(df, use_container_width=True)
                
                # Create a simple chart to visualize the data
                fig = px.line(
                    df, 
                    x='detection_date', 
                    y='detection_count',
                    title="Detection Counts from Direct Query",
                    markers=True
                )
                st.plotly_chart(fig, use_container_width=True)
                
            else:
                st.warning("⚠️ Query returned no data.")
                
        except Exception as e:
            st.error(f"❌ Query failed: {e}")
    
    with st.expander("Database Connection Details", expanded=False):
        st.code(f"Database URI: {DB_URI.replace(DB_PASSWORD, '********')}")
        
        # Test the connection
        try:
            # Check if we can connect
            test_query = "SELECT 1"
            result = pd.read_sql(test_query, engine)
            st.success("✅ Database connection successful")
            
            # Check the tables
            tables_query = "SHOW TABLES"
            tables = pd.read_sql(tables_query, engine)
            st.write("Available tables:")
            st.dataframe(tables)
            
            # Get table row counts
            st.write("Table row counts:")
            counts = {}
            for table in tables.iloc[:, 0]:
                count_query = f"SELECT COUNT(*) as count FROM {table}"
                count = pd.read_sql(count_query, engine).iloc[0]['count']
                counts[table] = count
            
            counts_df = pd.DataFrame(list(counts.items()), columns=['Table', 'Row Count'])
            st.dataframe(counts_df)
            
        except Exception as e:
            st.error(f"❌ Database connection error: {e}")
            
    with st.expander("Detection Data Sample", expanded=False):
        try:
            # Get a sample of detection data
            sample_query = """
            SELECT * FROM detections 
            ORDER BY timestamp DESC 
            LIMIT 10
            """
            sample = pd.read_sql(sample_query, engine)
            
            if not sample.empty:
                st.write("Recent detections sample:")
                st.dataframe(sample)
                
                # Get date range
                range_query = """
                SELECT 
                    MIN(DATE(timestamp)) as min_date,
                    MAX(DATE(timestamp)) as max_date,
                    COUNT(DISTINCT DATE(timestamp)) as date_count
                FROM detections
                """
                date_range = pd.read_sql(range_query, engine)
                
                st.write("Date range in detections table:")
                st.dataframe(date_range)
                
                # Check for null timestamps
                null_query = "SELECT COUNT(*) as null_count FROM detections WHERE timestamp IS NULL"
                null_count = pd.read_sql(null_query, engine).iloc[0]['null_count']
                
                if null_count > 0:
                    st.warning(f"⚠️ Found {null_count} records with NULL timestamps")
                else:
                    st.success("✅ No NULL timestamps found")
                
            else:
                st.warning("No detection data found")
                
        except Exception as e:
            st.error(f"Error querying detection data: {e}")
            
    with st.expander("Run Custom SQL Query", expanded=False):
        custom_query = st.text_area("Enter a custom SQL query:", 
                                  "SELECT DATE(timestamp) as date, COUNT(*) as count FROM detections GROUP BY date ORDER BY date")
        
        if st.button("Run Query"):
            try:
                if custom_query.strip():
                    result = pd.read_sql(custom_query, engine)
                    st.write("Query results:")
                    st.dataframe(result)
                else:
                    st.warning("Please enter a query")
            except Exception as e:
                st.error(f"Error executing query: {e}")
                
def debug_detection_chart_data():
    """Debug the data flow for the detection chart"""
    
    with st.expander("Detection Chart Data Flow Debug", expanded=True):
        # 1. Get raw data from database
        st.subheader("1. Raw Database Query")
        try:
            query = """
            SELECT DATE(timestamp) AS detection_date, 
                   SUM(num_detections) AS detection_count  -- Sum detections per date
            FROM detections
            GROUP BY detection_date
            ORDER BY detection_date ASC;
            """
            raw_df = pd.read_sql(query, engine)
            
            if not raw_df.empty:
                # Convert to datetime for consistent handling
                if not pd.api.types.is_datetime64_any_dtype(raw_df["detection_date"]):
                    raw_df["detection_date"] = pd.to_datetime(raw_df["detection_date"])
                
                st.write(f"Raw data has {len(raw_df)} rows")
                st.dataframe(raw_df, use_container_width=True)
                
                # Check Feb 16th specifically
                feb16 = raw_df[raw_df['detection_date'].dt.strftime('%Y-%m-%d') == '2025-02-16']
                if not feb16.empty:
                    st.success(f"✅ Feb 16th data found: {feb16['detection_count'].values[0]} detections")
                else:
                    st.warning("⚠️ Feb 16th data not found in raw query!")
            else:
                st.warning("No data returned from database")
        except Exception as e:
            st.error(f"Error executing raw query: {e}")
        
        # 2. Check data after date filtering
        st.subheader("2. After Date Filtering")
        days_to_display = 30  # Default filter
        
        try:
            # Filter to date range
            end_date = datetime.now().date()
            start_date = end_date - timedelta(days=days_to_display)
            
            if not raw_df.empty:
                # Apply the same filter used in the chart
                mask = (raw_df["detection_date"].dt.date >= start_date) & (raw_df["detection_date"].dt.date <= end_date)
                filtered_df = raw_df[mask].copy()
                
                st.write(f"After filtering: {len(filtered_df)} rows")
                st.dataframe(filtered_df, use_container_width=True)
                
                # Check Feb 16th specifically
                feb16 = filtered_df[filtered_df['detection_date'].dt.strftime('%Y-%m-%d') == '2025-02-16']
                if not feb16.empty:
                    st.success(f"✅ Feb 16th still present after filtering: {feb16['detection_count'].values[0]} detections")
                else:
                    st.warning("⚠️ Feb 16th filtered out!")
            
        except Exception as e:
            st.error(f"Error in date filtering: {e}")
        
        # 3. Check after filling gaps
        st.subheader("3. After Filling Gaps")
        try:
            if 'filtered_df' in locals() and not filtered_df.empty:
                # Create continuous date range
                date_range = pd.date_range(start=start_date, end=end_date, freq='D')
                
                # Create dataframe with all dates
                all_dates = pd.DataFrame({"detection_date": date_range})
                
                # Merge with filtered data
                filtered_df_date_only = filtered_df.copy()
                filtered_df_date_only["detection_date"] = filtered_df_date_only["detection_date"].dt.date
                filtered_df_date_only["detection_date"] = pd.to_datetime(filtered_df_date_only["detection_date"])
                
                merged_df = pd.merge(all_dates, filtered_df_date_only, on="detection_date", how="left")
                merged_df["detection_count"] = merged_df["detection_count"].fillna(0)
                
                st.write(f"After filling gaps: {len(merged_df)} rows")
                st.dataframe(merged_df, use_container_width=True)
                
                # Check Feb 16th specifically
                feb16 = merged_df[merged_df['detection_date'].dt.strftime('%Y-%m-%d') == '2025-02-16']
                if not feb16.empty:
                    st.write(f"Feb 16th after gap filling: {feb16['detection_count'].values[0]} detections")
                    
                    # If it's zero but should have data, there's a merge problem
                    if feb16['detection_count'].values[0] == 0:
                        st.error("⚠️ Feb 16th data was LOST during the merge/gap filling process!")
                        
                        # Check the specific format of the dates to see if there's a mismatch
                        st.write("Date format in filtered_df:")
                        if not filtered_df.empty:
                            feb16_filtered = filtered_df[filtered_df['detection_date'].dt.strftime('%Y-%m-%d') == '2025-02-16']
                            if not feb16_filtered.empty:
                                st.write(f"Feb 16th original date value: {feb16_filtered['detection_date'].iloc[0]}")
                                st.write(f"Date type: {type(feb16_filtered['detection_date'].iloc[0])}")
                            
                        st.write("Date format in date_range:")
                        feb16_idx = (date_range.strftime('%Y-%m-%d') == '2025-02-16')
                        if feb16_idx.any():
                            st.write(f"Feb 16th in date_range: {date_range[feb16_idx][0]}")
                            st.write(f"Date type: {type(date_range[feb16_idx][0])}")
                else:
                    st.error("⚠️ Feb 16th missing from the filled dataset!")
        except Exception as e:
            st.error(f"Error in gap filling: {e}")
