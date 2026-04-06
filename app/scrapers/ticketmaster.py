import logging
from datetime import datetime, timedelta, timezone

import httpx

from app.config import settings
from app.scrapers.base import RateLimiter, format_price

logger = logging.getLogger(__name__)

API_URL = "https://app.ticketmaster.com/discovery/v2/events.json"
PAGE_SIZE = 100
MAX_PAGE = 9  # Ticketmaster caps deep pagination at ~1000 results
CHUNK_DAYS = 30  # Split into monthly chunks to stay under pagination cap

rate_limiter = RateLimiter(min_delay=0.25)  # 5 req/sec limit


def fetch_events(city_config: dict, days: int = 270, progress: dict | None = None) -> list[dict]:
    """Fetch music events from Ticketmaster for the next N days.

    Splits into monthly chunks to avoid Ticketmaster's pagination cap.
    Returns a list of normalised event dicts ready for storage.
    """
    api_key = settings.ticketmaster_api_key
    if not api_key:
        logger.warning("  TICKETMASTER_API_KEY not set, skipping Ticketmaster fetch")
        return []

    tm_config = city_config["ticketmaster"]
    city_label = city_config["label"]
    currency = city_config["currency"]
    now = datetime.now(timezone.utc)
    end_date = now + timedelta(days=days)

    # Build monthly chunks
    chunks = []
    chunk_start = now
    while chunk_start < end_date:
        chunk_end = min(chunk_start + timedelta(days=CHUNK_DAYS), end_date)
        chunks.append((chunk_start, chunk_end))
        chunk_start = chunk_end

    all_events = []

    for chunk_idx, (chunk_start, chunk_end) in enumerate(chunks):
        start_str = chunk_start.strftime("%Y-%m-%dT%H:%M:%SZ")
        end_str = chunk_end.strftime("%Y-%m-%dT%H:%M:%SZ")
        page = 0

        while True:
            rate_limiter.wait()

            params = {
                "apikey": api_key,
                "city": tm_config["city"],
                "countryCode": tm_config["countryCode"],
                "classificationName": "Music",
                "startDateTime": start_str,
                "endDateTime": end_str,
                "size": PAGE_SIZE,
                "page": page,
                "sort": "date,asc",
            }

            try:
                resp = httpx.get(API_URL, params=params, timeout=20)
                resp.raise_for_status()
                data = resp.json()
            except Exception as e:
                logger.warning(f"  Ticketmaster request failed (chunk {chunk_idx + 1}, page {page}): {e}")
                break

            embedded = data.get("_embedded", {})
            items = embedded.get("events", [])
            page_info = data.get("page", {})
            total_pages = page_info.get("totalPages", 1)

            if not items:
                break

            for item in items:
                normalised = _normalise_event(item, city_label, currency)
                if normalised:
                    all_events.append(normalised)

            logger.info(f"  Ticketmaster chunk {chunk_idx + 1}/{len(chunks)} page {page + 1}/{total_pages}: {len(items)} events")

            if progress is not None:
                progress["step"] = f"Fetching Ticketmaster events... month {chunk_idx + 1}/{len(chunks)}"
                progress["current"] = chunk_idx + 1
                progress["total"] = len(chunks)

            page += 1
            if page >= total_pages or page > MAX_PAGE:
                break

    logger.info(f"  Ticketmaster fetch complete: {len(all_events)} events")
    return all_events


def _normalise_event(event: dict, city_label: str, currency: str) -> dict | None:
    """Convert a Ticketmaster event into our standard format."""
    if not event:
        return None

    # Parse date
    dates = event.get("dates", {})
    start = dates.get("start", {})
    date_str = start.get("localDate")
    if not date_str:
        return None

    time_str = start.get("localTime", "")
    if time_str:
        try:
            dt = datetime.strptime(f"{date_str}T{time_str}", "%Y-%m-%dT%H:%M:%S")
        except ValueError:
            dt = datetime.strptime(date_str, "%Y-%m-%d")
    else:
        dt = datetime.strptime(date_str, "%Y-%m-%d")

    # Skip cancelled events
    status = dates.get("status", {}).get("code", "")
    if status in ("cancelled", "postponed"):
        return None

    # Venue
    embedded = event.get("_embedded", {})
    venues = embedded.get("venues", [])
    venue_name = venues[0].get("name", "Unknown Venue") if venues else "Unknown Venue"

    # Artists from attractions
    attractions = embedded.get("attractions", [])
    lineup = [a["name"] for a in attractions if a.get("name")]

    title = event.get("name", "")
    event_id = event.get("id", "")
    source_url = event.get("url", "")

    # Price
    price = None
    price_ranges = event.get("priceRanges", [])
    if price_ranges:
        min_price = price_ranges[0].get("min")
        if min_price is not None:
            price = format_price(min_price, currency)

    return {
        "title": title,
        "date": dt,
        "venue_name": venue_name,
        "venue_location": city_label,
        "lineup_raw": ", ".join(lineup) if lineup else None,
        "lineup_parsed": lineup,
        "source_name": "ticketmaster",
        "source_id": event_id,
        "source_url": source_url,
        "ticket_url": source_url,
        "price": price,
    }
