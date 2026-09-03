#!/usr/bin/env python3

import argparse
import random
import threading
import time
import numpy as np
import sounddevice as sd

# Internal modular imports
from config_manager import (
    DEFAULT_CONFIG,
    DEFAULT_PHRASES,
    LOG_FILE,
    PROJECT_DIR,
    CONFIG_PATH,
    PHRASES_PATH,
    logger,
    setup_logger,
    load_config,
    load_phrases
)
from flight_tracker import (
    AIRPORT_NAMES,
    AIRLINE_NAMES,
    format_airport_name,
    format_flight_spoken,
    haversine_km,
    get_flight_route,
    check_overhead_flight
)
from speech_engine import (
    open_or_refresh_flightradar_tab,
    is_flightradar_tab_open,
    play_audio_process_with_tab_monitor,
    speak_and_launch
)
from calibration import run_calibration

try:
    from activity_monitor import check_trigger_permitted, is_audio_playing, is_in_meeting
except ImportError:
    from .activity_monitor import check_trigger_permitted, is_audio_playing, is_in_meeting


def detect_finger_snap(indata, sample_rate, config):
    """
    Dedicated acoustic finger snap detector.
    Combines time-domain transient analysis (Peak, RMS, Crest Factor) and
    frequency-domain FFT spectral analysis (High Snap Band 2000-8000Hz vs Low Band 100-1500Hz, and Spectral Centroid).
    Rejects speech, speech hallucinations, coughs, hand claps, typing, and ambient room noise.
    """
    peak = float(np.max(np.abs(indata)))
    rms = float(np.sqrt(np.mean(indata ** 2)))
    if rms < 1e-6:
        return False, {"peak": peak, "rms": rms, "crest": 0.0, "ratio": 0.0, "centroid": 0.0}

    crest_factor = peak / rms

    threshold_snap_peak = float(config.get("threshold_snap_peak", config.get("threshold_peak", 0.08)))
    min_crest_factor = float(config.get("min_crest_factor", 4.0))
    max_snap_rms = float(config.get("max_snap_rms", 0.08))
    min_snap_ratio = float(config.get("min_snap_ratio", 1.1))
    min_spectral_centroid = float(config.get("min_spectral_centroid", 2200.0))

    # Fast time-domain check: must be a sharp transient with low continuous energy
    if peak < threshold_snap_peak or crest_factor < min_crest_factor or rms > max_snap_rms:
        return False, {"peak": peak, "rms": rms, "crest": crest_factor, "ratio": 0.0, "centroid": 0.0}

    # Frequency-domain spectral analysis
    signal = indata.flatten()
    fft_vals = np.abs(np.fft.rfft(signal))
    freqs = np.fft.rfftfreq(len(signal), d=1.0 / sample_rate)

    low_mask = (freqs >= 100) & (freqs < 1500)
    snap_mask = (freqs >= 2000) & (freqs <= 8000)

    low_energy = float(np.sum(fft_vals[low_mask] ** 2))
    snap_energy = float(np.sum(fft_vals[snap_mask] ** 2))
    snap_ratio = snap_energy / (low_energy + 1e-6)

    total_mag = float(np.sum(fft_vals))
    spectral_centroid = float(np.sum(freqs * fft_vals) / (total_mag + 1e-6))

    metrics = {
        "peak": peak,
        "rms": rms,
        "crest": crest_factor,
        "ratio": snap_ratio,
        "centroid": spectral_centroid
    }

    if snap_ratio >= min_snap_ratio and spectral_centroid >= min_spectral_centroid:
        return True, metrics

    return False, metrics


