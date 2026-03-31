import logging
import re
from datetime import datetime

from sqlmodel import Session, select

from app.models import Event, EventSource
from app.scrapers.dice import fetch_london_events as fetch_dice_events
from app.scrapers.ra import fetch_london_events as fetch_ra_events
from app.scrapers.skiddle import fetch_london_events as fetch_skiddle_events

logger = logging.getLogger(__name__)

# Per-user event progress tracking: user_id -> progress dict
event_progress: dict[int, dict] = {}


def _get_event_progress(user_id: int) -> dict:
    """Get or create event progress dict for a user."""
    if user_id not in event_progress:
        event_progress[user_id] = {
            "running": False,
            "step": "",
            "current": 0,
            "total": 0,
            "done": False,
        }
    return event_progress[user_id]


def _dedupe_key(venue_name: str, date: datetime) -> str:
    """Normalise venue + date into a deduplication key."""
    normalised = re.sub(r"[^a-z0-9]", "", venue_name.lower())
    date_str = date.strftime("%Y-%m-%d")
    return f"{normalised}_{date_str}"


def fetch_all_events(session: Session, user_id: int) -> dict:
    """Fetch London events from all sources and store them.

    Returns a summary dict.
    """
    progress = _get_event_progress(user_id)
    progress.update(running=True, step="Fetching events...", current=0, total=0, done=False)

    # Load existing events for dedup
    existing_events = {e.dedupe_key: e for e in session.exec(select(Event)).all()}

    new_events = 0
    updated_events = 0
    total_fetched = 0

    # Fetch from each source
    sources = [
        ("RA", fetch_ra_events),
        ("Skiddle", fetch_skiddle_events),
        ("Dice", fetch_dice_events),
    ]

    for source_label, fetch_fn in sources:
        progress["step"] = f"Fetching {source_label} events..."
        logger.info(f"Fetching London events from {source_label}...")

        raw_events = fetch_fn(days=60, progress=progress)
        total_fetched += len(raw_events)

        progress["step"] = f"Storing {len(raw_events)} {source_label} events..."
        progress["total"] = len(raw_events)

        deferred_sources = []

        for i, raw in enumerate(raw_events):
            progress["current"] = i + 1
            key = _dedupe_key(raw["venue_name"], raw["date"])

            if key in existing_events:
                event = existing_events[key]
                # Merge lineup
                existing_parsed = set(event.lineup_parsed or [])
                new_parsed = set(raw.get("lineup_parsed") or [])
                merged = list(existing_parsed | new_parsed)
                if len(merged) > len(existing_parsed):
                    event.lineup_parsed = merged
                    event.lineup_raw = ", ".join(merged)
                    session.add(event)
                updated_events += 1
            else:
                event = Event(
                    title=raw["title"],
                    date=raw["date"],
                    venue_name=raw["venue_name"],
                    venue_location=raw.get("venue_location"),
                    lineup_raw=raw.get("lineup_raw"),
                    lineup_parsed=raw.get("lineup_parsed", []),
                    dedupe_key=key,
                )
                session.add(event)
                existing_events[key] = event
                new_events += 1

            deferred_sources.append((event, raw))

        # Single flush to assign IDs for all new events, then add sources
        session.flush()
        for event, raw in deferred_sources:
            _ensure_source(session, event, raw)

        session.commit()

    progress.update(running=False, step="Done", done=True)

    summary = {
        "total_fetched": total_fetched,
        "new_events": new_events,
        "updated_events": updated_events,
    }
    logger.info(f"Event fetch complete: {summary}")
    return summary


def _add_source(session: Session, event: Event, raw: dict):
    """Add an EventSource record."""
    source = EventSource(
        event_id=event.id,
        source_name=raw["source_name"],
        source_id=raw.get("source_id"),
        source_url=raw.get("source_url"),
        ticket_url=raw.get("ticket_url"),
        price=raw.get("price"),
    )
    session.add(source)


def _ensure_source(session: Session, event: Event, raw: dict):
    """Add source if it doesn't already exist for this event."""
    existing = session.exec(
        select(EventSource).where(
            EventSource.event_id == event.id,
            EventSource.source_name == raw["source_name"],
        )
    ).first()
    if not existing:
        _add_source(session, event, raw)
