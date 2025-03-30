import streamlit as st
import config
import socket

# Add custom CSS to ensure wide mode
st.markdown("""
<style>
    .block-container {
        max-width: 100% !important;
        padding-top: 1rem;
        padding-right: 1rem;
        padding-left: 1rem;
        padding-bottom: 1rem;
    }
</style>
""", unsafe_allow_html=True)

import pandas as pd
import numpy as np
import folium
from streamlit_folium import st_folium
import altair as alt
import time
import logging
from datetime import datetime, timedelta
import requests
import io
from PIL import Image
import pymysql
from sqlalchemy import create_engine
import plotly.express as px
from streamlit_plotly_events import plotly_events
import plotly.graph_objects as go
import matplotlib.pyplot as plt

from utils import check_device_status, discover_devices, add_connection_log
from state_manager import calculate_metrics, process_queues
 
# Database connection details
DB_HOST = config.DATABASE_HOST
DB_USER = config.DATABASE_USER
DB_PASSWORD = config.DATABASE_PASSWORD
DB_NAME = config.DATABASE_NAME
DB_PORT = config.DATABASE_PORT

def verify_database_connection():
    """Verify database connection and log status."""
    try:
        # Test connection with explicit parameters
        connection = pymysql.connect(
            host=DB_HOST,
            port=DB_PORT,
            user=DB_USER,
            password=DB_PASSWORD,
            database=DB_NAME,
            connect_timeout=5  # Add timeout
        )
        connection.ping()  # Test if connection is alive
        connection.close()
        logger.info(f"Database connection verified successfully to {DB_HOST}:{DB_PORT}")
        return True, None
    except Exception as e:
        error_msg = f"Database connection failed: {str(e)}"
        logger.error(f"{error_msg} (Host: {DB_HOST}, Port: {DB_PORT}, User: {DB_USER}, DB: {DB_NAME})")
        return False, error_msg

# Create SQLAlchemy engine with connection pooling and better logging
engine = create_engine(
    f"mariadb+pymysql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}",
    pool_size=config.DATABASE_POOL_SIZE,
    max_overflow=config.DATABASE_MAX_OVERFLOW,
    pool_timeout=config.DATABASE_POOL_TIMEOUT,
    pool_recycle=config.DATABASE_POOL_RECYCLE,
    echo=False  # Disable SQL query logging
)

def fetch_detection_data():
    """Fetch daily detection counts and metrics from MariaDB using SQLAlchemy."""
    try:
        # Verify connection first
        if not verify_database_connection():
            return pd.DataFrame()
            
        # Improved query with all necessary metrics
        query = """
        SELECT 
            DATE(timestamp) AS detection_date,
            COUNT(DISTINCT detection_id) AS detection_events,
            SUM(num_detections) AS detection_count,
            AVG(gas_value) AS avg_gas_value,
            MAX(gas_value) AS max_gas_value,
            COUNT(DISTINCT device_id) AS active_devices
        FROM detections
        WHERE 
            timestamp IS NOT NULL AND
            timestamp >= DATE_SUB(NOW(), INTERVAL 90 DAY)
        GROUP BY DATE(timestamp)
        ORDER BY detection_date ASC;
        """
        
        # Execute the query and log the result
        logger.info("Executing detection data query")
        df = pd.read_sql(query, engine)
        
        # Fill NaN values with 0
        df = df.fillna(0)
        
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
        return pd.DataFrame()

# Setup logger
logger = logging.getLogger('waste-dashboard.ui')

def create_dashboard_ui(receiver, log_file):
    """Create the dashboard UI using Streamlit components"""
    #######################
    # Check Database Connection
    db_status, error_msg = verify_database_connection()
    
    #######################
    # Process Data
    process_queues(receiver)
    metrics = calculate_metrics()
    
    #######################
    # Sidebar
    create_sidebar(receiver)
    
    #######################
    # Main Layout
    main_container = st.container()
    with main_container:
        # Title and Status
        col1, col2 = st.columns([2, 3])
        with col1:
            st.write('<h1 style="margin: 0; white-space: nowrap;">Waste Detection</h1>', unsafe_allow_html=True)
        with col2:
            st.empty()
        
        # Key Metrics
        with st.container():
            stat_cols = st.columns(4)
            with stat_cols[0]:
                st.metric(
                    label="Total Detections", 
                    value=metrics["total_detections"],
                    delta=f"{metrics['detection_rate']:.1f}/hour"
                )
            with stat_cols[1]:
                st.metric(
                    label="Gas Alerts", 
                    value=metrics["total_gas_alerts"],
                    delta=metrics["gas_delta"]
                )
            with stat_cols[2]:
                st.metric(
                    label="Active Devices", 
                    value=metrics["active_devices"]
                )
            with stat_cols[3]:
                st.metric(
                    label="Total Items", 
                    value=sum(metrics["waste_categories"].values())
                )
        
        # Main Content Tabs
        tab1, tab2, tab3 = st.tabs(["Map View", "Analytics", "Device Details"])
        
        with tab1:
            create_map_view(metrics)
        
        with tab2:
            create_analytics_view(metrics)
        
        with tab3:
            create_device_details(metrics)
        
        # Footer
        st.markdown("---")
        col1, col2 = st.columns(2)
        with col1:
            st.markdown(f"**Dashboard Status:** Running since {datetime.now().strftime('%H:%M:%S')}")
        with col2:
            st.markdown(f"**Log File:** {log_file}")

