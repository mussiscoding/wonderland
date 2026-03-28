import logging
import threading
from collections import defaultdict

import spotipy
from sqlmodel import Session, select

from app.models import Artist, GenreClassification
from app.scoring import compute_auto_score, get_genre_map

logger = logging.getLogger(__name__)

# Global import progress tracking
import_progress = {
    "running": False,
    "step": "",
    "current": 0,
    "total": 0,
    "done": False,
}


def import_all_artists(sp: spotipy.Spotify, session: Session) -> dict:
    """Import artists from all Spotify sources and compute auto-scores.

    Returns a summary dict with counts.
    """
    import_progress.update(running=True, step="", current=0, total=0, done=False)

    # Collect signals per artist: spotify_id -> {name, genres, signals}
    artist_data: dict[str, dict] = {}

    # Fetch sources that DON'T include genres first
    import_progress["step"] = "Fetching saved tracks..."
    logger.info("Fetching saved tracks...")
    _fetch_saved_tracks(sp, artist_data)

    import_progress["step"] = "Fetching playlist artists..."
    logger.info("Fetching playlist artists...")
    _fetch_playlist_artists(sp, artist_data)

    import_progress["step"] = "Fetching recently played..."
    logger.info("Fetching recently played...")
    _fetch_recently_played(sp, artist_data)

    # Fetch sources that DO include genres last, so they overwrite empty genres
    import_progress["step"] = "Fetching top artists..."
    logger.info("Fetching top artists...")
    _fetch_top_artists(sp, artist_data)

    import_progress["step"] = "Fetching followed artists..."
    logger.info("Fetching followed artists...")
    _fetch_followed_artists(sp, artist_data)

    # Load all existing artists in one query (not N+1)
    existing_by_sid = {
        a.spotify_id: a for a in session.exec(select(Artist)).all()
    }

    # Preserve genres from DB for artists we already have them for
    for spotify_id, data in artist_data.items():
        if not data["genres"]:
            existing = existing_by_sid.get(spotify_id)
            if existing and existing.genres:
                data["genres"] = existing.genres

    # Backfill genres from MusicBrainz for artists still missing them
    logger.info("Backfilling missing genres...")
    _backfill_genres(sp, artist_data, session, existing_by_sid)

    import_progress["step"] = "Syncing genres and scoring..."

    # Ensure all genres exist in the classification table
    _sync_genre_classifications(session, artist_data)

    # Load genre map for scoring
    genre_map = get_genre_map(session)

    # Upsert into database
    new_count = 0
    updated_count = 0

    for spotify_id, data in artist_data.items():
        existing = existing_by_sid.get(spotify_id)
        genres = data["genres"] or (existing.genres if existing else [])
        auto_score = compute_auto_score(data["signals"], genres, genre_map)

        if existing:
            existing.name = data["name"]
            if data["genres"]:
                existing.genres = data["genres"]
            existing.auto_score = auto_score
            existing.source_signals = data["signals"]
            session.add(existing)
            updated_count += 1
        else:
            artist = Artist(
                spotify_id=spotify_id,
                name=data["name"],
                genres=genres,
                auto_score=auto_score,
                source_signals=data["signals"],
            )
            session.add(artist)
            new_count += 1

    session.commit()

    import_progress.update(running=False, step="Done", done=True)

    summary = {
        "total_artists": len(artist_data),
        "new": new_count,
        "updated": updated_count,
    }
    logger.info(f"Import complete: {summary}")
    return summary


def _sync_genre_classifications(session: Session, artist_data: dict):
    """Add any new genres to the classification table as 'unclassified'."""
    all_genres: set[str] = set()
    for data in artist_data.values():
        for g in data.get("genres", []):
            all_genres.add(g.lower())

    existing = {
        gc.name for gc in session.exec(select(GenreClassification)).all()
    }

    new_genres = all_genres - existing
    if new_genres:
        logger.info(f"  Adding {len(new_genres)} new genres to classification table")
        for genre_name in new_genres:
            session.add(GenreClassification(name=genre_name))
        session.commit()


