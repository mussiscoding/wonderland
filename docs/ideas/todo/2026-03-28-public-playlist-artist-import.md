---
date: 2026-03-28
idea: Import artists from public playlists we don't own
type: extension
extends: spotify import
status: idea
---

# Public Playlist Artist Import

The Spotify dev mode API blocks reading tracks from playlists you don't own (403), which means we're missing a huge signal source. Most of the big dance/electronic playlists are curated by labels, promoters, or Spotify editorial — exactly the ones that would tell us who's playing live soon. Without those artists in our system, we can't match them to events.

## Rough shape
- Some way to feed in playlist URLs/IDs for public playlists we care about
- Fetch the artist list from those playlists without needing user-auth API access
- Could be: client credentials API flow, scraping the web player, or a browser extension that dumps the data
- Artists from these playlists get the `playlist_appearances` signal like normal
- Maybe a UI to manage "watched playlists" — paste a Spotify URL, we pull the artists

## Open questions
- Does client credentials flow (app-level auth, no user) allow reading public playlist tracks? If so this is trivial
- If not, can we get the data from the web player HTML/JS, or does it need a headless browser?
- Should these playlists be treated differently from the user's own playlists in scoring?
- Do we want a one-time import or periodic re-sync of watched playlists?
