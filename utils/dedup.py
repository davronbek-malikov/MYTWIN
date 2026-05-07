"""
Deduplication cache for files and voice messages.
Prevents the same Telegram file from being processed twice within the window.
"""
import time

_WINDOW_SECONDS = 300  # 5 minutes
_cache: dict[tuple, float] = {}


def is_duplicate(user_id: int, file_unique_id: str) -> bool:
    """Return True if this file was already processed recently."""
    _evict()
    key = (user_id, file_unique_id)
    if key in _cache:
        return True
    _cache[key] = time.time()
    return False


def _evict() -> None:
    cutoff = time.time() - _WINDOW_SECONDS
    stale = [k for k, t in _cache.items() if t < cutoff]
    for k in stale:
        del _cache[k]
