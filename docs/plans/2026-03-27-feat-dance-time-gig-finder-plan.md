---
title: "feat: wonderland gig finder"
type: feat
status: active
date: 2026-03-27
---

# wonderland: London Gig Finder for Dance Music

## Overview

A personal tool that pulls your Spotify listening history, helps you identify which artists you'd actually want to see live (distinct from "listen to most"), fetches London events from multiple sources, and matches them — surfacing gigs you'd otherwise miss.

Brainstorm: `docs/brainstorms/2026-03-27-wonderland-brainstorm.md`

## Proposed Solution

Python app using FastAPI + SQLite + HTMX. The pipeline:

1. **Import** artists from Spotify (top artists, followed, saved tracks, playlists, recently played)
2. **Score & Filter** using genre tags + listening signals (auto-scoring)
3. **Curate** — user adjusts "want to see live" scores, independent of play count
4. **Fetch Events** from Bandsintown, RA, Skiddle, Dice (in that priority order)
5. **Match** curated artists to event lineups (fuzzy matching, lineup parsing)
6. **Score Events** by artist relevance and lineup overlap
7. **Display** ranked results in a web UI

## Tech Stack

- **Python 3.12+**
- **FastAPI** — web framework, API + HTML serving
- **SQLite** — persistence (via SQLModel)
- **Jinja2 + HTMX** — simple interactive UI without a JS framework
- **spotipy** — Spotify OAuth (PKCE) + API calls
- **rapidfuzz** — fuzzy artist name matching
- **requests / httpx** — scraping + API calls
- **BeautifulSoup4** — HTML parsing for scraped sources
- **APScheduler** — periodic event fetching (optional, can start with manual refresh)

## Data Model

```
┌──────────────┐       ┌──────────────────┐       ┌──────────────┐
│   Artist     │       │   Event          │       │   EventSource│
├──────────────┤       ├──────────────────┤       ├──────────────┤
│ id           │       │ id               │       │ id           │
│ spotify_id   │       │ title            │       │ event_id  FK │
│ name         │       │ date             │       │ source_name  │
│ genres[]     │       │ venue_name       │       │ source_id    │
│ auto_score   │       │ venue_location   │       │ source_url   │
│ manual_score │       │ lineup_raw       │       │ ticket_url   │
│ excluded     │       │ lineup_parsed[]  │       │ price        │
│ source_signals│      │ dedupe_key       │       │ last_fetched │
│ created_at   │       │ created_at       │       └──────────────┘
│ updated_at   │       │ updated_at       │
└──────┬───────┘       └──────┬───────────┘
       │                      │
       │    ┌─────────────┐   │
       └───►│   Match     │◄──┘
            ├─────────────┤
            │ artist_id FK│
            │ event_id  FK│
            │ confidence  │
            │ match_type  │  (exact, fuzzy, alias)
            │ matched_name│  (what string actually matched)
            └─────────────┘
```

**Key decisions:**
- `auto_score` (0-100) is computed from signals. `manual_score` (nullable) overrides when set.
- `excluded` flag = "never show this artist" (distinct from low score).
- `dedupe_key` on Event = normalised(venue_name + date) for cross-source deduplication.
- `EventSource` is a join table — one Event can come from multiple sources, we keep all source URLs/prices.
- `lineup_parsed` stored as JSON array of individual artist names after parsing.
- `source_signals` on Artist stored as JSON — breakdown of why the auto-score is what it is (for transparency in the UI).

## Auto-Scoring Formula

**Genre multiplier** (primary lever):
- Electronic/dance genres (techno, house, drum and bass, garage, etc.): `1.0x`
- Adjacent genres (ambient, experimental, downtempo): `0.5x`
- Everything else: `0.1x`
- No genre tags: `0.3x` (benefit of the doubt)

Genre classification will need a mapping of Spotify genre strings to these buckets. Spotify has hundreds of micro-genres ("dark progressive house", "uk garage", etc.) — start with keyword matching on the genre string (contains "techno", "house", "bass", etc.) and refine.

