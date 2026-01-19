"""
Morticia Sail Plan Tracker

A Streamlit web application for logging sail configurations on the SeaCart 30
trimaran "Morticia". Provides a touch-friendly interface optimized for phones
and tablets, with data persistence to InfluxDB for integration with
OpenPlotter/Signal K/Grafana monitoring stacks.
"""

from __future__ import annotations

__version__ = "0.9.1"

import os
import sys
import tomllib
from datetime import datetime, time as dt_time, timedelta, timezone
from pathlib import Path
from typing import TYPE_CHECKING
from zoneinfo import ZoneInfo

import requests
import streamlit as st
from dotenv import load_dotenv
from influxdb_client import InfluxDBClient, Point, WritePrecision
from influxdb_client.client.write_api import SYNCHRONOUS
from timezonefinder import TimezoneFinder

if TYPE_CHECKING:
    from influxdb_client import InfluxDBClient as InfluxDBClientType

# Load environment variables from .env file if present
load_dotenv()

# InfluxDB Configuration (from environment variables)
INFLUX_URL = os.getenv("INFLUX_URL", "http://localhost:8086")
INFLUX_TOKEN = os.getenv("INFLUX_TOKEN", "")
INFLUX_ORG = os.getenv("INFLUX_ORG", "openplotter")
INFLUX_BUCKET = os.getenv("INFLUX_BUCKET", "default")

# Signal K Configuration (for automatic timezone from GPS)
SIGNALK_URL = os.getenv("SIGNALK_URL", "http://localhost:3000")

# Timezone finder instance (reused for performance)
_tz_finder = TimezoneFinder()


def get_boat_position() -> tuple[float, float] | None:
    """
    Fetch the boat's current GPS position from Signal K.

    Returns:
        Tuple of (latitude, longitude) or None if unavailable.
    """
    try:
        response = requests.get(
            f"{SIGNALK_URL}/signalk/v1/api/vessels/self/navigation/position",
            timeout=2,
        )
        if response.status_code == 200:
            data = response.json()
            lat = data.get("value", {}).get("latitude")
            lon = data.get("value", {}).get("longitude")
            if lat is not None and lon is not None:
                return (lat, lon)
    except requests.RequestException:
        pass
    return None


def get_boat_timezone() -> ZoneInfo:
    """
    Get the timezone for the boat's current position.

    Fetches GPS position from Signal K and converts to timezone.
    Falls back to UTC if position unavailable or lookup fails.

    Returns:
        ZoneInfo object for the boat's timezone.
    """
    # Check cache in session state (refresh every 10 minutes)
    cache_key = "tz_cache"
    cache_time_key = "tz_cache_time"
    now = datetime.now(timezone.utc)

    if cache_key in st.session_state and cache_time_key in st.session_state:
        cache_age = (now - st.session_state[cache_time_key]).total_seconds()
        if cache_age < 600:  # 10 minutes
            return st.session_state[cache_key]

    # Fetch position and lookup timezone
    position = get_boat_position()
    if position:
        tz_name = _tz_finder.timezone_at(lat=position[0], lng=position[1])
        if tz_name:
            tz = ZoneInfo(tz_name)
            st.session_state[cache_key] = tz
            st.session_state[cache_time_key] = now
            return tz

    # Fall back to UTC
    return ZoneInfo("UTC")


def format_local_time(dt: datetime, tz: ZoneInfo) -> str:
    """
    Format a datetime in the given timezone (HH:MM only for compact display).

    Args:
        dt: Datetime to format (should be timezone-aware).
        tz: Target timezone.

    Returns:
        Formatted time string like "14:32".
    """
    local_dt = dt.astimezone(tz)
    return local_dt.strftime("%H:%M")


def format_local_datetime(dt: datetime, tz: ZoneInfo) -> str:
    """
    Format a datetime with date in the given timezone.

    Args:
        dt: Datetime to format (should be timezone-aware).
        tz: Target timezone.

    Returns:
        Formatted string like "01/15 14:32 CDT".
    """
    local_dt = dt.astimezone(tz)
    tz_abbrev = local_dt.strftime("%Z")
    return local_dt.strftime(f"%m/%d %H:%M {tz_abbrev}")


