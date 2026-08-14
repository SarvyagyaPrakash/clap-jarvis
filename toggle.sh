#!/usr/bin/env bash

# Toggle clap-jarvis background daemon ON/OFF with macOS notification banner

PLIST="${HOME}/Library/LaunchAgents/com.user.clapjarvis.plist"

if launchctl list | grep -q "com.user.clapjarvis"; then
    echo "Stopping JARVIS background daemon..."
    launchctl unload "${PLIST}" 2>/dev/null || true
    osascript -e 'display notification "JARVIS has been paused." with title "JARVIS 🛑" subtitle "Microphone listener OFF"' 2>/dev/null || true
    echo "🛑 JARVIS is now OFF."
else
    echo "Starting JARVIS background daemon..."
    launchctl load "${PLIST}" 2>/dev/null || true
    osascript -e 'display notification "JARVIS is active and listening." with title "JARVIS 🟢" subtitle "Microphone listener ON"' 2>/dev/null || true
    echo "🟢 JARVIS is now ON."
fi
