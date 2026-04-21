# Genre Profile Templates (Phase 2)

**Date:** 2026-04-19
**Status:** Ready for planning
**Builds on:** [User-Level Genre Ranking (Phase 1)](2026-03-31-user-level-genre-ranking-brainstorm.md)

## What We're Building

New users choose a genre starter template at signup (dance, jazz, rock, pop, country, or "no preference") which seeds their `UserGenreClassification` table. The template is a one-time seed — after that, the user has complete control over their classifications. There is no ongoing profile identity; if they want to shift focus, they just reclassify genres themselves.

## Why This Approach

- **Templates are just starters** — no profile identity, no switching mechanism, no propagation from admin to existing users. Simple.
- **All templates in one table** — add `profile_name` column to existing `GenreClassification`. No new tables, no special treatment for dance.
- **Start minimal** — only classify ~20-30 obvious genres per template. Everything else stays unclassified (0.3x). Grow via admin over time.
- **Import-first flow** — user imports artists before choosing a template, so `seed_user_genres()` runs synchronously with the chosen profile_name. No need to persist the choice on the User model.

## Key Decisions

1. **Templates live in `GenreClassification`** — Add `profile_name` column. Existing rows get `profile_name='dance'`. New rows added for jazz/rock/pop/country.

2. **Drop `User.genre_profile`** — the template choice is transient. The new flow (import → choose profile → seed) means `seed_user_genres()` runs synchronously in the `/choose-profile` POST handler with the profile_name from the form. No need to persist it.

3. **Import-first signup flow** — Auth callback redirects new users (no `UserArtist` rows) to `/imports` instead of `/artists`. After import completes, redirect to `/choose-profile`. User picks a template, `seed_user_genres()` runs, then redirect to `/artists`. Includes a "No preference" option that seeds everything as unclassified.

4. **Profile selection page** — simple radio list with flavour text explaining this is just a helpful starter and they can customise every genre afterwards.

5. **`seed_user_genres()` takes a `profile_name` parameter** — filters `GenreClassification` by `profile_name`. For "none" (no preference), all genres seeded as unclassified with no template lookup.

6. **Re-import always seeds new genres as unclassified** — the template is only used for the first seed. On subsequent imports, new genres get `unclassified` regardless.

7. **No admin propagation** — admin edits to templates only affect future signups. Existing users are never touched. `user_modified` tracking no longer needed.

8. **"Reset to defaults" becomes "Clear all classifications"** — sets all the user's genres to unclassified. Clean slate, no template re-seeding.

9. **Abandoned flow defaults to unclassified** — if a user imports but abandons before picking a profile (closes browser), they land on `/artists` next time. Their genres get seeded as unclassified on next import/rescore. They can classify manually from `/genres`.

## Resolved Questions

- **Should users be able to switch profiles?** No. They just reclassify genres manually, or use "Clear all classifications" for a blank slate.
- **Should admin changes propagate to existing users?** No. Templates are for future signups only.
- **Do we need `User.genre_profile`?** No. The import-first flow means the template choice is available synchronously when `seed_user_genres()` runs — no need to persist it.
- **How to populate non-dance templates?** Start minimal (~20-30 genres each), grow via admin over time.
- **What if the user doesn't want a starter?** "No preference" option. All genres seeded as unclassified.
- **What about re-imports?** New genres always seeded as unclassified, regardless of original template.
- **What if user abandons mid-flow?** They land on `/artists` next login. Genres default to unclassified.
- **How to detect new vs returning user?** Check for `UserArtist` rows. No artists = new user → redirect to `/imports`.

## Data Model Changes

```
GenreClassification (modified)
  + profile_name: str (indexed, default "dance")
  Existing UniqueConstraint on `name` → changes to UniqueConstraint(profile_name, name)

User (modified)
  - Drop `genre_profile` column
```

No changes to `UserGenreClassification` model.

## Extensions (Future)

- Auto-classify new genres via LLM/semantic matching against template patterns
- Let users pick a template when clearing classifications (re-seed instead of blanking)
- "Suggest a profile" based on the user's Spotify listening history
