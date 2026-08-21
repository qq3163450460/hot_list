from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, HttpUrl


class HotItem(BaseModel):
    """Platform-independent representation of one ranked hot-list item."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    platform: str = Field(min_length=1)
    rank: int = Field(ge=1)
    title: str = Field(min_length=1)
    url: HttpUrl | None = None
    image_url: HttpUrl | None = None
    hot_value: int | float | str | None = None
    category: str | None = None
    description: str | None = None
    collected_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: dict[str, Any] = Field(default_factory=dict)


class PlatformResult(BaseModel):
    """Collection outcome for one platform, including recoverable failures."""

    model_config = ConfigDict(extra="forbid")

    platform: str = Field(min_length=1)
    items: list[HotItem] = Field(default_factory=list)
    error: str | None = None
    collected_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class AggregateResult(BaseModel):
    """Combined collection results without allowing one platform to hide another."""

    model_config = ConfigDict(extra="forbid")

    results: list[PlatformResult] = Field(default_factory=list)
    collected_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
