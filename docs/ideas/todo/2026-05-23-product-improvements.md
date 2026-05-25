# Product Improvements — UX, Features & Design

Ideas from a product review focused on making the app better for a small group of friends. Not about monetization or competitive positioning — just making a better app.

## UX Quick Wins

### Event titles should be clickable
Event titles in the table are plain text. Wrap them in a link to the first source URL so every row is immediately actionable. One-line template change in `events.html` line 122.

### Show event relevance score
`compute_event_score` is already called and stored in `event_scores` in `routes/events.py` but never passed to the template. Display it so users understand why events are ranked the way they are.

### Remember city selection
Berlin-based friends have to switch from London on every visit. Store last city selection in the session cookie.

### Post-onboarding redirect to Events
After first import + genre profile selection, redirect to `/events` instead of `/artists`. New users land on their artist list and think "so what?" — events is where the value is.

### Show genre classification impact
When a user classifies a genre as H/M/L, nothing visibly changes. Show a toast like "12 artist scores updated" so they know their action had an effect.

### Simplify signal breakdowns on artist detail
Replace raw point-math display (`"3 saved (+21) ×0.65 genre match"`) with human-readable summary: "You've saved 3 of their tracks and they match genres you like." Keep raw numbers behind a "details" toggle for power users.

### Score tooltip
Add a small `?` icon next to the "Score" column header on artists page that explains what scores mean in plain English.

### Show matched count on toggle
Change "My artists" / "All events" toggle to show counts: "My artists (23)" vs "All events (156)".

### "Last updated" timestamp on events
Users have no idea if event data is fresh or a week old. Show "Events last updated: 2 hours ago" on the events page.

### Fix "Back to artists" link context
Artist detail page always links back to `/artists` even when you came from events. Use referrer or query param to return to the right place.

## Social Features

### "Interested / Going" flags
Let users mark events as interested/going. Show which friends have flagged the same event. Needs one new table: `EventInterest(user_id, event_id, status)`. This is the thing that tips "maybe" to "yes."

### Group night out scoring
Already sketched in `docs/ideas/todo/2026-03-30-group-party-scoring.md`. Merge scores across friends, show per-person breakdown. Viral growth — every group member is a new user.

### "What are my friends into?"
Show artists that 3+ friends follow but you don't. Friend-powered discovery from data already in `UserArtist`.

### Share to WhatsApp + calendar export
People plan nights in WhatsApp. Add a share button that formats event details as clean text. Plus `.ics` download for calendar apps. Two small endpoints using data already in `Event` and `EventSource`.

### Past event history / "I was there"
Let users mark past events as "went" to build a personal gig history. Feeds into discovery over time.

## Discovery Features

### Venue affinity
Derive which venues consistently host lineups the user scores highly on. Data is already there: join `Event` → `Match` → `UserArtist`, group by `venue_name`. Answers "I don't know these DJs but I always have a good night at Phonox."

### Lineup co-occurrence discovery (Similar Vibes)
Already detailed in `docs/ideas/todo/2026-03-27-similar-vibes-discovery.md`. "This DJ appeared on 4 lineups with artists you love." Uses accumulated historical data no other app has. Medium-term north star feature.

### Festival mode
Paste a festival lineup, see match score across the whole thing. Lineup parser already handles stage prefixes. Group results by day/stage.

### Manual artist entry
Already sketched in `docs/ideas/todo/2026-03-28-manual-artist-entry.md`. Artists you want to see live but aren't in Spotify. Simple form: name + score, matching works on name.

### Taste profile summary
Dashboard with stats: "You follow 340 artists across 45 genres. Top genre: UK garage. 23 events match you this month." All derivable from existing tables. Fun, shareable.

## Data Quality

### Stale event cleanup
Events fetched up to 270 days out are never cleaned up. Past events can appear in results. Add a startup job or periodic cleanup deleting events older than yesterday.

### Sold out / availability tracking
Add a `status` field to `EventSource` (on sale, sold out, few remaining). RA and Dice both surface this info. Saves the frustration of getting excited about a sold-out event.

### Smarter event dedup
Current dedup is `venue_name + city + date`. Add secondary layer matching on overlapping lineups (3+ shared artists = likely duplicate) to catch variant venue names.

### Price filter
Normalize `EventSource.price` to numeric values. Add "under £X" filter to events page.

### Scraper health monitoring
Alert when a scraper returns zero events or fails. Simple log check prevents silent data staleness.
