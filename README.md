# 👏 clap-jarvis

[![macOS](https://img.shields.io/badge/Platform-macOS-black?logo=apple&logoColor=white)](https://apple.com)
[![Python 3.9+](https://img.shields.io/badge/Python-3.9%2B-blue?logo=python&logoColor=white)](https://python.org)
[![Neural TTS](https://img.shields.io/badge/TTS-Edge--Neural--TTS-orange)](https://github.com/rany2/edge-tts)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

**clap-jarvis** is your personal macOS background assistant inspired by Iron Man's JARVIS. It runs silently in the background 24/7 as a native LaunchAgent daemon.

Snap your fingers or clap twice, and JARVIS responds in an ultra-realistic British neural voice, provides dynamic contextual greetings, and tracks real-time aircraft flying overhead via FlightRadar24.

---

## ✨ Features

- 🤌 **Dual Clap & Finger-Snap Detection**: High-precision transient analysis engineered specifically for percussive claps and finger snaps with minimal ambient false-positives.
- 🎙️ **Ultra-Realistic Neural Voice**: Powered by Microsoft Edge Neural TTS (`en-GB-RyanNeural`) for a cinematic British butler experience, with offline macOS `say` fallback.
- ✈️ **Overhead Flight Tracking**: Queries real-time airspace data to detect planes within your configured radius (e.g. 150 km), calculates ETA/altitude/speed, announces origin & destination in natural language, and opens FlightRadar24 focused on the aircraft.
- 🔇 **Smart Media & Meeting Suppression**:
  - Automatically suppresses triggers when music or video is playing (Spotify, Apple Music, YouTube in Chromium/Safari browsers, VLC, QuickTime).
  - Configurable meeting detection (Zoom, Google Meet, Teams, FaceTime, Webex, Slack Huddle).
- 🖥️ **Native macOS HUD Notification**: A sleek, floating glassmorphism HUD indicator (`hud_notifier`) built in Swift that displays status overlays atop all windows and Spaces when toggled.
- ⚡ **Instant Control & Hot Reloading**: Toggle anytime with `jarvis`, a Desktop shortcut, or shell scripts. Updates to greetings in `phrases.json` take effect instantly without restarting.

---

## 🎯 How to Use It Day-to-Day

### 1. Triggering JARVIS
Perform **2 snaps** or **2 claps** in quick succession near your Mac microphone:
- 🤌 **2 Finger Snaps** *(even light or quiet snaps)*
- 👏 **2 Hand Claps**

### 2. What JARVIS Does
1. **Speaks a dynamic greeting** loaded from `phrases.json`.
2. **Scans the local airspace**: If an aircraft is within your radius, JARVIS speaks the flight info and automatically opens/focuses the FlightRadar24 tracking page in your browser.

> 🤌🤌 *(2 snaps)*
>
> **JARVIS:** *"Hello sir, welcome back. Preferred choice of vibe today: Tame Impala or AC/DC?"*
>
> **JARVIS:** *"Sir, Flight AIC101 from Delhi to New York JFK is currently overhead at an altitude of 35,000 feet and a speed of approximately 900 kilometers per hour."*
>
> 🌐 *FlightRadar24 opens in your browser focused on the aircraft.*

---

## 🚀 Installation & Setup

### Prerequisites
- macOS 12 Monterey or later
- Python 3.9+
- Xcode Command Line Tools (`xcode-select --install`) for compiling the native Swift helpers

### Quick Install
Clone the repository and run the install script:

```bash
git clone https://github.com/SarvyagyaPrakash/clap-jarvis.git
cd clap-jarvis
chmod +x *.sh
./install.sh
```

The installer will:
1. Create a Python virtual environment in `./venv`.
2. Install dependencies (`edge-tts`, `sounddevice`, `numpy`, `requests`, `SpeechRecognition`).
3. Compile native Swift helpers (`hud_notifier` & `media_detector`).
4. Register and start the background LaunchAgent daemon (`com.user.clapjarvis.plist`).

---

## 🎙️ Granting Microphone Permission (Crucial)

macOS requires explicit Microphone authorization for background audio capture:

1. Open **System Settings** → **Privacy & Security** → **Microphone**.
2. Ensure **Terminal** (or your terminal emulator such as **iTerm2**) is enabled.
3. If permissions were newly granted, restart the service:
   ```bash
   ./install.sh
   ```

---

## 🎛️ Turning JARVIS ON & OFF

You can pause or resume JARVIS at any time using any of these methods:

### Method A: Terminal Shortcut (Fastest)
Add an alias to your `~/.zshrc` or `~/.bashrc`:
```bash
alias jarvis="/path/to/clap-jarvis/toggle.sh"
```
Then simply type:
```bash
jarvis
```
A floating HUD banner (`🟢 Microphone listener ON` / `🛑 Microphone listener OFF`) will appear in the top-right corner of your screen.

### Method B: Double-Click Desktop Shortcut
Double-click `Toggle JARVIS.command` in Finder or place a shortcut on your Desktop.

### Method C: Helper Scripts
```bash
./toggle.sh   # Toggle ON / OFF with HUD indicator
./start.sh    # Turn ON / Resume daemon
./stop.sh     # Turn OFF / Pause daemon
```

---

## ⚙️ Configuration (`config.json`)

Customize detection sensitivity, coordinates, voice, and suppression behavior in `config.json`:

```json
{
  "threshold_peak": 0.18,
  "threshold_snap_peak": 0.12,
  "min_crest_factor": 4.5,
  "threshold_rms": 0.004,
  "required_claps": 2,
  "window_seconds": 2.5,
  "cooldown_seconds": 4.0,
  "voice": "en-GB-RyanNeural",
  "enable_flight_check": true,
  "enable_jarvis_wake_word": false,
  "suppress_during_audio": true,
  "suppress_during_meetings": false,
  "latitude": 23.23352,
  "longitude": 77.43257,
  "radius_km": 150.0
}
```

### Parameter Reference

| Setting | Type | Description |
| :--- | :--- | :--- |
| `required_claps` | `int` | Number of snaps/claps required to trigger (default: `2`). |
| `window_seconds` | `float` | Maximum time window to complete the required snaps/claps (default: `2.5s`). |
| `cooldown_seconds` | `float` | Silence cooldown after activation to prevent self-triggering (default: `4.0s`). |
| `voice` | `string` | Neural voice identifier (e.g., `en-GB-RyanNeural`, `en-GB-SoniaNeural`, `en-US-GuyNeural`). |
| `enable_flight_check` | `bool` | Whether to scan and announce overhead aircraft via FlightRadar24. |
| `latitude` / `longitude` | `float` | Your coordinates for airspace calculations. |
| `radius_km` | `float` | Airspace search radius in kilometers (default: `150.0`). |
| `suppress_during_audio` | `bool` | Prevent triggering while audio/video is actively playing in media apps or browser tabs. |
| `suppress_during_meetings` | `bool` | Prevent triggering while in video calls (Zoom, Meet, Teams, etc.). |
| `threshold_snap_peak` | `float` | Peak threshold for snap transients (default: `0.12`). |
| `threshold_peak` | `float` | Peak threshold for hand claps (default: `0.18`). |
| `min_crest_factor` | `float` | Minimum crest factor (peak-to-RMS ratio) to distinguish sharp snaps from voice. |

---

## 💬 Customizing Phrases (`phrases.json`)

Add or edit lines in `phrases.json`:

```json
[
  "Hello sir, welcome back. Prefered choice of vibe today: Tame Impala or ACDC?",
  "Terrific timing, sir. Your suit is 80% charged. Coffee is on the table.",
  "Good to see you again, sir. Your Porsche will reach by tonight.",
  "Welcome back, sir. Your Pizza is on the way. Do you want me to turn on the X-box?",
  "Welcome back sir, your meeting with Elon Musk is clashing with your dinner with your girlfriend. Do you want me to inform Elon to reschedule?"
]
```

> 💡 **Hot Reload**: Changes to `phrases.json` are applied instantly upon the next trigger without restarting the daemon.

---

## 🔍 Calibration & Diagnostics

### 1. Live Sensitivity Calibration
Run calibration mode in Terminal to view real-time percussive meters and test your snap/clap detection:
```bash
./venv/bin/python clap_jarvis.py --calibrate
```

### 2. Live Logs
Monitor real-time daemon events and trigger logs:
```bash
tail -f ~/Library/Logs/clap-jarvis.log
```

Error log:
```bash
tail -f ~/Library/Logs/clap-jarvis.err.log
```

---

## 🗑️ Uninstallation

To completely stop and remove the background LaunchAgent:
```bash
./uninstall.sh
```

---

## 📄 License

This project is licensed under the MIT License.
