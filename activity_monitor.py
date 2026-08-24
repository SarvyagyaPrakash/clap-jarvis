#!/usr/bin/env python3
"""macOS activity monitor to detect active audio/video playback, paused media differentiation, and active video conferencing meetings."""

import json
import os
import subprocess
import time
from typing import Tuple, Optional, Set

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
MEDIA_DETECTOR_BIN = os.path.join(SCRIPT_DIR, "media_detector")
MEDIA_DETECTOR_SWIFT = os.path.join(SCRIPT_DIR, "media_detector.swift")


def ensure_media_detector():
    """Ensures native MediaRemote detector binary is compiled and ready."""
    if not os.path.exists(MEDIA_DETECTOR_BIN) and os.path.exists(MEDIA_DETECTOR_SWIFT):
        try:
            subprocess.run(
                ["swiftc", "-O", MEDIA_DETECTOR_SWIFT, "-o", MEDIA_DETECTOR_BIN],
                timeout=6.0,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
        except Exception:
            pass


ensure_media_detector()


def get_running_process_basenames() -> Set[str]:
    """Retrieves lowercased basenames of all currently running processes."""
    try:
        out = subprocess.check_output(
            ["ps", "-ax", "-o", "comm="],
            universal_newlines=True,
            timeout=1.0
        )
        basenames = set()
        for line in out.splitlines():
            line = line.strip()
            if line:
                basenames.add(os.path.basename(line).lower())
        return basenames
    except Exception:
        return set()


def check_media_remote() -> Tuple[bool, Optional[str]]:
    """Queries macOS MediaRemote via native helper to detect if any audio/video is actively playing vs paused."""
    if not os.path.exists(MEDIA_DETECTOR_BIN):
        ensure_media_detector()

    if os.path.exists(MEDIA_DETECTOR_BIN):
        try:
            out = subprocess.check_output(
                [MEDIA_DETECTOR_BIN],
                universal_newlines=True,
                timeout=0.6
            ).strip()
            if out:
                data = json.loads(out)
                is_playing = bool(data.get("is_playing", False))
                rate = float(data.get("rate", 0.0))
                if is_playing or rate > 0.0:
                    title = (data.get("title") or "").strip()
                    artist = (data.get("artist") or "").strip()
                    if title and artist:
                        desc = f"{title} - {artist}"
                    elif title:
                        desc = title
                    else:
                        desc = "Media playing"
                    return True, f"Active media playback: \"{desc}\""
        except Exception:
            pass

    return False, None


def check_media_players(running_procs: Set[str]) -> Tuple[bool, Optional[str]]:
    """Checks desktop media players (Spotify, Apple Music, QuickTime Player, VLC); returns (True, details) only if actively playing."""
    # 1. Spotify
    if "spotify" in running_procs:
        try:
            out = subprocess.check_output(
                ["osascript", "-e", 'tell application "Spotify" to get player state as string'],
                universal_newlines=True,
                timeout=0.6
            ).strip().lower()
            if out == "playing":
                track_info = ""
                try:
                    track_info = subprocess.check_output(
                        ["osascript", "-e", 'tell application "Spotify" to return (get name of current track) & " by " & (get artist of current track)'],
                        universal_newlines=True,
                        timeout=0.5
                    ).strip()
                except Exception:
                    pass
                desc = f"Spotify ({track_info})" if track_info else "Spotify"
                return True, f"Media player playing: {desc}"
        except Exception:
            pass

    # 2. Apple Music
    if "music" in running_procs:
        try:
            out = subprocess.check_output(
                ["osascript", "-e", 'tell application "Music" to get player state as string'],
                universal_newlines=True,
                timeout=0.6
            ).strip().lower()
            if out == "playing":
                track_info = ""
                try:
                    track_info = subprocess.check_output(
                        ["osascript", "-e", 'tell application "Music" to return (get name of current track) & " by " & (get artist of current track)'],
                        universal_newlines=True,
                        timeout=0.5
                    ).strip()
                except Exception:
                    pass
                desc = f"Apple Music ({track_info})" if track_info else "Apple Music"
                return True, f"Media player playing: {desc}"
        except Exception:
            pass

    # 3. QuickTime Player
    if "quicktime player" in running_procs:
        try:
            out = subprocess.check_output(
                ["osascript", "-e", 'tell application "QuickTime Player" to return (exists (documents whose playing is true))'],
                universal_newlines=True,
                timeout=0.6
            ).strip().lower()
            if out == "true":
                return True, "Media player playing: QuickTime Player"
        except Exception:
            pass

    # 4. VLC
    if "vlc" in running_procs:
        try:
            out = subprocess.check_output(
                ["osascript", "-e", 'tell application "VLC" to if playing then return "true"'],
                universal_newlines=True,
                timeout=0.6
            ).strip().lower()
            if out == "true":
                return True, "Media player playing: VLC"
        except Exception:
            pass

    return False, None


def check_browser_media(running_procs: Set[str]) -> Tuple[bool, Optional[str]]:
    """Inspects tabs in running Chromium browsers (Brave, Chrome, Edge, Arc, Opera, Vivaldi) for active HTML5 media playback."""
    chromium_browsers = [
        ("brave browser", "Brave Browser"),
        ("google chrome", "Google Chrome"),
        ("microsoft edge", "Microsoft Edge"),
        ("arc", "Arc"),
        ("opera", "Opera"),
        ("vivaldi", "Vivaldi")
    ]

    for proc_key, app_title in chromium_browsers:
        if proc_key in running_procs:
            scpt = f"""
            tell application "{app_title}"
                set isPlaying to false
                set playingTitle to ""
                repeat with w in windows
                    repeat with t in tabs of w
                        try
                            tell t
                                set jsResult to (execute javascript "(() => {{ const media = Array.from(document.querySelectorAll(\x27video, audio\x27)); return media.some(m => !m.paused && !m.ended && m.currentTime > 0); }})()")
                            end tell
                            if jsResult is true or jsResult is "true" then
                                set isPlaying to true
                                set playingTitle to (title of t)
                                exit repeat
                            end if
                        end try
                    end repeat
                    if isPlaying then exit repeat
                end repeat
                return playingTitle
            end tell
            """
            try:
                res = subprocess.check_output(
                    ["osascript", "-e", scpt],
                    universal_newlines=True,
                    timeout=0.8
                ).strip()
                if res:
                    return True, f"Browser media playing in {app_title}: \"{res}\""
            except Exception:
                pass

    return False, None


def is_audio_playing(config: Optional[dict] = None) -> Tuple[bool, Optional[str]]:
    """Returns (True, reason) if any media player or browser tab is actively playing audio/video, else (False, None)."""
    if config and not config.get("suppress_during_audio", True):
        return False, None

    # 1. Native macOS MediaRemote check (covers YouTube in all browsers, Spotify, Apple Music, etc.)
    is_playing, desc = check_media_remote()
    if is_playing:
        return True, desc

    running_procs = get_running_process_basenames()

    # 2. Direct AppleScript media players check (Spotify, Music, QuickTime, VLC)
    is_playing, desc = check_media_players(running_procs)
    if is_playing:
        return True, desc

    # 3. Browser tab DOM media query check
    is_playing, desc = check_browser_media(running_procs)
    if is_playing:
        return True, desc

    return False, None


def check_video_conferencing_apps(running_procs: Set[str]) -> Tuple[bool, Optional[str]]:
    """Detects active video conferencing apps (Zoom, Google Meet, Microsoft Teams, FaceTime, Webex, etc.)."""
    # 1. Zoom
    if "zoom.us" in running_procs or "zoom.real.app" in running_procs:
        if "cpthost" in running_procs or "aomhost" in running_procs:
            return True, "Zoom meeting in progress (active media/screen engine)"
        try:
            out = subprocess.check_output(
                ["osascript", "-e", 'tell application "zoom.us" to return (name of every window)'],
                universal_newlines=True,
                timeout=0.6
            )
            if any(w in out.lower() for w in ["zoom meeting", "meeting", "webinar"]):
                return True, "Zoom meeting window active"
        except Exception:
            pass

    # 2. Google Meet in Chromium browser tabs
    chromium_browsers = [
        ("brave browser", "Brave Browser"),
        ("google chrome", "Google Chrome"),
        ("microsoft edge", "Microsoft Edge"),
        ("arc", "Arc"),
        ("opera", "Opera")
    ]
    for proc_key, app_title in chromium_browsers:
        if proc_key in running_procs:
            scpt = f"""
            tell application "{app_title}"
                set inMeet to false
                set meetTitle to ""
                repeat with w in windows
                    repeat with t in tabs of w
                        try
                            set tabUrl to (URL of t)
                            if tabUrl contains "meet.google.com/" and not (tabUrl ends with "meet.google.com/") and not (tabUrl contains "meet.google.com/landing") then
                                set inMeet to true
                                set meetTitle to (title of t)
                                exit repeat
                            end if
                        end try
                    end repeat
                    if inMeet then exit repeat
                end repeat
                return meetTitle
            end tell
            """
            try:
                res = subprocess.check_output(
                    ["osascript", "-e", scpt],
                    universal_newlines=True,
                    timeout=0.8
                ).strip()
                if res:
                    return True, f"Google Meet in progress ({app_title}): \"{res}\""
            except Exception:
                pass

    # 3. Microsoft Teams
    if "msteams" in running_procs or "microsoft teams" in running_procs:
        if any(p in running_procs for p in ["teams call", "teamsmeeting", "msteams helper (renderer)"]):
            return True, "Microsoft Teams call in progress"

    # 4. FaceTime
    if "facetime" in running_procs and "avconferenced" in running_procs:
        return True, "FaceTime call in progress"

    # 5. Cisco Webex
    if any(w in running_procs for w in ["cisco webex meetings", "webex", "ciscocollabhost", "meetingcenter"]):
        return True, "Cisco Webex meeting in progress"

    # 6. Discord voice / call
    if "discord" in running_procs:
        try:
            out = subprocess.check_output(["pmset", "-g", "assertions"], universal_newlines=True, timeout=0.6)
            if "discord" in out.lower() and ("audio-in" in out.lower() or "audio-out" in out.lower()):
                return True, "Discord voice call in progress"
        except Exception:
            pass

    # 7. Slack Huddle / Call
    if "slack" in running_procs:
        try:
            out = subprocess.check_output(["pmset", "-g", "assertions"], universal_newlines=True, timeout=0.6)
            if "slack" in out.lower() and ("audio-in" in out.lower() or "audio-out" in out.lower()):
                return True, "Slack huddle/call in progress"
        except Exception:
            pass

    # 8. Other meeting apps
    other_meeting_apps = {
        "skype": "Skype call",
        "tencentmeeting": "Tencent Meeting",
        "voov meeting": "VooV Meeting",
        "feishu": "Feishu meeting",
        "lark": "Lark meeting",
        "gotomeeting": "GoToMeeting",
        "bluejeans": "BlueJeans meeting",
        "around": "Around video call",
        "tuple": "Tuple screen-sharing call"
    }
    for proc_name, label in other_meeting_apps.items():
        if proc_name in running_procs:
            return True, f"{label} active"

    return False, None


def is_in_meeting(config: Optional[dict] = None) -> Tuple[bool, Optional[str]]:
    """Returns (True, reason) if the user is in an active video conference (Zoom, Meet, Teams, etc.), else (False, None)."""
    if config and not config.get("suppress_during_meetings", True):
        return False, None

    running_procs = get_running_process_basenames()
    return check_video_conferencing_apps(running_procs)


def check_trigger_permitted(config: Optional[dict] = None) -> Tuple[bool, Optional[str]]:
    """Evaluates whether a snap/clap/wake-word trigger is permitted right now; returns (True, None) or (False, suppression_reason)."""
    # 1. Audio Playback Check
    audio_playing, audio_reason = is_audio_playing(config)
    if audio_playing:
        return False, f"Audio currently playing ({audio_reason})"

    # 2. Meeting Check
    in_meeting, meeting_reason = is_in_meeting(config)
    if in_meeting:
        return False, f"User in meeting ({meeting_reason})"

    return True, None


if __name__ == "__main__":
    print("=" * 65)
    print("  ACTIVITY & AUDIO MONITOR STATUS CHECK")
    print("=" * 65)
    t0 = time.time()
    permitted, reason = check_trigger_permitted()
    elapsed_ms = (time.time() - t0) * 1000

    audio_active, audio_desc = is_audio_playing()
    meeting_active, meeting_desc = is_in_meeting()

    print(f"Elapsed evaluation time: {elapsed_ms:.1f}ms")
    print(f"Audio Playing:           {audio_active} ({audio_desc or 'None'})")
    print(f"In Meeting:              {meeting_active} ({meeting_desc or 'None'})")
    print(f"Trigger Permitted:       {permitted}")
    if not permitted:
        print(f"Suppression Reason:      {reason}")
    print("=" * 65)
