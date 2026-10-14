#!/usr/bin/env python3
import json
import logging
from datetime import datetime, timezone
import requests

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

API_URL = "https://api-v3.thaiwater.net/api/v1/thaiwater30/public/waterlevel_load"
OUTPUT_FILE = "bkk_samutprakan_canals.json"

# Province codes for Bangkok (10) and Samut Prakan (11)
TARGET_PROVINCES = {"10": "Bangkok", "11": "Samut Prakan"}

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

def fetch_water_levels():
    logging.info(f"Fetching water level data from {API_URL}")
    try:
        response = requests.get(API_URL, headers=HEADERS, timeout=30)
        response.raise_for_status()
        payload = response.json()
    except Exception as err:
        logging.error(f"Failed to fetch data: {err}")
        return None

    waterlevel_list = payload.get("data", {}).get("waterlevel_data", {}).get("data", [])
    logging.info(f"Total stations returned by API: {len(waterlevel_list)}")

    filtered_stations = []
    
    for item in waterlevel_list:
        geocode = item.get("geocode", {})
        prov_code = str(geocode.get("province_code", ""))
        
        if prov_code in TARGET_PROVINCES:
            station_info = item.get("station", {})
            agency_info = item.get("agency", {})
            basin_info = item.get("basin", {})

            record = {
                "id": item.get("id"),
                "station_id": station_info.get("id"),
                "station_name_th": station_info.get("tele_station_name", {}).get("th") if isinstance(station_info.get("tele_station_name"), dict) else station_info.get("tele_station_name"),
                "station_name_en": station_info.get("tele_station_name", {}).get("en") if isinstance(station_info.get("tele_station_name"), dict) else None,
                "river_or_canal_name": item.get("river_name"),
                "province_code": prov_code,
                "province_en": TARGET_PROVINCES[prov_code],
                "province_th": geocode.get("province_name", {}).get("th"),
                "district_th": geocode.get("amphoe_name", {}).get("th"),
                "subdistrict_th": geocode.get("tumbon_name", {}).get("th"),
                "latitude": station_info.get("tele_station_lat"),
                "longitude": station_info.get("tele_station_long"),
                "waterlevel_datetime": item.get("waterlevel_datetime"),
                "waterlevel_msl": item.get("waterlevel_msl"),
                "diff_wl_bank": item.get("diff_wl_bank"),
                "diff_wl_bank_text": item.get("diff_wl_bank_text"),
                "situation_level": item.get("situation_level"),
                "min_bank": station_info.get("min_bank"),
                "agency_short": agency_info.get("agency_shortname", {}).get("en"),
                "basin_en": basin_info.get("basin_name", {}).get("en")
            }
            filtered_stations.append(record)

    logging.info(f"Found {len(filtered_stations)} target canal/river stations in BKK and Samut Prakan.")

    output_data = {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "target_provinces": list(TARGET_PROVINCES.values()),
        "record_count": len(filtered_stations),
        "stations": filtered_stations
    }

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(output_data, f, ensure_ascii=False, indent=2)

    logging.info(f"Successfully saved data to {OUTPUT_FILE}")

if __name__ == "__main__":
    fetch_water_levels()
