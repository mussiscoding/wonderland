---
date: 2026-05-28
idea: Make the hardcoded dance-only filters on DICE and Skiddle genre-aware so non-dance events can come through
type: extension
extends: event scrapers
status: done
---

# De-dance-ify the DICE & Skiddle source filters

Turns out two of our scrapers throw away everything non-dance *at the source*, before scoring or matching ever sees it. DICE sends `filter[type_tags]=music:dj` (`app/scrapers/dice.py:49`) and Skiddle sends `eventcode=CLUB` (`app/scrapers/skiddle.py:49`). So if we want the app to surface jazz/rock/pop/country gigs, adding Ents24 isn't enough — these two filters quietly cap us at dance. (RA is dance-only by nature; that's a separate problem.)

## Rough shape
- Make the DICE `type_tags` and Skiddle `eventcode` filters configurable rather than hardcoded.
- Probably drive them off the broader set of genre profiles, or just widen/drop them and let the existing fuzzy-matching + genre scoring do the filtering downstream.
- Check what DICE `type_tags` and Skiddle `eventcode` values map to other genres (does DICE have music tags beyond `music:dj`? does Skiddle have non-CLUB codes for live gigs?).

## Findings (probed live APIs, London, next 60 days — 2026-05-28)

**DICE** classifies events with a `type_tags` namespace. On one unfiltered 200-event page:
- `music:gig` 79 (live music — the big miss), `music:dj` 40 (what we keep), `music:party` 32
- non-music noise: `culture:comedy` 19, `culture:sport` 10, plus art/social/theatre/film/talks (~20)
- So `music:dj` discards ~2x as many live-music events as it keeps.
- **DICE does NOT accept comma-separated `type_tags`** — `music:dj,music:gig` returned 0. Can't widen the filter to a list.

**Skiddle** eventcodes (documented; comma-separated = OR union, confirmed):
- `CLUB` 612 (current), `LIVE` 191 (missing), `FEST` 11
- `LIVE,CLUB,FEST` = 814 (clean "all music" set, no comedy/theatre/sport)
- no eventcode = 4032 (5x volume but mostly noise: comedy, theatre, sport, arts, bar/pub, kids)

## Resolved approach — just widen the searches, let matching filter
- **Skiddle**: change `eventcode` from `CLUB` to `LIVE,CLUB,FEST` (configurable default). Clean +33%. (Could also drop it entirely, but that's 5x volume of mostly non-music, so the three-code union is the sweet spot.)
- **DICE**: drop `filter[type_tags]` entirely. No client-side filtering — the default events view already hides score-0 events (`app/routes/events.py:95-96`), and comedy/sport/theatre never match an imported artist, so they never surface.
- We are **not** routing genre profiles through the queries, **not** using DICE `genre_tags`, and **not** filtering by type our side — downstream fuzzy-matching + scoring is the filter.

### Caveats of dropping DICE's filter (both fine for a personal tool)
- The `?show_all=1` events view drops the score filter and would then show non-music too. Fix there if it ever annoys.
- Every fetched event is stored (`fetch_all_events`), so we persist ~25% non-music rows that never surface, and matching runs over more rows. Cheap at this scale.

## Open questions
- Volume/rate-limit impact of the wider pulls — measured page-1 above; full-run volume still to confirm but fine for a personal tool.
- RA is dance-only by nature; separate problem, out of scope here.
- Relates to the Ents24 work in `docs/brainstorms/2026-05-28-broaden-event-sources-brainstorm.md` (logged there as a follow-on).
