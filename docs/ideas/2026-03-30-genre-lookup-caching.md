---
date: 2026-03-30
idea: Stop re-fetching genres for artists that have no data in source APIs
type: extension
extends: artist genre enrichment
status: idea
---

# Genre Lookup Caching

Right now if an artist has no genres, we keep hitting MusicBrainz (or whatever source) every time — even if we already know they don't have data there. We need a way to distinguish "we haven't looked yet" from "we looked and got nothing back." Bonus: let users manually fill in genres for artists the APIs can't help with.

## Rough shape
- Track genre lookup status per artist — something like "not yet looked up" vs "looked up, nothing found" vs "has genres"
- Skip API calls for artists already marked as "nothing found"
- Let users manually assign genres to artists missing them
- Some kind of staleness/refresh mechanism so we can re-check periodically (e.g. if MusicBrainz adds genre data later)

## Open questions
- How long before a "nothing found" result goes stale and we retry? Time-based? Manual trigger?
- Should user-assigned genres be treated differently from API-sourced ones? (e.g. flagged so they don't get overwritten on refresh)
- Is this just an Artist model field, or does it want its own lookup log table?
