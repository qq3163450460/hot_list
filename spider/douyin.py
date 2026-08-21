from __future__ import annotations

from collections.abc import Mapping
from typing import Any
from urllib.parse import quote

from pydantic import HttpUrl, ValidationError

from spider.base import BaseSpider
from spider.models import HotItem
from tools.exceptions import SpiderResponseError
from tools.http import HttpClient


DOUYIN_LABELS: dict[int, str] = {
    1: "新",
    2: "荐",
    3: "热",
    4: "爆",
    5: "首发",
}


class DouyinSpider(BaseSpider):
    """Collect and normalize entries from the Douyin hot-search list."""

    platform = "douyin"

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
        payload = await self.http_client.get_json(
            platform=self.platform,
            url=self.endpoint,
            headers={
                "Accept": "application/json",
                "User-Agent": (
                    "com.ss.android.ugc.aweme/130200 "
                    "(Linux; U; Android 10; zh_CN)"
                ),
            },
        )
        if not isinstance(payload, Mapping):
            raise SpiderResponseError(
                self.platform,
                "Douyin response root must be an object",
            )
        return self.parse(payload)

    def parse(self, payload: Mapping[str, Any]) -> list:
        data = payload.get("data")
        if not isinstance(data, Mapping):
            raise SpiderResponseError(
                self.platform,
                "Douyin response is missing data object",
            )

        raw_items = data.get("word_list")
        if not isinstance(raw_items, list):
            raise SpiderResponseError(
                self.platform,
                "Douyin response is missing data.word_list",
            )

        positions = [
            raw.get("position")
            for raw in raw_items
            if isinstance(raw, Mapping) and isinstance(raw.get("position"), int)
        ]
        position_offset = 1 if 0 in positions else 0

        items: list[HotItem] = []
        for raw in raw_items:
            if not isinstance(raw, Mapping):
                continue

            word = raw.get("word")
            if not isinstance(word, str) or not word.strip():
                continue
            title = word.strip()

            position = raw.get("position")
            rank = position + position_offset if isinstance(position, int) and position >= 0 else len(items) + 1

            hot_value = raw.get("hot_value")
            if not isinstance(hot_value, (int, float, str)):
                hot_value = None

            label = raw.get("label")
            category = DOUYIN_LABELS.get(label) if isinstance(label, int) else None

            items.append(
                HotItem(
                    platform=self.platform,
                    rank=rank,
                    title=title,
                    url=self._search_url(title),
                    image_url=self._cover_url(raw.get("word_cover")),
                    hot_value=hot_value,
                    category=category,
                    metadata={
                        "position": position,
                        "label": label,
                        "sentence_id": raw.get("sentence_id"),
                        "sentence_tag": raw.get("sentence_tag"),
                        "group_id": raw.get("group_id"),
                        "event_time": raw.get("event_time"),
                        "view_count": raw.get("view_count"),
                        "video_count": raw.get("video_count"),
                        "word_type": raw.get("word_type"),
                        "hotlist_param": raw.get("hotlist_param"),
                    },
                )
            )

        return items

    @staticmethod
    def _search_url(word: str) -> HttpUrl:
        return HttpUrl(f"https://www.douyin.com/search/{quote(word, safe='')}")

    @classmethod
    def _cover_url(cls, value: Any) -> HttpUrl | None:
        if not isinstance(value, Mapping):
            return None
        urls = value.get("url_list")
        if not isinstance(urls, list):
            return None
        for candidate in urls:
            url = cls._optional_http_url(candidate)
            if url is not None:
                return url
        return None

    @staticmethod
    def _optional_http_url(value: Any) -> HttpUrl | None:
        if not isinstance(value, str) or not value.strip():
            return None
        try:
            return HttpUrl(value.strip())
        except ValidationError:
            return None
