# Event Scrapers

Each scraper fetches upcoming events from a different source and normalises them into a common format consumed by `app/events.py`.

## Common Interface

All scrapers expose a `fetch_events(city_config) -> list[dict]` function. Each returned dict has:

```python
{
    "title": str,           # Event name
    "venue_name": str,      # Normalised venue name
    "venue_location": str,  # City name (e.g. "London")
    "date": datetime,       # Event date/time
    "lineup": list[str],    # Artist names (parsed from title/description)
    "url": str,             # Link to event page
    "price": str | None,    # Formatted price string
    "source": str,          # Source identifier (e.g. "ra", "dice")
}
```

## Scrapers

### Resident Advisor (`ra.py`)
- **Method**: GraphQL API (`ra.co/graphql`)
- **Auth**: None (public API)
- **Rate limit**: 1.5s between requests (strict — RA will block)
- **Key details**: Filters by area code (e.g. 13 = London, 34 = Berlin). Paginates with cursor-based `startIndex`. Lineup comes from `event.artists[].name`.
- **Fragility**: GraphQL schema changes break the scraper. Field names have changed before.

### Dice (`dice.py`)
- **Method**: REST API (`events.dice.fm/v1/events`)
- **Auth**: `x-api-key` header (`DICE_API_KEY` env var)
- **Rate limit**: None enforced, but be respectful
- **Key details**: Filters by `filter=music:dj` and geohash. Returns structured lineup in `lineup[].name`. Paginates with `page_size` + `offset`.

### Skiddle (`skiddle.py`)
- **Method**: REST API (`www.skiddle.com/api/v1/events`)
- **Auth**: API key as query param (`SKIDDLE_API_KEY`)
- **Rate limit**: None enforced
- **Key details**: Searches by latitude/longitude/radius. Filters by `eventcode=CLUB`. Artist names parsed from `artists[].name`. Paginates with `limit` + `offset`.

### Eventbrite (`eventbrite.py`)
- **Method**: REST API for events + HTML scraping for venue discovery
- **Auth**: `EVENTBRITE_TOKEN` env var (Bearer token)
- **Rate limit**: None enforced, but HTML scraping should be gentle
- **Key details**: Two-phase approach:
  1. **Venue discovery**: Scrapes Eventbrite browse pages (`/d/united-kingdom--london/music/`) to find venue organiser IDs. Results cached in `data/eventbrite_venues_{city}.json` with 7-day refresh.
  2. **Event fetch**: Queries API for each discovered venue's upcoming events.
- **Fragility**: HTML scraping for venue discovery breaks when Eventbrite changes page structure. The API itself is stable.
- **Lineup parsing**: Artist names extracted from event title/description text, not structured data.

### Ticketmaster (`ticketmaster.py`)
- **Method**: REST API (Discovery API `app.ticketmaster.com/discovery/v2/events`)
- **Auth**: API key as query param (`TICKETMASTER_API_KEY`)
- **Rate limit**: 5 requests/second (API enforced)
- **Key details**: Searches by `classificationName=music`, DMA ID for city. Paginates with `page` + `size`. Date range chunked by month to avoid API limits. Structured `_embedded.attractions[].name` for lineup.

## Adding a New Scraper

1. Create `app/scrapers/newname.py` with a `fetch_events(city_config)` function
2. Add city-specific params to `app/cities.py` `CITY_CONFIG`
3. Register the scraper in `app/events.py` `_SCRAPERS` list
4. The event pipeline handles dedup, matching, and storage automatically

## Shared Utilities (`base.py`)

- `RateLimiter`: Token-bucket rate limiter with configurable interval
- `parse_iso_datetime(s)`: Parses ISO 8601 date strings to datetime
- `format_price(min_price, max_price, currency)`: Formats price ranges for display
