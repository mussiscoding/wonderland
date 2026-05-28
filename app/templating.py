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


def fetch_notice(user) -> dict:
    """Render-time state for the fetch-complete toast (admin only).

    Returns {"state": "running"} while a fetch runs, {"state": "toast", "new", "updated"}
    when one finished and hasn't been dismissed, else {"state": ""}.
    """
    if not is_admin_user(user):
        return {"state": ""}
    from app.events import event_progress

    p = event_progress.get(user.id)
    if not p:
        return {"state": ""}
    if p.get("running"):
        return {"state": "running"}
    if p.get("done") and not p.get("acknowledged", True):
        return {
            "state": "toast",
            "new": p.get("new_events", 0),
            "updated": p.get("updated_events", 0),
            "unchanged": p.get("unchanged_events", 0),
        }
    return {"state": ""}


templates.env.globals["is_admin_user"] = is_admin_user
templates.env.globals["fetch_notice"] = fetch_notice
