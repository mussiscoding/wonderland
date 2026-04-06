"""Database migrations. Runs on startup, detects what's needed."""

import json
import logging
import os
import shutil
from datetime import datetime
from pathlib import Path

from sqlmodel import Session, SQLModel, select, text

from app.database import engine
from app.models import User, UserArtist, ArtistGenre, UserGenreClassification  # noqa: F401 - registers models
import app.models  # noqa: F401

logger = logging.getLogger(__name__)

# Old category names → new category names
_CATEGORY_REMAP = {
    "dance": "high",
    "adjacent": "medium",
    "other": "low",
}


def run_migration():
    """Detect old schema and migrate if needed."""
    with Session(engine) as session:
        # Check if Artist table still has the old auto_score column
        try:
            result = session.exec(
                text("SELECT auto_score FROM artist LIMIT 1")
            )
            result.all()
        except Exception:
            # Column doesn't exist — already migrated or fresh DB
            pass
        else:
            logger.info("Detected old single-user schema. Running migration...")
            _migrate_to_multi_user(session)

        # Populate ArtistGenre junction table from Artist.genres JSON
        _migrate_genres_to_junction_table(session)

        # Add genre_profile column to User if missing
        _add_genre_profile_column(session)

        # Migrate genre categories and seed per-user genre classifications
        _migrate_genre_categories(session)
        _seed_user_genre_classifications(session)

        # Multi-city: backfill venue_location and recompute dedupe keys
        _migrate_dedupe_keys_for_city(session)

    # Rename old eventbrite venues file
    _rename_eventbrite_venue_file()


def _migrate_to_multi_user(session: Session):
    """Copy Artist score data to UserArtist records, then drop old columns."""
    try:
        # Ensure new tables exist before migrating data into them
        SQLModel.metadata.create_all(engine)

        # Create placeholder user
        user = session.exec(
            select(User).where(User.spotify_id == "original-user")
        ).first()

        if not user:
            user = User(spotify_id="original-user", display_name="Original User")
            session.add(user)
            session.commit()
            session.refresh(user)

        # Read old artist data and create UserArtist records
        rows = session.exec(
            text(
                "SELECT id, auto_score, manual_score, excluded, source_signals "
                "FROM artist "
                "WHERE auto_score > 0 OR manual_score IS NOT NULL OR excluded = 1"
            )
        ).all()

        for row in rows:
            artist_id, auto_score, manual_score, excluded, source_signals_raw = row

            # Parse source_signals JSON
            source_signals = {}
            if source_signals_raw:
                try:
                    source_signals = json.loads(source_signals_raw) if isinstance(source_signals_raw, str) else source_signals_raw
                except (json.JSONDecodeError, TypeError):
                    pass

            # Check if UserArtist already exists
            existing = session.exec(
                select(UserArtist).where(
                    UserArtist.user_id == user.id,
                    UserArtist.artist_id == artist_id,
                )
            ).first()

            if not existing:
                ua = UserArtist(
                    user_id=user.id,
                    artist_id=artist_id,
                    auto_score=auto_score or 0.0,
                    manual_score=manual_score,
                    excluded=bool(excluded),
                    source_signals=source_signals,
                )
                session.add(ua)

        session.commit()

        # Drop old columns from Artist
        for col in ("auto_score", "manual_score", "excluded", "source_signals"):
            try:
                session.exec(text(f"ALTER TABLE artist DROP COLUMN {col}"))
            except Exception as e:
                logger.warning(f"Could not drop column {col}: {e}")

        session.commit()

        # Clean up old cache file
        cache_path = "data/.spotify_cache"
        if os.path.exists(cache_path):
            os.remove(cache_path)
            logger.info("Removed old .spotify_cache file")

        migrated_count = len(rows)
        logger.info(f"Migration complete: {migrated_count} artist scores moved to UserArtist")

    except Exception as e:
        logger.error(f"Migration failed: {e}. You may need to delete data/wonderland.db and re-import.")
        raise


