#!/usr/bin/env python3
"""
fetch_practice_canal.py

Fetches live canal and river water level telemetry from ThaiWater (HII API v3).
Parses station data across both raw API payloads and diagnostic file wrappers,
filters specifically for Bangkok and Samut Prakan waterways, and exports
standardized station metrics to 'bkk_samutprakan_canals.json'.

If the live fetch fails, it records the exact error diagnostic without
simulating or generating fake data.
"""

import json
import ssl
import time
import urllib.request
import urllib.error
from datetime import datetime, timezone

# Primary and fallback endpoints for ThaiWater public water level telemetry
PRIMARY_CANAL_ENDPOINT = "https://api-v3.thaiwater.net/api/v1/thaiwater30/public/waterlevel_load"
FALLBACK_CANAL_ENDPOINT = "https://api-v3.thaiwater.net/api/v1/thaiwater30/public/waterlevel"
OUTPUT_FILE = "bkk_samutprakan_canals.json"

TARGET_PROVINCES = {"Bangkok", "Samut Prakan", "กรุงเทพมหานคร", "สมุทรปราการ"}


def extract_raw_station_list(payload: dict) -> list:
    """
    Extracts the station array flexibly, handling both direct live API
    payloads and wrapped diagnostic file formats.
    """
    if not isinstance(payload, dict):
        return []

    # 1. Direct Live API response: payload["waterlevel_data"]["data"]
    if "waterlevel_data" in payload and isinstance(payload["waterlevel_data"], dict):
        return payload["waterlevel_data"].get("data", [])

    # 2. Wrapped diagnostic file format: payload["data"]["waterlevel_data"]["data"]
    if "data" in payload and isinstance(payload["data"], dict):
        inner_data = payload["data"]
        if "waterlevel_data" in inner_data and isinstance(inner_data["waterlevel_data"], dict):
            return inner_data["waterlevel_data"].get("data", [])

    # 3. Standard list payload fallback
    if isinstance(payload.get("data"), list):
        return payload["data"]

    return []


def fetch_endpoint_json(url: str) -> tuple[dict, list]:
    """
    Fetches JSON from an endpoint and returns diagnostic information
    along with parsed station objects.
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

            diagnostic["status_code"] = status
            diagnostic["response_time_sec"] = elapsed

            payload = json.loads(raw_bytes.decode("utf-8"))
            station_list = extract_raw_station_list(payload)

            if station_list:
                diagnostic["success"] = True
                return diagnostic, station_list
            else:
                diagnostic["error"] = "HTTP 200 OK received, but station array was empty or structure unparseable."
                return diagnostic, []

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
    Filters raw telemetry records for Bangkok and Samut Prakan stations.
    """
    filtered_stations = []

    for item in raw_stations:
        geocode = item.get("geocode", {})
        prov_obj = geocode.get("province_name", {})

        prov_en = prov_obj.get("en") if isinstance(prov_obj, dict) else None
        prov_th = prov_obj.get("th") if isinstance(prov_obj, dict) else None

        if prov_en in TARGET_PROVINCES or prov_th in TARGET_PROVINCES:
            station_info = item.get("station", {})
            station_name_obj = station_info.get("tele_station_name", {})

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
    print(f"Fetching live canal/river telemetry from primary endpoint: {PRIMARY_CANAL_ENDPOINT}")
    diagnostic, raw_stations = fetch_endpoint_json(PRIMARY_CANAL_ENDPOINT)

    # Secondary fallback attempt if primary endpoint yields no stations
    if not diagnostic["success"] or not raw_stations:
        print(f"Primary endpoint failed or returned no stations. Attempting fallback: {FALLBACK_CANAL_ENDPOINT}")
        fb_diagnostic, fb_stations = fetch_endpoint_json(FALLBACK_CANAL_ENDPOINT)
        if fb_diagnostic["success"] and fb_stations:
            diagnostic, raw_stations = fb_diagnostic, fb_stations

    if not diagnostic["success"] or not raw_stations:
        print(f"FAILED to fetch live canal data: {diagnostic['error']}")
        output_payload = {
            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
            "target_provinces": ["Bangkok", "Samut Prakan"],
            "diagnostic": diagnostic,
            "total_raw_stations": 0,
            "record_count": 0,
            "stations": []
        }
    else:
        filtered = parse_bkk_samutprakan_stations(raw_stations)
        print(f"Successfully fetched live data. Found {len(filtered)} stations in Bangkok and Samut Prakan out of {len(raw_stations)} total raw stations.")

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

    print(f"Data saved strictly to '{OUTPUT_FILE}'.")


if __name__ == "__main__":
    main()
