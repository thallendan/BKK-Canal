#!/usr/bin/env python3
"""
fetch_practice_khlongmap.py

Probes, scrapes, and dumps real-time telemetry from BMA DDS KlongMap & Canal Portals:
1. BMA KlongMap Main (https://weather.bangkok.go.th/KlongMap)
2. BMA Water Portal Main (https://weather.bangkok.go.th/water/)
3. BMA Canal Flow Portal Main (https://weather.bangkok.go.th/flow/)
4. BMA Road Flood Telemetry (https://weather.bangkok.go.th/flood/)
5. Local Station Detail Telemetry (Khlong Bang Na Sukhumvit, Srinagarindra, Bangna-Trad, etc.)

Extracts:
- Water level elevations (m MSL) inside and outside gates
- Pump operational states (Running vs. Standby)
- Flow discharge rate (m3/s) and stream velocity (m/s)
- 5-minute historical timeseries tables

Writes output strictly to 'data_practice_khlongmap.json' with diagnostic metadata.
Never generates mock or simulated data if endpoints fail.
"""

import json
import re
import ssl
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone

OUTPUT_FILE = "data_practice_khlongmap.json"

ENDPOINTS = [
    {
        "key": "bma_klongmap_main",
        "name": "BMA DDS KlongMap Flow Portal",
        "url": "https://weather.bangkok.go.th/KlongMap"
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
        "name": "BMA DDS Roadside Flood Telemetry",
        "url": "https://weather.bangkok.go.th/flood/"
    },
    {
        "key": "st_bangna_srinagarindra",
        "name": "Khlong Bang Na (Srinagarindra Station Detail)",
        "url": "https://weather.bangkok.go.th/water/StationDetail?id=49"
    },
    {
        "key": "st_bangna_sukhumvit",
        "name": "Khlong Bang Na (Sukhumvit Station Detail)",
        "url": "https://weather.bangkok.go.th/water/StationDetail?id=237"
    },
    {
        "key": "st_bangna_trad_56",
        "name": "Khlong Bang Na (Bangna-Trad 56 Station Detail)",
        "url": "https://weather.bangkok.go.th/water/StationDetail?id=256"
    },
    {
        "key": "st_bangkok_yai",
        "name": "Khlong Bangkok Yai Outfall Station Detail",
        "url": "https://weather.bangkok.go.th/water/StationDetail?id=94"
    },
    {
        "key": "st_mahasawat",
        "name": "Khlong Maha Sawat Gate Station Detail",
        "url": "https://weather.bangkok.go.th/water/StationDetail?id=73"
    }
]


def clean_html_text(html_content: str) -> str:
    """Strips HTML tags, styles, scripts, and normalizes whitespace."""
    text = re.sub(r'<style[^>]*>.*?</style>', ' ', html_content, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r'<script[^>]*>.*?</script>', ' ', text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r'<[^>]+>', ' ', text)
    text = re.sub(r'&nbsp;', ' ', text)
    text = re.sub(r'\s+', ' ', text)
    return text.strip()


def parse_bma_water_main(body_text: str) -> dict:
    """Parses BMA water level monitoring table."""
    clean_text = clean_html_text(body_text)
    stations = []

    # Scrape pairs: [Station Name] [Current Level] [Bank Threshold]
    matches = re.findall(
        r'([\u0E00-\u0E7FA-Za-z0-9_.\-\s/]+?)\s*([-+]?\d+\.\d+)\s+([-+]?\d+\.\d+)',
        clean_text
    )

    for st_name, level_str, bank_str in matches:
        try:
            curr_level = float(level_str)
            bank_thresh = float(bank_str)
            stations.append({
                "station_name": st_name.strip(),
                "water_level_msl": curr_level,
                "bank_threshold_msl": bank_thresh,
                "buffer_remaining_meters": round(bank_thresh - curr_level, 2)
            })
        except ValueError:
            continue

    # Isolate Bangna / Samrong / Phra Khanong local focus
    target_kws = ["bangna", "บางนา", "samrong", "สำโรง", "ปลัดเปรียง", "พระโขนง"]
    local_focus = [s for s in stations if any(kw in s["station_name"].lower() for kw in target_kws)]

    return {
        "local_focus_stations": local_focus,
        "total_stations_scraped": len(stations),
        "all_stations_sample": stations[:25]
    }


