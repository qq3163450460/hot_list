from __future__ import annotations

import asyncio
import time


class AsyncRateLimiter:
    """Serialize request starts and enforce a configurable minimum interval."""

    def __init__(self, requests_per_second: float) -> None:
        if requests_per_second <= 0:
            raise ValueError("requests_per_second must be greater than zero")
        self._minimum_interval = 1.0 / requests_per_second
        self._last_request_started_at = 0.0
        self._lock = asyncio.Lock()

    async def wait(self) -> None:
        """Wait until the next request may start without exceeding the rate."""

        async with self._lock:
            now = time.monotonic()
            remaining = self._minimum_interval - (now - self._last_request_started_at)
            if remaining > 0:
                await asyncio.sleep(remaining)
            self._last_request_started_at = time.monotonic()
