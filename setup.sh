#!/bin/bash
# Setup script for Earth Law Tracker

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PLIST_NAME="com.earthlaw.tracker"
PLIST_PATH="$HOME/Library/LaunchAgents/${PLIST_NAME}.plist"
PYTHON_PATH="$(which python3)"

echo "=== Earth Law Tracker Setup ==="
echo ""

# Install Python dependencies
echo "Installing Python dependencies..."
pip3 install -r "$SCRIPT_DIR/requirements.txt"
echo ""

# Create logs directory
mkdir -p "$SCRIPT_DIR/logs"

# Create launchd plist for every-other-day scheduling
# launchd doesn't natively support "every other day", so we run daily at 8am
# and the script itself can track when it last ran (or we just accept daily).
# For simplicity, we schedule it daily — the deduplication in the script
# means running daily just catches more articles without duplicates.
echo "Setting up automatic scheduling..."

cat > "$PLIST_PATH" << EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>${PLIST_NAME}</string>
    <key>ProgramArguments</key>
    <array>
        <string>${PYTHON_PATH}</string>
        <string>${SCRIPT_DIR}/fetch_articles.py</string>
    </array>
    <key>StartCalendarInterval</key>
    <dict>
        <key>Hour</key>
        <integer>8</integer>
        <key>Minute</key>
        <integer>0</integer>
    </dict>
    <key>StandardOutPath</key>
    <string>${SCRIPT_DIR}/logs/fetch.log</string>
    <key>StandardErrorPath</key>
    <string>${SCRIPT_DIR}/logs/fetch_error.log</string>
    <key>WorkingDirectory</key>
    <string>${SCRIPT_DIR}</string>
</dict>
</plist>
EOF

# Load the schedule (unload first if already loaded)
launchctl unload "$PLIST_PATH" 2>/dev/null || true
launchctl load "$PLIST_PATH"

echo ""
echo "=== Setup Complete! ==="
echo ""
echo "What was set up:"
echo "  - Python dependencies installed"
echo "  - Automatic daily fetch scheduled for 8:00 AM"
echo "    (Articles are deduplicated so daily runs just catch more)"
echo ""
echo "To get started:"
echo "  1. Fetch articles now:  python3 $SCRIPT_DIR/fetch_articles.py"
echo "  2. View in browser:     python3 $SCRIPT_DIR/app.py"
echo "     Then open http://localhost:5001"
echo ""
echo "To stop automatic fetching:"
echo "  launchctl unload $PLIST_PATH"
echo ""
