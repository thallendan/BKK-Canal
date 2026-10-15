#!/usr/bin/env python3
"""
fetch_macro.py

Macro Hydrological Aggregator for Greater Bangkok and Chao Phraya Basin.
Fetches live data across 5 primary sources:
1. Global Teleconnections (NOAA CPC / Australian BoM)
2. Headwater Reservoir Storage (HII / RID Dam Report)
3. Mainstem Chao Phraya Hydraulics & Flow Discharge (ThaiWater v3)
4. Nationwide & Local Rainfall Telemetry (ThaiWater v3)
5. Estuary Sea Level & Tide Extremes (HII / Fort Phrachulachomklao)

Outputs strictly to 'macro_data.json'. Handles missing endpoints without data simulation.
"""

import json
import re
import ssl
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone

OUTPUT_FILE = "macro_data.json"

# Endpoints
URL_ENSO = "https://www.cpc.ncep.noaa.gov/data/indices/sstoi.indices"
URL_MJO = "https://www.bom.gov.au/clim_data/IDCKGEM000/rmm.74toRealtime.txt"
URL_IOD = "https://psl.noaa.gov/data/timeseries/month/data/dmi.had.long.data"
URL_HEAT = "https://www.cpc.ncep.noaa.gov/products/analysis_monitoring/ocean/index/heat_content_index.txt"
URL_DAMS = "https://tiwrmdev.hii.or.th/DATA/REPORT/php/rid_dam_1.php?lang=en"
URL_TIDE = "https://tiwrmdev.hii.or.th/v3/sealevel"
URL_RIVER = "https://api-v3.thaiwater.net/api/v1/thaiwater30/public/waterlevel_load"
URL_RAIN = "https://api-v3.thaiwater.net/api/v1/thaiwater30/public/rain_24h"


def create_ssl_context():
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    return ctx


def http_get(url, timeout=20):
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
                return raw.decode("utf-8"), response.status
            except UnicodeDecodeError:
                return raw.decode("latin-1", errors="replace"), response.status
    except Exception as e:
        return None, str(e)


# -------------------------------------------------------------------
# 1. Macro Climate Teleconnections Parser
# -------------------------------------------------------------------
def fetch_teleconnections():
    tc = {"enso": None, "mjo_phase": None, "mjo_amp": None, "iod": None, "heat_content": None, "status": "SUCCESS"}
    
    # ENSO
    enso_raw, _ = http_get(URL_ENSO)
    if enso_raw:
        lines = [l.strip() for l in enso_raw.splitlines() if l.strip() and not l.startswith("YR")]
        if lines:
            parts = lines[-1].split()
            if len(parts) >= 10:
                try: tc["enso"] = float(parts[9])
                except ValueError: pass

    # MJO
    mjo_raw, _ = http_get(URL_MJO)
    if mjo_raw:
        lines = [l.strip() for l in mjo_raw.splitlines() if l.strip() and not l.startswith("RMM") and not l.startswith("year")]
        for l in reversed(lines):
            parts = l.split()
            if len(parts) >= 7 and parts[5] != "999":
                try:
                    tc["mjo_phase"] = int(parts[5])
                    tc["mjo_amp"] = float(parts[6])
                    break
                except ValueError: pass

    # IOD
    iod_raw, _ = http_get(URL_IOD)
    if iod_raw:
        lines = [l.strip() for l in iod_raw.splitlines() if l.strip() and len(l.split()) > 2]
        for l in reversed(lines):
            parts = l.split()
            if len(parts) >= 13 and parts[0].isdigit():
                for idx in range(12, 0, -1):
                    try:
                        v = float(parts[idx])
                        if v > -900:
                            tc["iod"] = v
                            break
                    except ValueError: continue
                if tc["iod"] is not None: break

    # Ocean Heat Content
    heat_raw, _ = http_get(URL_HEAT)
    if heat_raw:
        lines = [l.strip() for l in heat_raw.splitlines() if l.strip() and l[0].isdigit()]
        if lines:
            parts = lines[-1].split()
            if len(parts) >= 4:
                try: tc["heat_content"] = float(parts[3])
                except ValueError: pass

    return tc


