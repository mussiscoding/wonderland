import logging
from datetime import date

from fastapi import APIRouter, Depends, Request, Response
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlmodel import Session, select

from app.auth import get_current_user
from app.cities import CITY_CONFIG
from app.database import get_session
from app.models import Artist, Event, EventSource, Match, UserArtist, UserEvent
from app.matching import normalise_name
from app.scoring import compute_event_score
from app.templating import templates

logger = logging.getLogger(__name__)

router = APIRouter()


def user_event_scores(session: Session, user_id: int) -> dict[int, float]:
    """Map event_id -> event score for this user (only events with qualifying matches)."""
    user_artists = session.exec(
        select(UserArtist).where(UserArtist.user_id == user_id)
    ).all()
    ua_by_artist_id = {ua.artist_id: ua for ua in user_artists}

    pairs_by_event: dict[int, list] = {}
    for m in session.exec(select(Match)).all():
        ua = ua_by_artist_id.get(m.artist_id)
        if not ua or ua.excluded:
            continue
        pairs_by_event.setdefault(m.event_id, []).append((ua.effective_score, m.confidence))

    return {eid: compute_event_score(pairs) for eid, pairs in pairs_by_event.items()}


def count_user_matched_events(session: Session, user_id: int) -> int:
    """Count upcoming events (today onward) that match this user's library."""
    scores = user_event_scores(session, user_id)
    matched_ids = [eid for eid, s in scores.items() if s > 0]
    if not matched_ids:
        return 0
    today = date.today()
    events = session.exec(select(Event).where(Event.id.in_(matched_ids))).all()
    return sum(1 for e in events if e.date.date() >= today)


@router.get("/events", response_class=HTMLResponse)
def list_events(
    request: Request,
    q: str = "",
    sort: str = "",
    show_all: str = "",  # legacy: aliased to view=all
    view: str = "",
    date_from: str = "",
    date_to: str = "",
    city: str = "london",
    session: Session = Depends(get_session),
):
    user = get_current_user(request, session)
    if not user:
        return RedirectResponse("/login", status_code=303)

    # Resolve view (back-compat: show_all=1 → view=all; default → mine)
    if not view:
        view = "all" if show_all else "mine"
    if view not in ("mine", "saved", "all"):
        view = "mine"
    # Default sort flips to date for saved view; score for the others
    if not sort:
        sort = "date" if view == "saved" else "score"

    # Load this user's saved event IDs (used by view=saved filter + row stripes)
    saved_event_ids: set[int] = set(session.exec(
        select(UserEvent.event_id).where(UserEvent.user_id == user.id)
    ).all())

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

    # Compute event scores for sorting and filtering (reuse matches already loaded above)
    event_scores = {
        eid: compute_event_score([(m["effective_score"], m["confidence"]) for m in ms])
        for eid, ms in matches_by_event.items()
    }

    # Load sources
    sources_by_event = {}
    for s in session.exec(select(EventSource)).all():
        sources_by_event.setdefault(s.event_id, []).append(s)

    # View filter
    if view == "mine":
        events = [e for e in events if event_scores.get(e.id, 0) > 0]
    elif view == "saved":
        events = [e for e in events if e.id in saved_event_ids]
    # view == "all": no additional filter

    # Default to today if no date_from specified
    if not date_from:
        date_from = date.today().isoformat()

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
    elif sort == "date_desc":
        events.sort(key=lambda e: e.date, reverse=True)
    else:
        events.sort(key=lambda e: e.date)

    # Build event score breakdowns for tooltips
    event_breakdowns: dict[int, dict] = {}
    for event in events:
        event_matches = matches_by_event.get(event.id, [])
        rows = []
        for m in event_matches:
            contrib = round(m["effective_score"] * m["confidence"] / 100.0, 1)
            rows.append({
                "name": m["artist"].name,
                "artist_id": m["artist"].id,
                "contrib": contrib,
            })
        rows.sort(key=lambda r: r["contrib"], reverse=True)
        event_breakdowns[event.id] = {
            "rows": rows,
            "total": event_scores.get(event.id, 0),
        }

    # Empty-state distinguishers for the Saved view
    saved_total = len(saved_event_ids)
    saved_upcoming_total = 0
    if view == "saved" and saved_total and not events:
        today_d = date.today()
        saved_upcoming_total = sum(
            1 for e in session.exec(
                select(Event).where(Event.id.in_(saved_event_ids))
            ).all()
            if e.date.date() >= today_d
        )

    return templates.TemplateResponse(
        request,
        "events.html",
        {
            "events": events,
            "matches_by_event": matches_by_event,
            "sources_by_event": sources_by_event,
            "event_scores": event_scores,
            "event_breakdowns": event_breakdowns,
            "saved_event_ids": saved_event_ids,
            "q": q,
            "sort": sort,
            "view": view,
            "total_count": len(events),
            "saved_total": saved_total,
            "saved_upcoming_total": saved_upcoming_total,
            "date_from": date_from,
            "date_to": date_to,
            "city": city,
            "city_options": CITY_CONFIG,
            "current_user": user,
        },
    )


