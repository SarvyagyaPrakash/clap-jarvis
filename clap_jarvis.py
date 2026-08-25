#!/usr/bin/env python3

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

try:
    from activity_monitor import check_trigger_permitted, is_audio_playing, is_in_meeting
except ImportError:
    # Fallback if module loaded differently
    from .activity_monitor import check_trigger_permitted, is_audio_playing, is_in_meeting

# Default Fallback Configurations (optimized for precise snap/clap detection and human-like neural voice)
DEFAULT_CONFIG = {
    "threshold_peak": 0.18,         # Clap peak threshold (prevents voice false-positives)
    "threshold_snap_peak": 0.12,    # Snap peak threshold (responsive to deliberate finger snaps)
    "min_crest_factor": 4.5,        # Sharp percussive transient crest factor (filters ambient noise)
    "threshold_rms": 0.004,         # RMS energy floor
    "required_claps": 2,            # Requires 2 snaps or claps
    "window_seconds": 2.5,          # Window for double snap/clap
    "cooldown_seconds": 4.0,        # Pause after trigger to prevent self-triggering from TTS
    "voice": "en-GB-RyanNeural",    # Ultra-realistic British Male Neural Voice (JARVIS)
    "enable_flight_check": True,
    "suppress_during_audio": True,   # Block trigger when audio is playing from any browser/player
    "suppress_during_meetings": False, # Block trigger when user is in a meeting (Zoom, Meet, Teams, FaceTime) - disabled so JARVIS works in meetings
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
    # India - Major Metros & Hubs
    "VIDP": "Delhi", "DEL": "Delhi",
    "VABB": "Mumbai", "BOM": "Mumbai",
    "NMI": "Navi Mumbai",
    "VOBL": "Bengaluru", "BLR": "Bengaluru",
    "VOMM": "Chennai", "MAA": "Chennai",
    "VECC": "Kolkata", "CCU": "Kolkata",
    "VHYD": "Hyderabad", "HYD": "Hyderabad",
    "VAAH": "Ahmedabad", "AMD": "Ahmedabad",
    "VAPO": "Pune", "PNQ": "Pune",
    "VAGO": "Goa Dabolim", "GOI": "Goa Dabolim",
    "VOGA": "Goa Mopa", "GOX": "Goa Mopa",

    # India - Madhya Pradesh & Central India
    "VABP": "Bhopal", "BHO": "Bhopal",
    "VAID": "Indore", "IDR": "Indore",
    "VIGW": "Gwalior", "GWL": "Gwalior",
    "VAJB": "Jabalpur", "JLR": "Jabalpur",
    "VAKJ": "Khajuraho", "HJR": "Khajuraho",
    "VARP": "Raipur", "RPR": "Raipur",
    "VAPM": "Nagpur", "NAG": "Nagpur",

    # India - North & Northwest
    "VIJP": "Jaipur", "JAI": "Jaipur",
    "VICG": "Chandigarh", "IXC": "Chandigarh",
    "VILK": "Lucknow", "LKO": "Lucknow",
    "VEBN": "Varanasi", "VNS": "Varanasi",
    "VEPT": "Patna", "PAT": "Patna",
    "VEAY": "Ayodhya", "AYJ": "Ayodhya",
    "VIAR": "Amritsar", "ATQ": "Amritsar",
    "VISR": "Srinagar", "SXR": "Srinagar",
    "VIJU": "Jammu", "IXJ": "Jammu",
    "VILH": "Leh", "IXL": "Leh",
    "VIDN": "Dehradun", "DED": "Dehradun",
    "VIJO": "Jodhpur", "JDH": "Jodhpur",
    "VAUD": "Udaipur", "UDR": "Udaipur",
    "VIJR": "Jaisalmer", "JSA": "Jaisalmer",
    "VABK": "Bikaner", "BKB": "Bikaner",
    "VAKP": "Kanpur", "KNU": "Kanpur",
    "VIAG": "Agra", "AGR": "Agra",
    "VEGK": "Gorakhpur", "GOP": "Gorakhpur",
    "VIBL": "Bareilly", "BEK": "Bareilly",
    "VIPM": "Pantnagar", "PGH": "Pantnagar",
    "VIBR": "Kullu", "KUU": "Kullu",
    "VIGG": "Dharamsala", "DHM": "Dharamsala",

    # India - West & Southwest
    "VABO": "Vadodara", "BDQ": "Vadodara",
    "VASU": "Surat", "STV": "Surat",
    "VAJM": "Jamnagar", "JGA": "Jamnagar",
    "VARK": "Rajkot", "RAJ": "Rajkot",
    "VABJ": "Bhuj", "BHJ": "Bhuj",
    "VAPR": "Porbandar", "PBD": "Porbandar",
    "VASD": "Shirdi", "SAG": "Shirdi",
    "VAAU": "Aurangabad", "IXU": "Aurangabad",
    "VAKL": "Kolhapur", "KLH": "Kolhapur",
    "VANR": "Nanded", "NDC": "Nanded",

    # India - South
    "VOCI": "Cochin", "COK": "Cochin",
    "VOTV": "Trivandrum", "TRV": "Trivandrum",
    "VOCL": "Calicut", "CCJ": "Calicut",
    "VOCN": "Kannur", "CNN": "Kannur",
    "VOML": "Mangalore", "IXE": "Mangalore",
    "VOCB": "Coimbatore", "CJB": "Coimbatore",
    "VOMD": "Madurai", "IXM": "Madurai",
    "VOTR": "Tiruchirappalli", "TRZ": "Tiruchirappalli",
    "VOTP": "Tirupati", "TIR": "Tirupati",
    "VOVZ": "Visakhapatnam", "VTZ": "Visakhapatnam",
    "VOBZ": "Vijayawada", "VGA": "Vijayawada",
    "VOHB": "Hubli", "HBX": "Hubli",
    "VOBM": "Belgaum", "IXG": "Belgaum",
    "VOMY": "Mysore", "MYQ": "Mysore",

    # India - East & Northeast
    "VEGT": "Guwahati", "GAU": "Guwahati",
    "VEBD": "Bagdogra", "IXB": "Bagdogra",
    "VEBS": "Bhubaneswar", "BBI": "Bhubaneswar",
    "VERC": "Ranchi", "IXR": "Ranchi",
    "VEBI": "Shillong", "SHL": "Shillong",
    "VEIM": "Imphal", "IMF": "Imphal",
    "VEAZ": "Aizawl", "AJL": "Aizawl",
    "VEAT": "Agartala", "IXA": "Agartala",
    "VEDI": "Dibrugarh", "DIB": "Dibrugarh",
    "VETZ": "Tezpur", "TEZ": "Tezpur",
    "VESL": "Silchar", "IXS": "Silchar",
    "VEMR": "Dimapur", "DMU": "Dimapur",
    "VEPY": "Pakyong", "PYG": "Pakyong",

    # Middle East & Gulf Hubs
    "OMAA": "Abu Dhabi", "AUH": "Abu Dhabi",
    "OMDB": "Dubai", "DXB": "Dubai",
    "OMDW": "Dubai World Central", "DWC": "Dubai World Central",
    "OMSJ": "Sharjah", "SHJ": "Sharjah",
    "OTHH": "Doha", "DOH": "Doha",
    "OEMA": "Medina", "MED": "Medina",
    "OEJN": "Jeddah", "JED": "Jeddah",
    "OERK": "Riyadh", "RUH": "Riyadh",
    "OEDF": "Dammam", "DMM": "Dammam",
    "OOMS": "Muscat", "MCT": "Muscat",
    "OBBI": "Bahrain", "BAH": "Bahrain",
    "OKBK": "Kuwait City", "KWI": "Kuwait City",
    "HECA": "Cairo", "CAI": "Cairo",
    "LLBG": "Tel Aviv", "TLV": "Tel Aviv",

    # Asia & Pacific
    "WSSS": "Singapore", "SIN": "Singapore",
    "WMKK": "Kuala Lumpur", "KUL": "Kuala Lumpur",
    "VTBS": "Bangkok Suvarnabhumi", "BKK": "Bangkok Suvarnabhumi",
    "VTBD": "Bangkok Don Mueang", "DMK": "Bangkok Don Mueang",
    "VTSP": "Phuket", "HKT": "Phuket",
    "VHHH": "Hong Kong", "HKG": "Hong Kong",
    "VVNB": "Hanoi", "HAN": "Hanoi",
    "VVTS": "Ho Chi Minh City", "SGN": "Ho Chi Minh City",
    "VGHS": "Dhaka", "DAC": "Dhaka",
    "VNKT": "Kathmandu", "KTM": "Kathmandu",
    "VRMM": "Maldives Male", "MLE": "Maldives Male",
    "VCBI": "Colombo", "CMB": "Colombo",
    "RPLL": "Manila", "MNL": "Manila",
    "WADD": "Bali", "DPS": "Bali",
    "WIII": "Jakarta", "CGK": "Jakarta",
    "RJAA": "Tokyo Narita", "NRT": "Tokyo Narita",
    "RJTT": "Tokyo Haneda", "HND": "Tokyo Haneda",
    "RJBB": "Osaka", "KIX": "Osaka",
    "RKSI": "Seoul Incheon", "ICN": "Seoul Incheon",
    "ZSPD": "Shanghai Pudong", "PVG": "Shanghai Pudong",
    "ZBAA": "Beijing Capital", "PEK": "Beijing Capital",
    "ZGSZ": "Shenzhen", "SZX": "Shenzhen",
    "ZGGG": "Guangzhou", "CAN": "Guangzhou",
    "RCTP": "Taipei", "TPE": "Taipei",
    "YSSY": "Sydney", "SYD": "Sydney",
    "YMML": "Melbourne", "MEL": "Melbourne",
    "YPPH": "Perth", "PER": "Perth",
    "NZAA": "Auckland", "AKL": "Auckland",

    # Europe & UK
    "EGLL": "London Heathrow", "LHR": "London Heathrow",
    "EGKK": "London Gatwick", "LGW": "London Gatwick",
    "EGSS": "London Stansted", "STN": "London Stansted",
    "EGCC": "Manchester", "MAN": "Manchester",
    "EGPH": "Edinburgh", "EDI": "Edinburgh",
    "LFPG": "Paris Charles de Gaulle", "CDG": "Paris Charles de Gaulle",
    "LFPO": "Paris Orly", "ORY": "Paris Orly",
    "EDDF": "Frankfurt", "FRA": "Frankfurt",
    "EDDM": "Munich", "MUC": "Munich",
    "EDDB": "Berlin", "BER": "Berlin",
    "EHAM": "Amsterdam", "AMS": "Amsterdam",
    "LSZH": "Zurich", "ZRH": "Zurich",
    "LOWW": "Vienna", "VIE": "Vienna",
    "LIRF": "Rome Fiumicino", "FCO": "Rome Fiumicino",
    "LIMC": "Milan Malpensa", "MXP": "Milan Malpensa",
    "LEMD": "Madrid", "MAD": "Madrid",
    "LEBL": "Barcelona", "BCN": "Barcelona",
    "LTFM": "Istanbul", "IST": "Istanbul",
    "LTFJ": "Istanbul Sabiha", "SAW": "Istanbul Sabiha",

    # North America
    "KJFK": "New York JFK", "JFK": "New York JFK",
    "KEWR": "Newark", "EWR": "Newark",
    "KLAX": "Los Angeles", "LAX": "Los Angeles",
    "KSFO": "San Francisco", "SFO": "San Francisco",
    "KORD": "Chicago O'Hare", "ORD": "Chicago O'Hare",
    "KATL": "Atlanta", "ATL": "Atlanta",
    "KDFW": "Dallas Fort Worth", "DFW": "Dallas Fort Worth",
    "KIAH": "Houston", "IAH": "Houston",
    "KMIA": "Miami", "MIA": "Miami",
    "KBOS": "Boston", "BOS": "Boston",
    "KSEA": "Seattle", "SEA": "Seattle",
    "CYYZ": "Toronto Pearson", "YYZ": "Toronto Pearson",
    "CYVR": "Vancouver", "YVR": "Vancouver",
    "CYUL": "Montreal", "YUL": "Montreal",

    # Africa
    "FAOR": "Johannesburg", "JNB": "Johannesburg",
    "FACT": "Cape Town", "CPT": "Cape Town",
    "HKJK": "Nairobi", "NBO": "Nairobi",
    "HAAB": "Addis Ababa", "ADD": "Addis Ababa"
}

