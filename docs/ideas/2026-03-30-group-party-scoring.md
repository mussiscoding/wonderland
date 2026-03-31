---
date: 2026-03-30
idea: Combine multiple users' Spotify taste into a group score for finding gigs everyone would enjoy
type: extension
extends: multi-user auth & event scoring
status: idea
---

# Group / Party Scoring

Now that we have multi-user auth, the next obvious thing is: you're going out with 3 mates, which night has the best lineup for *all* of you? Create a group, combine everyone's artist scores, and rank events by collective interest. The group score for an event would factor in all members' artist affinities — so a night where everyone recognises at least one act beats a night where only you care.

## Rough shape
- Create a "party" or "group" — just a named collection of users
- Each member links their Spotify (already works via existing auth)
- Group event score = some combination of all members' individual event scores (sum? average? could weight by "at least N people care")
- Group events page shows the merged ranking — highlight which artists each person contributed
- Could show a breakdown: "John: 80, Sarah: 45, Mike: 20" per event so you can see who's driving the score

## Open questions
- How to combine scores? Simple average favours events everyone likes a bit; sum favours events one person loves. Maybe both views?
- Should there be a minimum threshold — e.g. at least 2 out of 4 people need a score > 0 for the event to rank?
- How do you invite someone to a group? Share a link? They need to be logged in already?
- Temporary groups (for a specific weekend) vs persistent groups (your regular crew)?
