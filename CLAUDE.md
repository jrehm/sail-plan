# Claude Code Context

Project context for AI-assisted development. For deployment instructions, see [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md).

## Project Summary

**Morticia Sail Plan Tracker** (v0.9.0) - Streamlit app for logging sail configurations on a SeaCart 30 trimaran. Runs on Raspberry Pi with OpenPlotter/Signal K/InfluxDB/Grafana stack.

## Architecture

```
sail_plan_app.py          # Single-file Streamlit app (~900 lines)
├── Signal K integration  # GPS position → timezone lookup
├── InfluxDB persistence  # Time-series sail config storage
├── Session state mgmt    # Multi-user consistency
└── Mobile-first UI       # Touch-optimized with st.pills, fragments
```

### Key Patterns

- **Fresh fetch on render**: `get_current_sail_config()` called every page load for multi-user consistency
- **Caching**: `@st.cache_data` with TTL on DB queries (30s config, 60s history)
- **Fragments**: `@st.fragment` for sail selector enables partial reruns
- **Pending state**: Session tracks uncommitted changes, shows yellow indicator

### Data Flow

1. Page loads → fetch committed state from InfluxDB
2. User taps pills → session state updated, `has_pending_changes = True`
3. User taps UPDATE → write to InfluxDB, clear caches, `has_pending_changes = False`
4. Other users see new state on their next interaction

## File Structure

```
sail-plan/
├── sail_plan_app.py     # Main application
├── requirements.txt     # Python deps
├── pyproject.toml       # Package config + tool settings
├── Makefile             # Dev commands
├── .env.example         # Config template
├── .env                 # Local config (gitignored)
├── docs/
│   ├── DEPLOYMENT.md    # RPi setup, systemd, auto-sync
│   └── SCHEMA.md        # InfluxDB schema, Grafana queries
├── CHANGELOG.md         # Version history
└── scripts/
    └── sync.sh          # GitHub auto-sync (created on Pi)
```

## Development Commands

```bash
make run          # Local dev server
make run-network  # Accessible on LAN
make lint         # Ruff linter
make format       # Ruff formatter
make typecheck    # Mypy
```

## Testing Checklist

When making changes, verify:

1. **Timezone**: Header shows local time (not UTC) when Signal K has GPS fix
2. **Multi-user**: Open on two devices, change on one, verify other sees update
3. **Pending indicator**: Yellow "Unsaved changes" appears when selections differ from DB
4. **Delete**: Sidebar history → trash icon → confirm → entry removed
5. **Backdate**: Check "Backdate entry" → select date/time → UPDATE → verify in history
6. **Mobile**: Test on phone - buttons large enough, no horizontal scroll

## Common Tasks

### Bump Version

1. Update `__version__` in `sail_plan_app.py`
2. Add entry to `CHANGELOG.md`
3. Commit with message: `Release vX.Y.Z`

### Add New Sail Option

1. Add to appropriate list: `MAIN_STATES`, `HEADSAILS`, or `DOWNWIND_SAILS`
2. Add display name to `SAIL_DISPLAY` dict
3. Update `docs/SCHEMA.md` if needed

### Modify UI Styling

CSS is embedded in `sail_plan_app.py` around line 330. Key classes:
- `.compact-header` - Title bar
- `.state-banner` - Current config display
- `.section-label` - MAIN/HEADSAIL/DOWNWIND headers
- `[data-testid="stPills"]` - Sail selection buttons

## Environment

- **Python**: 3.11+
- **Key deps**: streamlit, influxdb-client, timezonefinder, requests, python-dotenv
- **Services**: InfluxDB (port 8086), Signal K (port 3000), Streamlit (port 8501)

## Known Considerations

- **Timezone caching**: 10-minute TTL - won't update mid-race if crossing timezone
- **History limit**: Shows last 50 entries from past 7 days
- **Pills deselection**: `st.pills` doesn't support clicking selected item to deselect - user must select different option
