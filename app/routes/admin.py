import logging
import threading

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlmodel import Session

from app.auth import get_current_user
from app.cities import CITY_CONFIG, ALL_CITIES
from app.database import get_session, engine
from app.events import fetch_all_events, _get_event_progress
from app.matching import run_matching
from app.spotify import resolve_lineup_artists, resolve_progress
from app.templating import templates, is_admin_user

logger = logging.getLogger(__name__)

router = APIRouter()



def _run_fetch_background(user_id: int, cities: list[str]):
    """Run event fetch + matching in a background thread."""
    progress = _get_event_progress(user_id)
    with Session(engine) as session:
        try:
            summary = fetch_all_events(session, user_id, cities=cities)
            progress.update(running=True, step="Matching artists to events...", current=0, total=0)
            run_matching(session)
            progress.update(
                running=False,
                step="Done",
                done=True,
                new_events=summary["new_events"],
                updated_events=summary["updated_events"],
                unchanged_events=summary["unchanged_events"],
                acknowledged=False,
            )
        except Exception as e:
            logger.error(f"Background event fetch failed: {e}")
            progress.update(running=False, step=f"Error: {e}", done=False)


@router.get("/admin", response_class=HTMLResponse)
def admin_page(request: Request, session: Session = Depends(get_session)):
    user = get_current_user(request, session)
    if not user:
        return RedirectResponse("/login", status_code=303)
    if not is_admin_user(user):
        return RedirectResponse("/artists", status_code=303)

    progress = _get_event_progress(user.id)

    return templates.TemplateResponse(
        request,
        "admin.html",
        {
            "current_user": user,
            "city_options": CITY_CONFIG,
            "progress": progress,
            "resolve_progress": resolve_progress,
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
    if not is_admin_user(user):
        return RedirectResponse("/artists", status_code=303)

    progress = _get_event_progress(user.id)
    if progress["running"]:
        return RedirectResponse(f"/admin/fetch/progress?city={city}", status_code=303)

    cities = ALL_CITIES if city == "both" else [city]
    threading.Thread(target=_run_fetch_background, args=(user.id, cities), daemon=True).start()
    return RedirectResponse(f"/admin/fetch/progress?city={city}", status_code=303)


def _user_event_progress(user) -> dict:
    _EMPTY = {
        "running": False, "done": False, "step": "", "current": 0, "total": 0,
        "new_events": 0, "updated_events": 0, "unchanged_events": 0, "acknowledged": True,
    }
    return _get_event_progress(user.id) if user else _EMPTY


@router.get("/admin/fetch/notification", response_class=HTMLResponse)
def fetch_notification(request: Request, session: Session = Depends(get_session)):
    """Poll target: returns the re-arming poller while a fetch runs, the static toast
    once it finishes (no trigger, so polling stops), or empty otherwise."""
    user = get_current_user(request, session)
    if not user or not is_admin_user(user):
        return HTMLResponse("")
    progress = _get_event_progress(user.id)
    if progress.get("running"):
        return templates.TemplateResponse(request, "fetch_poller.html", {})
    if progress.get("done") and not progress.get("acknowledged", True):
        return templates.TemplateResponse(
            request,
            "fetch_toast.html",
            {
                "new_events": progress.get("new_events", 0),
                "updated_events": progress.get("updated_events", 0),
                "unchanged_events": progress.get("unchanged_events", 0),
            },
        )
    return HTMLResponse("")


@router.post("/admin/fetch/notification/dismiss", response_class=HTMLResponse)
def dismiss_fetch_notification(request: Request, session: Session = Depends(get_session)):
    user = get_current_user(request, session)
    if user and is_admin_user(user):
        _get_event_progress(user.id)["acknowledged"] = True
    return HTMLResponse("")


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


# ---------------------------------------------------------------------------
# Resolve lineup artists
# ---------------------------------------------------------------------------

def _run_resolve_background():
    """Run lineup artist resolution in a background thread."""
    with Session(engine) as session:
        try:
            resolve_lineup_artists(session)
        except Exception as e:
            logger.error(f"Background resolve failed: {e}")
            resolve_progress.update(running=False, step=f"Error: {e}", done=False)


@router.post("/admin/resolve")
def run_resolve(request: Request, session: Session = Depends(get_session)):
    user = get_current_user(request, session)
    if not user:
        return RedirectResponse("/login", status_code=303)
    if not is_admin_user(user):
        return RedirectResponse("/artists", status_code=303)

    if resolve_progress["running"]:
        return RedirectResponse("/admin/resolve/progress", status_code=303)

    threading.Thread(target=_run_resolve_background, daemon=True).start()
    return RedirectResponse("/admin/resolve/progress", status_code=303)


@router.get("/admin/resolve/progress", response_class=HTMLResponse)
def resolve_progress_page(request: Request, session: Session = Depends(get_session)):
    user = get_current_user(request, session)
    if resolve_progress["done"] and not resolve_progress["running"]:
        return RedirectResponse("/admin", status_code=303)

    return templates.TemplateResponse(
        request,
        "fetch_progress.html",
        {
            "progress": resolve_progress,
            "current_user": user,
            "city": "",
            "heading": "Resolving Lineup Artists",
            "progress_bar_url": "/admin/resolve/progress-bar",
        },
    )


@router.get("/admin/resolve/progress-bar", response_class=HTMLResponse)
def resolve_progress_bar(request: Request):
    return templates.TemplateResponse(
        request,
        "fetch_progress_bar.html",
        {"progress": resolve_progress, "redirect_url": "/admin"},
    )
