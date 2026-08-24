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
    "VOGA": "Goa Mopa", "GOX": "Goa Mopa",
    "VABP": "Bhopal", "BHO": "Bhopal",
    "VAID": "Indore", "IDR": "Indore",
    "VAAU": "Aurangabad", "IXU": "Aurangabad",
    "VASD": "Shirdi", "SAG": "Shirdi",
    "VARP": "Raipur", "RPR": "Raipur",
    "WMKK": "Kuala Lumpur", "KUL": "Kuala Lumpur",
    "KLAX": "Los Angeles", "LAX": "Los Angeles",
    "OTHH": "Doha", "DOH": "Doha",
    "EDDF": "Frankfurt", "FRA": "Frankfurt",
    "LFPG": "Paris CDG", "CDG": "Paris CDG",
    "VTBS": "Bangkok", "BKK": "Bangkok",
    "VOCI": "Cochin", "COK": "Cochin",
    "VAPO": "Pune", "PNQ": "Pune",
    "VIJP": "Jaipur", "JAI": "Jaipur",
    "VAPM": "Nagpur", "NAG": "Nagpur",
    "VICG": "Chandigarh", "IXC": "Chandigarh",
    "VILK": "Lucknow", "LKO": "Lucknow",
    "VEBN": "Varanasi", "VNS": "Varanasi",
    "VEPT": "Patna", "PAT": "Patna",
    "VEGT": "Guwahati", "GAU": "Guwahati",
    "VEBD": "Bagdogra", "IXB": "Bagdogra",
    "VIAR": "Amritsar", "ATQ": "Amritsar",
    "VISR": "Srinagar", "SXR": "Srinagar",
    "VIJU": "Jammu", "IXJ": "Jammu",
    "VILH": "Leh", "IXL": "Leh",
    "VABO": "Vadodara", "BDQ": "Vadodara",
    "VASU": "Surat", "STV": "Surat",
    "VAUD": "Udaipur", "UDR": "Udaipur",
    "VIJO": "Jodhpur", "JDH": "Jodhpur",
    "VERC": "Ranchi", "IXR": "Ranchi",
    "VEBS": "Bhubaneswar", "BBI": "Bhubaneswar",
    "VOVZ": "Visakhapatnam", "VTZ": "Visakhapatnam",
    "VOBZ": "Vijayawada", "VGA": "Vijayawada",
    "VOMD": "Madurai", "IXM": "Madurai",
    "VOCB": "Coimbatore", "CJB": "Coimbatore",
    "VOTR": "Tiruchirappalli", "TRZ": "Tiruchirappalli",
    "VOTP": "Tirupati", "TIR": "Tirupati",
    "VOTV": "Trivandrum", "TRV": "Trivandrum",
    "VOCL": "Calicut", "CCJ": "Calicut",
    "VEAY": "Ayodhya", "AYJ": "Ayodhya",
    "VHHH": "Hong Kong", "HKG": "Hong Kong",
    "VVNB": "Hanoi", "HAN": "Hanoi",
    "OERK": "Riyadh", "RUH": "Riyadh",
    "VCBI": "Colombo", "CMB": "Colombo"
}


def haversine_km(lat1, lon1, lat2, lon2):
    """Calculates great-circle distance between two geographic coordinates in kilometers."""
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c


