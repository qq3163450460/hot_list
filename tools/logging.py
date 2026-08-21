from __future__ import annotations

import logging
import re
from collections.abc import Mapping
from typing import Any

_SENSITIVE_KEYS = frozenset({
    "authorization",
    "cookie",
    "set-cookie",
    "token",
    "access_token",
    "refresh_token",
    "api_key",
    "apikey",
    "password",
    "secret",
})
_BEARER_PATTERN = re.compile(r"(?i)(bearer\s+)[^\s,;]+")
_COOKIE_PATTERN = re.compile(r"(?i)((?:cookie|set-cookie)\s*[=:]\s*)[^\r\n]+")


def redact_value(value: Any) -> Any:
    """Recursively redact credentials while preserving safe diagnostic structure."""

    if isinstance(value, Mapping):
        return {
            str(key): "***REDACTED***"
            if str(key).lower() in _SENSITIVE_KEYS
            else redact_value(item)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [redact_value(item) for item in value]
    if isinstance(value, tuple):
        return tuple(redact_value(item) for item in value)
    if isinstance(value, str):
        redacted = _BEARER_PATTERN.sub(r"\1***REDACTED***", value)
        return _COOKIE_PATTERN.sub(r"\1***REDACTED***", redacted)
    return value


class RedactingFilter(logging.Filter):
    """Remove common credentials from log messages and structured arguments."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.msg = redact_value(record.msg)
        if isinstance(record.args, Mapping):
            record.args = redact_value(record.args)
        elif isinstance(record.args, tuple):
            record.args = tuple(redact_value(value) for value in record.args)
        return True


def configure_logging(level: str = "INFO") -> None:
    """Configure process logging with one shared credential-redaction filter."""

    handler = logging.StreamHandler()
    handler.addFilter(RedactingFilter())
    handler.setFormatter(
        logging.Formatter(
            "%(asctime)s %(levelname)s %(name)s %(message)s",
            datefmt="%Y-%m-%dT%H:%M:%S%z",
        )
    )
    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level.upper())
