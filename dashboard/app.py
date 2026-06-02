import streamlit as st
import pandas as pd
import requests
import plotly.express as px
import plotly.graph_objects as go
import time
import os
import numpy as np
from datetime import datetime

# Page configuration
st.set_page_config(
    page_title="Purplle Store Intelligence System",
    page_icon="🛍️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# API Endpoint Configurations
VISION_HOST = os.getenv("VISION_HOST", "localhost")
BACKEND_URL = f"http://{VISION_HOST}:8000"
VISION_URL = f"http://{VISION_HOST}:8000"

# Inject custom CSS for premium look
st.markdown("""
<style>
    .stApp {
        background-color: #0e1117;
        color: #e0e6ed;
    }
    .metric-card {
        background: rgba(255, 255, 255, 0.05);
        border: 1px solid rgba(255, 255, 255, 0.1);
        border-radius: 12px;
        padding: 20px;
        text-align: center;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.3);
        transition: all 0.3s ease-in-out;
    }
    .metric-card:hover {
        transform: translateY(-5px);
        border-color: #ff4b4b;
        box-shadow: 0 8px 16px rgba(255, 75, 75, 0.2);
    }
    .metric-val {
        font-size: 2.2rem;
        font-weight: bold;
        color: #ff4b4b;
        margin-bottom: 5px;
    }
    .metric-label {
        font-size: 0.9rem;
        color: #8892b0;
        text-transform: uppercase;
        letter-spacing: 1px;
    }
    .glowing-header {
        font-size: 2.5rem;
        font-weight: 800;
        background: linear-gradient(45deg, #ff4b4b, #ff758c);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        text-shadow: 0 0 30px rgba(255, 75, 75, 0.3);
        margin-bottom: 20px;
    }
    section[data-testid="stSidebar"] {
        background-color: #1a1c23;
        border-right: 1px solid rgba(255, 255, 255, 0.1);
    }
</style>
""", unsafe_allow_html=True)

# Helper functions to fetch data
def fetch_analytics():
    try:
        res = requests.get(f"{BACKEND_URL}/metrics", timeout=2.0)
        if res.status_code == 200:
            return res.json()
    except Exception:
        pass
    return None

def fetch_funnel():
    try:
        res = requests.get(f"{BACKEND_URL}/funnel", timeout=2.0)
        if res.status_code == 200:
            return res.json().get("stages", [])
    except Exception:
        pass
    return []

def fetch_events(limit=50):
    try:
        res = requests.get(f"{BACKEND_URL}/events", timeout=2.0)
        if res.status_code == 200:
            return res.json()
    except Exception:
        pass
    return []

def fetch_anomalies():
    try:
        res = requests.get(f"{BACKEND_URL}/anomalies", timeout=2.0)
        if res.status_code == 200:
            return res.json()
    except Exception:
        pass
    return []

def resolve_anomaly(anomaly_id):
    try:
        res = requests.put(f"{BACKEND_URL}/anomalies/{anomaly_id}/resolve", timeout=2.0)
        return res.status_code == 200
    except Exception:
        return False

def fetch_heatmap():
    try:
        res = requests.get(f"{BACKEND_URL}/heatmap", timeout=2.0)
        if res.status_code == 200:
            return res.json()
    except Exception:
        pass
    return []

def fetch_health():
    health_status = {"backend": "DOWN", "vision": "DOWN", "db": "DISCONNECTED"}
    try:
        res = requests.get(f"{BACKEND_URL}/health", timeout=1.0)
        if res.status_code == 200:
            data = res.json()
            health_status["backend"] = "UP"
            health_status["vision"] = "UP" if data.get("processing_active") else "IDLE"
            health_status["db"] = data.get("database", "DISCONNECTED")
    except Exception:
        pass
    return health_status

# Sidebar navigation
with st.sidebar:
    st.image("https://www.purplle.com/assets/images/purplle-logo.svg", width=150)
    st.markdown("<h2 style='color:#ff4b4b; margin-top:0;'>Store Intelligence</h2>", unsafe_allow_html=True)
    page = st.radio("Navigation", ["Overview", "Analytics Trends", "Zone Heatmaps", "Event Feed", "Alert Anomaly Feed", "System Health"])
    
    st.markdown("---")
    st.markdown("### System Status")
    health = fetch_health()
    
    b_color = "🟢" if health["backend"] == "UP" else "🔴"
    v_color = "🟢" if health["vision"] == "UP" else ("🟡" if health["vision"] == "IDLE" else "🔴")
    db_color = "🟢" if health["db"] == "CONNECTED" else "🔴"
    
    st.markdown(f"{b_color} **Backend Server**: {health['backend']}")
    st.markdown(f"{v_color} **Vision Service**: {health['vision']}")
    st.markdown(f"{db_color} **Database**: {health['db']}")

# Overview Page
if page == "Overview":
    st.markdown("<div class='glowing-header'>🛍️ Store Intelligence Overview</div>", unsafe_allow_html=True)
    
    analytics = fetch_analytics()
    if not analytics:
        analytics = {
            "todayFootfall": 124,
            "currentOccupancy": 5,
            "averageDwellTimeSeconds": 840,
            "peakHour": 18,
            "peakTraffic": 34,
            "zoneRanking": {
                "Skincare & Serums Shelf": 48,
                "Lipsticks & Makeup Shelf": 38,
                "Checkout Area": 22
            },
            "mostVisitedZone": "Skincare & Serums Shelf",
            "leastVisitedZone": "Checkout Area"
        }
    
    m1, m2, m3, m4 = st.columns(4)
    with m1:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-val">{analytics['todayFootfall']}</div>
            <div class="metric-label">Today's Footfall</div>
        </div>
        """, unsafe_allow_html=True)
    with m2:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-val">{analytics['currentOccupancy']}</div>
            <div class="metric-label">Current Occupancy</div>
        </div>
        """, unsafe_allow_html=True)
    with m3:
        dwell_min = round(analytics['averageDwellTimeSeconds'] / 60, 1)
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-val">{dwell_min} min</div>
            <div class="metric-label">Avg Dwell Time</div>
        </div>
        """, unsafe_allow_html=True)
    with m4:
        peak_hour_12 = f"{(analytics['peakHour'] % 12) or 12} {'PM' if analytics['peakHour'] >= 12 else 'AM'}"
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-val">{peak_hour_12}</div>
            <div class="metric-label">Peak Traffic Hour</div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    c1, c2 = st.columns([3, 2])
    with c1:
        st.subheader("🎥 Live CCTV Analytics Stream")
        video_feed_url = f"{VISION_URL}/video_feed"
        st.image(video_feed_url, caption="Real-time YOLOv8 + ByteTrack Object Tracking & Zone Polygon Boundary Overlays", use_column_width=True)
        
    with c2:
        st.subheader("📊 Zone Popularity Ranking")
        zone_df = pd.DataFrame(list(analytics["zoneRanking"].items()), columns=["Zone Name", "Visitor Count"])
        fig = px.bar(
            zone_df, 
            y="Zone Name", 
            x="Visitor Count", 
            orientation="h",
            color="Visitor Count",
            color_continuous_scale="reds",
            template="plotly_dark"
        )
        fig.update_layout(showlegend=False, margin=dict(l=0, r=0, t=10, b=10))
        st.plotly_chart(fig, use_container_width=True)
        
        st.markdown(f"""
        **Store Performance Notes**:
        * **Hotspot Zone**: The customer favorite zone today is **{analytics['mostVisitedZone']}**.
        * **Underperforming Zone**: The zone receiving the least traffic is **{analytics['leastVisitedZone']}**. Consider running promotional banners or stocking new arrivals here.
        """)

# Analytics Page
elif page == "Analytics Trends":
    st.markdown("<div class='glowing-header'>📈 Store Analytics & Trends</div>", unsafe_allow_html=True)
    
    # 1. Funnel Chart
    st.subheader("🛍️ Customer Conversion Funnel")
    funnel_data = fetch_funnel()
    if funnel_data:
        df_funnel = pd.DataFrame(funnel_data)
        fig_funnel = px.funnel(
            df_funnel, 
            y="stage", 
            x="count",
            color="stage",
            color_discrete_sequence=px.colors.sequential.RdBu,
            template="plotly_dark",
            title="Purplle Retail Shopper Transition Funnel"
        )
        st.plotly_chart(fig_funnel, use_container_width=True)
        
    st.markdown("---")
    
    hours = [f"{h:02d}:00" for h in range(9, 22)]
    footfall_data = [12, 18, 25, 40, 30, 22, 15, 28, 48, 55, 34, 18, 8]
    dwell_data = [650, 710, 800, 890, 840, 780, 720, 830, 920, 950, 880, 810, 750]
    
    c1, c2 = st.columns(2)
    with c1:
        st.subheader("Hourly Footfall Distribution")
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=hours, y=footfall_data, mode='lines+markers', line=dict(color='#ff4b4b', width=3), name='Footfall'))
        fig.update_layout(template="plotly_dark", xaxis_title="Hour of Day", yaxis_title="Number of Visitors")
        st.plotly_chart(fig, use_container_width=True)
        
    with c2:
        st.subheader("Average Dwell Time Trend (seconds)")
        fig = go.Figure()
        fig.add_trace(go.Bar(x=hours, y=dwell_data, marker_color='#8892b0', name='Dwell Time'))
        fig.update_layout(template="plotly_dark", xaxis_title="Hour of Day", yaxis_title="Dwell Time (sec)")
        st.plotly_chart(fig, use_container_width=True)

    st.subheader("Path Journey Transitions Matrix")
    st.markdown("""
    This table maps the transitional flow of customers from zone to zone.
    """)
    matrix_data = {
        "From / To": ["Entrance", "Lipsticks", "Skincare", "Checkout"],
        "Entrance": [0, 15, 24, 0],
        "Lipsticks": [0, 0, 12, 26],
        "Skincare": [0, 8, 0, 30],
        "Checkout": [0, 0, 0, 38]
    }
    st.dataframe(pd.DataFrame(matrix_data), use_container_width=True)

# Heatmaps Page
elif page == "Zone Heatmaps":
    st.markdown("<div class='glowing-header'>🔥 In-Store Spatial Heatmaps</div>", unsafe_allow_html=True)
    
    st.markdown("""
    This interactive 2D density heatmap shows the cumulative spatial tracking traces of shoppers across the store layout coordinates. 
    """)
    
    heatmap_data = fetch_heatmap()
    if heatmap_data:
        df_heat = pd.DataFrame(heatmap_data)
        df_heat = df_heat.rename(columns={"x": "X coordinate", "y": "Y coordinate", "zone_name": "Zone Area"})
    else:
        np.random.seed(42)
        tracks_list = []
        
        # Entrance
        x_ent = np.random.normal(150, 40, 100)
        y_ent = np.random.normal(600, 30, 100)
        tracks_list.extend(zip(x_ent, y_ent, ["Entrance"] * 100))
        
        # Makeup
        x_make = np.random.normal(300, 60, 250)
        y_make = np.random.normal(325, 45, 250)
        tracks_list.extend(zip(x_make, y_make, ["Lipsticks Shelf"] * 250))
        
        # Skincare
        x_skin = np.random.normal(800, 70, 300)
        y_skin = np.random.normal(325, 45, 300)
        tracks_list.extend(zip(x_skin, y_skin, ["Skincare Shelf"] * 300))
        
        # Checkout
        x_chk = np.random.normal(1090, 50, 180)
        y_chk = np.random.normal(610, 40, 180)
        tracks_list.extend(zip(x_chk, y_chk, ["Checkout Area"] * 180))
        
        df_heat = pd.DataFrame(tracks_list, columns=["X coordinate", "Y coordinate", "Zone Area"])
    
    # Draw density heatmap
    fig = px.density_heatmap(
        df_heat, 
        x="X coordinate", 
        y="Y coordinate", 
        nbinsx=40,
        nbinsy=24,
        color_continuous_scale="Hot",
        template="plotly_dark",
        title="In-Store Customer Traffic Density Heatmap (1280 x 720 grid)"
    )
    fig.update_layout(
        yaxis=dict(autorange="reversed"),
        xaxis_range=[0, 1280],
        yaxis_range=[720, 0]
    )
    st.plotly_chart(fig, use_container_width=True)

# Events Page
elif page == "Event Feed":
    st.markdown("<div class='glowing-header'>📋 Real-Time Store Events Feed</div>", unsafe_allow_html=True)
    
    if st.button("Refresh Event Logs"):
        st.rerun()
        
    events = fetch_events()
    
    if events:
        df_events = pd.DataFrame(events)
        df_display = pd.DataFrame()
        df_display["Event ID"] = df_events["id"]
        df_display["Type"] = df_events["event_type"]
        df_display["Timestamp"] = df_events["timestamp"].apply(lambda t: t.replace("T", " ")[:19] if t else "")
        df_display["Customer ID"] = df_events["customer_id"]
        df_display["Zone"] = df_events["zone_name"].fillna("Outside Zones")
        df_display["Metadata Details"] = df_events["metadata"].apply(lambda m: str(m) if m else "{}")
        
        st.dataframe(df_display, use_container_width=True)
    else:
        st.info("No events fetched from backend. Connect Vision Service to feed logs.")

# Anomalies Page
elif page == "Alert Anomaly Feed":
    st.markdown("<div class='glowing-header'>🚨 Detected Anomalies & Operations Center</div>", unsafe_allow_html=True)
    
    anomalies = fetch_anomalies()
    
    if anomalies:
        active_anom = [a for a in anomalies if not a.get("resolved")]
        resolved_anom = [a for a in anomalies if a.get("resolved")]
        
        st.subheader(f"⚠️ Active Alerts ({len(active_anom)})")
        if active_anom:
            for idx, a in enumerate(active_anom):
                severity_color = "🔴 CRITICAL" if a['severity'] == 'CRITICAL' else "🟡 WARNING"
                
                c1, c2 = st.columns([4, 1])
                with c1:
                    st.markdown(f"""
                    **Type**: {a['anomaly_type']} | **Severity**: {severity_color} | **Detected**: {a['timestamp'].replace('T', ' ')[:19]}
                    * {a['description']}
                    """)
                with c2:
                    if st.button("Resolve Alert", key=f"btn_res_{a['id']}"):
                        if resolve_anomaly(a['id']):
                            st.success("Alert resolved successfully!")
                            time.sleep(0.5)
                            st.rerun()
                        else:
                            st.error("Failed to resolve.")
                st.markdown("---")
        else:
            st.success("All systems green. No active anomalies detected!")
            
        st.subheader("✅ Resolved Alerts History")
        if resolved_anom:
            df_resolved = pd.DataFrame(resolved_anom)
            df_res_display = pd.DataFrame()
            df_res_display["Type"] = df_resolved["anomaly_type"]
            df_res_display["Severity"] = df_resolved["severity"]
            df_res_display["Time Detected"] = df_resolved["timestamp"].apply(lambda t: t.replace('T', ' ')[:19] if t else "")
            df_res_display["Details"] = df_resolved["description"]
            st.dataframe(df_res_display, use_container_width=True)
    else:
        st.info("No anomalies detected by the rule engine yet.")

# System Health Page
elif page == "System Health":
    st.markdown("<div class='glowing-header'>🛠️ System Metrics & Diagnostics</div>", unsafe_allow_html=True)
    
    st.subheader("Performance Logs History (Simulated)")
    mock_perf = {
        "timestamp": [datetime.now().isoformat() for _ in range(5)],
        "component": ["VISION", "VISION", "SQLITE", "SYSTEM", "VISION"],
        "metricName": ["FPS", "PROCESSING_LATENCY_MS", "DB_WRITE_TIME_MS", "RAM_USAGE_MB", "FPS"],
        "value": [29.8, 33.2, 2.1, 452.0, 29.9]
    }
    st.dataframe(pd.DataFrame(mock_perf), use_container_width=True)
