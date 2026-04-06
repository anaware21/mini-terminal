import os
from datetime import datetime, timezone
from dotenv import load_dotenv
from supabase import create_client
from scrape_gas_price import fetch_html, get_regular_price, get_premium_price

load_dotenv()

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_KEY"]

URLS = [
    # SoCal
    "https://www.costco.com/w/-/ca/alhambra/428",
    "https://www.costco.com/w/-/ca/inglewood/769",
    "https://www.costco.com/w/-/ca/marina-del-rey/479",
    "https://www.costco.com/w/-/ca/burbank/677",
    "https://www.costco.com/w/-/ca/monterey-park/1318",
    # North Jersey
    "https://www.costco.com/w/-/nj/east-hanover/244",
    "https://www.costco.com/w/-/nj/wharton/315",
    "https://www.costco.com/w/-/nj/wayne/1177",
    "https://www.costco.com/w/-/nj/edison/323",
    "https://www.costco.com/w/-/nj/union/320",
    # DFW
    "https://www.costco.com/w/-/tx/dallas/1266",
    "https://www.costco.com/w/-/tx/frisco/1097",
    "https://www.costco.com/w/-/tx/mckinney/1284",
    "https://www.costco.com/w/-/tx/plano/664",
    "https://www.costco.com/w/-/tx/arlington/668"
]


def scrape_all(urls):
    html_pages = fetch_html(urls)
    regular_rows = []
    premium_rows = []
    for url, html in zip(urls, html_pages):
        base = {
            "date": datetime.now(timezone.utc).date().isoformat(),
            "url": url,
            "location": url.split("/")[-2],
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        regular_rows.append({**base, "price": get_regular_price(html)})
        premium_rows.append({**base, "price": get_premium_price(html)})
    return regular_rows, premium_rows


def upload(regular_rows, premium_rows):
    client = create_client(SUPABASE_URL, SUPABASE_KEY)
    client.table("costco_reg_gas_by_loc").insert(regular_rows).execute()
    client.table("costco_prm_gas_by_loc").insert(premium_rows).execute()

    reg_prices = [r["price"] for r in regular_rows if r["price"] is not None]
    prm_prices = [r["price"] for r in premium_rows if r["price"] is not None]
    client.table("costco_daily_avg").insert({
        "date": datetime.now(timezone.utc).date().isoformat(),
        "avg_reg_price": sum(reg_prices) / len(reg_prices) if reg_prices else None,
        "avg_prm_price": sum(prm_prices) / len(prm_prices) if prm_prices else None,
    }).execute()


if __name__ == "__main__":
    regular_rows, premium_rows = scrape_all(URLS)
    print("Regular:")
    for r in regular_rows:
        print(f"  {r}")
    print("Premium:")
    for r in premium_rows:
        print(f"  {r}")
    upload(regular_rows, premium_rows)
    print("Uploaded successfully.")
