import logging
from datetime import datetime, timedelta
from math import radians, sin, cos, asin, sqrt

import httpx

from app.scrapers.base import RateLimiter

logger = logging.getLogger(__name__)

API_BASE = "https://rest.bandsintown.com"
APP_ID = "wonderland_gig_finder"

# Central London coordinates and radius
LONDON_LAT = 51.5074
LONDON_LON = -0.1278
MAX_DISTANCE_MILES = 15

rate_limiter = RateLimiter(min_delay=0.5)


def _haversine_miles(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Distance in miles between two lat/lon points."""
    lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
    return 2 * 3956 * asin(sqrt(a))


def _is_london(venue: dict) -> bool:
    """Check if a venue is within the London area."""
    lat = venue.get("latitude")
    lon = venue.get("longitude")
    if not lat or not lon:
        # Fall back to city name check
        city = (venue.get("city") or "").lower()
        return "london" in city
    try:
        return _haversine_miles(LONDON_LAT, LONDON_LON, float(lat), float(lon)) <= MAX_DISTANCE_MILES
    except (ValueError, TypeError):
        return False


def _normalise_venue(venue: dict) -> str:
    """Extract a clean venue name."""
    return venue.get("name", "Unknown Venue")


def _parse_datetime(dt_str: str) -> datetime:
    """Parse Bandsintown datetime string."""
    # Format: "2026-04-15T20:00:00"
    for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(dt_str, fmt)
        except ValueError:
            continue
    return datetime.strptime(dt_str[:10], "%Y-%m-%d")


def fetch_events_for_artist(artist_name: str) -> list[dict]:
    """Fetch upcoming London events for an artist from Bandsintown.

    Returns a list of normalised event dicts ready for storage.
    """
    rate_limiter.wait()

    # Date range: today to 60 days out
    today = datetime.now().strftime("%Y-%m-%d")
    end = (datetime.now() + timedelta(days=60)).strftime("%Y-%m-%d")

    try:
        resp = httpx.get(
            f"{API_BASE}/artists/{artist_name}/events",
            params={"app_id": APP_ID, "date": f"{today},{end}"},
            timeout=15,
        )

        if resp.status_code == 404:
            return []
        if resp.status_code == 403:
            logger.warning(f"  Bandsintown 403 for '{artist_name}' — may be rate limited")
            return []
        resp.raise_for_status()

        data = resp.json()
        if isinstance(data, dict):
            # Sometimes returns {"errorMessage": "..."} for unknown artists
            return []

    except Exception as e:
        logger.warning(f"  Bandsintown request failed for '{artist_name}': {e}")
        return []

    events = []
    for raw in data:
        venue = raw.get("venue", {})
        if not _is_london(venue):
            continue

        dt = _parse_datetime(raw.get("datetime", ""))
        venue_name = _normalise_venue(venue)
        lineup = raw.get("lineup", [])
        title = raw.get("title") or ", ".join(lineup) or artist_name

        # Build ticket URL from offers
        offers = raw.get("offers", [])
        ticket_url = None
        for offer in offers:
            if offer.get("url"):
                ticket_url = offer["url"]
                break

        events.append({
            "title": title,
            "date": dt,
            "venue_name": venue_name,
            "venue_location": venue.get("city", "London"),
            "lineup_raw": ", ".join(lineup) if lineup else None,
            "lineup_parsed": lineup,
            "source_name": "bandsintown",
            "source_id": str(raw.get("id", "")),
            "source_url": raw.get("url"),
            "ticket_url": ticket_url,
        })

    return events
