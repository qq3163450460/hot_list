from __future__ import annotations

import asyncio
import logging

from spider.models import AggregateResult, PlatformResult
from tools.exceptions import PlatformDisabledError, SpiderError
from tools.registry import SpiderRegistry

logger = logging.getLogger(__name__)


class HotListService:
    """Collect platform hot lists through the shared spider registry."""

    def __init__(self, registry: SpiderRegistry) -> None:
        self.registry = registry

    async def collect_platform(self, platform: str) -> PlatformResult:
        """Collect one enabled platform and preserve domain failures in the result."""

        spider = self.registry.get(platform)
        if not spider.enabled:
            raise PlatformDisabledError(f"Platform is disabled: {platform}")

        try:
            items = await spider.fetch()
            return PlatformResult(platform=platform, items=items)
        except SpiderError as exc:
            logger.warning("Collection failed platform=%s error=%s", platform, exc)
            return PlatformResult(platform=platform, error=str(exc))
        except Exception as exc:
            logger.exception("Unexpected collection failure platform=%s", platform)
            return PlatformResult(
                platform=platform,
                error=f"Unexpected collection failure: {type(exc).__name__}",
            )

    async def collect_all(self) -> AggregateResult:
        """Collect all enabled platforms concurrently without cross-platform failure propagation."""

        results = await asyncio.gather(
            *(self.collect_platform(spider.platform) for spider in self.registry.enabled())
        )
        return AggregateResult(results=list(results))

    def platform_statuses(self) -> list[dict[str, str | bool]]:
        """Return registered platform names and their configured availability."""

        return [
            {"platform": spider.platform, "enabled": spider.enabled}
            for spider in self.registry.all()
        ]
