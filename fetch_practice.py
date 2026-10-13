from datetime import datetime, timezone
import json
import ssl
import urllib.request

# Primary Live Telemetry Endpoint
URL_THAIWATER_LEVELS = (
    "https://api-v3.thaiwater.net/api/v1/thaiwater30/public/waterlevel_load"
)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML,"
        " like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9,th;q=0.8",
    "Origin": "https://www.thaiwater.net",
    "Referer": "https://www.thaiwater.net/",
}

# 20 Target Canal Sectors with Coordinates & Search Keywords
CANAL_DEFINITIONS = [
    {
        "id": "C01",
        "name": "Khlong Saen Saep",
        "pump_station": "Phra Khanong Pumping Complex",
        "district": "Wattana / Khlong Toei",
        "bank_limit_msl": 1.20,
        "path": [
            [13.7485, 100.5350],
            [13.7490, 100.5600],
            [13.7430, 100.5980],
            [13.7120, 100.5920],
        ],
        "station_lat": 13.7120,
        "station_lon": 100.5920,
        "keywords": ["แสนแสบ", "Saen Saep", "Saen Saeb", "พระโขนง"],
    },
    {
        "id": "C02",
        "name": "Khlong Phra Khanong",
        "pump_station": "Phra Khanong Sluice Gate",
        "district": "Phra Khanong",
        "bank_limit_msl": 1.50,
        "path": [
            [13.7120, 100.5920],
            [13.7050, 100.5890],
            [13.7010, 100.5830],
        ],
        "station_lat": 13.7010,
        "station_lon": 100.5830,
        "keywords": ["พระโขนง", "Phra Khanong"],
    },
    {
        "id": "C03",
        "name": "Khlong Prawet Buri Rom",
        "pump_station": "Prawet Control Gate",
        "district": "Prawet / Lat Krabang",
        "bank_limit_msl": 1.10,
        "path": [
            [13.7120, 100.5920],
            [13.7180, 100.6500],
            [13.7220, 100.7200],
            [13.7250, 100.7800],
        ],
        "station_lat": 13.7180,
        "station_lon": 100.6500,
        "keywords": ["ประเวศ", "Prawet", "Pravet"],
    },
    {
        "id": "C04",
        "name": "Khlong Lat Krabang",
        "pump_station": "Lat Krabang Pumping Station",
        "district": "Lat Krabang",
        "bank_limit_msl": 1.00,
        "path": [
            [13.7220, 100.7200],
            [13.6800, 100.7250],
            [13.6300, 100.7300],
        ],
        "station_lat": 13.6800,
        "station_lon": 100.7250,
        "keywords": ["ลาดกระบัง", "Lat Krabang", "Ladt Krabang"],
    },
    {
        "id": "C05",
        "name": "Khlong Sam Sen",
        "pump_station": "Sam Sen Pumping Station",
        "district": "Phaya Thai / Dusit",
        "bank_limit_msl": 1.30,
        "path": [
            [13.7780, 100.5400],
            [13.7750, 100.5200],
            [13.7720, 100.5020],
        ],
        "station_lat": 13.7720,
        "station_lon": 100.5020,
        "keywords": ["สามเสน", "Sam Sen", "Samsen"],
    },
    {
        "id": "C06",
        "name": "Khlong Bang Sue",
        "pump_station": "Bang Sue Drainage Tunnel Complex",
        "district": "Chatuchak / Bang Sue",
        "bank_limit_msl": 1.25,
        "path": [
            [13.8050, 100.5650],
            [13.8020, 100.5350],
            [13.7980, 100.5200],
        ],
        "station_lat": 13.7980,
        "station_lon": 100.5200,
        "keywords": ["บางซื่อ", "Bang Sue", "Bangsue"],
    },
    {
        "id": "C07",
        "name": "Khlong Lat Phrao",
        "pump_station": "Lat Phrao Water Control Station",
        "district": "Huai Khwang / Lat Phrao",
        "bank_limit_msl": 1.15,
        "path": [
            [13.8500, 100.5900],
            [13.8000, 100.5850],
            [13.7550, 100.5800],
        ],
        "station_lat": 13.8000,
        "station_lon": 100.5850,
        "keywords": ["ลาดพร้าว", "Lat Phrao", "Latprao"],
    },
    {
        "id": "C08",
        "name": "Khlong Prem Prachakon",
        "pump_station": "Prem Prachakon Gate",
        "district": "Don Mueang / Lak Si",
        "bank_limit_msl": 1.35,
        "path": [
            [13.9200, 100.5950],
            [13.8600, 100.5600],
            [13.7700, 100.5300],
        ],
        "station_lat": 13.8600,
        "station_lon": 100.5600,
        "keywords": ["เปรมประชากร", "Prem Prachakon", "Premprachakorn"],
    },
    {
        "id": "C09",
        "name": "Khlong Tan / Bang Kapi",
        "pump_station": "Bang Kapi Control Gate",
        "district": "Bangkapi",
        "bank_limit_msl": 1.20,
        "path": [
            [13.7600, 100.6200],
            [13.7450, 100.6000],
            [13.7380, 100.5850],
        ],
        "station_lat": 13.7450,
        "station_lon": 100.6000,
        "keywords": [
            "บางกะปิ",
            "คลองตัน",
            "Bang Kapi",
            "Bangkapi",
            "Khlong Tan",
        ],
    },
    {
        "id": "C10",
        "name": "Khlong Rangsit Prayunsak",
        "pump_station": "Chulalongkorn Sluice Gate",
        "district": "Pathum Thani Boundary",
        "bank_limit_msl": 1.60,
        "path": [
            [13.9800, 100.5400],
            [13.9820, 100.6200],
            [13.9850, 100.7500],
        ],
        "station_lat": 13.9800,
        "station_lon": 100.5400,
        "keywords": ["รังสิต", "จุฬาลงกรณ์", "Rangsit", "Chulalongkorn"],
    },
    {
        "id": "C11",
        "name": "Khlong Bangkok Yai",
        "pump_station": "Bangkok Yai Pumping Station",
        "district": "Thonburi / Bangkok Yai",
        "bank_limit_msl": 1.40,
        "path": [
            [13.7250, 100.4700],
            [13.7320, 100.4880],
            [13.7400, 100.4930],
        ],
        "station_lat": 13.7400,
        "station_lon": 100.4930,
        "keywords": ["บางกอกใหญ่", "Bangkok Yai"],
    },
    {
        "id": "C12",
        "name": "Khlong Bangkok Noi",
        "pump_station": "Bangkok Noi Control Gate",
        "district": "Bangkok Noi",
        "bank_limit_msl": 1.45,
        "path": [
            [13.8000, 100.4500],
            [13.7700, 100.4700],
            [13.7600, 100.4850],
        ],
        "station_lat": 13.7600,
        "station_lon": 100.4850,
        "keywords": ["บางกอกน้อย", "Bangkok Noi"],
    },
    {
        "id": "C13",
        "name": "Khlong Phasi Charoen",
        "pump_station": "Phasi Charoen Station",
        "district": "Phasi Charoen / Bang Khae",
        "bank_limit_msl": 1.10,
        "path": [
            [13.7200, 100.4600],
            [13.7120, 100.4000],
            [13.7050, 100.3200],
        ],
        "station_lat": 13.7200,
        "station_lon": 100.4600,
        "keywords": ["ภาษีเจริญ", "Phasi Charoen", "Phasicharoen"],
    },
    {
        "id": "C14",
        "name": "Khlong Sanam Chai",
        "pump_station": "Sanam Chai Water Gate",
        "district": "Bang Khun Thian",
        "bank_limit_msl": 1.20,
        "path": [
            [13.7000, 100.4700],
            [13.6300, 100.4400],
            [13.5500, 100.4000],
        ],
        "station_lat": 13.6300,
        "station_lon": 100.4400,
        "keywords": ["สนามชัย", "Sanam Chai", "Sanamchai"],
    },
    {
        "id": "C15",
        "name": "Khlong Maha Sawat",
        "pump_station": "Maha Sawat Control Gate",
        "district": "Taling Chan / Nonthaburi",
        "bank_limit_msl": 1.50,
        "path": [
            [13.8050, 100.4700],
            [13.8020, 100.3800],
            [13.7980, 100.2800],
        ],
        "station_lat": 13.8050,
        "station_lon": 100.4700,
        "keywords": ["มหาสวัสดิ์", "Maha Sawat", "Mahasawat"],
    },
    {
        "id": "C16",
        "name": "Khlong Samut Prakan / Pak Nam",
        "pump_station": "Pak Nam Fort Station",
        "district": "Mueang Samut Prakan",
        "bank_limit_msl": 1.80,
        "path": [
            [13.6000, 100.5900],
            [13.5800, 100.5950],
            [13.5600, 100.5980],
        ],
        "station_lat": 13.5600,
        "station_lon": 100.5980,
        "keywords": ["สมุทรปราการ", "ปากน้ำ", "Samut Prakan", "Pak Nam"],
    },
    {
        "id": "C17",
        "name": "Khlong Dan",
        "pump_station": "Khlong Dan Coastal Station",
        "district": "Bang Bo (Samut Prakan)",
        "bank_limit_msl": 1.70,
        "path": [
            [13.5500, 100.7800],
            [13.5100, 100.8000],
            [13.4800, 100.8200],
        ],
        "station_lat": 13.5100,
        "station_lon": 100.8000,
        "keywords": ["คลองด่าน", "Khlong Dan", "Khlongdan"],
    },
    {
        "id": "C18",
        "name": "Khlong Suvarnabhumi",
        "pump_station": "Suvarnabhumi Main Canal Station",
        "district": "Bang Phli (Samut Prakan)",
        "bank_limit_msl": 1.30,
        "path": [
            [13.6800, 100.7500],
            [13.6000, 100.7600],
            [13.5300, 100.7700],
        ],
        "station_lat": 13.6000,
        "station_lon": 100.7600,
        "keywords": ["สุวรรณภูมิ", "บางพลี", "Suvarnabhumi", "Bang Phli"],
    },
    {
        "id": "C19",
        "name": "Khlong Samrong",
        "pump_station": "Samrong Pumping Station",
        "district": "Samrong / Mueang Samut Prakan",
        "bank_limit_msl": 1.35,
        "path": [
            [13.6500, 100.5900],
            [13.6300, 100.6500],
            [13.6100, 100.7500],
        ],
        "station_lat": 13.6500,
        "station_lon": 100.5900,
        "keywords": ["สำโรง", "Samrong"],
    },
    {
        "id": "C20",
        "name": "Khlong Phra Ya Phren",
        "pump_station": "Bang Bor Control Gate",
        "district": "Bang Sao Thong (Samut Prakan)",
        "bank_limit_msl": 1.25,
        "path": [
            [13.6900, 100.8200],
            [13.6200, 100.8300],
            [13.5500, 100.8400],
        ],
        "station_lat": 13.6200,
        "station_lon": 100.8300,
        "keywords": [
            "พระยาแพรก",
            "บางเสาธง",
            "บางบ่อ",
            "Bang Bor",
            "Bang Sao Thong",
        ],
    },
]


