---
date: 2026-03-29
idea: Show a top song preview clip for each artist to aid recognition
type: extension
extends: artist scoring
status: complete
---

# Artist Song Preview for Recognition

Half the reason we're building this is that playlist artists aren't always recognizable by name alone — you've heard the music but can't place "DJ Whatever." Playing a short clip of their most-played song would make manual scoring way faster because you'd instantly know "oh, THAT artist."

## Rough shape
- Pull each artist's top track (ideally the one we've listened to most, or failing that their Spotify top track)
- Display a play button next to each artist on the artists page
- Play a ~10-30 second preview clip inline — Spotify's API returns a `preview_url` (30s MP3) on track objects, so this might be free to use without a full player embed
- Could also show the track name so there's a text cue alongside the audio

## Open questions
- Are Spotify `preview_url`s still reliably available? They've been flaky/deprecated in some regions — need to check current API status
- Do we already store enough track data during import to know which song we've played most per artist, or would we need an extra API call?
- Would an embedded Spotify player widget be better than raw preview URLs (richer UX but heavier dependency)?
- Licensing/ToS implications of playing previews outside the Spotify app?
