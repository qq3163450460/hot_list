from __future__ import annotations

from collections.abc import Iterable

from spider.base import BaseSpider
from tools.exceptions import PlatformNotFoundError


class SpiderRegistry:
    """Central registry for platform adapters keyed by unique platform name."""

    def __init__(self, spiders: Iterable[BaseSpider] = ()) -> None:
        self._spiders: dict[str, BaseSpider] = {}
        for spider in spiders:
            self.register(spider)

    def register(self, spider: BaseSpider) -> None:
        """Register one adapter and reject duplicate platform identifiers."""

        if spider.platform in self._spiders:
            raise ValueError(f"Platform already registered: {spider.platform}")
        self._spiders[spider.platform] = spider

    def get(self, platform: str) -> BaseSpider:
        """Return a registered adapter or raise a domain-specific error."""

        try:
            return self._spiders[platform]
        except KeyError as exc:
            raise PlatformNotFoundError(f"Unknown platform: {platform}") from exc

    def all(self) -> tuple[BaseSpider, ...]:
        """Return all registered adapters in deterministic registration order."""

        return tuple(self._spiders.values())

    def enabled(self) -> tuple[BaseSpider, ...]:
        """Return adapters currently enabled by configuration."""

        return tuple(spider for spider in self._spiders.values() if spider.enabled)

    def platforms(self) -> tuple[str, ...]:
        """Return all registered platform names."""

        return tuple(self._spiders)
