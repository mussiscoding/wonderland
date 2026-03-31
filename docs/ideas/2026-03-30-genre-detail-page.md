---
date: 2026-03-30
idea: Genre detail page showing all artists with that genre
type: extension
extends: genres
status: complete
---

# Genre Detail Page

From the genres list, clicking a genre should take you to `/genre/{genre}` and show all the artists tagged with that genre. Simple drill-down from the genres overview.

## Rough shape
- Clickable genre names on `/genres` linking to `/genre/{genre_name}`
- Detail page lists all artists that have that genre in their genres JSON
- Probably link through to artist pages / upcoming events from there too - to artist pages yes.

## Open questions
- Should genres with slashes or spaces in the name use slugs or URL encoding? - yes
- Any filtering/sorting on the artist list (e.g. by number of upcoming events)? - sort by score
- Show genre classification category (dance/adjacent/other) on the detail page? - yes
