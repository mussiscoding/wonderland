import logging
import re

from rapidfuzz import fuzz
from sqlmodel import Session, select

from app.models import Artist, Event, Match

logger = logging.getLogger(__name__)

FUZZY_THRESHOLD = 75

# Suffixes to strip when normalising artist names
STRIP_SUFFIXES = [
    r"\(live\)", r"\(dj set\)", r"\(dj\)", r"\(hybrid\)",
    r"& friends", r"all night long", r"all night",
    r"\(vinyl\)", r"\(b2b\)",
]

# Names to ignore in lineups
IGNORE_NAMES = {
    "residents", "tba", "tbc", "tbd", "special guest",
    "special guests", "more tba", "support tba", "guests",
    "and more", "plus more", "plus guests", "plus special guests",
}


def normalise_name(name: str) -> str:
    """Normalise an artist name for matching."""
    s = name.lower().strip()

    # Strip common suffixes
    for suffix in STRIP_SUFFIXES:
        s = re.sub(suffix, "", s, flags=re.IGNORECASE).strip()

    # Remove "DJ " / "MC " prefix
    s = re.sub(r"^(dj|mc)\s+", "", s, flags=re.IGNORECASE)

    # Strip punctuation except & (important for e.g. "Chase & Status")
    s = re.sub(r"[^\w\s&]", "", s)

    # Collapse whitespace
    s = re.sub(r"\s+", " ", s).strip()

    return s


def parse_lineup(lineup_raw: str) -> list[str]:
    """Parse a raw lineup string into individual artist names."""
    if not lineup_raw:
        return []

    # Remove room/stage prefixes like "Room 1:" or "Main Stage:"
    text = re.sub(r"(room|stage|floor|arena)\s*\d*\s*:", "", lineup_raw, flags=re.IGNORECASE)

    # Split on common delimiters
    parts = re.split(r"[,;\|\n]|(?:\s/\s)", text)

    # Handle "b2b" as a separator -> keep both artists
    expanded = []
    for part in parts:
        if re.search(r"\bb2b\b", part, re.IGNORECASE):
            expanded.extend(re.split(r"\s+b2b\s+", part, flags=re.IGNORECASE))
        else:
            expanded.append(part)

    # Clean up and filter
    names = []
    for name in expanded:
        name = name.strip()
        if not name:
            continue
        # Handle "presents:" — take the artist before "presents"
        if "presents" in name.lower():
            before = name.lower().split("presents")[0].strip()
            if before:
                name = before

        normalised = normalise_name(name)
        if normalised and normalised not in IGNORE_NAMES and len(normalised) > 1:
            names.append(name.strip())

    return names


def run_matching(session: Session) -> dict:
    """Match artists to event lineups and create Match records.

    Returns a summary dict.
    """
    # Clear existing matches for a clean re-run
    existing_matches = session.exec(select(Match)).all()
    for m in existing_matches:
        session.delete(m)
    session.flush()

    # Load all non-excluded artists
    artists = session.exec(select(Artist)).all()
    artist_lookup: dict[str, Artist] = {}  # normalised_name -> Artist
    for a in artists:
        if a.excluded:
            continue
        norm = normalise_name(a.name)
        artist_lookup[norm] = a

    events = session.exec(select(Event)).all()

    total_matches = 0
    events_with_matches = 0

    for event in events:
        lineup_names = event.lineup_parsed or []
        if not lineup_names:
            # Try parsing from raw if parsed is empty
            lineup_names = parse_lineup(event.lineup_raw)
            if lineup_names and not event.lineup_parsed:
                event.lineup_parsed = lineup_names
                session.add(event)

        event_matched = False

        for lineup_name in lineup_names:
            norm_lineup = normalise_name(lineup_name)
            if not norm_lineup or norm_lineup in IGNORE_NAMES:
                continue

            # Try exact match first (fast path)
            artist = artist_lookup.get(norm_lineup)
            if artist:
                _add_match(session, artist, event, 100.0, "exact", lineup_name)
                total_matches += 1
                event_matched = True
                continue

            # Fuzzy match
            best_score = 0
            best_artist = None
            for norm_name, candidate in artist_lookup.items():
                score = fuzz.token_set_ratio(norm_lineup, norm_name)
                if score > best_score:
                    best_score = score
                    best_artist = candidate

            if best_score >= FUZZY_THRESHOLD and best_artist:
                _add_match(session, best_artist, event, best_score, "fuzzy", lineup_name)
                total_matches += 1
                event_matched = True

        if event_matched:
            events_with_matches += 1

    session.commit()

    summary = {
        "total_events": len(events),
        "events_with_matches": events_with_matches,
        "total_matches": total_matches,
    }
    logger.info(f"Matching complete: {summary}")
    return summary


def _add_match(
    session: Session,
    artist: Artist,
    event: Event,
    confidence: float,
    match_type: str,
    matched_name: str,
):
    match = Match(
        artist_id=artist.id,
        event_id=event.id,
        confidence=confidence,
        match_type=match_type,
        matched_name=matched_name,
    )
    session.add(match)