def create_sidebar(receiver):
    """Create the sidebar with controls and status"""
    with st.sidebar:
        st.title("Dashboard Controls")
        
        # Add discover devices button
        if st.button("🔍 Discover Devices"):
            st.info("Scanning network for devices...")
            from utils import discover_devices
            discover_devices()
        
        # Show connection status
        st.subheader("Connection Status")
        
        # Get own IP address
        import socket
        try:
            hostname = socket.gethostname()
            dashboard_ip = socket.gethostbyname(hostname)
            st.text(f"Dashboard IP: {dashboard_ip}")
            
            # Get all IPs
            ip_info = socket.getaddrinfo(hostname, None)
            alt_ips = set()
            for item in ip_info:
                ip = item[4][0]
                if ip != dashboard_ip and not ip.startswith('127.') and ':' not in ip:
                    alt_ips.add(ip)
            if alt_ips:
                st.text("Alternative IPs:")
                for ip in alt_ips:
                    st.text(f"  • {ip}")
        except:
            st.text("Could not determine IP")
        
        # Show MQTT connection status
        mqtt_status = receiver.get_status()
        active_devices = mqtt_status.get("active_devices", set())
        if mqtt_status["running"] and active_devices:
            st.markdown("""
                <div style="background-color: #0f5132; color: white; padding: 10px; border-radius: 5px; margin: 5px 0;">
                    ✓ Connected to MQTT<br>
                    Active Devices: {count}
                </div>
            """.format(count=len(active_devices)), unsafe_allow_html=True)
        else:
            st.markdown("""
                <div style="background-color: #842029; color: white; padding: 10px; border-radius: 5px; margin: 5px 0;">
                    ✗ No Active Devices
                </div>
            """, unsafe_allow_html=True)
            
        # Show database connection status
        db_connected = verify_database_connection()[0]
        if db_connected:
            st.markdown("""
                <div style="background-color: #0f5132; color: white; padding: 10px; border-radius: 5px; margin: 5px 0;">
                    ✓ Connected to Database
                </div>
            """, unsafe_allow_html=True)
        else:
            st.markdown("""
                <div style="background-color: #842029; color: white; padding: 10px; border-radius: 5px; margin: 5px 0;">
                    ✗ Database Not Connected
                </div>
            """, unsafe_allow_html=True)
            
        # Show active devices
        active_devices = st.session_state.receiver_status.get("active_devices", set())
        if active_devices:
            st.text(f"Active Devices: {len(active_devices)}")
            for device_id in active_devices:
                if device_id in st.session_state.device_ips:
                    st.text(f"  • {device_id}: {st.session_state.device_ips[device_id]}")
                else:
                    st.text(f"  • {device_id}: Unknown IP")
        else:
            st.text("No Active Devices")

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
              delta=f"{metrics['detection_rate']:.1f}/hour")
    st.metric(label="Gas Alerts", value=str(metrics["total_gas_alerts"]), 
              delta=f"{metrics['gas_delta']}")
    st.metric(label="Active Edge Devices", value=str(metrics["active_devices"]))
    
    # Add waste category metrics
    st.markdown("#### Waste Categories")
    for category, count in metrics["waste_categories"].items():
        percentage = metrics["waste_percentages"].get(category, 0)
        st.metric(label=category.capitalize(), 
                 value=str(count),
                 delta=f"{percentage:.1f}%")
    
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
            "Gas Alerts": device_data.get("gas_alerts", 0),
            "Last Update": last_update_str
        })
    
    if device_list:
        df_devices = pd.DataFrame(device_list)
        st.dataframe(df_devices, use_container_width=True, hide_index=True)
    else:
        st.info("No devices connected yet. Waiting for connections...")