**Listening signal score** (additive, before genre multiplier):
| Signal | Points | Cap |
|--------|--------|-----|
| Followed artist | 30 | 30 |
| Saved/hearted tracks | 5 per track | 25 |
| Intentional listening (artist/album context) | 3 per play | 20 |
| Playlist appearances | 2 per playlist | 15 |
| Top artist (any time range) | 10 | 10 |

**Final auto_score** = `genre_multiplier * sum_of_signals`, capped at 100.

**Effective score** = `manual_score` if set, otherwise `auto_score`. Excluded artists are never shown in event results.

All artists appear in the curate view (sorted by score), no hard threshold. A visual divider at score ~30 separates "likely relevant" from "probably not" as a starting guide.

## Event Scoring Formula

For each matched event:
- Sum the effective scores of all matched artists on the lineup
- Bonus: `+20` for each additional matched artist beyond the first (rewards multi-match lineups)
- Normalise to 0-100 range

Display: events sorted by score descending. Show which artists matched and their individual scores.

## Implementation Phases

### Phase 1: Foundation + Spotify Import

Get the project scaffolded, Spotify connected, and artists imported into the database.

**Tasks:**
- [x] `app/main.py` — FastAPI app with basic routing
- [x] `app/models.py` — SQLModel models for Artist, Event, EventSource, Match
- [x] `app/database.py` — SQLite connection, table creation
- [x] `app/auth.py` — Spotify OAuth PKCE flow using spotipy
  - Register app at developer.spotify.com
  - Redirect URI: `http://127.0.0.1:8000/callback` (not localhost — banned since Nov 2025)
  - Scopes: `user-top-read`, `user-follow-read`, `user-library-read`, `user-read-recently-played`
  - Persist refresh token in DB so auth is one-time
- [x] `app/spotify.py` — Import logic: pull top artists (3 time ranges), followed artists, saved tracks (paginated, extract unique artists), playlist tracks (all user playlists, extract unique artists), recently played (with context field)
  - Deduplicate by spotify_id
  - Store genre tags, source signals per artist
  - Handle pagination — saved tracks can be 10K+, ~200 API calls. Use token refresh if needed mid-import.
- [x] `app/scoring.py` — Auto-scoring: genre classification + listening signal weights
  - Genre keyword matching on Spotify genre strings
  - Compute and store auto_score + source_signals breakdown
- [x] `app/templates/artists.html` — Basic artist list page (Jinja2 + HTMX)
  - Sortable by score
  - Show: name, genres, auto_score, source signal breakdown
  - Search/filter box
  - Genre filter toggles
