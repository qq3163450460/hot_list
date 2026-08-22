from __future__ import annotations

from collections.abc import Mapping
from typing import Any
from urllib.parse import quote

from pydantic import HttpUrl

from spider.base import BaseSpider
from spider.models import HotItem
from tools.exceptions import SpiderResponseError
from tools.http import HttpClient


class WeiboSpider(BaseSpider):
    """Collect and normalize Weibo hot-search entries."""

    platform = "weibo"

    def __init__(
        self,
        http_client: HttpClient,
        *,
        endpoint: str,
        cookie: str | None = None,
        enabled: bool = True,
    ) -> None:
        super().__init__(http_client, enabled=enabled)
        self.endpoint = endpoint
        self.cookie = cookie

    async def fetch(self) -> list[HotItem]:
        headers = {
            "Accept": "application/json, text/plain, */*",
            "Referer": "https://weibo.com/hot/search",
        }
        if self.cookie:
            headers["Cookie"] = self.cookie

        payload = await self.http_client.get_json(
            platform=self.platform,
            url=self.endpoint,
            headers=headers,
        )
        if not isinstance(payload, Mapping):
            raise SpiderResponseError(self.platform, "Weibo response root must be an object")
        return self.parse(payload)

    def parse(self, payload: Mapping[str, Any]) -> list[HotItem]:
        data = payload.get("data")
        if not isinstance(data, Mapping):
            raise SpiderResponseError(self.platform, "Weibo response is missing data")

        realtime = data.get("realtime")
        if not isinstance(realtime, list):
            raise SpiderResponseError(self.platform, "Weibo response is missing data.realtime")

        items: list[HotItem] = []
        for raw in realtime:
            if not isinstance(raw, Mapping):
                continue

            title_value = raw.get("word") or raw.get("note")
            if not isinstance(title_value, str) or not title_value.strip():
                continue

            title = title_value.strip()
            rank_value = raw.get("rank")
            rank = len(items) + 1
            hot_value = raw.get("num")
            category_value = raw.get("category") or raw.get("label_name")
            category = (
                category_value.strip()
                if isinstance(category_value, str) and category_value.strip()
                else None
            )

            items.append(
                HotItem(
                    platform=self.platform,
                    rank=rank,
                    title=title,
                    url=HttpUrl(f"https://s.weibo.com/weibo?q={quote('#' + title + '#')}"),
                    hot_value=hot_value if isinstance(hot_value, (int, float, str)) else None,
                    category=category,
                    metadata={
                        "raw_rank": rank_value,
                        "word_scheme": raw.get("word_scheme"),
                        "is_hot": raw.get("is_hot"),
                        "is_new": raw.get("is_new"),
                    },
                )
            )

        return sorted(items, key=lambda item: item.rank)
