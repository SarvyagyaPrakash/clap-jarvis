#!/usr/bin/env python3

import asyncio
import os
import subprocess
import threading
import time
import webbrowser
from config_manager import logger

try:
    import edge_tts
    HAS_EDGE_TTS = True
except ImportError:
    HAS_EDGE_TTS = False


def open_or_refresh_flightradar_tab(target_url):
    """Refreshes an existing FlightRadar24 tab in any running browser if present, otherwise opens a new tab via webbrowser.open()."""
    chromium_candidates = [
        ("brave browser", "Brave Browser"),
        ("google chrome", "Google Chrome"),
        ("microsoft edge", "Microsoft Edge"),
        ("arc", "Arc"),
        ("opera", "Opera"),
        ("vivaldi", "Vivaldi")
    ]

    try:
        from activity_monitor import get_running_process_basenames
        running = get_running_process_basenames()
    except Exception:
        running = set()

    for proc_key, app_title in chromium_candidates:
        if proc_key in running:
            scpt = f"""
            tell application "{app_title}"
                repeat with w in windows
                    set tIndex to 0
                    repeat with t in tabs of w
                        set tIndex to tIndex + 1
                        if (URL of t) contains "flightradar24.com" then
                            set URL of t to "{target_url}"
                            set active tab index of w to tIndex
                            set index of w to 1
                            activate
                            return "updated"
                        end if
                    end repeat
                end repeat
                return "not_found"
            end tell
            """
            try:
                res = subprocess.check_output(["osascript", "-e", scpt], universal_newlines=True, timeout=0.8).strip()
                if res == "updated":
                    logger.info(f"Refreshed existing FlightRadar24 tab in {app_title} to '{target_url}' (no duplicate tab opened).")
                    return True
            except Exception:
                pass

    if "safari" in running:
        safari_scpt = f"""
        tell application "Safari"
            repeat with w in windows
                repeat with t in tabs of w
                    if (URL of t) contains "flightradar24.com" then
                        set URL of t to "{target_url}"
                        set current tab of w to t
                        set index of w to 1
                        activate
                        return "updated"
                    end if
                end repeat
            end repeat
            return "not_found"
        end tell
        """
        try:
            res = subprocess.check_output(["osascript", "-e", safari_scpt], universal_newlines=True, timeout=0.8).strip()
            if res == "updated":
                logger.info(f"Refreshed existing FlightRadar24 tab in Safari to '{target_url}' (no duplicate tab opened).")
                return True
        except Exception:
            pass

    logger.info(f"No existing FlightRadar24 tab found. Opening in default browser: {target_url}")
    webbrowser.open(target_url)
    return False


def is_flightradar_tab_open():
    """Checks if any FlightRadar24 tab is currently open in any running browser."""
    chromium_candidates = [
        ("brave browser", "Brave Browser"),
        ("google chrome", "Google Chrome"),
        ("google chrome canary", "Google Chrome Canary"),
        ("chromium", "Chromium"),
        ("microsoft edge", "Microsoft Edge"),
        ("arc", "Arc"),
        ("opera", "Opera"),
        ("vivaldi", "Vivaldi")
    ]

    try:
        from activity_monitor import get_running_process_basenames
        running = get_running_process_basenames()
    except Exception:
        running = set()

    for proc_key, app_title in chromium_candidates:
        if proc_key in running:
            scpt = f"""
            tell application "{app_title}"
                repeat with w in windows
                    repeat with t in tabs of w
                        if (URL of t) contains "flightradar24.com" then
                            return "true"
                        end if
                    end repeat
                end repeat
                return "false"
            end tell
            """
            try:
                res = subprocess.check_output(["osascript", "-e", scpt], universal_newlines=True, timeout=0.6).strip()
                if res == "true":
                    return True
            except Exception:
                pass

    if "safari" in running:
        safari_scpt = """
        tell application "Safari"
            repeat with w in windows
                repeat with t in tabs of w
                    if (URL of t) contains "flightradar24.com" then
                        return "true"
                    end if
                end repeat
            end repeat
            return "false"
        end tell
        """
        try:
            res = subprocess.check_output(["osascript", "-e", safari_scpt], universal_newlines=True, timeout=0.6).strip()
            if res == "true":
                return True
        except Exception:
            pass

    return False


