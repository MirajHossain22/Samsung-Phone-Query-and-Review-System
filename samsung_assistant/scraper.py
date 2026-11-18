"""GSMArena scraper for Samsung phones (requests + BeautifulSoup).

Usage:
    python -m samsung_assistant.scraper                  # default list of 12 flagship models
    python -m samsung_assistant.scraper --limit 15 --delay 6
    python -m samsung_assistant.scraper --urls https://www.gsmarena.com/samsung_galaxy_s23-12082.php

GSMArena rate-limits aggressively (HTTP 429). Keep the delay >= 4 s, scrape a
small set once, and re-use the database afterwards. Please respect the site's terms.
"""
from __future__ import annotations

import argparse
import logging
import re
import time
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from .db import Database
from .repository import PhoneRepository

BASE = "https://www.gsmarena.com/"
BRAND_PAGE = BASE + "samsung-phones-9.php"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Chrome/124.0 Safari/537.36 (+internship-assignment; polite scraper)",
    "Accept-Language": "en-US,en;q=0.9",
}
DEFAULT_TARGETS = [
    "Samsung Galaxy S21", "Samsung Galaxy S21+", "Samsung Galaxy S21 Ultra",
    "Samsung Galaxy S22", "Samsung Galaxy S22+", "Samsung Galaxy S22 Ultra",
    "Samsung Galaxy S23", "Samsung Galaxy S23+", "Samsung Galaxy S23 Ultra",
    "Samsung Galaxy S24", "Samsung Galaxy S24+", "Samsung Galaxy S24 Ultra",
]
log = logging.getLogger("scraper")


def _model_key(name: str) -> str:
    key = name.casefold().replace("+", " plus ")
    key = re.sub(r"\s+", " ", key).strip()
    return re.sub(r"\s+5g$", "", key)


# ------------------------------------------------------------------ fetching
def fetch(url: str, session: requests.Session, retries: int = 4, delay: float = 5.0) -> str:
    for attempt in range(1, retries + 1):
        resp = session.get(url, headers=HEADERS, timeout=30)
        if resp.status_code == 200 and resp.text.strip():
            return resp.text
        # GSMArena sometimes returns an empty 200 response for desktop phone
        # pages while serving the same public specification page on its mobile
        # host. Keep the canonical desktop URL in the database, but parse the
        # accessible mobile representation.
        if resp.status_code == 200 and url.startswith(BASE):
            mobile_url = url.replace(BASE, "https://m.gsmarena.com/", 1)
            mobile = session.get(mobile_url, headers=HEADERS, timeout=30)
            if mobile.status_code == 200 and mobile.text.strip():
                log.info("desktop response was empty; using mobile page for %s", url)
                return mobile.text
        if resp.status_code in (429, 503):
            wait = delay * attempt * 2
            log.warning("HTTP %s for %s - backing off %.0fs", resp.status_code, url, wait)
            time.sleep(wait)
            continue
        if resp.status_code == 200:
            wait = delay * attempt
            log.warning("empty HTTP 200 response for %s - retrying in %.0fs", url, wait)
            time.sleep(wait)
            continue
        resp.raise_for_status()
    raise RuntimeError(f"Giving up on {url}")


# ------------------------------------------------------------------- parsing
def parse_listing(html: str) -> dict[str, str]:
    """Return {phone name: absolute URL} from a brand listing page."""
    soup = BeautifulSoup(html, "lxml")
    found = {}
    for a in soup.select("div.makers ul li a"):
        name = a.get_text(" ", strip=True)
        if name and a.get("href"):
            found[name] = urljoin(BASE, a["href"])
    return found


def next_listing_page(html: str) -> str | None:
    soup = BeautifulSoup(html, "lxml")
    nxt = soup.select_one("a.pages-next")
    return urljoin(BASE, nxt["href"]) if nxt and nxt.get("href") else None


def parse_phone_page(html: str, url: str = "") -> dict:
    """Parse one GSMArena phone page into {name, url, image_url, announced, specs}."""
    soup = BeautifulSoup(html, "lxml")
    title = soup.select_one("h1.specs-phone-name-title, h1.section.nobor")
    if title is None:
        raise ValueError("Not a GSMArena phone page (no spec title found)")
    name = title.get_text(" ", strip=True)
    if not name.lower().startswith("samsung"):
        name = f"Samsung {name}"

    specs: dict[str, dict[str, str]] = {}
    for table in soup.select("#specs-list table"):
        th = table.find("th")
        if th is None:
            continue
        category = th.get_text(" ", strip=True)
        if category.casefold() == "selfie camera":
            category = "Selfie camera"
        last_key = None
        for tr in table.find_all("tr"):
            ttl, nfo = tr.select_one("td.ttl"), tr.select_one("td.nfo")
            if nfo is None:
                continue
            key = ttl.get_text(" ", strip=True) if ttl else ""
            value = nfo.get_text(" ", strip=True)
            if not value:
                continue
            bucket = specs.setdefault(category, {})
            if not key:                       # continuation row: append to previous key
                key = last_key or "Info"
            if key in bucket:
                bucket[key] += "; " + value
            else:
                bucket[key] = value
            last_key = key

    img = soup.select_one("div.specs-photo-main img, #specs-cp-pic img")
    announced = specs.get("Launch", {}).get("Announced")
    return {
        "name": name,
        "url": url,
        "image_url": img["src"] if img and img.get("src") else None,
        "announced": announced,
        "specs": specs,
    }


# ----------------------------------------------------------------- orchestration
def collect_urls(session: requests.Session, targets: list[str], delay: float) -> dict[str, str]:
    """Walk the Samsung brand listing pages and pick the exact target names."""
    wanted = {_model_key(t): t for t in targets}
    found: dict[str, str] = {}
    page_url = BRAND_PAGE
    while page_url and len(found) < len(wanted):
        html = fetch(page_url, session, delay=delay)
        for name, url in parse_listing(html).items():
            full = name if name.lower().startswith("samsung") else f"Samsung {name}"
            key = _model_key(full)
            if key in wanted:
                found[wanted[key]] = url
        page_url = next_listing_page(html)
        time.sleep(delay)
    missing = set(targets) - set(found)
    if missing:
        log.warning("Not found on listing pages: %s", ", ".join(sorted(missing)))
    return found


def scrape(urls: list[str], repo: PhoneRepository, delay: float = 5.0) -> int:
    session = requests.Session()
    saved = 0
    for url in urls:
        try:
            record = parse_phone_page(fetch(url, session, delay=delay), url)
            repo.upsert_phone(record)
            saved += 1
            log.info("saved %-32s (%d spec categories)", record["name"], len(record["specs"]))
        except Exception as exc:  # keep going; one bad page must not kill the run
            log.error("failed %s: %s", url, exc)
        time.sleep(delay)
    return saved


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--urls", nargs="*", help="Scrape these phone URLs instead of the default list")
    ap.add_argument("--limit", type=int, default=12, help="Max phones from the default list (10-15)")
    ap.add_argument("--delay", type=float, default=5.0, help="Seconds between requests")
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    db = Database()
    db.init_schema()
    repo = PhoneRepository(db)
    urls = args.urls
    if not urls:
        found = collect_urls(requests.Session(), DEFAULT_TARGETS[: args.limit], args.delay)
        urls = list(found.values())
    n = scrape(urls, repo, args.delay)
    print(f"Done: {n}/{len(urls)} phones stored ({repo.count()} total in database).")


if __name__ == "__main__":
    main()
