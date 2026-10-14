#!/usr/bin/env python3
"""
fetch_practice_canal.py

Fetches live canal and river water level telemetry from ThaiWater (HII API v3).
Parses nested station data, filters specifically for Bangkok and Samut Prakan
waterways, and exports standardized station metrics to 'bkk_samutprakan_canals.json'.

If the live fetch fails, it records the exact error diagnostic without
simulating or generating fake data.
"""

import json
import ssl
import time
import urllib.request
import urllib.error
from datetime import datetime, timezone

# Live endpoint for ThaiWater public water level telemetry
CANAL_ENDPOINT_URL = "https://api-v3.thaiwater.net/api/v1/thaiwater30/public/waterlevel_load"
OUTPUT_FILE = "bkk_samutprakan_canals.json"

TARGET_PROVINCES = {"Bangkok", "Samut Prakan", "กรุงเทพมหานคร", "สมุทรปราการ"}


def fetch_live_canal_data(url: str) -> tuple[dict, list]:
    """
    Fetches raw JSON from the live endpoint and returns diagnostic metadata
    along with parsed station records.
    """
    start_time = time.time()
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        )
    }

    req = urllib.request.Request(url, headers=headers)
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE

    diagnostic = {
        "endpoint_url": url,
        "fetch_timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "success": False,
        "status_code": None,
        "response_time_sec": None,
        "error": None
    }

    try:
        with urllib.request.urlopen(req, context=ctx, timeout=20) as response:
            elapsed = round(time.time() - start_time, 3)
            status = response.status
            raw_bytes = response.read()

            diagnostic["success"] = True
            diagnostic["status_code"] = status
            diagnostic["response_time_sec"] = elapsed

            payload = json.loads(raw_bytes.decode("utf-8"))
            
            # Correct nested pathway: response -> data -> waterlevel_data -> data
            station_list = (
                payload.get("data", {})
                .get("waterlevel_data", {})
                .get("data", [])
            )
            return diagnostic, station_list

    except urllib.error.HTTPError as e:
        diagnostic["status_code"] = e.code
        diagnostic["error"] = f"HTTP Error {e.code}: {e.reason}"
    except urllib.error.URLError as e:
        diagnostic["error"] = f"URL Connection Error: {e.reason}"
    except TimeoutError:
        diagnostic["error"] = "Connection timed out (20s limit)"
    except Exception as e:
        diagnostic["error"] = f"Fetch or JSON parsing failed: {str(e)}"

    return diagnostic, []


def parse_bkk_samutprakan_stations(raw_stations: list) -> list:
    """
    Filters raw telemetry records for Bangkok and Samut Prakan stations,
    handling nested geocode names and safely formatting fields.
    """
    filtered_stations = []

    for item in raw_stations:
        geocode = item.get("geocode", {})
        prov_obj = geocode.get("province_name", {})
        
        # Safely extract English and Thai province names
        prov_en = prov_obj.get("en") if isinstance(prov_obj, dict) else None
        prov_th = prov_obj.get("th") if isinstance(prov_obj, dict) else None

        if prov_en in TARGET_PROVINCES or prov_th in TARGET_PROVINCES:
            station_info = item.get("station", {})
            station_name_obj = station_info.get("tele_station_name", {})
            
            # Format station name safely even if language keys are missing
            if isinstance(station_name_obj, dict):
                st_name_en = station_name_obj.get("en")
                st_name_th = station_name_obj.get("th")
                display_name = st_name_en or st_name_th or f"Station {item.get('id')}"
            else:
                display_name = str(station_name_obj)

            parsed_record = {
                "station_id": item.get("id"),
                "province_en": prov_en,
                "province_th": prov_th,
                "station_name": display_name,
                "station_name_detail": station_name_obj,
                "river_or_canal": item.get("river_name"),
                "water_level_m_msl": item.get("waterlevel_msl"),
                "water_level_m_ground": item.get("waterlevel_m"),
                "bank_height_m_msl": item.get("ground_level"),
                "situation_level": item.get("situation_level"),
                "station_type": item.get("station_type"),
                "telemetry_time": item.get("waterlevel_datetime"),
                "raw_station_data": item
            }
            filtered_stations.append(parsed_record)

    return filtered_stations


def main():
    print(f"Fetching live canal/river telemetry from {CANAL_ENDPOINT_URL}...")
    diagnostic, raw_stations = fetch_live_canal_data(CANAL_ENDPOINT_URL)

    if not diagnostic["success"]:
        print(f"FAILED to fetch live data: {diagnostic['error']}")
        output_payload = {
            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
            "target_provinces": ["Bangkok", "Samut Prakan"],
            "diagnostic": diagnostic,
            "record_count": 0,
            "stations": []
        }
    else:
        filtered = parse_bkk_samutprakan_stations(raw_stations)
        print(f"Successfully fetched live data. Found {len(filtered)} stations in Bangkok and Samut Prakan.")
        
        output_payload = {
            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
            "target_provinces": ["Bangkok", "Samut Prakan"],
            "diagnostic": diagnostic,
            "total_raw_stations": len(raw_stations),
            "record_count": len(filtered),
            "stations": filtered
        }

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(output_payload, f, indent=2, ensure_ascii=False)

    print(f"Data saved to '{OUTPUT_FILE}'.")


if __name__ == "__main__":
    main()
