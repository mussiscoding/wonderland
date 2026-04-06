---
date: 2026-04-06
topic: multi-city-support
---

# Multi-City Support (London + Berlin)

## What We're Building

Add a city dropdown to the events page and fetch flow so users can view and fetch events for London or Berlin independently. No user preference storage — just a query param filter.

## Why This Approach

Simplest possible path: the `venue_location` field already exists on every event, scrapers just need a city parameter, and the events list page just needs a dropdown that filters on `venue_location`. No schema changes, no user preferences, no complex state.

## Key Decisions

- **City as query param, not user setting**: Users may want to check multiple cities in one sitting. `?city=london` / `?city=berlin` on the events page, defaulting to London.
- **Fetch is per-city**: The fetch form gets a city selector. Only fetches events for the chosen city, so fetch time doesn't double. Can also offer "Both" option.
- **Scraper availability by city**:
  - London: RA (area 13), Dice, Skiddle, Ticketmaster, Eventbrite — all 5
  - Berlin: RA (area 34), Ticketmaster (city=Berlin, countryCode=DE), Eventbrite (browse Berlin page) — 3 of 5
  - Dice returned 403 for Berlin, Skiddle is UK-only
- **No DB schema changes**: `venue_location` already exists. Events from both cities coexist in the same table. Artist matching is city-agnostic.
- **No performance concerns**: Doubling events is trivial at current scale. Could add an index on `venue_location` later if needed.

## Scope

### Scrapers
- Refactor each scraper's `fetch_london_events(days)` → `fetch_events(city, days)` with a city config dict mapping city names to API params (area codes, lat/lon, country codes, etc.)
- Skip scrapers that don't support the requested city (Dice/Skiddle for Berlin)

### Fetch flow
- Add city selector to the fetch form (London / Berlin / Both)
- Pass city through to the fetch worker

### Events list page
- Add city dropdown filter (query param `?city=`)
- Default to "All" or "London" (TBD)
- Filter events by `venue_location`

## Resolved Questions

- Default filter: **London** (not "All")
- Artist detail pages: **add a city column** to the matched events shown there

## Next Steps

→ `/workflows:plan` for implementation details
