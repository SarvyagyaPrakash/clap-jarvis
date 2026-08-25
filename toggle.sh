#!/usr/bin/env bash

# Toggle clap-jarvis background daemon ON/OFF with macOS notification banner

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PLIST="${HOME}/Library/LaunchAgents/com.user.clapjarvis.plist"
HUD_BIN="${SCRIPT_DIR}/hud_notifier"

# Ensure HUD binary is compiled
if [ ! -f "${HUD_BIN}" ] && [ -f "${SCRIPT_DIR}/hud_notifier.swift" ]; then
    swiftc -O "${SCRIPT_DIR}/hud_notifier.swift" -o "${HUD_BIN}" 2>/dev/null || true
fi

notify() {
    local title="$1"
    local subtitle="$2"
    local state="$3"

    afplay /System/Library/Sounds/Glass.aiff 2>/dev/null &

    # 1. Native Floating Screen HUD (or fallback to Notification Center banner if HUD binary unavailable)
    if [ -f "${HUD_BIN}" ]; then
        "${HUD_BIN}" "${title}" "${subtitle}" "${state}" &
    else
        osascript -e "display notification \"${subtitle}\" with title \"${title}\"" 2>/dev/null || true
    fi
}

if launchctl list | grep -q "com.user.clapjarvis"; then
    echo "Stopping JARVIS background daemon..."
    launchctl unload "${PLIST}" 2>/dev/null || true
    notify "JARVIS 🛑" "Microphone listener OFF" "off"
    echo "🛑 JARVIS is now OFF."
else
    echo "Starting JARVIS background daemon..."
    launchctl load "${PLIST}" 2>/dev/null || true
    notify "JARVIS 🟢" "Microphone listener ON" "on"
    echo "🟢 JARVIS is now ON."
fi