@st.cache_resource(ttl=60)
def get_cached_map_data(devices, user_location=None, last_update=None):
    """Create and cache map data"""
    # Force cache invalidation when devices are updated
    current_time = datetime.now().strftime('%H:%M:%S')
    
    # Find first active device with valid coordinates
    center = config.MAP_DEFAULT_CENTER
    for device_id, device_data in devices.items():
        if 'lat' in device_data and 'lon' in device_data:
            center = [device_data['lat'], device_data['lon']]
            break

    # Create map centered on device location or default
    m = folium.Map(
        location=center,
        zoom_start=config.MAP_DEFAULT_ZOOM,
        tiles="cartodbdark_matter"
    )
    
    # Add markers for each device
    for device_id, device_data in devices.items():
        # Skip devices without location data
        if 'lat' not in device_data or 'lon' not in device_data:
            logger.warning(f"Device {device_id} has no location data")
            continue
            
        # Determine device status
        try:
            last_updated = device_data.get('last_updated')
            if isinstance(last_updated, str):
                last_updated = datetime.fromisoformat(last_updated)
            time_diff = datetime.now() - last_updated
            is_active = time_diff < timedelta(minutes=5)
        except:
            is_active = False
        
        # Create popup content
        popup_content = f"""
        <div style='font-family: Arial, sans-serif;'>
            <h4>{device_id}</h4>
            <p>Status: {'🟢 Active' if is_active else '🔴 Inactive'}</p>
            <p>Location: {device_data['lat']:.6f}, {device_data['lon']:.6f}</p>
            <p>Detections: {device_data.get('detections', 0)}</p>
            <p>Gas Alerts: {device_data.get('gas_alerts', 0)}</p>
            <p>Last Updated: {device_data.get('last_updated', 'Never').strftime('%H:%M:%S') if isinstance(device_data.get('last_updated'), datetime) else 'Never'}</p>
        </div>
        """
            
        # Add marker
        folium.Marker(
            location=[device_data['lat'], device_data['lon']],
            popup=folium.Popup(popup_content, max_width=300),
            icon=folium.Icon(
                color='green' if is_active else 'red',
                icon='video-camera' if is_active else 'warning-sign',
                prefix='fa'
            )
        ).add_to(m)
        
    return m

def create_map_view(metrics):
    """Create map view"""
    if not st.session_state.get('show_live_feed', False):
        st.markdown("### Device Locations")
        user_location = get_user_location()
        last_update_time = st.session_state.last_processed_data
        
        # Get cached map data
        cached_map = get_cached_map_data(st.session_state.devices, user_location, last_update_time)
        
        # Display map using st_folium (not cached)
        map_data = st_folium(cached_map, width="100%", height=600)
        
        # Handle map click events
        if map_data["last_object_clicked"] is not None:
            clicked_lat = map_data["last_object_clicked"].get("lat")
            clicked_lng = map_data["last_object_clicked"].get("lng")
            
            if clicked_lat and clicked_lng:
                # Find device near clicked coordinates
                for device_id, device_data in st.session_state.devices.items():
                    if 'lat' in device_data and 'lon' in device_data:
                        if (abs(device_data["lat"] - clicked_lat) < 0.01 and 
                            abs(device_data["lon"] - clicked_lng) < 0.01):
                            display_device_info(device_id, device_data)
                            break
    else:
        col1, col2 = st.columns([3, 1])
        with col1:
            user_location = get_user_location()
            last_update_time = st.session_state.last_processed_data
            cached_map = get_cached_map_data(st.session_state.devices, user_location, last_update_time)
            st_folium(cached_map, width="100%", height=600)
        with col2:
            if "show_device_feed" in st.session_state:
                device_id = st.session_state.show_device_feed
                if device_id in st.session_state.devices:
                    device_data = st.session_state.devices[device_id]
                    st.markdown("### Device Info")
                    display_device_info(device_id, device_data)
                    
                    # Display live video feed
                    if 'last_frame' in device_data:
                        try:
                            # Convert base64 frame to image
                            import base64
                            import io
                            from PIL import Image
                            
                            # Decode base64 frame
                            frame_data = base64.b64decode(device_data['last_frame'])
                            image = Image.open(io.BytesIO(frame_data))
                            
                            # Display the image
                            st.image(image, caption="Live Feed", use_column_width=True)
                        except Exception as e:
                            st.error(f"Error displaying video feed: {e}")
                            logger.error(f"Error displaying video feed: {e}")
                    else:
                        st.info("Waiting for video feed...")

def display_device_info(device_id, device_data):
    """Display detailed information about a device"""
    st.markdown(f"#### Device: {device_id}")
    
    # Status
    is_active = device_id in st.session_state.receiver_status.get("active_devices", set())
    status_indicator = "🟢" if is_active else "🔴"
    st.markdown(f"**Status:** {status_indicator} {'Active' if is_active else 'Inactive'}")
    
    # Metrics
    col1, col2 = st.columns(2)
    with col1:
        st.metric("Total Detections", device_data.get("detections", 0))
    with col2:
        st.metric("Gas Alerts", device_data.get("gas_alerts", 0))
    
    # Last Update
    if 'last_updated' in device_data:
        try:
            last_updated = device_data['last_updated']
            if isinstance(last_updated, str):
                last_updated = datetime.fromisoformat(last_updated)
            st.markdown(f"**Last Update:** {last_updated.strftime('%Y-%m-%d %H:%M:%S')}")
        except:
            st.markdown("**Last Update:** Unknown")
    
    # Location
    if 'lat' in device_data and 'lon' in device_data:
        st.markdown(f"**Location:** {device_data['lat']:.6f}, {device_data['lon']:.6f}")
    
    # IP Address
    if device_id in st.session_state.device_ips:
        st.markdown(f"**IP Address:** {st.session_state.device_ips[device_id]}")

