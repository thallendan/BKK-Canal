#!/usr/bin/env python3
"""
fetch_master_water_level.py
---------------------------
Aggregates hydrological telemetry from ThaiWater (HII), RID, and BMA DDS.
Outputs consolidated data to master_water_level_data.json.
"""

import json
import os
import re
import time
from datetime import datetime, timezone
import requests

# Standard Dam Capacity Baseline Reference (Million Cubic Meters - MCM)
DAM_CAPACITY_BASICS = {
    "bhumibol": 13462.0,
    "sirikit": 9510.0,
    "kwai_noi": 939.0,
    "pasak": 872.0,
    "srinagarind": 17745.0,
    "vajiralongkorn": 8860.0
}

DEFAULT_TIMEOUT = 12

def get_bma_headers(referer_path="flood"):
    return {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "X-Requested-With": "XMLHttpRequest",
        "Referer": f"https://weather.bangkok.go.th/{referer_path}/",
        "Accept": "*/*",
        "Accept-Language": "en-GB,en-US;q=0.9,en;q=0.8"
    }


def parse_dam_storage_html(html_text):
    """Parses RID/HII Dam report HTML and ensures capacities are populated."""
    dams_data = {
        "bhumibol": {"capacity_mcm": DAM_CAPACITY_BASICS["bhumibol"], "storage_mcm": None, "storage_pct": None, "usable_mcm": None},
        "sirikit": {"capacity_mcm": DAM_CAPACITY_BASICS["sirikit"], "storage_mcm": None, "storage_pct": None, "usable_mcm": None},
        "kwai_noi": {"capacity_mcm": DAM_CAPACITY_BASICS["kwai_noi"], "storage_mcm": None, "storage_pct": None, "usable_mcm": None},
        "pasak": {"capacity_mcm": DAM_CAPACITY_BASICS["pasak"], "storage_mcm": None, "storage_pct": None, "usable_mcm": None},
        "srinagarind": {"capacity_mcm": DAM_CAPACITY_BASICS["srinagarind"], "storage_mcm": None, "storage_pct": None, "usable_mcm": None},
        "vajiralongkorn": {"capacity_mcm": DAM_CAPACITY_BASICS["vajiralongkorn"], "storage_mcm": None, "storage_pct": None, "usable_mcm": None}
    }

    dam_patterns = {
        "bhumibol": [r"Bhumibol", r"ภูมิพล"],
        "sirikit": [r"Sirikit", r"สิริกิติ์"],
        "kwai_noi": [r"Kwai Noi", r"แควน้อย"],
        "pasak": [r"Pasak", r"ป่าสัก"],
        "srinagarind": [r"Srinagarind", r"ศรีนครินทร์"],
        "vajiralongkorn": [r"Vajiralongkorn", r"วชิราลงกรณ"]
    }

    for dam_key, patterns in dam_patterns.items():
        for pat in patterns:
            match = re.search(rf"{pat}.*?(\d[\d,]*\.?\d*).*?(\d[\d,]*\.?\d*)", html_text, re.IGNORECASE | re.DOTALL)
            if match:
                try:
                    val1 = float(match.group(1).replace(",", ""))
                    val2 = float(match.group(2).replace(",", ""))
                    
                    if val1 > val2 and val1 > 500:
                        cap = val1
                        stor = val2
                    else:
                        cap = DAM_CAPACITY_BASICS[dam_key]
                        stor = val1

                    pct = round((stor / cap) * 100.0, 1) if cap > 0 else 0.0
                    if not (0 < pct <= 110):
                        continue  # implausible match; leave as None
                    dams_data[dam_key] = {
                        "capacity_mcm": cap,
                        "storage_mcm": stor,
                        "storage_pct": pct,
                        "usable_mcm": max(0.0, stor - (cap * 0.1))
                    }
                    break
                except ValueError:
                    continue

    return dams_data


