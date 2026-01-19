# Sail Plan Tracker

[![Version](https://img.shields.io/badge/version-0.9.1-blue.svg)](CHANGELOG.md)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.11+-blue.svg)](https://python.org)
[![Streamlit](https://img.shields.io/badge/streamlit-1.28+-red.svg)](https://streamlit.io)

A touch-friendly web app for logging sail configurations. Designed for use on a Raspberry Pi with OpenPlotter/Signal K/InfluxDB/Grafana. Boat-specific sail inventory is fully configurable via TOML.

## Table of Contents

- [Features](#features)
- [Quick Start](#quick-start)
- [Usage](#usage)
- [Sail Inventory](#sail-inventory)
- [Documentation](#documentation)
- [Development](#development)
- [License](#license)

## Features

- **Touch-optimized UI** - Large buttons designed for phones and tablets
- **Real-time logging** - Sail changes stored instantly in InfluxDB
- **Automatic timezone** - Detects local time from Signal K GPS position
- **Multi-user safe** - Fresh state on every load, pending changes indicator
- **Backdating** - Log missed entries with correct timestamps
- **History & delete** - View recent changes, correct mistakes
- **Offline-friendly** - Works on boat's local network

## Quick Start

```bash
# Clone and install
git clone https://github.com/jrehm/sail-plan.git
cd sail-plan
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with your InfluxDB token

# Configure boat (customize sail inventory for your boat)
cp boat_config.toml.example boat_config.toml
# Edit boat_config.toml with your boat name and sails

# Run
streamlit run sail_plan_app.py
```

Access at `http://localhost:8501` or from other devices at `http://<pi-ip>:8501`

## Usage

1. **Select sails** - Tap the pill buttons to set current sail configuration
2. **Add notes** - Use the NOTE button for conditions or comments
3. **Save** - Tap UPDATE to log the change
4. **Backdate** - Check "Backdate entry" to log a past change
5. **History** - Open sidebar to view/delete recent entries

### Multi-User Workflow

Multiple crew can use the app simultaneously:
- Each load fetches current state from the database
- Yellow "Unsaved changes" banner shows pending edits
- Changes from other users appear on your next interaction

## Boat Configuration

Sail inventory is configured in `boat_config.toml`. Copy the example file and customize for your boat:

```toml
[boat]
name = "My Boat"

[sails.main]
options = ["DOWN", "FULL", "REEF1", "REEF2"]

[sails.headsail]
options = ["JIB", "GENOA", "STORM"]

[sails.downwind]
options = ["SPINNAKER", "GENNAKER"]

[display]
DOWN = "DN"
REEF1 = "R1"
# ... short display names for UI buttons
```

See `boat_config.toml.example` for a full template.

## Documentation

| Document | Description |
|----------|-------------|
| [CHANGELOG](CHANGELOG.md) | Version history and release notes |
| [Deployment Guide](docs/DEPLOYMENT.md) | Installation, systemd service, auto-sync setup |
| [Schema Reference](docs/SCHEMA.md) | InfluxDB schema, Grafana queries, Signal K integration |

## Development

```bash
# Install dev dependencies
make install-dev

# Run linter
make lint

# Format code
make format

# Type checking
make typecheck

# Run locally
make run

# Run on network (accessible from other devices)
make run-network
```

## License

[MIT](LICENSE)
