"""
Morticia Sail Plan Tracker

A Streamlit web application for logging sail configurations on the SeaCart 30
trimaran "Morticia". Provides a touch-friendly interface optimized for phones
and tablets, with data persistence to InfluxDB for integration with
OpenPlotter/Signal K/Grafana monitoring stacks.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import TYPE_CHECKING

import streamlit as st
from dotenv import load_dotenv
from influxdb_client import InfluxDBClient, Point, WritePrecision
from influxdb_client.client.write_api import SYNCHRONOUS

if TYPE_CHECKING:
    from influxdb_client import InfluxDBClient as InfluxDBClientType

# Load environment variables from .env file if present
load_dotenv()

# InfluxDB Configuration (from environment variables)
INFLUX_URL = os.getenv("INFLUX_URL", "http://localhost:8086")
INFLUX_TOKEN = os.getenv("INFLUX_TOKEN", "")
INFLUX_ORG = os.getenv("INFLUX_ORG", "openplotter")
INFLUX_BUCKET = os.getenv("INFLUX_BUCKET", "default")

# Sail definitions
MAIN_STATES = ["DOWN", "FULL", "R1", "R2", "R3", "R4"]
HEADSAILS = ["JIB", "J1", "STORM"]
DOWNWIND_SAILS = ["BIGGEE", "REACHING_SPI", "WHOMPER"]

# Display names for sails
SAIL_DISPLAY = {
    "BIGGEE": "Biggee (Code 0)",
    "REACHING_SPI": "Reaching Spi",
    "WHOMPER": "Whomper",
    "JIB": "Jib",
    "J1": "J1",
    "STORM": "Storm Jib",
}


def get_influx_client() -> InfluxDBClient:
    """Create and return a configured InfluxDB client instance."""
    return InfluxDBClient(url=INFLUX_URL, token=INFLUX_TOKEN, org=INFLUX_ORG)


def get_current_sail_config() -> dict[str, str | bool]:
    """
    Fetch the most recent sail configuration from InfluxDB.

    Returns:
        Dictionary containing main, headsail, downwind, staysail_mode, and comment.
        Returns default values if no configuration found or on error.
    """
    client = get_influx_client()
    query_api = client.query_api()
    
    query = f'''
    from(bucket: "{INFLUX_BUCKET}")
        |> range(start: -30d)
        |> filter(fn: (r) => r["_measurement"] == "sail_config")
        |> filter(fn: (r) => r["vessel"] == "morticia")
        |> pivot(rowKey:["_time"], columnKey: ["_field"], valueColumn: "_value")
        |> sort(columns: ["_time"], desc: true)
        |> limit(n: 1)
    '''
    
    try:
        tables = query_api.query(query)
        for table in tables:
            for record in table.records:
                return {
                    "main": record.values.get("main", "DOWN"),
                    "headsail": record.values.get("headsail", ""),
                    "downwind": record.values.get("downwind", ""),
                    "staysail_mode": record.values.get("staysail_mode", False),
                    "comment": record.values.get("comment", ""),
                }
    except Exception as e:
        st.error(f"Error reading from InfluxDB: {e}")
    
    client.close()
    return {"main": "DOWN", "headsail": "", "downwind": "", "staysail_mode": False, "comment": ""}


def write_sail_config(
    main: str,
    headsail: str,
    downwind: str,
    staysail_mode: bool,
    comment: str,
    timestamp: datetime | None = None,
) -> bool:
    """
    Write a sail configuration entry to InfluxDB.

    Args:
        main: Main sail state (DOWN, FULL, R1-R4).
        headsail: Headsail selection (JIB, J1, STORM, or empty).
        downwind: Downwind sail selection (BIGGEE, REACHING_SPI, WHOMPER, or empty).
        staysail_mode: Whether jib is being used as staysail with Reaching Spi.
        comment: Optional note about conditions or reason for change.
        timestamp: Optional backdated timestamp. Uses current UTC time if None.

    Returns:
        True if write succeeded, False otherwise.
    """
    client = get_influx_client()
    write_api = client.write_api(write_options=SYNCHRONOUS)
    
    if timestamp is None:
        timestamp = datetime.now(timezone.utc)
    
    point = (
        Point("sail_config")
        .tag("vessel", "morticia")
        .field("main", main)
        .field("headsail", headsail)
        .field("downwind", downwind)
        .field("staysail_mode", staysail_mode)
        .field("comment", comment)
        .time(timestamp, WritePrecision.S)
    )
    
    try:
        write_api.write(bucket=INFLUX_BUCKET, record=point)
        client.close()
        return True
    except Exception as e:
        st.error(f"Error writing to InfluxDB: {e}")
        client.close()
        return False


def get_recent_entries(limit: int = 10) -> list[dict]:
    """
    Fetch recent sail log entries from the past 7 days.

    Args:
        limit: Maximum number of entries to return.

    Returns:
        List of dictionaries containing time, main, headsail, downwind,
        staysail_mode, and comment for each entry.
    """
    client = get_influx_client()
    query_api = client.query_api()
    
    query = f'''
    from(bucket: "{INFLUX_BUCKET}")
        |> range(start: -7d)
        |> filter(fn: (r) => r["_measurement"] == "sail_config")
        |> filter(fn: (r) => r["vessel"] == "morticia")
        |> pivot(rowKey:["_time"], columnKey: ["_field"], valueColumn: "_value")
        |> sort(columns: ["_time"], desc: true)
        |> limit(n: {limit})
    '''
    
    entries = []
    try:
        tables = query_api.query(query)
        for table in tables:
            for record in table.records:
                entries.append({
                    "time": record.get_time(),
                    "main": record.values.get("main", ""),
                    "headsail": record.values.get("headsail", ""),
                    "downwind": record.values.get("downwind", ""),
                    "staysail_mode": record.values.get("staysail_mode", False),
                    "comment": record.values.get("comment", ""),
                })
    except Exception as e:
        st.error(f"Error reading history: {e}")
    
    client.close()
    return entries


# Page configuration
st.set_page_config(
    page_title="Morticia Sail Plan",
    page_icon="⛵",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# Custom CSS for large touch targets and responsive design
st.markdown("""
<style>
    /* Base responsive settings */
    .main .block-container {
        padding: 1rem;
        max-width: 100%;
    }
    
    /* Large touch-friendly buttons */
    .stButton > button {
        width: 100%;
        min-height: 60px;
        font-size: 1.2rem;
        font-weight: bold;
        border-radius: 12px;
        margin: 4px 0;
        touch-action: manipulation;
    }
    
    /* Active sail state - green */
    .stButton > button[data-active="true"] {
        background-color: #28a745 !important;
        color: white !important;
        border: 3px solid #1e7e34 !important;
    }
    
    /* Inactive sail state - grey */
    .stButton > button[data-active="false"] {
        background-color: #6c757d !important;
        color: white !important;
        border: 2px solid #545b62 !important;
    }
    
    /* All Down button - red/orange */
    .all-down-btn > button {
        background-color: #dc3545 !important;
        color: white !important;
        min-height: 70px;
        font-size: 1.4rem;
    }
    
    /* Update button - blue, extra large */
    .update-btn > button {
        background-color: #007bff !important;
        color: white !important;
        min-height: 80px;
        font-size: 1.5rem;
    }
    
    /* Section headers */
    .section-header {
        font-size: 1.1rem;
        font-weight: bold;
        color: #333;
        margin: 1rem 0 0.5rem 0;
        padding-bottom: 0.3rem;
        border-bottom: 2px solid #ddd;
    }
    
    /* Current time display */
    .time-display {
        font-size: 1.5rem;
        font-weight: bold;
        text-align: center;
        padding: 0.5rem;
        background-color: #f8f9fa;
        border-radius: 8px;
        margin-bottom: 1rem;
    }
    
    /* Status summary */
    .status-summary {
        font-size: 1.2rem;
        padding: 1rem;
        background-color: #e9ecef;
        border-radius: 8px;
        margin: 1rem 0;
        text-align: center;
    }
    
    /* Responsive adjustments for tablets landscape */
    @media (min-width: 768px) {
        .stButton > button {
            min-height: 70px;
            font-size: 1.3rem;
        }
    }
    
    /* Phone portrait - stack everything */
    @media (max-width: 480px) {
        .stButton > button {
            min-height: 55px;
            font-size: 1.1rem;
        }
        .main .block-container {
            padding: 0.5rem;
        }
    }