def fill_missing_dates(df):
    """Fill missing dates in the detection data with zeros"""
    if df.empty:
        return df
        
    # Ensure we have a datetime index
    df['detection_date'] = pd.to_datetime(df['detection_date'])
    df.set_index('detection_date', inplace=True)
    
    # Create a complete date range
    date_range = pd.date_range(start=df.index.min(), end=df.index.max(), freq='D')
    
    # Reindex the dataframe with the complete date range
    df = df.reindex(date_range, fill_value=0)
    
    # Reset the index to make detection_date a column again
    df.reset_index(inplace=True)
    df.rename(columns={'index': 'detection_date'}, inplace=True)
    
    return df

@st.cache_data(ttl=60)
def get_cached_analytics_data(metrics):
    """Cache analytics data calculations"""
    return {
        'waste_data': pd.DataFrame({
            'Category': list(metrics["waste_categories"].keys()),
            'Count': list(metrics["waste_categories"].values()),
            'Percentage': [metrics["waste_percentages"].get(cat, 0) for cat in metrics["waste_categories"].keys()]
        }).sort_values('Count', ascending=False)
    }

def create_analytics_view(metrics):
    """Create analytics view with improved layout and interactivity"""
    # Main container with tabs for different views
    tab1, tab2 = st.tabs(["Overview", "Detailed Analysis"])
    
    with tab1:
        # Top row with key metrics
        metric_cols = st.columns(4)
        with metric_cols[0]:
            st.metric(
                label="Daily Detections",
                value=metrics.get("daily_detections", 0),
                delta=f"{metrics.get('daily_detection_rate', 0):.1f}/hour"
            )
        with metric_cols[1]:
            st.metric(
                label="Waste Categories",
                value=len(metrics.get("waste_categories", {})),
                delta="Active"
            )
        with metric_cols[2]:
            st.metric(
                label="Avg. Gas Level",
                value=f"{metrics.get('avg_gas_level', 0):.1f}",
                delta=f"{metrics.get('gas_level_delta', 0):.1f}"
            )
        with metric_cols[3]:
            st.metric(
                label="Detection Rate",
                value=f"{metrics.get('detection_rate', 0):.1f}/hour",
                delta=f"{metrics.get('rate_delta', 0):.1f}"
            )
        
        # Main content area with improved layout
        col1, col2 = st.columns([3, 1])
        with col1:
            create_bottom_section_plotly()
        with col2:
            st.markdown("### Waste Categories")
            cached_data = get_cached_analytics_data(metrics)
            display_waste_categories_with_data(cached_data['waste_data'])
            
            # Add export button
            if st.button("📥 Export Data"):
                export_analytics_data(cached_data)
    
    with tab2:
        st.markdown("### Detailed Analysis")
        # Add date range selector
        date_col1, date_col2 = st.columns(2)
        with date_col1:
            start_date = st.date_input(
                "Start Date",
                datetime.now().date() - timedelta(days=30),
                max_value=datetime.now().date()
            )
        with date_col2:
            end_date = st.date_input(
                "End Date",
                datetime.now().date(),
                max_value=datetime.now().date()
            )
        
        # Add analysis options
        analysis_type = st.selectbox(
            "Analysis Type",
            ["Trend Analysis", "Category Breakdown", "Device Performance", "Environmental Impact"]
        )
        
        if analysis_type == "Trend Analysis":
            display_trend_analysis(start_date, end_date)
        elif analysis_type == "Category Breakdown":
            display_category_breakdown(start_date, end_date)
        elif analysis_type == "Device Performance":
            display_device_performance(start_date, end_date)
        else:
            display_environmental_impact(start_date, end_date)

def display_waste_categories_with_data(waste_data):
    """Display waste categories with improved visualization"""
    if waste_data.empty:
        st.warning("No waste category data available.")
        return
        
    fig = px.bar(
        waste_data,
        x='Count',
        y='Category',
        orientation='h',
        text='Percentage',
        labels={'Count': 'Number of Items', 'Category': 'Waste Type'},
        title="Waste Distribution",
        color='Count',  # Use count for color intensity
        color_continuous_scale='Viridis'  # Changed from RdYlGn
    )
    
    # Enhanced styling
    fig.update_layout(
        height=300,
        margin=dict(l=0, r=0, t=30, b=0),
        plot_bgcolor="#1e1e1e",
        paper_bgcolor="#1e1e1e",
        font=dict(color="#ffffff"),
        hovermode='y unified',
        showlegend=False,
        coloraxis_showscale=False
    )
    
    fig.update_traces(
        texttemplate='%{text:.1f}%',
        textposition='outside',
        marker_line_color='#ffffff',
        marker_line_width=1
    )
    
    # Add hover template
    fig.update_traces(
        hovertemplate="<b>%{y}</b><br>" +
                     "Count: %{x}<br>" +
                     "Percentage: %{text}<br>" +
                     "<extra></extra>"
    )
    
    st.plotly_chart(fig, use_container_width=True)

