import logging
import threading

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlmodel import Session, select

from app.auth import get_current_user, get_spotify_client
from app.database import get_session, engine
from app.models import Artist, UserArtist
from app.scoring import get_genre_map
from app.spotify import import_all_artists, import_progress, _get_progress, backfill_lastfm
from app.templating import templates

logger = logging.getLogger(__name__)

router = APIRouter()


def _run_import_background(sp, user_id: int):
    """Run import in a background thread with its own DB session."""
    progress = _get_progress(user_id)
    with Session(engine) as session:
        try:
            import_all_artists(sp, session, user_id)
        except Exception as e:
            logger.error(f"Background import failed: {e}")
            progress.update(running=False, step=f"Error: {e}", done=False)


@router.post("/import")
def run_import(request: Request, session: Session = Depends(get_session)):
    user = get_current_user(request, session)
    if not user:
        return RedirectResponse("/login", status_code=303)

    sp = get_spotify_client(session, user.id)
    if not sp:
        return RedirectResponse("/login", status_code=303)

    progress = _get_progress(user.id)
    if not progress["running"]:
        threading.Thread(
            target=_run_import_background, args=(sp, user.id), daemon=True
        ).start()

    # If HTMX request, return the progress bar fragment inline
    if request.headers.get("HX-Request"):
        return templates.TemplateResponse(
            request,
            "import_progress_inline.html",
            {"progress": progress},
        )

    return RedirectResponse("/import/progress", status_code=303)


@router.get("/import/progress", response_class=HTMLResponse)
def show_progress(request: Request, session: Session = Depends(get_session)):
    user = get_current_user(request, session)
    progress = _get_progress(user.id) if user else {"running": False, "done": False, "step": "", "current": 0, "total": 0}

    if progress["done"] and not progress["running"]:
        return RedirectResponse("/artists", status_code=303)

    return templates.TemplateResponse(
        request,
        "import_progress.html",
        {"progress": progress, "current_user": user},
    )


@router.get("/import/progress-bar", response_class=HTMLResponse)
def progress_bar(request: Request, session: Session = Depends(get_session)):
    user = get_current_user(request, session)
    progress = _get_progress(user.id) if user else {"running": False, "done": False, "step": "", "current": 0, "total": 0}
    return templates.TemplateResponse(
        request,
        "import_progress_bar.html",
        {"progress": progress, "current_user": user},
    )


@router.get("/import/progress-inline", response_class=HTMLResponse)
def progress_inline(request: Request, session: Session = Depends(get_session)):
    user = get_current_user(request, session)
    progress = _get_progress(user.id) if user else {"running": False, "done": False, "step": "", "current": 0, "total": 0}
    return templates.TemplateResponse(
        request,
        "import_progress_inline.html",
        {"progress": progress},
    )


@router.post("/backfill-lastfm")
def run_lastfm_backfill(request: Request, session: Session = Depends(get_session)):
    user = get_current_user(request, session)
    if not user:
        return RedirectResponse("/login", status_code=303)

    progress = _get_progress(user.id)
    if not progress["running"]:
        progress.update(running=True, step="Starting Last.fm backfill...", current=0, total=0, done=False)

        uid = user.id
        def _run():
            with Session(engine) as bg_session:
                try:
                    backfill_lastfm(bg_session, uid)
                except Exception as e:
                    logger.error(f"Last.fm backfill failed: {e}")
                    _get_progress(uid).update(running=False, step=f"Error: {e}", done=False)

        threading.Thread(target=_run, daemon=True).start()

    if request.headers.get("HX-Request"):
        return templates.TemplateResponse(
            request,
            "import_progress_inline.html",
            {"progress": progress},
        )

    return RedirectResponse("/import/progress", status_code=303)


@router.get("/artist/{artist_id}", response_class=HTMLResponse)
def show_artist(
    request: Request,
    artist_id: int,
    session: Session = Depends(get_session),
):
    user = get_current_user(request, session)
    if not user:
        return RedirectResponse("/login", status_code=303)

    artist = session.get(Artist, artist_id)
    if not artist:
        return RedirectResponse("/artists", status_code=303)

    # Load user-specific scoring data
    user_artist = session.exec(
        select(UserArtist).where(
            UserArtist.user_id == user.id,
            UserArtist.artist_id == artist_id,
        )
    ).first()

    return templates.TemplateResponse(
        request,
        "artist_detail.html",
        {
            "artist": artist,
            "user_artist": user_artist,
            "genre_map": get_genre_map(session),
            "current_user": user,
        },
    )


@router.get("/artists", response_class=HTMLResponse)
def list_artists(
    request: Request,
    q: str = "",
    genre: str = "",
    sort: str = "score",
    session: Session = Depends(get_session),
):
    user = get_current_user(request, session)

    if not user:
        # Show connect prompt for unauthenticated users
        return templates.TemplateResponse(
            request,
            "artists.html",
            {
                "artists": [],
                "q": q,
                "genre": genre,
                "sort": sort,
                "current_user": None,
                "genre_map": {},
                "total_count": 0,
                "import_progress": {"running": False, "done": False, "step": "", "current": 0, "total": 0},
            },
        )

    # Load user's artists with their scores
    user_artists = session.exec(
        select(UserArtist).where(UserArtist.user_id == user.id)
    ).all()

    artist_ids = [ua.artist_id for ua in user_artists]
    artists_by_id = {}
    if artist_ids:
        artists_by_id = {
            a.id: a for a in session.exec(
                select(Artist).where(Artist.id.in_(artist_ids))
            ).all()
        }

    # Build merged artist+score objects for the template
    merged = []
    for ua in user_artists:
        artist = artists_by_id.get(ua.artist_id)
        if not artist:
            continue
        merged.append({
            "id": artist.id,
            "name": artist.name,
            "genres": artist.genres or [],
            "effective_score": ua.effective_score,
            "auto_score": ua.auto_score,
            "manual_score": ua.manual_score,
            "excluded": ua.excluded,
            "source_signals": ua.source_signals or {},
            "spotify_id": artist.spotify_id,
        })

    if q:
        q_lower = q.lower()
        merged = [a for a in merged if q_lower in a["name"].lower()]

    if genre:
        genre_lower = genre.lower()
        merged = [
            a for a in merged
            if any(genre_lower in g.lower() for g in a["genres"])
        ]

    if sort == "score":
        merged.sort(key=lambda a: a["effective_score"], reverse=True)
    elif sort == "name":
        merged.sort(key=lambda a: a["name"].lower())

    progress = _get_progress(user.id)

    return templates.TemplateResponse(
        request,
        "artists.html",
        {
            "artists": merged,
            "q": q,
            "genre": genre,
            "sort": sort,
            "current_user": user,
            "genre_map": get_genre_map(session),
            "total_count": len(merged),
            "import_progress": progress,
        },
    )
