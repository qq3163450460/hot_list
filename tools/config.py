from __future__ import annotations

from functools import lru_cache

from pydantic import Field, HttpUrl
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables and an optional .env file."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_prefix="HOT_LIST_",
        extra="ignore",
    )

    request_timeout_seconds: float = Field(default=10.0, gt=0)
    max_retries: int = Field(default=3, ge=1, le=10)
    retry_min_wait_seconds: float = Field(default=0.2, ge=0)
    retry_max_wait_seconds: float = Field(default=2.0, ge=0)
    requests_per_second: float = Field(default=2.0, gt=0)
    user_agent: str = "hot-list/0.1 (+https://localhost)"
    log_level: str = "INFO"
    debug: bool = False

    database_url: str = "sqlite+aiosqlite:///./data/hot_list.db"
    app_timezone: str = "Asia/Shanghai"
    scheduler_enabled: bool = True
    collect_on_startup: bool = True
    collect_cron_minute: int = Field(default=0, ge=0, le=59)

    weibo_enabled: bool = True
    weibo_endpoint: HttpUrl = HttpUrl("https://weibo.com/ajax/side/hotSearch")
    weibo_cookie: str | None = None

    bilibili_enabled: bool = True
    bilibili_endpoint: HttpUrl = HttpUrl(
        "https://api.bilibili.com/x/web-interface/search/square"
    )
    bilibili_cookie: str | None = None

    toutiao_enabled: bool = True
    toutiao_endpoint: HttpUrl = HttpUrl(
        "https://www.toutiao.com/hot-event/hot-board/?origin=toutiao_pc"
    )

    baidu_enabled: bool = True
    baidu_endpoint: HttpUrl = HttpUrl(
        "https://top.baidu.com/board?tab=realtime"
    )

    # Zhihu hot-search endpoint and response contract.
    zhihu_enabled: bool = True
    zhihu_endpoint: HttpUrl = HttpUrl("https://www.zhihu.com/api/v4/search/hot_search")
    zhihu_cookie: str | None = None
    zhihu_request_contract_verified: bool = True

    # Douyin hot-search endpoint and verified response contract.
    douyin_enabled: bool = True
    douyin_endpoint: HttpUrl = HttpUrl(
        "https://aweme.snssdk.com/aweme/v1/hot/search/list/"
    )

    # Restricted adapters intentionally have no endpoint, token, signature, or response-field
    # settings until an authorized and reproducible official request chain is captured.
    xiaohongshu_enabled: bool = True
    hupu_enabled: bool = True


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return one immutable-by-convention settings instance per process."""

    return Settings()
