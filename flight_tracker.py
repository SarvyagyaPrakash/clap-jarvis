#!/usr/bin/env python3

import math
import requests
from config_manager import logger

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

    # 1. Try FlightRadar24 web find API
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
            airborne_flights.sort(key=lambda x: x["dist_km"])
            flight = airborne_flights[0]
            cand_fr24_id = flight.get("fr24_id")

            if cand_fr24_id:
                fr24_url = f"https://www.flightradar24.com/{cand_fr24_id}"
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