def create_bottom_section_plotly():
    """Create the bottom section with enhanced detection history chart"""
    st.markdown("### Detection History")
    
    # Controls in an expander for better space management
    with st.expander("Chart Controls", expanded=False):
        col1, col2, col3 = st.columns([2, 1, 1])
        
        with col1:
            date_ranges = [
                {"label": "Last 7 days", "days": 7},
                {"label": "Last 30 days", "days": 30},
                {"label": "Last 90 days", "days": 90},
                {"label": "Year to date", "days": (datetime.now().date() - datetime(datetime.now().year, 1, 1).date()).days},
                {"label": "All time", "days": 9999}
            ]
            selected_range = st.selectbox(
                "Date Range",
                options=range(len(date_ranges)),
                format_func=lambda i: date_ranges[i]["label"],
                index=1  # Default to 30 days
            )
        
        with col2:
            chart_type = st.radio(
                "Chart Type",
                options=["Line", "Bar", "Area"],
                horizontal=True,
                index=0  # Default to Line
            )
        
        with col3:
            refresh = st.button("🔄 Refresh")
    
    # Force refresh on button click
    if refresh:
        st.cache_data.clear()
        st.rerun()
    
    # Get cached detection data
    df = get_cached_detection_data()
    
    if df.empty:
        st.warning("No detection data available.")
        return
    
    # Filter data based on selected date range
    days = date_ranges[selected_range]["days"]
    cutoff_date = datetime.now().date() - timedelta(days=days)
    df['detection_date'] = pd.to_datetime(df['detection_date']).dt.date
    df = df[df['detection_date'] >= cutoff_date]
    
    # Enhanced metric selector
    metric = st.radio(
        "Chart Metric", 
        options=["Total Items", "Detection Events", "Gas Level"],
        horizontal=True,
        index=0
    )
    
    # Set the y-axis based on metric selection
    y_column = {
        "Total Items": "detection_count",
        "Detection Events": "detection_events",
        "Gas Level": "avg_gas_value"
    }[metric]
    
    try:
        # Create the chart with enhanced styling
        if chart_type == "Line":
            fig = px.line(
                df,
                x="detection_date",
                y=y_column,
                title=f"Daily {metric}"
            )
            fig.update_traces(
                mode='lines+markers',
                marker=dict(size=8, color='#00ff00'),
                line=dict(width=2, color='#00ff00')
            )
        elif chart_type == "Bar":
            fig = px.bar(
                df,
                x="detection_date",
                y=y_column,
                title=f"Daily {metric}",
                color_discrete_sequence=['#00ff00']
            )
        else:  # Area chart
            fig = px.area(
                df,
                x="detection_date",
                y=y_column,
                title=f"Daily {metric}",
                color_discrete_sequence=['#00ff00']
            )
        
        # Enhanced layout
        fig.update_layout(
            xaxis=dict(
                showgrid=True,
                gridcolor='rgba(255,255,255,0.1)',
                tickformat='%b %d',
                title="Date"
            ),
            yaxis=dict(
                showgrid=True,
                gridcolor='rgba(255,255,255,0.1)',
                title=metric
            ),
            plot_bgcolor='#1e1e1e',
            paper_bgcolor='#1e1e1e',
            font=dict(color='white'),
            height=450,
            hovermode='x unified'
        )
        
        # Add trend line for line charts
        if chart_type == "Line":
            # Calculate trend line
            x_numeric = np.arange(len(df))
            z = np.polyfit(x_numeric, df[y_column], 1)
            p = np.poly1d(z)
            
            fig.add_trace(
                go.Scatter(
                    x=df['detection_date'],
                    y=p(x_numeric),
                    name='Trend',
                    line=dict(color='red', dash='dash', width=2)
                )
            )
        
        st.plotly_chart(fig, use_container_width=True)
        
        # Summary statistics with improved formatting
        st.markdown("### Summary Statistics")
        col1, col2, col3 = st.columns(3)
        
        with col1:
            total = int(df[y_column].sum())
            st.metric(
                "Total",
                f"{total:,}",
                delta=f"{total/len(df):.1f}/day" if len(df) > 0 else None
            )
        with col2:
            avg = df[y_column].mean()
            st.metric(
                "Average",
                f"{avg:.1f}",
                delta=f"{(df[y_column].std()/avg*100):.1f}% σ" if avg > 0 else None
            )
        with col3:
            peak = int(df[y_column].max())
            st.metric(
                "Peak",
                f"{peak:,}",
                delta=f"{(peak/avg if avg > 0 else 0):.1f}x avg" if avg > 0 else None
            )
            
    except Exception as e:
        st.error(f"Error creating chart: {e}")
        logger.error(f"Chart error: {e}")

