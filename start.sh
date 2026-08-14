#!/usr/bin/env bash
# Start clap-jarvis background service

PLIST="${HOME}/Library/LaunchAgents/com.user.clapjarvis.plist"

if [ ! -f "${PLIST}" ]; then
    echo "LaunchAgent plist not found. Running install.sh..."
    "$(dirname "$0")/install.sh"
else
    echo "Starting clap-jarvis background daemon..."
    launchctl load "${PLIST}" 2>/dev/null || true
    echo "✅ clap-jarvis is now ACTIVE and running in the background."
fi
