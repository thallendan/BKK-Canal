#!/usr/bin/env python3
"""
fetch_canals.py

Fetches live BMA canal telemetry directly from the Bangkok Drainage and 
Sewerage Department using a 2-step session to acquire cookies before querying 
the AJAX endpoint.

Output file: canals.json
"""

import json
import time
import requests
from datetime import datetime, timezone

URL_HOME = "https://weather.bangkok.go.th/KlongMap"
URL_API = "https://weather.bangkok.go.th/Klongmap/GetDataForUpdate"
OUTPUT_FILE = "canals.json"

HEADERS_HOME = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "th-TH,th;q=0.9,en-US;q=0.8,en;q=0.7",
}

HEADERS_API = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Referer": "https://weather.bangkok.go.th/KlongMap",
    "X-Requested-With": "XMLHttpRequest",
    "Accept": "application/json, text/javascript, */*; q=0.01",
    "Accept-Language": "th-TH,th;q=0.9,en-US;q=0.8,en;q=0.7",
}

def fetch_bma_canal_data():
    """Establishes an ASP.NET session on the homepage before requesting JSON telemetry."""
    session = requests.Session()
    start_time = time.time()

    try:
        # Step 1: Visit homepage to acquire session cookies and initialize session state
        resp_home = session.get(URL_HOME, headers=HEADERS_HOME, timeout=15, verify=False)
        if resp_home.status_code != 200:
            return False, resp_home.status_code, 0, None, f"Homepage returned HTTP {resp_home.status_code}"

        # Small delay to mimic standard client execution
        time.sleep(1)

        # Step 2: Query telemetry endpoint with established session context
        resp_api = session.get(URL_API, headers=HEADERS_API, timeout=15, verify=False)
        elapsed = round(time.time() - start_time, 3)

        if resp_api.status_code == 200:
            data = resp_api.json()
            return True, resp_api.status_code, elapsed, data, None
        else:
            return False, resp_api.status_code, elapsed, None, f"API returned HTTP {resp_api.status_code}"

    except requests.exceptions.RequestException as e:
        return False, None, 0, None, f"Request failed: {str(e)}"
    except json.JSONDecodeError:
        return False, 200, 0, None, "Response was not valid JSON"

def process_canal_payload(data):
    """Parses raw BMA telemetry into structured canal and station models."""
    water_stations = data.get("waterStation", [])
    river_maps = data.get("riverMap", [])
    
    river_lookup = {}
    for r in river_maps:
        rid = r.get("river_map_id")
        if rid is not None:
            river_lookup[rid] = {
                "name_th": r.get("river_map_name", ""),
                "name_en": r.get("river_map_name_en", "")
            }

    parsed_stations = []
    normal_count = 0
    warning_count = 0
    critical_count = 0
    latest_ts = None

    for st in water_stations:
        info = st.get("water_station_info") or {}
        last = st.get("water_level_last") or {}

        station_name = info.get("station_name", "Unknown Station")
        ts = last.get("site_timestamp")
        if ts and not latest_ts:
            latest_ts = ts

        wl_in = last.get("wl_in")
        warning_thresh = info.get("warning")
        critical_thresh = info.get("critical")
        dry_thresh = info.get("dry_in")

        status = "NORMAL"
        if wl_in is not None and warning_thresh is not None and critical_thresh is not None:
            try:
                wl_val = float(wl_in)
                warn_val = float(warning_thresh)
                crit_val = float(critical_thresh)

                if wl_val >= crit_val:
                    status = "CRITICAL"
                    critical_count += 1
                elif wl_val >= warn_val:
                    status = "WARNING"
                    warning_count += 1
                else:
                    normal_count += 1
            except (ValueError, TypeError):
                normal_count += 1
        else:
            normal_count += 1

        parsed_stations.append({
            "water_id": st.get("water_id"),
            "system_id": st.get("system_id"),
            "station_name": station_name,
            "water_level_msl": float(wl_in) if wl_in is not None else None,
            "threshold_warning_msl": float(warning_thresh) if warning_thresh is not None else None,
            "threshold_critical_msl": float(critical_thresh) if critical_thresh is not None else None,
            "threshold_dry_msl": float(dry_thresh) if dry_thresh is not None else None,
            "status": status,
            "timestamp": ts
        })

    return {
        "summary": {
            "total_stations": len(parsed_stations),
            "normal_count": normal_count,
            "warning_count": warning_count,
            "critical_count": critical_count,
            "latest_station_timestamp": latest_ts
        },
        "canals": [
            {"river_map_id": k, **v} for k, v in river_lookup.items()
        ],
        "stations": parsed_stations
    }

def main():
    # Disable SSL warnings for government self-signed chain handling
    requests.packages.urllib3.disable_warnings()

    timestamp_utc = datetime.now(timezone.utc).isoformat()
    print("Fetching live BMA canal telemetry...")
    
    success, status_code, elapsed, raw_data, error_msg = fetch_bma_canal_data()

    if not success or not raw_data:
        payload = {
            "timestamp_utc": timestamp_utc,
            "is_live": False,
            "status_code": status_code,
            "error": error_msg,
            "summary": None,
            "canals": [],
            "stations": []
        }
        print(f"Fetch failed: {error_msg}")
    else:
        processed = process_canal_payload(raw_data)
        payload = {
            "timestamp_utc": timestamp_utc,
            "is_live": True,
            "status_code": status_code,
            "response_time_sec": elapsed,
            **processed
        }
        print(f"Successfully fetched {processed['summary']['total_stations']} canal stations in {elapsed}s.")

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)

    print(f"Saved canal telemetry to '{OUTPUT_FILE}'.")

if __name__ == "__main__":
    main()
