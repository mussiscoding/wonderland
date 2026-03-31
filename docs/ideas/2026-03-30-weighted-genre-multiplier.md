---
date: 2026-03-30
idea: Genre multiplier should consider all genres, not just pick the best one — one "adjacent" tag among five "other" tags shouldn't get the full 0.5x
type: extension
extends: genre scoring
status: idea
---

# Weighted Genre Multiplier

Currently the genre multiplier picks the *best* category across all an artist's genres. So Bishop Briggs has "electronic" (adjacent, 0.5x) but also alternative rock, folk, indie pop, indie rock, soul — all "other" (0.1x). She gets 0.5x because of that one electronic tag, but she's clearly not a dance artist. The multiplier should reflect the balance of genres, not just the best one.

## Rough shape
- Instead of `max(multipliers)`, use a weighted average or majority-wins approach
- e.g. average all genre multipliers: Bishop Briggs = (0.5 + 0.1 + 0.1 + 0.1 + 0.1 + 0.1) / 6 = 0.17
- Or: weight by proportion — if 5/6 genres are "other", the multiplier should be much closer to 0.1 than 0.5
- Could also do: only count the best genre if it represents at least N% of the artist's genres (e.g. majority rule)

## Open questions
- Which approach feels right — average, weighted, or threshold-based?
- Should "dance" genres still be able to override everything? (e.g. an artist tagged "techno" + 3 other genres is still clearly a dance artist)
- Does this need UI changes to show the breakdown, or just change the multiplier calculation?
