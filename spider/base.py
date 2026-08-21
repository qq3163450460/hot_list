from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Mapping
from typing import Any

from spider.models import HotItem
from tools.http import HttpClient


class BaseSpider(ABC):
    """Common contract for every platform-specific hot-list adapter."""

    platform: str

    def __init__(self, http_client: HttpClient, *, enabled: bool = True) -> None:
        self.http_client = http_client
        self.enabled = enabled

    @abstractmethod
    async def fetch(self) -> list[HotItem]:
        """Fetch and normalize the current platform hot list."""

    @abstractmethod
    def parse(self, payload: Mapping[str, Any]) -> list[HotItem]:
        """Normalize a decoded platform response into unified hot items."""
