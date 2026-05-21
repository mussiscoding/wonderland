# Dance Time

A web app that helps music fans discover upcoming events featuring artists they already listen to. Connects to Spotify to import a user's music library, scrapes event listings from multiple sources, and fuzzy-matches artists against lineups to surface relevant gigs.

## Tech Stack

- **Backend**: Python 3.12, FastAPI, SQLModel (SQLite), Jinja2 templates
- **Frontend**: Server-rendered HTML + HTMX for partial updates, minimal CSS
- **Auth**: Spotify OAuth (via spotipy) with PKCE, Fernet-encrypted token storage, session cookies
- **Scraping**: 5 event sources (RA, Dice, Skiddle, Eventbrite, Ticketmaster)
- **Matching**: rapidfuzz for fuzzy artist-to-lineup matching (threshold 85)
- **Deployment**: Hetzner VPS, systemd service, uvicorn

## Running Locally

```bash
source .venv/bin/activate          # Always activate venv first
cp .env.example .env               # Fill in API keys
python -m uvicorn app.main:app --reload
```

SQLite DB lives at `data/wonderland.db`. Created automatically on first run.

## Project Structure

```
app/
  main.py           - FastAPI app, lifespan (init_db + run_migration)
  config.py         - Pydantic BaseSettings, all env vars
  database.py       - SQLite engine, init_db, get_session
  models.py         - SQLModel table definitions
  auth.py           - Spotify OAuth, token encryption, session helpers
  migration.py      - Startup migrations (detect-and-fix), genre profile seeds
  scoring.py        - Auto-scoring (signal weights + genre multipliers), rescoring
  matching.py       - Fuzzy artist matching against event lineups
  events.py         - Event fetch orchestration, dedup by venue+date+city
  spotify.py        - Spotify import (artists, genres, signals), Last.fm backfill
  cities.py         - Multi-city config (London, Berlin) with per-scraper params
  templating.py     - Jinja2 template setup

  routes/
    auth.py         - /login, /callback, /logout, /choose-profile
    artists.py      - /artists, /artist/{id}, /import, progress endpoints
    genres.py       - /genres, /genre/{name}, classify, bulk-classify, reset
    events.py       - /events with date/city/search filters
    admin.py        - /admin, background event fetch + matching trigger

  scrapers/         - See app/scrapers/README.md
    base.py         - Shared utilities (RateLimiter, date parsing, price formatting)
    ra.py           - Resident Advisor (GraphQL)
    dice.py         - Dice (REST API)
    skiddle.py      - Skiddle (REST API)
    eventbrite.py   - Eventbrite (REST API + HTML scraping for venue discovery)
    ticketmaster.py - Ticketmaster Discovery API

  templates/        - Jinja2 HTML templates (base.html + page templates)

data/               - SQLite DB, scraper caches (gitignored)
docs/               - Planning docs, front-end spec
```

## Key Conventions

- **Always activate `.venv`** before running any Python commands
- **Migrations run on startup** in `migration.py` — detect old schema, fix in-place. No migration framework.
- **SQLite table rebuild** pattern for altering constraints (CREATE new → INSERT SELECT → DROP old → RENAME)
- **Multi-user**: All artist scores are per-user via `UserArtist` junction table. Genre classifications are also per-user via `UserGenreClassification`.
- **Genre profiles**: Template classifications (dance, jazz, rock, pop, country) seeded into `GenreClassification`. Users get a copy in `UserGenreClassification` on first import.
- **Background threads**: Spotify import and event fetch run in daemon threads with polling progress bars (HTMX 1s poll).
- **Admin gating**: Admin routes check `ADMIN_SPOTIFY_IDS` env var (comma-separated Spotify IDs).
- **Update `docs/front-end-spec.md`** whenever front-end behaviour changes.

## Environment Variables

See `.env.example`. Key ones:
- `SPOTIFY_CLIENT_ID`, `SPOTIFY_CLIENT_SECRET`, `SPOTIFY_REDIRECT_URI` — Spotify OAuth
- `SKIDDLE_API_KEY`, `DICE_API_KEY` — Event scraper API keys
- `LAST_FM_API_KEY` — Last.fm genre backfill
- `SESSION_SECRET`, `FERNET_KEY` — Session signing and token encryption
- `ADMIN_SPOTIFY_IDS` — Comma-separated admin Spotify user IDs
- `EVENTBRITE_TOKEN`, `TICKETMASTER_API_KEY` — Additional scraper auth
