# Mobile Responsive

**Date:** 2026-05-22
**Status:** Ready to build

## Problem

The app is desktop-only. On mobile (375–430px):
- Everything overflows horizontally — container has no mobile awareness
- Nav bar wraps badly — 4 links + user area all crammed in one row
- Tables overflow — too many columns, fixed widths
- Controls (search + buttons) don't stack

## Changes by area

### 1. Nav — hamburger menu (`base.html`)

Replace the always-visible nav bar with a hamburger button (top-left corner, floating). Tapping it opens an overlay panel from the left side (like image 4 — the red box), covering ~70% of the screen width. Overlay contains:
- All nav links: Artists, Events, Genres, Admin
- User area: display name, Switch, Log out

On desktop (>600px), nav stays as-is — no hamburger, normal horizontal bar.

The hamburger button is always visible on mobile so you can navigate from any page.

### 2. Artists page layout (`artists.html`)

Mobile layout top to bottom:
1. Hamburger button + "wonderland" title (same line)
2. Search bar (full width)
3. Artist table: Score, Artist, Genres (3 columns — Signals already removed)

User area (name, Switch, Log out, Re-import) lives in the nav overlay on mobile — not on the page itself.

Genre tags: keep 2-row max (same as desktop).

### 3. Artist detail (`artist_detail.html`)

- Keep current layout (table works fine at 3 cols without Signals on mobile)
- Events table stays between artist info and Spotify embed (already the case in template order — events come before the embed)
- Score modal: already 280px, fits mobile

### 4. Events page (`events.html`) — biggest change

**Drop columns (desktop AND mobile):**
- Remove Score column
- Remove Matched Artists column (redundant — matched artists already highlighted in Lineup)

**Hide on mobile only:**
- Price column (keep on desktop, hide via CSS on mobile)

**Final columns: Date, Event, Venue, Lineup, Price (desktop only), Links**

Lineup column already shows matched artists as green pills and others as grey pills. This is the only place you see who matched, so it stays.

Links column stays for now — gives direct access to RA/Dice/Skiddle. Future: event detail pages could replace this.

Controls on mobile: search full-width, city/dates stack below.

### 5. Genres (`genres.html`)

- Probably fine as-is — 4 narrow columns (Genre, Artists, Category, H/M/L buttons)
- Will revisit after global CSS fixes if it still looks bad

### 6. Genre detail (`genre_detail.html`)

- 3 columns (Score, Artist, Genres) — same as artists table, benefits from same global fixes

### 7. Admin, progress pages, choose-profile, request-access

- All simple/centered layouts — just need global container padding fix (20px → 12px)

## Implementation order

1. **Events page column cleanup** — remove Score, Matched Artists, Price (template change, desktop+mobile)
2. **Global mobile CSS** in `base.html` — container padding, controls stacking, table cell padding
3. **Hamburger nav** — new markup + CSS + JS in `base.html`
4. **Artists page** — mobile layout ordering (title row, user row, search row)
5. Test on actual phone, iterate

## Not doing yet

- Event detail pages (future — would allow removing Links column too)
- Any backend changes