def export_analytics_data(cached_data):
    """Export analytics data to CSV"""
    try:
        # Create DataFrame from cached data
        df = pd.DataFrame(cached_data['waste_data'])
        
        # Generate timestamp for filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"waste_analytics_{timestamp}.csv"
        
        # Convert to CSV
        csv = df.to_csv(index=False)
        
        # Create download button
        st.download_button(
            label="📥 Download CSV",
            data=csv,
            file_name=filename,
            mime="text/csv"
        )
    except Exception as e:
        st.error(f"Error exporting data: {e}")
        logger.error(f"Export error: {e}")

def create_device_details(metrics):
    """Create device details view"""
    st.markdown("### Device Status")
    
    # Force refresh when devices are updated
    current_time = datetime.now().strftime('%H:%M:%S')
    st.markdown(f"<div style='display: none'>{current_time}</div>", unsafe_allow_html=True)
    
    create_device_status_table(metrics)
    
    if st.session_state.get('show_connection_log', False):
        st.markdown("### Connection Log")
        display_connection_log()

@st.cache_data(ttl=300)
def get_cached_detection_data():
    """Cache detection data fetch and processing"""
    df = fetch_detection_data()
    if not df.empty:
        return fill_missing_dates(df)
    return pd.DataFrame(columns=["detection_date", "detection_count"])

def create_device_status_table(metrics):
    """Create an enhanced device status table"""
    if not st.session_state.devices:
        st.info("No devices connected yet. Waiting for connections...")
        return
        
    # Create DataFrame for devices
    device_data = []
    for device_id, device_info in st.session_state.devices.items():
        is_active = device_id in st.session_state.receiver_status.get("active_devices", set())
        
        try:
            last_updated = device_info['last_updated']
            if isinstance(last_updated, str):
                last_updated = datetime.fromisoformat(last_updated)
            time_diff = datetime.now() - last_updated
            status = "🟢 Active" if time_diff < timedelta(minutes=5) else "🟠 Inactive"
            last_seen = last_updated.strftime("%H:%M:%S")
        except:
            status = "🔴 Unknown"
            last_seen = "Unknown"
            
        device_data.append({
            "Device ID": device_id,
            "Status": status,
            "Detections": device_info["detections"],
            "Gas Alerts": device_info.get("gas_alerts", 0),
            "Last Seen": last_seen,
            "IP Address": st.session_state.device_ips.get(device_id, "Unknown"),
            "Live Feed": device_id,  # We'll use this to create buttons
            "Connection Log": device_id  # We'll use this to create buttons
        })
    
    # Convert to DataFrame
    df_devices = pd.DataFrame(device_data)
    
    # Create columns for the table and buttons
    col1, col2 = st.columns([3, 1])
    
    with col1:
        # Create headers first
        header_cols = st.columns([2, 2, 1, 1, 1.5, 2, 1.5, 1.5])
        with header_cols[0]:
            st.markdown("**Device ID**")
        with header_cols[1]:
            st.markdown("**Status**")
        with header_cols[2]:
            st.markdown("**Detections**")
        with header_cols[3]:
            st.markdown("**Gas Alerts**")
        with header_cols[4]:
            st.markdown("**Last Seen**")
        with header_cols[5]:
            st.markdown("**IP Address**")
        with header_cols[6]:
            st.markdown("**Live Feed**")
        with header_cols[7]:
            st.markdown("**Log**")
        
        # Add a separator line
        st.markdown("---")
        
        # Display the table rows
        for index, row in df_devices.iterrows():
            cols = st.columns([2, 2, 1, 1, 1.5, 2, 1.5, 1.5])
            with cols[0]:
                st.write(row["Device ID"])
            with cols[1]:
                st.write(row["Status"])
            with cols[2]:
                st.write(str(row["Detections"]))
            with cols[3]:
                st.write(str(row["Gas Alerts"]))
            with cols[4]:
                st.write(row["Last Seen"])
            with cols[5]:
                st.write(row["IP Address"])
            with cols[6]:
                if st.button("📺 Live", key=f"live_{row['Device ID']}"):
                    st.session_state.show_device_feed = row["Device ID"]
                    st.session_state.show_live_feed = True
            with cols[7]:
                if st.button("📝", key=f"log_{row['Device ID']}"):
                    st.session_state.show_connection_log = True
                    st.session_state.selected_device_log = row["Device ID"]
    
    # Show live feed or connection log in the second column if selected
    with col2:
        if st.session_state.get("show_live_feed", False) and "show_device_feed" in st.session_state:
            device_id = st.session_state.show_device_feed
            if device_id in st.session_state.devices:
                device_data = st.session_state.devices[device_id]
                st.markdown("### Live Feed")
                
                # Get device IP address
                device_ip = st.session_state.device_ips.get(device_id, None)
                if device_ip and device_ip != "Unknown":
                    # Create iframe to show live feed from device's web server
                    video_url = f"http://{device_ip}:8000/video_feed"
                    st.markdown(f"""
                        <div style="width:100%; height:400px; background-color:#1e1e1e; border-radius:10px; overflow:hidden;">
                            <iframe src="{video_url}" 
                                    width="100%" 
                                    height="100%" 
                                    frameborder="0" 
                                    style="background-color:#1e1e1e;">
                            </iframe>
                        </div>
                        """, 
                        unsafe_allow_html=True
                    )
                else:
                    st.error("Device IP address unknown. Cannot display video feed.")
                
                # Add a close button
                if st.button("❌ Close Feed"):
                    st.session_state.show_live_feed = False
                    st.session_state.show_device_feed = None
        
        elif st.session_state.get("show_connection_log", False) and "selected_device_log" in st.session_state:
            device_id = st.session_state.selected_device_log
            st.markdown(f"### Connection Log - {device_id}")
            
            # Filter connection log for selected device
            device_logs = [log for log in st.session_state.connection_log 
                         if "device_id" in log and log["device_id"] == device_id]
            
            # Display logs
            for log in device_logs[-10:]:  # Show last 10 logs
                st.text(f"{log['timestamp'].strftime('%H:%M:%S')}: {log['event']}")
                if 'details' in log:
                    st.text(f"  {log['details']}")
            
            # Add a close button
            if st.button("❌ Close Log"):
                st.session_state.show_connection_log = False
                st.session_state.selected_device_log = None

