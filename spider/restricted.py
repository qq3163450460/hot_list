from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from spider.base import BaseSpider
from tools.exceptions import SpiderResponseError
from tools.http import HttpClient


class RestrictedSpider(BaseSpider):
    """Fail safely when an official request chain or response contract is unavailable."""

    platform: str

    def __init__(
        self,
        http_client: HttpClient,
        *,
        enabled: bool = True,
        failure_code: str = "official_request_chain_not_captured",
    ) -> None:
        super().__init__(http_client, enabled=enabled)
        self.failure_code = failure_code

    async def fetch(self) -> list:
        """Refuse speculative collection without verified official request evidence."""

        raise SpiderResponseError(self.platform, self.failure_code)

    def parse(self, payload: Mapping[str, Any]) -> list:
        """Reject unverified response shapes instead of guessing platform fields."""

        del payload
        raise SpiderResponseError(self.platform, "response_schema_unverified")


class XiaohongshuSpider(RestrictedSpider):
    """Restricted Xiaohongshu adapter pending verified login and request evidence."""

    platform = "xiaohongshu"

    def __init__(self, http_client: HttpClient, *, enabled: bool = True) -> None:
        super().__init__(
            http_client,
            enabled=enabled,
            failure_code="login_state_required",
        )


class HupuSpider(RestrictedSpider):
    """Restricted Hupu adapter pending an authorized, reproducible HAR capture."""

    platform = "hupu"
