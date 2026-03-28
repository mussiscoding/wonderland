import os

import spotipy
from spotipy.oauth2 import SpotifyOAuth

SCOPES = [
    "user-top-read",
    "user-follow-read",
    "user-library-read",
    "user-read-recently-played",
    "playlist-read-private",
    "playlist-read-collaborative",
]


def get_spotify_oauth() -> SpotifyOAuth:
    return SpotifyOAuth(
        client_id=os.environ["SPOTIFY_CLIENT_ID"],
        client_secret=os.environ["SPOTIFY_CLIENT_SECRET"],
        redirect_uri=os.environ.get(
            "SPOTIFY_REDIRECT_URI", "http://127.0.0.1:8000/callback"
        ),
        scope=" ".join(SCOPES),
        cache_path="data/.spotify_cache",
        open_browser=False,
    )


def is_authenticated() -> bool:
    oauth = get_spotify_oauth()
    return oauth.get_cached_token() is not None


def get_spotify_client() -> spotipy.Spotify | None:
    oauth = get_spotify_oauth()
    token_info = oauth.get_cached_token()
    if not token_info:
        return None
    return spotipy.Spotify(auth=token_info["access_token"])
