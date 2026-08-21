from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.orm import selectinload

from database.models import HotItem, HotSnapshot
from spider.models import HotItem as DomainHotItem
from spider.models import PlatformResult
from tools.timezone import get_timezone, local_day_bounds


class HotRepository:
    """Persist and query hourly hot-list snapshots using portable ORM statements."""

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        timezone_name: str,
    ) -> None:
        self.session_factory = session_factory
        self.timezone_name = timezone_name

    async def save_result(
        self,
        result: PlatformResult,
        snapshot_hour: datetime,
    ) -> tuple[HotSnapshot, bool]:
        """Save one platform result once per hour and return whether it was inserted."""

        async with self.session_factory() as session:
            existing = await self._find_snapshot(session, result.platform, snapshot_hour)
            if existing is not None:
                return existing, False

            snapshot = HotSnapshot(
                platform=result.platform,
                snapshot_hour=snapshot_hour.astimezone(timezone.utc),
                collected_at=result.collected_at.astimezone(timezone.utc),
                status="failed" if result.error else "success",
                error=result.error,
                item_count=len(result.items),
            )
            snapshot.items = [
                self._to_item(item, position)
                for position, item in enumerate(result.items, start=1)
            ]
            session.add(snapshot)
            try:
                await session.commit()
            except IntegrityError:
                await session.rollback()
                existing = await self._find_snapshot(session, result.platform, snapshot_hour)
                if existing is None:
                    raise
                return existing, False
            await session.refresh(snapshot)
            return snapshot, True

    async def replace_result(
        self,
        result: PlatformResult,
        snapshot_hour: datetime,
    ) -> HotSnapshot:
        """Atomically replace only one platform's snapshot for the specified hour."""

        async with self.session_factory() as session:
            existing = await self._find_snapshot(session, result.platform, snapshot_hour)
            if existing is None:
                snapshot = HotSnapshot(
                    platform=result.platform,
                    snapshot_hour=snapshot_hour.astimezone(timezone.utc),
                    collected_at=result.collected_at.astimezone(timezone.utc),
                    status="failed" if result.error else "success",
                    error=result.error,
                    item_count=len(result.items),
                )
                session.add(snapshot)
            else:
                snapshot = existing
                snapshot.collected_at = result.collected_at.astimezone(timezone.utc)
                snapshot.status = "failed" if result.error else "success"
                snapshot.error = result.error
                snapshot.item_count = len(result.items)
                snapshot.items.clear()

            snapshot.items = [
                self._to_item(item, position)
                for position, item in enumerate(result.items, start=1)
            ]
            await session.commit()
            await session.refresh(snapshot)
            return snapshot

    async def has_snapshot(self, platform: str, snapshot_hour: datetime) -> bool:
        """Return whether a platform already has a snapshot for the specified hour."""

        async with self.session_factory() as session:
            statement = select(HotSnapshot.id).where(
                HotSnapshot.platform == platform,
                HotSnapshot.snapshot_hour == snapshot_hour.astimezone(timezone.utc),
            )
            return (await session.scalar(statement)) is not None

    async def latest(self, platform: str | None = None) -> list[dict[str, Any]]:
        """Return each platform's latest available snapshot."""

        async with self.session_factory() as session:
            platforms_statement = select(HotSnapshot.platform).distinct()
            if platform is not None:
                platforms_statement = platforms_statement.where(HotSnapshot.platform == platform)
            platforms = list((await session.scalars(platforms_statement)).all())
            snapshots: list[HotSnapshot] = []
            for platform_name in platforms:
                statement = (
                    select(HotSnapshot)
                    .where(HotSnapshot.platform == platform_name)
                    .options(selectinload(HotSnapshot.items))
                    .order_by(HotSnapshot.snapshot_hour.desc(), HotSnapshot.collected_at.desc())
                    .limit(1)
                )
                snapshot = await session.scalar(statement)
                if snapshot is not None:
                    snapshots.append(snapshot)
            return [self._serialize_snapshot(snapshot) for snapshot in snapshots]

    async def dates(self) -> list[str]:
        """Return local calendar dates that contain persisted snapshots."""

        async with self.session_factory() as session:
            statement = select(HotSnapshot.snapshot_hour).order_by(
                HotSnapshot.snapshot_hour.desc()
            )
            values = (await session.scalars(statement)).all()
        zone = get_timezone(self.timezone_name)
        return sorted(
            {self._aware(value).astimezone(zone).date().isoformat() for value in values},
            reverse=True,
        )

    async def hours(self, day: date) -> list[str]:
        """Return only local hours that have snapshots on the requested date."""

        start, end = local_day_bounds(day, self.timezone_name)
        async with self.session_factory() as session:
            statement = (
                select(HotSnapshot.snapshot_hour)
                .where(HotSnapshot.snapshot_hour >= start, HotSnapshot.snapshot_hour <= end)
                .order_by(HotSnapshot.snapshot_hour.desc())
            )
            values = (await session.scalars(statement)).all()
        zone = get_timezone(self.timezone_name)
        return sorted(
            {self._aware(value).astimezone(zone).strftime("%H") for value in values},
            reverse=True,
        )

    async def history(
        self,
        day: date,
        hour: int | None = None,
        platform: str | None = None,
        *,
        scope: str = "snapshot",
    ) -> list[dict[str, Any]]:
        """Return snapshots for a local day while preserving the legacy latest-hour default.

        ``scope="day"`` returns every persisted snapshot inside the configured local
        calendar day. The default ``scope="snapshot"`` keeps the previous behavior:
        an explicit hour returns that local hour, otherwise the true latest snapshot
        time shared by the returned platforms is selected.
        """

        start, end = local_day_bounds(day, self.timezone_name)
        async with self.session_factory() as session:
            statement = (
                select(HotSnapshot)
                .where(HotSnapshot.snapshot_hour >= start, HotSnapshot.snapshot_hour <= end)
                .options(selectinload(HotSnapshot.items))
                .order_by(HotSnapshot.snapshot_hour.desc(), HotSnapshot.platform.asc())
            )
            if platform is not None:
                statement = statement.where(HotSnapshot.platform == platform)
            snapshots = list((await session.scalars(statement)).unique().all())

        zone = get_timezone(self.timezone_name)
        if scope == "day":
            return [self._serialize_snapshot(snapshot) for snapshot in snapshots]
        if hour is not None:
            snapshots = [
                snapshot
                for snapshot in snapshots
                if self._aware(snapshot.snapshot_hour).astimezone(zone).hour == hour
            ]
        elif snapshots:
            latest_hour = max(
                self._aware(snapshot.snapshot_hour).astimezone(zone)
                for snapshot in snapshots
            )
            snapshots = [
                snapshot
                for snapshot in snapshots
                if self._aware(snapshot.snapshot_hour).astimezone(zone) == latest_hour
            ]
        return [self._serialize_snapshot(snapshot) for snapshot in snapshots]

    async def delete_all(self) -> None:
        """Delete persisted snapshots, primarily for isolated tests."""

        async with self.session_factory() as session:
            await session.execute(delete(HotSnapshot))
            await session.commit()

    async def _find_snapshot(
        self,
        session: AsyncSession,
        platform: str,
        snapshot_hour: datetime,
    ) -> HotSnapshot | None:
        statement = (
            select(HotSnapshot)
            .where(
                HotSnapshot.platform == platform,
                HotSnapshot.snapshot_hour == snapshot_hour.astimezone(timezone.utc),
            )
            .options(selectinload(HotSnapshot.items))
        )
        snapshot = await session.scalar(statement)
        return snapshot

    @staticmethod
    def _to_item(item: DomainHotItem, position: int) -> HotItem:
        return HotItem(
            platform=item.platform,
            position=position,
            rank=item.rank,
            title=item.title,
            url=str(item.url) if item.url is not None else None,
            image_url=str(item.image_url) if item.image_url is not None else None,
            hot_value=str(item.hot_value) if item.hot_value is not None else None,
            category=item.category,
            description=item.description,
            collected_at=item.collected_at.astimezone(timezone.utc),
            item_metadata=item.metadata,
        )

    def _serialize_snapshot(self, snapshot: HotSnapshot) -> dict[str, Any]:
        zone = get_timezone(self.timezone_name)
        return {
            "platform": snapshot.platform,
            "snapshot_hour": self._aware(snapshot.snapshot_hour).astimezone(zone).isoformat(),
            "collected_at": self._aware(snapshot.collected_at).astimezone(zone).isoformat(),
            "status": snapshot.status,
            "error": snapshot.error,
            "item_count": snapshot.item_count,
            "items": [
                {
                    "platform": item.platform,
                    "rank": item.rank,
                    "title": item.title,
                    "url": item.url,
                    "image_url": item.image_url,
                    "hot_value": item.hot_value,
                    "category": item.category,
                    "description": item.description,
                    "collected_at": self._aware(item.collected_at).astimezone(zone).isoformat(),
                    "metadata": item.item_metadata,
                }
                for item in snapshot.items
            ],
        }

    @staticmethod
    def _aware(value: datetime) -> datetime:
        return value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)
