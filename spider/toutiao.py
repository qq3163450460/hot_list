from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from pydantic import HttpUrl, ValidationError

from spider.base import BaseSpider
from spider.models import HotItem
from tools.exceptions import SpiderResponseError
from tools.http import HttpClient

# Toutiao returns machine-readable label codes in `Label`. They are translated
# to Chinese badge text here so platform-specific knowledge stays centralized,
# matching the approach used by the Bilibili and Zhihu adapters.
TOUTIAO_LABEL_TEXT_BY_CODE: dict[str, str] = {
    "depth": "深度",
    "hot": "热",
    "interpretation": "解读",
    "new": "新",
    "onsite": "现场",
    "recentprogress": "进展",
    "refuterumors": "辟谣",
}


def resolve_label_text(label_value: Any) -> str | None:
    """Translate a Toutiao label code to display text, passing through unknowns."""

    if not isinstance(label_value, str):
        return None
    text = label_value.strip()
    if not text:
        return None
    return TOUTIAO_LABEL_TEXT_BY_CODE.get(text.lower(), text)


class ToutiaoSpider(BaseSpider):
    """Collect and normalize Toutiao hot-board entries."""

    platform = "toutiao"

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
                "Accept": "application/json, text/plain, */*",
                "Referer": "https://www.toutiao.com/",
            },
        )
        if not isinstance(payload, Mapping):
            raise SpiderResponseError(
                self.platform,
                "Toutiao response root must be an object",
            )
        return self.parse(payload)

    def parse(self, payload: Mapping[str, Any]) -> list:
        data = payload.get("data")
        if not isinstance(data, list):
            raise SpiderResponseError(
                self.platform,
                "Toutiao response is missing data list",
            )

        items: list[HotItem] = []
        for raw in data:
            if not isinstance(raw, Mapping):
                continue

            title_value = raw.get("Title")
            if not isinstance(title_value, str) or not title_value.strip():
                continue

            hot_value = raw.get("HotValue")
            category = resolve_label_text(raw.get("Label"))
            url = self._optional_http_url(raw.get("Url"))
            image_url = self._optional_http_url(
                raw.get("Image") or raw.get("ImageUrl")
            )

            items.append(
                HotItem(
                    platform=self.platform,
                    rank=len(items) + 1,
                    title=title_value.strip(),
                    url=url,
                    image_url=image_url,
                    hot_value=(
                        hot_value
                        if isinstance(hot_value, (int, float, str))
                        else None
                    ),
                    category=category,
                    metadata={
                        "cluster_id": raw.get("ClusterId"),
                        "schema": raw.get("Schema"),
                        "label_url": raw.get("LabelUrl"),
                        "cluster_type": raw.get("ClusterType"),
                    },
                )
            )

        return items

    @staticmethod
    def _optional_http_url(value: Any) -> HttpUrl | None:
        if not isinstance(value, str) or not value.strip():
            return None
        try:
            return HttpUrl(value.strip())
        except ValidationError:
            return None
