# Working with me

## Vibes

This is a personal tool built for ourselves and our friends. It is not a commercial product. Focus on features and usefulness over efficiency at scale.

## The repo is the source of truth

We don't use external ticketing, wikis, or project management tools. Plans, decisions, specs, and working notes all live in this repo — primarily under `docs/`. If it's not in the repo, it doesn't exist.

## Living documents

The following docs are maintained as we work, not as an afterthought. Update them before or immediately after committing related changes:

- **`docs/front-end-spec.md`** — Updated whenever templates or routes change. Describes user interactions and page behaviour.
- **`docs/project-structure.md`** — Updated whenever files are added, moved, or removed.
- **`docs/decisions.md`** — Updated when we make a non-obvious architectural or design choice. Always propose the entry and wait for confirmation before writing.
- **`docs/plans/`** — Feature plans and ideas live here.

## Workflow rules

- Always activate `.venv` before running any Python commands.
- Migrations run on startup in `migration.py` — detect old schema, fix in-place. No migration framework.
- SQLite table rebuild pattern for altering constraints (CREATE new -> INSERT SELECT -> DROP old -> RENAME).
- Multi-user: artist scores are per-user via `UserArtist`. Genre classifications are per-user via `UserGenreClassification`.
- Genre profiles (dance, jazz, rock, pop, country) are seeded into `GenreClassification`. Users get a copy in `UserGenreClassification` on first import.
- Background threads: Spotify import and event fetch run in daemon threads with polling progress bars (HTMX 1s poll).
- Admin routes check `ADMIN_SPOTIFY_IDS` env var.
