from __future__ import annotations

from collections.abc import Callable
from typing import Any

import httpx
from tenacity import AsyncRetrying, retry_if_exception, stop_after_attempt, wait_exponential


def is_retryable_exception(exc: BaseException) -> bool:
    """Return whether a failed request is safe to retry."""

    if isinstance(exc, (httpx.TimeoutException, httpx.NetworkError)):
        return True
    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.status_code == 429 or exc.response.status_code >= 500
    return False


def build_async_retrying(
    *,
    max_attempts: int,
    min_wait_seconds: float,
    max_wait_seconds: float,
    before_sleep: Callable[[Any], None] | None = None,
) -> AsyncRetrying:
    """Build the shared async retry policy used by all platform adapters."""

    return AsyncRetrying(
        retry=retry_if_exception(is_retryable_exception),
        stop=stop_after_attempt(max_attempts),
        wait=wait_exponential(min=min_wait_seconds, max=max_wait_seconds),
        before_sleep=before_sleep,
        reraise=True,
    )