def parse_bma_station_detail(body_text: str) -> dict:
    """Parses individual BMA StationDetail pages including water levels, pump states, and 5-min tables."""
    clean_text = clean_html_text(body_text)

    # 1. Extract Station Name & Canal Name
    title_match = re.search(r'สถานีวัดระดับน้ำ\s*-\s*([\u0E00-\u0E7F\sA-Za-z0-9_.-]+)', clean_text)
    station_title = title_match.group(1).strip() if title_match else "Unknown Station"

    # 2. Extract Pump Operational Status
    pumps_active = "เครื่องสูบน้ำกำลังทำงาน" in clean_text
    pumps_waiting = "เครื่องสูบน้ำรอทำงาน" in clean_text
    pump_status = "RUNNING" if pumps_active else ("STANDBY" if pumps_waiting else "N/A")

    # 3. Extract Headwater / Tailwater levels if available
    inner_level = None
    outer_level = None
    level_match = re.search(r'ระดับน้ำด้านใน\s*([-+]?\d+\.\d+)\s*ม\.รทก\.\s*ระดับน้ำด้านนอก\s*([-+]?\d+\.\d+)', clean_text)
    if level_match:
        inner_level = float(level_match.group(1))
        outer_level = float(level_match.group(2))

    # 4. Extract 5-minute Timeseries Table Samples
    time_series = []
    ts_matches = re.findall(
        r'(\d{2}/\d{2}/\d{4}\s+\d{2}:\d{2})\s+([-+]?\d+\.\d+|-)(?:\s+([-+]?\d+\.\d+|-))?',
        clean_text
    )
    for dt, val1, val2 in ts_matches[:10]:
        time_series.append({
            "datetime": dt,
            "level_m_msl": float(val1) if val1 and val1 != '-' else None,
            "secondary_level_m_msl": float(val2) if val2 and val2 != '-' else None
        })

    return {
        "station_title": station_title,
        "pump_status": pump_status,
        "headwater_inner_msl": inner_level,
        "tailwater_outer_msl": outer_level,
        "recent_5min_timeseries": time_series
    }


def parse_endpoint_content(key: str, body_text: str) -> dict:
    if key == "bma_water_main":
        return parse_bma_water_main(body_text)
    elif key.startswith("st_"):
        return parse_bma_station_detail(body_text)
    else:
        # General text extract for raw map dumps
        clean_text = clean_html_text(body_text)
        return {
            "raw_text_length": len(clean_text),
            "text_preview": clean_text[:500]
        }


def classify_format(content_type: str, body_text: str) -> str:
    text_head = body_text.strip()[:300].lower()
    if "text/html" in content_type.lower() or "<html" in text_head or "<!doctype html" in text_head:
        return "HTML Document (Web Report)"
    if "application/json" in content_type.lower() or (text_head.startswith("{") or text_head.startswith("[")):
        return "JSON Structured Data"
    return "Plain Text / Unformatted"


def fetch_endpoint(endpoint: dict) -> tuple[dict, dict]:
    url = endpoint["url"]
    name = endpoint["name"]
    key = endpoint["key"]
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
        "key": key,
        "name": name,
        "url": url,
        "success": False,
        "status_code": None,
        "content_type": "Unknown",
        "response_time_sec": None,
        "size_bytes": 0,
        "line_count": 0,
        "data_format": "N/A",
        "sample_preview": [],
        "error": None
    }

    parsed_data = {}

    try:
        with urllib.request.urlopen(req, context=ctx, timeout=20) as response:
            elapsed = round(time.time() - start_time, 3)
            status = response.status
            content_type = response.headers.get("Content-Type", "Unknown")
            raw_bytes = response.read()

            try:
                body_text = raw_bytes.decode("utf-8")
            except UnicodeDecodeError:
                body_text = raw_bytes.decode("latin-1", errors="replace")

            lines = body_text.splitlines()
            non_empty_lines = [line.strip() for line in lines if line.strip()]

            diagnostic["success"] = True
            diagnostic["status_code"] = status
            diagnostic["content_type"] = content_type
            diagnostic["response_time_sec"] = elapsed
            diagnostic["size_bytes"] = len(raw_bytes)
            diagnostic["line_count"] = len(lines)
            diagnostic["data_format"] = classify_format(content_type, body_text)
            diagnostic["sample_preview"] = non_empty_lines[:8]

            parsed_data = parse_endpoint_content(key, body_text)

    except urllib.error.HTTPError as e:
        diagnostic["status_code"] = e.code
        diagnostic["error"] = f"HTTP Error {e.code}: {e.reason}"
    except urllib.error.URLError as e:
        diagnostic["error"] = f"URL Connection Error: {e.reason}"
    except TimeoutError:
        diagnostic["error"] = "Connection timed out (20s limit)"
    except Exception as e:
        diagnostic["error"] = f"Fetch failed: {str(e)}"

    return diagnostic, parsed_data


def main():
    print(f"Fetching practice KlongMap & BMA canal data from {len(ENDPOINTS)} endpoints...")
    results = []
    parsed_summary = {}

    for ep in ENDPOINTS:
        print(f" -> Fetching {ep['name']} ({ep['url']})")
        diag, parsed = fetch_endpoint(ep)
        results.append(diag)
        if parsed:
            parsed_summary[ep["key"]] = parsed

    successful = sum(1 for r in results if r["success"])
    failed = len(results) - successful

    is_live = successful > 0
    status_code = "SUCCESS" if is_live else "FETCH_FAILED"
    timestamp_str = datetime.now(timezone.utc).isoformat()

    output_payload = {
        "timestamp_utc": timestamp_str,
        "updated_at_utc": timestamp_str,
        "is_live": is_live,
        "status": status_code,
        "total_endpoints": len(ENDPOINTS),
        "successful_count": successful,
        "failed_count": failed,
        "parsed_summary": parsed_summary,
        "results": results
    }

    if not is_live:
        output_payload["error_message"] = "Failed to connect to BMA KlongMap endpoints."

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(output_payload, f, indent=2, ensure_ascii=False)

    print(f"Completed fetch. {successful}/{len(ENDPOINTS)} endpoints succeeded. Saved to '{OUTPUT_FILE}'.")


if __name__ == "__main__":
    main()
