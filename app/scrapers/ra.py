import logging
from datetime import datetime, timedelta

import httpx

from app.scrapers.base import RateLimiter

logger = logging.getLogger(__name__)

GRAPHQL_URL = "https://ra.co/graphql"
LONDON_AREA_CODE = 13

HEADERS = {
    "Content-Type": "application/json",
    "Referer": "https://ra.co/events/uk/london",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:106.0)",
}

QUERY = (
    "query GET_EVENT_LISTINGS("
    "$filters: FilterInputDtoInput, "
    "$filterOptions: FilterOptionsInputDtoInput, "
    "$page: Int, $pageSize: Int) {"
    "eventListings(filters: $filters, filterOptions: $filterOptions, "
    "pageSize: $pageSize, page: $page) {"
    "data {id listingDate event {"
    "...eventListingsFields "
    "artists {id name __typename} __typename} __typename} "
    "totalResults __typename}}"
    "fragment eventListingsFields on Event {"
    "id date startTime endTime title contentUrl "
    "flyerFront isTicketed attending "
    "venue {id name contentUrl live __typename} __typename}"
)

PAGE_SIZE = 20

rate_limiter = RateLimiter(min_delay=1.5)


def fetch_london_events(days: int = 60, progress: dict | None = None) -> list[dict]:
    """Fetch all London events from RA for the next N days.

    Returns a list of normalised event dicts ready for storage.
    """
    now = datetime.utcnow()
    start = now.strftime("%Y-%m-%dT00:00:00.000Z")
    end = (now + timedelta(days=days)).strftime("%Y-%m-%dT23:59:59.999Z")

    all_events = []
    page = 1

    while True:
        rate_limiter.wait()

        payload = {
            "operationName": "GET_EVENT_LISTINGS",
            "variables": {
                "filters": {
                    "areas": {"eq": LONDON_AREA_CODE},
                    "listingDate": {"gte": start, "lte": end},
                },
                "filterOptions": {"genre": True},
                "pageSize": PAGE_SIZE,
                "page": page,
            },
            "query": QUERY,
        }

        try:
            resp = httpx.post(
                GRAPHQL_URL, json=payload, headers=HEADERS, timeout=20
            )
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            logger.warning(f"  RA GraphQL request failed (page {page}): {e}")
            break

        listings = data.get("data", {}).get("eventListings", {})
        items = listings.get("data", [])
        total = listings.get("totalResults", 0)

        if not items:
            break

        for item in items:
            event = item.get("event", {})
            normalised = _normalise_event(event)
            if normalised:
                all_events.append(normalised)

        logger.info(f"  RA page {page}: {len(items)} events (total: {total})")

        if progress is not None:
            total_pages = (total + PAGE_SIZE - 1) // PAGE_SIZE
            progress["step"] = f"Fetching RA events... page {page}/{total_pages}"
            progress["current"] = page
            progress["total"] = total_pages

        if page * PAGE_SIZE >= total:
            break
        page += 1

    logger.info(f"  RA fetch complete: {len(all_events)} events")
    return all_events


def _normalise_event(event: dict) -> dict | None:
    """Convert an RA event into our standard format."""
    if not event:
        return None

    venue = event.get("venue", {})
    artists = event.get("artists", [])
    lineup = [a["name"] for a in artists if a.get("name")]

    # Parse date
    date_str = event.get("startTime") or event.get("date")
    if not date_str:
        return None

    try:
        dt = datetime.strptime(date_str[:19], "%Y-%m-%dT%H:%M:%S")
    except ValueError:
        try:
            dt = datetime.strptime(date_str[:10], "%Y-%m-%d")
        except ValueError:
            return None

    title = event.get("title", "")
    venue_name = venue.get("name", "Unknown Venue")
    content_url = event.get("contentUrl", "")
    source_url = f"https://ra.co{content_url}" if content_url else None

    return {
        "title": title,
        "date": dt,
        "venue_name": venue_name,
        "venue_location": "London",
        "lineup_raw": ", ".join(lineup) if lineup else None,
        "lineup_parsed": lineup,
        "source_name": "ra",
        "source_id": str(event.get("id", "")),
        "source_url": source_url,
        "ticket_url": source_url,  # RA event page has ticket links
        "attending": event.get("attending", 0),
    }
