#!/usr/bin/env python3

import argparse
import random
import threading
import time
import numpy as np
import sounddevice as sd
import speech_recognition as sr

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


class ClapDaemon:
    def __init__(self):
        self.config = load_config()
        self.phrases = load_phrases()
        self.clap_timestamps = []
        self.cooldown_until = 0.0
        self.last_clap_time = 0.0
        self.min_inter_clap_gap = 0.10
        self.is_speaking = False
        self.lock = threading.Lock()

        # Audio speech buffer for "Jarvis" wake word speech recognition
        self.speech_chunks = []
        self.speech_recognizer = sr.Recognizer()
        self.is_recognizing = False

        # Full-cycle shuffle deck to guarantee every phrase is spoken at least once before repeating
        self.phrase_deck = []
        self.last_spoken = None

    def on_speech_complete(self):
        """Callback invoked when JARVIS TTS audio playback finishes."""
        cooldown = float(self.config.get("cooldown_seconds", 4.0))
        self.cooldown_until = time.time() + cooldown
        self.is_speaking = False
        self.clap_timestamps.clear()
        self.speech_chunks.clear()
        logger.info(f"Speech complete. Buffer cooldown active for {cooldown}s.")

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
                if not self.is_speaking and now >= self.cooldown_until:
                    logger.info(">>> TRIGGER DETECTED: Spoken wake word 'Jarvis'! <<<")
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

            # Ignore all audio while speaking or during cooldown (prevents overlapping speech and TTS self-triggering)
            if self.is_speaking or now < self.cooldown_until:
                self.clap_timestamps.clear()
                self.speech_chunks.clear()
                return

            peak = float(np.max(np.abs(indata)))
            rms = float(np.sqrt(np.mean(indata ** 2)))
            crest_factor = peak / (rms + 1e-6)

            threshold_peak = float(self.config.get("threshold_peak", 0.18))
            threshold_snap_peak = float(self.config.get("threshold_snap_peak", 0.05))
            threshold_rms = float(self.config.get("threshold_rms", 0.002))
            min_crest_factor = float(self.config.get("min_crest_factor", 3.8))

            # 1. Check Hand Clap and Finger Snap transients (both require sharp crest factors to reject speech and noise)
            min_clap_crest = max(3.2, min_crest_factor * 0.85)
            is_clap = peak >= threshold_peak and rms >= threshold_rms and crest_factor >= min_clap_crest
            is_snap = peak >= threshold_snap_peak and crest_factor >= min_crest_factor

            if is_clap or is_snap:
                if now - self.last_clap_time >= self.min_inter_clap_gap:
                    self.last_clap_time = now
                    self.clap_timestamps.append(now)
                    event_type = "Hand Clap" if is_clap else "Finger Snap"
                    logger.info(f"{event_type} detected! Peak: {peak:.3f}, RMS: {rms:.3f}, Crest: {crest_factor:.1f}")

                    window_seconds = float(self.config.get("window_seconds", 3.0))
                    required_claps = int(self.config.get("required_claps", 3))
                    self.clap_timestamps = [t for t in self.clap_timestamps if now - t <= window_seconds]

                    if len(self.clap_timestamps) >= required_claps:
                        if not self.is_speaking:
                            logger.info(f">>> TRIGGER DETECTED: {required_claps} claps/snaps within window! <<<")
                            self.clap_timestamps.clear()
                            self.speech_chunks.clear()
                            threading.Thread(target=self.handle_trigger, daemon=True).start()
                            return

            # 2. Accumulate continuous speech audio for "Jarvis" wake word recognition
            if self.config.get("enable_jarvis_wake_word", False):
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
        """Handles response logic upon trigger (double clap, double snap, or spoken 'Jarvis')."""
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

        voice = self.config.get("voice", "en-GB-RyanNeural")
        speak_and_launch(spoken_line, voice, flight_data=flight_info, on_done=self.on_speech_complete)

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
    parser.add_argument("--status", action="store_true", help="Check live audio playback and meeting activity status")
    args = parser.parse_args()

    config = load_config()

    if args.status:
        print("=" * 65)
        print("  CLAP-JARVIS ACTIVITY & AUDIO STATUS CHECK")
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
        daemon = ClapDaemon()
        daemon.run()


if __name__ == "__main__":
    main()