def fetch_live_json(url):
  """Fetches raw JSON response from live remote endpoint with error handling."""
  ctx = ssl.create_default_context()
  ctx.check_hostname = False
  ctx.verify_mode = ssl.CERT_NONE

  try:
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=20, context=ctx) as response:
      raw = response.read().decode("utf-8", errors="ignore")
      return json.loads(raw)
  except Exception as e:
    print(f"HTTP Fetch Exception from {url}: {e}")
    return None


def extract_station_list(json_data):
  """Safely unpacks station list from various ThaiWater JSON wrappers."""
  if isinstance(json_data, list):
    return json_data
  if isinstance(json_data, dict):
    for key in ["data", "waterlevel_data", "waterlevel", "result"]:
      if key in json_data and isinstance(json_data[key], list):
        return json_data[key]
  return []


def get_station_coords(st):
  """Extracts latitude and longitude from station dictionary."""
  station_obj = st.get("station", st)
  lat = (
      station_obj.get("lat")
      or station_obj.get("latitude")
      or st.get("lat")
      or st.get("latitude")
  )
  lon = (
      station_obj.get("long")
      or station_obj.get("lon")
      or station_obj.get("longitude")
      or st.get("long")
      or st.get("lon")
  )
  try:
    return float(lat), float(lon)
  except (TypeError, ValueError):
    return None, None


