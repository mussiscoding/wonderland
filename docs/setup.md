# Setup

## Running locally

```bash
source .venv/bin/activate          # Always activate venv first
cp .env.example .env               # Fill in API keys
python -m uvicorn app.main:app --reload
```

SQLite DB lives at `data/wonderland.db`. Created automatically on first run.

## Environment variables

See `.env.example`. Key ones:
- `SPOTIFY_CLIENT_ID`, `SPOTIFY_CLIENT_SECRET`, `SPOTIFY_REDIRECT_URI` — Spotify OAuth
- `SKIDDLE_API_KEY`, `DICE_API_KEY` — Event scraper API keys
- `LAST_FM_API_KEY` — Last.fm genre backfill
- `SESSION_SECRET`, `FERNET_KEY` — Session signing and token encryption
- `ADMIN_SPOTIFY_IDS` — Comma-separated admin Spotify user IDs
- `EVENTBRITE_TOKEN`, `TICKETMASTER_API_KEY` — Additional scraper auth
