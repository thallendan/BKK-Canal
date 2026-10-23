#!/usr/bin/env python3
"""
fetch_master_water_level.py

Master fetch script for all water level, river discharge, canal telemetry, 
dam storage, estuary tides, watergate loads, and road flood sensors.

Endpoints Covered:
1. Canal & River Water Levels (Primary & Fallback) - ThaiWater v3
2. Watergate & Sluice Gate Load - ThaiWater v3
3. Chao Phraya Estuary Sea Level & Tide - HII / Navy
4. Thailand Dam Storage Report - RID / HII
5. Chao Phraya Basin Compact Report - ThaiWater / HII
6. Chao Phraya Basin Full Hydro Report - HII
7. Chao Phraya Basin Small Overview Chart - HII
8. BMA DDS Direct Telemetry API - Bangkok DDS
9. BMA DDS Water Level Monitoring Main - Bangkok DDS
10. BMA DDS Canal Flow & Velocity Main - Bangkok DDS
11. BMA Roadside Flood Telemetry Main - Bangkok DDS
12. BMA DDS Individual Station Details - Bangkok DDS

*(Note: BMA DDS KlongMap Flow Portal Main is intentionally excluded as specified)*

Saves output strictly to 'master_water_level_data.json'.
Handles endpoint failures gracefully without generating mock data.
"""

import json
import re
import ssl
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone

OUTPUT_FILE = "master_water_level_data.json"

PRIMARY_CANAL_ENDPOINT = "https://api-v3.thaiwater.net/api/v1/thaiwater30/public/waterlevel_load"
FALLBACK_CANAL_ENDPOINT = "https://api-v3.thaiwater.net/api/v1/thaiwater30/public/waterlevel"

ENDPOINTS = [
    {
        "key": "waterlevel_thaiwater",
        "name": "Canal & River Water Levels (ThaiWater v3)",
        "url": PRIMARY_CANAL_ENDPOINT
    },
    {
        "key": "watergate_load",
        "name": "Watergate & Sluice Gate Load (ThaiWater v3)",
        "url": "https://api-v3.thaiwater.net/api/v1/thaiwater30/public/watergate_load"
    },
    {
        "key": "estuary_tide",
        "name": "Chao Phraya Estuary Sea Level & Tide (Fort Phrachulachomklao)",
        "url": "https://tiwrmdev.hii.or.th/v3/sealevel"
    },
    {
        "key": "dam_storage",
        "name": "Thailand Dam Storage Report (RID/HII)",
        "url": "https://tiwrmdev.hii.or.th/DATA/REPORT/php/rid_dam_1.php?lang=en"
    },
    {
        "key": "chaophraya_compact",
        "name": "Chao Phraya Basin Compact Report",
        "url": "https://waterchart.thaiwater.net/basin/chaophraya"
    },
    {
        "key": "chaophraya_full",
        "name": "Chao Phraya Basin Full Hydro Report",
        "url": "https://tiwrm.hii.or.th/DATA/REPORT/php/chart/chaopraya/2013/chaopraya.php"
    },
    {
        "key": "chaophraya_small",
        "name": "Chao Phraya Basin Small Overview Chart",
        "url": "https://tiwrmdev.hii.or.th/DATA/REPORT/php/chart/chaopraya/small/chaopraya.php"
    },
    {
        "key": "bma_direct_api",
        "name": "BMA DDS Direct Telemetry API",
        "url": "https://weather.bangkok.go.th/Klongmap/GetDataForUpdate"
    },
    {
        "key": "bma_water_main",
        "name": "BMA DDS Water Level Monitoring Main",
        "url": "https://weather.bangkok.go.th/water/"
    },
    {
        "key": "bma_flow_main",
        "name": "BMA DDS Canal Flow & Velocity Main",
        "url": "https://weather.bangkok.go.th/flow/"
    },
    {
        "key": "bma_flood_main",
        "name": "BMA Roadside Flood Telemetry Main",
        "url": "https://weather.bangkok.go.th/flood/"
    },
    {
        "key": "bma_station_detail_49",
        "name": "BMA DDS Individual Station Details (Khlong Bang Na Srinagarindra)",
        "url": "https://weather.bangkok.go.th/water/StationDetail?id=49"
    },
    {
        "key": "bma_station_detail_237",
        "name": "BMA DDS Individual Station Details (Khlong Bang Na Sukhumvit)",
        "url": "https://weather.bangkok.go.th/water/StationDetail?id=237"
    }
]


