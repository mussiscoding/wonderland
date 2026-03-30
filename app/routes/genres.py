from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlmodel import Session, select

from app.database import get_session
from app.models import GenreClassification, Artist
from app.scoring import rescore_all_artists
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
    # Auto-populate from existing artists if the table is empty
    if session.exec(select(GenreClassification).limit(1)).first() is None:
        artists = session.exec(select(Artist)).all()
        seen: set[str] = set()
        for artist in artists:
            for g in (artist.genres or []):
                key = g.lower()
                if key not in seen:
                    session.add(GenreClassification(name=key))
                    seen.add(key)
        if seen:
            session.commit()

    genres = session.exec(
        select(GenreClassification).order_by(GenreClassification.name)
    ).all()

    if q:
        q_lower = q.lower()
        genres = [g for g in genres if q_lower in g.name]

    if category:
        genres = [g for g in genres if g.category == category]

    # Count artists per genre
    artists = session.exec(select(Artist)).all()
    genre_counts: dict[str, int] = {}
    for artist in artists:
        for g in (artist.genres or []):
            key = g.lower()
            genre_counts[key] = genre_counts.get(key, 0) + 1

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

        rescore_all_artists(session)

    # If HTMX request, return just the updated row
    if request.headers.get("HX-Request"):
        artists = session.exec(select(Artist)).all()
        artist_count = sum(
            1 for a in artists
            if any(g.lower() == genre.name for g in (a.genres or []))
        )
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

    rescore_all_artists(session)

    return RedirectResponse("/genres", status_code=303)


@router.post("/genres/rescore")
def rescore_artists(session: Session = Depends(get_session)):
    """Recompute all artist auto-scores using current genre classifications."""
    rescore_all_artists(session)
    return RedirectResponse("/artists", status_code=303)
