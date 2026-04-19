import logging
import smtplib
import time
from email.message import EmailMessage

import spotipy
from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlmodel import Session, select

from app.auth import encrypt_token_info, get_login_oauth
from app.config import settings
from app.database import get_session
from app.models import AccessRequest, User
from app.templating import templates

logger = logging.getLogger(__name__)

router = APIRouter()

# OAuth state between /login and /callback. Entries expire after 10 minutes.
_pending_oauth: dict[str, tuple] = {}
_OAUTH_TTL = 600  # seconds


@router.get("/login")
def login(request: Request, switch: str = ""):
    show_dialog = bool(switch)
    oauth, cache = get_login_oauth(show_dialog=show_dialog)

    auth_url = oauth.get_authorize_url()
    state = oauth.state

    # Clean up stale entries before adding new one
    now = time.monotonic()
    stale = [k for k, (_, _, t) in _pending_oauth.items() if now - t > _OAUTH_TTL]
    for k in stale:
        del _pending_oauth[k]

    _pending_oauth[state] = (oauth, cache, now)

    return RedirectResponse(auth_url)


@router.get("/callback")
def callback(
    request: Request,
    code: str = "",
    state: str = "",
    error: str = "",
    session: Session = Depends(get_session),
):
    if error or not code:
        return RedirectResponse("/request-access")

    # Retrieve the OAuth object from the login step
    pending = _pending_oauth.pop(state, None)
    if not pending:
        # Fallback: create a fresh OAuth if state was lost
        oauth, cache = get_login_oauth()
    else:
        oauth, cache, _ = pending

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


@router.get("/request-access", response_class=HTMLResponse)
def request_access_page(request: Request):
    return templates.TemplateResponse(
        request, "request_access.html", {"submitted": False}
    )


@router.post("/request-access", response_class=HTMLResponse)
def request_access_submit(
    request: Request,
    email: str = Form(...),
    session: Session = Depends(get_session),
):
    access_request = AccessRequest(email=email)
    session.add(access_request)
    session.commit()

    _send_access_request_email(email)

    return templates.TemplateResponse(
        request, "request_access.html", {"submitted": True}
    )


def _send_access_request_email(requester_email: str):
    addr = settings.gmail_address
    pw = settings.gmail_app_password
    if not addr or not pw:
        logger.warning("Gmail not configured — skipping access request email")
        return

    msg = EmailMessage()
    msg["Subject"] = "Wonderland access request"
    msg["From"] = addr
    msg["To"] = addr
    msg.set_content(f"{requester_email} wants access to Wonderland.")

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
            smtp.login(addr, pw)
            smtp.send_message(msg)
    except Exception:
        logger.exception("Failed to send access request email")
