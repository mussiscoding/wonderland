---
title: Widen DICE & Skiddle scraper source filters
type: feat
status: active
date: 2026-05-28
---

# Widen DICE & Skiddle scraper source filters

Both scrapers currently discard non-dance events *at the source API*, before scoring or
artist-matching ever sees them. This caps the whole app at dance/club events. Widening the
two filters lets live music (jazz/rock/pop/folk/indie…) flow through to the existing
fuzzy-matching + scoring pipeline, which already filters events down to a user's library.

Full findings and the resolved approach: `docs/ideas/2026-05-28-de-dance-ify-source-filters.md`.

## Background (verified against live APIs, London, next 60 days — 2026-05-28)

- **DICE** `filter[type_tags]=music:dj` (`app/scrapers/dice.py:49`) keeps only DJ/club.
  On one unfiltered 200-event page: `music:gig` 79 (live music — the big miss),
  `music:dj` 40, `music:party` 32, plus ~49 non-music (`culture:comedy`, `culture:sport`, etc.).
  - DICE `type_tags` filtering is **exact, single-value only**: bare `music`, `music:*`
    wildcard, and comma list `music:dj,music:gig` all return **0**. So we cannot widen the
    filter to a list — we must drop it.
- **Skiddle** `eventcode=CLUB` (`app/scrapers/skiddle.py:49`) keeps only club nights (612).
  `LIVE`=191, `FEST`=11. Comma-separated `eventcode` is an OR union (confirmed):
  `LIVE,CLUB,FEST`=814 (clean all-music set). Dropping it entirely = 4032 (5x, mostly
  noise: comedy/theatre/sport/arts/bar-pub/kids).

## Why no client-side filtering is needed

The default events view (`app/routes/events.py:95-96`) already hides events with score 0.
Non-music events have no lineup that matches an imported Spotify artist, so they score 0 and
never surface. Artist matching *is* the filter.

## Proposed Solution

Minimal, two-file change. Values become named module constants (this app's existing
"configurable" idiom, cf. `PAGE_SIZE`) rather than env vars — they rarely change and
env-var sprawl would be over-engineering for a personal tool.

### `app/scrapers/skiddle.py`

Change the hardcoded `eventcode` from `"CLUB"` to a module constant defaulting to the
three-code music union.

```python
# near top, with PAGE_SIZE
EVENT_CODES = "LIVE,CLUB,FEST"  # live music + club nights + festivals; OR union
```

```python
# in params dict (currently line 49)
"eventcode": EVENT_CODES,
```

### `app/scrapers/dice.py`

Drop `filter[type_tags]` from the request params entirely (currently line 49). No
replacement filter, no client-side type filtering — matching handles it downstream.

```python
params = {
    "page[size]": PAGE_SIZE,
    "page[number]": page,
    "filter[cities]": dice_city,
    # type_tags filter removed — DICE only supports exact single-value matching,
    # so we pull all event types and let artist matching filter downstream.
}
```

Update the docstring on `fetch_events` (`app/scrapers/dice.py:23`): it says "Fetch DJ/club
events" — change to reflect that it now fetches all events for the city.

## Acceptance Criteria

- [ ] Skiddle requests use `eventcode=LIVE,CLUB,FEST` via a module constant.
- [ ] DICE requests send no `filter[type_tags]` param.
- [ ] DICE `fetch_events` docstring no longer claims DJ/club-only.
- [ ] A live smoke fetch for one city returns live-music events (e.g. a `music:gig` /
      Skiddle `LIVE` event) that previously would have been excluded.
- [ ] The default `/events` view is unchanged in shape — still only shows score>0 events.

## Caveats (accepted — fine for a personal tool)

- `/events?show_all=1` drops the score filter and will now show non-music too. Out of scope;
  fix there later if it ever annoys.
- Every fetched event is stored (`app/events.py` `fetch_all_events`), so we persist ~25%
  (DICE) / more (Skiddle) non-music rows that never surface, and matching iterates over more
  rows. Cheap at this scale.
- Slightly longer fetch runs (more pages, `RateLimiter` min_delay=1.0s/request). Acceptable.

## Verification

1. Activate `.venv`.
2. Syntax/import check both scrapers.
3. Run an ad-hoc fetch (or the admin fetch flow) for London and confirm live-music events
   appear and the run completes without errors. (Requires `DICE_API_KEY` / `SKIDDLE_API_KEY`,
   both present locally — do not commit them.)
4. Confirm `/events` default view still filters to matched events.

## Documentation & follow-ups

- **`docs/decisions.md`** — propose an entry (await user confirmation per working-with-me.md):
  *"Source scrapers pull broad event sets and rely on downstream artist-matching/scoring to
  filter, rather than narrowing at each provider's API. DICE has no multi-value type filter,
  so we drop it; Skiddle uses the `LIVE,CLUB,FEST` union."*
- **`docs/front-end-spec.md`** — no change expected (no route/template change).
- **`docs/project-structure.md`** — no change (no files added/moved/removed).
- On completion, move `docs/ideas/2026-05-28-de-dance-ify-source-filters.md` →
  `docs/ideas/done/`.
- Related: Ents24 work in `docs/brainstorms/2026-05-28-broaden-event-sources-brainstorm.md`
  (separate follow-on). RA is dance-only by nature — out of scope.

## References

- Idea: `docs/ideas/2026-05-28-de-dance-ify-source-filters.md`
- `app/scrapers/dice.py:45-50`, `app/scrapers/skiddle.py:44-56`
- `app/routes/events.py:95-96` (score>0 default filter)
- Skiddle eventcodes: https://github.com/Skiddle/web-api/wiki/Events-API
