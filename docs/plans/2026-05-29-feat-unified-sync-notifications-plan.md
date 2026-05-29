---
title: Unified sync notifications (artists + events toasts)
type: feat
status: done
date: 2026-05-29
---

# Unified sync notifications (artists + events toasts)

Generalise the admin fetch-complete toast into one notification system that covers both
the Spotify artist import (all users) and the admin event fetch (admins only), with **live
"…ing" toasts while running** and **dismissible completion toasts** when done. Replaces the
current single-purpose `fetch_notice` machinery — one poller, one endpoint, no duplication.

Builds on the existing toast (`docs/plans/2026-05-29-feat-fetch-complete-toast-plan.md`).

## Toast copy

- Import running: **"Syncing your library…"** (no ×, auto-replaced on completion)
- Import done: **"Synced {N} artists — you match {M} upcoming events"** (dismissible)
- Import error: **"Library sync failed — please try again"** (dismissible)
- Fetch running (admin): **"Fetching events…"** (no ×)
- Fetch done (admin): **"Events fetch complete — X new, Y updated, Z unchanged"** (dismissible, unchanged)
- Fetch error (admin): **"Event fetch failed — please try again"** (dismissible)

Error toasts use a distinct (red/warning) style vs the green success border.

Genre count deliberately omitted — users can have 700+ genres, so it's noise. No
"classify your genres" nudge for the same reason (unreachable target = permanent nag).

## State (server-side, in-memory, per user)

Two existing dicts are the source of truth:
- `event_progress[user_id]` (`app/events.py`) — already has `running/done/acknowledged` +
  `new_events/updated_events/unchanged_events`. **Add:** `error` (default `None`).
- `import_progress[user_id]` (`app/spotify.py`) — currently `running/step/current/total/done`.
  **Add:** `acknowledged` (default `True`), `total_artists`, `matched_events`, `error` (default `None`).

`import_all_artists` already returns `{total_artists, new, updated}` but
`_run_import_background` (`app/routes/artists.py:27`) throws it away — capture it, compute the
user's matched-event count, and stash `total_artists` + `matched_events` + `acknowledged=False`
on completion.

## Error state (so failures don't vanish silently)

**Current behaviour (the bug this fixes):** both background runners catch exceptions and set
`running=False, step="Error: …", done=False` (`app/routes/artists.py:33-35`, and the equivalent
in `admin.py`). Because the toast logic only fires on `done`, an error makes the running toast
**silently disappear** with no completion and no warning — it looks like it succeeded.

**Fix:** on exception, also set `error=<message>` and `acknowledged=False` (keep `done=False`,
so the existing `/import/progress` and `/admin/fetch/progress` *success* redirects are
unaffected — they still key off `done`). `notifications(user)` then surfaces a dismissible
**error toast** when `error and not acknowledged`. Dismiss clears it the same way as a success
toast. `done` stays strictly = success; `error` is the terminal-failure signal.

## New helper: matched upcoming events for a user

The events page already computes this inline (`app/routes/events.py:80-96`). Extract a small
`count_user_matched_events(session, user_id) -> int` (events with score > 0 and `date >= today`)
and reuse it both there and in the import completion path. Cheap; no new state.

## Mechanism (one poller, one endpoint)

**`notifications(user) -> list[dict]`** Jinja global (replaces `fetch_notice`). Returns the
active notices for this user, each `{kind, state, ...}` where `kind` is `artists` / `events` and
`state` is `running` / `done` / `error`:
- `artists` notice (Spotify library sync; any logged-in user): `running` → live; `done and not acknowledged` → completion w/ counts; `error and not acknowledged` → error toast.
- `events` notice (event fetch; **admin only**): same three states.
- omit a notice when idle / acknowledged. Empty list = nothing to show.

**`app/templates/notifications.html`** — renders `<div id="notifications" class="toast-stack">`
containing each notice as a toast (success = green, error = red, running = live/no ×). The
container carries the poll trigger (`hx-get="/notifications" hx-trigger="every 2s"
hx-swap="outerHTML"`) **only if any notice is `running`**; once everything is terminal
(`done`/`error`, static) it has no trigger, so polling stops. Used by both the `base.html`
include and the endpoint (single render path).

**`base.html`** — `{% if notifications(current_user) %}{% include "notifications.html" %}{% endif %}`
right after `<body>` (replaces the current fetch-only block). Idle pages render nothing → zero requests.

**`GET /notifications`** — renders `notifications.html` for the current user (the poll target).
Returns empty string when there are no notices.

**`POST /notifications/dismiss?kind=artists|events`** — sets that kind's `acknowledged=True`, then
re-renders `notifications.html` (container swapped via `outerHTML`, so remaining toasts persist
and a fully-cleared stack returns empty).

Remove the old `/admin/fetch/notification(/dismiss)` endpoints, `fetch_notice`,
`fetch_poller.html`, and `fetch_toast.html` (folded into the unified partial).

## Admin gating

- `artists` notice: all logged-in users.
- `events` notice: gated by `is_admin_user` inside `notifications(user)` and re-checked in both endpoints.
- Non-admins never receive fetch markup; logged-out users get nothing.

## Acceptance criteria

- [ ] Running a Spotify re-import shows a live "Syncing your library…" toast on whatever page the user is on, then a dismissible "Synced N artists — you match M upcoming events".
- [ ] M matches the count shown on the events page for that user.
- [ ] Admin event fetch shows "Fetching events…" then the existing completion toast — both via the unified poller.
- [ ] Non-admins never see the `events` toast; logged-out users see nothing.
- [ ] Idle pages make zero `/notifications` requests; polling stops the moment all active syncs finish.
- [ ] Completion toasts persist across navigation until dismissed; running toasts have no ×.
- [ ] If an import and a fetch are somehow both active, both toasts stack and poll under one container.
- [ ] A failed sync shows a dismissible error toast (not a silently vanishing running toast); the running toast never disappears with no terminal state.
- [ ] An error does **not** trigger the success redirects on `/import/progress` or `/admin/fetch/progress` (`done` stays false on failure).

## Caveats

- In-memory state: server restart mid-sync loses the toast (same as existing progress bars — no regression).
- A page loaded *before* a sync starts, never navigated, has no poller until next navigation. The
  originating page is covered by its existing inline progress bar (`/artists`, `/admin`). SSE would
  close this gap if ever needed; out of scope.
- `docs/front-end-spec.md` — update the existing fetch-toast section to describe the unified system.

## Changes

- `app/spotify.py` — `import_progress` defaults gain `acknowledged/total_artists/matched_events/error`.
- `app/events.py` — `event_progress` default gains `error`.
- `app/routes/artists.py` — `_run_import_background` captures summary + matched count, sets completion state; on exception sets `error` + `acknowledged=False`.
- `app/routes/admin.py` — `_run_fetch_background` on exception sets `error` + `acknowledged=False` (in addition to the endpoint changes below).
- `app/routes/events.py` — extract `count_user_matched_events` helper, reuse in list view.
- `app/templating.py` — `notifications(user)` global (replaces `fetch_notice`).
- `app/templates/notifications.html` — new unified partial (replaces `fetch_poller.html` + `fetch_toast.html`).
- `app/templates/base.html` — unified include + toast-stack CSS.
- `app/routes/admin.py` — drop the two fetch-notification endpoints; add `/notifications` + `/notifications/dismiss` (or place in a small `app/routes/notifications.py`).
- `docs/front-end-spec.md` — update.