# -------------------------------------------------------------------
# 2. Dam Storage Parser
# -------------------------------------------------------------------
def fetch_dams():
    html_text, err = http_get(URL_DAMS)
    if not html_text:
        return {"status": "DATA_UNAVAILABLE", "error": err}

    target_dams = {
        "bhumibol": ["bhumibol", "bhumipol", "ภูมิพล"],
        "sirikit": ["sirikit", "สิริกิติ์"],
        "kwai_noi": ["kheaw noi", "kwai noi", "kwae noi", "แควน้อย"],
        "pasak": ["pa sak jorasit", "pasak", "pa sak", "ป่าสัก"],
        "srinagarind": ["srinakarin", "srinagarind", "ศรีนครินทร์"],
        "vajiralongkorn": ["wachiralongkorn", "vajiralongkorn", "วชิราลงกรณ"]
    }

    clean_html = html_text.replace("&nbsp;", " ").replace("<tr", "\n<tr")
    parsed = {}

    for line in clean_html.splitlines():
        plain = " ".join(re.sub(r"<[^>]+>", " ", line).split()).lower()
        if not plain: continue

        for dam_key, kws in target_dams.items():
            if dam_key not in parsed and any(kw in plain for kw in kws):
                matches = re.findall(r'[-+]?\d+(?:,\d{3})*(?:\.\d+)?', line)
                nums = []
                for m in matches:
                    try: nums.append(float(m.replace(",", "")))
                    except ValueError: pass
                if len(nums) >= 5:
                    parsed[dam_key] = {
                        "capacity_mcm": nums[0],
                        "storage_mcm": nums[2],
                        "storage_pct": nums[3],
                        "usable_mcm": nums[4]
                    }

    return {"status": "SUCCESS", "dams": parsed}


# -------------------------------------------------------------------
# 3. Mainstem River Gauges & Flow Discharge
# -------------------------------------------------------------------
def fetch_river_flow():
    raw_json, err = http_get(URL_RIVER)
    if not raw_json:
        return {"status": "DATA_UNAVAILABLE", "error": err}

    try:
        data = json.loads(raw_json)
        records = data.get("data", []) if isinstance(data, dict) else data
        
        # Priority Chao Phraya River Stations
        key_stations = ["C.2", "C.13", "C.29A", "C.35", "CPY008", "CPY012", "CPY014"]
        found_stations = []

        for rec in records:
            st = rec.get("station", {})
            st_name = st.get("tele_station_name", {}).get("th", "")
            st_code = st.get("tele_station_oldcode", "")
            
            if any(k in st_name or k in st_code for k in key_stations):
                found_stations.append({
                    "station_code": st_code,
                    "name": st_name,
                    "water_level_m": rec.get("waterlevel_m"),
                    "discharge_m3s": rec.get("discharge"),
                    "bank_capacity_pct": rec.get("waterlevel_in_percent"),
                    "lat": st.get("tele_station_lat"),
                    "lon": st.get("tele_station_long")
                })

        return {"status": "SUCCESS", "stations": found_stations}
    except Exception as e:
        return {"status": "PARSING_ERROR", "error": str(e)}


