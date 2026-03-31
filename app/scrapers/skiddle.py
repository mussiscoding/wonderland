import logging
from datetime import datetime, timedelta, timezone

import httpx

from app.config import settings
from app.scrapers.base import RateLimiter, parse_iso_datetime

logger = logging.getLogger(__name__)

API_BASE = "https://www.skiddle.com/api/v1"
LONDON_LAT = 51.5074
LONDON_LON = -0.1278
RADIUS_MILES = 15
PAGE_SIZE = 100  # Skiddle max

rate_limiter = RateLimiter(min_delay=1.0)


def fetch_london_events(days: int = 60, progress: dict | None = None) -> list[dict]:
    """Fetch London club events from Skiddle for the next N days.

    Returns a list of normalised event dicts ready for storage.
    """
    api_key = settings.skiddle_api_key
    if not api_key:
        logger.warning("  SKIDDLE_API_KEY not set, skipping Skiddle fetch")
        return []

    now = datetime.now(timezone.utc)
    min_date = now.strftime("%Y-%m-%d")
    max_date = (now + timedelta(days=days)).strftime("%Y-%m-%d")

    all_events = []
    offset = 0

    while True:
        rate_limiter.wait()

        params = {
            "api_key": api_key,
            "latitude": LONDON_LAT,
            "longitude": LONDON_LON,
            "radius": RADIUS_MILES,
            "eventcode": "CLUB",
            "minDate": min_date,
            "maxDate": max_date,
            "description": 1,
            "limit": PAGE_SIZE,
            "offset": offset,
            "order": "date",
        }

        try:
            resp = httpx.get(f"{API_BASE}/events/search/", params=params, timeout=20)
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            logger.warning(f"  Skiddle request failed (offset {offset}): {e}")
            break

        if data.get("error"):
            logger.warning(f"  Skiddle API error: {data}")
            break

        results = data.get("results", [])
        total = int(data.get("totalcount", 0))

        if not results:
            break

        for item in results:
            normalised = _normalise_event(item)
            if normalised:
                all_events.append(normalised)

        page_num = (offset // PAGE_SIZE) + 1
        total_pages = max(1, -(-total // PAGE_SIZE))  # ceil division
        logger.info(f"  Skiddle page {page_num}: {len(results)} events (total: {total})")

        if progress is not None:
            progress["step"] = f"Fetching Skiddle events... page {page_num}/{total_pages}"
            progress["current"] = page_num
            progress["total"] = total_pages

        offset += PAGE_SIZE
        if offset >= total:
            break

    logger.info(f"  Skiddle fetch complete: {len(all_events)} events")
    return all_events


def _normalise_event(event: dict) -> dict | None:
    """Convert a Skiddle event into our standard format."""
    if not event:
        return None

    if event.get("cancelled") == "1":
        return None

    date_str = event.get("date")
    dt = parse_iso_datetime(date_str)
    if not dt:
        return None

    venue = event.get("venue", {})
    artists = event.get("artists", [])
    lineup = [a["name"] for a in artists if a.get("name")]

    title = event.get("eventname", "")
    venue_name = venue.get("name", "Unknown Venue")
    event_id = str(event.get("id", ""))
    link = event.get("link", "")

    price = None
    entry_price = event.get("entryprice")
    if entry_price:
        try:
            p = float(entry_price)
            if p > 0:
                price = f"£{p:.0f}" if p == int(p) else f"£{p:.2f}"
        except (ValueError, TypeError):
            pass

    return {
        "title": title,
        "date": dt,
        "venue_name": venue_name,
        "venue_location": "London",
        "lineup_raw": ", ".join(lineup) if lineup else None,
        "lineup_parsed": lineup,
        "source_name": "skiddle",
        "source_id": event_id,
        "source_url": link,
        "ticket_url": link,
        "price": price,
    }
