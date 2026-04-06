---
title: "feat: Multi-city support (London + Berlin)"
type: feat
status: active
date: 2026-04-06
---

# Multi-City Support (London + Berlin)

## Overview

Add city selection to the events page and fetch flow so users can view and fetch events for London or Berlin. City is a query param (`?city=london`), defaulting to London. No user preference storage.

## Key Decisions

- **City identifiers**: query params are lowercase (`london`, `berlin`), `venue_location` stores title case (`London`, `Berlin`), mapping dict handles conversion
- **Central city config**: single `CITY_CONFIG` dict with per-city scraper params (area codes, coordinates, country codes, currency symbols, browse URLs)
- **Scraper refactor**: `fetch_london_events(days, progress)` → `fetch_events(city, days, progress)` with city config lookup; skip unsupported scrapers gracefully
- **Dedupe key**: add city component, migration to recompute existing keys
- **Currency**: determined by city at scrape time (London=£, Berlin=€)
- **Eventbrite venue cache**: separate files per city
- **Fetch form**: inherits current page's city filter; redirect preserves city
- **Events page filter**: London / Berlin / All, default London
- **Preserve all other filters** (search, sort, dates, show_all) when switching city
- **Artist detail**: plain text city column between Venue and Price
- **Progress for "Both"**: single combined progress, step messages include city name

## Scraper Availability

| Scraper | London | Berlin | Notes |
|---|---|---|---|
| RA | area 13 | area 34 | GraphQL `areas.eq` param |
| Dice | `london` | skip | 403 for Berlin |
| Skiddle | lat/lon 51.50/-0.12 | skip | UK-only |
| Ticketmaster | city=London, CC=GB | city=Berlin, CC=DE | Works |
| Eventbrite | uk/london browse | germany/berlin browse | Separate venue caches |

## Implementation Plan

### Phase 1: City Config + Scraper Refactor

#### 1a. Create city config (`app/cities.py`)

```python
CITY_CONFIG = {
    "london": {
        "label": "London",
        "currency": "£",
        "ra_area_code": 13,
        "ticketmaster": {"city": "London", "countryCode": "GB"},
        "dice_city": "london",
        "skiddle": {"lat": 51.5074, "lon": -0.1278, "radius": 15},
        "eventbrite_browse": "https://www.eventbrite.co.uk/d/united-kingdom--london/music--events/",
        "eventbrite_venue_file": "data/eventbrite_venues_london.json",
        "scrapers": ["ra", "dice", "skiddle", "ticketmaster", "eventbrite"],
    },
    "berlin": {
        "label": "Berlin",
        "currency": "€",
        "ra_area_code": 34,
        "ticketmaster": {"city": "Berlin", "countryCode": "DE"},
        "dice_city": None,  # not supported
        "skiddle": None,  # not supported
        "eventbrite_browse": "https://www.eventbrite.de/d/germany--berlin/music--events/",
        "eventbrite_venue_file": "data/eventbrite_venues_berlin.json",
        "scrapers": ["ra", "ticketmaster", "eventbrite"],
    },
}
```

#### 1b. Refactor each scraper

Each scraper's `fetch_london_events(days, progress)` becomes `fetch_events(city_config, days, progress)` where `city_config` is the relevant dict from `CITY_CONFIG`.

Changes per scraper:
- **RA** (`app/scrapers/ra.py`): Accept area code from config instead of `LONDON_AREA_CODE`. Update Referer header. Pass currency to `_normalise_event`. Set `venue_location` from config label.
- **Dice** (`app/scrapers/dice.py`): Accept city slug from config. Return `[]` early if `dice_city` is None.
- **Skiddle** (`app/scrapers/skiddle.py`): Accept lat/lon/radius from config. Return `[]` early if `skiddle` is None.
- **Ticketmaster** (`app/scrapers/ticketmaster.py`): Accept city/countryCode from config.
- **Eventbrite** (`app/scrapers/eventbrite.py`): Accept browse URL and venue file path from config.

Currency: each scraper's `_normalise_event` / `_parse_cost` uses the currency symbol from config instead of hardcoded `£`.

#### 1c. Update orchestrator (`app/events.py`)

- `fetch_all_events(session, user_id)` → `fetch_all_events(session, user_id, cities)`
- `cities` is a list like `["london"]` or `["london", "berlin"]`
- Loop over cities, then loop over that city's scraper list
- Progress messages include city name: `"Fetching RA events (Berlin)..."`
- Import from `app/cities` instead of individual scraper modules

