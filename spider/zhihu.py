from __future__ import annotations

from collections.abc import Mapping
from pathlib import PurePosixPath
from typing import Any
from urllib.parse import urlsplit

from pydantic import HttpUrl

from spider.base import BaseSpider
from spider.models import HotItem
from tools.exceptions import SpiderResponseError
from tools.http import HttpClient

# Known Zhihu hot-list label image identifiers. Keys may be full URLs,
# filenames, or stable path fragments so future mappings can be added here
# without coupling platform-specific rules to the frontend.
ZHIHU_LABEL_TEXT_BY_IDENTIFIER: dict[str, str] = {
    "hot.png": "热",
    "new.png": "新",
    "exclusive.png": "独家",
    "selected.png": "精选",
    "recommend.png": "推荐",
    "video.png": "视频",
}


def resolve_hot_label(image_url: str) -> str | None:
    """Resolve a Zhihu label image URL to maintainable Chinese label text."""

    parsed = urlsplit(image_url)
    filename = PurePosixPath(parsed.path).name.lower()
    normalized_url = image_url.lower()
    for identifier, label in ZHIHU_LABEL_TEXT_BY_IDENTIFIER.items():
        normalized_identifier = identifier.lower()
        if filename == normalized_identifier or normalized_identifier in normalized_url:
            return label
    return None


class ZhihuSpider(BaseSpider):
    """Collect and normalize Zhihu hot-list entries."""

    platform = "zhihu"

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
            "Referer": "https://www.zhihu.com/hot",
        }
        if self.cookie:
            headers["Cookie"] = self.cookie

        payload = await self.http_client.get_json(
            platform=self.platform,
            url=self.endpoint,
            params={"limit": 50, "desktop": "true"},
            headers=headers,
        )
        if not isinstance(payload, Mapping):
            raise SpiderResponseError(self.platform, "Zhihu response root must be an object")
        return self.parse(payload)

    def parse(self, payload: Mapping[str, Any]) -> list[HotItem]:
        raw_items = payload.get("hot_search_queries")
        if not isinstance(raw_items, list):
            raise SpiderResponseError(
                self.platform,
                "Zhihu response is missing hot_search_queries list",
            )

        items: list[HotItem] = []
        for raw in raw_items:
            if not isinstance(raw, Mapping):
                continue

            title_value = raw.get("query") or raw.get("real_query")
            if not isinstance(title_value, str) or not title_value.strip():
                continue

            link_value = raw.get("redirect_link")
            item_url = (
                HttpUrl(link_value)
                if isinstance(link_value, str)
                and link_value.startswith(("http://", "https://"))
                else None
            )

            image_item_value = raw.get("image_item")
            image_item = (
                image_item_value
                if isinstance(image_item_value, Mapping)
                else {}
            )
            image_value = image_item.get("icon_url") or raw.get("icon_url")
            image_url = (
                HttpUrl(image_value)
                if isinstance(image_value, str)
                and image_value.startswith(("http://", "https://"))
                else None
            )

            hot_value = raw.get("hot")
            if not isinstance(hot_value, (int, float, str)):
                hot_value = None

            label_value = raw.get("label")
            category = (
                label_value.strip()
                if isinstance(label_value, str) and label_value.strip()
                else None
            )

            index_value = raw.get("index")
            rank = index_value + 1 if isinstance(index_value, int) else len(items) + 1

            metadata: dict[str, Any] = {
                "hot_show": raw.get("hot_show"),
                "query_id": raw.get("query_id"),
                "hot_source": raw.get("hot_source"),
                "search_source": raw.get("search_source"),
            }

            items.append(
                HotItem(
                    platform=self.platform,
                    rank=rank,
                    title=title_value.strip(),
                    url=item_url,
                    image_url=image_url,
                    hot_value=hot_value,
                    category=category,
                    metadata=metadata,
                )
            )

        return items