def display_connection_log():
    """Display the connection log with formatting"""
    if not st.session_state.connection_log:
        st.info("No connection events recorded yet")
        return
        
    for entry in reversed(st.session_state.connection_log[-10:]):
        timestamp = entry["timestamp"].strftime("%H:%M:%S")
        device = entry.get("device_id", "")
        event = entry["event"]
        details = entry.get("details", "")
        
        # Create a formatted log entry
        if device:
            st.markdown(f"**{timestamp}** [{device}] {event}")
        else:
            st.markdown(f"**{timestamp}** {event}")
            
        if details:
            st.markdown(f"<span style='margin-left:20px; color: #999;'>{details}</span>", 
                      unsafe_allow_html=True)

def display_trend_analysis(start_date, end_date):
    """Display trend analysis for the selected date range"""
    try:
        # Fetch data for the selected date range
        query = """
        SELECT 
            DATE(timestamp) AS date,
            COUNT(DISTINCT detection_id) AS detection_events,
            SUM(num_detections) AS total_detections,
            AVG(gas_value) AS avg_gas_value
        FROM detections
        WHERE DATE(timestamp) BETWEEN %s AND %s
        GROUP BY DATE(timestamp)
        ORDER BY date ASC
        """
        
        df = pd.read_sql(query, engine, params=(start_date, end_date))
        
        if df.empty:
            st.warning("No data available for the selected date range.")
            return
            
        # Create a figure with secondary y-axis
        fig = go.Figure()
        
        # Add traces
        fig.add_trace(go.Scatter(
            x=df['date'],
            y=df['total_detections'],
            name="Total Detections",
            line=dict(color='#00ff00', width=2)
        ))
        
        fig.add_trace(go.Scatter(
            x=df['date'],
            y=df['avg_gas_value'],
            name="Average Gas Level",
            yaxis='y2',
            line=dict(color='#ff0000', width=2)
        ))
        
        # Update layout
        fig.update_layout(
            title="Detection and Gas Level Trends",
            xaxis=dict(title="Date"),
            yaxis=dict(title="Total Detections", side='left'),
            yaxis2=dict(title="Average Gas Level", side='right', overlaying='y'),
            plot_bgcolor='#1e1e1e',
            paper_bgcolor='#1e1e1e',
            font=dict(color='white'),
            height=400
        )
        
        st.plotly_chart(fig, use_container_width=True)
        
        # Show summary statistics
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Total Detections", f"{int(df['total_detections'].sum()):,}")
        with col2:
            st.metric("Avg. Gas Level", f"{df['avg_gas_value'].mean():.1f}")
        with col3:
            st.metric("Detection Events", f"{int(df['detection_events'].sum()):,}")
            
    except Exception as e:
        st.error(f"Error in trend analysis: {e}")
        logger.error(f"Trend analysis error: {e}")