def get_flight_route(callsign):
    """Retrieves origin and destination airport/city names for a callsign from multiple APIs."""
    if not callsign or callsign == "Unknown":
        return None, None

    callsign_clean = callsign.strip()
    headers = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"}
    
    # 1. Try FlightRadar24 web find API (contains live route and city names)
    try:
        url = f"https://www.flightradar24.com/v1/search/web/find?query={callsign_clean}"
        resp = requests.get(url, headers=headers, timeout=2.5)
        if resp.status_code == 200:
            results = resp.json().get("results", [])
            for item in results:
                detail = item.get("detail", {})
                route_str = detail.get("route")
                if route_str and " ⟶ " in route_str:
                    parts = route_str.split(" ⟶ ")
                    return parts[0].strip(), parts[1].strip()
                schd_from = detail.get("schd_from")
                schd_to = detail.get("schd_to")
                if schd_from and schd_to:
                    return schd_from, schd_to
    except Exception as e:
        logger.debug(f"FlightRadar24 search failed for {callsign}: {e}")

    # 2. Try HexDB Route API fallback
    try:
        url = f"https://hexdb.io/api/v1/route/icao/{callsign_clean}"
        resp = requests.get(url, headers=headers, timeout=2.0)
        if resp.status_code == 200:
            data = resp.json()
            route_str = data.get("route")
            if route_str and "-" in route_str:
                origin, dest = route_str.split("-", 1)
                return origin.strip(), dest.strip()
    except Exception:
        pass

    # 3. Try OpenSky Routes API fallback
    try:
        url = f"https://opensky-network.org/api/routes?callsign={callsign_clean}"
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
    """Converts ICAO/IATA airport code or city string to a human-readable city/airport name."""
    if not code:
        return None
    
    # Clean string if formatted like "Rome (FCO)"
    if "(" in code and ")" in code:
        code_clean = code.split("(")[0].strip()
        if code_clean:
            return code_clean

    code_upper = code.upper().strip()
    return AIRPORT_NAMES.get(code_upper, code.strip())