@router.get("/event/{event_id}", response_class=HTMLResponse)
def show_event(
    request: Request,
    event_id: int,
    session: Session = Depends(get_session),
):
    user = get_current_user(request, session)
    if not user:
        return RedirectResponse("/login", status_code=303)

    event = session.get(Event, event_id)
    if not event:
        return RedirectResponse("/events", status_code=303)

    # Saved state for this event (drives the star button) + the user's full saved
    # set (used to stripe rows in the Similar events table below).
    saved_event_ids: set[int] = set(session.exec(
        select(UserEvent.event_id).where(UserEvent.user_id == user.id)
    ).all())
    is_saved = event_id in saved_event_ids

    # Load sources for this event
    sources = session.exec(
        select(EventSource).where(EventSource.event_id == event_id)
    ).all()

    # Load matches for this event
    matches = session.exec(
        select(Match).where(Match.event_id == event_id)
    ).all()

    artists_by_id = {}
    if matches:
        artist_ids = [m.artist_id for m in matches]
        artists_by_id = {
            a.id: a for a in session.exec(
                select(Artist).where(Artist.id.in_(artist_ids))
            ).all()
        }

    # Load user's artist data for matched artists only
    ua_by_artist_id = {}
    if matches:
        ua_by_artist_id = {
            ua.artist_id: ua
            for ua in session.exec(
                select(UserArtist).where(
                    UserArtist.user_id == user.id,
                    UserArtist.artist_id.in_(artist_ids),
                )
            ).all()
        }

    # Build match info, score breakdown, and normalised name lookup
    matched_artist_ids = set()
    breakdown_rows = []
    matched_names_norm = {}
    for m in matches:
        artist = artists_by_id.get(m.artist_id)
        ua = ua_by_artist_id.get(m.artist_id)
        if not artist or not ua or ua.excluded:
            continue
        matched_artist_ids.add(m.artist_id)
        matched_names_norm[normalise_name(m.matched_name)] = artist
        contrib = round(ua.effective_score * m.confidence / 100.0, 1)
        breakdown_rows.append({
            "name": artist.name,
            "artist_id": artist.id,
            "contrib": contrib,
        })
    breakdown_rows.sort(key=lambda r: r["contrib"], reverse=True)

    event_score = compute_event_score([
        (ua_by_artist_id[m.artist_id].effective_score, m.confidence)
        for m in matches
        if m.artist_id in matched_artist_ids
    ])

    # Look up all lineup artists by normalised name
    lineup_names = event.lineup_parsed or []
    norms_by_name = {n: normalise_name(n) for n in lineup_names}
    lineup_norms = [norm for norm in norms_by_name.values() if norm]
    resolved_artists = {}
    if lineup_norms:
        resolved_artists = {
            a.name_normalised: a
            for a in session.exec(
                select(Artist).where(Artist.name_normalised.in_(lineup_norms))
            ).all()
        }

    lineup = []
    for name in lineup_names:
        norm = norms_by_name.get(name, "")
        matched_artist = matched_names_norm.get(norm)
        resolved_artist = matched_artist or resolved_artists.get(norm)
        lineup.append({
            "name": name,
            "artist": resolved_artist,
            "is_matched": matched_artist is not None,
        })
    # Sort: matched first, then resolved, then unresolved
    lineup.sort(key=lambda x: (not x["is_matched"], x["artist"] is None, x["name"].lower()))

    # Similar events: other events sharing 2+ matched artists
    similar_events = []
    if matched_artist_ids:
        other_matches = session.exec(
            select(Match).where(
                Match.artist_id.in_(matched_artist_ids),
                Match.event_id != event_id,
            )
        ).all()
        # Group by event, count shared artists
        event_shared: dict[int, set[int]] = {}
        for m in other_matches:
            event_shared.setdefault(m.event_id, set()).add(m.artist_id)
        # Only events sharing 2+ artists (or 1 if few matches)
        min_shared = 1 if len(matched_artist_ids) <= 2 else 2
        similar_ids = [
            eid for eid, aids in event_shared.items()
            if len(aids) >= min_shared
        ]
        if similar_ids:
            today = date.today()
            similar_raw = session.exec(
                select(Event).where(
                    Event.id.in_(similar_ids),
                    Event.date >= today,
                )
            ).all()
            similar_events = [
                {
                    "event": e,
                    "shared_count": len(event_shared[e.id]),
                    "shared_names": [
                        artists_by_id[aid].name
                        for aid in event_shared[e.id]
                        if aid in artists_by_id
                    ],
                }
                for e in similar_raw
            ]
            similar_events.sort(key=lambda x: x["shared_count"], reverse=True)
            similar_events = similar_events[:10]

    return templates.TemplateResponse(
        request,
        "event_detail.html",
        {
            "event": event,
            "sources": sources,
            "lineup": lineup,
            "breakdown_rows": breakdown_rows,
            "event_score": event_score,
            "similar_events": similar_events,
            "is_saved": is_saved,
            "saved_event_ids": saved_event_ids,
            "current_user": user,
        },
    )


