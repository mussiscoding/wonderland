from fastapi.templating import Jinja2Templates

from app.config import settings

templates = Jinja2Templates(directory="app/templates")

_admin_ids = None


def _get_admin_ids() -> set[str]:
    global _admin_ids
    if _admin_ids is None:
        raw = settings.admin_spotify_ids
        _admin_ids = {s.strip() for s in raw.split(",") if s.strip()} if raw else set()
    return _admin_ids


def is_admin_user(user) -> bool:
    if not user:
        return False
    return user.spotify_id in _get_admin_ids()


_RUNNING_MSG = {"artists": "Syncing your Spotify…", "events": "Fetching events…"}
_ERROR_MSG = {
    "artists": "Library sync failed — please try again",
    "events": "Event fetch failed — please try again",
}


def _done_message(p: dict, kind: str) -> str:
    if kind == "artists":
        return (
            f"Synced {p.get('total_artists', 0)} artists "
            f"— you match {p.get('matched_events', 0)} upcoming events"
        )
    return (
        f"Events fetch complete — {p.get('new_events', 0)} new, "
        f"{p.get('updated_events', 0)} updated, {p.get('unchanged_events', 0)} unchanged"
    )


def _notice_from(p: dict | None, kind: str) -> dict | None:
    """Build a notice dict {kind, state, message} from a progress dict, or None."""
    if not p:
        return None
    if p.get("running"):
        return {"kind": kind, "state": "running", "message": _RUNNING_MSG[kind]}
    if not p.get("acknowledged", True):
        if p.get("error"):
            return {"kind": kind, "state": "error", "message": _ERROR_MSG[kind]}
        if p.get("done"):
            return {"kind": kind, "state": "done", "message": _done_message(p, kind)}
    return None


def notifications(user) -> list[dict]:
    """Active sync notices for this user: artists (all users) + events (admin only).

    Each notice is {"kind": "artists"|"events", "state": "running"|"done"|"error", ...}.
    """
    if not user:
        return []
    from app.events import event_progress
    from app.spotify import import_progress

    notices = []
    artists = _notice_from(import_progress.get(user.id), "artists")
    if artists:
        notices.append(artists)
    if is_admin_user(user):
        events = _notice_from(event_progress.get(user.id), "events")
        if events:
            notices.append(events)
    return notices


templates.env.globals["is_admin_user"] = is_admin_user
templates.env.globals["notifications"] = notifications