def play_audio_process_with_tab_monitor(cmd, monitor_flightradar=False):
    """Executes audio playback command (afplay or say) and cancels immediately if the monitored FlightRadar tab is closed."""
    try:
        proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception as e:
        logger.error(f"Failed to start speech playback process {cmd}: {e}")
        return False

    if not monitor_flightradar:
        proc.wait()
        return proc.returncode == 0

    seen_tab = is_flightradar_tab_open()
    start_time = time.time()
    tab_grace_period = 3.0

    while proc.poll() is None:
        tab_open = is_flightradar_tab_open()
        if tab_open:
            seen_tab = True
        elif seen_tab:
            logger.info("🛑 FlightRadar24 tab was closed by user. Immediately stopping JARVIS speech.")
            proc.terminate()
            try:
                proc.wait(timeout=0.2)
            except Exception:
                proc.kill()
            return True
        elif time.time() - start_time > tab_grace_period:
            logger.info("🛑 FlightRadar24 tab no longer open. Stopping JARVIS speech.")
            proc.terminate()
            try:
                proc.wait(timeout=0.2)
            except Exception:
                proc.kill()
            return True

        time.sleep(0.15)

    return proc.returncode == 0


def speak_and_launch(phrase, voice, flight_data=None, on_done=None):
    """Speaks phrase non-blockingly using neural TTS (edge-tts) or macOS 'say' fallback."""
    logger.info(f"Speaking response using voice '{voice}': '{phrase}'")

    monitor_fr24 = bool(flight_data)
    speech_start_time = time.time()

    def run_speech():
        played_successfully = False
        # Exclusively lock to en-GB-RyanNeural voice
        target_voice = "en-GB-RyanNeural"

        try:
            # 1. Try Ultra-Realistic Neural TTS via edge-tts
            if HAS_EDGE_TTS and ("Neural" in target_voice or "en-GB" in target_voice):
                tmp_mp3 = f"/tmp/jarvis_speech_{int(time.time()*1000)}.mp3"
                try:
                    async def generate():
                        communicate = edge_tts.Communicate(phrase, target_voice)
                        await communicate.save(tmp_mp3)

                    asyncio.run(generate())

                    if monitor_fr24 and not is_flightradar_tab_open() and (time.time() - speech_start_time > 2.5):
                        logger.info("FlightRadar24 tab closed before audio playback started. Aborting speech.")
                    else:
                        play_audio_process_with_tab_monitor(["afplay", tmp_mp3], monitor_flightradar=monitor_fr24)
                        played_successfully = True
                except Exception as e:
                    logger.warning(f"edge-tts neural generation failed ({e}), falling back to macOS 'say'.")
                finally:
                    if os.path.exists(tmp_mp3):
                        try:
                            os.remove(tmp_mp3)
                        except Exception:
                            pass

            # 2. Fallback to native macOS 'say' command
            if not played_successfully:
                try:
                    play_audio_process_with_tab_monitor(["say", "-v", "Daniel", phrase], monitor_flightradar=monitor_fr24)
                except Exception as e:
                    logger.error(f"Failed to execute native 'say' command: {e}")
        finally:
            if on_done:
                try:
                    on_done()
                except Exception as e:
                    logger.error(f"Error in on_done speech callback: {e}")

    # Launch browser open/refresh concurrently in parallel background thread
    def launch_browser():
        try:
            if flight_data and flight_data.get("fr24_url"):
                url = flight_data["fr24_url"]
                logger.info(f"Tracking exact verified plane on FlightRadar24: {url}")
            elif flight_data and flight_data.get("callsign"):
                callsign = flight_data["callsign"]
                url = f"https://www.flightradar24.com/flight/{callsign.lower()}"
                logger.info(f"Tracking exact flight on FlightRadar24 via callsign: {url}")
            elif flight_data and flight_data.get("icao24"):
                icao24 = flight_data["icao24"]
                url = f"https://www.flightradar24.com/data/aircraft/{icao24.lower()}"
                logger.info(f"Tracking exact aircraft on FlightRadar24 via ICAO24 hex: {url}")
            elif flight_data and flight_data.get("lat") and flight_data.get("lon"):
                lat, lon = flight_data["lat"], flight_data["lon"]
                url = f"https://www.flightradar24.com/{lat:.2f},{lon:.2f}/11"
                logger.info(f"Opening FlightRadar24 map centered at tracked coordinates: {url}")
            else:
                url = "https://www.flightradar24.com"
                logger.info(f"Opening main FlightRadar24 website: {url}")

            open_or_refresh_flightradar_tab(url)
        except Exception as e:
            logger.error(f"Failed to open/refresh browser URL: {e}")

    threading.Thread(target=launch_browser, daemon=True).start()
    threading.Thread(target=run_speech, daemon=True).start()