def get_station_id(st):
  """Extracts station ID from station dictionary."""
  station_obj = st.get("station", st)
  return (
      station_obj.get("id")
      or station_obj.get("tele_station_id")
      or st.get("id")
      or "UNKNOWN"
  )


def get_station_name(st):
  """Extracts Thai and English station names from station dictionary."""
  station_obj = st.get("station", st)
  name_field = station_obj.get("tele_station_name") or station_obj.get(
      "station_name"
  )
  if isinstance(name_field, dict):
    th = name_field.get("th", "")
    en = name_field.get("en", "")
    return f"{th} {en}".strip()
  if isinstance(name_field, str):
    return name_field
  return ""


def get_water_level_msl(st):
  """Extracts reported water level in meters MSL."""
  val = st.get("waterlevel_msl")
  if val is None:
    val = st.get("waterlevel_m")
  try:
    if val is not None:
      return float(val)
  except (TypeError, ValueError):
    pass
  return None


def find_matching_live_station_strict_keywords(canal, live_stations):
  """Finds matching live station by STRICT KEYWORD MATCHING ONLY.

  Zero spatial fallback. If no keyword matches, returns None.
  """
  for st in live_stations:
    st_name = get_station_name(st)
    msl = get_water_level_msl(st)

    if msl is None:
      continue

    # Strict Keyword Match Check
    for kw in canal["keywords"]:
      if kw.lower() in st_name.lower():
        st_id = get_station_id(st)
        return st, st_id, st_name, msl

  # NO SPATIAL DISTANCE FALLBACK
  return None, None, None, None


