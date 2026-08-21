from __future__ import annotations

import asyncio
from pathlib import Path

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from database.models import Base


class Database:
    """Own the asynchronous SQLAlchemy engine and session factory."""

    def __init__(self, database_url: str) -> None:
        self.database_url = database_url
        self.engine: AsyncEngine | None = None
        self.session_factory: async_sessionmaker[AsyncSession] | None = None

    async def initialize(self) -> None:
        """Create the engine, ensure the SQLite directory exists, and create tables."""

        if self.database_url.startswith("sqlite+"):
            database_path = self.database_url.split("///", maxsplit=1)[-1]
            if database_path and database_path != ":memory:":
                await asyncio.to_thread(
                    lambda: Path(database_path)
                    .expanduser()
                    .resolve()
                    .parent.mkdir(parents=True, exist_ok=True)
                )

        self.engine = create_async_engine(self.database_url, pool_pre_ping=True)
        self.session_factory = async_sessionmaker(
            self.engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )
        async with self.engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)

    def session(self) -> AsyncSession:
        """Create a new asynchronous ORM session."""

        if self.session_factory is None:
            raise RuntimeError("Database has not been initialized")
        return self.session_factory()

    async def dispose(self) -> None:
        """Release all pooled database connections."""

        if self.engine is not None:
            await self.engine.dispose()
        self.engine = None
        self.session_factory = None
