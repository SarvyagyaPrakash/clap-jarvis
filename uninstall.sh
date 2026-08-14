#!/usr/bin/env bash

# clap-jarvis uninstallation script for macOS LaunchAgent

DEST_PLIST="${HOME}/Library/LaunchAgents/com.user.clapjarvis.plist"

echo "==============================================="
echo "       Uninstalling clap-jarvis LaunchAgent    "
echo "==============================================="

if launchctl list | grep -q "com.user.clapjarvis"; then
    echo "Unloading LaunchAgent via launchctl..."
    launchctl unload "${DEST_PLIST}" 2>/dev/null || true
else
    echo "LaunchAgent is not currently loaded."
fi

if [ -f "${DEST_PLIST}" ]; then
    echo "Removing plist file from '${DEST_PLIST}'..."
    rm -f "${DEST_PLIST}"
    echo "Plist removed."
else
    echo "No plist file found at '${DEST_PLIST}'."
fi

echo "==============================================="
echo "     clap-jarvis uninstalled successfully.     "
echo "==============================================="