def display_category_breakdown(start_date, end_date):
    """Display waste category breakdown for the selected date range"""
    try:
        # Fetch category data
        query = """
        SELECT 
            di.class_name,
            COUNT(*) AS count,
            AVG(di.confidence) AS avg_confidence
        FROM detections d
        JOIN detected_items di ON d.detection_id = di.detection_id
        WHERE DATE(d.timestamp) BETWEEN %s AND %s
        GROUP BY di.class_name
        ORDER BY count DESC
        """
        
        df = pd.read_sql(query, engine, params=(start_date, end_date))
        
        if df.empty:
            st.warning("No category data available for the selected date range.")
            return
            
        # Create pie chart with discrete colors
        fig = px.pie(
            df,
            values='count',
            names='class_name',
            title="Waste Category Distribution",
            color='avg_confidence',
            color_discrete_sequence=px.colors.sequential.Viridis
        )
        
        fig.update_layout(
            plot_bgcolor='#1e1e1e',
            paper_bgcolor='#1e1e1e',
            font=dict(color='white'),
            height=400
        )
        
        st.plotly_chart(fig, use_container_width=True)
        
        # Show detailed breakdown
        st.markdown("### Detailed Breakdown")
        df['avg_confidence'] = df['avg_confidence'].round(2)
        st.dataframe(df, use_container_width=True)
        
    except Exception as e:
        st.error(f"Error in category breakdown: {e}")
        logger.error(f"Category breakdown error: {e}")

def display_device_performance(start_date, end_date):
    """Display device performance metrics for the selected date range"""
    try:
        # Fetch device performance data
        query = """
        SELECT 
            d.device_id,
            COUNT(DISTINCT d.detection_id) AS detection_events,
            SUM(d.num_detections) AS total_detections,
            AVG(d.gas_value) AS avg_gas_value,
            COUNT(DISTINCT DATE(d.timestamp)) AS active_days
        FROM detections d
        WHERE DATE(d.timestamp) BETWEEN %s AND %s
        GROUP BY d.device_id
        ORDER BY total_detections DESC
        """
        
        df = pd.read_sql(query, engine, params=(start_date, end_date))
        
        if df.empty:
            st.warning("No device performance data available for the selected date range.")
            return
            
        # Create performance metrics
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Total Devices", len(df))
        with col2:
            st.metric("Total Detections", f"{int(df['total_detections'].sum()):,}")
        with col3:
            st.metric("Avg. Active Days", f"{df['active_days'].mean():.1f}")
        
        # Create device performance chart
        fig = px.bar(
            df,
            x='device_id',
            y=['total_detections', 'detection_events'],
            title="Device Performance Comparison",
            barmode='group'
        )
        
        fig.update_layout(
            plot_bgcolor='#1e1e1e',
            paper_bgcolor='#1e1e1e',
            font=dict(color='white'),
            height=400
        )
        
        st.plotly_chart(fig, use_container_width=True)
        
        # Show detailed device metrics
        st.markdown("### Device Metrics")
        st.dataframe(df, use_container_width=True)
        
    except Exception as e:
        st.error(f"Error in device performance analysis: {e}")
        logger.error(f"Device performance error: {e}")

def display_environmental_impact(start_date, end_date):
    """Display environmental impact analysis for the selected date range"""
    try:
        # Fetch environmental impact data
        query = """
        SELECT 
            DATE(d.timestamp) AS date,
            COUNT(DISTINCT d.detection_id) AS detection_events,
            SUM(d.num_detections) AS total_detections,
            AVG(d.gas_value) AS avg_gas_value,
            COUNT(DISTINCT d.device_id) AS active_devices
        FROM detections d
        WHERE DATE(d.timestamp) BETWEEN %s AND %s
        GROUP BY DATE(d.timestamp)
        ORDER BY date ASC
        """
        
        df = pd.read_sql(query, engine, params=(start_date, end_date))
        
        if df.empty:
            st.warning("No environmental impact data available for the selected date range.")
            return
            
        # Calculate environmental metrics
        total_detections = df['total_detections'].sum()
        avg_gas_level = df['avg_gas_value'].mean()
        max_gas_level = df['avg_gas_value'].max()
        
        # Display key metrics
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Total Items Detected", f"{int(total_detections):,}")
        with col2:
            st.metric("Average Gas Level", f"{avg_gas_level:.1f}")
        with col3:
            st.metric("Peak Gas Level", f"{max_gas_level:.1f}")
        
        # Create environmental impact chart
        fig = go.Figure()
        
        fig.add_trace(go.Scatter(
            x=df['date'],
            y=df['total_detections'],
            name="Daily Detections",
            line=dict(color='#00ff00', width=2)
        ))
        
        fig.add_trace(go.Scatter(
            x=df['date'],
            y=df['avg_gas_value'],
            name="Gas Level",
            yaxis='y2',
            line=dict(color='#ff0000', width=2)
        ))
        
        fig.update_layout(
            title="Environmental Impact Trends",
            xaxis=dict(title="Date"),
            yaxis=dict(title="Daily Detections", side='left'),
            yaxis2=dict(title="Gas Level", side='right', overlaying='y'),
            plot_bgcolor='#1e1e1e',
            paper_bgcolor='#1e1e1e',
            font=dict(color='white'),
            height=400
        )
        
        st.plotly_chart(fig, use_container_width=True)
        
        # Show daily breakdown
        st.markdown("### Daily Environmental Impact")
        st.dataframe(df, use_container_width=True)
        
    except Exception as e:
        st.error(f"Error in environmental impact analysis: {e}")
        logger.error(f"Environmental impact error: {e}")

