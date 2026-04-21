import logging
import threading

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlmodel import Session

from app.auth import get_current_user
from app.cities import CITY_CONFIG, ALL_CITIES
from app.config import settings
from app.database import get_session, engine
from app.events import fetch_all_events, _get_event_progress
from app.matching import run_matching
from app.templating import templates

logger = logging.getLogger(__name__)

router = APIRouter()

_admin_ids = None


def _get_admin_ids() -> set[str]:
    global _admin_ids
    if _admin_ids is None:
        raw = settings.admin_spotify_ids
        _admin_ids = {s.strip() for s in raw.split(",") if s.strip()} if raw else set()
    return _admin_ids


def _is_admin(user) -> bool:
    return user.spotify_id in _get_admin_ids()


def _run_fetch_background(user_id: int, cities: list[str]):
    """Run event fetch + matching in a background thread."""
    progress = _get_event_progress(user_id)
    with Session(engine) as session:
        try:
            fetch_all_events(session, user_id, cities=cities)
            progress.update(running=True, step="Matching artists to events...", current=0, total=0)
            run_matching(session)
            progress.update(running=False, step="Done", done=True)
        except Exception as e:
            logger.error(f"Background event fetch failed: {e}")
            progress.update(running=False, step=f"Error: {e}", done=False)


@router.get("/admin", response_class=HTMLResponse)
def admin_page(request: Request, session: Session = Depends(get_session)):
    user = get_current_user(request, session)
    if not user:
        return RedirectResponse("/login", status_code=303)
    if not _is_admin(user):
        return RedirectResponse("/artists", status_code=303)

    progress = _get_event_progress(user.id)

    return templates.TemplateResponse(
        request,
        "admin.html",
        {
            "current_user": user,
            "city_options": CITY_CONFIG,
            "progress": progress,
        },
    )


@router.post("/admin/fetch")
def run_fetch(
    request: Request,
    city: str = Form("london"),
    session: Session = Depends(get_session),
):
    user = get_current_user(request, session)
    if not user:
        return RedirectResponse("/login", status_code=303)
    if not _is_admin(user):
        return RedirectResponse("/artists", status_code=303)

    progress = _get_event_progress(user.id)
    if progress["running"]:
        return RedirectResponse(f"/admin/fetch/progress?city={city}", status_code=303)

    cities = ALL_CITIES if city == "both" else [city]
    threading.Thread(target=_run_fetch_background, args=(user.id, cities), daemon=True).start()
    return RedirectResponse(f"/admin/fetch/progress?city={city}", status_code=303)


def _user_event_progress(user) -> dict:
    _EMPTY = {"running": False, "done": False, "step": "", "current": 0, "total": 0}
    return _get_event_progress(user.id) if user else _EMPTY


@router.get("/admin/fetch/progress", response_class=HTMLResponse)
def fetch_progress_page(request: Request, city: str = "london", session: Session = Depends(get_session)):
    user = get_current_user(request, session)
    progress = _user_event_progress(user)

    if progress["done"] and not progress["running"]:
        return RedirectResponse(f"/events?city={city}", status_code=303)

    return templates.TemplateResponse(
        request,
        "fetch_progress.html",
        {"progress": progress, "current_user": user, "city": city},
    )


@router.get("/admin/fetch/progress-bar", response_class=HTMLResponse)
def fetch_progress_bar(request: Request, city: str = "london", session: Session = Depends(get_session)):
    user = get_current_user(request, session)
    progress = _user_event_progress(user)
    return templates.TemplateResponse(
        request,
        "fetch_progress_bar.html",
        {"progress": progress, "city": city},
    )
