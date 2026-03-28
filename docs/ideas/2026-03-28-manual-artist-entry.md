---
date: 2026-03-28
idea: Allow manually adding artists that aren't in Spotify library
type: extension
extends: artist import
status: idea
---

# Manual Artist Entry

Some artists you definitely want to see live aren't in your Spotify library — maybe you discovered them at a gig, through a friend, or they're just not on Spotify much. Aidan Doherty and Warmup are examples: melodic house artists you'd give a 100 score to, but they won't show up through any of the current Spotify import signals.

## Rough shape
- A way to manually add an artist by name (and optionally genre + score)
- Could be a simple form on the artists page: name, genre override, manual score
- These artists skip auto-scoring entirely — the user IS the signal
- They still get matched against event lineups like any other artist
- Could also allow setting genre directly (e.g. "melodic house") without needing MusicBrainz lookup

## Open questions
- Should manual artists have a spotify_id? Could search Spotify to link them, or just leave it null
- Should there be a bulk add (paste a list of names)?
- How to handle if the artist later shows up in a Spotify import — merge or keep separate?