class SnapDaemon:
    def __init__(self):
        self.config = load_config()
        self.phrases = load_phrases()
        self.snap_timestamps = []
        self.cooldown_until = 0.0
        self.last_snap_time = 0.0
        self.min_inter_snap_gap = 0.15
        self.is_speaking = False
        self.lock = threading.Lock()

        # Full-cycle shuffle deck to guarantee every phrase is spoken at least once before repeating
        self.phrase_deck = []
        self.last_spoken = None

    def on_speech_complete(self):
        """Callback invoked when JARVIS TTS audio playback finishes."""
        cooldown = float(self.config.get("cooldown_seconds", 3.5))
        self.cooldown_until = time.time() + cooldown
        self.is_speaking = False
        self.snap_timestamps.clear()
        logger.info(f"Speech complete. Snap listener cooldown active for {cooldown}s.")

    def audio_callback(self, indata, frames, time_info, status):
        """Audio streaming callback executed for every frame chunk."""
        try:
            if status:
                logger.warning(f"Audio callback status: {status}")

            now = time.time()

            # Ignore all audio while speaking or during cooldown (prevents TTS self-triggering)
            if self.is_speaking or now < self.cooldown_until:
                self.snap_timestamps.clear()
                return

            sample_rate = int(self.config.get("sample_rate", 44100))
            is_snap, metrics = detect_finger_snap(indata, sample_rate, self.config)

            if is_snap:
                if now - self.last_snap_time >= self.min_inter_snap_gap:
                    self.last_snap_time = now
                    self.snap_timestamps.append(now)
                    logger.info(
                        f"🤌 Finger Snap detected! Peak: {metrics['peak']:.3f}, Crest: {metrics['crest']:.1f}, "
                        f"Ratio: {metrics['ratio']:.2f}x, Centroid: {metrics['centroid']:.0f}Hz"
                    )

                    window_seconds = float(self.config.get("window_seconds", 2.5))
                    required_snaps = int(self.config.get("required_snaps", 2))
                    self.snap_timestamps = [t for t in self.snap_timestamps if now - t <= window_seconds]

                    if len(self.snap_timestamps) >= required_snaps:
                        if not self.is_speaking:
                            logger.info(f">>> TRIGGER DETECTED: {required_snaps} finger snaps within {window_seconds}s window! <<<")
                            self.snap_timestamps.clear()
                            threading.Thread(target=self.handle_trigger, daemon=True).start()
                            return
        except Exception as e:
            logger.error(f"Error inside audio callback: {e}", exc_info=True)

    def get_random_phrase(self):
        """Selects a phrase via full-cycle shuffle deck so every phrase is spoken exactly once before any repeats."""
        phrases = load_phrases()
        if not phrases:
            return "At your service, sir."

        # Keep deck synchronized with any file updates on disk
        self.phrase_deck = [p for p in self.phrase_deck if p in phrases]

        # If deck is exhausted, shuffle all phrases into a new cycle
        if not self.phrase_deck:
            new_deck = phrases.copy()
            random.shuffle(new_deck)

            # Prevent back-to-back duplicate across cycle boundary
            if len(new_deck) > 1 and new_deck[0] == self.last_spoken:
                new_deck[0], new_deck[-1] = new_deck[-1], new_deck[0]

            self.phrase_deck = new_deck

        chosen = self.phrase_deck.pop(0)
        self.last_spoken = chosen
        return chosen

    def handle_trigger(self):
        """Handles response logic upon finger snap trigger."""
        with self.lock:
            if self.is_speaking:
                logger.info("Trigger ignored: JARVIS is already actively speaking.")
                return
            self.is_speaking = True

        self.config = load_config()

        # Step 1: Intelligent Audio Playback & Meeting Activity Guard
        is_permitted, suppression_reason = check_trigger_permitted(self.config)
        if not is_permitted:
            logger.info(f"🚫 [TRIGGER SUPPRESSED] {suppression_reason}")
            self.is_speaking = False
            self.cooldown_until = time.time() + 2.0
            return

        logger.info("⚡ [TRIGGER ALLOWED] System clear (no audio playing, no meeting active). Executing JARVIS response...")

        flight_info = None
        spoken_line = None

        # 1. Flight Overhead Check if enabled
        if self.config.get("enable_flight_check", True):
            flight_info = check_overhead_flight(self.config)
            if flight_info:
                spoken_line = flight_info.get("spoken_text")

        # 2. Fallback to random phrase from phrases.json if no flight found
        if not spoken_line:
            spoken_line = self.get_random_phrase()

        # Enforce en-GB-RyanNeural as the exclusive voice
        voice = "en-GB-RyanNeural"
        speak_and_launch(spoken_line, voice, flight_data=flight_info, on_done=self.on_speech_complete)

    def run(self):
        """Starts main loop listening continuously for finger snaps with auto-reconnect on sleep/wake."""
        logger.info("Starting JARVIS daemon (strictly tuned for finger snaps)...")
        sample_rate = int(self.config.get("sample_rate", 44100))
        block_size = int(self.config.get("block_size", 1024))

        while True:
            try:
                with sd.InputStream(samplerate=sample_rate, blocksize=block_size, channels=1, callback=self.audio_callback):
                    logger.info(f"Audio stream opened successfully at {sample_rate}Hz. Listening exclusively for finger snaps...")
                    while True:
                        time.sleep(1)
            except sd.PortAudioError as pa_err:
                logger.warning(f"Audio stream issue (e.g. system sleep/wake or mic reset): {pa_err}. Retrying in 3 seconds...")
                time.sleep(3)
            except KeyboardInterrupt:
                logger.info("JARVIS snap daemon stopped by user.")
                break
            except Exception as e:
                logger.warning(f"Audio stream error: {e}. Retrying connection in 3 seconds...", exc_info=True)
                time.sleep(3)


# Backward compatibility alias
ClapDaemon = SnapDaemon


def main():
    parser = argparse.ArgumentParser(description="JARVIS finger snap activation daemon")
    parser.add_argument("--calibrate", action="store_true", help="Run live sensitivity and frequency calibration for finger snaps")
    parser.add_argument("--status", action="store_true", help="Check live audio playback and meeting activity status")
    args = parser.parse_args()

    config = load_config()

    if args.status:
        print("=" * 65)
        print("  JARVIS SNAP ACTIVITY & AUDIO STATUS CHECK")
        print("=" * 65)
        permitted, reason = check_trigger_permitted(config)
        audio_playing, audio_desc = is_audio_playing(config)
        in_meeting, meeting_desc = is_in_meeting(config)
        print(f"Audio Playing:     {audio_playing} ({audio_desc or 'None'})")
        print(f"In Meeting:        {in_meeting} ({meeting_desc or 'None'})")
        print(f"Trigger Permitted: {permitted}")
        if not permitted:
            print(f"Block Reason:      {reason}")
        print("=" * 65)
    elif args.calibrate:
        run_calibration(config)
    else:
        daemon = SnapDaemon()
        daemon.run()


if __name__ == "__main__":
    main()
