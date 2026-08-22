from __future__ import annotations

import asyncio
import time
from collections.abc import Callable, Coroutine
from typing import Any, TypeVar, cast

T = TypeVar("T")


class SingleFlightCache:
    """TTL cache that collapses concurrent loads of the same key into one call.

    Designed for the read-heavy hot-list endpoints: while one loader task is
    running, every other caller awaits the same task instead of issuing its own
    database query. Values are shared between callers, so loaders must return
    effectively immutable results.
    """

    def __init__(self, ttl_seconds: float) -> None:
        self.ttl_seconds = ttl_seconds
        self._entries: dict[str, tuple[float, Any]] = {}
        self._in_flight: dict[str, asyncio.Task[Any]] = {}

    async def get_or_load(
        self,
        key: str,
        loader: Callable[[], Coroutine[Any, Any, T]],
    ) -> T:
        """Return the cached value, or run ``loader`` once and cache the result."""

        entry = self._entries.get(key)
        if entry is not None and entry[0] > time.monotonic():
            return cast(T, entry[1])

        in_flight = self._in_flight.get(key)
        if in_flight is not None:
            return cast(T, await in_flight)

        task = asyncio.create_task(loader())
        self._in_flight[key] = task
        try:
            value = await task
        except BaseException:
            if self._in_flight.get(key) is task:
                del self._in_flight[key]
            raise
        if self._in_flight.get(key) is task:
            del self._in_flight[key]
        self._entries[key] = (time.monotonic() + self.ttl_seconds, value)
        return value

    def invalidate(self) -> None:
        """Drop every cached entry so subsequent reads hit the loader again."""

        self._entries.clear()
