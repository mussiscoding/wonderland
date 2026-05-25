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


def user_has_genres(session: Session, user_id: int) -> bool:
    """Check if a user has any genre classifications yet."""
    return session.exec(
        select(UserGenreClassification.id).where(
            UserGenreClassification.user_id == user_id
        ).limit(1)
    ).first() is not None


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

    classifications = session.exec(
        select(GenreClassification).where(
            GenreClassification.profile_name == "dance"
        )
    ).all()
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


def score_breakdown(source_signals: dict, genres: list[str], genre_map: dict[str, str]) -> dict:
    """Build a breakdown of score components for display.

    Returns {rows: [{pts, label}], mult: float, score: int}.
    """
    w = SIGNAL_WEIGHTS
    rows = []

    if source_signals.get("followed"):
        rows.append({"pts": w["followed"]["points"], "label": "followed"})

    saved = source_signals.get("saved_tracks", 0)
    if saved:
        pts = min(saved * w["saved_tracks"]["per"], w["saved_tracks"]["cap"])
        rows.append({"pts": pts, "label": f"{saved} saved"})

    intentional = source_signals.get("intentional_plays", 0)
    if intentional:
        pts = min(intentional * w["intentional_plays"]["per"], w["intentional_plays"]["cap"])
        rows.append({"pts": pts, "label": f"{intentional} active play{'s' if intentional != 1 else ''}"})

    playlists = source_signals.get("playlist_appearances", 0)
    if playlists:
        pts = min(playlists * w["playlist_appearances"]["per"], w["playlist_appearances"]["cap"])
        rows.append({"pts": pts, "label": f"{playlists} playlist{'s' if playlists != 1 else ''}"})

    unique = source_signals.get("unique_songs", 0)
    if unique:
        pts = min(unique * w["unique_songs"]["per"], w["unique_songs"]["cap"])
        rows.append({"pts": pts, "label": f"{unique} track{'s' if unique != 1 else ''} in library"})

    top_artist_ranges = source_signals.get("top_artist", [])
    if top_artist_ranges is True:
        rows.append({"pts": w["top_artist"]["legacy_points"], "label": "top artist"})
    elif top_artist_ranges:
        pts = min(
            sum(w["top_artist"].get(r, 0) for r in top_artist_ranges),
            w["top_artist"]["cap"],
        )
        if pts:
            rows.append({"pts": pts, "label": "top artist"})

    signal_total = sum(r["pts"] for r in rows)
    mult = round(genre_multiplier(genres, genre_map), 2)
    score = min(round(mult * signal_total), 100)

    return {"rows": rows, "mult": mult, "score": score}


def compute_auto_score(source_signals: dict, genres: list[str], genre_map: dict[str, str]) -> float:
    bd = score_breakdown(source_signals, genres, genre_map)
    return min(round(bd["mult"] * sum(r["pts"] for r in bd["rows"]), 1), 100.0)


def seed_user_genres(session: Session, user_id: int, profile_name: str = "dance") -> None:
    """Seed UserGenreClassification for a user's artists from a profile template.

    Only inserts genres the user doesn't have yet. For "none", all new genres
    are seeded as unclassified.
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

    # Load template for the chosen profile
    if profile_name == "none":
        template = {}
    else:
        template = {
            gc.name: gc.category
            for gc in session.exec(
                select(GenreClassification).where(
                    GenreClassification.profile_name == profile_name
                )
            ).all()
        }

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
