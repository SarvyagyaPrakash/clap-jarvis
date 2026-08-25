#!/usr/bin/env bash
# Start clap-jarvis background service

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PLIST="${HOME}/Library/LaunchAgents/com.user.clapjarvis.plist"
HUD_BIN="${SCRIPT_DIR}/hud_notifier"

if [ ! -f "${PLIST}" ]; then
    echo "LaunchAgent plist not found. Running install.sh..."
    "${SCRIPT_DIR}/install.sh"
else
    echo "Starting clap-jarvis background daemon..."
    launchctl load "${PLIST}" 2>/dev/null || true
    if [ -f "${HUD_BIN}" ]; then
        "${HUD_BIN}" "JARVIS 🟢" "Microphone listener ON" "on" &
    fi
    osascript -e 'display notification "Microphone listener ON" with title "JARVIS 🟢" sound name "Glass"' 2>/dev/null || true
    echo "✅ clap-jarvis is now ACTIVE and running in the background."
fi
