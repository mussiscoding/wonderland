from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import UniqueConstraint
from sqlmodel import Field, SQLModel, JSON, Column


def _utcnow():
    return datetime.now(timezone.utc)


class User(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    spotify_id: str = Field(unique=True, index=True)
    display_name: str = Field(default="")
    genre_profile: str = Field(default="dance")
    encrypted_token_info: Optional[str] = Field(default=None)
    created_at: datetime = Field(default_factory=_utcnow)
    updated_at: datetime = Field(
        default_factory=_utcnow,
        sa_column_kwargs={"onupdate": _utcnow},
    )


class Artist(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    spotify_id: str = Field(unique=True, index=True)
    name: str
    created_at: datetime = Field(default_factory=_utcnow)
    updated_at: datetime = Field(
        default_factory=_utcnow,
        sa_column_kwargs={"onupdate": _utcnow},
    )


class UserArtist(SQLModel, table=True):
    __table_args__ = (
        UniqueConstraint("user_id", "artist_id", name="uq_user_artist"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", index=True)
    artist_id: int = Field(foreign_key="artist.id", index=True)
    auto_score: float = Field(default=0.0)
    manual_score: Optional[float] = Field(default=None)
    excluded: bool = Field(default=False)
    source_signals: dict = Field(default_factory=dict, sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=_utcnow)
    updated_at: datetime = Field(
        default_factory=_utcnow,
        sa_column_kwargs={"onupdate": _utcnow},
    )

    @property
    def effective_score(self) -> float:
        if self.manual_score is not None:
            return self.manual_score
        return self.auto_score


class ArtistGenre(SQLModel, table=True):
    __table_args__ = (
        UniqueConstraint("artist_id", "genre_name", name="uq_artist_genre"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    artist_id: int = Field(foreign_key="artist.id", index=True)
    genre_name: str = Field(index=True)


class GenreClassification(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(unique=True, index=True)
    category: str = Field(default="unclassified")  # "high", "medium", "low", "unclassified"


class UserGenreClassification(SQLModel, table=True):
    __table_args__ = (
        UniqueConstraint("user_id", "genre_name", name="uq_user_genre"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", index=True)
    genre_name: str = Field(index=True)
    category: str = Field(default="unclassified")  # "high", "medium", "low", "unclassified"
    user_modified: bool = Field(default=False)
    created_at: datetime = Field(default_factory=_utcnow)
    updated_at: datetime = Field(
        default_factory=_utcnow,
        sa_column_kwargs={"onupdate": _utcnow},
    )


class Event(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    title: str
    date: datetime
    venue_name: str
    venue_location: Optional[str] = None
    lineup_raw: Optional[str] = None
    lineup_parsed: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    dedupe_key: str = Field(index=True)
    created_at: datetime = Field(default_factory=_utcnow)
    updated_at: datetime = Field(
        default_factory=_utcnow,
        sa_column_kwargs={"onupdate": _utcnow},
    )


class EventSource(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    event_id: int = Field(foreign_key="event.id", index=True)
    source_name: str  # "bandsintown", "ra", "skiddle", "dice"
    source_id: Optional[str] = None
    source_url: Optional[str] = None
    ticket_url: Optional[str] = None
    price: Optional[str] = None
    last_fetched: datetime = Field(default_factory=_utcnow)


class Match(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    artist_id: int = Field(foreign_key="artist.id", index=True)
    event_id: int = Field(foreign_key="event.id", index=True)
    confidence: float
    match_type: str  # "exact", "fuzzy", "alias"
    matched_name: str  # the string that actually matched
