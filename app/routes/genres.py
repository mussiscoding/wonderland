from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import func
from sqlmodel import Session, select

from app.auth import get_current_user
from app.database import get_session
from app.models import ArtistGenre, GenreClassification, Artist, UserArtist
from app.scoring import rescore_all_users, get_genre_map
from app.templating import templates

router = APIRouter()


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

    # Auto-populate from existing ArtistGenre if the classification table is empty
    if session.exec(select(GenreClassification).limit(1)).first() is None:
        existing_genres = session.exec(
            select(ArtistGenre.genre_name).distinct()
        ).all()
        for genre_name in existing_genres:
            session.add(GenreClassification(name=genre_name))
        if existing_genres:
            session.commit()

    genres = session.exec(
        select(GenreClassification).order_by(GenreClassification.name)
    ).all()

    if q:
        q_lower = q.lower()
        genres = [g for g in genres if q_lower in g.name]

    if category:
        genres = [g for g in genres if g.category == category]

    # Count artists per genre via junction table
    count_results = session.exec(
        select(ArtistGenre.genre_name, func.count(ArtistGenre.artist_id))
        .group_by(ArtistGenre.genre_name)
    ).all()
    genre_counts = dict(count_results)

    if sort == "artists_desc":
        genres.sort(key=lambda g: genre_counts.get(g.name, 0), reverse=True)
    elif sort == "artists_asc":
        genres.sort(key=lambda g: genre_counts.get(g.name, 0))

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

    genre = session.exec(
        select(GenreClassification).where(GenreClassification.name == genre_name)
    ).first()

    # Single joined query: artists with this genre + their user scores
    results = session.exec(
        select(Artist, UserArtist)
        .join(ArtistGenre, ArtistGenre.artist_id == Artist.id)
        .outerjoin(
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
    genre_map = get_genre_map(session)

    return templates.TemplateResponse(
        request,
        "genre_detail.html",
        {
            "genre_name": genre_name,
            "genre": genre,
            "artists": matched,
            "genre_map": genre_map,
            "current_user": user,
        },
    )


@router.post("/genres/{genre_id}/classify")
def classify_genre(
    request: Request,
    genre_id: int,
    category: str = Form(),
    session: Session = Depends(get_session),
):
    genre = session.get(GenreClassification, genre_id)
    if genre and category in ("dance", "adjacent", "other", "unclassified"):
        genre.category = category
        session.add(genre)
        session.commit()

        rescore_all_users(session)

    # If HTMX request, return just the updated row
    if request.headers.get("HX-Request"):
        artist_count = session.exec(
            select(func.count(ArtistGenre.id))
            .where(ArtistGenre.genre_name == genre.name)
        ).one()
        return templates.TemplateResponse(
            request,
            "genre_row.html",
            {"genre": genre, "artist_count": artist_count},
        )

    # Otherwise redirect back to genres page
    return RedirectResponse("/genres", status_code=303)


@router.post("/genres/bulk-classify")
def bulk_classify(
    category: str = Form(),
    genre_ids: str = Form(""),
    session: Session = Depends(get_session),
):
    if category not in ("dance", "adjacent", "other", "unclassified"):
        return RedirectResponse("/genres", status_code=303)

    ids = [int(x) for x in genre_ids.split(",") if x.strip()]
    for gid in ids:
        genre = session.get(GenreClassification, gid)
        if genre:
            genre.category = category
            session.add(genre)
    session.commit()

    rescore_all_users(session)

    return RedirectResponse("/genres", status_code=303)
