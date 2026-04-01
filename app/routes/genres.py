import logging

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import func
from sqlmodel import Session, select

from app.auth import get_current_user
from app.config import settings
from app.database import get_session
from app.models import ArtistGenre, GenreClassification, Artist, UserArtist, UserGenreClassification
from app.scoring import get_genre_map, rescore_user_artists, seed_user_genres
from app.templating import templates

logger = logging.getLogger(__name__)

router = APIRouter()

VALID_CATEGORIES = ("high", "medium", "low", "unclassified")

_admin_ids = None


def _get_admin_ids() -> set[str]:
    global _admin_ids
    if _admin_ids is None:
        raw = settings.admin_spotify_ids
        _admin_ids = {s.strip() for s in raw.split(",") if s.strip()} if raw else set()
    return _admin_ids


def _is_admin(user) -> bool:
    return user.spotify_id in _get_admin_ids()


@router.get("/genres", response_class=HTMLResponse)
def list_genres(
    request: Request,
    q: str = "",
    category: str = "",
    sort: str = "",
    session: Session = Depends(get_session),
):
    user = get_current_user(request, session)
    if not user:
        return RedirectResponse("/login", status_code=303)

    # Query user's genre classifications
    genres = session.exec(
        select(UserGenreClassification)
        .where(UserGenreClassification.user_id == user.id)
        .order_by(UserGenreClassification.genre_name)
    ).all()

    if not genres:
        # No genres yet — show empty state
        return templates.TemplateResponse(
            request,
            "genres.html",
            {
                "genres": [],
                "genre_counts": {},
                "q": q,
                "category": category,
                "sort": sort,
                "total_count": 0,
                "current_user": user,
            },
        )

    if q:
        q_lower = q.lower()
        genres = [g for g in genres if q_lower in g.genre_name]

    if category:
        genres = [g for g in genres if g.category == category]

    # Count artists per genre scoped to user's library
    user_artist_ids = session.exec(
        select(UserArtist.artist_id).where(UserArtist.user_id == user.id)
    ).all()

    if user_artist_ids:
        count_results = session.exec(
            select(ArtistGenre.genre_name, func.count(ArtistGenre.artist_id))
            .where(ArtistGenre.artist_id.in_(user_artist_ids))
            .group_by(ArtistGenre.genre_name)
        ).all()
        genre_counts = dict(count_results)
    else:
        genre_counts = {}

    if sort == "artists_desc":
        genres.sort(key=lambda g: genre_counts.get(g.genre_name, 0), reverse=True)
    elif sort == "artists_asc":
        genres.sort(key=lambda g: genre_counts.get(g.genre_name, 0))

    return templates.TemplateResponse(
        request,
        "genres.html",
        {
            "genres": genres,
            "genre_counts": genre_counts,
            "q": q,
            "category": category,
            "sort": sort,
            "total_count": len(genres),
            "current_user": user,
        },
    )


@router.get("/genre/{genre_name:path}", response_class=HTMLResponse)
def genre_detail(
    request: Request,
    genre_name: str,
    session: Session = Depends(get_session),
):
    user = get_current_user(request, session)
    if not user:
        return RedirectResponse("/login", status_code=303)

    # Get user's classification for this genre
    ugc = session.exec(
        select(UserGenreClassification).where(
            UserGenreClassification.user_id == user.id,
            UserGenreClassification.genre_name == genre_name,
        )
    ).first()

    # Artists with this genre scoped to user's library
    results = session.exec(
        select(Artist, UserArtist)
        .join(ArtistGenre, ArtistGenre.artist_id == Artist.id)
        .join(
            UserArtist,
            (UserArtist.artist_id == Artist.id) & (UserArtist.user_id == user.id),
        )
        .where(ArtistGenre.genre_name == genre_name)
    ).all()

    # Load all genres per matched artist in one query (for genre tags display)
    artist_ids = [artist.id for artist, _ in results]
    if artist_ids:
        genre_rows = session.exec(
            select(ArtistGenre).where(ArtistGenre.artist_id.in_(artist_ids))
        ).all()
    else:
        genre_rows = []
    genres_by_artist: dict[int, list[str]] = {}
    for ag in genre_rows:
        genres_by_artist.setdefault(ag.artist_id, []).append(ag.genre_name)

    matched = []
    for artist, ua in results:
        matched.append({
            "id": artist.id,
            "name": artist.name,
            "genres": genres_by_artist.get(artist.id, []),
            "effective_score": ua.effective_score if ua else 0,
        })

    matched.sort(key=lambda a: a["effective_score"], reverse=True)
    genre_map = get_genre_map(session, user.id)

    return templates.TemplateResponse(
        request,
        "genre_detail.html",
        {
            "genre_name": genre_name,
            "genre": ugc,
            "artists": matched,
            "genre_map": genre_map,
            "current_user": user,
        },
    )


