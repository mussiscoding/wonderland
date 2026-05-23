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
- Columns: Date, Event, Venue, Lineup, Price (desktop only), Links
- **Date header**: clickable, toggles between ascending (earliest first, ▲) and descending (▼)
- **Date**: formatted as "Mon 01 Jan"
- **Lineup**: all artists as pills — matched artists highlighted in green (sorted first), others in grey. Capped at 6 with "+N" overflow. Matched artist pills link to `/artist/{id}` (same styling as non-linked pills).
- **Price**: cheapest price from sources, or dash if none. Hidden on mobile.
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
- **Clear all classifications button**: sets all genre classifications to unclassified. Requires confirmation dialog. Positioned right-aligned in controls bar.

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
