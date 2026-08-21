from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from pydantic import HttpUrl, ValidationError

from spider.base import BaseSpider
from spider.models import HotItem
from tools.exceptions import SpiderResponseError
from tools.http import HttpClient


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
            category_value = raw.get("Label")
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
                    category=(
                        category_value.strip()
                        if isinstance(category_value, str)
                        and category_value.strip()
                        else None
                    ),
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