# Boat configuration from TOML file
def load_boat_config() -> dict:
    """
    Load boat-specific configuration from TOML file.

    Looks for boat_config.toml in the same directory as the app.
    Falls back to boat_config.toml.example if not found.
    Exits with error if neither file exists.
    """
    app_dir = Path(__file__).parent
    config_path = app_dir / "boat_config.toml"
    example_path = app_dir / "boat_config.toml.example"

    if config_path.exists():
        with open(config_path, "rb") as f:
            return tomllib.load(f)
    elif example_path.exists():
        with open(example_path, "rb") as f:
            return tomllib.load(f)
    else:
        sys.exit("Error: boat_config.toml not found. Copy boat_config.toml.example to boat_config.toml and customize.")


_boat_config = load_boat_config()

# Sail definitions (loaded from boat_config.toml)
BOAT_NAME = _boat_config.get("boat", {}).get("name", "Boat")
MAIN_STATES = _boat_config.get("sails", {}).get("main", {}).get("options", [])
HEADSAILS = _boat_config.get("sails", {}).get("headsail", {}).get("options", [])
DOWNWIND_SAILS = _boat_config.get("sails", {}).get("downwind", {}).get("options", [])

# Display names for sails (short versions for buttons)
SAIL_DISPLAY = _boat_config.get("display", {})


def get_influx_client() -> InfluxDBClient:
    """Create and return a configured InfluxDB client instance."""
    return InfluxDBClient(url=INFLUX_URL, token=INFLUX_TOKEN, org=INFLUX_ORG)


@st.cache_data(ttl=30)
def get_current_sail_config() -> dict[str, str | bool]:
    """
    Fetch the most recent sail configuration from InfluxDB.
    Cached for 30 seconds to reduce database queries.

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
                client.close()
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


@st.cache_data(ttl=30)
def get_recent_entries(limit: int = 10) -> list[dict]:
    """
    Fetch recent sail log entries from the past 7 days.
    Cached for 60 seconds to reduce database queries.

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


def delete_sail_entry(timestamp: datetime) -> bool:
    """
    Delete a sail configuration entry from InfluxDB.

    Args:
        timestamp: The exact timestamp of the entry to delete.

    Returns:
        True if delete succeeded, False otherwise.
    """
    client = get_influx_client()
    delete_api = client.delete_api()

    # Delete requires a time range - use 1 second window around the exact timestamp
    start = timestamp - timedelta(milliseconds=500)
    stop = timestamp + timedelta(milliseconds=500)

    try:
        delete_api.delete(
            start=start,
            stop=stop,
            predicate='_measurement="sail_config" AND vessel="morticia"',
            bucket=INFLUX_BUCKET,
            org=INFLUX_ORG,
        )
        client.close()
        return True
    except Exception as e:
        st.error(f"Error deleting entry: {e}")
        client.close()
        return False


