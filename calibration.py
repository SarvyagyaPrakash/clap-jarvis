#!/usr/bin/env python3

import sys
import time
import numpy as np
import sounddevice as sd
from config_manager import logger


def run_calibration(config):
    """Runs a 30-second calibration mode printing live peak, Crest Factor, Snap Frequency Ratio, and Centroid levels."""
    print("=" * 85)
    print("  JARVIS FINGER SNAP CALIBRATION (LIVE ACOUSTIC & SPECTRAL MONITOR)")
    print("=" * 85)
    print("Snap your fingers firmly near your Mac. The detector checks:")
    print(" - Peak amplitude (impulse intensity)")
    print(" - Crest factor (transient sharpness)")
    print(" - High-to-Low Ratio (2-8kHz snap resonance vs <1.5kHz speech/ambient band)")
    print(" - Spectral Centroid (frequency center of mass in Hz)")
    print("\nPress Ctrl+C at any time to exit calibration.\n")

    sample_rate = int(config.get("sample_rate", 44100))
    block_size = int(config.get("block_size", 1024))

    threshold_snap_peak = float(config.get("threshold_snap_peak", config.get("threshold_peak", 0.08)))
    min_crest_factor = float(config.get("min_crest_factor", 4.0))
    max_snap_rms = float(config.get("max_snap_rms", 0.08))
    min_snap_ratio = float(config.get("min_snap_ratio", 1.1))
    min_spectral_centroid = float(config.get("min_spectral_centroid", 2200.0))

    def calibrate_callback(indata, frames, time_info, status):
        if status:
            logger.warning(f"Audio status issue: {status}")

        peak = float(np.max(np.abs(indata)))
        rms = float(np.sqrt(np.mean(indata ** 2)))
        crest_factor = peak / (rms + 1e-6)

        # FFT spectral analysis
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

        is_snap = (
            peak >= threshold_snap_peak and
            crest_factor >= min_crest_factor and
            rms <= max_snap_rms and
            snap_ratio >= min_snap_ratio and
            spectral_centroid >= min_spectral_centroid
        )

        event_str = "               "
        if is_snap:
            event_str = "🤌 [SNAP DETECTED!]"
        elif peak >= threshold_snap_peak and crest_factor >= min_crest_factor:
            if snap_ratio < min_snap_ratio or spectral_centroid < min_spectral_centroid:
                event_str = "❌ [REJECTED: NOT A SNAP]"

        bar_len = int(min(peak, 1.0) * 20)
        bar = "#" * bar_len + " " * (20 - bar_len)
        sys.stdout.write(
            f"\rPk: {peak:.3f} [{bar}] | Cr: {crest_factor:4.1f} | Ratio: {snap_ratio:4.1f}x | Centroid: {spectral_centroid:4.0f}Hz | {event_str}"
        )
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
