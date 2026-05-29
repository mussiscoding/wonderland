from typing import Literal

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from sqlmodel import Session

from app.auth import get_current_user
from app.database import get_session
from app.events import event_progress
from app.spotify import import_progress
from app.templating import templates, notifications

router = APIRouter()

# Maps notice kind -> the per-user progress dict it reads/acknowledges.
_PROGRESS = {"artists": import_progress, "events": event_progress}


def _render(request: Request, user) -> HTMLResponse:
    notices = notifications(user)
    if not notices:
        return HTMLResponse("")
    return templates.TemplateResponse(request, "notifications.html", {"notices": notices})


@router.get("/notifications", response_class=HTMLResponse)
def get_notifications(request: Request, session: Session = Depends(get_session)):
    """Poll target: renders active sync toasts; the container re-arms the poll only
    while something is running, so polling stops once everything is terminal."""
    user = get_current_user(request, session)
    if not user:
        return HTMLResponse("")
    return _render(request, user)


@router.post("/notifications/dismiss", response_class=HTMLResponse)
def dismiss_notification(
    request: Request,
    kind: Literal["artists", "events"],
    session: Session = Depends(get_session),
):
    user = get_current_user(request, session)
    if not user:
        return HTMLResponse("")
    progress_store = _PROGRESS[kind]
    if user.id in progress_store:
        progress_store[user.id]["acknowledged"] = True
    return _render(request, user)
