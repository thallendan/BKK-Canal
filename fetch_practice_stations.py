#!/usr/bin/env python3
"""
fetch_practice_stations.py

Fetches live weather and hydrological telemetry from two Chao Phraya basin web portals:
1. Chao Phraya basin compact (https://waterchart.thaiwater.net/basin/chaophraya)
2. Chao Phraya basin full (https://tiwrm.hii.or.th/DATA/REPORT/php/chart/chaopraya/2013/chaopraya.php)

Scrapes, extracts, and structures:
- Dam storage volume (MCM), percentage (%), daily inflow, and discharge
- Sluice gate headwater vs. tailwater levels (m MSL) & flow discharge (m3/s)
- Regional river/canal monitoring stations (BKK, CPY, GLF, ATG series)
- Hydrological transit lag times between basin nodes

Writes strictly to 'data_practice_stations.json' with full diagnostic logging.
Never generates mock or simulated data if endpoints fail.
"""

import json
import re
import ssl
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone

OUTPUT_FILE = "data_practice_stations.json"

ENDPOINTS = [
    {
        "key": "chaophraya_compact",
        "name": "Chao Phraya Basin Compact",
        "url": "https://waterchart.thaiwater.net/basin/chaophraya"
    },
    {
        "key": "chaophraya_full",
        "name": "Chao Phraya Basin Full",
        "url": "https://tiwrm.hii.or.th/DATA/REPORT/php/chart/chaopraya/2013/chaopraya.php"
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


def parse_chaophraya_compact(body_text: str) -> dict:
    """Extracts reservoirs, water gates, regional stations, and transit lag times."""
    clean_text = clean_html_text(body_text)

    # 1. Dam and Reservoir Storage Metrics
    dams = []
    dam_pattern = re.compile(
        r'(เขื่อน[\u0E00-\u0E7F\s]+?)\s*([\d\.,]+)\s*ล้าน\.\s*ลบ\.ม\.\s*\(\s*([\d\.]+)%\s*\)'
        r'(?:\s*ไหลลง\s*([\d\.,]+))?(?:\s*ระบาย\s*([\d\.,]+))?'
    )
    for m in dam_pattern.finditer(clean_text):
        dams.append({
            "dam_name": m.group(1).strip(),
            "storage_mcm": float(m.group(2).replace(',', '')),
            "storage_pct": float(m.group(3)),
            "inflow_mcm": float(m.group(4).replace(',', '')) if m.group(4) else None,
            "discharge_mcm": float(m.group(5).replace(',', '')) if m.group(5) else None
        })

    # 2. Water Control Gates & Sluice Gates (ปตร.)
    gates = []
    gate_pattern = re.compile(
        r'(ปตร\.[^\s<]+(?:\s+[^\s<]+)?)\s*(?:(ATG\d+))?\s*(?:(msl|cms))?\s*'
        r'([-+]?\d*\.?\d+|-)?\s*/\s*([-+]?\d*\.?\d+|-)?'
    )
    for m in gate_pattern.finditer(clean_text):
        name = m.group(1).strip()
        code = m.group(2)
        unit = m.group(3)
        val1 = m.group(4) if m.group(4) and m.group(4) != '-' else None
        val2 = m.group(5) if m.group(5) and m.group(5) != '-' else None

        gates.append({
            "gate_name": name,
            "code": code,
            "unit": unit,
            "headwater_level": float(val1) if val1 else None,
            "tailwater_level": float(val2) if val2 else None
        })

    # 3. Regional Canal & River Stations (BKK, CPY, GLF, THA, YOM, NAN, PIN, WAN)
    stations = []
    st_pattern = re.compile(
        r'\b(BKK\d+|CPY\d+|GLF\d+|THA\d+|YOM\d+|NAN\d+|PIN\d+|WAN\d+|LBI\d+|DIV\d+)\b'
        r'\s*([\u0E00-\u0E7F\sA-Za-z0-9_.-]*?)\s*(msl|cms)?\s*([-+]?\d*\.?\d+|-)?\s*/\s*([-+]?\d*\.?\d+|-)?'
    )
    for m in st_pattern.finditer(clean_text):
        st_id = m.group(1).strip()
        st_name = m.group(2).strip()
        unit = m.group(3)
        val1 = m.group(4) if m.group(4) and m.group(4) != '-' else None
        val2 = m.group(5) if m.group(5) and m.group(5) != '-' else None

        stations.append({
            "station_id": st_id,
            "station_name": st_name,
            "unit": unit,
            "water_level": float(val1) if val1 else None,
            "discharge": float(val2) if val2 else None
        })

    # 4. Hydrological Travel / Lag Times
    lag_times = re.findall(r'(\d+(?:\.\d+)?\s*(?:วัน|ชม\.))', clean_text)
    unique_lag_times = sorted(list(set(lag_times)))

    return {
        "dams": dams,
        "gates_and_regulators": gates,
        "monitoring_stations": stations,
        "transit_lag_times": unique_lag_times
    }


def parse_chaophraya_full(body_text: str) -> dict:
    """Extracts hardware ATG regulators, mainstem stations, and diversion flows."""
    clean_text = clean_html_text(body_text)

    # 1. Regulator ATG Sensor Hardware Network
    atg_regulators = []
    atg_pattern = re.compile(
        r'(ATG\d+)\s*(?:[\u0E00-\u0E7F\sA-Za-z0-9_.-]*?)\s*(?:(ปตร\.[^\s]+))?\s*'
        r'(?:([\d\.-]+)\s*msl)?\s*(?:([\d\.-]+)\s*msl)?\s*(?:([\d\.-]+)\s*cms)?',
        re.IGNORECASE
    )
    for m in atg_pattern.finditer(clean_text):
        code = m.group(1).upper()
        name = m.group(2) if m.group(2) else ""
        hw = m.group(3) if m.group(3) and m.group(3) != '-' else None
        tw = m.group(4) if m.group(4) and m.group(4) != '-' else None
        q = m.group(5) if m.group(5) and m.group(5) != '-' else None

        atg_regulators.append({
            "code": code,
            "gate_name": name,
            "headwater_msl": float(hw) if hw else None,
            "tailwater_msl": float(tw) if tw else None,
            "discharge_cms": float(q) if q else None
        })

    # 2. Mainstem Gauge Stations & Side Diversions
    gauges_and_diversions = []
    div_pattern = re.compile(
        r'\b(CPY\d+|BKK\d+|DIV\d+|Bang\s*Sai|บางไทร|ปากคลอง\d*|คลองผันน้ำ[^\s]+)\b'
        r'\s*([\u0E00-\u0E7F\sA-Za-z0-9_.-]*?)\s*(msl|cms)?\s*([-+]?\d*\.?\d+|-)?',
        re.IGNORECASE
    )
    for m in div_pattern.finditer(clean_text):
        id_tag = m.group(1).strip()
        name = m.group(2).strip()
        unit = m.group(3)
        val = m.group(4) if m.group(4) and m.group(4) != '-' else None

        gauges_and_diversions.append({
            "identifier": id_tag,
            "name": name,
            "unit": unit,
            "value": float(val) if val else None
        })

    return {
        "atg_regulators": atg_regulators,
        "gauges_and_diversions": gauges_and_diversions
    }


def parse_endpoint_content(key: str, body_text: str) -> dict:
    """Routes response content to the appropriate site parser."""
    if key == "chaophraya_compact":
        return parse_chaophraya_compact(body_text)
    elif key == "chaophraya_full":
        return parse_chaophraya_full(body_text)
    return {}


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
    print(f"Fetching practice station data from {len(ENDPOINTS)} Chao Phraya basin endpoints...")
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
        output_payload["error_message"] = "Failed to connect to practice Chao Phraya basin endpoints."

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(output_payload, f, indent=2, ensure_ascii=False)

    print(f"Completed fetch. {successful}/{len(ENDPOINTS)} endpoints succeeded. Saved to '{OUTPUT_FILE}'.")


if __name__ == "__main__":
    main()
