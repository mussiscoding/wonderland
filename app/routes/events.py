import logging
from datetime import date

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlmodel import Session, select

from app.auth import get_current_user
from app.cities import CITY_CONFIG
from app.database import get_session
from app.models import Artist, Event, EventSource, Match, UserArtist
from app.scoring import compute_event_score
from app.templating import templates

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/events", response_class=HTMLResponse)
def list_events(
    request: Request,
    q: str = "",
    sort: str = "score",
    show_all: str = "",
    date_from: str = "",
    date_to: str = "",
    city: str = "london",
    session: Session = Depends(get_session),
):
    user = get_current_user(request, session)
    if not user:
        return RedirectResponse("/login", status_code=303)

    # Filter events by city
    if city == "all":
        events = session.exec(select(Event)).all()
    else:
        city_label = CITY_CONFIG.get(city, {}).get("label", city.title())
        events = session.exec(
            select(Event).where(Event.venue_location == city_label)
        ).all()

    # Load all matches with artist info
    matches = session.exec(select(Match)).all()
    artists_by_id = {
        a.id: a for a in session.exec(select(Artist)).all()
    }

    # Load current user's UserArtist data for scoring
    user_artists = session.exec(
        select(UserArtist).where(UserArtist.user_id == user.id)
    ).all()
    ua_by_artist_id = {ua.artist_id: ua for ua in user_artists}

    # Build match data per event, filtered to user's artists
    matches_by_event: dict[int, list[dict]] = {}
    for m in matches:
        artist = artists_by_id.get(m.artist_id)
        if not artist:
            continue
        # Only include matches for artists the user has imported
        ua = ua_by_artist_id.get(m.artist_id)
        if not ua:
            continue
        # Skip excluded artists for this user
        if ua.excluded:
            continue

        matches_by_event.setdefault(m.event_id, []).append({
            "artist": artist,
            "effective_score": ua.effective_score,
            "confidence": m.confidence,
            "match_type": m.match_type,
            "matched_name": m.matched_name,
        })

    # Compute event scores using user-specific scores
    event_scores: dict[int, float] = {}
    for event in events:
        event_matches = matches_by_event.get(event.id, [])
        matched_pairs = [
            (m["effective_score"], m["confidence"])
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

    # Date filter
    if date_from:
        try:
            df = date.fromisoformat(date_from)
            events = [e for e in events if e.date.date() >= df]
        except ValueError:
            pass
    if date_to:
        try:
            dt = date.fromisoformat(date_to)
            events = [e for e in events if e.date.date() <= dt]
        except ValueError:
            pass

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
    elif sort == "score_asc":
        events.sort(key=lambda e: event_scores.get(e.id, 0))
    elif sort == "date":
        events.sort(key=lambda e: e.date)
    elif sort == "date_desc":
        events.sort(key=lambda e: e.date, reverse=True)

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
            "date_from": date_from,
            "date_to": date_to,
            "city": city,
            "city_options": CITY_CONFIG,
            "current_user": user,
        },
    )
