---
date: 2026-04-01
idea: Multiple genre profile templates with admin UI for base classifications
type: extension
extends: user-level genre ranking
status: idea
---

# Genre Profile Templates + Admin Classification UI

Right now there's one hardcoded "dance" profile template backed by the global `GenreClassification` table. Every new user gets seeded from it. The idea is to support multiple profile templates (jazz, rock, electronic, etc.) and give admins a proper UI to manage the base classifications that seed new users — instead of only being able to classify via the API route.

## Rough shape
- Multiple named profile templates, each with its own set of genre→category mappings
- Admin UI page for managing templates: view all genres in a template, bulk-classify them, create new templates
- Users could pick a profile when they first sign up (or switch later), which re-seeds their `UserGenreClassification` from that template
- The existing "Reset to defaults" button would reset to whichever profile the user has selected
- Admin UI could also show which genres are unclassified across templates to help prioritize classification work

## Open questions
- Should templates be stored as rows in a new table, or as separate columns/tags on `GenreClassification`?
- Can a user blend multiple profiles (e.g. "I like jazz AND electronic") or is it one template at a time?
- How does a new template get bootstrapped — copy from an existing one and tweak, or start from scratch?
- Should there be a "community" angle where popular user overrides inform template defaults?
