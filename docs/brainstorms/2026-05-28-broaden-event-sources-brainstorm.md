---
date: 2026-05-28
updated: 2026-05-29
topic: broaden-event-sources
---

# Broadening Event Sources Beyond Dance

## Next steps (actions)

1. **Email Ents24** for API/partner access — `events@ents24.com` (or partner enquiry via ents24.com). Their public API is alive but the self-service developer portal is dead, so contact is the only way in. Ask specifically for a key/credentials for `api.ents24.com`.
2. **Apply to WeGotTickets affiliate program** — contact form at `clients.wegottickets.com/affiliates.php`. In the request, **explicitly ask for a sample feed** so we can confirm it includes structured artist/lineup data before committing.
3. ~~De-dance-ify DICE/Skiddle~~ — **DONE (2026-05-29)**. Skiddle widened to `LIVE,CLUB,FEST`; DICE filter dropped in favour of client-side `music:*` filtering. See `docs/ideas/2026-05-28-de-dance-ify-source-filters.md`. This was the only broadening lever shippable without external access — and it's shipped.

> Both new genre-agnostic sources turned out to be **human-gated** (application/email), not self-service. The shippable broadening lever (de-dance-ify) is now done; remaining gains depend on Ents24 / WeGotTickets access (steps 1–2).

---

## What we're trying to do

The app's five sources (RA, DICE, Skiddle, Eventbrite, Ticketmaster) are tuned for dance — DICE filters `music:dj`, Skiddle filters `eventcode=CLUB`, RA is dance-only by nature. We want to broaden coverage to the app's other genre profiles (Jazz, Rock, Pop, Country).

## Key finding: there's no "RA for jazz/rock/etc." with an API

Research across jazz, rock/metal/folk/country, and general aggregators found one clear pattern: **genre-specific platforms are editorial gig guides** (blogs, prose tour announcements), not scrapable feeds. So you don't broaden by adding "the jazz version of RA" — you broaden by either (a) widening the genre-agnostic sources, or (b) loosening the dance filters on sources you already have.

Genre coverage for guitar/band music (rock, metal, folk, country, punk) is therefore best obtained from **Ticketmaster subgenre filters** (already integrated — it classifies Rock/Metal/Folk/Country/Punk) plus Skiddle, **not** from new per-genre scrapers.

Jazz is the *only* genre with a real dedicated dataset. None have a usable public API (Skiddle, already integrated, is the only one with an open key), so a jazz push would be **scraping work**. Parked unless we want a jazz-specific effort. Sources found, best first:

| Source | Coverage | Access | Notes |
|---|---|---|---|
| **Jazz Near You** (jazznearyou.com, All About Jazz) | Global (343 cities, 36k venues) | Scrape (accepts inbound XML/JSON event feeds; no documented public *read* API) | Largest dedicated jazz dataset anywhere — venue gigs, festivals, jam sessions |
| **Jazz In London** (jazzin.london) | London | Scrape — clean per-venue calendar ("All Venues" page) | Curated, 7-days/week club listings |
| **Jazzwise gig guide** (jazzwise.com) | UK nationwide | Scrape | Authoritative UK-wide jazz gig guide |
| **EFG London Jazz Festival** (efglondonjazzfestival.org.uk) | London festival | Scrape "What's On"/lineup — also syndicated to Skiddle, so may come free via existing source | 10-day festival, hundreds of acts |
| **Venue sites: Ronnie Scott's, Vortex, 606, PizzaExpress Live** | London | Scrape per venue (also appear on Songkick/Bandsintown/RA) | Single-venue, high-quality jazz lineups |
| **UK Jazz News** (ukjazznews.com, ex-London Jazz News) | UK | Scrape (editorial, less structured) | News + curated gig picks |
| **Jazz North / Jazz Promotion Network** (jazznorth.org, jazzpromotionnetwork.org.uk) | UK North / national | Scrape — mostly promoter *directories*, not structured listings | Grassroots/Northern coverage |
| **Jazzfuel** (jazzfuel.com) | Global | Not a data source | Industry/careers resource — use only as a *seed list* of venues/festivals to scrape |

## The aggregator-vs-feeder insight

Aggregators are just unions of upstream feeders. Ents24's coverage comes from three streams:
1. **Ticketing feeders it links to:** Ticketmaster, See Tickets, Ticketweb, WeGotTickets, + smaller independents.
2. **Direct submissions:** promoters/venues/performers via email + their Backstage platform (Backstage sells via a See Tickets partnership).
3. **A human content team** manually adding ~10k listings/week — "every show regardless of who sells tickets."

