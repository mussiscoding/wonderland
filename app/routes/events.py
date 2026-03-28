import logging
import threading

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlmodel import Session, select

from app.database import get_session, engine
from app.events import fetch_all_events, event_progress
from app.matching import run_matching
from app.models import Artist, Event, EventSource, Match
from app.scoring import compute_event_score
from app.templating import templates

logger = logging.getLogger(__name__)

router = APIRouter()


def _run_fetch_background():
    """Run event fetch + matching in a background thread."""
    from sqlmodel import Session as SSession

    with SSession(engine) as session:
        try:
            fetch_all_events(session)
            event_progress.update(running=True, step="Matching artists to events...", current=0, total=0)
            run_matching(session)
            event_progress.update(running=False, step="Done", done=True)
        except Exception as e:
            logger.error(f"Background event fetch failed: {e}")
            event_progress.update(running=False, step=f"Error: {e}", done=False)


@router.post("/events/fetch")
def run_fetch():
    if event_progress["running"]:
        return RedirectResponse("/events/fetch/progress", status_code=303)

    threading.Thread(target=_run_fetch_background, daemon=True).start()
    return RedirectResponse("/events/fetch/progress", status_code=303)


@router.get("/events/fetch/progress", response_class=HTMLResponse)
def fetch_progress(request: Request):
    if event_progress["done"] and not event_progress["running"]:
        return RedirectResponse("/events", status_code=303)

    return templates.TemplateResponse(
        request,
        "fetch_progress.html",
        {"progress": event_progress},
    )


@router.get("/events/fetch/progress-bar", response_class=HTMLResponse)
def fetch_progress_bar(request: Request):
    return templates.TemplateResponse(
        request,
        "fetch_progress_bar.html",
        {"progress": event_progress},
    )


@router.get("/events", response_class=HTMLResponse)
def list_events(
    request: Request,
    q: str = "",
    sort: str = "score",
    show_all: str = "",
    session: Session = Depends(get_session),
):
    events = session.exec(select(Event)).all()

    # Load all matches with artist info
    matches = session.exec(select(Match)).all()
    artists_by_id = {
        a.id: a for a in session.exec(select(Artist)).all()
    }

    # Build match data per event
    matches_by_event: dict[int, list[dict]] = {}
    for m in matches:
        artist = artists_by_id.get(m.artist_id)
        if not artist:
            continue
        matches_by_event.setdefault(m.event_id, []).append({
            "artist": artist,
            "confidence": m.confidence,
            "match_type": m.match_type,
            "matched_name": m.matched_name,
        })

    # Compute event scores
    event_scores: dict[int, float] = {}
    for event in events:
        event_matches = matches_by_event.get(event.id, [])
        matched_pairs = [
            (m["artist"].effective_score, m["confidence"])
            for m in event_matches
        ]
        event_scores[event.id] = compute_event_score(matched_pairs)

    # Load sources
    sources_by_event = {}
    for s in session.exec(select(EventSource)).all():
        sources_by_event.setdefault(s.event_id, []).append(s)

    # Filter to matched events unless show_all
    if not show_all:
        events = [e for e in events if event_scores.get(e.id, 0) > 0]

    # Search filter
    if q:
        q_lower = q.lower()
        events = [
            e for e in events
            if q_lower in e.title.lower()
            or q_lower in e.venue_name.lower()
            or any(q_lower in a.lower() for a in (e.lineup_parsed or []))
        ]

    # Sort
    if sort == "score":
        events.sort(key=lambda e: event_scores.get(e.id, 0), reverse=True)
    elif sort == "date":
        events.sort(key=lambda e: e.date)

    return templates.TemplateResponse(
        request,
        "events.html",
        {
            "events": events,
            "event_scores": event_scores,
            "matches_by_event": matches_by_event,
            "sources_by_event": sources_by_event,
            "q": q,
            "sort": sort,
            "show_all": show_all,
            "total_count": len(events),
        },
    )
