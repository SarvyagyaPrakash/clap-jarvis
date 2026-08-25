#!/usr/bin/env bash
# Stop clap-jarvis background service

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PLIST="${HOME}/Library/LaunchAgents/com.user.clapjarvis.plist"
HUD_BIN="${SCRIPT_DIR}/hud_notifier"

echo "Stopping clap-jarvis background daemon..."
launchctl unload "${PLIST}" 2>/dev/null || true
if [ -f "${HUD_BIN}" ]; then
    "${HUD_BIN}" "JARVIS 🛑" "Microphone listener OFF" "off" &
fi
osascript -e 'display notification "Microphone listener OFF" with title "JARVIS 🛑" sound name "Glass"' 2>/dev/null || true
echo "🛑 clap-jarvis is now OFF / PAUSED."
