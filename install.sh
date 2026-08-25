#!/usr/bin/env bash
set -e

# clap-jarvis installation script for macOS LaunchAgent

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="${SCRIPT_DIR}/venv"
VENV_PYTHON="${VENV_DIR}/bin/python"
CLAP_SCRIPT="${SCRIPT_DIR}/clap_jarvis.py"
PLIST_TEMPLATE="${SCRIPT_DIR}/com.user.clapjarvis.plist"
DEST_PLIST_DIR="${HOME}/Library/LaunchAgents"
DEST_PLIST="${DEST_PLIST_DIR}/com.user.clapjarvis.plist"
LOG_DIR="${HOME}/Library/Logs"

echo "==============================================="
echo "        Installing clap-jarvis LaunchAgent      "
echo "==============================================="

# 1. Create virtualenv
if [ ! -d "${VENV_DIR}" ]; then
    echo "[1/4] Creating Python virtual environment in '${VENV_DIR}'..."
    python3 -m venv "${VENV_DIR}"
else
    echo "[1/4] Python virtual environment already exists in '${VENV_DIR}'."
fi

# 2. Install dependencies
echo "[2/4] Installing Python dependencies from requirements.txt..."
"${VENV_PYTHON}" -m pip install --upgrade pip
"${VENV_PYTHON}" -m pip install -r "${SCRIPT_DIR}/requirements.txt"

# Compile native Swift helpers (HUD overlay & MediaRemote detector)
if [ -f "${SCRIPT_DIR}/hud_notifier.swift" ]; then
    swiftc -O "${SCRIPT_DIR}/hud_notifier.swift" -o "${SCRIPT_DIR}/hud_notifier" 2>/dev/null || true
fi
if [ -f "${SCRIPT_DIR}/media_detector.swift" ]; then
    swiftc -O "${SCRIPT_DIR}/media_detector.swift" -o "${SCRIPT_DIR}/media_detector" 2>/dev/null || true
fi

# 3. Generate LaunchAgent plist file with absolute paths
echo "[3/4] Generating LaunchAgent plist definition..."
mkdir -p "${DEST_PLIST_DIR}"
mkdir -p "${LOG_DIR}"

# Unload if currently loaded
if launchctl list | grep -q "com.user.clapjarvis"; then
    echo "       Unloading existing LaunchAgent..."
    launchctl unload "${DEST_PLIST}" 2>/dev/null || true
fi

# Substitute placeholder tokens into actual plist
sed -e "s|__VENV_PYTHON__|${VENV_PYTHON}|g" \
    -e "s|__SCRIPT_PATH__|${CLAP_SCRIPT}|g" \
    -e "s|__LOG_DIR__|${LOG_DIR}|g" \
    -e "s|__PROJECT_DIR__|${SCRIPT_DIR}|g" \
    "${PLIST_TEMPLATE}" > "${DEST_PLIST}"

# 4. Load LaunchAgent
echo "[4/4] Loading LaunchAgent via launchctl..."
launchctl load "${DEST_PLIST}"

echo ""
echo "==============================================="
echo "          INSTALLATION COMPLETE! 🎉           "
echo "==============================================="
echo ""
echo "CRITICAL ACTION REQUIRED (Microphone Permission):"
echo "------------------------------------------------"
echo "macOS will NOT allow background daemons to access the microphone by default."
echo ""
echo "You MUST grant Microphone permission manually:"
echo "1. Open 'System Settings' -> 'Privacy & Security' -> 'Microphone'."
echo "2. Ensure permission is enabled for Terminal / Python binary (${VENV_PYTHON})."
echo "   (If running from iTerm2/Terminal, ensure Terminal is toggled ON)."
echo ""
echo "Useful Commands:"
echo "• Test calibration mode:  ${VENV_PYTHON} ${CLAP_SCRIPT} --calibrate"
echo "• View daemon output log: tail -f ~/Library/Logs/clap-jarvis.log"
echo "• View error log:         tail -f ~/Library/Logs/clap-jarvis.err.log"
echo "• Uninstall daemon:       ./uninstall.sh"
echo "==============================================="
