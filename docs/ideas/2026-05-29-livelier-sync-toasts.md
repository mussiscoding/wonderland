---
date: 2026-05-29
idea: Make the running sync toasts livelier — surface the step and/or a little animation, without going full progress bar
type: extension
extends: sync notification toasts
status: idea
---

# Livelier sync toasts

Right now the running toasts just say "Syncing your Spotify…" / "Fetching events…" — static. They feel a bit dead while a sync churns. We already track a text `step` (and a `current`/`total` count during the genre-backfill phase), so we could show *something* moving. Note to self: don't overcomplicate this — no progress bar, keep it light and fun.

## Rough shape
- Surface `progress.step` in the running toast, e.g. "Syncing your Spotify… — Fetching playlist artists…". The data already exists in `import_progress`/`event_progress`.
- Maybe append the count when we happen to have one (genre-backfill phase), e.g. "… (142/863)" — but only when it's there, don't force it.
- A bit of life on the "…" itself — animate the ellipsis (jumping/bouncing dots) so the toast visibly breathes even when the step text isn't changing. CSS-only.

## The real pain: genre backfill is brutally slow
The reason a sync drags is the MusicBrainz genre backfill: it does `time.sleep(1.1)` per artist (`app/spotify.py:310/323/348/351`) to respect MB's ~1 req/sec rate limit. So backfilling N artists takes ~1.1×N seconds — minutes for a few hundred. Livelier toasts paper over it, but the actual fix is making this not take forever. Worth thinking about separately:
- Batch/parallelise where MB allows, or cache genres globally so we never re-look-up an artist already known (it's a shared `Artist` catalog — one user's backfill should benefit everyone).
- Or lean harder on Last.fm (0.25s sleep) / Spotify genres first and only fall back to MB for the stragglers.
- Or make backfill fully background + incremental so the *import* feels done quickly and genres trickle in after.

## Open questions
- Does the step text update often enough to feel alive, or do we lean on the animated dots for the quieter phases?
- Just the animated dots (simplest), just the step text, or both?
- Keep it strictly CSS for the animation (no JS), to stay simple?
- Is the slow backfill better solved by a global genre cache (shared catalog) than by any toast change?
