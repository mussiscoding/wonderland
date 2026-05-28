---
title: Persistent fetch-complete toast (admin)
type: feat
status: done
date: 2026-05-29
---

# Persistent fetch-complete toast (admin)

When an admin runs an event fetch, show a toast — *"Fetch complete — X new, Y updated"* —
that appears on whatever page they're on when the fetch finishes and stays until they
manually close it. Admin-only. No forever-polling: polling exists only during the active
fetch and stops the instant it completes.

## State (server-side, in-memory)

The existing per-user `event_progress[user_id]` dict (`app/events.py`) is the single source
of truth — server RAM, not browser. Already added: `new_events`, `updated_events`,
`acknowledged`. Derived condition:

- `running` → fetch in flight
- `done and not acknowledged` → finished, toast not yet dismissed

## Behaviour

**Render-time gate in `base.html`** (admin only), three cases:
- `running` → render the polling div (`hx-get` notification endpoint, `hx-trigger="every 2s"`, `hx-swap="outerHTML"`).
- `done and not acknowledged` → render the static toast directly (no poll).
- else → render nothing (zero requests when idle).

**Poll endpoint `GET /admin/fetch/notification`** (only hit while running):
- still running → return the polling div again (keep watching).
- now done → return the static toast **without** the `every 2s` trigger → polling stops, toast stays.

**Dismiss `POST /admin/fetch/notification/dismiss`** → set `acknowledged=True`, return empty → toast removed.

`acknowledged` governs only cross-page persistence (a fresh page after completion re-renders
the static toast), not polling.

## Admin gating

Everything behind `is_admin_user`:
- `base.html` poller/toast block wrapped in `{% if current_user and is_admin_user(current_user) and ... %}`.
- Both endpoints check `get_current_user` + `is_admin_user`, redirect/empty otherwise.

## Changes

- `app/templating.py` — register a Jinja global `fetch_pending(user)` reading the progress dict (admin-gated).
- `app/templates/base.html` — conditional poller/toast block + minimal toast CSS (reuse existing dark/green vars).
- `app/templates/fetch_toast.html` — new toast partial (message + × dismiss button).
- `app/routes/admin.py` — `_run_fetch_background` sets counts + `acknowledged=False` on done; add the two endpoints; add new keys to `_EMPTY`.
- `app/events.py` — progress dict defaults (already done).

## Acceptance criteria

- [ ] Non-admin users never get the poller or toast (no requests, no markup).
- [ ] Idle admin pages make zero notification requests.
- [ ] Starting a fetch then navigating to another page shows the toast there on completion.
- [ ] Toast persists across navigation until the × is clicked; never auto-dismisses.
- [ ] Polling stops the moment the fetch completes (verify in network tab).
- [ ] Toast shows correct new/updated counts.

## Notes / caveats

- In-memory state: a server restart mid-fetch loses the toast (same as existing progress bar — no regression).
- Edge: a stale tab loaded *before* the fetch started (and never navigated) has no poller and won't show the toast. Acceptable; SSE would be the fix if ever needed.
- `docs/front-end-spec.md` — update (new admin-facing UI behaviour).
