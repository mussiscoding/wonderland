---
date: 2026-03-31
idea: Expand event sources beyond RA, Skiddle, Dice, and Ticketmaster
type: extension
extends: event scraping
status: idea
---

# Event Source Expansion

## Current sources (working)

| Source | Method | Notes |
|--------|--------|-------|
| Resident Advisor | Undocumented GraphQL API | Works well, good for electronic/club events |
| Skiddle | Public REST API (key required) | Good for club nights, London radius search |
| Dice | REST API (key required) | Good for DJ/club events |
| Ticketmaster | Public Discovery API (free key) | Added 2026-03-31. Huge catalogue — 2780 London music events over 9 months. Monthly chunking needed to work around 1000-result pagination cap. 5000 calls/day free tier. |

## Investigated and ruled out

| Source | Status | Why |
|--------|--------|-----|
| Eventbrite | Dead | Killed their public event search API in February 2020. Can only query by specific venue ID or organisation ID now — useless for discovery. |
| Bandsintown | Dead | API requires you to claim an artist profile to get a key, and that key only grants access to events for artists you manage. No public event search. Investigated twice (pre-2026-03-31 and again on 2026-03-31), same wall both times. |
| Songkick | Dead | Paid commercial API with license fee. "Currently not approving API requests for student projects, educational purposes or hobbyist purposes." |
| Shotgun | Blocked | No public API. Website is behind Vercel bot protection — can't scrape with simple HTTP requests. Would need Playwright/browser automation, which is a big dependency jump. Strong for London electronic/club events so worth revisiting if we add browser automation. |
| FIXR | Dead | API is organiser-only — designed for event creators to read their own listings, not for third-party discovery. |

## Potential future sources

- **Shotgun** — revisit if we add Playwright. Very relevant for London electronic scene.
- **See Tickets** — major UK ticketing platform, no public API but could be scrapeable.
- **Fatsoma** — smaller promoters, worth investigating.
