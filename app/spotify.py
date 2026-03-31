import logging
import os
import time
from collections import defaultdict

import httpx
import spotipy
from sqlmodel import Session, select

from app.models import Artist, GenreClassification, UserArtist
from app.scoring import compute_auto_score, get_genre_map, rescore_user_artists

logger = logging.getLogger(__name__)

MB_HEADERS = {"User-Agent": "wonderland/0.1 (personal gig finder)"}
MB_ARTIST = "https://musicbrainz.org/ws/2/artist/"
MB_URL = "https://musicbrainz.org/ws/2/url/"

LASTFM_API_KEY = os.getenv("LAST_FM_API_KEY")
LASTFM_API_URL = "https://ws.audioscrobbler.com/2.0/"

# Per-user import progress tracking: user_id -> progress dict
import_progress: dict[int, dict] = {}


def _get_progress(user_id: int) -> dict:
    """Get or create progress dict for a user."""
    if user_id not in import_progress:
        import_progress[user_id] = {
            "running": False,
            "step": "",
            "current": 0,
            "total": 0,
            "done": False,
        }
    return import_progress[user_id]


def import_all_artists(sp: spotipy.Spotify, session: Session, user_id: int) -> dict:
    """Import artists from all Spotify sources and compute auto-scores.

    Writes to the shared Artist catalog and per-user UserArtist records.
    Returns a summary dict with counts.
    """
    progress = _get_progress(user_id)
    progress.update(running=True, step="", current=0, total=0, done=False)

    # Collect signals per artist: spotify_id -> {name, genres, signals}
    artist_data: dict[str, dict] = {}

    # Fetch sources that DON'T include genres first
    progress["step"] = "Fetching saved tracks..."
    logger.info("Fetching saved tracks...")
    _fetch_saved_tracks(sp, artist_data)

    progress["step"] = "Fetching playlist artists..."
    logger.info("Fetching playlist artists...")
    _fetch_playlist_artists(sp, artist_data)

    progress["step"] = "Fetching recently played..."
    logger.info("Fetching recently played...")
    _fetch_recently_played(sp, artist_data)

    # Fetch sources that DO include genres last, so they overwrite empty genres
    progress["step"] = "Fetching top artists..."
    logger.info("Fetching top artists...")
    _fetch_top_artists(sp, artist_data)

    progress["step"] = "Fetching followed artists..."
    logger.info("Fetching followed artists...")
    _fetch_followed_artists(sp, artist_data)

    # Upsert shared Artist catalog (name, spotify_id, genres only)
    existing_by_sid = {
        a.spotify_id: a for a in session.exec(select(Artist)).all()
    }

    new_count = 0
    updated_count = 0

    for spotify_id, data in artist_data.items():
        existing = existing_by_sid.get(spotify_id)
        if existing:
            existing.name = data["name"]
            if data["genres"]:
                existing.genres = data["genres"]
            session.add(existing)
            updated_count += 1
        else:
            artist = Artist(
                spotify_id=spotify_id,
                name=data["name"],
                genres=data["genres"],
            )
            session.add(artist)
            new_count += 1

    session.commit()

    # Reload to get IDs for newly inserted artists
    existing_by_sid = {
        a.spotify_id: a for a in session.exec(select(Artist)).all()
    }

    # Preserve genres from DB for artists we already have them for
    for spotify_id, data in artist_data.items():
        if not data["genres"]:
            existing = existing_by_sid.get(spotify_id)
            if existing and existing.genres:
                data["genres"] = existing.genres

    # Create/update UserArtist records NOW (before slow genre backfill)
    # so the user can see their artists immediately with initial scores.
    progress["step"] = "Scoring artists..."
    _upsert_user_artists(session, user_id, artist_data, existing_by_sid)

    # Backfill genres from MusicBrainz for artists still missing them
    # (slow — but artists are already visible to the user above)
    logger.info("Backfilling missing genres...")
    _backfill_genres(sp, artist_data, session, existing_by_sid, progress)

    # Ensure all genres exist in the classification table
    _sync_genre_classifications(session, artist_data)

    # Final rescore using DB genres + existing classifications
    progress["step"] = "Rescoring with genres..."
    rescore_user_artists(session, user_id)

    progress.update(running=False, step="Done", done=True)

    summary = {
        "total_artists": len(artist_data),
        "new": new_count,
        "updated": updated_count,
    }
    logger.info(f"Import complete: {summary}")
    return summary


