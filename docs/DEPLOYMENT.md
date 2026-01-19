# Deployment Guide

This guide covers deploying the Sail Plan Tracker on a Raspberry Pi running OpenPlotter.

## Prerequisites

- Raspberry Pi with OpenPlotter installed
- InfluxDB 2.x running and configured
- Signal K server running (for automatic timezone)
- Python 3.11+

## Installation

### 1. Clone the Repository

```bash
cd /home/pi
git clone https://github.com/jrehm/sail-plan.git
cd sail-plan
```

### 2. Create Virtual Environment

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

Or using make:
```bash
make install
```

### 3. Configure Environment

```bash
cp .env.example .env
nano .env
```

Configure your settings:
```bash
# InfluxDB Configuration
INFLUX_URL=http://localhost:8086
INFLUX_TOKEN=your-influxdb-token-here
INFLUX_ORG=openplotter
INFLUX_BUCKET=default

# Signal K Configuration (for automatic timezone from GPS)
SIGNALK_URL=http://localhost:3000
```

**Getting your InfluxDB token:**
1. Open InfluxDB UI at `http://localhost:8086`
2. Navigate to Data > API Tokens
3. Generate or copy an existing token with read/write access to your bucket

### 4. Configure Boat

```bash
cp boat_config.toml.example boat_config.toml
nano boat_config.toml
```

Customize for your boat's sail inventory:
```toml
[boat]
name = "Your Boat Name"

[sails.main]
options = ["DOWN", "FULL", "REEF1", "REEF2"]

[sails.headsail]
options = ["JIB", "GENOA"]

[sails.downwind]
options = ["SPINNAKER"]

[display]
DOWN = "DN"
# ... short names for UI buttons
```

### 5. Test the Application

```bash
make run
# Or: streamlit run sail_plan_app.py
```

Access at `http://localhost:8501`

## Running as a Service

### Create systemd Service

Create `/etc/systemd/system/sail-plan.service`:

```ini
[Unit]
Description=Sail Plan Tracker
After=network.target influxdb.service signalk.service

[Service]
Type=simple
User=pi
WorkingDirectory=/home/pi/sail-plan
EnvironmentFile=/home/pi/sail-plan/.env
ExecStart=/home/pi/sail-plan/venv/bin/streamlit run sail_plan_app.py --server.address 0.0.0.0 --server.port 8501 --server.headless true
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

### Enable and Start

```bash
sudo systemctl daemon-reload
sudo systemctl enable sail-plan
sudo systemctl start sail-plan
```

### Verify

```bash
sudo systemctl status sail-plan
```

Access from crew phones/tablets at: `http://<pi-ip-address>:8501`

## Automatic GitHub Sync

Set up automatic updates from GitHub so changes pushed to the repository are automatically deployed.

### 1. Create Sync Script

Create `/home/pi/sail-plan/scripts/sync.sh`:

```bash
#!/bin/bash
cd /home/pi/sail-plan
git fetch origin main
LOCAL=$(git rev-parse HEAD)
REMOTE=$(git rev-parse origin/main)

if [ "$LOCAL" != "$REMOTE" ]; then
    echo "$(date): Pulling updates..."
    git pull origin main
    # Reinstall dependencies if requirements changed
    source venv/bin/activate
    pip install -q -r requirements.txt
    # Restart the service
    sudo systemctl restart sail-plan
    echo "$(date): Service restarted"
else
    echo "$(date): Already up to date"
fi
```

Make executable:
```bash
mkdir -p /home/pi/sail-plan/scripts
chmod +x /home/pi/sail-plan/scripts/sync.sh
```

### 2. Create systemd Timer

Create `/etc/systemd/system/sail-plan-sync.timer`:

```ini
[Unit]
Description=Sync sail-plan from GitHub

[Timer]
OnBootSec=2min
OnUnitActiveSec=5min
Persistent=true

[Install]
WantedBy=timers.target
```

### 3. Create systemd Service for Sync

Create `/etc/systemd/system/sail-plan-sync.service`:

```ini
[Unit]
Description=Sync sail-plan from GitHub

[Service]
Type=oneshot
User=pi
ExecStart=/home/pi/sail-plan/scripts/sync.sh
```

### 4. Allow Passwordless Restart

Add to `/etc/sudoers.d/sail-plan`:
```
pi ALL=(ALL) NOPASSWD: /bin/systemctl restart sail-plan
```

### 5. Enable the Timer

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now sail-plan-sync.timer
```

### Verify Sync

```bash
systemctl status sail-plan-sync.timer
journalctl -u sail-plan-sync -f
```

## Troubleshooting

### App Won't Start

```bash
journalctl -u sail-plan -f
```

Common issues:
- Missing `.env` file or invalid token
- InfluxDB not running
- Port 8501 already in use

### Timezone Shows UTC

The app falls back to UTC when it can't determine position. Check:
1. Signal K is running: `systemctl status signalk`
2. GPS has a fix: Check Signal K dashboard
3. Signal K URL is correct in `.env`

### Sync Not Working

```bash
journalctl -u sail-plan-sync -f
```

Common issues:
- Git authentication (ensure SSH keys or credentials configured)
- Network connectivity
- Script not executable

### InfluxDB Errors

1. Verify token is valid in InfluxDB UI
2. Check bucket name matches `.env`
3. Ensure token has write permissions

## Network Access

The app listens on all interfaces (`0.0.0.0`) by default when run as a service. Crew can access it at:

```
http://<raspberry-pi-ip>:8501
```

Find your Pi's IP:
```bash
hostname -I
```

## File Structure

```
/home/pi/sail-plan/
├── .env                       # Environment config (gitignored)
├── .env.example               # Environment template
├── boat_config.toml           # Boat-specific config (sail inventory)
├── boat_config.toml.example   # Boat config template
├── sail_plan_app.py           # Main application
├── requirements.txt           # Python dependencies
├── venv/                      # Python virtual environment
└── scripts/
    └── sync.sh                # GitHub sync script
```
