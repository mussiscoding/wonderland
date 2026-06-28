# Project Structure

```
app/
  main.py           - FastAPI app, lifespan (init_db + run_migration)
  config.py         - Pydantic BaseSettings, all env vars
  database.py       - SQLite engine, init_db, get_session
  models.py         - SQLModel table definitions (User, Artist, UserArtist, ArtistGenre, GenreClassification, UserGenreClassification, UserEvent, Event, EventSource, Match, AccessRequest)
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
    events.py       - /events list (view + date/city/search filters), /event/{id} detail, /event/{id}/save and /unsave
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
docs/               - Plans, specs, decisions, project structure
```