# Page configuration
st.set_page_config(
    page_title=f"{BOAT_NAME} Sail Plan",
    page_icon="⛵",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# Compact mobile-first CSS
st.markdown("""
<style>
    /* Hide Streamlit chrome but keep sidebar toggle */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    /* Keep header visible for sidebar hamburger menu */
    header[data-testid="stHeader"] {
        background: transparent !important;
        height: auto !important;
    }

    /* Compact container with bottom padding for iOS dock */
    .main .block-container {
        padding: 0.5rem 0.5rem 5rem 0.5rem;
        max-width: 100%;
    }

    /* Remove default streamlit spacing */
    .stVerticalBlock > div {
        gap: 0.25rem;
    }

    /* Prevent horizontal scroll on entire page */
    .main, .main .block-container, [data-testid="stAppViewContainer"] {
        max-width: 100vw !important;
        overflow-x: hidden !important;
    }

    /* Style pills for touch-friendly mobile use */
    [data-testid="stPills"] {
        gap: 15px !important;
    }
    [data-testid="stPills"] button {
        min-height: 102px !important;
        padding: 1.2rem 2.1rem !important;
        font-size: 2.6rem !important;
        font-weight: bold !important;
        border-radius: 18px !important;
        touch-action: manipulation;
    }
    /* Pills container should wrap on mobile */
    [data-testid="stPills"] > div {
        flex-wrap: wrap !important;
        justify-content: center !important;
        gap: 15px !important;
    }

    /* Bottom bar columns - keep side by side */
    [data-testid="stHorizontalBlock"] {
        flex-wrap: nowrap !important;
        gap: 8px !important;
    }
    [data-testid="column"] {
        min-width: 0 !important;
    }

    /* Sticky header container - positioned below Streamlit header */
    .sticky-header {
        position: sticky;
        top: 0;
        z-index: 99;
        background: transparent;
        padding: 0.25rem 0;
        margin-bottom: 0.25rem;
    }

    /* Compact header */
    .compact-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding: 0.4rem 0.75rem;
        background: #1a1a2e;
        color: white;
        border-radius: 10px;
        margin-bottom: 0.4rem;
    }
    .compact-header .title {
        font-size: 1.4rem;
        font-weight: bold;
    }
    .compact-header .time {
        font-size: 1.2rem;
        color: #ccc;
    }

    /* Current state banner */
    .state-banner {
        font-size: 1.3rem;
        font-weight: bold;
        text-align: center;
        padding: 0.6rem;
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        border-radius: 10px;
        margin-bottom: 0.4rem;
    }

    /* Section labels */
    .section-label {
        font-size: 1.65rem;
        font-weight: bold;
        color: #666;
        margin: 0.7rem 0 0.35rem 0;
        text-transform: uppercase;
        letter-spacing: 0.05em;
    }

    /* Touch-friendly buttons */
    .stButton > button {
        width: 100%;
        min-height: 56px;
        font-size: 1.2rem;
        font-weight: bold;
        border-radius: 10px;
        touch-action: manipulation;
    }

    /* Primary button (UPDATE) - green */
    .stButton > button[kind="primary"] {
        background-color: #28a745 !important;
        color: white !important;
        border: 2px solid #1e7e34 !important;
    }

    /* Popover trigger button styling */
    .stPopover > div > button {
        min-height: 52px !important;
        font-size: 1.1rem !important;
        font-weight: bold !important;
        border-radius: 10px !important;
    }

    /* Checkboxes - compact */
    .stCheckbox {
        padding: 0 !important;
    }
    .stCheckbox label {
        font-size: 0.85rem !important;
    }

    /* Date/time inputs - compact */
    .stDateInput, .stTimeInput {
        margin-bottom: 0.25rem !important;
    }
    .stDateInput input, .stTimeInput input {
        padding: 0.4rem !important;
        font-size: 0.95rem !important;
    }

    /* Pending changes indicator */
    .pending-indicator {
        background-color: #fff3cd;
        color: #856404;
        padding: 0.2rem 0.5rem;
        border-radius: 4px;
        font-size: 0.8rem;
        text-align: center;
    }

    /* Sidebar styling - compact history with scroll */
    [data-testid="stSidebar"] > div:first-child {
        overflow-y: auto !important;
        max-height: 100vh !important;
    }
    .sidebar .sidebar-content {
        padding: 0.5rem;
    }
    [data-testid="stSidebar"] [data-testid="stHorizontalBlock"] {
        gap: 2px !important;
        flex-wrap: nowrap !important;
        align-items: center !important;
        margin-bottom: 0.15rem;
    }
    [data-testid="stSidebar"] [data-testid="column"] {
        padding: 0 !important;
    }
    [data-testid="stSidebar"] .stButton > button {
        min-height: 28px !important;
        min-width: 28px !important;
        padding: 0.1rem 0.4rem !important;
        font-size: 0.85rem !important;
    }
    [data-testid="stSidebar"] small {
        line-height: 1.2;
        display: block;
    }
    /* History row styling */
    .history-row {
        padding: 4px 6px;
        border-radius: 4px;
    }

    /* Popover styling - position higher for mobile keyboard */
    .stPopover {
        width: 100%;
    }
    .stPopover > div > button {
        width: 100%;
    }
    [data-testid="stPopover"] > div > div {
        top: 10vh !important;
        bottom: auto !important;
        max-height: 40vh !important;
    }
    [data-testid="stPopover"] textarea {
        font-size: 16px !important; /* Prevents iOS zoom on focus */
    }

    /* Ensure border-box sizing */
    *, *::before, *::after {
        box-sizing: border-box;
    }

    /* Mobile optimizations - keep things readable */
    @media (max-width: 500px) {
        .main .block-container {
            padding: 0.4rem 0.4rem 5rem 0.4rem;
        }
        .state-banner {
            font-size: 1.15rem;
            padding: 0.5rem;
        }
        .compact-header .title {
            font-size: 1.25rem;
        }
        .compact-header .time {
            font-size: 1.1rem;
        }
        .section-label {
            font-size: 1.5rem;
            margin: 0.6rem 0 0.3rem 0;
        }
        /* Pills stay readable on mobile */
        [data-testid="stPills"] button {
            min-height: 93px !important;
            padding: 1rem 1.6rem !important;
            font-size: 2.4rem !important;
        }
    }

    /* Dark mode adjustments */
    @media (prefers-color-scheme: dark) {
        .pending-indicator {
            background-color: #5c4d00;
            color: #ffd700;
        }
        .history-row {
            color: #e0e0e0 !important;
        }
        .history-row small, .history-row b, .history-row i {
            color: #e0e0e0 !important;
        }
    }

    /* Streamlit dark theme detection */
    [data-testid="stAppViewContainer"][data-theme="dark"] .pending-indicator,
    .stApp[data-theme="dark"] .pending-indicator {
        background-color: #5c4d00;
        color: #ffd700;
    }
    [data-testid="stSidebar"][data-theme="dark"] .history-row,
    [data-testid="stSidebar"] .history-row small,
    [data-testid="stSidebar"] .history-row b {
        color: inherit !important;
    }
</style>
""", unsafe_allow_html=True)

# Get timezone
boat_tz = get_boat_timezone()
current_time = format_local_time(datetime.now(timezone.utc), boat_tz)

# Always fetch current committed state from InfluxDB (ensures multi-user consistency)
committed_config = get_current_sail_config()

# Initialize or sync session state with committed state
if "has_pending_changes" not in st.session_state:
    st.session_state.has_pending_changes = False

if "pending_comment" not in st.session_state:
    st.session_state.pending_comment = ""

if not st.session_state.has_pending_changes:
    # Sync UI state with database
    st.session_state.main = committed_config["main"]
    st.session_state.headsail = committed_config["headsail"]
    st.session_state.downwind = committed_config["downwind"]
    st.session_state.staysail_mode = committed_config["staysail_mode"]
    # Clear comment - notes are per-entry, not carried forward
    st.session_state.pending_comment = ""


def has_changes() -> bool:
    """Check if current selections differ from committed state."""
    return (
        st.session_state.main != committed_config["main"]
        or st.session_state.headsail != committed_config["headsail"]
        or st.session_state.downwind != committed_config["downwind"]
        or st.session_state.staysail_mode != committed_config["staysail_mode"]
    )


def mark_pending():
    """Mark that user has made uncommitted changes."""
    st.session_state.has_pending_changes = True


def clear_pending():
    """Clear pending changes flag after successful save."""
    st.session_state.has_pending_changes = False
    st.session_state.pending_comment = ""


def format_config_summary(main: str, headsail: str, downwind: str, staysail_mode: bool) -> str:
    """Format sail configuration as a readable summary string."""
    parts = []

    # Main sail
    if main == "DOWN":
        parts.append("Main: DOWN")
    else:
        parts.append(f"Main: {main}")

    # Headsail
    if headsail:
        sail_name = SAIL_DISPLAY.get(headsail, headsail)
        if staysail_mode:
            sail_name += " (S)"
        parts.append(sail_name)

    # Downwind
    if downwind:
        parts.append(SAIL_DISPLAY.get(downwind, downwind))

    if not headsail and not downwind and main == "DOWN":
        return "All sails down"

    return " + ".join(parts)


# ============ SIDEBAR (History) ============
with st.sidebar:
    st.markdown("### History")

    if "pending_delete" not in st.session_state:
        st.session_state.pending_delete = None

    entries = get_recent_entries(50)
    if entries:
        for i, entry in enumerate(entries):
            time_str = format_local_datetime(entry["time"], boat_tz)
            parts = []
            if entry["main"]:
                parts.append(f"M:{entry['main']}")
            if entry["headsail"]:
                h = SAIL_DISPLAY.get(entry["headsail"], entry["headsail"])
                if entry["staysail_mode"]:
                    h += "(S)"
                parts.append(h)
            if entry["downwind"]:
                parts.append(SAIL_DISPLAY.get(entry["downwind"], entry["downwind"]))

            config = " + ".join(parts) if parts else "All down"
            entry_key = entry["time"].isoformat()
            is_pending = st.session_state.pending_delete == entry_key

            # Alternate row shading (semi-transparent for dark mode compatibility)
            bg_color = "rgba(128,128,128,0.3)" if i % 2 == 0 else "rgba(128,128,128,0.1)"

            if is_pending:
                # Compact confirmation row
                st.markdown(f'<div style="background:{bg_color};padding:4px;border-radius:4px;">', unsafe_allow_html=True)
                cols = st.columns([3, 1, 1])
                with cols[0]:
                    st.markdown("<small>Delete?</small>", unsafe_allow_html=True)
                with cols[1]:
                    if st.button("✓", key=f"confirm_{i}", help="Confirm delete"):
                        if delete_sail_entry(entry["time"]):
                            st.session_state.pending_delete = None
                            get_recent_entries.clear()
                            get_current_sail_config.clear()
                            st.rerun()
                with cols[2]:
                    if st.button("✗", key=f"cancel_{i}", help="Cancel"):
                        st.session_state.pending_delete = None
                        st.rerun()
                st.markdown("</div>", unsafe_allow_html=True)
            else:
                # Compact entry row with inline delete
                comment_text = f' <i>"{entry["comment"]}"</i>' if entry["comment"] else ""
                cols = st.columns([5, 1])
                with cols[0]:
                    st.markdown(
                        f'<div class="history-row" style="background:{bg_color};">'
                        f'<small><b>{time_str}</b><br/>{config}{comment_text}</small>'
                        f'</div>',
                        unsafe_allow_html=True
                    )
                with cols[1]:
                    if st.button("🗑", key=f"delete_{i}", help="Delete entry"):
                        st.session_state.pending_delete = entry_key
                        st.rerun()
    else:
        st.markdown("*No recent entries*")


# ============ MAIN CONTENT ============

# Build pending indicator HTML if needed
pending_html = ""
if has_changes():
    pending_html = '<div class="pending-indicator">Unsaved changes</div>'

# Current state summary
config_summary = format_config_summary(
    st.session_state.main,
    st.session_state.headsail,
    st.session_state.downwind,
    st.session_state.staysail_mode,
)

# Sticky header containing: title/time and pending indicator
st.markdown(f'''
<div class="sticky-header">
    <div class="compact-header">
        <span class="title">{BOAT_NAME.upper()}</span>
        <span class="time" id="header-clock">{current_time}</span>
    </div>
    {pending_html}
</div>
<script>
    function updateClock() {{
        const now = new Date();
        const hours = String(now.getHours()).padStart(2, '0');
        const minutes = String(now.getMinutes()).padStart(2, '0');
        const clockEl = document.getElementById('header-clock');
        if (clockEl) clockEl.textContent = hours + ':' + minutes;
    }}
    updateClock();
    setInterval(updateClock, 30000);
</script>
''', unsafe_allow_html=True)

# State banner and UPDATE button side by side
col_status, col_update = st.columns([2, 1])
with col_status:
    st.markdown(f'<div class="state-banner">{config_summary}</div>', unsafe_allow_html=True)
with col_update:
    update_clicked = st.button("UPDATE", key="update", use_container_width=True, type="primary")

# ============ SAIL SELECTION (Fragment for fast updates) ============
@st.fragment
def sail_selector():
    """Fragment for sail selection - enables partial reruns for faster response."""
    # Main sail
    st.markdown('<div class="section-label">MAIN</div>', unsafe_allow_html=True)
    main_options = {opt: SAIL_DISPLAY.get(opt, opt) for opt in MAIN_STATES}
    main_selection = st.pills(
        "Main sail",
        options=list(main_options.keys()),
        format_func=lambda x: main_options[x],
        default=st.session_state.main,
        key="main_pills",
        label_visibility="collapsed",
    )
    if main_selection and main_selection != st.session_state.main:
        st.session_state.main = main_selection
        mark_pending()

    # Headsail
    st.markdown('<div class="section-label">HEADSAIL</div>', unsafe_allow_html=True)
    headsail_options = {sail: SAIL_DISPLAY.get(sail, sail) for sail in HEADSAILS}
    headsail_selection = st.pills(
        "Headsail",
        options=list(headsail_options.keys()),
        format_func=lambda x: headsail_options[x],
        default=st.session_state.headsail if st.session_state.headsail else None,
        key="headsail_pills",
        label_visibility="collapsed",
    )
    new_headsail = headsail_selection if headsail_selection else ""
    if new_headsail != st.session_state.headsail:
        st.session_state.headsail = new_headsail
        if new_headsail != "JIB" or st.session_state.downwind != "REACHING_SPI":
            st.session_state.staysail_mode = False
        mark_pending()

    # Downwind
    st.markdown('<div class="section-label">DOWNWIND</div>', unsafe_allow_html=True)
    downwind_options = {sail: SAIL_DISPLAY.get(sail, sail) for sail in DOWNWIND_SAILS}
    downwind_selection = st.pills(
        "Downwind",
        options=list(downwind_options.keys()),
        format_func=lambda x: downwind_options[x],
        default=st.session_state.downwind if st.session_state.downwind else None,
        key="downwind_pills",
        label_visibility="collapsed",
    )
    new_downwind = downwind_selection if downwind_selection else ""
    if new_downwind != st.session_state.downwind:
        st.session_state.downwind = new_downwind
        if new_downwind != "REACHING_SPI":
            st.session_state.headsail = ""
            st.session_state.staysail_mode = False
        elif st.session_state.headsail not in ["JIB", ""]:
            st.session_state.headsail = ""
        mark_pending()

    # Staysail toggle
    if st.session_state.headsail == "JIB" and st.session_state.downwind == "REACHING_SPI":
        staysail = st.checkbox(
            "Jib as Staysail",
            value=st.session_state.staysail_mode,
            key="staysail_check"
        )
        if staysail != st.session_state.staysail_mode:
            st.session_state.staysail_mode = staysail
            mark_pending()

# Render the sail selector fragment
sail_selector()

# ============ BOTTOM ACTION BAR ============

# Comment popover
has_comment = bool(st.session_state.pending_comment)
popover_label = "NOTE ✓" if has_comment else "NOTE"
with st.popover(popover_label, use_container_width=True):
    comment = st.text_area(
        "Add a note",
        key="pending_comment",
        height=60,
        placeholder="Conditions, reason for change...",
        label_visibility="collapsed"
    )

# Backdate toggle (collapsible)
use_backdate = st.checkbox("Backdate entry", key="use_backdate")
if use_backdate:
    local_now = datetime.now(timezone.utc).astimezone(boat_tz)
    tz_abbrev = local_now.strftime("%Z")
    entry_date = st.date_input("Date", value=local_now.date(), key="entry_date", label_visibility="collapsed")
    # Hour and minute dropdowns on separate lines (5-min granularity)
    current_hour = local_now.hour
    current_min = (local_now.minute // 5) * 5  # Round to nearest 5
    hours = list(range(24))
    minutes = list(range(0, 60, 5))
    sel_hour = st.selectbox("Hour", hours, index=current_hour, key="entry_hour", format_func=lambda x: f"{x:02d}h")
    sel_min = st.selectbox("Minute", minutes, index=minutes.index(current_min), key="entry_min", format_func=lambda x: f"{x:02d}m")
    entry_time = dt_time(sel_hour, sel_min)
    local_dt = datetime.combine(entry_date, entry_time).replace(tzinfo=boat_tz)
    st.session_state.backdate_time = local_dt.astimezone(timezone.utc)
else:
    st.session_state.backdate_time = None

# Handle UPDATE button click (button is at top of page)
if update_clicked:
    # Get backdate time if set
    timestamp = st.session_state.get("backdate_time")

    success = write_sail_config(
        main=st.session_state.main,
        headsail=st.session_state.headsail,
        downwind=st.session_state.downwind,
        staysail_mode=st.session_state.staysail_mode,
        comment=st.session_state.pending_comment,
        timestamp=timestamp
    )
    if success:
        clear_pending()
        # Clear caches so new data appears
        get_current_sail_config.clear()
        get_recent_entries.clear()
        st.toast("Saved!", icon="✅")
        st.rerun()
    else:
        st.error("Failed to save")

# Version footer
st.markdown(
    f'<div style="text-align:center;color:#999;font-size:0.75rem;margin-top:1rem;">v{__version__}</div>',
    unsafe_allow_html=True
)