def create_ssl_context():
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    return ctx


def http_get(url: str, timeout: int = 20) -> tuple[str | None, int | None, str | None]:
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ),
        "Accept": "application/json, text/plain, text/html, */*"
    }
    req = urllib.request.Request(url, headers=headers)
    ctx = create_ssl_context()
    try:
        with urllib.request.urlopen(req, context=ctx, timeout=timeout) as response:
            raw = response.read()
            try:
                text = raw.decode("utf-8")
            except UnicodeDecodeError:
                text = raw.decode("latin-1", errors="replace")
            return text, response.status, None
    except urllib.error.HTTPError as e:
        return None, e.code, f"HTTP Error {e.code}: {e.reason}"
    except urllib.error.URLError as e:
        return None, None, f"URL Error: {e.reason}"
    except Exception as e:
        return None, None, f"Fetch failed: {str(e)}"


def clean_html_text(html_content: str) -> str:
    text = re.sub(r'<style[^>]*>.*?</style>', ' ', html_content, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r'<script[^>]*>.*?</script>', ' ', text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r'<[^>]+>', ' ', text)
    text = re.sub(r'&nbsp;', ' ', text)
    text = re.sub(r'\s+', ' ', text)
    return text.strip()


# -------------------------------------------------------------------
# Specialized Parsers
# -------------------------------------------------------------------
def parse_waterlevel_thaiwater(body_text: str) -> dict:
    try:
        data = json.loads(body_text)
        records = []
        if isinstance(data, dict):
            records = data.get("data", []) or data.get("waterlevel_data", {}).get("data", [])
        elif isinstance(data, list):
            records = data
        return {
            "record_count": len(records),
            "sample_record": records[0] if records else {}
        }
    except Exception as e:
        return {"error": str(e)}


def parse_watergate_load(body_text: str) -> dict:
    try:
        data = json.loads(body_text)
        records = data.get("data", []) if isinstance(data, dict) else data
        return {
            "watergate_count": len(records) if isinstance(records, list) else 0,
            "sample_watergate": records[0] if isinstance(records, list) and records else {}
        }
    except Exception as e:
        return {"error": str(e)}


def parse_estuary_tide(body_text: str) -> dict:
    res = {"realtime_glf001_msl": None, "predicted_n03_bounds": "N/A"}
    clean_html = body_text.replace("&nbsp;", " ")
    glf_match = re.search(r'<tr[^>]*rel="GLF001"[^>]*>(.*?)</tr>', clean_html, re.DOTALL | re.IGNORECASE)
    if glf_match:
        tds = re.findall(r'<td[^>]*>(.*?)</td>', glf_match.group(1), re.DOTALL | re.IGNORECASE)
        td_clean = [re.sub(r'<[^>]+>', '', td).strip() for td in tds]
        if len(td_clean) >= 5:
            try:
                res["realtime_glf001_msl"] = float(td_clean[4])
                res["period"] = f"{td_clean[2]} {td_clean[3]}"
            except ValueError:
                pass

    n03_match = re.search(r'<tr[^>]*rel="N03"[^>]*>(.*?)</tr>', clean_html, re.DOTALL | re.IGNORECASE)
    if n03_match:
        tds = re.findall(r'<td[^>]*>(.*?)</td>', n03_match.group(1), re.DOTALL | re.IGNORECASE)
        td_clean = [re.sub(r'<[^>]+>', ' ', td).strip() for td in tds]
        if len(td_clean) >= 3:
            res["predicted_n03_bounds"] = f"Max: {td_clean[1]} | Min: {td_clean[2]}"
    return res


def parse_dam_storage(body_text: str) -> dict:
    target_dams = {
        "bhumibol": ["bhumibol", "bhumipol", "ภูมิพล"],
        "sirikit": ["sirikit", "สิริกิติ์"],
        "kwai_noi": ["kheaw noi", "kwai noi", "kwae noi", "แควน้อย"],
        "pasak": ["pa sak jorasit", "pasak", "pa sak", "ป่าสัก"],
        "srinagarind": ["srinakarin", "srinagarind", "ศรีนครินทร์"],
        "vajiralongkorn": ["wachiralongkorn", "vajiralongkorn", "วชิราลงกรณ"]
    }
    clean_html = body_text.replace("&nbsp;", " ").replace("<tr", " \n<tr")
    parsed = {}
    for line in clean_html.splitlines():
        plain = " ".join(re.sub(r"<[^>]+>", " ", line).split()).lower()
        if not plain:
            continue
        for dam_key, kws in target_dams.items():
            if dam_key not in parsed and any(kw in plain for kw in kws):
                matches = re.findall(r'[-+]?\d+(?:,\d{3})*(?:\.\d+)?', line)
                nums = [float(m.replace(",", "")) for m in matches if m.replace(",", "").replace(".", "", 1).isdigit()]
                if len(nums) >= 5:
                    parsed[dam_key] = {
                        "capacity_mcm": nums[0],
                        "storage_mcm": nums[2],
                        "storage_pct": nums[3],
                        "usable_mcm": nums[4]
                    }
    return parsed


