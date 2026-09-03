# 🤌 snap-jarvis — Your Mac, but it answers finger snaps

[![macOS](https://img.shields.io/badge/Platform-macOS-black?logo=apple&logoColor=white)](https://apple.com)
[![Python 3.9+](https://img.shields.io/badge/Python-3.9%2B-blue?logo=python&logoColor=white)](https://python.org)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

Snap your fingers twice. And your Mac talks back to you in a smooth British neural voice (`en-GB-RyanNeural`), Iron Man style. It even tells you if there's a plane flying over your head right now.

No apps to open. No buttons to press. JARVIS lives quietly in the background and wakes up strictly when *you* snap.

> 🤌🤌 *(two snaps)*
>
> **JARVIS:** *"Good to see you again, sir."*

Sounds fun? It takes about **5 minutes** to set up. Let's go. 🚀

---

## 🧰 Before we start — what you'll need

- ✅ A Mac (macOS 12 Monterey or newer)
- ✅ A working microphone (built-in is fine)
- ✅ Internet connection (JARVIS streams his voice + checks flights online)
- ✅ About 5 minutes

That's it. No coding knowledge needed.

---

## 🚀 Installation (follow along step by step)

### Step 1 — Open the Terminal

Press `⌘ + Space`, type **Terminal**, hit Enter.

A window with white (or black) text appears. This is where you talk to your Mac directly. Don't worry — I'll tell you exactly what to type.

### Step 2 — Install Apple's build tools (one-time thing)

JARVIS needs a small Apple toolkit to build his on-screen display. Paste this and hit Enter:

```bash
xcode-select --install
```

A popup will appear → click **Install** → wait for it to finish (a few minutes).

> 💡 **If you see** *"command line tools are already installed"* — great, you're ahead of schedule. Move on!

### Step 3 — Download JARVIS

Paste these two lines (one at a time):

```bash
git clone https://github.com/SarvyagyaPrakash/clap-jarvis.git
cd clap-jarvis
```

✅ **Checkpoint:** You're now inside the JARVIS folder. You can't see it, but trust the process.

> 😱 **"Command not found: git"?** Your Mac wants to install developer tools first — just run Step 2's command again, or paste this instead:
> ```bash
> git --version
> ```
> A popup appears → click **Install** → then retry Step 3.

### Step 4 — Run the magic installer

```bash
chmod +x *.sh
./install.sh
```

This single command does everything: sets up Python, installs what's needed, builds JARVIS's helpers, and starts him running in the background.

✅ **Checkpoint:** Wait until you see:

```
===============================================
          INSTALLATION COMPLETE! 🎉
===============================================
```

If you see that — you're 90% done. One last permission to grant.

---

## 🎙️ Step 5 — Let JARVIS hear you (important!)

macOS is protective of your microphone, so we need to explicitly allow it:

1. Click the  in your menu bar → **System Settings**
2. Go to **Privacy & Security** → **Microphone**
3. Find **Terminal** (or iTerm2, whichever you use) and switch it **ON**

> 💡 Don't see Terminal in the list? That's fine — it usually appears after the first run. Just continue to Step 6; macOS will pop up asking for permission, click **OK**, then come back here and re-run:
> ```bash
> ./install.sh
> ```

---

## 🧪 Is it working? Let's find out!

Time for the fun part. Make sure you're somewhere not too noisy, then:

### Test 1: The Snap Test 🤌🤌

Simply **snap your fingers twice**, sharply, near your Mac.

🎉 **Did JARVIS speak?** Congratulations — you now have your own JARVIS.

🤔 **Nothing happened?** Try this quick check — paste in Terminal:

```bash
tail -f ~/Library/Logs/clap-jarvis.log
```

Now snap again while watching the screen:

| What you see | What it means |
| :--- | :--- |
| Lines appear mentioning a trigger / phrase | He heard your snaps! If he's silent, check your volume 🔊 |
| Nothing appears at all | He can't hear you → mic permission issue, redo Step 5 |
| An error mentioning microphone/audio | Same fix — Step 5, then re-run `./install.sh` |

*(Press `Ctrl + C` to stop watching the log when you're done.)*

### Test 2: The Hearing Test 🎚️

Want to see how loudly JARVIS perceives your snaps in real time? Run his calibration mode:

```bash
./venv/bin/python clap_jarvis.py --calibrate
```

Snap a few times — you should see meters jump and display `🤌 [SNAP DETECTED!]`. If they barely move, get closer to the mic or adjust thresholds in `config.json`. *(Press `Ctrl + C` to exit.)*

### Test 3: Confirm he's always on duty 🫡

```bash
launchctl list | grep clapjarvis
```

If you see a line containing `com.user.clapjarvis` with a number next to it — JARVIS is officially running in the background, even after restarts.

---

## 🎛️ Turning JARVIS ON & OFF

Need quiet time? Pause him any of these ways:

**Option A — The one-word command (fastest)**

```bash
./toggle.sh
```

A banner appears on screen: `🟢 Microphone listener ON` or `🛑 Microphone listener OFF`.

<details>
<summary><b>Option B — Double-click from Finder (no Terminal at all)</b></summary>

Open the `clap-jarvis` folder in Finder and double-click **`Toggle JARVIS.command`**.
*(First time only: right-click → Open → Open, because Macs are suspicious of new files.)*

</details>

**Option C — Power-user shortcut**

Add this once to make a personal command called `jarvis`:

```bash
echo 'alias jarvis="/path/to/clap-jarvis/toggle.sh"' >> ~/.zshrc && source ~/.zshrc
```

*(Replace `/path/to/clap-jarvis` with wherever you put the folder — drag the folder into Terminal to get its path automatically.)*

From then on, just typing `jarvis` toggles him forever.

---

## ✨ Make JARVIS yours

All settings live in two simple files inside the folder. Open them with TextEdit and edit away.

### 🗣️ Change what he says (`phrases.json`)

Edit the list, save — changes apply **instantly**, no restart needed:

```json
[
  "Welcome back, sir. Your coffee machine missed you.",
  "Good evening, sir. Shall I dim the lights?",
  "Hello sir. The internet says you've been scrolling for 3 hours."
]
```

### ⚙️ Change how he behaves (`config.json`)

The settings people actually change:

| I want to... | Change this |
| :--- | :--- |
| Voice | Exclusively locked to British Neural Voice (`"voice": "en-GB-RyanNeural"`) |
| Stop flight announcements | `"enable_flight_check": false` |
| Update my location for flight tracking | Set `latitude` / `longitude` ([find yours here](https://latlong.info)) |
| Make him less sensitive to snaps | Raise `"threshold_snap_peak"` to `0.12` |
| Make him more sensitive to snaps | Lower `"threshold_snap_peak"` to `0.06` |

> 🤫 **Nice touch:** JARVIS automatically stays silent while you're listening to music or watching videos — so no random interruptions mid-song.

---

## 🆘 Something's wrong? (Plain-English fixes)

| Problem | Fix |
| :--- | :--- |
| **Installed fine, but ignores my snaps** | 99% of the time it's mic permission → redo Step 5, then `./install.sh`. Also try sharper snaps closer to the mic. |
| **Speaks, but too quietly** | Turn up system volume — his voice plays through your speakers. |
| **Triggers randomly during videos/music** | That shouldn't happen — he suppresses himself during media playback. Check `"suppress_during_audio": true` in `config.json`. |
| **Flight announcements are about the wrong city** | Update `latitude` / `longitude` in `config.json` to your location. |
| **`swiftc: command not found` during install** | Run `xcode-select --install` (Step 2) and retry. |
| **Everything broke / want a fresh start** | `./uninstall.sh` → then `./install.sh` again. Clean slate. |

Still stuck? Watch his live thoughts while reproducing the problem:

```bash
tail -f ~/Library/Logs/clap-jarvis.log        # what he's doing
tail -f ~/Library/Logs/clap-jarvis.err.log    # what went wrong
```

---

## 🗑️ Breaking up with JARVIS

We'll miss you. To remove him completely:

```bash
./uninstall.sh
```

Then just delete the folder. No traces left behind.

---

## 🤓 Under the hood (for the curious)

- Listens via `sounddevice` and uses high-frequency FFT spectral analysis (2kHz - 8kHz) + Crest Factor analysis to specifically detect finger snaps and reject speech, claps, typing, or room noise
- Voice: Exclusively Microsoft Edge British Neural TTS (`en-GB-RyanNeural`)
- Flights: real-time airspace data within your radius, announced with altitude/speed/route, opens FlightRadar24 focused on the aircraft
- Runs as a native macOS **LaunchAgent** — survives reboots, zero windows, zero dock icons
- Native Swift HUD overlay for status banners, plus smart suppression during media/meetings

---

## 📄 License

MIT — free to use, modify, and show off to friends.