Mapping Ents24's feeders against what we already hold:

| Ents24 feeder | Our status |
|---|---|
| Ticketmaster | ✅ Integrated |
| Ticketweb | ✅ Covered — owned by Ticketmaster, same Discovery API |
| DICE / Skiddle / Eventbrite | ✅ Integrated (also common UK feeders) |
| See Tickets | ❌ Ruled out — no public API, affiliate-only |
| WeGotTickets | ⏳ Application-gated (investigating) |

**Conclusion: we already hold most of Ents24's feeders.** Going to Ents24 directly would net essentially two new things — **See Tickets** and **WeGotTickets** — both affiliate-gated, same wall as Ents24 itself. Its third stream (human-curated long tail of tiny gigs no ticketing API carries) **can't be replicated programmatically** — that's the unique value Ents24 sells, and it's labour, not a feed.

## Source-by-source status

### Genre-agnostic — viable but gated
- **Ents24** — API alive (`api.ents24.com`, returns 401 = needs key), returns excellent **structured** data: on `event/list` inline you get `artists[]` (id+name), per-stage festival lineups (`stages[].days[].artists[]`), `genre[]`, `venue` with lat/lon, `price`/`tickets[]`. Auth is OAuth2 client credentials. **Blocker:** self-service portal `developers.ents24.com` is **NXDOMAIN** (dead) and the GitHub docs repo was archived April 2026 — no way to get a key except by emailing them. Lineup-data question is *already answered* (structured, excellent); the only thing missing is access + exact `event/list` request param names.
- **WeGotTickets** — site, affiliate portal, and `services.wegottickets.com` feed host all live. Offers free RSS + customisable XML feeds to affiliates (consumed by Songkick, Bandsintown, Ents24, TickX — a real, maintained pipeline). **Blockers:** (1) access is application-gated (contact form → "we'll be in touch"), not self-service; (2) **unconfirmed whether the feed carries structured artist/lineup data** — the affiliate page won't say, sample feeds sit behind sign-up. Also note coverage is **additive/grassroots only** — it lists *only events it sells tickets for*, so it's small/independent UK gigs the majors miss, not a broad firehose.

### Ruled out / dead (don't reconsider)
- **Setlist.fm** — useless for us: historical setlists only, no upcoming events.
- **Songkick** — API closed to new applicants.
- **Last.fm events** — API methods removed.
- **See Tickets** — no public API; affiliate-only.
- **Bandsintown** — keys are per-artist; bulk needs a partnership.
- **Eventful / Festicket / Bandcamp Live / AllGigs / Gigwise / fROOTS** — dead, defunct, or no discovery API.

(Canonical registry: `docs/ideas/done/2026-03-31-event-source-expansion.md`.)

### Not yet checked — smaller UK ticketing feeders worth a DNS/curl test
- **Gigantic, Alttickets, Fatsoma, Gigseekr** — possible *self-serve* feeders. A self-service feeder beats an application-gated aggregator, so these are worth a quick viability pass before committing to the gated routes.

## Process lesson (so we don't repeat it)

Verify API access against **live DNS, not search results**. Search engines and research agents serve *cached* docs and will happily describe a developer portal that no longer resolves — exactly how Ents24 burned a research cycle. Before recommending/planning any source: `nslookup` the developer-portal host, curl it, and check the live main site for a developer link. 401 from the API base = "alive, needs key"; NXDOMAIN on the portal = "you can't get a key."

## If/when access lands — Ents24 integration notes

- New `app/scrapers/ents24.py` with `fetch_events(city_config)`; city params in `app/cities.py`; register in `app/events.py` `_SCRAPERS`. Pipeline handles dedup/matching/storage.
- Auth: OAuth2 client credentials → access token. New env vars e.g. `ENTS24_CLIENT_ID` / `ENTS24_CLIENT_SECRET`.
- `event/list` carries everything inline (artists, genre, venue, price) — **no N+1 per-event fetches** needed, unlike Eventbrite.
- Filter to `parentKey=Music` (from `event/genres`) to drop comedy/theatre/sport noise.
- Genre strategy: pull broadly and let existing fuzzy-matching + genre scoring filter downstream (same as other sources) — don't couple the scraper to profile state.
- Remaining unknown: exact `event/list` request param names for location/distance/genre/date (the response shapes are known from the archived schemas; the request schema wasn't published).
