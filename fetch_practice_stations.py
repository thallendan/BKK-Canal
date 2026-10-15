#!/usr/bin/env python3
"""
fetch_practice_stations.py

Fetches live data from Chao Phraya basin telemetry endpoints:
1. Chao Phraya basin compact (https://waterchart.thaiwater.net/basin/chaophraya)
2. Chao Phraya basin full (https://tiwrm.hii.or.th/DATA/REPORT/php/chart/chaopraya/2013/chaopraya.php)

Saves diagnostic and parsed telemetry output strictly to 'data_practice_stations.json'.
Never simulates or generates mock data if endpoints fail.
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


def classify_format(content_type: str, body_text: str) -> str:
    text_head = body_text.strip()[:300].lower()
    if "text/html" in content_type.lower() or "<html" in text_head or "<!doctype html" in text_head:
        return "HTML Document (Web Report)"
    if "application/json" in content_type.lower() or (text_head.startswith("{") or text_head.startswith("[")):
        return "JSON Structured Data"
    return "Plain Text / Unformatted"


def parse_html_content(key: str, body_text: str) -> dict:
    """Extracts summary telemetry readings from HTML pages where available."""
    parsed = {}

    if key == "chaophraya_compact":
        # Extract station water level / flow matches (e.g., msl or cms readings)
        matches = re.findall(r'([\u0E00-\u0E7FA-Za-z0-9_.\-\s]+)\s+(msl|cms)\s+([-+]?\d*\.?\d+)', body_text)
        if matches:
            parsed["sample_readings_count"] = len(matches)
            parsed["sample_readings"] = [
                {"location": m[0].strip(), "unit": m[1], "value": m[2]}
                for m in matches[:10]
            ]
    elif key == "chaophraya_full":
        # Extract regulator ATG identifiers or dam tags
        atg_matches = re.findall(r'(ATG\d+|ปตร\.[^\s<]+)', body_text)
        if atg_matches:
            parsed["regulators_found"] = sorted(list(set(atg_matches)))[:15]

    return parsed


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

            parsed_data = parse_html_content(key, body_text)

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
