#!/usr/bin/env python3

import sys
import time
import numpy as np
import sounddevice as sd
from config_manager import logger


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

        threshold_peak = float(config.get("threshold_peak", 0.18))
        threshold_snap_peak = float(config.get("threshold_snap_peak", 0.05))
        threshold_rms = float(config.get("threshold_rms", 0.002))
        min_crest_factor = float(config.get("min_crest_factor", 3.8))

        min_clap_crest = max(3.2, min_crest_factor * 0.85)
        is_clap = peak >= threshold_peak and rms >= threshold_rms and crest_factor >= min_clap_crest
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
