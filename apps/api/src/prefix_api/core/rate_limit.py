"""Sliding-window rate limits for abuse-prone endpoints (guest login, password login, assistant).

The window is kept in this process only. That is correct for one API process, which is what
the demo and single-node deployments run. Several API workers would each keep their own
count, so a shared store (for example Redis) is the first item for a multi-node deployment
(see docs/DEPLOYMENT.md).
"""

import threading
import time
from collections import defaultdict, deque
from collections.abc import Callable

from prefix_api.domain.errors import RateLimitedError


class RateLimiter:
    def __init__(self, clock: Callable[[], float] = time.monotonic) -> None:
        self._clock = clock
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def check(self, key: str, *, limit: int, window_seconds: float) -> None:
        """Record one hit for ``key``; raise when it already made ``limit`` hits in the window."""
        with self._lock:
            self._refuse_if_full(key, limit=limit, window_seconds=window_seconds)
            self._hits[key].append(self._clock())

    def refuse_if_full(self, key: str, *, limit: int, window_seconds: float) -> None:
        """Raise when ``key`` already has ``limit`` hits in the window, without recording one."""
        with self._lock:
            self._refuse_if_full(key, limit=limit, window_seconds=window_seconds)

    def record(self, key: str) -> None:
        """Record one hit for ``key`` without checking the limit, for failures found afterwards."""
        with self._lock:
            self._hits[key].append(self._clock())

    def _refuse_if_full(self, key: str, *, limit: int, window_seconds: float) -> None:
        now = self._clock()
        hits = self._hits[key]
        while hits and hits[0] <= now - window_seconds:
            hits.popleft()
        if len(hits) >= limit:
            retry_after = int(hits[0] + window_seconds - now) + 1
            raise RateLimitedError(f"Too many requests. Try again in {retry_after} seconds")
