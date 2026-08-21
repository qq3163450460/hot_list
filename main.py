from __future__ import annotations

import argparse
import asyncio
import json
import os
import subprocess
import sys
from collections.abc import Sequence
from datetime import date
from typing import Any

from database.lifecycle import Database
from database.repository import HotRepository
from services.collection import CollectionService
from tools.config import get_settings
from tools.logging import configure_logging
from web.dependencies import get_collection_service, get_hot_list_service, get_http_client


def build_parser() -> argparse.ArgumentParser:
    """Build CLI commands for live collection, persistence, and history queries."""

    parser = argparse.ArgumentParser(description="Collect and query multi-platform hot lists")
    parser.add_argument("--indent", type=int, default=2)
    subparsers = parser.add_subparsers(dest="command")

    live = subparsers.add_parser("live", help="Collect live data without writing the database")
    live.add_argument("platform", nargs="?")

    collect = subparsers.add_parser("collect", help="Collect and persist the current hour")
    collect.add_argument("platform", nargs="?")

    latest = subparsers.add_parser("latest", help="Query latest persisted snapshots")
    latest.add_argument("--platform")

    history = subparsers.add_parser("history", help="Query a persisted date and optional hour")
    history.add_argument("date", type=date.fromisoformat)
    history.add_argument("--hour", type=int, choices=range(24))
    history.add_argument("--platform")

    subparsers.add_parser("serve", help="Start the production web server")
    subparsers.add_parser("dev", aliases=["debug"], help="Start the reload-enabled debug server")

    return parser


def print_json(value: Any, indent: int) -> None:
    """Print JSON while preserving Unicode and serializing date-like values."""

    print(json.dumps(value, ensure_ascii=False, indent=indent, default=str))


def run_web_server(*, debug: bool) -> int:
    """Start Uvicorn through one centralized production or development entry point."""

    command = [
        sys.executable,
        "-m",
        "uvicorn",
        "web.app:app",
        "--host",
        "127.0.0.1",
        "--port",
        "8765",
    ]
    environment = os.environ.copy()
    if debug:
        environment["HOT_LIST_DEBUG"] = "true"
        command.extend(["--reload", "--log-level", "debug"])

    return subprocess.run(command, env=environment, check=False).returncode


async def run(argv: Sequence[str] | None = None) -> int:
    """Execute the selected CLI operation and release all owned resources."""

    args = build_parser().parse_args(argv)
    command = args.command or "live"
    if command == "serve":
        return run_web_server(debug=False)
    if command in {"dev", "debug"}:
        return run_web_server(debug=True)

    settings = get_settings()
    configure_logging(settings.log_level)
    database: Database | None = None

    try:
        if command == "live":
            live_service = get_hot_list_service()
            platform = getattr(args, "platform", None)
            result = (
                await live_service.collect_all()
                if platform is None
                else await live_service.collect_platform(platform)
            )
            print(result.model_dump_json(indent=args.indent))
            return 0

        database = Database(settings.database_url)
        await database.initialize()
        if database.session_factory is None:
            raise RuntimeError("Database session factory was not initialized")
        repository = HotRepository(database.session_factory, settings.app_timezone)

        if command == "collect":
            collection_service = CollectionService(
                get_hot_list_service(),
                repository,
                settings.app_timezone,
            )
            print_json(
                await collection_service.collect_and_save(args.platform),
                args.indent,
            )
        elif command == "latest":
            print_json(await repository.latest(args.platform), args.indent)
        elif command == "history":
            print_json(
                await repository.history(args.date, hour=args.hour, platform=args.platform),
                args.indent,
            )
        return 0
    finally:
        await get_http_client().aclose()
        if database is not None:
            await database.dispose()
        get_collection_service.cache_clear()
        get_hot_list_service.cache_clear()
        get_http_client.cache_clear()
        get_settings.cache_clear()


def main() -> int:
    """Provide the synchronous console-script entry point."""

    return asyncio.run(run())


if __name__ == "__main__":
    raise SystemExit(main())