@router.post("/genres/{genre_name:path}/classify")
def classify_genre(
    request: Request,
    genre_name: str,
    category: str = Form(),
    session: Session = Depends(get_session),
):
    user = get_current_user(request, session)
    if not user:
        return RedirectResponse("/login", status_code=303)

    if category not in VALID_CATEGORIES:
        return RedirectResponse("/genres", status_code=303)

    # Update user's classification
    ugc = session.exec(
        select(UserGenreClassification).where(
            UserGenreClassification.user_id == user.id,
            UserGenreClassification.genre_name == genre_name,
        )
    ).first()

    if ugc:
        ugc.category = category
        ugc.user_modified = True
        session.add(ugc)
        session.commit()

        rescore_user_artists(session, user.id)

    # If HTMX request, return just the updated row
    if request.headers.get("HX-Request"):
        # Count user-scoped artists for this genre
        user_artist_ids = session.exec(
            select(UserArtist.artist_id).where(UserArtist.user_id == user.id)
        ).all()
        artist_count = session.exec(
            select(func.count(ArtistGenre.id))
            .where(
                ArtistGenre.genre_name == genre_name,
                ArtistGenre.artist_id.in_(user_artist_ids),
            )
        ).one() if user_artist_ids else 0
        return templates.TemplateResponse(
            request,
            "genre_row.html",
            {"genre": ugc, "artist_count": artist_count},
        )

    return RedirectResponse("/genres", status_code=303)


@router.post("/genres/bulk-classify")
def bulk_classify(
    request: Request,
    category: str = Form(),
    genre_names: str = Form(""),
    session: Session = Depends(get_session),
):
    user = get_current_user(request, session)
    if not user:
        return RedirectResponse("/login", status_code=303)

    if category not in VALID_CATEGORIES:
        return RedirectResponse("/genres", status_code=303)

    names = [x.strip() for x in genre_names.split(",") if x.strip()]
    for name in names:
        ugc = session.exec(
            select(UserGenreClassification).where(
                UserGenreClassification.user_id == user.id,
                UserGenreClassification.genre_name == name,
            )
        ).first()
        if ugc:
            ugc.category = category
            ugc.user_modified = True
            session.add(ugc)
    session.commit()

    rescore_user_artists(session, user.id)

    return RedirectResponse("/genres", status_code=303)


@router.post("/genres/reset")
def reset_genres(
    request: Request,
    session: Session = Depends(get_session),
):
    user = get_current_user(request, session)
    if not user:
        return RedirectResponse("/login", status_code=303)

    seed_user_genres(session, user.id, replace=True)
    rescore_user_artists(session, user.id)

    return RedirectResponse("/genres", status_code=303)


@router.post("/admin/genres/{genre_name:path}/classify")
def admin_classify_genre(
    request: Request,
    genre_name: str,
    category: str = Form(),
    session: Session = Depends(get_session),
):
    user = get_current_user(request, session)
    if not user or not _is_admin(user):
        raise HTTPException(status_code=403, detail="Admin access required")

    if category not in VALID_CATEGORIES:
        return RedirectResponse("/genres", status_code=303)

    # Update global template
    gc = session.exec(
        select(GenreClassification).where(GenreClassification.name == genre_name)
    ).first()
    if gc:
        gc.category = category
        session.add(gc)
        session.commit()

    # Propagate to users who haven't manually overridden this genre
    user_rows = session.exec(
        select(UserGenreClassification).where(
            UserGenreClassification.genre_name == genre_name,
            UserGenreClassification.user_modified == False,  # noqa: E712
        )
    ).all()

    affected_user_ids = set()
    for ugc in user_rows:
        ugc.category = category
        session.add(ugc)
        affected_user_ids.add(ugc.user_id)
    session.commit()

    # Rescore affected users
    for uid in affected_user_ids:
        rescore_user_artists(session, uid)

    return RedirectResponse("/genres", status_code=303)
