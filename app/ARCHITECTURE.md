# Architecture

## Data Flow Pipeline

```
Spotify OAuth Login
       |
       v
Import Artists ──> Artist + ArtistGenre + UserArtist tables
       |
       v
Choose Genre Profile ──> UserGenreClassification (seeded from template)
       |
       v
Score Artists ──> UserArtist.auto_score (signals * genre multiplier)
       |
       v
Fetch Events ──> Event + EventSource tables (from 5 scrapers)
       |
       v
Match Artists ──> Match table (fuzzy match artists against lineups)
       |
       v
Score Events ──> sum of matched artist scores * confidence
       |
       v
Display ──> /events page sorted by relevance to user
```

## Key Modules

### Authentication (`auth.py`)
- Spotify OAuth via spotipy with PKCE flow
- Token info encrypted with Fernet before storage in User.encrypted_token_info
- `get_spotify_client()` handles token refresh transparently
- Session cookie stores `user_id` (int)

### Spotify Import (`spotify.py`)
- Runs in a background daemon thread (see `routes/artists.py`)
- Collects signals: followed artists, saved tracks, playlist appearances, top artists, recent plays
- Each signal contributes points to `UserArtist.source_signals` dict
- Also fetches genres per artist into `ArtistGenre` junction table
- Progress tracked via in-memory dict, polled by HTMX every 1s
- Last.fm backfill available for artists missing Spotify genre data

### Scoring (`scoring.py`)

**Signal scoring** — each engagement signal earns points (capped):
| Signal | Points | Cap |
|--------|--------|-----|
| Followed | 30 | — |
| Saved tracks | 7 per | 35 |
| Intentional plays | 5 per | 35 |
| Playlist appearances | 4 per | 28 |
| Unique songs | 2 per | 28 |
| Top artist (short) | 20 | 35 combined |
| Top artist (medium) | 10 | |
| Top artist (long) | 5 | |

**Genre multiplier** — applied to signal total:
| Category | Multiplier |
|----------|-----------|
| high | 1.0 |
| medium | 0.5 |
| low | 0.1 |
| unclassified | 0.3 |

Final score = `min(genre_multiplier * signal_score, 100)`

`effective_score` = `manual_score` if set, otherwise `auto_score`. Excluded artists get 0.

### Genre System

Two-tier classification:
1. **GenreClassification** — global templates (dance, jazz, rock, pop, country profiles). Admin-editable. Rows keyed by `(profile_name, genre_name)`.
2. **UserGenreClassification** — per-user copy. Seeded from a template on first import, then user can customise. Keyed by `(user_id, genre_name)`.

Users choose a genre profile during onboarding (`/choose-profile`). "none" seeds everything as unclassified.

### Event Fetching (`events.py`)
- Orchestrated by `fetch_all_events(city)` — calls each scraper, deduplicates, stores
- Dedup key: normalised `venue_name + city + date` (`_dedupe_key()`)
- Each event can have multiple `EventSource` records (one per scraper that found it)
- Runs in background thread triggered from admin page

### Matching (`matching.py`)
- `match_events_to_artists(session)` — for each event, parses lineup text and fuzzy-matches against all artists in DB
- Uses rapidfuzz `fuzz.ratio` with threshold 85
- Creates `Match` records linking `event_id` to `artist_id` with confidence score
- Lineup parsing: splits on commas, `&`, `b2b`, `vs`, newlines; strips common suffixes like "(live)", "(DJ set)"

### Migration (`migration.py`)
- Runs on every startup in `main.py` lifespan
- Each migration function is idempotent — checks if migration is needed before running
- Pattern: try to SELECT the old/new column → if it exists/doesn't, migrate
- SQLite constraint changes use table rebuild pattern (can't ALTER constraints in SQLite)
- Also seeds genre profile templates (jazz, rock, pop, country) if not present

## Database Schema (key tables)

- **User** — spotify_id, display_name, encrypted_token_info
- **Artist** — spotify_id, name (genres moved to ArtistGenre junction)
- **ArtistGenre** — artist_id, genre_name (many-to-many)
- **UserArtist** — user_id, artist_id, auto_score, manual_score, excluded, source_signals (JSON)
- **GenreClassification** — profile_name, name, category (global templates)
- **UserGenreClassification** — user_id, genre_name, category, user_modified
- **Event** — title, venue_name, venue_location, date, dedupe_key
- **EventSource** — event_id, source, url, price, raw_title
- **Match** — event_id, artist_id, confidence, matched_name

## Multi-City Support

`cities.py` defines `CITY_CONFIG` with per-city scraper parameters (area codes, lat/lon, DMA IDs, geohashes). Currently configured: London, Berlin.
