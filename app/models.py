from datetime import datetime
from typing import Optional

from sqlmodel import Field, SQLModel, JSON, Column


class Artist(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    spotify_id: str = Field(unique=True, index=True)
    name: str
    genres: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    auto_score: float = Field(default=0.0)
    manual_score: Optional[float] = Field(default=None)
    excluded: bool = Field(default=False)
    source_signals: dict = Field(default_factory=dict, sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    @property
    def effective_score(self) -> float:
        if self.manual_score is not None:
            return self.manual_score
        return self.auto_score


class GenreClassification(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(unique=True, index=True)
    category: str = Field(default="unclassified")  # "dance", "adjacent", "other", "unclassified"


class Event(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    title: str
    date: datetime
    venue_name: str
    venue_location: Optional[str] = None
    lineup_raw: Optional[str] = None
    lineup_parsed: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    dedupe_key: str = Field(index=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class EventSource(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    event_id: int = Field(foreign_key="event.id", index=True)
    source_name: str  # "bandsintown", "ra", "skiddle", "dice"
    source_id: Optional[str] = None
    source_url: Optional[str] = None
    ticket_url: Optional[str] = None
    price: Optional[str] = None
    last_fetched: datetime = Field(default_factory=datetime.utcnow)


class Match(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    artist_id: int = Field(foreign_key="artist.id", index=True)
    event_id: int = Field(foreign_key="event.id", index=True)
    confidence: float
    match_type: str  # "exact", "fuzzy", "alias"
    matched_name: str  # the string that actually matched
