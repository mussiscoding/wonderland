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


templates.env.globals["is_admin_user"] = is_admin_user
