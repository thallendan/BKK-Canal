import os
import sys
import json
import requests

API_URL = "https://api-v3.thaiwater.net/api/v1/thaiwater30/public/watergate_load"
OUTPUT_FILE = "watergate_load.json"

def fetch_and_save_data():
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }

    try:
        print(f"Fetching watergate data from {API_URL}...")
        response = requests.get(API_URL, headers=headers, timeout=30)
        response.raise_for_status()

        data = response.json()

        with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        print(f"Successfully updated {OUTPUT_FILE}")

    except requests.exceptions.RequestException as e:
        print(f"HTTP Request failed: {e}", file=sys.stderr)
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"Failed to parse JSON response: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    fetch_and_save_data()
