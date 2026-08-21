from __future__ import annotations

from functools import lru_cache

from database.lifecycle import Database
from database.repository import HotRepository
from services.collection import CollectionService
from services.scheduler import SchedulerService
from spider.baidu import BaiduSpider
from spider.bilibili import BilibiliSpider
from spider.douyin import DouyinSpider
from spider.service import HotListService
from spider.toutiao import ToutiaoSpider
from spider.weibo import WeiboSpider
from spider.zhihu import ZhihuSpider
from tools.config import get_settings
from tools.http import HttpClient
from tools.registry import SpiderRegistry


@lru_cache(maxsize=1)
def get_http_client() -> HttpClient:
    """Create the shared process-wide HTTP client."""

    return HttpClient(get_settings())


@lru_cache(maxsize=1)
def get_hot_list_service() -> HotListService:
    """Build the service and register every configured platform adapter."""

    settings = get_settings()
    http_client = get_http_client()
    registry = SpiderRegistry(
        (
            WeiboSpider(
                http_client,
                endpoint=str(settings.weibo_endpoint),
                cookie=settings.weibo_cookie,
                enabled=settings.weibo_enabled,
            ),
            BilibiliSpider(
                http_client,
                endpoint=str(settings.bilibili_endpoint),
                cookie=settings.bilibili_cookie,
                enabled=settings.bilibili_enabled,
            ),
            ToutiaoSpider(
                http_client,
                endpoint=str(settings.toutiao_endpoint),
                enabled=settings.toutiao_enabled,
            ),
            BaiduSpider(
                http_client,
                endpoint=str(settings.baidu_endpoint),
                enabled=settings.baidu_enabled,
            ),
            ZhihuSpider(
                http_client,
                endpoint=str(settings.zhihu_endpoint),
                cookie=settings.zhihu_cookie,
                enabled=settings.zhihu_enabled,
            ),
            DouyinSpider(
                http_client,
                endpoint=str(settings.douyin_endpoint),
                enabled=settings.douyin_enabled,
            ),
        )
    )
    return HotListService(registry)


@lru_cache(maxsize=1)
def get_database() -> Database:
    """Return the process-wide asynchronous database lifecycle owner."""

    return Database(get_settings().database_url)


@lru_cache(maxsize=1)
def get_hot_repository() -> HotRepository:
    """Create the repository after database initialization."""

    database = get_database()
    if database.session_factory is None:
        raise RuntimeError("Database has not been initialized")
    return HotRepository(database.session_factory, get_settings().app_timezone)


@lru_cache(maxsize=1)
def get_collection_service() -> CollectionService:
    """Create the collection and persistence coordinator."""

    return CollectionService(
        get_hot_list_service(),
        get_hot_repository(),
        get_settings().app_timezone,
    )


@lru_cache(maxsize=1)
def get_scheduler_service() -> SchedulerService:
    """Create the process-wide hourly scheduler service."""

    settings = get_settings()
    return SchedulerService(
        get_collection_service(),
        settings.app_timezone,
        settings.collect_cron_minute,
    )