def _upsert_user_artists(
    session: Session,
    user_id: int,
    artist_data: dict,
    existing_by_sid: dict,
) -> None:
    """Create or update UserArtist records with current scores."""
    genre_map = get_genre_map(session)
    existing_ua = {
        ua.artist_id: ua for ua in session.exec(
            select(UserArtist).where(UserArtist.user_id == user_id)
        ).all()
    }

    for spotify_id, data in artist_data.items():
        artist = existing_by_sid.get(spotify_id)
        if not artist:
            continue
        genres = data["genres"] or artist.genres or []
        auto_score = compute_auto_score(data["signals"], genres, genre_map)

        ua = existing_ua.get(artist.id)
        if ua:
            ua.source_signals = dict(data["signals"])
            ua.auto_score = auto_score
            session.add(ua)
        else:
            ua = UserArtist(
                user_id=user_id,
                artist_id=artist.id,
                source_signals=dict(data["signals"]),
                auto_score=auto_score,
            )
            session.add(ua)

    session.commit()


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


def _backfill_genres(
    sp: spotipy.Spotify,
    artist_data: dict,
    session: Session,
    existing_by_sid: dict,
    progress: dict,
):
    """Fetch genres from MusicBrainz for artists missing them.

    Only backfills artists that don't already have genres in the shared catalog.
    """
    missing = [
        (sid, data) for sid, data in artist_data.items() if not data["genres"]
    ]
    # Fetch genres in order of signal strength so the most important
    # artists are backfilled first (useful when the process is interrupted).
    missing.sort(
        key=lambda pair: compute_auto_score(pair[1]["signals"], [], {}),
        reverse=True,
    )
    logger.info(f"  {len(missing)} artists missing genres, fetching from MusicBrainz...")

    progress.update(step="Fetching genres from MusicBrainz...", current=0, total=len(missing))

    found = 0
    for i, (sid, data) in enumerate(missing):
        progress["current"] = i + 1
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

                    # Update shared Artist catalog
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

    # Second pass: Last.fm for artists MusicBrainz missed
    if still_missing > 0 and LASTFM_API_KEY:
        _backfill_genres_lastfm(
            [sid for sid, data in missing if not data["genres"]],
            artist_data, session, existing_by_sid, progress,
        )


def backfill_lastfm(session: Session, user_id: int):
    """Standalone Last.fm genre backfill for artists with no genres."""
    if not LASTFM_API_KEY:
        logger.warning("LAST_FM_API_KEY not set, skipping Last.fm backfill")
        return

    progress = _get_progress(user_id)

    # Find artists that this user has imported but that lack genres
    user_artists = session.exec(
        select(UserArtist).where(UserArtist.user_id == user_id)
    ).all()
    artist_ids = [ua.artist_id for ua in user_artists]
    if not artist_ids:
        progress.update(running=False, step="No artists to backfill", done=True)
        return

    artists = session.exec(
        select(Artist).where(Artist.id.in_(artist_ids))
    ).all()
    missing = [a for a in artists if not a.genres]

    if not missing:
        logger.info("No artists missing genres.")
        progress.update(running=False, step="No artists missing genres", done=True)
        return

    # Build artist_data dict and existing_by_sid for reuse
    ua_by_artist_id = {ua.artist_id: ua for ua in user_artists}
    artist_data = {
        a.spotify_id: {
            "name": a.name,
            "genres": [],
            "signals": ua_by_artist_id.get(a.id, UserArtist()).source_signals or {},
        }
        for a in missing
    }
    existing_by_sid = {a.spotify_id: a for a in missing}

    progress.update(running=True, step="", current=0, total=0, done=False)
    _backfill_genres_lastfm(
        [a.spotify_id for a in missing],
        artist_data, session, existing_by_sid, progress,
    )

    # Sync any new genres into classification table and rescore
    _sync_genre_classifications(session, {sid: d for sid, d in artist_data.items() if d["genres"]})
    genre_map = get_genre_map(session)

    for sid, data in artist_data.items():
        if data["genres"]:
            artist = existing_by_sid[sid]
            artist.genres = data["genres"]
            session.add(artist)

            # Update user's auto_score
            ua = ua_by_artist_id.get(artist.id)
            if ua:
                ua.auto_score = compute_auto_score(
                    ua.source_signals or {}, data["genres"], genre_map
                )
                session.add(ua)

    session.commit()
    progress.update(running=False, step="Done", done=True)