def _ensure_artist(artist_data: dict, spotify_id: str, name: str, genres: list[str]):
    """Ensure an artist entry exists in our collection dict."""
    if spotify_id not in artist_data:
        artist_data[spotify_id] = {
            "name": name,
            "genres": genres,
            "signals": defaultdict(int),
        }
    # Always prefer non-empty genres
    if genres:
        artist_data[spotify_id]["genres"] = genres


def _backfill_genres(sp: spotipy.Spotify, artist_data: dict, session: Session, existing_by_sid: dict):
    """Fetch genres from MusicBrainz for artists missing them.

    Spotify dev mode (March 2026+) returns empty genres, so we use
    MusicBrainz tags instead. Rate limit: 1 request/sec.
    Genres are committed to the DB incrementally so progress survives restarts.
    """
    import time
    import httpx

    MB_HEADERS = {"User-Agent": "wonderland/0.1 (personal gig finder)"}
    MB_ARTIST = "https://musicbrainz.org/ws/2/artist/"
    MB_URL = "https://musicbrainz.org/ws/2/url/"

    missing = [
        (sid, data) for sid, data in artist_data.items() if not data["genres"]
    ]
    logger.info(f"  {len(missing)} artists missing genres, fetching from MusicBrainz...")

    import_progress.update(step="Fetching genres from MusicBrainz...", current=0, total=len(missing))

    found = 0
    for i, (sid, data) in enumerate(missing):
        import_progress["current"] = i + 1
        name = data["name"]
        try:
            mbid = None

            # Try exact match via Spotify ID first
            spotify_url = f"https://open.spotify.com/artist/{sid}"
            resp = httpx.get(
                MB_URL,
                params={"query": f'url:"{spotify_url}"', "fmt": "json"},
                headers=MB_HEADERS,
                timeout=10,
            )
            url_results = resp.json().get("urls", [])
            if url_results:
                relations = url_results[0].get("relation-list", [])
                for rel_group in relations:
                    for rel in rel_group.get("relations", []):
                        if "artist" in rel:
                            mbid = rel["artist"]["id"]
                            break

            # Fall back to name search
            if not mbid:
                time.sleep(1.1)
                resp = httpx.get(
                    MB_ARTIST,
                    params={"query": f'artist:"{name}"', "fmt": "json", "limit": 1},
                    headers=MB_HEADERS,
                    timeout=10,
                )
                results = resp.json().get("artists", [])
                if results and results[0].get("score", 0) >= 90:
                    mbid = results[0]["id"]

            if mbid:
                # Fetch tags for this artist
                time.sleep(1.1)
                resp2 = httpx.get(
                    f"{MB_ARTIST}{mbid}",
                    params={"inc": "tags", "fmt": "json"},
                    headers=MB_HEADERS,
                    timeout=10,
                )
                tags = resp2.json().get("tags", [])

                top_tags = sorted(tags, key=lambda t: t.get("count", 0), reverse=True)
                genres = [t["name"] for t in top_tags[:6] if t.get("count", 0) > 0]

                if genres:
                    data["genres"] = genres
                    found += 1

                    # Stage DB update for batch commit
                    existing = existing_by_sid.get(sid)
                    if existing:
                        existing.genres = genres
                        session.add(existing)

            # Batch commit every 25 artists
            if (i + 1) % 25 == 0:
                session.commit()

            time.sleep(1.1)  # MusicBrainz rate limit
        except Exception as e:
            logger.warning(f"  MusicBrainz lookup failed for {name}: {e}")
            time.sleep(1.1)

    # Commit any remaining staged updates
    session.commit()

    still_missing = sum(1 for sid, data in missing if not data["genres"])
    logger.info(f"  MusicBrainz backfill: found genres for {found}, still missing: {still_missing}")


def _fetch_top_artists(sp: spotipy.Spotify, artist_data: dict):
    """Fetch top artists across all three time ranges."""
    for time_range in ["short_term", "medium_term", "long_term"]:
        try:
            results = sp.current_user_top_artists(limit=50, time_range=time_range)
            for item in results.get("items", []):
                _ensure_artist(
                    artist_data, item["id"], item["name"], item.get("genres", [])
                )
                artist_data[item["id"]]["signals"]["top_artist"] = True
        except Exception as e:
            logger.warning(f"Failed to fetch top artists ({time_range}): {e}")


