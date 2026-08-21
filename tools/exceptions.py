from __future__ import annotations


class HotListError(Exception):
    """Base exception for the hot-list collection framework."""


class ConfigurationError(HotListError):
    """Raised when runtime configuration is invalid or incomplete."""


class PlatformNotFoundError(HotListError):
    """Raised when a requested platform is not registered."""


class PlatformDisabledError(HotListError):
    """Raised when collection is requested for a disabled platform."""


class SpiderError(HotListError):
    """Base exception for platform collection failures."""

    def __init__(self, platform: str, message: str) -> None:
        self.platform = platform
        super().__init__(message)


class SpiderRequestError(SpiderError):
    """Raised when an HTTP request cannot be completed successfully."""


class SpiderRateLimitError(SpiderRequestError):
    """Raised when a platform rejects a request because of rate limiting."""


class SpiderAuthenticationError(SpiderRequestError):
    """Raised when a platform requires authentication or rejects credentials."""


class SpiderResponseError(SpiderError):
    """Raised when a platform response is malformed or violates its contract."""