</style>
""", unsafe_allow_html=True)

# Initialize session state
if "initialized" not in st.session_state:
    current_config = get_current_sail_config()
    st.session_state.main = current_config["main"]
    st.session_state.headsail = current_config["headsail"]
    st.session_state.downwind = current_config["downwind"]
    st.session_state.staysail_mode = current_config["staysail_mode"]
    st.session_state.initialized = True

# Header with current time
st.markdown("# ⛵ MORTICIA")
current_time = datetime.now(timezone.utc).strftime("%H:%M:%S UTC")
st.markdown(f'<div class="time-display">{current_time}</div>', unsafe_allow_html=True)

# ALL DOWN button
st.markdown('<div class="all-down-btn">', unsafe_allow_html=True)
if st.button("⚓ ALL DOWN", key="all_down", use_container_width=True):
    st.session_state.main = "DOWN"
    st.session_state.headsail = ""
    st.session_state.downwind = ""
    st.session_state.staysail_mode = False
    st.rerun()
st.markdown('</div>', unsafe_allow_html=True)

st.markdown("---")

# MAIN SAIL section
st.markdown('<div class="section-header">MAIN</div>', unsafe_allow_html=True)

main_cols = st.columns(5)
main_options = ["FULL", "R1", "R2", "R3", "R4"]
for i, option in enumerate(main_options):
    with main_cols[i]:
        is_active = st.session_state.main == option
        btn_label = f"{'✓ ' if is_active else ''}{option}"
        if st.button(btn_label, key=f"main_{option}", use_container_width=True,
                     type="primary" if is_active else "secondary"):
            st.session_state.main = option
            st.rerun()

# Main DOWN button (full width)
is_down = st.session_state.main == "DOWN"
down_label = f"{'✓ ' if is_down else ''}⬇ DOWN"
if st.button(down_label, key="main_down", use_container_width=True,
             type="primary" if is_down else "secondary"):
    st.session_state.main = "DOWN"
    st.rerun()

st.markdown("---")

# HEADSAIL section
st.markdown('<div class="section-header">HEADSAIL</div>', unsafe_allow_html=True)

head_cols = st.columns(3)
for i, sail in enumerate(HEADSAILS):
    with head_cols[i]:
        is_active = st.session_state.headsail == sail
        btn_label = f"{'✓ ' if is_active else ''}{SAIL_DISPLAY.get(sail, sail)}"
        if st.button(btn_label, key=f"head_{sail}", use_container_width=True,
                     type="primary" if is_active else "secondary"):
            if is_active:
                # Deselect if already selected
                st.session_state.headsail = ""
                st.session_state.staysail_mode = False
            else:
                # Select this headsail (mutual exclusivity)
                st.session_state.headsail = sail
                # Clear staysail mode unless it's JIB with Reaching Spi
                if sail != "JIB" or st.session_state.downwind != "REACHING_SPI":
                    st.session_state.staysail_mode = False
            st.rerun()

# Staysail mode checkbox (only enabled when JIB + REACHING_SPI)
can_staysail = (st.session_state.headsail == "JIB" and 
                st.session_state.downwind == "REACHING_SPI")

if can_staysail:
    staysail = st.checkbox("☑ Jib as Staysail with Reaching Spi", 
                           value=st.session_state.staysail_mode,
                           key="staysail_check")
    if staysail != st.session_state.staysail_mode:
        st.session_state.staysail_mode = staysail
        st.rerun()
else:
    st.markdown('<p style="color: #999; font-size: 0.9rem;">Staysail mode: Select Jib + Reaching Spi</p>', 
                unsafe_allow_html=True)
    if st.session_state.staysail_mode:
        st.session_state.staysail_mode = False

st.markdown("---")

# DOWNWIND section
st.markdown('<div class="section-header">DOWNWIND</div>', unsafe_allow_html=True)

for sail in DOWNWIND_SAILS:
    is_active = st.session_state.downwind == sail
    btn_label = f"{'✓ ' if is_active else ''}{SAIL_DISPLAY.get(sail, sail)}"
    if st.button(btn_label, key=f"down_{sail}", use_container_width=True,
                 type="primary" if is_active else "secondary"):
        if is_active:
            # Deselect if already selected
            st.session_state.downwind = ""
            st.session_state.staysail_mode = False
        else:
            # Select this downwind sail (mutual exclusivity)
            st.session_state.downwind = sail
            # Clear headsail unless it's JIB with Reaching Spi (staysail mode)
            if sail != "REACHING_SPI":
                st.session_state.headsail = ""
                st.session_state.staysail_mode = False
            elif st.session_state.headsail not in ["JIB", ""]:
                st.session_state.headsail = ""
        st.rerun()

st.markdown("---")

# Current configuration summary
st.markdown('<div class="section-header">CURRENT CONFIG</div>', unsafe_allow_html=True)

config_parts = []
if st.session_state.main != "DOWN":
    config_parts.append(f"Main: {st.session_state.main}")
else:
    config_parts.append("Main: DOWN")

if st.session_state.headsail:
    sail_name = SAIL_DISPLAY.get(st.session_state.headsail, st.session_state.headsail)
    if st.session_state.staysail_mode:
        sail_name += " (staysail)"
    config_parts.append(sail_name)

if st.session_state.downwind:
    config_parts.append(SAIL_DISPLAY.get(st.session_state.downwind, st.session_state.downwind))

if not st.session_state.headsail and not st.session_state.downwind and st.session_state.main == "DOWN":
    config_summary = "⚓ All sails down"
else:
    config_summary = " + ".join(config_parts)

st.markdown(f'<div class="status-summary">{config_summary}</div>', unsafe_allow_html=True)

st.markdown("---")

# Optional fields
st.markdown('<div class="section-header">LOG ENTRY OPTIONS</div>', unsafe_allow_html=True)

# Backdate option
use_backdate = st.checkbox("📅 Backdate this entry", key="use_backdate")
entry_time = None
if use_backdate:
    col1, col2 = st.columns(2)
    with col1:
        entry_date = st.date_input("Date", value=datetime.now().date(), key="entry_date")
    with col2:
        entry_time_input = st.time_input("Time (UTC)", value=datetime.now().time(), key="entry_time")
    entry_time = datetime.combine(entry_date, entry_time_input).replace(tzinfo=timezone.utc)

# Comment field
comment = st.text_area("💬 Comment (optional)", height=80, key="comment",
                       placeholder="Sail change notes, conditions, etc...")

st.markdown("---")

# UPDATE button
st.markdown('<div class="update-btn">', unsafe_allow_html=True)
if st.button("💾 UPDATE SAIL PLAN", key="update", use_container_width=True):
    success = write_sail_config(
        main=st.session_state.main,
        headsail=st.session_state.headsail,
        downwind=st.session_state.downwind,
        staysail_mode=st.session_state.staysail_mode,
        comment=comment,
        timestamp=entry_time
    )
    if success:
        st.success("✅ Sail plan updated!")
        st.balloons()
    else:
        st.error("❌ Failed to update sail plan")
st.markdown('</div>', unsafe_allow_html=True)

# Recent history (collapsible)
with st.expander("📜 Recent Sail Changes"):
    entries = get_recent_entries(10)
    if entries:
        for entry in entries:
            time_str = entry["time"].strftime("%m/%d %H:%M UTC")
            parts = []
            if entry["main"]:
                parts.append(f"Main:{entry['main']}")
            if entry["headsail"]:
                h = SAIL_DISPLAY.get(entry["headsail"], entry["headsail"])
                if entry["staysail_mode"]:
                    h += "(S)"
                parts.append(h)
            if entry["downwind"]:
                parts.append(SAIL_DISPLAY.get(entry["downwind"], entry["downwind"]))
            
            config = " + ".join(parts) if parts else "All down"
            comment_str = f' - "{entry["comment"]}"' if entry["comment"] else ""
            
            st.markdown(f"**{time_str}**: {config}{comment_str}")
    else:
        st.markdown("*No recent entries*")
