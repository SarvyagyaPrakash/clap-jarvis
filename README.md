# 👏 clap-jarvis

`clap-jarvis` is your personal macOS background assistant inspired by Iron Man's JARVIS. It runs quietly in the background 24/7. Snap or clap **3 times**, and JARVIS will respond in a realistic British butler voice and open FlightRadar24 focused on any airplane flying overhead.

---

## 🎯 How to Use It Day-to-Day

### 1. Triggering JARVIS
Just clap your hands **3 times** or snap your fingers **3 times** in quick succession anywhere near your Mac:
- 👏 **3 Hand Claps**
- 🤌 **3 Finger Snaps** *(even light / quiet snaps work!)*

### 2. What Happens Next
1. JARVIS greets you in a realistic British voice (e.g., *"Hello sir, welcome back. Tame Impala or ACDC today?"*).
2. If an airplane is flying within 100 km of your location, JARVIS announces it with origin and destination details (e.g., *"Sir, flight AIC101 flying from Delhi to New York JFK is currently overhead at 35,000 feet."*) and opens FlightRadar24 directly focusing on that exact plane.

### 3. Example: What JARVIS Says
A typical session sounds like this:

> 👏👏👏 *(3 claps)*
>
> **JARVIS:** *"Hello sir, welcome back. Prefered choice of vibe today: Tame Impala? or ACDC?"*
>
> **JARVIS:** *"Sir, Flight AIC101 from Delhi to New York JFK will cross your coordinates at exactly 4 mins, at an altitude of 35,000 feet and a speed of approximately 900 kilometers per hour."*
>
> 🌐 *FlightRadar24 opens in your browser, focused on that exact plane.*

---

## 🎛️ How to Turn JARVIS ON & OFF

You can pause or resume JARVIS anytime using any of these 3 easy methods:

### Method A: Type `jarvis` in Terminal (Easiest)
Open Terminal and type:
```bash
jarvis
```
> ⚡ Automatically toggles JARVIS **ON 🟢** or **OFF 🛑** and shows a popup banner on your screen.

### Method B: Double-Click the Desktop Shortcut
Double-click `Toggle JARVIS.command` in the project folder (or on your desktop).

### Method C: Run Quick Scripts
```bash
./stop.sh    # Turn OFF / Pause
./start.sh   # Turn ON / Resume
./toggle.sh  # Toggle ON/OFF
```

---

## 💬 How to Customize What JARVIS Says

You can add, edit, or remove phrases anytime by opening [`phrases.json`](file:///Users/sarvyagyaprakash/DRIVE/CODE/jarvis4mac/clap-jarvis/phrases.json) in your text editor:

```json
[
  "Hello sir, welcome back. Tame Impala or ACDC today?",
  "Terrific timing, sir. Your suit is 80% charged. Coffee is on the table.",
  "Good to see you again, sir. Your Porsche will reach by tonight.",
  "Pizza is on the way, sir. Do you want me to turn on the X-box?",
  "Sir, your dinner with Elon Musk is clashing with your dinner with Miss Potts. Do you want me to inform Elon to reschedule?"
]
```
> 💡 Save the file and JARVIS updates his speech lines **instantly** without needing a restart!

---

## 🗺️ How to Set Your Location for Overhead Flight Tracking

Open [`config.json`](file:///Users/sarvyagyaprakash/DRIVE/CODE/jarvis4mac/clap-jarvis/config.json) to set your latitude, longitude, and search radius:

```json
{
  "latitude": 23.2875,
  "longitude": 77.3378,
  "radius_km": 100.0
}
```
Replace `"latitude"` and `"longitude"` with your coordinates (from Google Maps or iPhone Compass app).

---

## 🎙️ First-Time Setup: Granting Microphone Permission

macOS requires you to grant Microphone access once so background applications can record audio:

1. Open **System Settings** on your Mac.
2. Go to **Privacy & Security** → **Microphone**.
3. Ensure **Terminal** (or **iTerm2**) is toggled **ON**.
4. If permissions were missing, reload JARVIS:
   ```bash
   ./install.sh
   ```

---

## 🔍 Checking Logs & Testing

- **Live Activity Log**: Watch detections in real time:
  ```bash
  tail -f ~/Library/Logs/clap-jarvis.log
  ```
- **Test Sensitivity**: Run live calibration in Terminal to see real-time snap/clap visual meters:
  ```bash
  ./venv/bin/python clap_jarvis.py --calibrate
  ```

---

## 🗑️ How to Uninstall

To remove the background service completely:
```bash
./uninstall.sh
```