# -------------------------------------------------------------------
# 4. Regional & BKK Rainfall Telemetry Parser
# -------------------------------------------------------------------
def fetch_rainfall():
    raw_json, err = http_get(URL_RAIN)
    if not raw_json:
        return {"status": "DATA_UNAVAILABLE", "error": err}

    try:
        data = json.loads(raw_json)
        records = data.get("data", []) if isinstance(data, dict) else data
        
        bkk_samut_records = []
        max_1h = 0.0
        max_24h = 0.0

        for rec in records:
            geocode = rec.get("geocode", {})
            prov_en = geocode.get("province_name", {}).get("en", "")
            prov_th = geocode.get("province_name", {}).get("th", "")
            
            r1h = rec.get("rain_1h") or 0.0
            r24h = rec.get("rain_24h") or 0.0

            if r1h > max_1h: max_1h = r1h
            if r24h > max_24h: max_24h = r24h

            if "Bangkok" in prov_en or "Samut Prakan" in prov_en or "กรุงเทพ" in prov_th or "สมุทรปราการ" in prov_th:
                st = rec.get("station", {})
                bkk_samut_records.append({
                    "station_name": st.get("tele_station_name", {}).get("th", "Gauge"),
                    "province": prov_en if prov_en else prov_th,
                    "district": geocode.get("amphoe_name", {}).get("en", ""),
                    "rain_1h_mm": r1h,
                    "rain_24h_mm": r24h,
                    "lat": st.get("tele_station_lat"),
                    "lon": st.get("tele_station_long")
                })

        # Sort BKK/Samut Prakan by 24h rainfall descending
        bkk_samut_records.sort(key=lambda x: x["rain_24h_mm"], reverse=True)

        return {
            "status": "SUCCESS",
            "total_nationwide_stations": len(records),
            "max_nationwide_1h_mm": max_1h,
            "max_nationwide_24h_mm": max_24h,
            "bkk_samut_prakan_count": len(bkk_samut_records),
            "top_bkk_samut_stations": bkk_samut_records[:10]
        }
    except Exception as e:
        return {"status": "PARSING_ERROR", "error": str(e)}


# -------------------------------------------------------------------
# 5. Estuary Sea Level & Tide Bounds Parser
# -------------------------------------------------------------------
def fetch_estuary_tide():
    html_text, err = http_get(URL_TIDE)
    if not html_text:
        return {"status": "DATA_UNAVAILABLE", "error": err}

    res = {"realtime_msl": None, "predicted_bounds": "N/A", "status": "SUCCESS"}
    clean_html = html_text.replace("&nbsp;", " ")

    # Real-time gauge GLF001
    glf_match = re.search(r'<tr[^>]*rel="GLF001"[^>]*>(.*?)</tr>', clean_html, re.DOTALL | re.IGNORECASE)
    if glf_match:
        tds = re.findall(r'<td[^>]*>(.*?)</td>', glf_match.group(1), re.DOTALL | re.IGNORECASE)
        td_clean = [re.sub(r'<[^>]+>', '', td).strip() for td in tds]
        if len(td_clean) >= 5:
            try: res["realtime_msl"] = float(td_clean[4])
            except ValueError: pass

    # Predictive tide N03
    n03_match = re.search(r'<tr[^>]*rel="N03"[^>]*>(.*?)</tr>', clean_html, re.DOTALL | re.IGNORECASE)
    if n03_match:
        tds = re.findall(r'<td[^>]*>(.*?)</td>', n03_match.group(1), re.DOTALL | re.IGNORECASE)
        td_clean = [re.sub(r'<[^>]+>', ' ', td).strip() for td in tds]
        if len(td_clean) >= 3:
            res["predicted_bounds"] = f"Max: {td_clean[1]} | Min: {td_clean[2]}"

    return res


# -------------------------------------------------------------------
# Main Ingestion
# -------------------------------------------------------------------
def main():
    print("Executing Macro Fetch Pipeline...")
    ts = datetime.now(timezone.utc).isoformat()

    teleconnections = fetch_teleconnections()
    dams = fetch_dams()
    river_flow = fetch_river_flow()
    rainfall = fetch_rainfall()
    tide = fetch_estuary_tide()

    macro_payload = {
        "timestamp_utc": ts,
        "is_live": True,
        "teleconnections": teleconnections,
        "dam_storage": dams,
        "river_hydraulics": river_flow,
        "rainfall_telemetry": rainfall,
        "estuary_tide": tide
    }

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(macro_payload, f, indent=2, ensure_ascii=False)

    print(f"Successfully generated '{OUTPUT_FILE}'.")


if __name__ == "__main__":
    main()
