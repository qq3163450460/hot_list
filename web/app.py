from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from tools.config import get_settings
from tools.logging import configure_logging
from web.dependencies import (
    get_collection_service,
    get_database,
    get_hot_list_service,
    get_hot_repository,
    get_http_client,
    get_scheduler_service,
)
from web.routes import router

STATIC_DIR = Path(__file__).resolve().parent / "static"


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    """Initialize shared services and close owned network resources on shutdown."""

    settings = get_settings()
    configure_logging(settings.log_level)
    database = get_database()
    await database.initialize()
    get_hot_repository()
    collection_service = get_collection_service()
    scheduler_service = get_scheduler_service() if settings.scheduler_enabled else None

    if settings.collect_on_startup:
        await collection_service.collect_missing_current_hour()
    if scheduler_service is not None:
        scheduler_service.start()

    try:
        yield
    finally:
        if scheduler_service is not None:
            scheduler_service.shutdown()
        await get_http_client().aclose()
        await database.dispose()
        get_scheduler_service.cache_clear()
        get_collection_service.cache_clear()
        get_hot_repository.cache_clear()
        get_database.cache_clear()
        get_hot_list_service.cache_clear()
        get_http_client.cache_clear()
        get_settings.cache_clear()


def create_app() -> FastAPI:
    """Create the FastAPI application without contacting external platforms."""

    settings = get_settings()
    application = FastAPI(
        title="Hot List API",
        version="0.1.0",
        debug=settings.debug,
        lifespan=lifespan,
    )
    application.include_router(router)
    application.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

    @application.get("/", include_in_schema=False)
    async def homepage() -> FileResponse:
        """Serve the frontend without triggering platform collection."""

        return FileResponse(STATIC_DIR / "index.html", media_type="text/html")

    @application.get("/ai-analysis", include_in_schema=False)
    async def ai_analysis_page() -> FileResponse:
        """Serve the standalone AI analysis page without triggering collection."""

        return FileResponse(STATIC_DIR / "ai-analysis.html", media_type="text/html")

    return application


app = create_app()
