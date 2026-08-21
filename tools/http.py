from __future__ import annotations

import logging
from collections.abc import Mapping
from typing import Any

import httpx

from tools.config import Settings
from tools.exceptions import (
    SpiderAuthenticationError,
    SpiderRateLimitError,
    SpiderRequestError,
)
from tools.limiter import AsyncRateLimiter
from tools.retry import build_async_retrying

logger = logging.getLogger(__name__)


class HttpClient:
    """Shared asynchronous HTTP client with rate limiting and retry handling."""

    def __init__(
        self,
        settings: Settings,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self._settings = settings
        self._owns_client = client is None
        self._client = client or httpx.AsyncClient(
            timeout=httpx.Timeout(settings.request_timeout_seconds),
            follow_redirects=True,
            headers={"User-Agent": settings.user_agent},
        )
        self._limiter = AsyncRateLimiter(settings.requests_per_second)

    async def __aenter__(self) -> HttpClient:
        return self

    async def __aexit__(self, *_: object) -> None:
        await self.aclose()

    async def aclose(self) -> None:
        """Close the underlying client only when this instance created it."""

        if self._owns_client:
            await self._client.aclose()

    async def get_json(
        self,
        *,
        platform: str,
        url: str,
        params: Mapping[str, Any] | None = None,
        headers: Mapping[str, str] | None = None,
        cookies: dict[str, str] | None = None,
    ) -> Any:
        """Perform a rate-limited GET request and decode its JSON response."""

        return await self._request(
            method="GET",
            platform=platform,
            url=url,
            params=params,
            headers=headers,
            cookies=cookies,
        )

    async def post_json(
        self,
        *,
        platform: str,
        url: str,
        params: Mapping[str, Any] | None = None,
        headers: Mapping[str, str] | None = None,
        cookies: dict[str, str] | None = None,
        data: Mapping[str, Any] | None = None,
        json: Any = None,
    ) -> Any:
        """Perform a rate-limited POST request and decode its JSON response."""

        return await self._request(
            method="POST",
            platform=platform,
            url=url,
            params=params,
            headers=headers,
            cookies=cookies,
            data=data,
            json=json,
        )

    async def get_text(
        self,
        *,
        platform: str,
        url: str,
        params: Mapping[str, Any] | None = None,
        headers: Mapping[str, str] | None = None,
        cookies: dict[str, str] | None = None,
    ) -> str:
        """Perform a rate-limited GET request and return its text response."""

        retrying = build_async_retrying(
            max_attempts=self._settings.max_retries,
            min_wait_seconds=self._settings.retry_min_wait_seconds,
            max_wait_seconds=self._settings.retry_max_wait_seconds,
            before_sleep=lambda state: logger.warning(
                "Retrying platform=%s attempt=%s",
                platform,
                state.attempt_number,
            ),
        )

        try:
            async for attempt in retrying:
                with attempt:
                    await self._limiter.wait()
                    response = await self._client.get(
                        url,
                        params=params,
                        headers=headers,
                        cookies=cookies,
                    )
                    response.raise_for_status()
                    return response.text
        except httpx.HTTPStatusError as exc:
            status_code = exc.response.status_code
            if status_code == 429:
                raise SpiderRateLimitError(
                    platform,
                    f"Platform rate limit reached (HTTP {status_code})",
                ) from exc
            if status_code in {401, 403}:
                raise SpiderAuthenticationError(
                    platform,
                    f"Platform authentication rejected (HTTP {status_code})",
                ) from exc
            raise SpiderRequestError(
                platform,
                f"Platform request failed (HTTP {status_code})",
            ) from exc
        except (httpx.TimeoutException, httpx.NetworkError) as exc:
            raise SpiderRequestError(platform, "Platform request failed after retries") from exc

        raise SpiderRequestError(platform, "Platform request did not return a response")

    async def _request(
        self,
        *,
        method: str,
        platform: str,
        url: str,
        params: Mapping[str, Any] | None = None,
        headers: Mapping[str, str] | None = None,
        cookies: dict[str, str] | None = None,
        data: Mapping[str, Any] | None = None,
        json: Any = None,
    ) -> Any:
        """Apply shared rate limiting, retries, and error mapping to a JSON request."""

        retrying = build_async_retrying(
            max_attempts=self._settings.max_retries,
            min_wait_seconds=self._settings.retry_min_wait_seconds,
            max_wait_seconds=self._settings.retry_max_wait_seconds,
            before_sleep=lambda state: logger.warning(
                "Retrying platform=%s attempt=%s",
                platform,
                state.attempt_number,
            ),
        )

        try:
            async for attempt in retrying:
                with attempt:
                    await self._limiter.wait()
                    response = await self._client.request(
                        method,
                        url,
                        params=params,
                        headers=headers,
                        cookies=cookies,
                        data=data,
                        json=json,
                    )
                    response.raise_for_status()
                    return response.json()
        except httpx.HTTPStatusError as exc:
            status_code = exc.response.status_code
            if status_code == 429:
                raise SpiderRateLimitError(
                    platform,
                    f"Platform rate limit reached (HTTP {status_code})",
                ) from exc
            if status_code in {401, 403}:
                raise SpiderAuthenticationError(
                    platform,
                    f"Platform authentication rejected (HTTP {status_code})",
                ) from exc
            raise SpiderRequestError(
                platform,
                f"Platform request failed (HTTP {status_code})",
            ) from exc
        except (httpx.TimeoutException, httpx.NetworkError) as exc:
            raise SpiderRequestError(platform, "Platform request failed after retries") from exc
        except ValueError as exc:
            raise SpiderRequestError(platform, "Platform returned invalid JSON") from exc

        raise SpiderRequestError(platform, "Platform request did not return a response")