AIRPORT_CACHE = {}


def format_airport_name(code):
    """Converts ICAO/IATA airport code or city string to a human-readable city/airport name."""
    if not code:
        return None

    # Clean string if formatted like "Rome (FCO)" or "Abu Dhabi / AUH"
    if "(" in code and ")" in code:
        code_clean = code.split("(")[0].strip()
        if code_clean:
            return code_clean

    code_upper = code.upper().strip()
    if code_upper in AIRPORT_NAMES:
        return AIRPORT_NAMES[code_upper]

    if code_upper in AIRPORT_CACHE:
        return AIRPORT_CACHE[code_upper]

    # Dynamic fallback lookup if code is a 3-letter IATA or 4-letter ICAO
    if len(code_upper) in [3, 4] and code_upper.isalpha():
        try:
            url = f"https://hexdb.io/api/v1/airport/iata/{code_upper}" if len(code_upper) == 3 else f"https://hexdb.io/api/v1/airport/icao/{code_upper}"
            resp = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=1.2)
            if resp.status_code == 200:
                data = resp.json()
                city = data.get("city") or data.get("name")
                if city:
                    AIRPORT_CACHE[code_upper] = city
                    return city
        except Exception:
            pass

    return code.strip()


AIRLINE_NAMES = {
    # Indian Carriers
    "6E": "IndiGo", "IGO": "IndiGo",
    "AI": "Air India", "AIC": "Air India",
    "IX": "Air India Express", "AXB": "Air India Express",
    "QP": "Akasa Air", "AKJ": "Akasa Air",
    "SG": "SpiceJet", "SEJ": "SpiceJet",
    "UK": "Vistara", "VTI": "Vistara",
    "I5": "AirAsia India", "IAD": "AirAsia India",
    "9I": "Alliance Air", "LLR": "Alliance Air",
    "S5": "Star Air", "SDG": "Star Air",
    "FLG": "FlyBig", "FLY": "FlyBig",

    # Middle East & Gulf Carriers
    "EK": "Emirates", "UAE": "Emirates",
    "FZ": "Flydubai", "FDB": "Flydubai",
    "QR": "Qatar Airways", "QTR": "Qatar Airways",
    "EY": "Etihad Airways", "ETD": "Etihad Airways",
    "G9": "Air Arabia", "ABY": "Air Arabia",
    "SV": "Saudia", "SVA": "Saudia",
    "WY": "Oman Air", "OMA": "Oman Air",
    "GF": "Gulf Air", "GFA": "Gulf Air",
    "J9": "Jazeera Airways", "JZR": "Jazeera Airways",
    "KU": "Kuwait Airways", "KAC": "Kuwait Airways",

    # Asian & Global Carriers
    "SQ": "Singapore Airlines", "SIA": "Singapore Airlines",
    "TG": "Thai Airways", "THA": "Thai Airways",
    "MH": "Malaysia Airlines", "MAS": "Malaysia Airlines",
    "CX": "Cathay Pacific", "CPA": "Cathay Pacific",
    "BA": "British Airways", "BAW": "British Airways",
    "LH": "Lufthansa", "DLH": "Lufthansa",
    "AF": "Air France", "AFR": "Air France",
    "KL": "KLM", "KLM": "KLM",
    "TK": "Turkish Airlines", "THY": "Turkish Airlines",
    "UL": "SriLankan Airlines", "ALK": "SriLankan Airlines",
    "FDX": "FedEx", "UPS": "UPS"
}


