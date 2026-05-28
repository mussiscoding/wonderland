---
date: 2026-05-28
topic: broaden-event-sources
---

# Broadening Event Sources Beyond Dance

> **Outcome (2026-05-28): Ents24 is BLOCKED.** Its API is alive but the self-service developer portal (`developers.ents24.com`) is dead (NXDOMAIN) — no way to get a key without emailing them (untried). See the ruled-out registry in `docs/ideas/done/2026-03-31-event-source-expansion.md`. The genre-broadening lever for now is de-dance-ifying DICE/Skiddle (`docs/ideas/2026-05-28-de-dance-ify-source-filters.md`). The analysis below stands, but its recommended next step (build the Ents24 scraper) is on hold pending email access.

## What We're Building

The app's five sources (RA, DICE, Skiddle, Eventbrite, Ticketmaster) are tuned for dance — DICE filters `music:dj`, Skiddle filters `eventcode=CLUB`, RA is dance-only by nature. We want to broaden coverage to the app's other genre profiles (Jazz, Rock, Pop, Country). The first step is adding **Ents24** as a new, genre-agnostic UK listings source.

## Why This Approach

Research across jazz, rock/metal/folk/country, and general aggregators found a clear pattern: **there is no "RA equivalent" with an API for non-dance genres.** Genre-specific platforms are editorial gig guides (blogs, prose tour announcements), not scrapable feeds. Several once-obvious candidates are dead or closed: Songkick (API closed to new keys), Last.fm events (API removed), Gigwise, fROOTS, Eventful, Festicket.

The leverage is therefore in **genre-agnostic aggregators with genre filters**, not per-genre integrations. Ents24 is the best available: a confirmed-live (2026) open UK REST API with the deepest UK live-events database (~10k new listings/week), event/venue/artist endpoints, and genre + location + date filtering. It fits the existing `fetch_events(city_config)` scraper interface directly.

**Setlist.fm was considered and dropped** — it only carries *historical* setlists, so it can't surface upcoming events. Useful one day as artist-matching enrichment, but a different problem.

## Key Decisions

- **Add Ents24 as the first non-dance source.** Open API, fits existing scraper pattern, broadens all genres at once. — Rationale: highest leverage per integration; no genre-specific source with an API exists to add instead.
- **Don't build per-genre scrapers (jazz/rock/metal/folk/country).** — Rationale: those verticals are editorial blogs with no structured feed. Genre coverage comes from filtering aggregators (Ents24, plus the already-integrated Ticketmaster's Rock/Metal/Folk/Country/Punk subgenre classifications and Skiddle).
- **Drop Setlist.fm from this effort.** — Rationale: historical-only, not forward-looking.

## Ents24 integration notes (for planning)

- **Method**: REST API, base URL `https://api.ents24.com`. Official PHP client + public docs repo exist on GitHub (`Ents24/public-api-docs`, `Ents24/ents24-api-client`).
- **Auth**: Client credentials (register as an Ents24 user to create app credentials). New env var, e.g. `ENTS24_CLIENT_ID` / `ENTS24_CLIENT_SECRET`.
- **Filtering**: `event/list` supports location, distance, genre, and date-range params; `event/genres` returns the valid genre vocabulary.
- **Fits the pattern**: new `app/scrapers/ents24.py` with `fetch_events(city_config)`, city params in `app/cities.py`, register in `app/events.py` `_SCRAPERS`. Pipeline handles dedup/matching/storage.

## Open Questions

- **Genre filtering strategy.** Ents24 supports genre params. Do we (a) pull *all* genres and let the existing fuzzy-matching + genre-profile scoring do the filtering, or (b) pass the user's active genre profile through to the Ents24 query? Option (a) is simpler and matches how RA/DICE results are scored downstream; (b) reduces volume but couples the scraper to profile state. Lean (a) for v1.
- **Ents24 genre vocabulary → app genre taxonomy mapping.** Ents24's genre list (`event/genres`) won't match the app's Spotify-derived genres. Need a mapping or reliance on lineup fuzzy-matching. Likely defer to matching, same as other sources.
- **Lineup data quality.** Need to confirm whether Ents24 returns structured artist/lineup fields or whether lineup must be parsed from title/description (as with Eventbrite). Determines matching accuracy.
- **Follow-on (out of scope here): de-dance-ify existing sources.** DICE `music:dj` and Skiddle `eventcode=CLUB` still restrict to dance. Broadening fully will eventually mean making those filters profile-aware. Tracked separately.

## Next Steps

→ `/workflows:plan` for the Ents24 scraper implementation. Verify API access (register, get credentials, confirm lineup field shape) as the first planning task.
