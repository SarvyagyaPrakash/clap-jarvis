#!/usr/bin/env python3
"""
clap-jarvis: macOS background utility to detect double claps, double snaps, or spoken wake-word "Jarvis",
respond with a human-like neural butler TTS (edge-tts), and track overhead flights on FlightRadar24.
"""

import argparse
import asyncio
import json
import logging
import math
import os
import random
import sys
import time
import subprocess
import threading
import webbrowser
from logging.handlers import RotatingFileHandler

import numpy as np
import sounddevice as sd
import requests
import speech_recognition as sr

try:
    import edge_tts
    HAS_EDGE_TTS = True
except ImportError:
    HAS_EDGE_TTS = False

# Default Fallback Configurations (optimized for sensitivity and human-like neural voice)
DEFAULT_CONFIG = {
    "threshold_peak": 0.22,         # Clap peak threshold (prevents voice false-positives)
    "threshold_snap_peak": 0.12,   # Snap peak threshold
    "min_crest_factor": 4.0,        # High peak-to-RMS ratio (sharp percussive transients like claps/snaps)
    "threshold_rms": 0.006,         # RMS energy floor
    "required_claps": 3,            # Requires exactly 3 snaps or claps
    "window_seconds": 4.5,          # Flexible window for fast or slow claps/snaps
    "cooldown_seconds": 5.0,        # Pause after trigger to prevent self-triggering from TTS
    "voice": "en-GB-RyanNeural",    # Ultra-realistic British Male Neural Voice (JARVIS)
    "enable_flight_check": True,
    "latitude": 23.2875,            # Bhopal Airport coordinates
    "longitude": 77.3378,
    "radius_km": 100.0,
    "sample_rate": 44100,
    "block_size": 1024,
    "enable_jarvis_wake_word": False # Spoken "Jarvis" activation disabled
}

DEFAULT_PHRASES = [
    "Hello sir, welcome back.",
    "Terrific timing, sir — I just woke up too.",
    "Good to see you again, sir.",
    "Standing by, sir.",
    "At your service, sir. All defense protocols remain active.",
    "Sensors online and operating at maximum efficiency, sir.",
    "Always a pleasure, sir. How may I assist your genius today?",
    "Awaiting your command, sir. House systems are operating smoothly."
]

LOG_FILE = os.path.expanduser("~/Library/Logs/clap-jarvis.log")
PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(PROJECT_DIR, "config.json")
PHRASES_PATH = os.path.join(PROJECT_DIR, "phrases.json")


def setup_logger():
    """Sets up a rotating file logger and optional console handler."""
    logger = logging.getLogger("clap-jarvis")
    logger.setLevel(logging.INFO)
    logger.propagate = False

    log_dir = os.path.dirname(LOG_FILE)
    os.makedirs(log_dir, exist_ok=True)

    handler = RotatingFileHandler(LOG_FILE, maxBytes=2 * 1024 * 1024, backupCount=3)
    formatter = logging.Formatter("[%(asctime)s] [%(levelname)s] %(message)s", datefmt="%Y-%m-%d %H:%M:%S")
    handler.setFormatter(formatter)
    logger.addHandler(handler)

    if sys.stdout.isatty():
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)

    return logger


logger = setup_logger()


def load_config():
    """Loads config.json with fallback values and log warnings on error."""
    config = DEFAULT_CONFIG.copy()
    if not os.path.exists(CONFIG_PATH):
        logger.warning(f"Config file not found at '{CONFIG_PATH}'. Using default settings.")
        return config

    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            user_config = json.load(f)
            if isinstance(user_config, dict):
                config.update(user_config)
            else:
                logger.warning("Malformed config.json (not a dict). Using defaults.")
    except Exception as e:
        logger.warning(f"Failed to read config.json: {e}. Using default settings.")

    return config


def load_phrases():
    """Loads phrases.json with fallback defaults."""
    if not os.path.exists(PHRASES_PATH):
        logger.warning(f"Phrases file not found at '{PHRASES_PATH}'. Using default phrases.")
        return DEFAULT_PHRASES.copy()

    try:
        with open(PHRASES_PATH, "r", encoding="utf-8") as f:
            phrases = json.load(f)
            if isinstance(phrases, list) and len(phrases) > 0:
                return [str(p) for p in phrases]
            else:
                logger.warning("Phrases file is empty or not a list. Using default phrases.")
    except Exception as e:
        logger.warning(f"Failed to read phrases.json: {e}. Using default phrases.")

    return DEFAULT_PHRASES.copy()


