# Claude Code Handoff: Sail Plan Tracker - RPi Deployment

## Project Overview

**Morticia Sail Plan Tracker** is a Streamlit web app for logging sail configurations on a SeaCart 30 trimaran. It runs on a Raspberry Pi as part of an OpenPlotter/Signal K/Grafana stack.

**Repository**: https://github.com/jrehm/sail-plan

## Current State

The app is feature-complete and ready for deployment. Recent additions:

- **Automatic timezone** from Signal K GPS position (no UTC mental math)
- **Multi-user consistency** - fetches fresh state from InfluxDB on every render
- **Pending changes indicator** - yellow banner when user has unsaved changes
- **Delete functionality** - remove entries from history to correct mistakes
- **Environment-based config** - credentials in `.env` file, not code

## Task: Set Up Automated GitHub Sync

Create a systemd-based auto-sync mechanism that:

1. Periodically pulls latest code from GitHub (every 5 minutes)
2. Detects if code actually changed
3. Restarts the sail-plan service only when needed
4. Logs activity for debugging

### Recommended Implementation

**1. Create sync script** at `/home/pi/sail_plan/scripts/sync.sh`:
```bash
#!/bin/bash
cd /home/pi/sail_plan
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

**2. Create systemd timer** at `/etc/systemd/system/sail-plan-sync.timer`:
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

**3. Create systemd service** at `/etc/systemd/system/sail-plan-sync.service`:
```ini
[Unit]
Description=Sync sail-plan from GitHub

[Service]
Type=oneshot
User=pi
ExecStart=/home/pi/sail_plan/scripts/sync.sh
```

**4. Allow passwordless restart** - add to `/etc/sudoers.d/sail-plan`:
```
pi ALL=(ALL) NOPASSWD: /bin/systemctl restart sail-plan
```

**5. Enable the timer**:
```bash
sudo systemctl daemon-reload
sudo systemctl enable --now sail-plan-sync.timer
```

## Environment Details

- **Working directory**: `/home/pi/sail_plan` (adjust if different)
- **Python**: Uses venv at `/home/pi/sail_plan/venv`
- **Services**:
  - `sail-plan.service` - main Streamlit app
  - `influxdb.service` - time-series database
  - `signalk.service` - marine data server

## Configuration Files Needed

1. **`.env`** - copy from `.env.example` and configure:
   - `INFLUX_TOKEN` - get from InfluxDB admin
   - `SIGNALK_URL` - typically `http://localhost:3000`

## Verification Steps

After setup, verify:
1. `systemctl status sail-plan` - app running
2. `systemctl status sail-plan-sync.timer` - timer active
3. `journalctl -u sail-plan-sync` - sync logs
4. Access app at `http://<pi-ip>:8501`

## Testing the App

1. Open app on phone/tablet
2. Verify time shows local timezone (not UTC)
3. Change a sail selection - should see yellow "unsaved changes" banner
4. Click UPDATE - changes saved to InfluxDB
5. Open on second device - should see the update
6. Test delete: expand history, delete an entry, confirm

## Troubleshooting

- **App won't start**: Check `journalctl -u sail-plan -f`
- **Timezone shows UTC**: Verify Signal K is running and has GPS fix
- **Sync not working**: Check `journalctl -u sail-plan-sync -f`
- **InfluxDB errors**: Verify token and bucket name in `.env`

## File Structure

```
/home/pi/sail_plan/
├── .env                 # Local config (gitignored)
├── .env.example         # Config template
├── sail_plan_app.py     # Main application
├── requirements.txt     # Python dependencies
├── venv/                # Python virtual environment
└── scripts/
    └── sync.sh          # GitHub sync script (to create)
```

## Next Steps After Sync Setup

1. Test the full workflow on the boat
2. Verify timezone detection with actual GPS
3. Test with multiple crew phones simultaneously
4. Monitor for any issues during actual racing
