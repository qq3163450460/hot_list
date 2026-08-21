from __future__ import annotations

from collections.abc import Mapping
from pathlib import PurePosixPath
from typing import Any
from urllib.parse import quote, urlsplit

from pydantic import HttpUrl

from spider.base import BaseSpider
from spider.models import HotItem
from tools.exceptions import SpiderResponseError
from tools.http import HttpClient

# Bilibili returns compact hot-search labels in each trending entry's `icon`
# field. Known image identifiers are normalized here so platform-specific
# knowledge remains centralized and can be extended without frontend changes.
BILIBILI_LABEL_TEXT_BY_IDENTIFIER: dict[str, str] = {
    "EeuqbMwao9.png": "热",
    "UF7B1wVKT2.png": "新",
}


def resolve_hot_label(image_url: str) -> str | None:
    """Resolve a known Bilibili label image URL to Chinese label text."""

    parsed = urlsplit(image_url)
    filename = PurePosixPath(parsed.path).name
    normalized_url = image_url.lower()
    for identifier, label in BILIBILI_LABEL_TEXT_BY_IDENTIFIER.items():
        normalized_identifier = identifier.lower()
        if filename.lower() == normalized_identifier or normalized_identifier in normalized_url:
            return label
    return None


class BilibiliSpider(BaseSpider):
    """Collect and normalize Bilibili hot-search entries."""

    platform = "bilibili"

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
            "Referer": "https://www.bilibili.com/",
        }
        if self.cookie:
            headers["Cookie"] = self.cookie

        payload = await self.http_client.get_json(
            platform=self.platform,
            url=self.endpoint,
            params={"limit": 50},
            headers=headers,
        )
        if not isinstance(payload, Mapping):
            raise SpiderResponseError(self.platform, "Bilibili response root must be an object")
        return self.parse(payload)

    def parse(self, payload: Mapping[str, Any]) -> list[HotItem]:
        code = payload.get("code")
        if code not in (None, 0):
            raise SpiderResponseError(
                self.platform,
                f"Bilibili response reported error code {code}",
            )

        data = payload.get("data")
        if not isinstance(data, Mapping):
            raise SpiderResponseError(self.platform, "Bilibili response is missing data")

        trending = data.get("trending")
        if not isinstance(trending, Mapping):
            raise SpiderResponseError(self.platform, "Bilibili response is missing data.trending")

        raw_items = trending.get("list")
        if not isinstance(raw_items, list):
            raise SpiderResponseError(
                self.platform,
                "Bilibili response is missing data.trending.list",
            )

        items: list[HotItem] = []
        for raw in raw_items:
            if not isinstance(raw, Mapping):
                continue

            title_value = raw.get("keyword") or raw.get("show_name")
            if not isinstance(title_value, str) or not title_value.strip():
                continue

            title = title_value.strip()
            position = raw.get("position")
            rank = position if isinstance(position, int) and position > 0 else len(items) + 1
            hot_value = raw.get("hot_id")
            icon_value = raw.get("icon")
            icon = icon_value.strip() if isinstance(icon_value, str) else ""
            label_image_url = icon if icon.startswith(("http://", "https://")) else None
            mapped_label = resolve_hot_label(label_image_url) if label_image_url else None
            hot_label = mapped_label or (icon if icon and label_image_url is None else None)
            fallback_image = (
                HttpUrl(label_image_url)
                if label_image_url is not None and mapped_label is None
                else None
            )

            metadata: dict[str, Any] = {
                "show_name": raw.get("show_name"),
                "word_type": raw.get("word_type"),
            }
            if label_image_url is not None:
                metadata["label_image_url"] = label_image_url
            if mapped_label is not None:
                metadata["hot_label_mapping"] = mapped_label

            items.append(
                HotItem(
                    platform=self.platform,
                    rank=rank,
                    title=title,
                    url=HttpUrl(f"https://search.bilibili.com/all?keyword={quote(title)}"),
                    image_url=fallback_image,
                    hot_value=hot_value if isinstance(hot_value, (int, float, str)) else None,
                    category=hot_label,
                    metadata=metadata,
                )
            )

        return sorted(items, key=lambda item: item.rank)
