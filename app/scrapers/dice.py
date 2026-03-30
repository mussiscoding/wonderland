import logging
import os
from datetime import datetime, timedelta, timezone

import httpx

from app.scrapers.base import RateLimiter, parse_iso_datetime

logger = logging.getLogger(__name__)

API_URL = "https://events-api.dice.fm/v1/events"
PAGE_SIZE = 200  # Dice max

HEADERS = {
    "Accept": "application/json",
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)",
}

rate_limiter = RateLimiter(min_delay=1.0)


def fetch_london_events(days: int = 60, progress: dict | None = None) -> list[dict]:
    """Fetch London DJ/club events from DICE for the next N days.

    Returns a list of normalised event dicts ready for storage.
    """
    api_key = os.environ.get("DICE_API_KEY")
    if not api_key:
        logger.warning("  DICE_API_KEY not set, skipping Dice fetch")
        return []

    all_events = []
    page = 1

    while True:
        rate_limiter.wait()

        params = {
            "page[size]": PAGE_SIZE,
            "page[number]": page,
            "filter[cities]": "london",
            "filter[type_tags]": "music:dj",
        }

        try:
            headers = {**HEADERS, "x-api-key": api_key}
            resp = httpx.get(API_URL, params=params, headers=headers, timeout=20)
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            logger.warning(f"  Dice request failed (page {page}): {e}")
            break

        items = data.get("data", [])
        if not items:
            break

        for item in items:
            normalised = _normalise_event(item)
            if normalised:
                all_events.append(normalised)

        logger.info(f"  Dice page {page}: {len(items)} events")

        if progress is not None:
            progress["step"] = f"Fetching Dice events... page {page}"
            progress["current"] = page
            progress["total"] = page  # no total count from API

        next_link = data.get("links", {}).get("next")
        if not next_link:
            break
        page += 1

    logger.info(f"  Dice fetch complete: {len(all_events)} events")
    return all_events


def _normalise_event(event: dict) -> dict | None:
    """Convert a Dice event into our standard format."""
    if not event:
        return None

    if event.get("sold_out"):
        return None

    date_str = event.get("date")
    dt = parse_iso_datetime(date_str)
    if not dt:
        return None

    # Artist names from the simple array, fall back to detailed_artists
    artists = event.get("artists") or []
    if not artists:
        detailed = event.get("detailed_artists") or []
        artists = [a["name"] for a in detailed if a.get("name")]

    venue_name = event.get("venue") or "Unknown Venue"
    title = event.get("name", "")
    event_hash = event.get("hash", "")
    perm_name = event.get("perm_name", "")
    source_url = f"https://dice.fm/event/{event_hash}-{perm_name}" if event_hash else None

    # Price: minor units (pence) → human-readable string
    price = None
    ticket_types = event.get("ticket_types") or []
    if ticket_types:
        prices = [t["price"]["total"] for t in ticket_types if t.get("price", {}).get("total")]
        if prices:
            currency = event.get("currency", "GBP")
            min_price = min(prices) / 100
            price = f"{currency} {min_price:.2f}"

    return {
        "title": title,
        "date": dt,
        "venue_name": venue_name,
        "venue_location": "London",
        "lineup_raw": ", ".join(artists) if artists else None,
        "lineup_parsed": artists,
        "source_name": "dice",
        "source_id": str(event.get("id", "")),
        "source_url": source_url,
        "ticket_url": event.get("url") or source_url,
        "price": price,
    }