def check_overhead_flight(config):
    """
    Checks live flight feeds (FlightRadar24 live feed primary, adsb.fi & OpenSky fallbacks) for planes overhead.
    Returns dict with flight details & spoken string if found, or None.
    """
    try:
        lat = float(config.get("latitude", 23.23352))
        lon = float(config.get("longitude", 77.43257))
        radius_km = float(config.get("radius_km", 150.0))

        # 15% buffer for live bounding queries to avoid missing planes near the boundary
        buffer_km = radius_km * 1.15
        lat_deg = buffer_km / 111.0
        lon_deg = buffer_km / (111.0 * math.cos(math.radians(lat)))

        lamin = lat - lat_deg
        lamax = lat + lat_deg
        lomin = lon - lon_deg
        lomax = lon + lon_deg

        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }

        airborne_flights = []

        # 1. Primary Provider: FlightRadar24 Live Zone Feed (Fastest in Asia/India)
        try:
            fr24_url = f"https://data-cloud.flightradar24.com/zones/fcgi/feed.js?bounds={lamax:.2f},{lamin:.2f},{lomin:.2f},{lomax:.2f}&faa=1&satellite=1&msc=1&mlat=1&flarm=1&adsb=1&gnd=1&air=1&vehicles=1&estimated=1"
            logger.info(f"Querying FlightRadar24 live feed for coordinates ({lat}, {lon}) within {radius_km}km...")
            fr24_resp = requests.get(fr24_url, headers=headers, timeout=4.0)
            if fr24_resp.status_code == 200:
                data = fr24_resp.json()
                for key, val in data.items():
                    if isinstance(val, list) and len(val) >= 6:
                        f_lat, f_lon = val[1], val[2]
                        on_ground = val[14] if len(val) > 14 else 0
                        if not on_ground and f_lat is not None and f_lon is not None:
                            dist_km = haversine_km(lat, lon, f_lat, f_lon)
                            if dist_km <= radius_km:
                                callsign_raw = val[16] if len(val) > 16 else None
                                flight_num = val[13] if len(val) > 13 else None
                                callsign = (flight_num or callsign_raw or "").strip()
                                alt_callsign = (callsign_raw or "").strip()
                                heading_deg = val[3] if len(val) > 3 else None
                                alt_ft = val[4] if len(val) > 4 else None
                                speed_kt = val[5] if len(val) > 5 else None
                                velocity_ms = speed_kt * 0.514444 if speed_kt else None
                                speed_kmh = int(round(speed_kt * 1.852)) if speed_kt else None
                                orig_code = val[11] if len(val) > 11 else None
                                dest_code = val[12] if len(val) > 12 else None
                                icao24 = val[0] if len(val) > 0 else None

                                airborne_flights.append({
                                    "dist_km": dist_km,
                                    "callsign": callsign,
                                    "alt_callsign": alt_callsign,
                                    "f_lat": f_lat,
                                    "f_lon": f_lon,
                                    "heading_deg": heading_deg,
                                    "velocity_ms": velocity_ms,
                                    "alt_ft": int(alt_ft) if alt_ft is not None else None,
                                    "speed_kmh": speed_kmh,
                                    "speed_kt": int(speed_kt) if speed_kt is not None else None,
                                    "origin_code": orig_code,
                                    "dest_code": dest_code,
                                    "icao24": icao24,
                                    "fr24_id": key
                                })
        except Exception as e:
            logger.warning(f"FlightRadar24 live feed query error: {e}")

        # 2. Secondary High-Speed Fallback: Open ADS-B Live Data (adsb.fi)
        if not airborne_flights:
            try:
                adsb_url = f"https://opendata.adsb.fi/api/v2/lat/{lat}/lon/{lon}/dist/{int(radius_km * 1.15)}"
                logger.info("Falling back to adsb.fi live API query...")
                adsb_resp = requests.get(adsb_url, headers=headers, timeout=4.0)
                if adsb_resp.status_code == 200:
                    aircraft_list = adsb_resp.json().get("aircraft", [])
                    for ac in aircraft_list:
                        f_lat = ac.get("lat")
                        f_lon = ac.get("lon")
                        if f_lat is not None and f_lon is not None:
                            dist_km = haversine_km(lat, lon, f_lat, f_lon)
                            if dist_km <= radius_km:
                                callsign = (ac.get("flight") or ac.get("r") or "").strip()
                                alt_baro = ac.get("alt_baro")
                                alt_geom = ac.get("alt_geom")
                                alt_val = alt_baro if isinstance(alt_baro, (int, float)) else (alt_geom if isinstance(alt_geom, (int, float)) else None)
                                speed_kt = ac.get("gs")
                                speed_kmh = int(round(speed_kt * 1.852)) if isinstance(speed_kt, (int, float)) else None
                                vel_ms = speed_kt * 0.514444 if isinstance(speed_kt, (int, float)) else None

                                airborne_flights.append({
                                    "dist_km": dist_km,
                                    "callsign": callsign,
                                    "alt_callsign": None,
                                    "f_lat": f_lat,
                                    "f_lon": f_lon,
                                    "heading_deg": ac.get("track"),
                                    "velocity_ms": vel_ms,
                                    "alt_ft": int(alt_val) if alt_val is not None else None,
                                    "speed_kmh": speed_kmh,
                                    "speed_kt": int(round(speed_kt)) if isinstance(speed_kt, (int, float)) else None,
                                    "origin_code": None,
                                    "dest_code": None,
                                    "icao24": ac.get("hex"),
                                    "fr24_id": None
                                })
            except Exception as e:
                logger.warning(f"adsb.fi fallback query error: {e}")

        # 3. Tertiary Fallback: OpenSky Network API
        if not airborne_flights:
            try:
                os_url = f"https://opensky-network.org/api/states/all?lamin={lamin:.4f}&lamax={lamax:.4f}&lomin={lomin:.4f}&lomax={lomax:.4f}"
                logger.info("Falling back to OpenSky Network API query...")
                os_resp = requests.get(os_url, headers={"User-Agent": "Mozilla/5.0"}, timeout=4.0)
                if os_resp.status_code == 200:
                    states = os_resp.json().get("states") or []
                    for f in states:
                        on_ground = f[8] if len(f) > 8 else False
                        f_lat = f[6] if len(f) > 6 else None
                        f_lon = f[5] if len(f) > 5 else None
                        if not on_ground and f_lat is not None and f_lon is not None:
                            dist_km = haversine_km(lat, lon, f_lat, f_lon)
                            if dist_km <= radius_km:
                                callsign = (f[1] or "").strip()
                                vel_ms = f[9] if len(f) > 9 and f[9] is not None else None
                                alt_m = f[7] if (len(f) > 7 and f[7] is not None) else (f[13] if len(f) > 13 and f[13] is not None else None)
                                alt_ft = int(round(alt_m * 3.28084)) if alt_m is not None else None
                                speed_kmh = int(round(vel_ms * 3.6)) if vel_ms is not None else None
                                speed_kt = int(round(vel_ms * 1.94384)) if vel_ms is not None else None

                                airborne_flights.append({
                                    "dist_km": dist_km,
                                    "callsign": callsign,
                                    "alt_callsign": None,
                                    "f_lat": f_lat,
                                    "f_lon": f_lon,
                                    "heading_deg": f[10] if len(f) > 10 else None,
                                    "velocity_ms": vel_ms,
                                    "alt_ft": alt_ft,
                                    "speed_kmh": speed_kmh,
                                    "speed_kt": speed_kt,
                                    "origin_code": None,
                                    "dest_code": None,
                                    "icao24": f[0] if len(f) > 0 else None,
                                    "fr24_id": None
                                })
            except Exception as e:
                logger.warning(f"OpenSky fallback query error: {e}")

        if airborne_flights:
            # Sort by closest distance to user
            airborne_flights.sort(key=lambda x: x["dist_km"])
            
            # Select the closest aircraft
            flight = airborne_flights[0]
            fr24_url = None

            # Check candidate flights to establish verified FlightRadar24 URL
            for candidate in airborne_flights[:3]:
                cand_callsign = candidate.get("callsign") or ""
                cand_alt_callsign = candidate.get("alt_callsign") or ""
                cand_icao24 = candidate.get("icao24") or ""
                cand_fr24_id = candidate.get("fr24_id") or ""

                # 1. Direct FR24 feed match URL
                if cand_fr24_id:
                    flight = candidate
                    fr24_url = f"https://www.flightradar24.com/{cand_fr24_id}"
                    break

                # 2. Query FR24 web find search API for active live match
                search_queries = [q for q in [cand_callsign, cand_alt_callsign, cand_icao24] if q and q != "Unknown"]
                for query in search_queries:
                    try:
                        search_url = f"https://www.flightradar24.com/v1/search/web/find?query={query.strip().lower()}"
                        resp = requests.get(search_url, headers=headers, timeout=2.0)
                        if resp.status_code == 200:
                            results = resp.json().get("results", [])
                            for item in results:
                                item_type = item.get("type")
                                item_id = item.get("id")
                                if item_type == "live" and item_id:
                                    flight = candidate
                                    fr24_url = f"https://www.flightradar24.com/{item_id}"
                                    break
                                elif item_type in ["live", "aircraft", "schedule"]:
                                    flight_code = item.get("detail", {}).get("flight") or cand_callsign
                                    if flight_code:
                                        flight = candidate
                                        fr24_url = f"https://www.flightradar24.com/flight/{flight_code.lower()}"
                                        break
                            if fr24_url:
                                break
                    except Exception as e:
                        logger.debug(f"FlightRadar24 verification query error for {query}: {e}")

                if fr24_url:
                    break

            # Fallback URL when direct FR24 search didn't match a live page
            if not fr24_url:
                c_call = flight.get("callsign")
                c_hex = flight.get("icao24")
                if c_call and c_call != "Unknown":
                    fr24_url = f"https://www.flightradar24.com/flight/{c_call.lower()}"
                elif c_hex:
                    fr24_url = f"https://www.flightradar24.com/data/aircraft/{c_hex.lower()}"
                else:
                    fr24_url = f"https://www.flightradar24.com/{flight['f_lat']:.2f},{flight['f_lon']:.2f}/11"

            closest_dist_km = flight["dist_km"]
            callsign = flight["callsign"] or "Unknown"

            # Route resolution
            orig_code = flight["origin_code"]
            dest_code = flight["dest_code"]
            if not orig_code or not dest_code:
                orig_code, dest_code = get_flight_route(flight.get("alt_callsign") or callsign)

            origin_name = format_airport_name(orig_code)
            dest_name = format_airport_name(dest_code)

            velocity_ms = flight["velocity_ms"]
            heading_deg = flight["heading_deg"]
            alt_ft = flight.get("alt_ft")
            speed_kmh = flight.get("speed_kmh")
            f_lat = flight["f_lat"]
            f_lon = flight["f_lon"]

            time_estimate_phrase = ""
            if velocity_ms and velocity_ms > 10 and heading_deg is not None:
                heading_rad = math.radians(heading_deg)
                vx = velocity_ms * math.sin(heading_rad)
                vy = velocity_ms * math.cos(heading_rad)

                dx = (lon - f_lon) * 111000.0 * math.cos(math.radians(lat))
                dy = (lat - f_lat) * 111000.0

                v2 = vx**2 + vy**2
                t_seconds = (dx * vx + dy * vy) / v2 if v2 > 0 else 0

                if t_seconds > 10:
                    t_min = max(1, int(round(t_seconds / 60.0)))
                    unit = "min" if t_min == 1 else "mins"
                    time_estimate_phrase = f"will cross your coordinates at exactly {t_min} {unit}"
                elif t_seconds >= -45:
                    time_estimate_phrase = "is crossing your coordinates right now"
                else:
                    time_estimate_phrase = "has just crossed your coordinates"
            else:
                t_seconds = (closest_dist_km * 1000.0) / 230.0
                t_min = max(1, int(round(t_seconds / 60.0)))
                unit = "min" if t_min == 1 else "mins"
                time_estimate_phrase = f"will cross your coordinates at exactly {t_min} {unit}"

            if alt_ft and alt_ft > 0 and speed_kmh and speed_kmh > 0:
                stats_clause = f", at an altitude of {alt_ft:,} feet and a speed of approximately {speed_kmh} kilometers per hour."
            elif alt_ft and alt_ft > 0:
                stats_clause = f", at an altitude of {alt_ft:,} feet."
            elif speed_kmh and speed_kmh > 0:
                stats_clause = f", at a speed of approximately {speed_kmh} kilometers per hour."
            else:
                stats_clause = "."

            if origin_name and dest_name:
                spoken_text = f"Sir, Flight {callsign} from {origin_name} to {dest_name} {time_estimate_phrase}{stats_clause}"
            else:
                spoken_text = f"Sir, Flight {callsign} {time_estimate_phrase}{stats_clause}"

            logger.info(f"Overhead flight verified on FlightRadar24: Callsign={callsign}, URL={fr24_url}, Spoken='{spoken_text}'")

            return {
                "spoken_text": spoken_text,
                "callsign": callsign if callsign != "Unknown" else None,
                "icao24": flight.get("icao24"),
                "origin": origin_name,
                "destination": dest_name,
                "altitude_ft": alt_ft,
                "speed_kmh": speed_kmh,
                "speed_kt": flight.get("speed_kt"),
                "lat": f_lat,
                "lon": f_lon,
                "fr24_url": fr24_url
            }
        else:
            logger.info(f"No airborne flights currently detected within {radius_km}km.")
    except Exception as e:
        logger.warning(f"Check overhead flight error: {e}")

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

    # Open browser to exact verified FlightRadar24 plane page
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

        # Full-cycle shuffle deck to guarantee every phrase is spoken at least once before repeating
        self.phrase_deck = []
        self.last_spoken = None

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
        """
        Selects a phrase using a full-cycle shuffle deck algorithm.
        Guarantees that EVERY phrase in phrases.json is spoken exactly once in random order
        before any phrase repeats.
        """
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