#### 1d. Fix dedupe key (`app/events.py`)

- `_dedupe_key(venue_name, date)` → `_dedupe_key(venue_name, date, city)`
- Key format: `"{normalised_venue}_{city}_{date}"`
- Each scraper result dict already has `venue_location`; use that

### Phase 2: Data Migration

- Backfill any `NULL` `venue_location` values to `"London"`
- Recompute `dedupe_key` for all existing events to include `"london"` component
- Rename existing `data/eventbrite_venues.json` → `data/eventbrite_venues_london.json`

### Phase 3: Routes + Templates

#### 3a. Fetch form (`app/routes/events.py`)

- `POST /events/fetch` reads `city` form field (default `"london"`, options: `london`, `berlin`, `both`)
- Pass city list to `_run_fetch_background` → `fetch_all_events`
- After fetch, redirect to `/events/fetch/progress?city={city}` to preserve context
- After progress complete, redirect to `/events?city={city}`

#### 3b. Events list route (`app/routes/events.py`)

- Add `city: str = ""` query param to `list_events`
- Default to `"london"` if empty
- Filter events at DB query level: `select(Event).where(Event.venue_location == city_label)` (or no filter if `city == "all"`)
- Pass `city` to template context
- All redirect/link constructions include `city` param

#### 3c. Events template (`app/templates/events.html`)

- Add city dropdown (London / Berlin / All) in the filter controls area
- Thread `city` param through all existing URL constructions (sort links, show_all toggle, date filters, search form)
- Update empty state message to be city-aware
- Fetch form includes hidden or select input for city, defaulting to current filter

#### 3d. Artist detail template (`app/templates/artist_detail.html`)

- Add "City" column between Venue and Price in the matched events table
- Show `event.venue_location` as plain text
- Route (`app/routes/artists.py`) already loads the event objects which have `venue_location`

### Phase 4: Front-End Spec

- Update `docs/front-end-spec.md` with city filter behaviour, fetch form changes, and artist detail column addition

## Acceptance Criteria

- [ ] City dropdown on events page filters events by venue_location
- [ ] Default city is London
- [ ] Fetch form has city selector (London / Berlin / Both)
- [ ] Berlin fetch uses RA (area 34), Ticketmaster (DE), Eventbrite (Berlin browse)
- [ ] Dice and Skiddle are skipped gracefully for Berlin
- [ ] Berlin event prices show € not £
- [ ] Dedupe key includes city — no cross-city collisions
- [ ] Existing London events have dedupe keys migrated
- [ ] All existing filter controls (sort, search, dates, show_all) preserve city param
- [ ] Artist detail page shows city column on matched events
- [ ] Progress messages include city name when fetching
- [ ] Front-end spec updated

## Files to Change

| File | Changes |
|---|---|
| `app/cities.py` | **New** — CITY_CONFIG dict |
| `app/scrapers/ra.py` | Accept city config, parameterize area code + currency |
| `app/scrapers/dice.py` | Accept city config, skip if unsupported |
| `app/scrapers/skiddle.py` | Accept city config, skip if unsupported |
| `app/scrapers/ticketmaster.py` | Accept city config, parameterize city/country |
| `app/scrapers/eventbrite.py` | Accept city config, parameterize browse URL + venue cache |
| `app/events.py` | Accept cities param, city-aware dedupe key, city-aware orchestration |
| `app/routes/events.py` | City param on list_events, city on fetch form, thread through redirects |
| `app/templates/events.html` | City dropdown, thread city through all URLs, city-aware empty state |
| `app/templates/artist_detail.html` | Add city column |
| `app/routes/artists.py` | Ensure event.venue_location available in template context |
| `docs/front-end-spec.md` | Document city filter behaviour |
| `data/eventbrite_venues.json` | Rename to `eventbrite_venues_london.json` |

## References

- Brainstorm: `docs/brainstorms/2026-04-06-multi-city-support-brainstorm.md`
- RA Berlin area code: 34 (confirmed via GraphQL probe)
- Ticketmaster Berlin: `city=Berlin, countryCode=DE` (52 results confirmed)
- Eventbrite Berlin: browse page returns 56 event IDs (confirmed)
