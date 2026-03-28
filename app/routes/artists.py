import logging
import threading

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlmodel import Session, select

from app.auth import get_spotify_client, is_authenticated
from app.database import get_session, engine
from app.models import Artist
from app.scoring import get_genre_map
from app.spotify import import_all_artists, import_progress
from app.templating import templates

logger = logging.getLogger(__name__)

router = APIRouter()


def _run_import_background(sp):
    """Run import in a background thread with its own DB session."""
    from sqlmodel import Session as SSession

    with SSession(engine) as session:
        try:
            import_all_artists(sp, session)
        except Exception as e:
            logger.error(f"Background import failed: {e}")
            import_progress.update(running=False, step=f"Error: {e}", done=False)


@router.post("/import")
def run_import(request: Request):
    sp = get_spotify_client()
    if not sp:
        return RedirectResponse("/login", status_code=303)

    if not import_progress["running"]:
        threading.Thread(target=_run_import_background, args=(sp,), daemon=True).start()

    # If HTMX request, return the progress bar fragment inline
    if request.headers.get("HX-Request"):
        return templates.TemplateResponse(
            request,
            "import_progress_inline.html",
            {"progress": import_progress},
        )

    return RedirectResponse("/import/progress", status_code=303)


@router.get("/import/progress", response_class=HTMLResponse)
def show_progress(request: Request):
    if import_progress["done"] and not import_progress["running"]:
        return RedirectResponse("/artists", status_code=303)

    return templates.TemplateResponse(
        request,
        "import_progress.html",
        {"progress": import_progress},
    )


@router.get("/import/progress-bar", response_class=HTMLResponse)
def progress_bar(request: Request):
    return templates.TemplateResponse(
        request,
        "import_progress_bar.html",
        {"progress": import_progress},
    )


@router.get("/import/progress-inline", response_class=HTMLResponse)
def progress_inline(request: Request):
    return templates.TemplateResponse(
        request,
        "import_progress_inline.html",
        {"progress": import_progress},
    )


@router.get("/artists", response_class=HTMLResponse)
def list_artists(
    request: Request,
    q: str = "",
    genre: str = "",
    sort: str = "score",
    session: Session = Depends(get_session),
):
    artists = session.exec(select(Artist)).all()

    if q:
        q_lower = q.lower()
        artists = [a for a in artists if q_lower in a.name.lower()]

    if genre:
        genre_lower = genre.lower()
        artists = [
            a for a in artists
            if any(genre_lower in g.lower() for g in (a.genres or []))
        ]

    if sort == "score":
        artists.sort(key=lambda a: a.effective_score, reverse=True)
    elif sort == "name":
        artists.sort(key=lambda a: a.name.lower())

    return templates.TemplateResponse(
        request,
        "artists.html",
        {
            "artists": artists,
            "q": q,
            "genre": genre,
            "sort": sort,
            "authenticated": is_authenticated(),
            "genre_map": get_genre_map(session),
            "total_count": len(artists),
            "import_progress": import_progress,
        },
    )
