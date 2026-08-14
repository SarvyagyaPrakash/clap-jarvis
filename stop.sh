#!/usr/bin/env bash
# Stop clap-jarvis background service

PLIST="${HOME}/Library/LaunchAgents/com.user.clapjarvis.plist"

echo "Stopping clap-jarvis background daemon..."
launchctl unload "${PLIST}" 2>/dev/null || true
echo "🛑 clap-jarvis is now OFF / PAUSED."