def _backfill_genres_lastfm(
    missing_sids: list[str],
    artist_data: dict,
    session: Session,
    existing_by_sid: dict,
    progress: dict,
):
    """Fetch genres from Last.fm for artists MusicBrainz missed."""
    logger.info(f"  {len(missing_sids)} artists still missing genres, trying Last.fm...")
    progress.update(step="Fetching genres from Last.fm...", current=0, total=len(missing_sids))

    found = 0
    for i, sid in enumerate(missing_sids):
        progress["current"] = i + 1
        name = artist_data[sid]["name"]
        try:
            resp = httpx.get(
                LASTFM_API_URL,
                params={
                    "method": "artist.getTopTags",
                    "artist": name,
                    "api_key": LASTFM_API_KEY,
                    "format": "json",
                },
                timeout=10,
            )
            data = resp.json()
            tags = data.get("toptags", {}).get("tag", [])

            # Filter to tags with count >= 20 to get meaningful genres
            genres = [
                t["name"].lower()
                for t in tags[:8]
                if int(t.get("count", 0)) >= 20
            ]

            if genres:
                artist_data[sid]["genres"] = genres
                found += 1

                existing = existing_by_sid.get(sid)
                if existing:
                    existing.genres = genres
                    session.add(existing)

            if (i + 1) % 25 == 0:
                session.commit()

            time.sleep(0.25)
        except Exception as e:
            logger.warning(f"  Last.fm lookup failed for {name}: {e}")
            time.sleep(0.25)

    session.commit()

    still_missing = sum(1 for sid in missing_sids if not artist_data[sid]["genres"])
    logger.info(f"  Last.fm backfill: found genres for {found}, still missing: {still_missing}")


def _fetch_top_artists(sp: spotipy.Spotify, artist_data: dict):
    """Fetch top artists across all three time ranges."""
    for time_range in ["short_term", "medium_term", "long_term"]:
        try:
            results = sp.current_user_top_artists(limit=50, time_range=time_range)
            for item in results.get("items", []):
                _ensure_artist(
                    artist_data, item["id"], item["name"], item.get("genres", [])
                )
                signals = artist_data[item["id"]]["signals"]
                if not isinstance(signals.get("top_artist"), list):
                    signals["top_artist"] = []
                if time_range not in signals["top_artist"]:
                    signals["top_artist"].append(time_range)
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
    total_tracks = 0
    try:
        offset = 0
        while True:
            results = sp.current_user_saved_tracks(limit=50, offset=offset)
            items = results.get("items", [])
            if not items:
                break

            total_tracks += len(items)
            for item in items:
                track = item.get("track", {})
                for artist in track.get("artists", []):
                    _ensure_artist(artist_data, artist["id"], artist["name"], [])
                    artist_data[artist["id"]]["signals"]["saved_tracks"] += 1

            offset += len(items)
            if not results.get("next"):
                break
    except Exception as e:
        logger.warning(f"Failed to fetch saved tracks (at offset {offset}): {e}")
    logger.info(f"  Saved tracks: fetched {total_tracks} tracks")


def _fetch_playlist_artists(sp: spotipy.Spotify, artist_data: dict):
    """Fetch artists from user's own playlists and count playlist appearances."""
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

    # Convert collected track ID sets into unique_songs counts
    for data in artist_data.values():
        track_ids = data.pop("_playlist_track_ids", None)
        if track_ids:
            data["signals"]["unique_songs"] = len(track_ids)


def _process_playlist(sp: spotipy.Spotify, playlist_id: str, artist_data: dict):
    """Process a single playlist, extracting unique artists and track IDs."""
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
                track_id = track.get("id")
                for artist in track.get("artists", []):
                    artist_id = artist["id"]
                    if artist_id is None:
                        continue
                    _ensure_artist(artist_data, artist_id, artist["name"], [])
                    # Count each playlist only once per artist
                    if artist_id not in seen_in_playlist:
                        artist_data[artist_id]["signals"]["playlist_appearances"] += 1
                        seen_in_playlist.add(artist_id)
                    # Track unique songs per artist
                    if track_id:
                        if "_playlist_track_ids" not in artist_data[artist_id]:
                            artist_data[artist_id]["_playlist_track_ids"] = set()
                        artist_data[artist_id]["_playlist_track_ids"].add(track_id)

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
