---
date: 2026-05-29
idea: Harden SQLite against concurrent background jobs (event fetch + Spotify import) clashing on writes
type: extension
extends: database / background jobs
status: idea
---

# SQLite concurrency hardening

Our background jobs run in separate threads with separate sessions but share one SQLite DB,
and SQLite locks at the whole-database level for writes (no WAL configured — `app/database.py`
is a bare `create_engine`). So if an admin kicks off an event fetch while a Spotify library
sync is running, the two can collide. It's pre-existing, admin-only, and recoverable (one job
just errors and you re-run), but it's a sharp edge worth filing.

## The sharp one: `run_matching` wipes the whole Match table

`run_matching` does a blanket **`delete(Match)`** (`app/matching.py:104`) and then rebuilds every
row from scratch. So there is a window — the entire rebuild — where the `Match` table is empty or
only partially repopulated. Anything that reads matches during that window sees a degraded result:
- the events page would show **zero/incomplete matched events** mid-rebuild,
- the import's `matched_events` count (in the new notifications work) could be captured against a half-built table,
- and if an import is concurrently adding `Artist` rows, the rebuild reads whatever's committed at
  that instant, so the new matches can be incomplete until the *next* matching run.

It's not corruption and it self-heals on the next run, but the full-table-wipe-then-rebuild is the
root of the staleness, not just lock contention. Worth considering an incremental/transactional
rebuild (build into a temp set, swap) rather than delete-all-up-front.

## Rough shape
- Enable WAL mode + a generous `busy_timeout` on the engine (e.g. `connect_args={"timeout": 30}` + `PRAGMA journal_mode=WAL`). One small change, helps the whole app's concurrency, not just this case.
- The other failure mode: **lock contention** — concurrent commits serialise; if one holds the write lock past the timeout, the other throws `database is locked`, the job's try/except catches it, sync fails.
- Address the Match wipe (above) — at minimum keep the delete+rebuild inside one transaction so readers never see the empty window; better, rebuild into a shadow and swap.
- Alternative/extra: a global "a sync is already running" guard that blocks or queues the second job (more UX friction — probably overkill).

## Open questions
- Is WAL + busy_timeout enough on its own, or do we still want to serialise the two job types?
- Does WAL play nicely with the SQLite backup job (`project-backup@wonderland.service`) on the server?
- Surfacing: once the notification error-toast work lands, a clashed job will at least show an error toast rather than vanishing — is that good enough, or do we want retry?
