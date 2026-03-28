import logging
import time

logger = logging.getLogger(__name__)


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
