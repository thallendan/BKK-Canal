import json
import os
import re
from datetime import datetime, timezone, timedelta

# File paths
KLONGMAP_FILE = "klongmap-latest.json"
MASTER_DATA_FILE = "master_water_level_data.json"
FALLBACK_MASTER_FILE = "mater_water_level_data.json"
OUTPUT_HTML = "index.html"
OUTPUT_JSON = "processed_water_data.json"

def parse_dotnet_date(date_str):
    """Converts ASP.NET /Date(timestamp)/ format to UTC+7 ICT string."""
    if not date_str or not isinstance(date_str, str):
        return None
    match = re.search(r'\((\d+)\)', date_str)
    if match:
        timestamp_ms = int(match.group(1))
        utc_dt = datetime.fromtimestamp(timestamp_ms / 1000.0, tz=timezone.utc)
        ict_dt = utc_dt.astimezone(timezone(timedelta(hours=7)))
        return ict_dt.strftime("%Y-%m-%d %H:%M:%S ICT")
    return date_str

def load_json_file(file_path, fallback_path=None):
    """Loads JSON file from local disk."""
    target_path = file_path if os.path.exists(file_path) else fallback_path
    if not target_path or not os.path.exists(target_path):
        print(f"Warning: File not found ({file_path})")
        return None
    with open(target_path, "r", encoding="utf-8") as f:
        return json.load(f)

def process_station_data(map_data, master_data):
    """Extracts station information, water levels, thresholds, and pump status."""
    stations = map_data.get("waterStation", [])
    processed_stations = []

    for station in stations:
        info = station.get("water_station_info") or {}
        last_level = station.get("water_level_last") or {}
        pump_last = station.get("water_pump_last") or {}

        water_id = station.get("water_id") or info.get("water_id")
        name_th = station.get("station_name") or info.get("water_shortname") or info.get("water_name") or f"Station {water_id}"
        name_en = station.get("station_name_en") or info.get("water_shortname_en") or f"Station {water_id}"
        
        river = info.get("river_name", "N/A")
        lat = info.get("latitude")
        lon = info.get("longitude")
        
        wl_in = last_level.get("wl_in")
        wl_out01 = last_level.get("wl_out01") if last_level.get("wl_out01") != -99 else None
        
        warning_level = info.get("warning")
        critical_level = info.get("critical")
        
        timestamp_raw = last_level.get("site_timestamp") or last_level.get("update_timestamp")
        timestamp_formatted = parse_dotnet_date(timestamp_raw)

        active_pumps = 0
        if pump_last:
            for k, v in pump_last.items():
                if k.startswith("pump") and v is True:
                    active_pumps += 1

        processed_stations.append({
            "water_id": water_id,
            "name_th": name_th,
            "name_en": name_en,
            "river": river,
            "latitude": lat,
            "longitude": lon,
            "water_level_in": wl_in,
            "water_level_out": wl_out01,
            "warning_threshold": warning_level,
            "critical_threshold": critical_level,
            "active_pumps": active_pumps,
            "last_updated": timestamp_formatted
        })

    return processed_stations

def generate_html_report(stations, output_file):
    """Outputs a dashboard view in HTML."""
    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Bangkok Canal Water Level Monitor</title>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; margin: 20px; background-color: #f8f9fa; color: #212529; }}
        h1 {{ color: #0d6efd; }}
        .meta {{ margin-bottom: 20px; color: #6c757d; }}
        table {{ width: 100%; border-collapse: collapse; background: #ffffff; box-shadow: 0 1px 3px rgba(0,0,0,0.1); border-radius: 6px; overflow: hidden; }}
        th, td {{ padding: 12px 15px; text-align: left; border-bottom: 1px solid #dee2e6; }}
        th {{ background-color: #0d6efd; color: white; font-weight: 600; }}
        tr:hover {{ background-color: #f1f3f5; }}
    </style>
</head>
<body>
    <h1>Bangkok Canal Water Level Status</h1>
    <div class="meta">Total Stations Monitored: {len(stations)}</div>
    <table>
        <thead>
            <tr>
                <th>ID</th>
                <th>Station Name (EN)</th>
                <th>Station Name (TH)</th>
                <th>River / Canal</th>
                <th>Water Level (In)</th>
                <th>Warning Level</th>
                <th>Critical Level</th>
                <th>Active Pumps</th>
                <th>Last Updated</th>
            </tr>
        </thead>
        <tbody>
"""
    for s in stations:
        wl_in = f"{s['water_level_in']} m" if s['water_level_in'] is not None else "N/A"
        warn = f"{s['warning_threshold']} m" if s['warning_threshold'] is not None else "N/A"
        crit = f"{s['critical_threshold']} m" if s['critical_threshold'] is not None else "N/A"
        
        html_content += f"""            <tr>
                <td>{s['water_id']}</td>
                <td><strong>{s['name_en']}</strong></td>
                <td>{s['name_th']}</td>
                <td>{s['river']}</td>
                <td>{wl_in}</td>
                <td>{warn}</td>
                <td>{crit}</td>
                <td>{s['active_pumps']}</td>
                <td>{s['last_updated'] or 'N/A'}</td>
            </tr>
"""

    html_content += """        </tbody>
    </table>
</body>
</html>
"""
    with open(output_file, "w", encoding="utf-8") as f:
        f.write(html_content)

def main():
    map_data = load_json_file(KLONGMAP_FILE) or {}
    master_data = load_json_file(MASTER_DATA_FILE, FALLBACK_MASTER_FILE) or {}

    stations = process_station_data(map_data, master_data)

    with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump(stations, f, ensure_ascii=False, indent=2)

    generate_html_report(stations, OUTPUT_HTML)
    print(f"Processed {len(stations)} canal stations successfully. Generated {OUTPUT_HTML} and {OUTPUT_JSON}.")

if __name__ == "__main__":
    main()
