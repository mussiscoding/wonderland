---
date: 2026-03-30
topic: multi-user-spotify-auth
---

# Multi-User Spotify Auth & Per-User Scoring

## What We're Building

Transform the app from single-user to multi-user. Any user can link their Spotify account via a button, import their own artists, and see events scored against their personal artist affinities. Uses proper session-based auth so multiple users can be logged in simultaneously in different browser tabs.

## Why This Approach

A simpler "active profile switcher" (one user at a time) requires the same database changes but paints us into a corner. Session-based auth is barely more work and is the correct foundation whether this stays local or becomes a deployed web app.

## Key Decisions

- **Sessions over global state**: Use `starlette.middleware.sessions` with cookie-based sessions rather than a global "active user" variable. Every route resolves the current user from the session.
- **Shared artist catalog, per-user scores**: The `Artist` table becomes a shared catalog (spotify_id, name, genres). A new `UserArtist` junction table holds per-user data (auto_score, manual_score, excluded, source_signals).
- **Genre classification stays shared**: "house = dance" is objective enough to share. May extend to per-user in future.
- **Events, EventSource, Match stay shared**: Matches represent "this artist name appeared in this lineup" — objective fact. Event scoring is computed at display time from the current user's `UserArtist` data, not stored.
- **Genre backfill only for new artists**: When a second user imports and shares artists already in the catalog, those artists already have genres. Only genuinely new artists need MusicBrainz/Last.fm lookups.
- **Spotify tokens stored per-user in DB**: Replace the global `data/.spotify_cache` file with token fields on the `User` model.
- **Users only see their own artists**: The artist list/scores are scoped to artists where the current user has a `UserArtist` record.

## Data Model Changes

### New Tables

- **User**: id, spotify_id, display_name, spotify token data (access_token, refresh_token, token_expiry)
- **UserArtist**: user_id (FK), artist_id (FK), auto_score, manual_score, excluded, source_signals, created_at, updated_at

### Modified Tables

- **Artist**: Remove auto_score, manual_score, excluded, source_signals. Keep id, spotify_id, name, genres, created_at, updated_at.

### Unchanged Tables

- Event, EventSource, Match, GenreClassification

## Impact Summary

| Area | Change |
|------|--------|
| Auth | Session middleware, per-user Spotify tokens, login/callback creates User |
| Spotify import | Writes UserArtist instead of Artist scores; shared Artist catalog |
| Genre backfill | Only for artists not already in catalog |
| Scoring | Reads from UserArtist for current session user |
| Event list | Computes event scores against current user's UserArtist data |
| Artist list | Scoped to current user's UserArtist records |
| UI | Show who's logged in, "switch account" button |

## Open Questions

- Token storage: encrypt tokens at rest in SQLite, or acceptable as plaintext for a local/personal app?
- Should there be a way to delete a user and their data?
- How to handle the existing single-user data migration (current Artist scores → first User's UserArtist records)?

## Next Steps

-> `/workflows:plan` for implementation details
