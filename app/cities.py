"""City configuration for multi-city event scraping."""

CITY_CONFIG = {
    "london": {
        "label": "London",
        "currency": "£",
        "ra_area_code": 13,
        "ticketmaster": {"city": "London", "countryCode": "GB"},
        "dice_city": "london",
        "skiddle": {"lat": 51.5074, "lon": -0.1278, "radius": 15},
        "eventbrite_browse": "https://www.eventbrite.co.uk/d/united-kingdom--london/music--events/",
        "eventbrite_venue_file": "data/eventbrite_venues_london.json",
        "scrapers": ["ra", "dice", "skiddle", "ticketmaster", "eventbrite"],
    },
    "berlin": {
        "label": "Berlin",
        "currency": "€",
        "ra_area_code": 34,
        "ticketmaster": {"city": "Berlin", "countryCode": "DE"},
        "dice_city": None,
        "skiddle": None,
        "eventbrite_browse": "https://www.eventbrite.de/d/germany--berlin/music--events/",
        "eventbrite_venue_file": "data/eventbrite_venues_berlin.json",
        "scrapers": ["ra", "ticketmaster", "eventbrite"],
    },
}

ALL_CITIES = list(CITY_CONFIG.keys())
