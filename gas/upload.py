import os
import time
import requests
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from dotenv import load_dotenv
from supabase import create_client

load_dotenv()

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_KEY"]

API_URL = "https://www.costco.com/AjaxGetGasPricesService?warehouseid="

WAREHOUSES = {
    # SoCal
    "alhambra": 428,
    "inglewood": 769,
    "marina-del-rey": 479,
    "burbank": 677,
    "monterey-park": 1318,

    # North Jersey
    "wharton": 315,
    "wayne": 1177,
    "edison": 323,
    "east-hanover": 244,
    "union": 320,

    # DFW
    "dallas": 1266,
    "frisco": 1097,
    "mckinney": 1284,
    "plano": 664,
    "arlington": 668,

    # Chicago
    "chicago": 380,
    "chicago-south-loop": 1107,
    "niles": 383,
    "north-riverside": 1153,
    "melrose-park": 1085,

    # SeaTac
    "seattle": 1,
    "kirkland": 8,
    "redmond": 1225,
    "shoreline": 106,
    "woodinville": 747,
}


HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Referer": "https://www.costco.com/",
    "Accept": "application/json, text/plain, */*",
}


def fetch_prices(warehouse_id):
    resp = requests.get(f"{API_URL}{warehouse_id}", headers=HEADERS, timeout=15)
    print(resp.url)
    resp.raise_for_status()
    data = resp.json()
    prices = data[str(warehouse_id)]
    regular = float(prices["regular"]) if prices.get("regular") else None
    premium = float(prices["premium"]) if prices.get("premium") else None
    return regular, premium


def scrape_all(warehouses):
    regular_rows = []
    premium_rows = []
    for location, wid in warehouses.items():
        base = {
            "date": datetime.now(ZoneInfo("America/New_York")).date().isoformat(),
            "url": f"{API_URL}{wid}",
            "location": location,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        try:
            regular, premium = fetch_prices(wid)
        except Exception as e:
            print(f"WARNING: failed to fetch {location} ({wid}): {e}")
            regular = None
            premium = None
        regular_rows.append({**base, "price": regular})
        premium_rows.append({**base, "price": premium})
    return regular_rows, premium_rows


def _do_upload(client, regular_rows, premium_rows):
    client.table("costco_reg_gas_by_loc").insert(regular_rows).execute()
    client.table("costco_prm_gas_by_loc").insert(premium_rows).execute()

    reg_prices = [r["price"] for r in regular_rows if r["price"] is not None]
    prm_prices = [r["price"] for r in premium_rows if r["price"] is not None]
    client.table("costco_daily_avg").insert({
        "date": datetime.now(ZoneInfo("America/New_York")).date().isoformat(),
        "avg_reg_price": sum(reg_prices) / len(reg_prices) if reg_prices else None,
        "avg_prm_price": sum(prm_prices) / len(prm_prices) if prm_prices else None,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }).execute()


def upload(regular_rows, premium_rows, timeout=120, retry_delay=5):
    client = create_client(SUPABASE_URL, SUPABASE_KEY)
    deadline = time.monotonic() + timeout
    last_error = None
    attempt = 0

    while time.monotonic() < deadline:
        attempt += 1
        try:
            _do_upload(client, regular_rows, premium_rows)
            return None
        except Exception as e:
            last_error = e
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                break
            wait = min(retry_delay, remaining)
            print(f"Upload attempt {attempt} failed: {e}. Retrying in {wait:.1f}s...")
            time.sleep(wait)

    return last_error


if __name__ == "__main__":
    regular_rows, premium_rows = scrape_all(WAREHOUSES)
    print("Regular:")
    for r in regular_rows:
        print(f"  {r}")
    print("Premium:")
    for r in premium_rows:
        print(f"  {r}")
    error = upload(regular_rows, premium_rows)
    if error:
        print(f"Upload failed after 2 minutes: {error}")
    else:
        print("Uploaded successfully.")
