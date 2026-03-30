import json
import os

import spotipy
from cryptography.fernet import Fernet
from fastapi import Request
from spotipy.cache_handler import CacheHandler, MemoryCacheHandler
from spotipy.oauth2 import SpotifyOAuth
from sqlmodel import Session

from app.models import User

SCOPES = [
    "user-top-read",
    "user-follow-read",
    "user-library-read",
    "user-read-recently-played",
    "playlist-read-private",
    "playlist-read-collaborative",
]

_fernet = Fernet(os.environ["FERNET_KEY"])


class DatabaseCacheHandler(CacheHandler):
    """Stores Spotify tokens encrypted in the User table."""

    def __init__(self, db_session: Session, user_id: int):
        self.db_session = db_session
        self.user_id = user_id

    def get_cached_token(self):
        user = self.db_session.get(User, self.user_id)
        if not user or not user.encrypted_token_info:
            return None
        try:
            decrypted = _fernet.decrypt(user.encrypted_token_info.encode())
            return json.loads(decrypted)
        except Exception:
            return None

    def save_token_to_cache(self, token_info):
        user = self.db_session.get(User, self.user_id)
        if not user:
            return
        encrypted = _fernet.encrypt(json.dumps(token_info).encode()).decode()
        user.encrypted_token_info = encrypted
        self.db_session.add(user)
        self.db_session.commit()


def encrypt_token_info(token_info: dict) -> str:
    """Encrypt a token_info dict for storage."""
    return _fernet.encrypt(json.dumps(token_info).encode()).decode()


def _build_oauth(cache_handler: CacheHandler, show_dialog: bool = False) -> SpotifyOAuth:
    return SpotifyOAuth(
        client_id=os.environ["SPOTIFY_CLIENT_ID"],
        client_secret=os.environ["SPOTIFY_CLIENT_SECRET"],
        redirect_uri=os.environ.get(
            "SPOTIFY_REDIRECT_URI", "http://127.0.0.1:8000/callback"
        ),
        scope=" ".join(SCOPES),
        cache_handler=cache_handler,
        open_browser=False,
        show_dialog=show_dialog,
    )


def get_login_oauth(show_dialog: bool = False) -> tuple[SpotifyOAuth, MemoryCacheHandler]:
    """Create an OAuth manager for the login flow (no user yet).

    Returns (oauth, memory_cache) so the callback can retrieve the token.
    """
    cache = MemoryCacheHandler()
    oauth = _build_oauth(cache, show_dialog=show_dialog)
    return oauth, cache


def get_spotify_client(db_session: Session, user_id: int) -> spotipy.Spotify | None:
    """Get an authenticated Spotify client for a specific user."""
    user = db_session.get(User, user_id)
    if not user or not user.encrypted_token_info:
        return None
    cache_handler = DatabaseCacheHandler(db_session, user_id)
    oauth = _build_oauth(cache_handler)
    token_info = oauth.get_cached_token()
    if not token_info:
        return None
    return spotipy.Spotify(auth_manager=oauth)


def get_current_user(request: Request, db_session: Session) -> User | None:
    """Load the current user from the session cookie."""
    user_id = request.session.get("user_id")
    if not user_id:
        return None
    return db_session.get(User, user_id)
