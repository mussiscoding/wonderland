---
date: 2026-03-30
idea: Weight playlist scoring by unique songs, not just playlist count — one song in 5 playlists shouldn't score as high as 5 different songs
type: extension
extends: artist auto-scoring
status: complete
---

# Playlist Depth Scoring

Right now `playlist_appearances` just counts how many playlists an artist shows up in. But if it's the same one banger across 5 playlists, that's not the same as having a whole album spread across your library. The signal should reflect *depth* of listening — how many unique tracks you have, across how many playlists.

## Rough shape
- Store two separate signals in source_signals:
  - `playlist_appearances` — count of unique playlists (already have this)
  - `unique_songs` — count of unique track IDs across all playlists (new, easy to collect)
- Score using both: e.g. separate point allocations for each, or a combined formula
- Keeps them transparent in the UI — "3 playlists (+X)  5 unique songs (+Y)" tells you more than either alone
- 1 song in 5 playlists = high playlist count, low song count → casual listener
- 10 songs in 2 playlists = low playlist count, high song count → deep fan

## Open questions
- ~~Does the current import already have access to track IDs per artist per playlist, or would we need to change what we collect?~~ **Yes** — `_process_playlist` already iterates every track and has access to `track["id"]`, we just don't capture it. No extra API calls needed, just collect the track ID alongside the artist ID in the existing loop.
- How to weight this vs the other signals? The current cap is 42 points for playlists (7 playlists × 6 pts). New formula would need similar bounding.
- ~~Should saved tracks also factor in here, or keep those as a separate signal?~~ **Keep both.** Saved tracks (Liked Songs) will show up as a playlist too, so there's some double-counting — that's fine. Saved tracks stays as its own signal; the playlist signals just naturally include it. A heavily-liked artist *should* score higher.
