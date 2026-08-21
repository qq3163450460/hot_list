from __future__ import annotations

import logging
from zoneinfo import ZoneInfo

from apscheduler.schedulers.asyncio import AsyncIOScheduler  # type: ignore[import-untyped]
from apscheduler.triggers.cron import CronTrigger  # type: ignore[import-untyped]

from services.collection import CollectionService

logger = logging.getLogger(__name__)


class SchedulerService:
    """Manage hourly collection jobs and graceful scheduler shutdown."""

    def __init__(
        self,
        collection_service: CollectionService,
        timezone_name: str,
        cron_minute: int = 0,
    ) -> None:
        self.collection_service = collection_service
        self.timezone_name = timezone_name
        self.cron_minute = cron_minute
        self.scheduler = AsyncIOScheduler(timezone=ZoneInfo(timezone_name))

    def start(self) -> None:
        """Register the hourly collection job and start the scheduler once."""

        if self.scheduler.running:
            return
        self.scheduler.add_job(
            self.collection_service.collect_and_save,
            trigger=CronTrigger(
                minute=self.cron_minute,
                timezone=ZoneInfo(self.timezone_name),
            ),
            id="collect-hourly-hot-lists",
            replace_existing=True,
            coalesce=True,
            max_instances=1,
            misfire_grace_time=300,
        )
        self.scheduler.start()
        logger.info(
            "Hourly collection scheduler started minute=%s timezone=%s",
            self.cron_minute,
            self.timezone_name,
        )

    def shutdown(self) -> None:
        """Stop the scheduler without waiting for running jobs indefinitely."""

        if self.scheduler.running:
            self.scheduler.shutdown(wait=False)
            logger.info("Hourly collection scheduler stopped")
