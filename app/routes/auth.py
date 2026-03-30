import spotipy
from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from sqlmodel import Session, select

from app.auth import encrypt_token_info, get_login_oauth
from app.database import get_session
from app.models import User

router = APIRouter()

# Module-level cache for the OAuth object between /login and /callback
_pending_oauth = {}


@router.get("/login")
def login(request: Request, switch: str = ""):
    show_dialog = bool(switch)
    oauth, cache = get_login_oauth(show_dialog=show_dialog)

    # Store the OAuth/cache in memory keyed by state so callback can retrieve it
    auth_url = oauth.get_authorize_url()
    state = oauth.state
    _pending_oauth[state] = (oauth, cache)

    return RedirectResponse(auth_url)


@router.get("/callback")
def callback(
    request: Request,
    code: str = "",
    state: str = "",
    session: Session = Depends(get_session),
):
    if not code:
        return RedirectResponse("/")

    # Retrieve the OAuth object from the login step
    pending = _pending_oauth.pop(state, None)
    if not pending:
        # Fallback: create a fresh OAuth if state was lost
        oauth, cache = get_login_oauth()
    else:
        oauth, cache = pending

    # Exchange code for token
    token_info = oauth.get_access_token(code)

    # Get the user's Spotify profile
    sp = spotipy.Spotify(auth=token_info["access_token"])
    profile = sp.current_user()
    spotify_id = profile["id"]
    display_name = profile.get("display_name") or spotify_id

    # Find or create user
    user = session.exec(
        select(User).where(User.spotify_id == spotify_id)
    ).first()

    if not user:
        user = User(spotify_id=spotify_id, display_name=display_name)
        session.add(user)
        session.commit()
        session.refresh(user)
    else:
        user.display_name = display_name
        session.add(user)

    # Store encrypted token
    user.encrypted_token_info = encrypt_token_info(token_info)
    session.add(user)
    session.commit()

    # Set session
    request.session["user_id"] = user.id

    return RedirectResponse("/artists")


@router.get("/logout")
def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/artists")
