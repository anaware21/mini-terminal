import asyncio
import os

from playwright.async_api import async_playwright
from bs4 import BeautifulSoup


async def _fetch_page(browser, sem, url):
    async with sem:
        context = await browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:124.0) "
                "Gecko/20100101 Firefox/124.0"
            )
        )
        try:
            page = await context.new_page()
            await page.goto(url, wait_until="networkidle", timeout=60000)
            await page.get_by_text("Gas Station", exact=True).wait_for(state="visible", timeout=30000)
            await page.get_by_text("Gas Station", exact=True).click()
            await page.wait_for_selector('[data-testid="gas-station"] .skeleton-wrapper', state="detached", timeout=30000)
            await page.locator('[data-testid="gas-station"] dl:not([data-testid]) div span').first.wait_for(state="visible", timeout=30000)
            html = await page.content()
            return html
        finally:
            await context.close()


async def _fetch_all(urls):
    async with async_playwright() as p:
        headless = os.environ.get("HEADLESS", "true").lower() != "false"
        browser = await p.firefox.launch(headless=headless)
        sem = asyncio.Semaphore(5)
        tasks = [_fetch_page(browser, sem, url) for url in urls]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        await browser.close()
    return results


def fetch_html(urls):
    if isinstance(urls, str):
        urls = [urls]
    return asyncio.run(_fetch_all(urls))


def get_price(html, fuel_type):
    soup = BeautifulSoup(html, "html.parser")
    gas_section = soup.find("div", attrs={"data-testid": "gas-station"})
    if not gas_section:
        return None
    for row in gas_section.select("dl:not([data-testid]) div"):
        dt = row.find("dt")
        price_span = row.find("span")
        price_sup = row.find("sup")
        if dt and dt.get_text(strip=True).lower() == fuel_type.lower() and price_span:
            cents = price_sup.get_text(strip=True) if price_sup else ""
            return float(f"{price_span.get_text(strip=True).replace('$', '')}{cents}")
    return None


def get_regular_price(html):
    return get_price(html, "Regular")


def get_premium_price(html):
    return get_price(html, "Premium")


if __name__ == "__main__":
    urls = [
        "https://www.costco.com/w/-/ca/alhambra/428",
        "https://www.costco.com/w/-/ca/inglewood/769",
        "https://www.costco.com/w/-/ca/marina-del-rey/479"
    ]
    for url, html in zip(urls, fetch_html(urls)):
        print(f"{url}")
        print(f"  Regular: {get_regular_price(html)}")
        print(f"  Premium: {get_premium_price(html)}")
