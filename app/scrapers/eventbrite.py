import json
import logging
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx

from app.config import settings
from app.scrapers.base import RateLimiter, parse_iso_datetime

logger = logging.getLogger(__name__)

VENUES_FILE = Path("data/eventbrite_venues.json")
REFRESH_DAYS = 7
API_BASE = "https://www.eventbriteapi.com/v3"
BROWSE_URL = "https://www.eventbrite.co.uk/d/united-kingdom--london/music--events/"

rate_limiter = RateLimiter(min_delay=0.5)


def _headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _load_venues() -> tuple[dict[str, str], datetime | None]:
    """Load venue ID->name map and last_refreshed from JSON file."""
    if not VENUES_FILE.exists():
        return {}, None
    try:
        data = json.loads(VENUES_FILE.read_text())
        venues = data.get("venues", {})
        last_refreshed = None
        if data.get("last_refreshed"):
            last_refreshed = datetime.fromisoformat(data["last_refreshed"])
        return venues, last_refreshed
    except (json.JSONDecodeError, KeyError):
        logger.warning("  Eventbrite venues file corrupt, starting fresh")
        return {}, None


def _save_venues(venues: dict[str, str], last_refreshed: datetime):
    """Write venue ID->name map to JSON file."""
    VENUES_FILE.parent.mkdir(parents=True, exist_ok=True)
    data = {
        "last_refreshed": last_refreshed.isoformat(),
        "venues": venues,
    }
    VENUES_FILE.write_text(json.dumps(data, indent=2))


def _discover_venues(token: str, progress: dict | None = None) -> dict[str, str]:
    """Scrape Eventbrite browse pages to discover venue IDs.

    Fetches London music browse pages, extracts event IDs from URLs,
    then calls the events API to get venue info.
    """
    discovered: dict[str, str] = {}
    event_ids: set[str] = set()

    # Fetch multiple browse pages to find event IDs
    with httpx.Client(timeout=20, follow_redirects=True) as client:
        for page_num in range(1, 6):
            rate_limiter.wait()
            url = BROWSE_URL if page_num == 1 else f"{BROWSE_URL}?page={page_num}"
            try:
                resp = client.get(url)
                resp.raise_for_status()
                # Extract event IDs from URLs like /e/event-name-tickets-123456789
                ids = re.findall(r"/e/[^/]+-tickets-(\d+)", resp.text)
                event_ids.update(ids)
                logger.info(f"  Eventbrite browse page {page_num}: found {len(ids)} event IDs")
            except Exception as e:
                logger.warning(f"  Eventbrite browse page {page_num} failed: {e}")

    logger.info(f"  Eventbrite discovery: {len(event_ids)} unique event IDs from browse pages")

    # Look up each event to get its venue ID
    event_id_list = list(event_ids)
    with httpx.Client(timeout=20) as client:
        for i, event_id in enumerate(event_id_list):
            if progress is not None:
                progress["step"] = f"Discovering Eventbrite venues... event {i + 1}/{len(event_id_list)}"
                progress["current"] = i + 1
                progress["total"] = len(event_id_list)
            rate_limiter.wait()
            try:
                resp = client.get(
                    f"{API_BASE}/events/{event_id}/",
                    headers=_headers(token),
                    params={"expand": "venue"},
                )
                resp.raise_for_status()
                event_data = resp.json()
                venue = event_data.get("venue")
                if venue and venue.get("id"):
                    venue_id = str(venue["id"])
                    venue_name = venue.get("name", "Unknown Venue")
                    discovered[venue_id] = venue_name
            except Exception as e:
                logger.warning(f"  Eventbrite event {event_id} lookup failed: {e}")

    logger.info(f"  Eventbrite discovery: {len(discovered)} venues found")
    return discovered


def _fetch_venue_events(venue_id: str, venue_name: str, token: str) -> list[dict]:
    """Fetch live events for a single venue."""
    events = []
    url = f"{API_BASE}/venues/{venue_id}/events/"
    params = {"status": "live"}

    with httpx.Client(timeout=20) as client:
        while url:
            rate_limiter.wait()
            try:
                resp = client.get(url, headers=_headers(token), params=params)
                resp.raise_for_status()
                data = resp.json()
            except Exception as e:
                logger.warning(f"  Eventbrite venue {venue_name} ({venue_id}) fetch failed: {e}")
                break

            for event in data.get("events", []):
                normalised = _normalise_event(event, venue_name)
                if normalised:
                    events.append(normalised)

            # Eventbrite pagination
            pagination = data.get("pagination", {})
            if pagination.get("has_more_items"):
                page_num = pagination.get("page_number", 1) + 1
                params = {"status": "live", "page": page_num}
            else:
                url = None

    return events


def _normalise_event(event: dict, venue_name: str) -> dict | None:
    """Convert an Eventbrite event into our standard format."""
    start = event.get("start", {})
    dt = parse_iso_datetime(start.get("local"))
    if not dt:
        return None

    title = event.get("name", {}).get("text", "")
    if not title:
        return None

    event_id = str(event.get("id", ""))
    source_url = event.get("url", "")

    # Price: check if free, otherwise try to get from ticket_availability
    is_free = event.get("is_free", False)
    price = "Free" if is_free else None

    return {
        "title": title,
        "date": dt,
        "venue_name": venue_name,
        "venue_location": "London",
        "lineup_raw": title,
        "lineup_parsed": [title],
        "source_name": "eventbrite",
        "source_id": event_id,
        "source_url": source_url,
        "ticket_url": source_url,
        "price": price,
    }


def fetch_london_events(days: int = 270, progress: dict | None = None) -> list[dict]:
    """Fetch London music events from Eventbrite.

    Maintains a local venue ID cache with auto-refresh discovery.
    """
    token = settings.eventbrite_private_token
    if not token:
        logger.warning("  EVENTBRITE_PRIVATE_TOKEN not set, skipping Eventbrite fetch")
        return []

    # Load existing venues
    venues, last_refreshed = _load_venues()

    # Run discovery if stale or missing
    now = datetime.now(timezone.utc)
    needs_refresh = (
        not venues
        or last_refreshed is None
        or (now - last_refreshed) > timedelta(days=REFRESH_DAYS)
    )

    if needs_refresh:
        if progress is not None:
            progress["step"] = "Discovering Eventbrite venues..."
        logger.info("  Eventbrite: running venue discovery...")
        discovered = _discover_venues(token, progress=progress)
        venues.update(discovered)
        _save_venues(venues, now)
        logger.info(f"  Eventbrite: {len(venues)} total venues after discovery")

    if not venues:
        logger.warning("  Eventbrite: no venues found, skipping event fetch")
        return []

    # Fetch events from all venues
    all_events = []
    venue_list = list(venues.items())

    for i, (venue_id, venue_name) in enumerate(venue_list):
        if progress is not None:
            progress["step"] = f"Fetching Eventbrite events... venue {i + 1}/{len(venue_list)}"
            progress["current"] = i + 1
            progress["total"] = len(venue_list)

        events = _fetch_venue_events(venue_id, venue_name, token)
        all_events.extend(events)

    logger.info(f"  Eventbrite fetch complete: {len(all_events)} events from {len(venue_list)} venues")
    return all_events
