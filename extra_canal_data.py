import os
import json
import time
import logging
import requests
import pandas as pd
from datetime import datetime

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)

# Configuration mapping target river basins and agencies
TARGET_BASINS = {
    "12": "Pasak River Basin",
    "14": "Mae Klong River Basin",
    "16": "Bang Pakong River Basin"
}

TARGET_AGENCIES = {
    "G07003": "RID (Royal Irrigation Department)",
    "G09006": "DWR (Department of Water Resources)",
    "G11004": "TMD (Thai Meteorological Department)"
}

DWR_PARAMS = ["TC151002", "TC151003", "TC151004"]
OUTPUT_DIR = "data"

class RiverDataCollector:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36"
            ),
            "Accept": "*/*",
            "Accept-Language": "en-GB,en-US;q=0.9,en;q=0.8",
        })
        os.makedirs(OUTPUT_DIR, exist_ok=True)
        self.collected_records = []

    def init_dwr_session(self):
        """Initializes ASP.NET Core cookies by requesting the main DWR page."""
        url = "https://tele-bangpakong.dwr.go.th/?lang=EN"
        try:
            logging.info("Initializing DWR session cookies...")
            res = self.session.get(url, timeout=15)
            logging.info(f"DWR Session status: {res.status_code}")
        except Exception as e:
            logging.warning(f"Could not pre-initialize DWR session cookies: {e}")

    def fetch_dwr_telemetry(self):
        """Fetches station parameter data from DWR Bang Pakong telemetry endpoints."""
        self.init_dwr_session()
        dwr_results = []
        headers = {
            "Referer": "https://tele-bangpakong.dwr.go.th/?lang=EN",
            "X-Requested-With": "XMLHttpRequest"
        }

        # Override with custom cookie env var if provided in GitHub Secrets
        custom_cookie = os.getenv("DWR_SESSION_COOKIE")
        if custom_cookie:
            headers["Cookie"] = custom_cookie

        for param in DWR_PARAMS:
            endpoint = f"https://tele-bangpakong.dwr.go.th/home/updateparam?param={param}"
            try:
                logging.info(f"Fetching DWR Telemetry parameter: {param}")
                res = self.session.get(endpoint, headers=headers, timeout=15)
                
                if res.status_code == 200:
                    try:
                        data = res.json()
                    except json.JSONDecodeError:
                        data = {"raw_html": res.text}
                    
                    record = {
                        "source": "DWR_Telemetry",
                        "basin": "Bang Pakong River Basin (16)",
                        "parameter_code": param,
                        "timestamp": datetime.utcnow().isoformat(),
                        "payload": data
                    }
                    dwr_results.append(record)
                    self.collected_records.append(record)
                    logging.info(f"Successfully fetched DWR parameter {param}")
                else:
                    logging.warning(f"DWR parameter {param} returned status {res.status_code}")
            except Exception as e:
                logging.error(f"Failed to fetch DWR parameter {param}: {e}")
            time.sleep(1)

        return dwr_results

    def fetch_thaiwater_standard_api(self):
        """Queries Thaiwater standard API endpoints for target river basins and agencies."""
        base_urls = [
            "https://api-v3.thaiwater.net/api/v1/thaiwater30/public/waterlevel_load",
            "https://thaiwater.net/api/v1/StationInfo",
            "https://standard.thaiwater.net/twsapi/v1.0/StationInfo",
            "https://api.thaiwater.net/v1/WaterLevel"
        ]

        tw_results = []
        for basin_code, basin_name in TARGET_BASINS.items():
            for agency_code, agency_name in TARGET_AGENCIES.items():
                params = {
                    "basinCode": basin_code,
                    "agencyCode": agency_code,
                    "latest": "true"
                }
                
                for base_url in base_urls:
                    try:
                        logging.info(f"Probing Thaiwater API ({base_url}) for Basin {basin_code} ({agency_code})...")
                        res = self.session.get(base_url, params=params, timeout=10)
                        
                        if res.status_code == 200:
                            data = res.json()
                            record = {
                                "source": "Thaiwater_API",
                                "endpoint": base_url,
                                "basin_code": basin_code,
                                "basin_name": basin_name,
                                "agency_code": agency_code,
                                "agency_name": agency_name,
                                "timestamp": datetime.utcnow().isoformat(),
                                "payload": data
                            }
                            tw_results.append(record)
                            self.collected_records.append(record)
                            logging.info(f"Received valid payload from {base_url} for Basin {basin_code}")
                            break
                    except Exception as e:
                        logging.debug(f"Endpoint {base_url} unreachable or error: {e}")
                time.sleep(0.5)

        return tw_results

    def fetch_rid_telemetry(self):
        """Attempts fetching public telemetry markers from RID (telerid.rid.go.th)."""
        rid_endpoints = [
            "https://telerid.rid.go.th/api/v1/water_level",
            "https://telerid.rid.go.th/api/stations"
        ]
        
        rid_results = []
        for endpoint in rid_endpoints:
            try:
                logging.info(f"Checking RID Telemetry endpoint: {endpoint}")
                res = self.session.get(endpoint, timeout=10)
                if res.status_code == 200:
                    data = res.json()
                    record = {
                        "source": "RID_Telemetry",
                        "endpoint": endpoint,
                        "timestamp": datetime.utcnow().isoformat(),
                        "payload": data
                    }
                    rid_results.append(record)
                    self.collected_records.append(record)
                    logging.info(f"RID Telemetry responded from {endpoint}")
            except Exception as e:
                logging.debug(f"RID endpoint {endpoint} failed: {e}")

        return rid_results

    def save_outputs(self):
        """Exports gathered data to JSON and flattened CSV formats."""
        timestamp_str = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        json_filename = os.path.join(OUTPUT_DIR, f"river_data_{timestamp_str}.json")
        csv_filename = os.path.join(OUTPUT_DIR, f"river_data_summary_{timestamp_str}.csv")

        # Save complete raw JSON response payload
        with open(json_filename, "w", encoding="utf-8") as f:
            json.dump(self.collected_records, f, ensure_ascii=False, indent=2)
        logging.info(f"Saved JSON payload to {json_filename}")

        # Flatten records for summary CSV
        rows = []
        for rec in self.collected_records:
            rows.append({
                "timestamp": rec.get("timestamp"),
                "source": rec.get("source"),
                "basin_code": rec.get("basin_code", rec.get("basin", "")),
                "basin_name": rec.get("basin_name", ""),
                "agency_code": rec.get("agency_code", ""),
                "parameter_code": rec.get("parameter_code", ""),
                "status": "Success" if rec.get("payload") else "No Data"
            })
        
        df = pd.DataFrame(rows)
        df.to_csv(csv_filename, index=False, encoding="utf-8-sig")
        logging.info(f"Saved CSV summary to {csv_filename}")


if __name__ == "__main__":
    collector = RiverDataCollector()
    collector.fetch_dwr_telemetry()
    collector.fetch_thaiwater_standard_api()
    collector.fetch_rid_telemetry()
    collector.save_outputs()
