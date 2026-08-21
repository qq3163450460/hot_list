from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import JSON, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """Base class for all database models."""


class HotSnapshot(Base):
    """One platform collection result for a normalized application hour."""

    __tablename__ = "hot_snapshots"
    __table_args__ = (
        UniqueConstraint("platform", "snapshot_hour", name="uq_snapshot_platform_hour"),
        Index("ix_hot_snapshots_snapshot_hour", "snapshot_hour"),
        Index("ix_hot_snapshots_platform_collected", "platform", "collected_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    platform: Mapped[str] = mapped_column(String(64), nullable=False)
    snapshot_hour: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    collected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    item_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    items: Mapped[list[HotItem]] = relationship(
        back_populates="snapshot",
        cascade="all, delete-orphan",
        order_by="HotItem.position",
    )


class HotItem(Base):
    """A ranked item persisted as part of a platform snapshot."""

    __tablename__ = "hot_items"
    __table_args__ = (
        Index("ix_hot_items_snapshot_position", "snapshot_id", "position"),
        Index("ix_hot_items_platform_rank", "platform", "rank"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    snapshot_id: Mapped[int] = mapped_column(
        ForeignKey("hot_snapshots.id", ondelete="CASCADE"),
        nullable=False,
    )
    platform: Mapped[str] = mapped_column(String(64), nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    rank: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    url: Mapped[str | None] = mapped_column(Text, nullable=True)
    image_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    hot_value: Mapped[str | None] = mapped_column(String(255), nullable=True)
    category: Mapped[str | None] = mapped_column(String(255), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    collected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    item_metadata: Mapped[dict[str, Any]] = mapped_column("metadata", JSON, default=dict)

    snapshot: Mapped[HotSnapshot] = relationship(back_populates="items")
