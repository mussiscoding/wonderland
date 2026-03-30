import logging
import time
from datetime import datetime

logger = logging.getLogger(__name__)


def parse_iso_datetime(dt_str: str) -> datetime | None:
    """Parse an ISO datetime or date string, returning None on failure."""
    if not dt_str:
        return None
    for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(dt_str[:19] if "T" in fmt else dt_str[:10], fmt)
        except ValueError:
            continue
    return None


class RateLimiter:
    """Simple rate limiter: minimum delay between requests."""

    def __init__(self, min_delay: float = 0.5):
        self.min_delay = min_delay
        self._last_request = 0.0

    def wait(self):
        elapsed = time.time() - self._last_request
        if elapsed < self.min_delay:
            time.sleep(self.min_delay - elapsed)
        self._last_request = time.time()
