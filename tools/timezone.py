from __future__ import annotations

from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo


def get_timezone(name: str) -> ZoneInfo:
    """Return the configured IANA timezone."""

    return ZoneInfo(name)


def utc_now() -> datetime:
    """Return the current timezone-aware UTC datetime."""

    return datetime.now(timezone.utc)


def local_now(timezone_name: str) -> datetime:
    """Return the current datetime in the configured application timezone."""

    return utc_now().astimezone(get_timezone(timezone_name))


def snapshot_hour(value: datetime, timezone_name: str) -> datetime:
    """Normalize a datetime to the start of its local application hour."""

    if value.tzinfo is None:
        raise ValueError("datetime must be timezone-aware")
    return value.astimezone(get_timezone(timezone_name)).replace(
        minute=0,
        second=0,
        microsecond=0,
    )


def local_day_bounds(day: date, timezone_name: str) -> tuple[datetime, datetime]:
    """Return UTC boundaries for one calendar day in the application timezone."""

    zone = get_timezone(timezone_name)
    start_local = datetime.combine(day, datetime.min.time(), tzinfo=zone)
    end_local = start_local.replace(hour=23, minute=59, second=59, microsecond=999999)
    return start_local.astimezone(timezone.utc), end_local.astimezone(timezone.utc)
