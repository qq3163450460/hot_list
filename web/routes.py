from __future__ import annotations

from datetime import date
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response

from database.repository import HotRepository
from spider.service import HotListService
from web.dependencies import get_hot_list_service, get_hot_repository
from web.image_proxy import fetch_proxied_image

router = APIRouter()
ServiceDependency = Annotated[HotListService, Depends(get_hot_list_service)]
RepositoryDependency = Annotated[HotRepository, Depends(get_hot_repository)]


@router.get("/health")
async def health() -> dict[str, str]:
    """Return process health without contacting external platforms."""

    return {"status": "ok"}


@router.get("/api/platforms")
async def platforms(service: ServiceDependency) -> list[dict[str, str | bool]]:
    """List registered platforms and their configured enabled state."""

    return service.platform_statuses()


@router.get("/api/image-proxy", response_class=Response)
async def image_proxy(url: str) -> Response:
    """Proxy allowlisted external images with a platform-compatible Referer."""

    return await fetch_proxied_image(url)


@router.get("/api/hot")
async def all_hot_items(repository: RepositoryDependency) -> dict[str, Any]:
    """Return the latest persisted snapshot for every platform."""

    results = await repository.latest()
    return {"results": results, "empty": not results}


@router.get("/api/hot/{platform}")
async def platform_hot_items(
    platform: str,
    repository: RepositoryDependency,
) -> dict[str, Any]:
    """Return the latest persisted snapshot for one platform."""

    results = await repository.latest(platform)
    return results[0] if results else {"platform": platform, "items": [], "empty": True}


@router.get("/api/history/latest")
async def history_latest(repository: RepositoryDependency) -> dict[str, Any]:
    """Return the latest persisted snapshot for every platform."""

    results = await repository.latest()
    return {"results": results, "empty": not results}


@router.get("/api/history/dates")
async def history_dates(repository: RepositoryDependency) -> dict[str, list[str]]:
    """Return local dates that have persisted snapshots."""

    return {"dates": await repository.dates()}


@router.get("/api/history/hours")
async def history_hours(
    repository: RepositoryDependency,
    day: Annotated[date, Query(alias="date")],
) -> dict[str, Any]:
    """Return actual persisted hours for a local calendar date."""

    return {"date": day.isoformat(), "hours": await repository.hours(day)}


@router.get("/api/history/hot")
async def history_hot(
    repository: RepositoryDependency,
    day: Annotated[date, Query(alias="date")],
    hour: Annotated[int | None, Query(ge=0, le=23)] = None,
    platform: str | None = None,
    scope: Literal["snapshot", "day"] = "snapshot",
) -> dict[str, Any]:
    """Return historical snapshots without changing the legacy snapshot default.

    ``scope=day`` returns every available snapshot in the configured local day;
    ``scope=snapshot`` keeps the existing explicit-hour or latest-hour behavior.
    """

    results = await repository.history(day, hour=hour, platform=platform, scope=scope)
    snapshot_hours = sorted({result["snapshot_hour"] for result in results})
    selected_hour = (
        None
        if scope == "day"
        else max(snapshot_hours)[11:13] if snapshot_hours else None
    )
    return {
        "date": day.isoformat(),
        "hour": selected_hour,
        "scope": scope,
        "platform": platform,
        "snapshot_count": len(results),
        "covered_hours": sorted({value[11:13] for value in snapshot_hours}),
        "raw_item_count": sum(len(result.get("items", [])) for result in results),
        "results": results,
        "empty": not results,
    }