AIRPORT_NAMES = {
    "VIDP": "Delhi", "DEL": "Delhi",
    "VABB": "Mumbai", "BOM": "Mumbai",
    "VOBL": "Bengaluru", "BLR": "Bengaluru",
    "VOMM": "Chennai", "MAA": "Chennai",
    "VECC": "Kolkata", "CCU": "Kolkata",
    "VHYD": "Hyderabad", "HYD": "Hyderabad",
    "EGLL": "London Heathrow", "LHR": "London Heathrow",
    "KJFK": "New York JFK", "JFK": "New York JFK",
    "OMDB": "Dubai", "DXB": "Dubai",
    "WSSS": "Singapore", "SIN": "Singapore",
    "VAAH": "Ahmedabad", "AMD": "Ahmedabad",
    "VAGO": "Goa", "GOI": "Goa",
    "VABP": "Bhopal", "BHO": "Bhopal"
}


def get_flight_route(callsign):
    """Retrieves origin and destination airport codes for a callsign from route APIs."""
    if not callsign or callsign == "Unknown":
        return None, None

    headers = {"User-Agent": "Mozilla/5.0"}
    
    # 1. Try HexDB Route API
    try:
        url = f"https://hexdb.io/api/v1/route/icao/{callsign}"
        resp = requests.get(url, headers=headers, timeout=2.0)
        if resp.status_code == 200:
            data = resp.json()
            route_str = data.get("route")
            if route_str and "-" in route_str:
                origin, dest = route_str.split("-", 1)
                return origin.strip(), dest.strip()
    except Exception:
        pass

    # 2. Try OpenSky Routes API fallback
    try:
        url = f"https://opensky-network.org/api/routes?callsign={callsign}"
        resp = requests.get(url, headers=headers, timeout=2.0)
        if resp.status_code == 200:
            data = resp.json()
            route_arr = data.get("route")
            if route_arr and len(route_arr) >= 2:
                return route_arr[0].strip(), route_arr[1].strip()
    except Exception:
        pass

    return None, None


def format_airport_name(code):
    """Converts ICAO/IATA airport code to a human-readable city/airport name."""
    if not code:
        return None
    code_upper = code.upper()
    return AIRPORT_NAMES.get(code_upper, code_upper)


def check_overhead_flight(config):
    """
    Checks OpenSky Network API for flights overhead within bounding box.
    Returns dict with flight details & spoken string if found, or None if no flight / network error.
    """
    try:
        lat = float(config.get("latitude", 23.2875))
        lon = float(config.get("longitude", 77.3378))
        radius_km = float(config.get("radius_km", 100.0))

        # Approx degree offset calculations
        lat_deg = radius_km / 111.0
        lon_deg = radius_km / (111.0 * math.cos(math.radians(lat)))

        lamin = lat - lat_deg
        lamax = lat + lat_deg
        lomin = lon - lon_deg
        lomax = lon + lon_deg

        url = f"https://opensky-network.org/api/states/all?lamin={lamin:.4f}&lamax={lamax:.4f}&lomin={lomin:.4f}&lomax={lomax:.4f}"
        logger.info(f"Querying OpenSky Network API for coordinates ({lat}, {lon}) within {radius_km}km...")
        response = requests.get(url, timeout=3.0)
        
        if response.status_code == 200:
            data = response.json()
            states = data.get("states")
            if states and len(states) > 0:
                # Filter out planes on ground
                airborne_flights = []
                for f in states:
                    on_ground = f[8] if len(f) > 8 else False
                    f_lat = f[6]
                    f_lon = f[5]
                    if not on_ground and f_lat is not None and f_lon is not None:
                        dist_sq = (f_lat - lat)**2 + (f_lon - lon)**2
                        airborne_flights.append((dist_sq, f))

                if airborne_flights:
                    # Sort by closest distance to user
                    airborne_flights.sort(key=lambda x: x[0])
                    flight = airborne_flights[0][1]

                    callsign = (flight[1] or "").strip()
                    if not callsign or callsign == "":
                        callsign = "Unknown"

                    alt_m = flight[7] or flight[13]
                    if isinstance(alt_m, (int, float)):
                        alt_ft = int(alt_m * 3.28084)
                        altitude_str = f"{alt_ft} feet ({int(alt_m)} meters)"
                    else:
                        altitude_str = "unknown altitude"

                    origin_code, dest_code = get_flight_route(callsign)
                    origin_name = format_airport_name(origin_code)
                    dest_name = format_airport_name(dest_code)

                    if origin_name and dest_name:
                        spoken_text = f"Sir, flight {callsign} flying from {origin_name} to {dest_name} is currently overhead at {altitude_str}."
                    else:
                        spoken_text = f"Sir, flight {callsign} is currently overhead at {altitude_str}."

                    logger.info(f"Overhead flight detected: Callsign={callsign}, Route={origin_name}->{dest_name}, Altitude={altitude_str}")
                    
                    return {
                        "spoken_text": spoken_text,
                        "callsign": callsign if callsign != "Unknown" else None,
                        "origin": origin_name,
                        "destination": dest_name,
                        "lat": flight[6],
                        "lon": flight[5]
                    }
                else:
                    logger.info("OpenSky query: Planes found in area, but all are on the ground.")
            else:
                logger.info("OpenSky query completed: No flights currently overhead.")
        else:
            logger.warning(f"OpenSky API HTTP status {response.status_code}")
    except Exception as e:
        logger.warning(f"OpenSky API query failed or timed out: {e}")

    return None


