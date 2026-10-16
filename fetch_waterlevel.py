import json
import requests

URL = "https://api-v3.thaiwater.net/api/v1/thaiwater30/public/waterlevel_load"
OUTPUT_FILE = "waterlevel.json"

def fetch_and_save():
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "application/json, text/plain, */*",
    }
    
    response = requests.get(URL, headers=headers, timeout=30)
    response.raise_for_status()
    
    data = response.json()
    
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        
    print(f"Data successfully fetched and written to {OUTPUT_FILE}")

if __name__ == "__main__":
    fetch_and_save()
