# Front-End Spec

Describes the desired user interactions and page responses across all pages. Implementation-agnostic — this should read the same whether we're using HTMX, React, or anything else.

---

## Global

### Layout
- **Desktop**: horizontal nav bar with **Artists**, **Events**, **Genres**, **Admin** links. User area right-aligned: display name + "Switch" + "Log out" when logged in, or "Link Spotify" button when not
- **Mobile** (<=600px): hamburger button (top-left, fixed). Opens a left-side overlay panel (~70% width) with nav links and user area at the bottom. Tapping outside closes it.
- Favicon: disco ball emoji (🪩)
- Dark theme throughout

### Auth states
- **Not logged in**: Artists page shows empty state with "Connect Spotify" button. Events and Genres redirect to login.
- **Logged in**: All pages show the current user's data scoped to their account

### Genre tags (shared component)
- Appear on Artists, Artist Detail, Genre Detail, and Events pages
- Pill-shaped tags showing genre name, colour-coded by user's classification: green (high), amber (medium), grey (low/unclassified)
- Clickable — link to `/genre/{name}` detail page
- Visually identical whether clickable or not (no underline, no link colour)
- When many genres: show all that fit in 2 rows, overflow hidden (height computed dynamically from actual tag size)

### Score display (shared component)
- Bold number, colour-coded: green (50+), amber (30-49), grey (<30)

---

## Artists (`/artists`)

### Empty states
- No user logged in: "Connect Spotify to get started" + connect button
- Logged in, no artists: "No artists imported yet" + Import button

### Controls
- **Search box**: filters artists by name. Results update live after 300ms pause in typing, no submit needed. URL updates to reflect current filters.
- **Re-import button**: triggers background Spotify re-import. Shows inline progress indicator that polls every 1s until complete.

### Table
- Columns: Score, Artist, Genres
- **Score**: clickable — opens a modal to set a manual score (0–100). Shows "manual" label when overridden, "excluded" when excluded.
- **Score header**: clickable, toggles between descending (default, ▼) and ascending (▲)
- **Artist header**: clickable, toggles between A-Z (▲) and Z-A (▼)
- **Score divider**: when sorted by score descending, a dashed line appears between score 30 and below with text "below this line: probably not going to dance to these"
- **Artist name**: clickable, links to artist detail page
- **Genre tags**: shared component (see above)

### Import progress
- When import is running, an inline progress indicator appears next to the Re-import button
- Polls for updates every 1 second
- Disappears when import completes

---

## Artist Detail (`/artist/{id}`)

### Navigation
- "← Back to artists" link at top

### Content (top to bottom)
1. Single-row table with: Score, Artist name, Genre tags, Signals (same format as artist list). Score shows "manual"/"excluded" labels when applicable.
2. **Manual score controls**: "Score manually" button (opens modal) + "Exclude artist" checkbox. "Clear manual score" available in modal when a manual score is set.
3. **Events section**: table of all events where this artist has a match. Columns: Date, Event, Venue, City, Price, Links. Sorted by date ascending. Shows "No upcoming events found for this artist." if none.
4. Embedded Spotify artist player widget (iframe) + link to open in Spotify

---

## Events (`/events`)

### Controls
- **Search box**: filters events by title, venue, or artist name. Results update live after 300ms pause in typing. URL updates.
- **City dropdown**: filters events by city (London / Berlin / All cities). Part of the main form — updates live via htmx. Default is London. URL param: `?city=london|berlin|all`.
- **Date range**: two native date inputs (from/to) that filter events by date. Part of the main form — updates live via htmx like search.
- **Quick date buttons**: "Tonight", "This weekend", "This week", "This month", "All dates" — clicking one sets the date range inputs and triggers the filter. Pure client-side JS, no separate server logic.
- **Show all / Matched only toggle**: switches between showing only events with matched artists vs all events. Preserves city filter.

### Table
- Columns: Score, Date, Event, Venue, Lineup, Links
- **Score**: event relevance score (sum of matched artist contributions). Colour-coded like artist scores. Hover tooltip shows breakdown of which artists contribute how many points. Sortable (▼/▲).
- **Date header**: clickable, toggles between ascending (earliest first, ▲) and descending (▼)
- **Date**: formatted as "Mon 01/06"
- **Event title**: clickable, links to `/event/{id}` detail page
- **Lineup**: all artists as pills — matched artists highlighted in green (sorted first), others in grey. Capped at 6 with "+N" overflow. Matched artist pills link to `/artist/{id}`.
- **Links**: buttons for each source (RA, Skiddle, Dice) linking to the event on that platform. Opens in new tab.

### Empty state
- No matched events: suggests showing all events or fetching new ones
- No events at all: prompts to fetch events

---

## Event Detail (`/event/{id}`)

### Navigation
- "← Back to events" link at top

### Header
- Event title, date (full format: "Friday 05 June 2026"), venue name, city

