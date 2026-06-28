---
date: 2026-06-28
topic: saved-events
---

# Per-user saved events

## What we're building

A private "save this event" bookmark for logged-in users so they can shortlist gigs without having to book immediately, copy details elsewhere, or refind them on every visit. Surfaces as a star toggle on `/event/{id}`, a left-edge accent stripe on saved rows in `/events`, and a new `Saved` filter alongside the existing `My artists | All events` toggle. Past saved events drop out of view automatically once the date passes.

## Why this approach

Compared peer apps (Songkick, Bandsintown, RA, DICE, Eventbrite). Two-state interested/going patterns (Songkick, Bandsintown) only earn their complexity when there's a social audience for the signal. For a private discovery tool, the single-state RA/DICE/Eventbrite "Saved Events" model is the right ceiling. Existing codebase pattern (`UserArtist`, `UserGenreClassification`) makes a `UserEvent` join table a drop-in.

The save action deliberately *does not* appear inline on `/events` rows: the list is already horizontally cramped on mobile, and forcing the round-trip to the detail page is "annoying but not that annoying" given how rare saving is relative to browsing.

## Key decisions

- **One-state model, extensible schema** — single saved/unsaved bookmark, but `UserEvent` ships with a nullable `status` column so `booked` / `dismissed` can be added later without a migration dance. Rationale: solves the stated pain with the smallest surface; defers state-machine UX cost until we know we want it.
- **Save action lives only on the event detail page** — preserves the existing `/events` table's horizontal budget. Rationale: list is already tight on mobile; horizontal scroll or wrapped icons hurt the primary discovery flow more than a one-tap detour hurts the saving flow.
- **Saved state shown on `/events` via a left-edge accent stripe** — full row height, no column added, no horizontal cost. Uses the vertical space rows already commit to. Rationale: rows are tall (long titles + lineup pills); a vertical stripe scales naturally with row height and reads as "tabbed/flagged" without competing with the existing score-colour cues.
- **Filter becomes a dropdown: `My artists` / `Saved` / `All events`** — replaces the existing two-way segmented toggle with a single `<select>` styled to match the adjacent `city` filter-pill. Rationale: three options start to crowd the controls row on mobile (the segmented toggle is already wrapping); a dropdown collapses to constant width regardless of option count and keeps the controls row consistent with the city picker next to it.
- **Future-only by default** — saved events are auto-hidden from the `Saved` view once their date passes. Rationale: this is a discovery tool, not a journal; past events have no actionable value.
- **Strictly private** — no friend visibility, no public lists. Rationale: matches the personal-tool vibe from `docs/working-with-me.md`; avoids opening the social-features can of worms.
- **Migration via the existing `migration.py` detect-and-fix pattern** — no framework, no Alembic.

## Open questions

- **Exact action label on the event detail page** — "Save", "★ Save", "Add to saved", icon-only star toggle? Defer to the plan; should match the rest of the dark-theme button styles.
- **Toggle label** — "Saved" vs "Starred" on the `/events` filter. Probably "Saved" to match the action verb; confirm during implementation.
- **Counter / empty state copy** — does the `Saved` filter need a separate empty state ("No saved events yet — open an event and tap the star")? Likely yes; covered in the plan.
- **Notification toast on save?** — probably overkill given the existing unified-sync toast stack is reserved for background work, but worth a sentence in the plan.

## Next steps

→ `/workflows:plan` for implementation details (schema + migration block, route handlers, HTMX swap target, template changes for `/event/{id}` + `/events`, front-end-spec update, decisions.md entry if any non-obvious choices remain).