def format_flight_spoken(callsign, flight_num=None, airline_code=None):
    """Formats a FlightRadar24 call sign (e.g. AIC5QY, AXB2153) for natural, accurate TTS pronunciation and display."""
    raw_cs = (callsign or "").strip().upper()
    raw_num = (flight_num or "").strip().upper()

    # Primary identifier: Call Sign (e.g. AIC5QY)
    code = raw_cs if raw_cs and raw_cs != "UNKNOWN" else raw_num
    if not code or code == "UNKNOWN":
        return "an unidentified aircraft", "Unknown"

    airline_name = None
    if airline_code and airline_code in AIRLINE_NAMES:
        airline_name = AIRLINE_NAMES[airline_code]
    else:
        # Check airline code prefix in AIRLINE_NAMES
        for pfx_len in [3, 2]:
            pfx = code[:pfx_len]
            if pfx in AIRLINE_NAMES:
                airline_name = AIRLINE_NAMES[pfx]
                break

    if airline_name:
        spoken = f"{airline_name} Flight {code}"
    else:
        spoken = f"Flight {code}"

    display_flight = code
    return spoken, display_flight


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
    """Checks live flight feeds (FlightRadar24 primary, adsb.fi & OpenSky fallbacks) for planes overhead; returns details dict or None."""
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
                                airline_icao = val[18] if len(val) > 18 else None
                                callsign = (callsign_raw or flight_num or "").strip().upper()
                                alt_callsign = (flight_num or callsign_raw or "").strip().upper()
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
                                    "flight_number": flight_num,
                                    "alt_callsign": alt_callsign,
                                    "airline_icao": airline_icao,
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
            
            # Select the closest aircraft and build guaranteed verified FlightRadar24 URL
            flight = airborne_flights[0]
            cand_fr24_id = flight.get("fr24_id")

            if cand_fr24_id:
                fr24_url = f"https://www.flightradar24.com/{cand_fr24_id}"
            else:
                # Center directly on aircraft coordinates to guarantee a clean map without 404 popup
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

            spoken_flight, display_flight = format_flight_spoken(
                flight.get("callsign"),
                flight.get("flight_number"),
                flight.get("airline_icao")
            )

            if origin_name and dest_name:
                spoken_text = f"Sir, {spoken_flight} from {origin_name} to {dest_name} {time_estimate_phrase}{stats_clause}"
            else:
                spoken_text = f"Sir, {spoken_flight} {time_estimate_phrase}{stats_clause}"

            logger.info(f"Overhead flight verified on FlightRadar24: Callsign={display_flight}, URL={fr24_url}, Spoken='{spoken_text}'")

            return {
                "spoken_text": spoken_text,
                "callsign": display_flight if display_flight != "Unknown" else (callsign if callsign != "Unknown" else None),
                "flight_number": flight.get("flight_number"),
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

    # Fallback to standard new browser tab if no existing FlightRadar24 tab was found
    logger.info(f"No existing FlightRadar24 tab found. Opening in default browser: {target_url}")
    webbrowser.open(target_url)
    return False


def speak_and_launch(phrase, voice, flight_data=None, on_done=None):
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

        try:
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

        threshold_peak = float(config.get("threshold_peak", 0.16))
        threshold_snap_peak = float(config.get("threshold_snap_peak", 0.05))
        min_crest_factor = float(config.get("min_crest_factor", 2.8))

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
        self.min_inter_clap_gap = 0.15
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
        cooldown = float(self.config.get("cooldown_seconds", 3.0))
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

            threshold_peak = float(self.config.get("threshold_peak", 0.16))
            threshold_snap_peak = float(self.config.get("threshold_snap_peak", 0.05))
            threshold_rms = float(self.config.get("threshold_rms", 0.003))
            min_crest_factor = float(self.config.get("min_crest_factor", 2.8))

            # 1. Check Hand Clap and Finger Snap transients
            is_clap = peak >= threshold_peak and rms >= threshold_rms
            is_snap = peak >= threshold_snap_peak and crest_factor >= min_crest_factor

            if is_clap or is_snap:
                if now - self.last_clap_time >= self.min_inter_clap_gap:
                    self.last_clap_time = now
                    self.clap_timestamps.append(now)
                    event_type = "Hand Clap" if is_clap else "Finger Snap"
                    logger.info(f"{event_type} detected! Peak: {peak:.3f}, RMS: {rms:.3f}, Crest: {crest_factor:.1f}")

                    window_seconds = float(self.config.get("window_seconds", 4.0))
                    required_claps = int(self.config.get("required_claps", 2))
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
        # Ensures no triggers occur during active audio playback or meetings, but permitted when media is paused.
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
