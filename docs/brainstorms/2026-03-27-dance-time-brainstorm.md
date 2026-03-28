---
date: 2026-03-27
topic: wonderland-gig-finder
---

# wonderland: Gig Finder for London Dance Music

## What We're Building

A personal tool that extracts your full artist library from Spotify, helps you identify which of those artists you'd actually want to see live, and then finds London events featuring them.

**The core problem:** You listen to a wide range of music — not necessarily all dance music. Buried in your library are artists you'd love to go see in a warehouse or club, but finding them requires manually cross-referencing RA/Dice/Google with your Spotify, and you don't even know all the artist names because you listen via playlists. The challenge isn't just "find gigs" — it's "figure out which of my hundreds of artists are the ones I'd actually go dance to, then find their gigs."

## The Pipeline

### Step 1: Import
Pull your full artist library from Spotify — top artists (short/medium/long term), followed artists, saved tracks, playlist contents, recently played. The goal is to surface every artist you've listened to, even ones you couldn't name.

### Step 2: Score & Filter
Auto-score and filter artists using available signals:
- **Genre filtering** is key — Spotify provides genre tags per artist. Auto-boost electronic/dance genres, auto-demote others. This does heavy lifting so you don't have to manually curate hundreds of entries.
- **Listening signals** as secondary input, roughly ordered by strength:
  - **Followed artists** — explicit follow is a strong deliberate signal
  - **Saved/hearted tracks** — number of saved songs per artist (you don't heart passively)
  - **Intentional listening** — artist/album context in recently-played means the user actively sought them out (vs. playlist context which is passive). Limited to rolling window of 50 tracks, but can be accumulated over time by polling daily.
  - **Playlist appearances** — how many of your playlists they show up in (weaker, more passive)
  - **Play frequency** — from top artists endpoint (useful but noisy — high play count may just mean good background music, not "want to see live")
- Smart defaults so the list is useful before any manual input.

### Step 3: Curate
Present the scored/filtered list. You can adjust scores to reflect **"want to see live"** — which is a fundamentally different signal from "listen to a lot." A mellow ambient artist you play daily might score low; a DJ you rarely stream but love on a soundsystem scores high. Manual overrides on top of auto-scoring.

### Step 4: Fetch Events
Pull upcoming London events from multiple sources and normalise into a common format.

**What we need per event:** name/title, date, venue, lineup (list of artist names), ticket link, source (RA/Dice/etc.), and any other metadata available (price, description).

**Source-specific challenges:**
- **RA / Dice** — no official APIs. Scrape via undocumented GraphQL (RA) or HTML scraping. Open-source scrapers exist for both. Fragile — endpoints can change without notice. These are the most valuable sources for London dance/electronic.
- **Ticketmaster / Bandsintown / Skiddle** — legitimate APIs with free tiers. Two query models: location-first (Ticketmaster, Skiddle — "events in London") and artist-first (Bandsintown — "events for this artist"). Both are useful.
- **Deduplication** — the same event will appear on multiple sources. Need to deduplicate by venue + date + fuzzy title match, and merge lineup data (one source may have a more complete lineup than another).

**Caching:** Events don't change minute-to-minute. Cache aggressively to stay within rate limits and avoid hammering scraped sources. Refresh frequency TBD (daily? weekly?) — see Open Questions.

### Step 5: Match
Find which fetched events feature your curated artists.

**Lineup parsing:** Electronic events rarely have one artist. Listings typically come as either structured lineup data (if we're lucky) or a single string like "Floating Points b2b Four Tet, Sherelle, Jossy Mitsu". We need to:
- Split lineup strings into individual artist names (handle commas, "b2b", "&", "presents:", etc.)
- Handle b2b sets — if either artist matches, the event matches
- Match against any artist in a multi-DJ lineup — with DJ events this is the norm, not the exception

**Name matching (err on the side of loose):** False positives are a minor annoyance; missed events are actually painful. Start loose, tighten if consistently noisy.
- **Normalise** — lowercase, strip common suffixes ("DJ", "Live", "& Friends"), remove punctuation
- **Fuzzy matching** — Levenshtein / token-sort-ratio with a relatively low threshold to favour recall over precision
- **MusicBrainz aliases** as fallback — look up alternative names, stage names, real names
- **Log unmatched artists** — so we can spot patterns and improve matching over time

**b2b signal for discovery:** If an unknown artist is b2b with someone you scored highly, that's a strong similarity signal — arguably stronger than Spotify's related artists. Feed this into Step 7.

### Step 6: Score Events
Rank matched events by:
- **Artist "want to see live" score** — primary signal
- **Multiple artist matches** — a lineup with 3 of your artists beats one with 1
- Other factors (venue, date, price) deferred to later versions

### Step 7: Similar Artist Discovery (Stretch Goal)
Look at other artists on matched event lineups. If they're similar to your highly-scored artists (via Spotify related artists, genre overlap), recommend the event even if you don't recognise anyone on the bill. This is how you discover new nights out.

## Data Sources

### Spotify API (Primary — artist extraction)
- Free, OAuth 2.0 auth flow
- Endpoints: `/me/top/artists`, `/me/following`, `/me/tracks`, `/playlists/{id}/tracks`, `/me/player/recently-played`
- Also provides: genre tags, related artists (for step 7)

### Event Sources

| Source | Type | UK Dance Coverage | Notes |
|--------|------|-------------------|-------|
| **Resident Advisor** | Scraping (no API) | Excellent | The definitive source for London electronic. Undocumented GraphQL API, fragile but doable. Open-source scrapers exist. |
| **Dice.fm** | Scraping (no API) | Excellent | Strong London indie/electronic coverage. Apify scraper available. |
| **Ticketmaster** | Free API (5K/day) | Good but skews mainstream | Better for larger venues. Supplementary. |
| **Bandsintown** | Free API (app_id) | Good | Artist-centric query model fits well. |
| **Skiddle** | Free API | Good (UK-focused) | Good for UK club nights. |
| **Songkick** | Not accepting new keys | — | Monitor for reopening. |

**Strategy:** RA + Dice are the most valuable for London dance music but require scraping. Ticketmaster + Bandsintown + Skiddle provide a legitimate API foundation. Start with whichever is easiest to get working, layer on more sources over time.

## Delivery

- **Web app** during development — gives best visibility into what's being found and matched
- **Email digest** as a future bolt-on (cron job + email service)
- **Push notifications** possible later but more effort
- Running locally / simple server — personal tool, no multi-user auth needed

## Key Decisions
- **"Want to see live" vs "listen to most"**: These are different signals. Auto-scoring by genre gets us most of the way; manual curation fine-tunes.
- **Personal tool**: Spotify auth can be simple (single user), no need for polished onboarding.
- **Scraping RA/Dice**: Accept the fragility for v1 — they're too valuable for London dance music to skip, but don't depend solely on them.
- **Venue filtering deferred**: Nice to have but not v1.

## Extensions (Post-V1)

### Venue Filtering
Filter or boost/demote events by venue. Warehouse in Enfield > O2 Arena. Close > Far. Deferred from v1 but the event data model should capture venue info from the start.

### Similar Artists Discovery Tab
During the curate step (Step 3), add a second tab alongside your Spotify-sourced artists: **"Similar Artists"**. This surfaces artists you *don't* listen to but might want to see, sourced from:
- **Spotify related artists** — algorithmic similarity
- **Last.fm similar artists** — scrobble-based similarity, often better for niche/electronic
- **Discogs label overlap** — artists on the same labels as your highly-scored artists (strong signal in electronic music where labels define sound)
- **Lineup co-occurrence** — artists who repeatedly appear on the same events as your scored artists (built from our own scraped data over time)

Each similar artist gets a score based on how it was found and which of your artists it's linked to. The tab has toggles to:
- Enable/disable the entire similar artists concept
- Enable/disable individual similar artists
- Enable/disable individual similarity sources (e.g. use Last.fm but not Spotify)

Enabled similar artists feed into the match and event scoring steps just like your curated artists, but could be visually distinguished in results so you know "this event matched because of a similar artist, not one you picked directly."

### Email / Push Notifications
Bolt-on delivery methods once the core pipeline is solid.

## Open Questions
- Best tech stack? (depends on your preferences — to be decided in planning)
- How often to refresh event data? (daily? weekly?)
- How to persist the curated artist scores? (DB? simple JSON file to start?)
- RA scraping: roll our own or use existing open-source scrapers?

## Next Steps
→ `/workflows:plan` for implementation details