def speak_and_launch(phrase, voice, flight_data=None):
    """Speaks phrase non-blockingly using neural TTS (edge-tts) or macOS 'say' fallback."""
    logger.info(f"Speaking response using voice '{voice}': '{phrase}'")

    def run_speech():
        played_successfully = False
        target_voice = voice

        # Resolve voice alias to high quality British neural voice
        if target_voice in ["Daniel", "JARVIS", "Ryan", "default"]:
            target_voice = "en-GB-RyanNeural"
        elif target_voice in ["Thomas"]:
            target_voice = "en-GB-ThomasNeural"

        # 1. Try Ultra-Realistic Neural TTS via edge-tts
        if HAS_EDGE_TTS and ("Neural" in target_voice or "en-GB" in target_voice):
            tmp_mp3 = f"/tmp/jarvis_speech_{int(time.time()*1000)}.mp3"
            try:
                async def generate():
                    communicate = edge_tts.Communicate(phrase, target_voice)
                    await communicate.save(tmp_mp3)

                asyncio.run(generate())
                subprocess.run(["afplay", tmp_mp3], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
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
                subprocess.run(["say", "-v", "Daniel", phrase])
            except Exception as e:
                logger.error(f"Failed to execute native 'say' command: {e}")

    # Launch speech in background thread
    threading.Thread(target=run_speech, daemon=True).start()

    # Open browser to FlightRadar24
    try:
        if flight_data and flight_data.get("callsign"):
            callsign = flight_data["callsign"]
            url = f"https://www.flightradar24.com/flight/{callsign.lower()}"
            logger.info(f"Tracking exact flight on FlightRadar24: {url}")
        elif flight_data and flight_data.get("lat") and flight_data.get("lon"):
            lat, lon = flight_data["lat"], flight_data["lon"]
            url = f"https://www.flightradar24.com/{lat:.2f},{lon:.2f}/9"
            logger.info(f"Opening FlightRadar24 map centered at tracked coordinates: {url}")
        else:
            url = "https://www.flightradar24.com"
            logger.info(f"Opening FlightRadar24 main map: {url}")

        webbrowser.open(url)
    except Exception as e:
        logger.error(f"Failed to open browser URL: {e}")


def run_calibration(config):
    """Runs a 30-second calibration mode printing live peak, RMS, and Crest Factor levels."""
    print("=" * 75)
    print("  CLAP-JARVIS CALIBRATION (CLAPS, FINGER SNAPS & 'JARVIS' WAKE WORD)")
    print("=" * 75)
    print("1. Clap your hands OR snap your fingers and observe real-time spikes.")
    print("2. Say 'Jarvis' out loud to test speech recognition.")
    print("Press Ctrl+C at any time to exit calibration.\n")

    sample_rate = config.get("sample_rate", 44100)
    block_size = config.get("block_size", 1024)

    max_observed_peak = 0.0

    def calibrate_callback(indata, frames, time_info, status):
        nonlocal max_observed_peak
        if status:
            logger.warning(f"Audio status issue: {status}")

        peak = float(np.max(np.abs(indata)))
        rms = float(np.sqrt(np.mean(indata ** 2)))
        crest_factor = peak / (rms + 1e-6)

        if peak > max_observed_peak:
            max_observed_peak = peak

        threshold_peak = float(config.get("threshold_peak", 0.15))
        threshold_snap_peak = float(config.get("threshold_snap_peak", 0.05))
        min_crest_factor = float(config.get("min_crest_factor", 3.0))

        is_clap = peak >= threshold_peak and rms >= float(config.get("threshold_rms", 0.003))
        is_snap = peak >= threshold_snap_peak and crest_factor >= min_crest_factor

        event_str = "               "
        if is_clap and is_snap:
            event_str = "💥 [CLAP/SNAP] "
        elif is_clap:
            event_str = "👏 [HAND CLAP] "
        elif is_snap:
            event_str = "🤌 [FINGER SNAP]"

        bar_len = int(min(peak, 1.0) * 30)
        bar = "#" * bar_len + " " * (30 - bar_len)
        sys.stdout.write(f"\rPeak: {peak:.3f} [{bar}] | RMS: {rms:.3f} | Crest: {crest_factor:.1f} | {event_str}")
        sys.stdout.flush()

    try:
        with sd.InputStream(samplerate=sample_rate, blocksize=block_size, channels=1, callback=calibrate_callback):
            start_time = time.time()
            while time.time() - start_time < 30:
                time.sleep(0.1)
        print("\n\nCalibration completed (30s elapsed).")
    except KeyboardInterrupt:
        print("\n\nCalibration stopped by user.")
    except Exception as e:
        logger.error(f"Calibration audio error: {e}")
        print(f"\nError initializing microphone: {e}")
        print("Check Microphone permissions in System Settings -> Privacy & Security -> Microphone.")


class ClapDaemon:
    def __init__(self):
        self.config = load_config()
        self.phrases = load_phrases()
        self.clap_timestamps = []
        self.cooldown_until = 0.0
        self.last_clap_time = 0.0
        self.min_inter_clap_gap = 0.08
        
        # Audio speech buffer for "Jarvis" wake word speech recognition
        self.speech_chunks = []
        self.speech_recognizer = sr.Recognizer()
        self.is_recognizing = False

        # Non-repeating phrase memory for maximum randomness
        self.recent_phrases = []

    def check_speech_for_jarvis(self, audio_bytes):
        """Worker thread executing speech recognition for the wake word 'Jarvis'."""
        self.is_recognizing = True
        try:
            sample_rate = int(self.config.get("sample_rate", 44100))
            audio_data = sr.AudioData(audio_bytes, sample_rate, 2)
            text = self.speech_recognizer.recognize_google(audio_data).lower()
            logger.info(f"Transcribed speech: '{text}'")
            
            if "jarvis" in text:
                now = time.time()
                if now >= self.cooldown_until:
                    logger.info(">>> TRIGGER DETECTED: Spoken wake word 'Jarvis'! <<<")
                    cooldown_seconds = float(self.config.get("cooldown_seconds", 5.0))
                    self.cooldown_until = now + cooldown_seconds
                    threading.Thread(target=self.handle_trigger, daemon=True).start()
        except sr.UnknownValueError:
            pass  # Speech not clear or background noise
        except Exception as e:
            logger.debug(f"Speech recognition check exception: {e}")
        finally:
            self.is_recognizing = False

    def audio_callback(self, indata, frames, time_info, status):
        """Audio streaming callback executed for every frame chunk."""
        try:
            if status:
                logger.warning(f"Audio callback status: {status}")

            now = time.time()

            # Ignore audio while in cooldown (prevents TTS voice from self-triggering)
            if now < self.cooldown_until:
                self.speech_chunks.clear()
                return

            peak = float(np.max(np.abs(indata)))
            rms = float(np.sqrt(np.mean(indata ** 2)))
            crest_factor = peak / (rms + 1e-6)

            threshold_peak = float(self.config.get("threshold_peak", 0.15))
            threshold_snap_peak = float(self.config.get("threshold_snap_peak", 0.05))
            threshold_rms = float(self.config.get("threshold_rms", 0.003))
            min_crest_factor = float(self.config.get("min_crest_factor", 3.0))

            # 1. Check Hand Clap and Finger Snap transients
            is_clap = peak >= threshold_peak and rms >= threshold_rms
            is_snap = peak >= threshold_snap_peak and crest_factor >= min_crest_factor

            if is_clap or is_snap:
                if now - self.last_clap_time >= self.min_inter_clap_gap:
                    self.last_clap_time = now
                    self.clap_timestamps.append(now)
                    event_type = "Hand Clap" if is_clap else "Finger Snap"
                    logger.info(f"{event_type} detected! Peak: {peak:.3f}, RMS: {rms:.3f}, Crest: {crest_factor:.1f}")

                    window_seconds = float(self.config.get("window_seconds", 2.5))
                    required_claps = int(self.config.get("required_claps", 3))
                    self.clap_timestamps = [t for t in self.clap_timestamps if now - t <= window_seconds]

                    if len(self.clap_timestamps) >= required_claps:
                        logger.info(f">>> TRIGGER DETECTED: {required_claps} claps/snaps within window! <<<")
                        cooldown_seconds = float(self.config.get("cooldown_seconds", 5.0))
                        self.cooldown_until = now + cooldown_seconds
                        self.clap_timestamps.clear()
                        self.speech_chunks.clear()
                        threading.Thread(target=self.handle_trigger, daemon=True).start()
                        return

            # 2. Accumulate continuous speech audio for "Jarvis" wake word recognition
            if self.config.get("enable_jarvis_wake_word", True):
                if rms > 0.008:
                    int16_chunk = (indata * 32767).astype(np.int16).tobytes()
                    self.speech_chunks.append(int16_chunk)
                
                sample_rate = int(self.config.get("sample_rate", 44100))
                if len(self.speech_chunks) >= int((sample_rate / 1024) * 1.5):
                    if not self.is_recognizing:
                        full_audio_bytes = b"".join(self.speech_chunks)
                        self.speech_chunks.clear()
                        threading.Thread(target=self.check_speech_for_jarvis, args=(full_audio_bytes,), daemon=True).start()
                    else:
                        self.speech_chunks = self.speech_chunks[-10:]

        except Exception as e:
            logger.error(f"Error inside audio callback: {e}", exc_info=True)

    def get_random_phrase(self):
        """Selects a phrase randomly while preventing immediate duplicates."""
        phrases = load_phrases()
        if not phrases:
            return "At your service, sir."

        # Exclude recently spoken phrases if possible to increase randomness & variety
        available = [p for p in phrases if p not in self.recent_phrases]
        if not available:
            # History exhausted: reset history except for the very last spoken phrase
            last_spoken = self.recent_phrases[-1] if self.recent_phrases else None
            available = [p for p in phrases if p != last_spoken]
            self.recent_phrases.clear()
            if not available:
                available = phrases

        chosen = random.choice(available)

        # Retain history up to 50% of total phrase pool size (max 20 entries)
        max_history = max(1, min(len(phrases) - 1, 20))
        self.recent_phrases.append(chosen)
        if len(self.recent_phrases) > max_history:
            self.recent_phrases.pop(0)

        return chosen

    def handle_trigger(self):
        """Handles response logic upon trigger (double clap, double snap, or spoken 'Jarvis')."""
        flight_info = None
        spoken_line = None
        
        self.config = load_config()

        # 1. Flight Overhead Check if enabled
        if self.config.get("enable_flight_check", True):
            flight_info = check_overhead_flight(self.config)
            if flight_info:
                spoken_line = flight_info.get("spoken_text")

        # 2. Fallback to random phrase from phrases.json if no flight found
        if not spoken_line:
            spoken_line = self.get_random_phrase()

        voice = self.config.get("voice", "en-GB-RyanNeural")
        speak_and_launch(spoken_line, voice, flight_data=flight_info)

    def run(self):
        """Starts main loop listening continuously with auto-reconnect on sleep/wake."""
        logger.info("Starting clap-jarvis daemon...")
        sample_rate = int(self.config.get("sample_rate", 44100))
        block_size = int(self.config.get("block_size", 1024))

        while True:
            try:
                with sd.InputStream(samplerate=sample_rate, blocksize=block_size, channels=1, callback=self.audio_callback):
                    logger.info(f"Audio stream opened successfully at {sample_rate}Hz. Listening for double claps, finger snaps, or spoken 'Jarvis'...")
                    while True:
                        time.sleep(1)
            except sd.PortAudioError as pa_err:
                logger.warning(f"Audio stream issue (e.g. system sleep/wake or mic reset): {pa_err}. Retrying in 3 seconds...")
                time.sleep(3)
            except KeyboardInterrupt:
                logger.info("clap-jarvis stopped by user.")
                break
            except Exception as e:
                logger.warning(f"Audio stream error: {e}. Retrying connection in 3 seconds...", exc_info=True)
                time.sleep(3)


def main():
    parser = argparse.ArgumentParser(description="clap-jarvis double clap, finger snap, or 'Jarvis' wake-word daemon")
    parser.add_argument("--calibrate", action="store_true", help="Run 30-second live sensitivity calibration")
    args = parser.parse_args()

    config = load_config()

    if args.calibrate:
        run_calibration(config)
    else:
        daemon = ClapDaemon()
        daemon.run()


if __name__ == "__main__":
    main()