- [x] `requirements.txt` — fastapi, uvicorn, sqlmodel, spotipy, rapidfuzz, httpx, beautifulsoup4, jinja2, python-multipart
- [x] `.gitignore` — data/*.db, .env, __pycache__, .spotipy_cache
- [x] `.env.example` — SPOTIFY_CLIENT_ID, SPOTIFY_REDIRECT_URI

**Acceptance criteria:**
- [x] Can authenticate with Spotify via browser
- [x] All artists from Spotify are imported and stored with genre tags
- [x] Auto-scores are computed and visible in the web UI
- [x] Artist list is browsable, searchable, filterable by genre

### Phase 1a: Genre Classification + Scoring Refinement

Additions built after the initial Phase 1 import, before curation. Gives the user control over how genres map to scoring categories, and refines the artist list UI.

**Tasks:**
- [x] `app/models.py` — `GenreClassification` model (name, category) for DB-driven genre-to-category mapping
- [x] `app/templating.py` — Extracted shared Jinja2 templates config
- [x] `app/routes/genres.py` — Genre management page
  - `GET /genres` — List all genres with search (`q`) and category filter
  - Auto-populates `GenreClassification` table from imported artists' genres on first visit
  - Shows artist count per genre
  - `POST /genres/{id}/classify` — Set a genre's category (dance/adjacent/other) with HTMX inline update
  - `POST /genres/bulk-classify` — Bulk-classify multiple genres at once
  - `POST /genres/rescore` — Recompute all artist `auto_score` values using current genre classifications
- [x] `app/templates/genres.html` — Genre list page with search, category filter, and "Rescore Artists" button
- [x] `app/templates/genre_row.html` — HTMX partial for a single genre row with D/A/O classification buttons
- [x] `app/scoring.py` — DB-driven genre scoring
  - `get_genre_map(session)` — Loads genre→category mapping from `GenreClassification` table
  - `genre_multiplier()` — Uses best category across all artist genres (was keyword matching, now DB-driven)
- [x] `app/templates/artists.html` enhancements
  - Genre tags color-coded by classification category (dance=green, adjacent=amber)
  - Visual score divider at 30 ("below this line: probably not going to dance to these")
  - `genre_map` passed to template for category-aware rendering

**Acceptance criteria:**
- [x] All genres from imported artists appear in the genres page
- [x] Can classify genres as dance/adjacent/other via inline buttons
- [x] Can bulk-classify multiple genres
- [x] Rescoring updates all artist auto_scores based on current classifications
- [x] Artist list shows genre tags with category-aware coloring

### Phase 2: Curation

Let the user adjust scores and exclude artists.

**Tasks:**
- [ ] `app/templates/curate.html` — Curation interface
  - Each artist row: name, genres, auto_score, manual_score input, exclude toggle
  - HTMX for inline score updates (no full page reload)
  - Bulk actions: "exclude all non-electronic" button (uses genre filter)
  - Visual divider at score threshold
  - Show source signal breakdown on hover/expand (why was this auto-scored this way?)
- [ ] `app/routes/artists.py` — API endpoints for updating manual_score and excluded flag
  - `PATCH /api/artists/{id}` — update manual_score or excluded
  - `POST /api/artists/bulk-exclude` — exclude by genre filter
- [x] Re-import flow: button to re-pull Spotify data
  - New artists get auto-scored and flagged as "new" for review
  - Existing artists keep their manual_score and excluded status
  - Artists that disappear from Spotify are kept (scores persist)

**Acceptance criteria:**
- [ ] Can set manual scores on individual artists
- [ ] Can exclude artists (they disappear from event matching)
- [ ] Can bulk-exclude by genre
- [x] Re-import preserves manual scores
- [ ] Source signal breakdown is visible

### Phase 3: Event Fetching — Bandsintown *(abandoned)*

Originally planned as the first event source, but we went straight to RA (Phase 5) instead since it's more valuable for London electronic music. Bandsintown scraper code exists (`app/scrapers/bandsintown.py`) but is unused.

**Tasks:**
- [x] `app/scrapers/base.py` — Common interface for all scrapers
  - Rate limiting helper
  - Error handling: log failures, continue with other sources
- [x] `app/events.py` — Event deduplication logic
  - `dedupe_key` = normalise(venue_name) + date
  - When duplicate found: merge lineup data (union of artists), keep all EventSource records
- [x] Event time window: next 60 days by default
- [x] `app/templates/events.html` — Basic event list

### Phase 4: Matching + Event Scoring

The core value — connect your artists to events.

**Tasks:**
- [x] `app/matching.py` — Lineup parsing
  - Split raw lineup strings on: commas, semicolons, pipes, newlines, " / "
  - Detect and handle: "b2b", "&", "feat.", "ft.", "presents:", "all night long"
  - Strip suffixes: "(Live)", "(DJ Set)", "(DJ)", "& Friends"
  - Ignore: "residents", "TBA", "TBC", "special guest", promoter names
  - Room/stage splits: "Room 1: A, B / Room 2: C, D" — flatten to [A, B, C, D]
  - Store parsed lineup as JSON array on Event
- [x] `app/matching.py` — Artist matching
  - Normalise both sides: lowercase, strip punctuation, remove "DJ"/"MC" prefixes
  - Use `rapidfuzz.fuzz.token_set_ratio` with threshold of 75 (loose, as decided)
  - Try exact normalised match first (fast path), fuzzy only if no exact match
  - Log all matches with confidence scores
  - Log unmatched lineup artists for review (helps calibrate threshold)
  - Store Match records: artist_id, event_id, confidence, match_type, matched_name
- [x] `app/scoring.py` — Event scoring
  - Sum effective scores of matched artists
  - +20 bonus per additional matched artist beyond first
  - Normalise to 0-100
- [x] `app/templates/events.html` — Matched events view
  - Sorted by event score descending
  - Each event shows: title, date, venue, matched artists (highlighted in lineup), event score, ticket link
  - Unmatched events hidden by default, toggle to show all

**Acceptance criteria:**
- [x] Lineup strings are correctly parsed into individual artist names
- [x] Fuzzy matching finds artists with name variations
- [x] Events are scored and ranked
- [x] Matched events display with highlighted artists
- [ ] Match log available for threshold calibration

### Phase 5: RA Scraper

The most valuable source for London electronic music.

**Tasks:**
- [x] `app/scrapers/ra.py` — Resident Advisor scraper
  - Use GraphQL API (reverse-engineered, queries stored in config for easy updates)
  - Query: London events (area code 13), next 60 days
  - Extract: event title, date, venue, lineup, event URL
  - Fallback: parse `ld+json` structured data from event pages if GraphQL breaks
  - Rate limiting: polite delays between requests (1-2 seconds)
  - Error handling: if RA scraper fails, log warning and continue with other sources
- [x] Integrate into event fetch pipeline
  - Run alongside Bandsintown
  - Deduplication catches events appearing on both sources
- [x] ~~Test against 20-30 real RA event pages to validate lineup parsing~~ (works, not needed)

**Acceptance criteria:**
- [x] RA events fetched and stored
- [x] Lineups parsed correctly from RA's format
- [x] Deduplication works across RA + Bandsintown
- [x] Scraper fails gracefully if RA changes their API

### Phase 6: Skiddle + Dice Scrapers

**Tasks:**
- [x] `app/scrapers/skiddle.py` — Skiddle API integration
  - Free API key from skiddle.com/api
  - Location-first query: events near London, genre filter for dance/electronic
  - Normalise into Event model
- [x] `app/scrapers/dice.py` — Dice.fm scraper
  - Reverse-engineer frontend GraphQL or parse HTML
  - London electronic events
  - Rate limiting, error handling, graceful failure
- [x] Event deduplication across active sources (RA + Skiddle)
- [ ] Dashboard: show which sources last fetched successfully and when

**Acceptance criteria:**
- [x] All 3 event sources operational (RA + Skiddle + Dice; Bandsintown abandoned)
- [x] Deduplication handles cross-source overlap
- [ ] Source health visible in UI

### Phase 7: Polish + Ongoing Use

**Tasks:**
- [x] Manual refresh button in UI (re-fetch events on demand)
- [ ] "Last refreshed" timestamp visible per source
- [ ] "New since last visit" indicator on events
- [ ] Stale event cleanup: auto-hide events after their date passes
- [ ] MusicBrainz alias lookup for unmatched artists (async, cached)
- [ ] Manual alias table: user can add custom name mappings for tricky artists
- [ ] Export matched events (CSV/calendar format)
- [ ] Basic error handling: token refresh failures, scraper failures surfaced in UI

## Project Structure

```
wonderland/
  app/
    main.py              # FastAPI app, route registration
    database.py          # SQLite connection, init
    models.py            # SQLModel models (Artist, Event, EventSource, Match)
    auth.py              # Spotify OAuth PKCE via spotipy
    spotify.py           # Spotify import logic
    scoring.py           # Auto-scoring + event scoring
    matching.py          # Lineup parsing + fuzzy matching
    events.py            # Event deduplication, fetch orchestration
    scrapers/
      base.py            # Common scraper interface
      bandsintown.py
      ra.py
      skiddle.py
      dice.py
    routes/
      artists.py         # Artist CRUD + curation endpoints
      events.py          # Event listing + matching endpoints
      auth.py            # OAuth callback routes
    templates/
      base.html          # Layout template
      artists.html       # Artist list / curation
      events.html        # Matched event results
  data/                  # SQLite DB lives here (gitignored)
  docs/
    brainstorms/
    plans/
  requirements.txt
  .env.example
  .gitignore
```

## Key Technical Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Framework | FastAPI | Async (good for many API calls), auto-docs, Pydantic validation, modern Python |
| Database | SQLite via SQLModel | Zero setup, file-based, relational queries for matching/dedup, perfect for personal tool |
| UI | Jinja2 + HTMX | Interactive without a JS framework, server-rendered, simple |
| Spotify auth | PKCE via spotipy | No client secret needed, one-time browser auth then refresh token forever |
| Fuzzy matching | rapidfuzz token_set_ratio | Best-in-class speed, handles subset matching ("Bicep" matches "Bicep (Live)") |
| Matching threshold | 75 (loose) | Prefer false positives over missed events — user said start loose, tighten if noisy |
| Event sources | Bandsintown → RA → Skiddle → Dice | Easiest API first to validate pipeline, then most valuable scraping target, then fill in |
| Event window | 60 days | Balances coverage with data volume, adjustable later |
| London boundary | ~15 mile radius from 51.5074, -0.1278 | Covers Greater London, source-specific params where possible |

## Spotify API Notes

- **Premium required** for dev mode apps (as of March 9, 2026)
- **Redirect URI must be `http://127.0.0.1:PORT/callback`** (not localhost — banned Nov 2025)
- **Rate limit:** ~180 requests/minute rolling. Large initial import (500+ calls for heavy users) takes ~3 minutes.
- **Token lifetime:** 1 hour. Persist refresh token, auto-refresh before expiry.
- **Pagination:** Saved tracks can be 10K+ (200+ pages). Handle gracefully.
- **Recently played context field:** `context.type` of "artist" or "album" = intentional listening signal.

## Open Questions Resolved

| Question | Answer |
|----------|--------|
| Tech stack | Python, FastAPI, SQLite, HTMX |
| Persistence | SQLite (single file in data/) |
| Event refresh frequency | Manual for v1 (button in UI), scheduled later |
| Event source priority | Bandsintown → RA → Skiddle → Dice |
| Geographic boundary | ~15 miles from central London |
| Event time window | 60 days |
| Score range | 0-100 |
| Re-import strategy | New artists auto-scored + flagged, existing scores preserved, disappeared artists kept |
| Event interaction | Display-only for v1 (score, matched artists, ticket link) |

## References

- [Spotify Web API](https://developer.spotify.com/documentation/web-api)
- [Spotify PKCE Flow](https://developer.spotify.com/documentation/web-api/tutorials/code-pkce-flow)
- [Spotify Feb 2026 Migration Guide](https://developer.spotify.com/documentation/web-api/tutorials/february-2026-migration-guide)
- [Bandsintown API](https://help.artists.bandsintown.com/en/articles/9186477-api-documentation)
- [Skiddle API](https://github.com/Skiddle/web-api/wiki/Events-API)
- [RA GraphQL scraper (djb-gt)](https://github.com/djb-gt/resident-advisor-events-scraper)
- [RA Lineup Preview (Larry Hudson)](https://larryhudson.io/ra-lineup-preview/)
- [RapidFuzz](https://github.com/rapidfuzz/RapidFuzz)
- [FastAPI docs](https://fastapi.tiangolo.com/)
- [SQLModel docs](https://sqlmodel.tiangolo.com/)
- [HTMX docs](https://htmx.org/docs/)
- [Similar project: Finding Live Music I Like (Shawn Cruz)](https://shawncruz.com/posts/finding-live-music-i-like/)