### Tickets
- Buttons for each source (Resident Advisor, Dice, Skiddle, etc.) linking to the event page
- Each button shows the price from that source if available

### Lineup
- Full lineup as pills — matched artists in green (linked to artist detail), unmatched in grey
- Sorted: matched artists first, then resolved (have Spotify ID but not in user's library), then unresolved
- Resolved artists come from the admin "Resolve Lineup Artists" step which searches Spotify for lineup names

### Your score breakdown
- Headed "Your score breakdown" — personalised to the current user
- Columnar breakdown showing each matched artist's contribution to the event score
- Artist names link to their detail pages
- Total line shows colour-coded "your event score" label

### Listen
- Spotify embed players for all resolved artists (matched + resolved via Spotify search), compact 152px height
- Displayed in a flex-wrap grid (300px per embed)
- Only shown for artists with a known Spotify ID; unresolved lineup names are skipped

### Similar events
- Table of other events sharing matched artists with this event
- Columns: Date, Event (linked), Venue, Shared artists (as green pills)
- Requires 2+ shared artists (or 1 if the event has ≤2 matched artists)
- Limited to future events, sorted by shared count descending, max 10

---

## Genres (`/genres`)

Genre data is per-user — each user has their own genre classifications via `UserGenreClassification`. Artist counts are scoped to the user's library.

### Empty state
- No genres yet (user hasn't imported): "No genres yet" message with link to Artists page to import

### Controls
- **Search box**: filters genres by name. Results update live after 300ms pause in typing. URL updates.
- **Category dropdown**: filters by classification (All, Unclassified, High, Medium, Low). Triggers filter on change.
- **Clear all classifications button**: sets all genre classifications to unclassified. Requires confirmation dialog. Positioned right-aligned in controls bar.

### Table
- Columns: Genre, Artists, Category, Rating
- **Genre name**: clickable, links to genre detail page
- **Artists header**: clickable, toggles sort by artist count (descending ▼ → ascending ▲ → default)
- **Artists column**: count of user's artists with this genre
- **Category column**: shows classification as a coloured tag (green for high, amber for medium, grey for low/unclassified)
- **Rating column**: three small buttons (H, M, L) for classifying genre as High, Medium, or Low
  - Active classification is highlighted (green for H, amber for M, grey for L)
  - Clicking a button immediately reclassifies the genre for this user only, updates just that row inline (no full page reload), and triggers a rescore of the user's artists

---

## Genre Detail (`/genre/{name}`)

### Navigation
- "← Back to genres" link at top

### Header
- Genre name with classification badge (coloured tag showing user's classification: high/medium/low/unclassified)
- **Classification badge is clickable** — shows an H/M/L popup to reclassify the genre inline. Triggers rescore and page reload on selection.
- Artist count (scoped to user's library)

### Table
- Columns: Score, Artist, Genres
- Sorted by score descending
- Only shows artists in the user's library
- **Artist name**: clickable, links to artist detail page
- **Genre tags**: shared component

---

## Admin (`/admin`)

### Content
- **Fetch Events**: city selector (London / Berlin / Both) + Fetch button. Triggers background event fetch from sources that support the selected city. Redirects to progress page. Progress messages include city name.

---

## Event Fetch Progress (`/admin/fetch/progress`)

- Full-page progress display during event fetching
- Shows current step (which source is being fetched)
- Progress bar with count (e.g. "42 / 100")
- Auto-polls every 1 second for updates
- Auto-redirects to events page when complete

### Fetch-complete toast (admin only)
- When an admin's event fetch finishes, a toast appears bottom-right: "Events fetch complete — X new, Y updated, Z unchanged" (new = first-seen events, updated = existing events whose lineup gained artists, unchanged = re-seen with no change)
- Persists until manually dismissed via the × button; never auto-dismisses
- Appears on whatever page the admin is on when the fetch completes, and re-appears on navigation until dismissed (driven by server-side per-user fetch state)
- A hidden poller is rendered only while a fetch is running; it stops polling the moment the fetch completes (no idle polling). Non-admins never receive the poller or toast.

---

## Choose Profile (`/choose-profile`)

- Shown once after a new user's first import completes (before they have any `UserGenreClassification` rows)
- Nav bar is hidden during onboarding
- Heading: "What music are you into?"
- Subtitle explains this is just a starting point and genres can be changed later
- Radio list: Dance & Electronic (default), Jazz, Rock, Pop, Country, "No preference — I'll classify genres myself"
- Single "Continue" button submits the form
- POST seeds `UserGenreClassification` from the chosen template, rescores artists, then redirects to `/artists`
- Returning users (who already have genre classifications) are redirected straight to `/artists` if they visit this page

---

## Artist Import Progress (`/import/progress`)

- Full-page progress display during Spotify import
- Shows current step (which data source is being pulled)
- Progress bar with count
- Auto-polls every 1 second for updates
- New users (no genre classifications): auto-redirects to `/choose-profile` when complete
- Returning users: auto-redirects to `/artists` when complete