def _migrate_genres_to_junction_table(session: Session):
    """Populate ArtistGenre from Artist.genres JSON if the table is empty."""
    # Skip if already populated
    existing = session.exec(text("SELECT COUNT(*) FROM artistgenre")).one()
    if existing[0] > 0:
        return

    # Check if the old genres column still exists
    try:
        session.exec(text("SELECT genres FROM artist LIMIT 1")).all()
    except Exception:
        # Column already dropped — nothing to migrate
        return

    rows = session.exec(text("SELECT id, genres FROM artist WHERE genres IS NOT NULL")).all()
    if not rows:
        return

    logger.info("Populating ArtistGenre junction table from Artist.genres JSON...")
    count = 0
    for artist_id, genres_raw in rows:
        genres = json.loads(genres_raw) if isinstance(genres_raw, str) else genres_raw
        if not genres:
            continue
        for genre in genres:
            genre_lower = genre.lower()
            session.add(ArtistGenre(artist_id=artist_id, genre_name=genre_lower))
            count += 1

    session.commit()
    logger.info(f"  Migrated {count} artist-genre associations")

    # Drop the old column now that data is migrated
    try:
        session.exec(text("ALTER TABLE artist DROP COLUMN genres"))
        session.commit()
        logger.info("  Dropped Artist.genres column")
    except Exception:
        pass


def _add_genre_profile_column(session: Session):
    """Add genre_profile column to User table if it doesn't exist."""
    try:
        session.exec(text("SELECT genre_profile FROM user LIMIT 1")).all()
    except Exception:
        logger.info("Adding genre_profile column to User table...")
        session.exec(text("ALTER TABLE user ADD COLUMN genre_profile VARCHAR DEFAULT 'dance'"))
        session.commit()


def _migrate_genre_categories(session: Session):
    """Remap GenreClassification categories: dance→high, adjacent→medium, other→low."""
    from app.models import GenreClassification

    # Check if any rows still use old category names
    old_rows = session.exec(
        select(GenreClassification).where(
            GenreClassification.category.in_(["dance", "adjacent", "other"])
        )
    ).all()
    if not old_rows:
        return

    logger.info(f"Remapping {len(old_rows)} genre classifications to new category names...")
    for gc in old_rows:
        gc.category = _CATEGORY_REMAP.get(gc.category, gc.category)
        session.add(gc)
    session.commit()
    logger.info("  Genre category remap complete")


def _seed_user_genre_classifications(session: Session):
    """Seed UserGenreClassification for existing users who don't have any rows yet."""
    from app.scoring import seed_user_genres

    # Check if table exists and has any rows already
    try:
        existing_count = session.exec(
            text("SELECT COUNT(*) FROM usergenreclassification")
        ).one()
        if existing_count[0] > 0:
            return
    except Exception:
        # Table doesn't exist yet — will be created by create_all
        return

    users = session.exec(select(User)).all()
    if not users:
        return

    logger.info(f"Seeding UserGenreClassification for {len(users)} existing users...")
    for user in users:
        seed_user_genres(session, user.id)
    logger.info("  User genre seeding complete")


def _migrate_dedupe_keys_for_city(session: Session):
    """Backfill venue_location and recompute dedupe keys to include city."""
    from app.events import _dedupe_key

    # Early exit: check if any keys still use old format (no city component)
    # Old format has exactly one underscore: "venuename_2026-01-01"
    # New format has two: "venuename_london_2026-01-01"
    sample = session.exec(
        text("SELECT dedupe_key FROM event WHERE dedupe_key NOT LIKE '%_%_%' LIMIT 1")
    ).first()
    if sample is None:
        # Also check for NULL venue_location
        null_location = session.exec(
            text("SELECT id FROM event WHERE venue_location IS NULL LIMIT 1")
        ).first()
        if null_location is None:
            return

    rows = session.exec(text("SELECT id, venue_name, venue_location, date, dedupe_key FROM event")).all()
    if not rows:
        return

    migrated = 0
    for row_id, venue_name, venue_location, date_val, old_key in rows:
        location = venue_location or "London"

        # Parse date from SQLite string if needed
        if isinstance(date_val, str):
            dt = datetime.strptime(date_val[:19], "%Y-%m-%dT%H:%M:%S" if "T" in date_val else "%Y-%m-%d")
        else:
            dt = date_val

        new_key = _dedupe_key(venue_name, dt, location)

        if old_key != new_key or venue_location is None:
            session.exec(
                text("UPDATE event SET dedupe_key = :new_key, venue_location = :location WHERE id = :id"),
                params={"new_key": new_key, "location": location, "id": row_id},
            )
            migrated += 1

    if migrated > 0:
        session.commit()
        logger.info(f"  Migrated {migrated} event dedupe keys to include city")


def _rename_eventbrite_venue_file():
    """Rename old eventbrite_venues.json to city-specific name."""
    old_path = Path("data/eventbrite_venues.json")
    new_path = Path("data/eventbrite_venues_london.json")
    if old_path.exists() and not new_path.exists():
        shutil.move(str(old_path), str(new_path))
        logger.info("  Renamed eventbrite_venues.json → eventbrite_venues_london.json")