def _fetch_followed_artists(sp: spotipy.Spotify, artist_data: dict):
    """Fetch all followed artists (paginated)."""
    try:
        results = sp.current_user_followed_artists(limit=50)
        while results:
            artists = results.get("artists", {})
            for item in artists.get("items", []):
                _ensure_artist(
                    artist_data, item["id"], item["name"], item.get("genres", [])
                )
                artist_data[item["id"]]["signals"]["followed"] = True

            if artists.get("next"):
                after = artists["cursors"]["after"]
                results = sp.current_user_followed_artists(limit=50, after=after)
            else:
                break
    except Exception as e:
        logger.warning(f"Failed to fetch followed artists: {e}")


def _fetch_saved_tracks(sp: spotipy.Spotify, artist_data: dict):
    """Fetch saved/hearted tracks and count per artist."""
    try:
        offset = 0
        while True:
            results = sp.current_user_saved_tracks(limit=50, offset=offset)
            items = results.get("items", [])
            if not items:
                break

            for item in items:
                track = item.get("track", {})
                for artist in track.get("artists", []):
                    _ensure_artist(artist_data, artist["id"], artist["name"], [])
                    artist_data[artist["id"]]["signals"]["saved_tracks"] += 1

            offset += len(items)
            if not results.get("next"):
                break
    except Exception as e:
        logger.warning(f"Failed to fetch saved tracks: {e}")


def _fetch_playlist_artists(sp: spotipy.Spotify, artist_data: dict):
    """Fetch artists from user's own playlists and count playlist appearances.

    Spotify dev mode only allows reading tracks from playlists the user owns,
    so we skip followed/saved playlists from other users.
    """
    try:
        user_id = sp.current_user()["id"]
        playlists = sp.current_user_playlists(limit=50)
        while playlists:
            for playlist in playlists.get("items", []):
                if playlist.get("owner", {}).get("id") != user_id:
                    continue
                _process_playlist(sp, playlist["id"], artist_data)

            if playlists.get("next"):
                playlists = sp.next(playlists)
            else:
                break
    except Exception as e:
        logger.warning(f"Failed to fetch playlists: {e}")


def _process_playlist(sp: spotipy.Spotify, playlist_id: str, artist_data: dict):
    """Process a single playlist, extracting unique artists."""
    seen_in_playlist: set[str] = set()
    try:
        results = sp.playlist_tracks(playlist_id, limit=100)
        track_count = 0
        while results:
            for item in results.get("items", []):
                track = item.get("track") or item.get("item")
                if not track:
                    continue
                track_count += 1
                for artist in track.get("artists", []):
                    artist_id = artist["id"]
                    if artist_id is None:
                        continue
                    _ensure_artist(artist_data, artist_id, artist["name"], [])
                    # Count each playlist only once per artist
                    if artist_id not in seen_in_playlist:
                        artist_data[artist_id]["signals"]["playlist_appearances"] += 1
                        seen_in_playlist.add(artist_id)

            if results.get("next"):
                results = sp.next(results)
            else:
                break
        logger.info(f"    Playlist {playlist_id}: {track_count} tracks, {len(seen_in_playlist)} artists")
    except Exception as e:
        logger.warning(f"Failed to process playlist {playlist_id}: {e}")


def _fetch_recently_played(sp: spotipy.Spotify, artist_data: dict):
    """Fetch recently played tracks, noting intentional listening context."""
    try:
        results = sp.current_user_recently_played(limit=50)
        for item in results.get("items", []):
            track = item.get("track", {})
            context = item.get("context")

            # Check if this was intentional listening (artist or album context)
            is_intentional = False
            if context and context.get("type") in ("artist", "album"):
                is_intentional = True

            for artist in track.get("artists", []):
                _ensure_artist(artist_data, artist["id"], artist["name"], [])
                if is_intentional:
                    artist_data[artist["id"]]["signals"]["intentional_plays"] += 1
    except Exception as e:
        logger.warning(f"Failed to fetch recently played: {e}")
