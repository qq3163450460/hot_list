from __future__ import annotations

import json
import re
from collections.abc import Mapping
from typing import Any

from pydantic import HttpUrl, ValidationError

from spider.base import BaseSpider
from spider.models import HotItem
from tools.exceptions import SpiderResponseError
from tools.http import HttpClient


class BaiduSpider(BaseSpider):
    """Collect and normalize entries from the public Baidu hot-board page."""

    platform = "baidu"
    _STATE_PATTERN = re.compile(r"<!--s-data:(.*?)-->", re.DOTALL)

    def __init__(
        self,
        http_client: HttpClient,
        *,
        endpoint: str,
        enabled: bool = True,
    ) -> None:
        super().__init__(http_client, enabled=enabled)
        self.endpoint = endpoint

    async def fetch(self) -> list:
        html = await self.http_client.get_text(
            platform=self.platform,
            url=self.endpoint,
            headers={
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Referer": "https://www.baidu.com/",
            },
        )
        return self.parse_html(html)

    def parse_html(self, html: str) -> list:
        match = self._STATE_PATTERN.search(html)
        if match is None:
            raise SpiderResponseError(self.platform, "Baidu page is missing embedded hot-list data")

        try:
            payload = json.loads(match.group(1))
        except json.JSONDecodeError as exc:
            raise SpiderResponseError(
                self.platform,
                "Baidu embedded hot-list data is invalid JSON",
            ) from exc

        if not isinstance(payload, Mapping):
            raise SpiderResponseError(self.platform, "Baidu embedded data root must be an object")
        return self.parse(payload)

    def parse(self, payload: Mapping[str, Any]) -> list:
        data = payload.get("data")
        if not isinstance(data, Mapping):
            raise SpiderResponseError(self.platform, "Baidu response is missing data")

        cards = data.get("cards")
        if not isinstance(cards, list):
            raise SpiderResponseError(self.platform, "Baidu response is missing data.cards")

        content: list[Any] | None = None
        for card in cards:
            if not isinstance(card, Mapping) or card.get("component") != "hotList":
                continue
            candidate = card.get("content")
            if isinstance(candidate, list):
                content = candidate
                break

        if content is None:
            raise SpiderResponseError(self.platform, "Baidu response is missing hotList content")

        items: list[HotItem] = []
        for raw in content:
            if not isinstance(raw, Mapping):
                continue

            title_value = raw.get("word") or raw.get("query")
            if not isinstance(title_value, str) or not title_value.strip():
                continue

            hot_value = raw.get("hotScore")
            hot_tag = self._meaningful_tag(raw.get("hotTag"))
            items.append(
                HotItem(
                    platform=self.platform,
                    rank=len(items) + 1,
                    title=title_value.strip(),
                    url=self._optional_http_url(raw.get("url") or raw.get("rawUrl")),
                    image_url=None,
                    hot_value=hot_value if isinstance(hot_value, (int, float, str)) else None,
                    description=None,
                    metadata={
                        "source_index": raw.get("index"),
                        "hot_change": raw.get("hotChange"),
                        "hot_tag": hot_tag,
                        "is_top": raw.get("isTop"),
                        "query": raw.get("query"),
                    },
                )
            )

        return items

    @staticmethod
    def _meaningful_tag(value: Any) -> str | None:
        if not isinstance(value, (str, int, float)):
            return None
        text = str(value).strip()
        if not text or text.isdigit() or text == "不":
            return None
        return text

    @staticmethod
    def _optional_http_url(value: Any) -> HttpUrl | None:
        if not isinstance(value, str) or not value.strip():
            return None
        try:
            return HttpUrl(value.strip())
        except ValidationError:
            return None