def parse_live_tide_gauge(live_stations):
  """Searches live telemetry for coastal/estuary tide gauges around Pak Nam / Gulf."""
  tide_keywords = ["ปากน้ำ", "ป้อมพระจุล", "สมุทรปราการ", "Bangkok Port", "Fort Chula"]
  for st in live_stations:
    st_name = get_station_name(st)
    msl = get_water_level_msl(st)
    if msl is None:
      continue

    for kw in tide_keywords:
      if kw.lower() in st_name.lower():
        st_id = get_station_id(st)
        return msl, st_name, st_id

  return None, None, None


def main():
  utc_now = datetime.now(timezone.utc).isoformat()

  raw_json = fetch_live_json(URL_THAIWATER_LEVELS)
  live_stations = extract_station_list(raw_json) if raw_json else []

  # Capture full list of raw live stations for inspectability
  raw_station_catalog = []
  for st in live_stations:
    st_id = get_station_id(st)
    st_name = get_station_name(st)
    lat, lon = get_station_coords(st)
    msl = get_water_level_msl(st)
    raw_station_catalog.append({
        "station_id": st_id,
        "station_name": st_name,
        "lat": lat,
        "lon": lon,
        "waterlevel_msl": msl,
    })

  if not live_stations:
    payload = {
        "is_live": False,
        "status": "FETCH_FAILED",
        "updated_at_utc": utc_now,
        "error_message": (
            "Unable to connect to live ThaiWater telemetry endpoint"
            " (api-v3.thaiwater.net)."
        ),
        "summary": {
            "paknam_tide_msl": None,
            "tide_state": "DATA_UNAVAILABLE",
            "gravity_drainage_window": "DATA_UNAVAILABLE",
            "active_pumping_stations": None,
            "avg_canal_capacity_pct": None,
        },
        "raw_stations_count": 0,
        "raw_station_catalog": [],
        "canals": [
            {
                "id": c["id"],
                "name": c["name"],
                "pump_station": c["pump_station"],
                "district": c["district"],
                "station_lat": c["station_lat"],
                "station_lon": c["station_lon"],
                "path": c["path"],
                "bank_limit_msl": c["bank_limit_msl"],
                "water_level_msl": None,
                "buffer_remaining_m": None,
                "capacity_pct": None,
                "delta_h_meters": None,
                "drainage_mode": "DATA_UNAVAILABLE",
                "pump_status": "UNKNOWN",
                "risk_level": "NO_DATA",
                "live_data_found": False,
                "matched_station_id": None,
                "matched_station_name": None,
            }
            for c in CANAL_DEFINITIONS
        ],
    }
    with open("data_practice.json", "w", encoding="utf-8") as f:
      json.dump(payload, f, indent=2)
    return

  paknam_tide_msl, tide_st_name, tide_st_id = parse_live_tide_gauge(
      live_stations
  )

  canals_data = []
  total_capacity_used = 0
  valid_capacity_count = 0
  pumps_active_count = 0
  matched_count = 0

  for canal in CANAL_DEFINITIONS:
    st, st_id, st_name, live_msl = find_matching_live_station_strict_keywords(
        canal, live_stations
    )

    if live_msl is not None:
      matched_count += 1
      buffer_remaining = round(canal["bank_limit_msl"] - live_msl, 2)
      capacity_pct = round((live_msl / canal["bank_limit_msl"]) * 100, 1)

      total_capacity_used += capacity_pct
      valid_capacity_count += 1

      if paknam_tide_msl is not None:
        delta_h = round(live_msl - paknam_tide_msl, 2)
        if delta_h > 0.05:
          drainage_mode = "GRAVITY_DRAIN"
          pump_status = "STANDBY"
        else:
          drainage_mode = "PUMP_REQUIRED"
          pump_status = "ACTIVE_PUMPING"
          pumps_active_count += 1
      else:
        delta_h = None
        drainage_mode = "UNKNOWN (No Tide Data)"
        pump_status = "UNKNOWN"

      if capacity_pct >= 85.0:
        risk_level = "HIGH"
      elif capacity_pct >= 65.0:
        risk_level = "ELEVATED"
      else:
        risk_level = "NORMAL"

      canals_data.append({
          "id": canal["id"],
          "name": canal["name"],
          "pump_station": canal["pump_station"],
          "district": canal["district"],
          "station_lat": canal["station_lat"],
          "station_lon": canal["station_lon"],
          "path": canal["path"],
          "bank_limit_msl": canal["bank_limit_msl"],
          "water_level_msl": live_msl,
          "buffer_remaining_m": buffer_remaining,
          "capacity_pct": capacity_pct,
          "delta_h_meters": delta_h,
          "drainage_mode": drainage_mode,
          "pump_status": pump_status,
          "risk_level": risk_level,
          "live_data_found": True,
          "matched_station_id": st_id,
          "matched_station_name": st_name,
      })
    else:
      # Unmatched case: No spatial fallback or value fabrication
      canals_data.append({
          "id": canal["id"],
          "name": canal["name"],
          "pump_station": canal["pump_station"],
          "district": canal["district"],
          "station_lat": canal["station_lat"],
          "station_lon": canal["station_lon"],
          "path": canal["path"],
          "bank_limit_msl": canal["bank_limit_msl"],
          "water_level_msl": None,
          "buffer_remaining_m": None,
          "capacity_pct": None,
          "delta_h_meters": None,
          "drainage_mode": "DATA_UNAVAILABLE",
          "pump_status": "UNKNOWN",
          "risk_level": "NO_DATA",
          "live_data_found": False,
          "matched_station_id": None,
          "matched_station_name": None,
      })

  avg_capacity = (
      round(total_capacity_used / valid_capacity_count, 1)
      if valid_capacity_count > 0
      else None
  )

  if matched_count == 20:
    status_str = "OK"
    err_msg = None
  elif matched_count > 0:
    status_str = "PARTIAL"
    err_msg = (
        f"Strict keyword match found live telemetry for {matched_count} of 20"
        f" canal sectors. {20 - matched_count} sectors have no matching station"
        " name in the live feed."
    )
  else:
    status_str = "FETCH_FAILED"
    err_msg = (
        "No matching station keywords found on live ThaiWater endpoints."
    )

  payload = {
      "is_live": matched_count > 0,
      "status": status_str,
      "updated_at_utc": utc_now,
      "error_message": err_msg,
      "summary": {
          "paknam_tide_msl": paknam_tide_msl,
          "tide_state": (
              (
                  "SPRING_HIGH_TIDE"
                  if paknam_tide_msl >= 1.40
                  else "NEAP_LOW_TIDE"
              )
              if paknam_tide_msl is not None
              else "DATA_UNAVAILABLE"
          ),
          "gravity_drainage_window": (
              (
                  "LOCKED (High Tide)"
                  if paknam_tide_msl >= 1.30
                  else "OPEN (Gravity Drain)"
              )
              if paknam_tide_msl is not None
              else "DATA_UNAVAILABLE"
          ),
          "active_pumping_stations": (
              pumps_active_count if paknam_tide_msl is not None else None
          ),
          "avg_canal_capacity_pct": avg_capacity,
      },
      "raw_stations_count": len(raw_station_catalog),
      "raw_station_catalog": raw_station_catalog,
      "canals": canals_data,
  }

  with open("data_practice.json", "w", encoding="utf-8") as f:
    json.dump(payload, f, indent=2)

  print(
      f"Practice sync completed: Matched {matched_count}/20 sectors. Saved to"
      " data_practice.json."
  )


if __name__ == "__main__":
  main()
