---
date: 2026-03-27
idea: Discovery tab for artists/nights you'd probably enjoy based on lineup co-occurrence
type: extension
extends: event matching & scoring
status: idea
---

# Similar Vibes Discovery Tab

With dance music you don't really care about the specific artist name — it's about the type, the style, the vibes. If an unknown DJ has historically played on the same lineups as artists you love, there's a strong chance you'd enjoy their night too. This is probably a better similarity signal than Spotify's "related artists" for this domain.

The idea is a second tab that mirrors the main "events for artists you know" view, but for events we *think* you'll like — based on lineup co-occurrence, genre overlap, and label connections. Same UI, same scoring, just clearly marked as discovery rather than known-artist matches.

## Rough shape

- **Persistent event store** — every time we scrape events (for the main matching pipeline), we also persist them. Past events don't get thrown away after matching; they accumulate into a historical dataset. This means the co-occurrence graph gets richer automatically over time without needing to re-scrape history.
- Build a co-occurrence graph from that stored lineup data: "artist A and artist B have appeared on the same lineup N times"
- Artists who frequently co-occur with your highly-scored artists get a derived similarity score
- Surface events featuring these similar artists in a parallel discovery tab
- Same event card format as the main tab, but flagged as "you might like this because X played with Y at Z"
- Could layer in other signals too — same label, same genre tags, same venue programming patterns
- The longer you run the app, the better discovery gets — it's learning from the London scene over time

## Open questions

- How many co-occurrences before we consider two artists "similar"? (threshold tuning)
- Should this be purely co-occurrence or blend with Spotify related artists / Last.fm?
- How do we explain *why* we're recommending something? ("because they've played with Floating Points 4 times" vs just a score)
- Does this need its own curation step or is it fully automatic?
- The persistent event store is probably useful to the core pipeline too (dedup, not re-fetching known events) — worth considering as a core feature rather than just a discovery prerequisite
- Could we seed the store with a one-time historical scrape to bootstrap the graph, or just let it build up organically?
