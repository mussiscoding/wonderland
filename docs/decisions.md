# Decisions

Architectural and design choices we've made explicitly. Each entry should capture what we decided, why, and any alternatives we considered.

---

## Events-first UX

We moved from an artists-first navigation to events-first. The build order was necessarily artists → genres → events (you need artists scored before you can score events), but that doesn't dictate what the user sees first. Artists and genres are admin work — the user tweaks them to improve their recommendations. Events are where they get value. The home page should answer "what should I go to?" not "here are your artists."

## Multi-signal scoring represents "want to see live"

The artist score is not "most listened to." It combines multiple signals — follows, saved tracks, playlist appearances, intentional plays, top artist rankings — each independently capped so no single signal dominates. Genre multipliers then weight the total so artists in genres you care about surface higher. The score represents "how much would I want to see this artist live given my listening and genre preferences." Manual override exists for when the auto-score gets it wrong.

## Genre multipliers are per-user, seeded from templates

A jazz fan's favourite artists shouldn't get crushed by dance-centric multipliers. On first import, users pick a genre profile (dance, jazz, rock, pop, country) which seeds their personal genre classifications. From that point they own their classifications independently — template changes don't retroactively affect existing users. Unclassified genres get a 0.3x "benefit of the doubt" multiplier rather than being penalised.

## Fuzzy matching biased toward recall, threshold 85

Artist-to-lineup matching uses rapidfuzz with a threshold of 85. False positives (a wrong match appearing in your events) are a minor annoyance you can ignore. Missed events (a real match not being found) are actually painful — you miss a gig. So we err on the side of loose matching. Names are heavily normalised first (strip DJ/MC prefixes, live/DJ set suffixes, punctuation). Short names (3 chars or fewer like "MK") skip fuzzy matching entirely because Levenshtein is too unreliable at that length — they can still be found by exact match.

## Multi-source scraping with lineup merging

We scrape from 5 sources (RA, Dice, Skiddle, Ticketmaster, Eventbrite) because no single source has complete coverage, especially for London dance music. Events are deduplicated by venue + date + city. When the same event appears on multiple sources, we merge lineups (union of artists) rather than discarding duplicates — RA might list 8 artists where Dice lists 6 with 2 unique ones. All sources are kept per event so users can choose where to buy tickets or check details.

## Per-user data model via junction tables

All artist scores and genre classifications are per-user, not global. `UserArtist` holds the per-user score and signal data for each artist. `UserGenreClassification` holds the per-user genre category assignments. This means two users can have completely different scores for the same artist and different genre weightings, which is the whole point — the app serves any music taste, not just one person's.
