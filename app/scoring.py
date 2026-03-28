from sqlmodel import Session, select

from app.models import GenreClassification

# Multipliers per category
CATEGORY_MULTIPLIERS = {
    "dance": 1.0,
    "adjacent": 0.5,
    "other": 0.1,
    "unclassified": 0.3,
}


def get_genre_map(session: Session) -> dict[str, str]:
    """Load genre -> category mapping from DB."""
    classifications = session.exec(select(GenreClassification)).all()
    return {gc.name: gc.category for gc in classifications}


def genre_multiplier(genres: list[str], genre_map: dict[str, str]) -> float:
    if not genres:
        return 0.3

    # Pick the best multiplier from classified genres only;
    # fall back to unclassified (0.3) if nothing has been classified yet.
    best_classified = None
    for genre in genres:
        category = genre_map.get(genre.lower(), "unclassified")
        if category == "unclassified":
            continue
        multiplier = CATEGORY_MULTIPLIERS[category]
        if best_classified is None or multiplier > best_classified:
            best_classified = multiplier

    return best_classified if best_classified is not None else 0.3


def compute_auto_score(source_signals: dict, genres: list[str], genre_map: dict[str, str]) -> float:
    signal_score = 0.0

    if source_signals.get("followed"):
        signal_score += 30

    saved_count = source_signals.get("saved_tracks", 0)
    signal_score += min(saved_count * 5, 25)

    intentional_count = source_signals.get("intentional_plays", 0)
    signal_score += min(intentional_count * 3, 20)

    playlist_count = source_signals.get("playlist_appearances", 0)
    signal_score += min(playlist_count * 2, 15)

    if source_signals.get("top_artist"):
        signal_score += 10

    multiplier = genre_multiplier(genres, genre_map)
    score = multiplier * signal_score

    return min(round(score, 1), 100.0)


def compute_event_score(matched_artists: list[tuple[float, float]]) -> float:
    """Compute an event score from matched artists.

    matched_artists: list of (artist_effective_score, match_confidence)
    """
    if not matched_artists:
        return 0.0

    # Sum effective scores, weighted by match confidence
    total = sum(score * (conf / 100.0) for score, conf in matched_artists)

    # Bonus for multi-artist lineups: +20 per additional match beyond the first
    if len(matched_artists) > 1:
        total += 20 * (len(matched_artists) - 1)

    return min(round(total, 1), 100.0)
