#!/usr/bin/env python3
"""
fetch_practice_canals.py

Fetches live water level data for canals and water stations from the ThaiWater v3 API
('https://api-v3.thaiwater.net/api/v1/thaiwater30/public/waterlevel_load')
and dumps the response payload along with diagnostic metadata to 'data_practice_canals.json'.

If the API request fails, error diagnostic metadata is recorded and no simulated
or mock data is generated.
"""

import json
import ssl
import time
import urllib.request
import urllib.error
from datetime import datetime, timezone

TARGET_URL = "https://api-v3.thaiwater.net/api/v1/thaiwater30/public/waterlevel_load"
OUTPUT_FILE = "data_practice_canals.json"


def fetch_canal_water_levels():
    start_time = time.time()

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
        "Accept": "application/json, text/plain, */*"
    }

    req = urllib.request.Request(TARGET_URL, headers=headers)
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE

    payload = {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "url": TARGET_URL,
        "success": False,
        "status_code": None,
        "response_time_sec": None,
        "record_count": 0,
        "error": None,
        "data": None
    }

    try:
        with urllib.request.urlopen(req, context=ctx, timeout=30) as response:
            elapsed = round(time.time() - start_time, 3)
            payload["status_code"] = response.status
            payload["response_time_sec"] = elapsed

            raw_bytes = response.read()
            try:
                body_text = raw_bytes.decode("utf-8")
            except UnicodeDecodeError:
                body_text = raw_bytes.decode("latin-1", errors="replace")

            parsed_data = json.loads(body_text)

            payload["success"] = True
            payload["data"] = parsed_data

            if isinstance(parsed_data, list):
                payload["record_count"] = len(parsed_data)
            elif isinstance(parsed_data, dict):
                data_field = parsed_data.get("data")
                payload["record_count"] = len(data_field) if isinstance(data_field, list) else len(parsed_data)

    except urllib.error.HTTPError as e:
        payload["status_code"] = e.code
        payload["error"] = f"HTTP Error {e.code}: {e.reason}"
    except urllib.error.URLError as e:
        payload["error"] = f"URL Connection Error: {e.reason}"
    except TimeoutError:
        payload["error"] = "Connection timed out (30s limit)"
    except Exception as e:
        payload["error"] = f"Fetch or JSON parsing failed: {str(e)}"

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)

    print(f"Fetch completed. Success={payload['success']}, Records={payload['record_count']}. Saved to {OUTPUT_FILE}.")


if __name__ == "__main__":
    fetch_canal_water_levels()
