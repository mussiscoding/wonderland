---
date: 2026-03-30
idea: Filter events by type (single/multi/festival), venue size, distance, and location beyond London
type: extension
extends: event listing & filtering
status: idea
---

# Event Filters: Type, Venue Size, Distance & Location

Right now events are just a flat list filtered by text search. You should be able to narrow down by the kind of night — a solo artist gig is a very different proposition to a multi-room festival. Venue capacity matters too (warehouse vs arena). And the whole thing is hardcoded to London — should be able to set your location, filter by distance, or sort by how far away it is.

## Rough shape
- **Event type filter**: single artist / multi-artist / festival — derive from lineup size and event metadata
- **Venue capacity**: small / medium / large, or a slider. Would need venue data enrichment (capacity isn't in current scraper data)
- **Location**: replace hardcoded London with user-settable location. Store lat/lng per user.
- **Distance sorting**: order events by distance from user's location
- **Distance filter**: "within X miles" radius filter
- **Multi-city**: scrapers would need to support location params rather than hardcoded London area codes
- ~~**Date quick filters**: "Tonight", "This weekend", "This week", "This month", "All time" as one-click buttons~~ ✅ done
- ~~**Date range picker**: calendar-based custom date range selection alongside the quick filters~~ ✅ done

## Open questions
- Where does venue capacity data come from? Scrapers don't currently provide it. Manual enrichment? Third-party API?
- How to classify event type — just lineup count, or do sources give us metadata (e.g. RA has "festival" tags)?
- How to get user location — browser geolocation, or just let them type a city/postcode?
- Do all scrapers support location params? RA uses area codes, Skiddle uses lat/lng radius, Dice is unclear
