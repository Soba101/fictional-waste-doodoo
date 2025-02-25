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

from utils import check_device_status, discover_devices, add_connection_log
from state_manager import calculate_metrics, process_queues

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
    # Bottom Section: Historical Chart
    create_bottom_section()
    
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
    
    # Display filters
    st.sidebar.subheader("Display Settings")
    selected_year = st.sidebar.selectbox("Select Year", [2023, 2024, 2025])
    detection_threshold = st.sidebar.slider("Detection Threshold", 0.0, 1.0, 0.5, 0.05)
    gas_threshold = st.sidebar.slider("Gas Alert Threshold", 0, 1000, 500, 50)
    
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

def create_bottom_section():
    """Create the bottom section with historical chart"""
    st.markdown("---")
    st.markdown("### Detection History")
    
    # Prepare data for chart
    if st.session_state.detection_history:
        # Group by hour for the chart
        df_history = pd.DataFrame(st.session_state.detection_history)
        df_history['hour'] = df_history['time'].dt.floor('h')
        
        hourly_counts = df_history.groupby(['hour', 'device'])['count'].sum().reset_index()
        hourly_counts = hourly_counts.sort_values('hour')
        
        # Create chart
        chart = alt.Chart(hourly_counts).mark_line(point=True).encode(
            x=alt.X('hour:T', title='Time'),
            y=alt.Y('count:Q', title='Detections'),
            color=alt.Color('device:N', title='Device'),
            tooltip=['hour', 'device', 'count']
        ).properties(
            width=800,
            height=300,
            title='Hourly Detection Counts by Device'
        ).interactive()
        
        st.altair_chart(chart, use_container_width=True)
    else:
        # Just create a placeholder chart with sample data
        sample_data = {
            'time': pd.date_range(start='2023-01-01', periods=10, freq='h'),
            'detections': np.random.randint(0, 20, 10)
        }
        df_sample = pd.DataFrame(sample_data).set_index('time')
        st.line_chart(df_sample)
        st.caption("Sample data shown. Waiting for real detection data...")