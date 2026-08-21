from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from typing import Any

from database.repository import HotRepository
from spider.models import PlatformResult
from spider.service import HotListService
from tools.timezone import local_now, snapshot_hour

logger = logging.getLogger(__name__)


class CollectionService:
    """Coordinate platform collection and idempotent hourly persistence."""

    def __init__(
        self,
        hot_list_service: HotListService,
        repository: HotRepository,
        timezone_name: str,
    ) -> None:
        self.hot_list_service = hot_list_service
        self.repository = repository
        self.timezone_name = timezone_name

    async def collect_and_save(
        self,
        platform: str | None = None,
        now: datetime | None = None,
    ) -> list[dict[str, Any]]:
        """Collect requested platforms and independently persist each result."""

        current_hour = snapshot_hour(
            now or local_now(self.timezone_name),
            self.timezone_name,
        )
        if platform is None:
            aggregate = await self.hot_list_service.collect_all()
            results = aggregate.results
        else:
            results = [await self.hot_list_service.collect_platform(platform)]

        return await asyncio.gather(
            *(self._save_isolated(result, current_hour) for result in results)
        )

    async def refresh_platform_current_hour(
        self,
        platform: str,
        now: datetime | None = None,
    ) -> dict[str, Any]:
        """Collect and atomically refresh only one platform's current-hour snapshot."""

        current_hour = snapshot_hour(
            now or local_now(self.timezone_name),
            self.timezone_name,
        )
        result = await self.hot_list_service.collect_platform(platform)
        snapshot = await self.repository.replace_result(result, current_hour)
        return {
            "platform": result.platform,
            "status": snapshot.status,
            "refreshed": True,
            "snapshot_id": snapshot.id,
            "item_count": snapshot.item_count,
            "error": snapshot.error,
        }

    async def collect_missing_current_hour(
        self,
        now: datetime | None = None,
    ) -> list[dict[str, Any]]:
        """Collect only enabled platforms missing a snapshot for the current hour."""

        current_hour = snapshot_hour(
            now or local_now(self.timezone_name),
            self.timezone_name,
        )
        platforms = [
            str(status["platform"])
            for status in self.hot_list_service.platform_statuses()
            if bool(status["enabled"])
            and not await self.repository.has_snapshot(str(status["platform"]), current_hour)
        ]
        results = await asyncio.gather(
            *(self.hot_list_service.collect_platform(platform) for platform in platforms)
        )
        return await asyncio.gather(
            *(self._save_isolated(result, current_hour) for result in results)
        )

    async def _save_isolated(
        self,
        result: PlatformResult,
        current_hour: datetime,
    ) -> dict[str, Any]:
        try:
            snapshot, inserted = await self.repository.save_result(result, current_hour)
            return {
                "platform": result.platform,
                "status": snapshot.status,
                "inserted": inserted,
                "snapshot_id": snapshot.id,
                "item_count": snapshot.item_count,
                "error": snapshot.error,
            }
        except Exception as exc:
            logger.exception("Snapshot persistence failed platform=%s", result.platform)
            return {
                "platform": result.platform,
                "status": "persistence_failed",
                "inserted": False,
                "snapshot_id": None,
                "item_count": 0,
                "error": f"{type(exc).__name__}: {exc}",
            }