def parse_bma_direct_api(body_text: str) -> dict:
    try:
        data = json.loads(body_text)
        water_stations = data.get("waterStation", [])
        river_maps = data.get("riverMap", [])
        return {
            "total_water_stations": len(water_stations),
            "total_river_maps": len(river_maps),
            "sample_station": water_stations[0] if water_stations else {}
        }
    except Exception as e:
        return {"error": str(e)}


def parse_bma_station_detail(body_text: str) -> dict:
    clean_text = clean_html_text(body_text)
    title_match = re.search(r'สถานีวัดระดับน้ำ\s*-\s*([฀-๿\sA-Za-z0-9_.-]+)', clean_text)
    station_title = title_match.group(1).strip() if title_match else "Unknown Station"
    pumps_active = "เครื่องสูบน้ำกำลังทำงาน" in clean_text
    pump_status = "RUNNING" if pumps_active else "STANDBY"
    return {
        "station_title": station_title,
        "pump_status": pump_status,
        "clean_text_length": len(clean_text)
    }


def parse_endpoint(key: str, body_text: str) -> dict:
    if key == "waterlevel_thaiwater":
        return parse_waterlevel_thaiwater(body_text)
    elif key == "watergate_load":
        return parse_watergate_load(body_text)
    elif key == "estuary_tide":
        return parse_estuary_tide(body_text)
    elif key == "dam_storage":
        return parse_dam_storage(body_text)
    elif key == "bma_direct_api":
        return parse_bma_direct_api(body_text)
    elif key.startswith("bma_station_detail"):
        return parse_bma_station_detail(body_text)
    else:
        clean_text = clean_html_text(body_text)
        return {
            "text_length": len(clean_text),
            "preview": clean_text[:300]
        }


def main():
    print(f"Executing Master Water Level Telemetry Fetch across {len(ENDPOINTS)} endpoints...")
    start_time = time.time()
    results = []
    parsed_summary = {}

    for ep in ENDPOINTS:
        print(f" -> Fetching {ep['name']} ({ep['url']})...")
        t0 = time.time()
        body_text, status, err = http_get(ep["url"])

        # Fallback check for ThaiWater primary water level endpoint
        if ep["key"] == "waterlevel_thaiwater" and not body_text:
            print(f"    Primary failed. Attempting fallback: {FALLBACK_CANAL_ENDPOINT}")
            body_text, status, err = http_get(FALLBACK_CANAL_ENDPOINT)

        elapsed = round(time.time() - t0, 3)

        diag = {
            "key": ep["key"],
            "name": ep["name"],
            "url": ep["url"],
            "success": body_text is not None,
            "status_code": status,
            "response_time_sec": elapsed,
            "error": err
        }

        if body_text:
            parsed = parse_endpoint(ep["key"], body_text)
            if parsed:
                parsed_summary[ep["key"]] = parsed

        results.append(diag)

    successful = sum(1 for r in results if r["success"])
    failed = len(results) - successful
    timestamp_str = datetime.now(timezone.utc).isoformat()

    output_payload = {
        "master_type": "WATER_LEVEL_AND_HYDROLOGICAL_TELEMETRY",
        "timestamp_utc": timestamp_str,
        "total_endpoints": len(ENDPOINTS),
        "successful_count": successful,
        "failed_count": failed,
        "parsed_summary": parsed_summary,
        "endpoint_diagnostics": results
    }

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(output_payload, f, indent=2, ensure_ascii=False)

    print(f"Completed in {round(time.time() - start_time, 2)}s. {successful}/{len(ENDPOINTS)} succeeded.")
    print(f"Results saved strictly to '{OUTPUT_FILE}'.")


if __name__ == "__main__":
    main()
