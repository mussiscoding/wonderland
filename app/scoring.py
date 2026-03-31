from sqlmodel import Session, select

from app.models import Artist, GenreClassification, User, UserArtist

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
    signal_score += min(saved_count * 7, 35)

    intentional_count = source_signals.get("intentional_plays", 0)
    signal_score += min(intentional_count * 5, 35)

    playlist_count = source_signals.get("playlist_appearances", 0)
    signal_score += min(playlist_count * 4, 28)

    unique_songs = source_signals.get("unique_songs", 0)
    signal_score += min(unique_songs * 2, 28)

    top_artist_points = {"short_term": 20, "medium_term": 10, "long_term": 5}
    top_artist_ranges = source_signals.get("top_artist", [])
    # Support legacy boolean format
    if top_artist_ranges is True:
        signal_score += 10
    else:
        signal_score += min(sum(top_artist_points.get(r, 0) for r in top_artist_ranges), 35)

    multiplier = genre_multiplier(genres, genre_map)
    score = multiplier * signal_score

    return min(round(score, 1), 100.0)


def rescore_user_artists(session: Session, user_id: int) -> None:
    """Recompute auto_score for all of a user's artists."""
    genre_map = get_genre_map(session)

    user_artists = session.exec(
        select(UserArtist).where(UserArtist.user_id == user_id)
    ).all()

    artist_ids = [ua.artist_id for ua in user_artists]
    if not artist_ids:
        return

    artists_by_id = {
        a.id: a for a in session.exec(
            select(Artist).where(Artist.id.in_(artist_ids))
        ).all()
    }

    for ua in user_artists:
        artist = artists_by_id.get(ua.artist_id)
        if not artist:
            continue
        ua.auto_score = compute_auto_score(
            ua.source_signals or {}, artist.genres or [], genre_map
        )
        session.add(ua)

    session.commit()


def rescore_all_users(session: Session) -> None:
    """Rescore all users' artists. Used when genre classifications change."""
    users = session.exec(select(User)).all()
    for user in users:
        rescore_user_artists(session, user.id)


def compute_event_score(matched_artists: list[tuple[float, float]]) -> float:
    """Compute an event score from matched artists.

    matched_artists: list of (artist_effective_score, match_confidence)
    """
    if not matched_artists:
        return 0.0

    # Sum effective scores, weighted by match confidence
    total = sum(score * (conf / 100.0) for score, conf in matched_artists)

    return min(round(total, 1), 100.0)
