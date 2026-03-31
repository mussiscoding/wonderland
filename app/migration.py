"""One-time migration from single-user Artist scores to multi-user UserArtist records."""

import json
import logging
import os

from sqlmodel import Session, SQLModel, select, text

from app.database import engine
from app.models import User, UserArtist, ArtistGenre  # noqa: F401 - registers models
import app.models  # noqa: F401

logger = logging.getLogger(__name__)


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
