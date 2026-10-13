from datetime import datetime, timezone
import json
import re
import ssl
import urllib.error
import urllib.request

# Public Hydrological & Climate Telemetry Endpoints
URL_ENSO = "https://www.cpc.ncep.noaa.gov/data/indices/sstoi.indices"
URL_MJO = (
    "https://www.bom.gov.au/climate/mjo/graphics/rmm.74toRealtime.txt"
)
URL_HII_CHAO_PHRAYA = (
    "https://tiwrmdev.hii.or.th/DATA/REPORT/php/chart/chaopraya/small/chaopraya.php"
)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML,"
        " like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

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
    },
]


def fetch_text_endpoint(url):
  """Fetches raw text content from remote HTTP endpoints without authentication."""
  ctx = ssl.create_default_context()
  ctx.check_hostname = False
  ctx.verify_mode = ssl.CERT_NONE

  try:
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=15, context=ctx) as response:
      return response.read().decode("utf-8", errors="ignore"), None
  except urllib.error.HTTPError as e:
    err_msg = f"HTTP Error {e.code}: {e.reason} for {url}"
    print(err_msg)
    return None, err_msg
  except Exception as e:
    err_msg = f"Network Error: {e} for {url}"
    print(err_msg)
    return None, err_msg


def main():
  utc_now = datetime.now(timezone.utc).isoformat()

  # Test fetching public climate & hydrological endpoints
  enso_text, enso_err = fetch_text_endpoint(URL_ENSO)
  hii_text, hii_err = fetch_text_endpoint(URL_HII_CHAO_PHRAYA)

  errors = []
  if enso_err:
    errors.append(enso_err)
  if hii_err:
    errors.append(hii_err)

  err_msg = " | ".join(errors) if errors else None

  canals_output = []
  for canal in CANAL_DEFINITIONS:
    canals_output.append({
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

  # Without Stormglass or live canal API keys, canal level is marked as unavailable
  payload = {
      "is_live": False,
      "status": "FETCH_FAILED",
      "updated_at_utc": utc_now,
      "error_message": (
          err_msg or "No unauthenticated live canal endpoints accessible."
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
      "canals": canals_output,
  }

  with open("data_practice.json", "w", encoding="utf-8") as f:
    json.dump(payload, f, indent=2)

  print("Sync complete. Output written to data_practice.json.")


if __name__ == "__main__":
  main()
