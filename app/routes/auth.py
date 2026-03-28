from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse

from app.auth import get_spotify_oauth

router = APIRouter()


@router.get("/login")
def login():
    oauth = get_spotify_oauth()
    auth_url = oauth.get_authorize_url()
    return RedirectResponse(auth_url)


@router.get("/callback")
def callback(request: Request, code: str = ""):
    if not code:
        return RedirectResponse("/")

    oauth = get_spotify_oauth()
    oauth.get_access_token(code)
    return RedirectResponse("/")
