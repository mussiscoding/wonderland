# User-Level Genre Ranking

**Date:** 2026-03-31
**Status:** Ready for planning

## What We're Building

Move genre classification from a single global system to per-user genre preferences. Currently all users share one `GenreClassification` table — when someone classifies "jazz" as "other", it affects scoring for every user. This means the app only works well for dance music fans.

The end state: users pick a **genre profile** on signup (dance, jazz, rock, pop, country) which seeds their personal genre→category mappings. They can then tweak individual genres on the `/genres` page, which becomes per-user.

**Phase 1 (this work):** Build the per-user infrastructure with a single "dance" default that matches the current global classifications. Existing users get migrated to this default.

**Phase 2 (extension):** Define the jazz, rock, pop, and country profile defaults. Add profile selection to signup flow.

## Why This Approach

The app currently wastes events for anyone who isn't into dance music. A jazz fan's favourite artists all get crushed by the 0.1x "other" multiplier. Per-user genre ranking is the foundation that makes the app useful for any music taste.

We chose **scoped-to-user's-artists** over copy-all-upfront or overrides-only because:
- Users only see genres relevant to their library — no noise from genres they'll never encounter
- No fallback/join logic at scoring time — every genre the user needs is in their table
- No broadcast writes when new genres appear — only users with the relevant artist get the row
- Simple queries — `get_genre_map(session, user_id)` reads only from `UserGenreClassification`

## Key Decisions

0. **Genre-agnostic categories** — Replace dance-centric labels (dance/adjacent/other) with generic ones: `high` (1.0x), `medium` (0.5x), `low` (0.1x), `unclassified` (0.3x, temporary). These work across all profile types — a jazz profile has jazz genres as "high", a dance profile has techno as "high", etc. Existing `GenreClassification` rows migrated: dance→high, adjacent→medium, other→low.

1. **Per-user /genres page** — The existing `/genres` page becomes user-scoped. Each user sees and edits their own genre mappings, with artist counts scoped to their library.

2. **Category comes from the user's profile default** — When a user first encounters a genre (via import), the category is copied from their profile's default template (e.g. the "dance" template). For Phase 1 there's only one profile, so this is the global `GenreClassification` table. After copying, the user's row is independent.

3. **Truly new genres start as unclassified (0.3x)** — If a genre doesn't exist in any template yet, it enters the global table as unclassified and gets added to the user's table as unclassified. An admin can classify it on the global table later.

4. **Admin classification propagates to unclassified users** — When an admin classifies a genre on the global template, all `UserGenreClassification` rows for that genre where `category = 'unclassified'` get updated. Users who have already manually reclassified it are left alone.

5. **Genre fetching only for new artists** — During a user import, genres are only fetched/synced for artists new to the system (no existing `ArtistGenre` rows). Refreshing genres for existing artists is a future cron/admin concern, not user-driven. This eliminates cross-user writes during import.

6. **Global GenreClassification stays as the admin-writable template** — It remains the source of truth for initial category assignments. Future profiles (jazz, rock, etc.) will be alternative templates. For Phase 1, the current global table IS the "dance" default.

7. **Rescoring becomes per-user only** — When a user changes a genre classification, only their scores are recomputed. Admin classify triggers rescore for all affected users (those whose unclassified row was updated).

## Data Model Sketch

```
User
  + genre_profile: str = "dance"  (which profile template they started from)

UserGenreClassification (NEW)
  id, user_id (FK, index=True), genre_name (str, index=True), category (str)
  created_at, updated_at
  UniqueConstraint(user_id, genre_name)

GenreClassification (existing, repurposed)
  Admin-writable template for the "dance" profile. Admins classify genres here;
  changes propagate to users who haven't overridden them.
  Future profiles may be additional tables or code constants.
```

## Migration Plan (Conceptual)

1. Create `UserGenreClassification` table
2. Add `genre_profile` column to `User` (default "dance")
3. For each existing user, seed their genres using `seed_user_genres()` (see below)
4. Update `get_genre_map()` to accept `user_id` and read from `UserGenreClassification`
5. Update `/genres` routes to be user-scoped (including artist counts scoped to user's artists)
6. Update classify endpoints to write to `UserGenreClassification` and rescore only that user
7. Update `spotify.py` import to only fetch/sync genres for artists new to the system (skip `_backfill_genres` and `_sync_artist_genres` for artists that already have `ArtistGenre` rows)
8. Update `_sync_genre_classifications()` to also create `UserGenreClassification` rows for the importing user via `seed_user_genres()`

### Shared `seed_user_genres()` function

A single reusable function that copies genres for a user's artists from their profile template into `UserGenreClassification`. Called from:
- **Migration** (step 3) — seed existing users
- **Signup/first import** — seed new users
- **Reset to defaults** — re-seed a user's genres from their profile template
- **Import genre sync** — add newly discovered genres for the importing user

## Resolved Questions

- **Should users be able to reset to their profile defaults?** Yes — add a "Reset to dance defaults" button on the `/genres` page. Good escape hatch.
- **Should profile selection be changeable after signup?** Not for Phase 1. Lock profile at signup, revisit when multiple profiles exist in Phase 2.

## Extensions (Phase 2+)

- Define jazz, rock, pop, and country profile templates
- Add profile selection to signup flow
- Allow profile switching after signup (only affects new genres vs full re-seed TBD)
- Auto-classify new genres via semantic/artist matching against profile templates instead of defaulting to unclassified
- Cron/admin job to refresh genres for existing artists and propagate changes to all users who have those artists
