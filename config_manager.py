#!/usr/bin/env python3

import json
import logging
import os
import sys
from logging.handlers import RotatingFileHandler

# Default Fallback Configurations (optimized for precise snap/clap detection and human-like neural voice)
DEFAULT_CONFIG = {
    "threshold_peak": 0.18,         # Clap peak threshold
    "threshold_snap_peak": 0.05,    # Snap peak threshold (responsive to all 3 deliberate finger snaps)
    "min_crest_factor": 3.8,        # Sharp percussive transient crest factor (filters ambient noise & voice)
    "threshold_rms": 0.002,         # RMS energy floor
    "required_claps": 3,            # Requires 3 snaps or claps
    "window_seconds": 3.0,          # Window for 3 snaps/claps
    "cooldown_seconds": 4.0,        # Pause after trigger to prevent self-triggering from TTS
    "voice": "en-GB-RyanNeural",    # Ultra-realistic British Male Neural Voice (JARVIS)
    "enable_flight_check": True,
    "suppress_during_audio": True,   # Block trigger when audio is playing from any browser/player
    "suppress_during_meetings": False, # Block trigger when user is in a meeting (Zoom, Meet, Teams, FaceTime)
    "latitude": 23.23352,            # MP Nagar, Bhopal coordinates
    "longitude": 77.43257,
    "radius_km": 150.0,
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
    _logger = logging.getLogger("clap-jarvis")
    _logger.setLevel(logging.INFO)
    _logger.propagate = False

    if not _logger.handlers:
        log_dir = os.path.dirname(LOG_FILE)
        os.makedirs(log_dir, exist_ok=True)

        handler = RotatingFileHandler(LOG_FILE, maxBytes=2 * 1024 * 1024, backupCount=3)
        formatter = logging.Formatter("[%(asctime)s] [%(levelname)s] %(message)s", datefmt="%Y-%m-%d %H:%M:%S")
        handler.setFormatter(formatter)
        _logger.addHandler(handler)

        if sys.stdout.isatty():
            console_handler = logging.StreamHandler(sys.stdout)
            console_handler.setFormatter(formatter)
            _logger.addHandler(console_handler)

    return _logger


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
