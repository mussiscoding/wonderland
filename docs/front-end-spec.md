# Front-End Spec

Describes the desired user interactions and page responses across all pages. Implementation-agnostic — this should read the same whether we're using HTMX, React, or anything else.

---

## Global

### Layout
- Fixed nav bar at top: **Artists**, **Events**, **Genres** links
- User area in nav (right-aligned): shows display name + "Switch" + "Log out" when logged in, or "Link Spotify" button when not
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
- Columns: Score, Artist, Genres, Signals
- **Score header**: clickable, toggles between descending (default, ▼) and ascending (▲)
- **Artist header**: clickable, toggles between A-Z (▲) and Z-A (▼)
- **Score divider**: when sorted by score descending, a dashed line appears between score 30 and below with text "below this line: probably not going to dance to these"
- **Artist name**: clickable, links to artist detail page
- **Genre tags**: shared component (see above)
- **Signals column**: shows breakdown of scoring signals — followed, saved tracks, intentional plays, playlist appearances, top artist ranges — each with point values. Ends with genre multiplier (e.g. "×1.0 genre match")

### Import progress
- When import is running, an inline progress indicator appears next to the Re-import button
- Polls for updates every 1 second
- Disappears when import completes

---

## Artist Detail (`/artist/{id}`)

### Navigation
- "← Back to artists" link at top

### Content
- Single-row table with: Score, Artist name, Genre tags, Signals (same format as artist list)
- Below the table: embedded Spotify artist player widget (iframe)
- Link to open artist in Spotify

---

## Events (`/events`)

### Controls
- **Search box**: filters events by title, venue, or artist name. Results update live after 300ms pause in typing. URL updates.
- **Date range**: two native date inputs (from/to) that filter events by date. Part of the main form — updates live via htmx like search.
- **Quick date buttons**: "Tonight", "This weekend", "This week", "This month", "All dates" — clicking one sets the date range inputs and triggers the filter. Pure client-side JS, no separate server logic.
- **Show all / Matched only toggle**: switches between showing only events with matched artists vs all events
- **Fetch Events button**: triggers background event fetch from all sources (RA, Skiddle, Dice). Redirects to progress page.

### Table
- Columns: Score, Date, Event, Venue, Matched Artists, Lineup, Price, Links
- **Score header**: clickable, toggles between descending (default, ▼) and ascending (▲)
- **Date header**: clickable, toggles between ascending (earliest first, ▲) and descending (▼)
- **Score**: event score based on sum of matched artist scores weighted by match confidence. Dash (—) if no matches.
- **Date**: formatted as "Mon 01 Jan"
- **Matched Artists**: shown as green genre-tag pills with artist name + their score in small text. Tooltip shows match type and confidence.
- **Lineup**: all artists as pills — matched artists highlighted in green (sorted first), others in grey. Capped at 6 with "+N" overflow.
- **Price**: cheapest price from sources, or dash if none
- **Links**: buttons for each source (RA, Skiddle, Dice) linking to the event on that platform. Opens in new tab.

### Empty state
- No matched events: suggests showing all events or fetching new ones
- No events at all: prompts to fetch events

---

## Genres (`/genres`)

Genre data is per-user — each user has their own genre classifications via `UserGenreClassification`. Artist counts are scoped to the user's library.

### Empty state
- No genres yet (user hasn't imported): "No genres yet" message with link to Artists page to import

### Controls
- **Search box**: filters genres by name. Results update live after 300ms pause in typing. URL updates.
- **Category dropdown**: filters by classification (All, Unclassified, High, Medium, Low). Triggers filter on change.
- **Reset to defaults button**: resets all genre classifications to the profile template defaults. Requires confirmation dialog. Positioned right-aligned in controls bar.

### Table
- Columns: Genre, Artists, Category, Actions
- **Genre name**: clickable, links to genre detail page
- **Artists header**: clickable, toggles sort by artist count (descending ▼ → ascending ▲ → default)
- **Artists column**: count of user's artists with this genre
- **Category column**: shows classification as a coloured tag (green for high, amber for medium, grey for low/unclassified)
- **Actions column**: three small buttons (H, M, L) for classifying genre as High, Medium, or Low
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

## Event Fetch Progress (`/events/fetch/progress`)

- Full-page progress display during event fetching
- Shows current step (which source is being fetched)
- Progress bar with count (e.g. "42 / 100")
- Auto-polls every 1 second for updates
- Auto-redirects to events page when complete

---

## Artist Import Progress (`/import/progress`)

- Full-page progress display during Spotify import
- Shows current step (which data source is being pulled)
- Progress bar with count
- Auto-polls every 1 second for updates
- Auto-redirects to artists page when complete