def main():
    session = requests.Session()
    
    # Endpoint definition matrix
    endpoints_to_fetch = [
        {
            "key": "waterlevel_thaiwater",
            "name": "Canal & River Water Levels (ThaiWater v3)",
            "url": "https://api-v3.thaiwater.net/api/v1/thaiwater30/public/waterlevel_load",
            "method": "GET",
            "headers": {"User-Agent": "Mozilla/5.0"}
        },
        {
            "key": "watergate_load",
            "name": "Watergate & Sluice Gate Load (ThaiWater v3)",
            "url": "https://api-v3.thaiwater.net/api/v1/thaiwater30/public/watergate_load",
            "method": "GET",
            "headers": {"User-Agent": "Mozilla/5.0"}
        },
        {
            "key": "estuary_tide",
            "name": "Chao Phraya Estuary Sea Level & Tide (Fort Phrachulachomklao)",
            "url": "https://tiwrmdev.hii.or.th/v3/sealevel",
            "method": "GET",
            "headers": {"User-Agent": "Mozilla/5.0"}
        },
        {
            "key": "dam_storage",
            "name": "Thailand Dam Storage Report (RID/HII)",
            "url": "https://tiwrmdev.hii.or.th/DATA/REPORT/php/rid_dam_1.php?lang=en",
            "method": "GET",
            "headers": {"User-Agent": "Mozilla/5.0"}
        },
        {
            "key": "chaophraya_compact",
            "name": "Chao Phraya Basin Compact Report",
            "url": "https://waterchart.thaiwater.net/basin/chaophraya",
            "method": "GET",
            "headers": {"User-Agent": "Mozilla/5.0"}
        },
        {
            "key": "chaophraya_full",
            "name": "Chao Phraya Basin Full Hydro Report",
            "url": "https://tiwrm.hii.or.th/DATA/REPORT/php/chart/chaopraya/2013/chaopraya.php",
            "method": "GET",
            "headers": {"User-Agent": "Mozilla/5.0"}
        },
        {
            "key": "chaophraya_small",
            "name": "Chao Phraya Basin Small Overview Chart",
            "url": "https://tiwrmdev.hii.or.th/DATA/REPORT/php/chart/chaopraya/small/chaopraya.php",
            "method": "GET",
            "headers": {"User-Agent": "Mozilla/5.0"}
        },
        {
            "key": "bma_roadside_flood",
            "name": "BMA DDS Roadside Flood Sensors (PageMap)",
            "url": "https://weather.bangkok.go.th/Flood/PageMap/GetData?id=0",
            "method": "GET",
            "headers": get_bma_headers("flood")
        },
        {
            "key": "bma_water_pagemap",
            "name": "BMA DDS Water Level Sensors (PageMap)",
            "url": "https://weather.bangkok.go.th/Water/PageMap/GetData",
            "method": "GET",
            "headers": get_bma_headers("water")
        },
        {
            "key": "bma_flow_pagemap",
            "name": "BMA DDS Canal Flow Metrics (PageMap)",
            "url": "https://weather.bangkok.go.th/Flow/PageMap/GetData",
            "method": "GET",
            "headers": get_bma_headers("flow")
        },
        {
            "key": "bma_flow_table",
            "name": "BMA DDS Canal Flow Data Table (PageMap)",
            "url": "https://weather.bangkok.go.th/Flow/PageMap/GetDataTable",
            "method": "GET",
            "headers": get_bma_headers("flow")
        }
    ]

    diagnostics = []
    parsed_summary = {}
    successful_count = 0
    failed_count = 0

    print(f"Starting master water level data acquisition across {len(endpoints_to_fetch)} endpoints...")

    for ep in endpoints_to_fetch:
        start_time = time.time()
        diag = {
            "key": ep["key"],
            "name": ep["name"],
            "url": ep["url"],
            "success": False,
            "status_code": None,
            "response_time_sec": 0.0,
            "error": None
        }

        try:
            res = session.request(
                method=ep["method"],
                url=ep["url"],
                headers=ep["headers"],
                timeout=DEFAULT_TIMEOUT
            )
            elapsed = round(time.time() - start_time, 3)
            diag["response_time_sec"] = elapsed
            diag["status_code"] = res.status_code

            if res.status_code == 200:
                diag["success"] = True
                successful_count += 1
                # Save raw page once so parsers can be written/debugged. Only when SAVE_RAW=1 (set in the GitHub workflow, not in Lambda)
                raw_names = {"chaophraya_full": "chaophraya_full_raw.html", "dam_storage": "rid_dam_raw.html", "estuary_tide": "estuary_raw.txt"}
                if os.environ.get("SAVE_RAW") == "1" and ep["key"] in raw_names and not os.path.exists(raw_names[ep["key"]]):
                    try:
                        with open(raw_names[ep["key"]], "w", encoding="utf-8") as rf:
                            rf.write(res.text)
                    except OSError as e:
                        print("could not save raw snapshot:", e)   # never let this break the data fetch
                
                # Dynamic parsing per endpoint response type
                if ep["key"] == "waterlevel_thaiwater":
                    data = res.json()
                    records = data.get("data", []) if isinstance(data, dict) else data
                    parsed_summary[ep["key"]] = {
                        "record_count": len(records),
                        "sample_record": records[0] if records else {}
                    }
                elif ep["key"] == "watergate_load":
                    data = res.json()
                    records = data.get("data", []) if isinstance(data, dict) else data
                    parsed_summary[ep["key"]] = {
                        "watergate_count": len(records) if isinstance(records, list) else 0,
                        "sample_watergate": records[0] if isinstance(records, list) and records else {}
                    }
                elif ep["key"] == "estuary_tide":
                    try:
                        data = res.json()
                    except ValueError:
                        parsed_summary[ep["key"]] = {"parse_error": "response was not JSON", "preview": re.sub(r"\s+", " ", res.text[:300]).strip()}
                        data = None
                    if data is not None:
                      parsed_summary[ep["key"]] = {
                        "realtime_glf001_msl": data.get("waterlevel_msl"),
                        "predicted_n03_bounds": data.get("tide_summary"),
                        "period": data.get("datetime")
                    }
                elif ep["key"] == "dam_storage":
                    parsed_summary[ep["key"]] = parse_dam_storage_html(res.text)
                elif ep["key"] == "bma_roadside_flood":
                    data = res.json()
                    tbl = data.get("dtTbl", [])
                    parsed_summary[ep["key"]] = {
                        "sensor_count": len(tbl),
                        "active_count": sum(1 for s in tbl if s.get("status") == 1),
                        "sample_sensor": tbl[0] if tbl else {}
                    }
                elif "bma_" in ep["key"]:
                    try:
                        data = res.json()
                        tbl = data.get("dtTbl", []) if isinstance(data, dict) else []
                        parsed_summary[ep["key"]] = {
                            "record_count": len(tbl),
                            "sample_record": tbl[0] if tbl else {}
                        }
                    except Exception:
                        parsed_summary[ep["key"]] = {
                            "text_length": len(res.text),
                            "preview": res.text[:200]
                        }
                else:
                    parsed_summary[ep["key"]] = {
                        "text_length": len(res.text),
                        "preview": re.sub(r'\s+', ' ', res.text[:200]).strip()
                    }
            else:
                diag["error"] = f"HTTP Error {res.status_code}: {res.reason}"
                failed_count += 1

        except Exception as err:
            elapsed = round(time.time() - start_time, 3)
            diag["response_time_sec"] = elapsed
            diag["error"] = str(err)
            failed_count += 1

        ps = parsed_summary.get(ep["key"], {})
        empty = (ps.get("record_count") == 0 or ps.get("watergate_count") == 0 or "parse_error" in ps
                 or (ep["key"] == "dam_storage" and all(v["storage_pct"] is None for v in ps.values())))
        diag["data_ok"] = bool(diag["success"] and not empty and not diag.get("error"))  # HTTP 200 is not the same as usable data
        diagnostics.append(diag)
        print(f"[{'OK' if diag['data_ok'] else ('EMPTY' if diag['success'] else 'FAIL')}] {ep['name']} -> Code {diag['status_code']} ({diag['response_time_sec']}s)")

    # Construct Master Data Payload
    master_payload = {
        "master_type": "WATER_LEVEL_AND_HYDROLOGICAL_TELEMETRY",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "total_endpoints": len(endpoints_to_fetch),
        "successful_count": successful_count,
        "failed_count": failed_count,
        "parsed_summary": parsed_summary,
        "endpoint_diagnostics": diagnostics
    }

    output_filename = "master_water_level_data.json"
    with open(output_filename, "w", encoding="utf-8") as f:
        json.dump(master_payload, f, indent=2, ensure_ascii=False)

    print(f"\nMaster water level acquisition complete. Summary saved to {output_filename}.")

if __name__ == "__main__":
    main()