def _login_redirect(request: Request):
    """Redirect to /login, using HX-Redirect for HTMX requests so the browser navigates."""
    if request.headers.get("HX-Request"):
        resp = Response(status_code=204)
        resp.headers["HX-Redirect"] = "/login"
        return resp
    return RedirectResponse("/login", status_code=303)


def _render_save_button(request: Request, event: Event, is_saved: bool):
    return templates.TemplateResponse(
        request,
        "_save_button.html",
        {"event": event, "is_saved": is_saved},
    )


@router.post("/event/{event_id}/save", response_class=HTMLResponse)
def save_event(
    event_id: int,
    request: Request,
    session: Session = Depends(get_session),
):
    user = get_current_user(request, session)
    if not user:
        return _login_redirect(request)

    event = session.get(Event, event_id)
    if not event:
        return RedirectResponse("/events", status_code=303)

    existing = session.exec(
        select(UserEvent).where(
            UserEvent.user_id == user.id,
            UserEvent.event_id == event_id,
        )
    ).first()
    if not existing:
        session.add(UserEvent(user_id=user.id, event_id=event_id))
        session.commit()

    return _render_save_button(request, event, is_saved=True)


@router.post("/event/{event_id}/unsave", response_class=HTMLResponse)
def unsave_event(
    event_id: int,
    request: Request,
    session: Session = Depends(get_session),
):
    user = get_current_user(request, session)
    if not user:
        return _login_redirect(request)

    event = session.get(Event, event_id)
    if not event:
        return RedirectResponse("/events", status_code=303)

    existing = session.exec(
        select(UserEvent).where(
            UserEvent.user_id == user.id,
            UserEvent.event_id == event_id,
        )
    ).first()
    if existing:
        session.delete(existing)
        session.commit()

    return _render_save_button(request, event, is_saved=False)
