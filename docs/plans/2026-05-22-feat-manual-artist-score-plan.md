# Manual Artist Score

**Date:** 2026-05-22
**Status:** Ready to build

## Summary

Add UI controls on the artist detail page to manually set an artist's score, clear a manual override, or exclude an artist entirely. The backend already supports all of this — `UserArtist` has `manual_score`, `excluded`, and an `effective_score` property that returns `manual_score` when set, otherwise `auto_score`. We just need a POST endpoint and a form.

## Changes

### 1. New POST endpoint — `app/routes/artists.py`

`POST /artist/{artist_id}/score`

- Accepts form fields: `manual_score` (number or empty string), `excluded` (checkbox)
- Validates score is 0–100 or empty (to clear)
- Updates `UserArtist.manual_score` and `UserArtist.excluded`
- Redirects back to `/artist/{artist_id}`
- Auth-gated: requires logged-in user, only modifies their own `UserArtist`

### 2. Artist detail template — `app/templates/artist_detail.html`

Below the existing score/signals table, add a small form:

- **Manual score input**: number input (0–100). Placeholder shows current auto_score so user knows what they're overriding.
- **Set button**: submits the manual score
- **Clear button**: removes manual override, reverts to auto_score. Only visible when a manual_score is currently set.
- **Exclude checkbox**: toggles `excluded` flag (zeros out effective score). Persists independently of manual score.
- **Visual indicator**: when manual_score is set, show a "manual" label next to the score in the table so it's clear the score is overridden. When excluded, show "excluded" label.

### 3. Update front-end spec — `docs/front-end-spec.md`

Add manual score controls to the Artist Detail section.

## What we're NOT doing

- No bulk manual scoring from the artist list page
- No manual score column on the artist list (effective_score already handles it transparently)
- No manual artist entry (separate idea in `docs/ideas/todo/2026-03-28-manual-artist-entry.md`)

## Existing infrastructure

All backend plumbing is already in place:

- `UserArtist.manual_score` — nullable float, already in model and DB
- `UserArtist.excluded` — bool, already in model and DB
- `UserArtist.effective_score` — property: returns `manual_score` if set, else `auto_score`; excluded artists effectively get 0 in event scoring
- Artist list and event pages already use `effective_score`, so manual overrides propagate automatically
