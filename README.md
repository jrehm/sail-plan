# Morticia Sail Plan Tracker

Streamlit web app for logging sail configurations on the SeaCart 30 trimaran "Morticia".
Data stored in InfluxDB for integration with OpenPlotter/Signal K/Grafana stack.

## Features

- Touch-friendly interface optimized for phones and tablets
- Real-time sail configuration logging to InfluxDB
- Automatic loading of last known sail state on startup
- Mutual exclusivity logic for headsails and downwind sails
- Staysail mode support (Jib + Reaching Spi combo)
- Optional backdating for missed entries
- Comment field for notes
- Recent history view

## Sail Inventory

- **Main**: Full, Reef 1-4, Down
- **Headsails**: Jib, J1, Storm Jib (mutually exclusive)
- **Downwind**: Biggee (Code 0), Reaching Spi, Whomper (mutually exclusive)
- **Special**: Jib can be used as staysail with Reaching Spi

## Installation (Raspberry Pi)

```bash
# Using a virtual environment (recommended)
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Or install system-wide
pip install -r requirements.txt --break-system-packages

# Or using make
make install
```

## Configuration

Copy the example environment file and configure your InfluxDB settings:

```bash
cp .env.example .env
```

Edit `.env` with your actual values:

```bash
INFLUX_URL=http://localhost:8086
INFLUX_TOKEN=your-influxdb-token-here
INFLUX_ORG=openplotter
INFLUX_BUCKET=default
```

## Running

```bash
# Basic (using make)
make run

# Or using streamlit directly
streamlit run sail_plan_app.py

# Accessible from other devices on boat network
make run-network
# Or: streamlit run sail_plan_app.py --server.address 0.0.0.0 --server.port 8501

# With auto-reload disabled (slightly faster)
streamlit run sail_plan_app.py --server.address 0.0.0.0 --server.runOnSave false
```

## Development

```bash
# Install dev dependencies (ruff, mypy)
make install-dev

# Run linter
make lint

# Format code
make format

# Type checking
make typecheck

# See all available commands
make help
```

Access from crew phones/tablets at: `http://<pi-ip-address>:8501`

## Run at Startup (systemd)

Create `/etc/systemd/system/sail-plan.service`:

```ini
[Unit]
Description=Morticia Sail Plan Tracker
After=network.target influxdb.service

[Service]
Type=simple
User=pi
WorkingDirectory=/home/pi/sail_plan
EnvironmentFile=/home/pi/sail_plan/.env
ExecStart=/home/pi/sail_plan/venv/bin/streamlit run sail_plan_app.py --server.address 0.0.0.0 --server.port 8501 --server.headless true
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Enable:
```bash
sudo systemctl daemon-reload
sudo systemctl enable sail-plan
sudo systemctl start sail-plan
```

## InfluxDB Schema

**Measurement**: `sail_config`

| Field | Type | Description |
|-------|------|-------------|
| main | string | DOWN, FULL, R1, R2, R3, R4 |
| headsail | string | JIB, J1, STORM, or empty |
| downwind | string | BIGGEE, REACHING_SPI, WHOMPER, or empty |
| staysail_mode | boolean | True if jib used as staysail |
| comment | string | Optional notes |

**Tags**: `vessel: "morticia"`

## Querying Data in Grafana

Example Flux query to show sail changes over time:

```flux
from(bucket: "Default")
  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
  |> filter(fn: (r) => r["_measurement"] == "sail_config")
  |> filter(fn: (r) => r["vessel"] == "morticia")
  |> pivot(rowKey:["_time"], columnKey: ["_field"], valueColumn: "_value")
```
