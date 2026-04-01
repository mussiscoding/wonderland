from sqlmodel import Session, select

from app.models import (
    Artist,
    ArtistGenre,
    GenreClassification,
    User,
    UserArtist,
    UserGenreClassification,
)

# Multipliers per category
CATEGORY_MULTIPLIERS = {
    "high": 1.0,
    "medium": 0.5,
    "low": 0.1,
    "unclassified": 0.3,
}

# Signal weights exposed for templates and scoring logic
SIGNAL_WEIGHTS = {
    "followed": {"points": 30},
    "saved_tracks": {"per": 7, "cap": 35},
    "intentional_plays": {"per": 5, "cap": 35},
    "playlist_appearances": {"per": 4, "cap": 28},
    "unique_songs": {"per": 2, "cap": 28},
    "top_artist": {
        "short_term": 20,
        "medium_term": 10,
        "long_term": 5,
        "cap": 35,
        "legacy_points": 10,
    },
}


def get_genre_map(session: Session, user_id: int | None = None) -> dict[str, str]:
    """Load genre -> category mapping.

    If user_id is provided, reads from UserGenreClassification.
    Otherwise falls back to global GenreClassification (for migration/seeding).
    """
    if user_id is not None:
        rows = session.exec(
            select(UserGenreClassification).where(
                UserGenreClassification.user_id == user_id
            )
        ).all()
        return {r.genre_name: r.category for r in rows}

    classifications = session.exec(select(GenreClassification)).all()
    return {gc.name: gc.category for gc in classifications}


def genre_multiplier(genres: list[str], genre_map: dict[str, str]) -> float:
    if not genres:
        return 0.3

    # Average the multipliers across all classified genres;
    # fall back to unclassified (0.3) if nothing has been classified yet.
    classified = []
    for genre in genres:
        category = genre_map.get(genre.lower(), "unclassified")
        if category == "unclassified":
            continue
        classified.append(CATEGORY_MULTIPLIERS[category])

    if not classified:
        return 0.3

    return sum(classified) / len(classified)


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


def seed_user_genres(session: Session, user_id: int, replace: bool = False) -> None:
    """Copy genres for a user's artists from their profile template.

    replace=False (default): insert only genres the user doesn't have yet.
    replace=True: delete all user's genre rows and re-seed from template.
      Genres not in the template get set to unclassified.
    """
    # Get the user's artist IDs
    user_artist_ids = session.exec(
        select(UserArtist.artist_id).where(UserArtist.user_id == user_id)
    ).all()
    if not user_artist_ids:
        return

    # Get all genre names for the user's artists
    artist_genres = session.exec(
        select(ArtistGenre.genre_name)
        .where(ArtistGenre.artist_id.in_(user_artist_ids))
        .distinct()
    ).all()
    if not artist_genres:
        return

    # Load the global template
    template = {
        gc.name: gc.category
        for gc in session.exec(select(GenreClassification)).all()
    }

    if replace:
        # Delete all existing user genre rows
        existing = session.exec(
            select(UserGenreClassification).where(
                UserGenreClassification.user_id == user_id
            )
        ).all()
        for row in existing:
            session.delete(row)
        session.flush()

        # Re-seed all genres from template
        for genre_name in artist_genres:
            category = template.get(genre_name, "unclassified")
            session.add(
                UserGenreClassification(
                    user_id=user_id,
                    genre_name=genre_name,
                    category=category,
                    user_modified=False,
                )
            )
    else:
        # Only insert genres the user doesn't have yet
        existing_names = set(
            session.exec(
                select(UserGenreClassification.genre_name).where(
                    UserGenreClassification.user_id == user_id
                )
            ).all()
        )
        for genre_name in artist_genres:
            if genre_name not in existing_names:
                category = template.get(genre_name, "unclassified")
                session.add(
                    UserGenreClassification(
                        user_id=user_id,
                        genre_name=genre_name,
                        category=category,
                        user_modified=False,
                    )
                )

    session.commit()


def rescore_user_artists(session: Session, user_id: int) -> None:
    """Recompute auto_score for all of a user's artists."""
    genre_map = get_genre_map(session, user_id)

    user_artists = session.exec(
        select(UserArtist).where(UserArtist.user_id == user_id)
    ).all()

    artist_ids = [ua.artist_id for ua in user_artists]
    if not artist_ids:
        return

    # Load genres from junction table
    genre_rows = session.exec(
        select(ArtistGenre).where(ArtistGenre.artist_id.in_(artist_ids))
    ).all()
    genres_by_artist: dict[int, list[str]] = {}
    for ag in genre_rows:
        genres_by_artist.setdefault(ag.artist_id, []).append(ag.genre_name)

    for ua in user_artists:
        ua.auto_score = compute_auto_score(
            ua.source_signals or {}, genres_by_artist.get(ua.artist_id, []), genre_map
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
