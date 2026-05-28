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
| Last.fm events | Dead | The `event.*` API methods were removed years ago. Events still display on the website but there is no API to read them. |
| Setlist.fm | Useless for us | Open free API, but it only carries **historical** setlists (what an artist played in the past), not upcoming events. We're an event-*discovery* app — past gigs are no use. Don't reconsider it as a listings source. |
| Ents24 | Blocked (email-only) | **Trap — looks open but isn't.** REST API at `api.ents24.com` is alive (returns 401, i.e. needs a key) and returns excellent *structured* data (artists[], per-stage festival lineups, genre[], venue lat/lon, tickets — all inline on `event/list`). BUT the self-service developer portal is gone: `developers.ents24.com` is **NXDOMAIN** (2026-05-28) and the `Ents24/public-api-docs` GitHub repo was archived April 2026. Live ents24.com has no developer/API link. No way to get a key without contacting them. Possible email path (events@ents24.com / partner enquiry) — untried as of 2026-05-28, worth pursuing if we want a genre-agnostic UK source. |
| Shotgun | Blocked | No public API. Website is behind Vercel bot protection — can't scrape with simple HTTP requests. Would need Playwright/browser automation, which is a big dependency jump. Strong for London electronic/club events so worth revisiting if we add browser automation. |
| FIXR | Dead | API is organiser-only — designed for event creators to read their own listings, not for third-party discovery. |
| Fever (feverup.com) | Blocked | No public API. Internal search gateway exists (`data-search.apigw.feverup.com`) but endpoints aren't discoverable without reverse-engineering JS bundles. Same category as Shotgun — would need browser automation. |

## Lesson: verify API access against live DNS, not search results

Search engines and LLM research agents serve **cached** docs — they happily describe a developer portal that no longer resolves (this is exactly how Ents24 wasted a research cycle on 2026-05-28). Before recommending or planning any new source, confirm self-service signup actually exists *today*: resolve the developer-portal hostname (`nslookup`), curl it, and check the live main site for a developer link. A 401 from the API base means "alive, needs key"; NXDOMAIN on the portal means "you can't get a key." The same trap killed Songkick and Bandsintown — the API exists, but not for new self-service applicants.

## Potential future sources

- **Shotgun** — revisit if we add Playwright. Very relevant for London electronic scene.
- **See Tickets** — major UK ticketing platform, no public API but could be scrapeable.
- **Fatsoma** — smaller promoters, worth investigating.
