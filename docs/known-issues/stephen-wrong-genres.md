---
date: 2026-03-28
issue: MusicBrainz genre backfill matches "Stephen" to Stephen King instead of the electronic artist
status: open
affects: musicbrainz genre backfill
---

# Stephen gets Stephen King's genres

The artist "Stephen" (Spotify ID `64N1HzkQEXvjlJBQinWeu2`) is an American electronic music singer-songwriter, but the MusicBrainz name search matches Stephen King (the author) because he's far more popular. This gives Stephen genres like "audio drama", "audiobook", "author" instead of electronic music tags.

## What we tried
- **Spotify ID → MusicBrainz URL lookup**: MusicBrainz does have the correct Stephen linked via his Spotify URL (`/ws/2/url/?query=url:"https://open.spotify.com/artist/64N1HzkQEXvjlJBQinWeu2"`), and it returns the right artist with disambiguation "American electronic music singer-songwriter". We added this as a first-pass lookup before the name fallback, but it's still hitting Stephen King — likely the Spotify ID lookup is succeeding but the genres from that MBID are empty, so the name fallback runs and gets King.
- **Filtering by music tags**: Tried requesting multiple candidates and picking the first with music tags, but reverted.

## Likely fix
Debug why the Spotify ID lookup path isn't preventing the name fallback from running. The MBID `4b8b04c6-9bac-4122-bf01-5e3bb174d2ec` might just not have tags in MusicBrainz, so even the correct match returns no genres.
