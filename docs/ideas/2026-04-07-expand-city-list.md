---
date: 2026-04-07
idea: Expand beyond London+Berlin to more UK cities and EU capitals
type: extension
extends: multi-city support
status: idea
---

# Expand City List

Now that the app has a proper `CITY_CONFIG` pattern with London and Berlin, adding more cities is mostly just data — new entries in the config dict with the right scraper params (RA area codes, Ticketmaster city/country, Eventbrite browse URLs). No code changes needed per city, just config.

Could easily add major UK cities (Manchester, Bristol, Leeds, Glasgow) and EU capitals (Amsterdam, Paris, Prague) since RA, Ticketmaster, and Eventbrite all have good coverage there. Dice and Skiddle would stay limited to their supported regions.

## Rough shape
- Add cities to `CITY_CONFIG` — each just needs area codes, API params, currency
- Current UI (dropdown) works fine for 5-10 cities
- At ~15+ cities, the dropdown gets unwieldy — would need a search/typeahead or grouping by country
- Could group by country in the dropdown as a middle step: "UK > London, Manchester, Bristol" / "Germany > Berlin"
- RA area codes would need discovering per city (same GraphQL probe approach used for Berlin)

## RA area code discovery

The `GET_AREAS` query on RA's GraphQL didn't work, but brute-forcing area IDs with the existing `GET_EVENT_LISTINGS` query does. Fetch 1 event for a candidate area ID and check the venue names to identify the city:

```python
# POST https://ra.co/graphql
payload = {
    "operationName": "GET_EVENT_LISTINGS",
    "variables": {
        "filters": {
            "areas": {"eq": AREA_ID},  # try IDs: 34=Berlin, 13=London, etc.
            "listingDate": {"gte": start, "lte": end},
        },
        "filterOptions": {},
        "pageSize": 1,
        "page": 1,
    },
    "query": QUERY,  # same GET_EVENT_LISTINGS query from ra.py
}
```

Known area codes: **13** = London, **34** = Berlin. Other IDs found during probing: 40=Montreal(?), 41=Madrid, 44=Paris, 45=Buenos Aires, 60=Switzerland, 75=Seoul, 80=Philadelphia.

## Open questions
- At what point does the city list need a proper search rather than a dropdown?
- Should cities be grouped by country in the UI?
- Is there a way to bulk-discover RA area codes, or is it one-by-one probing?
- Would users want to select multiple specific cities (not just "all"), or is per-city + all sufficient?
