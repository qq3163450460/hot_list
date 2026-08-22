from __future__ import annotations

import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)


async def validate_turnstile_token(
    secret_key: str,
    token: str,
    remote_ip: str | None = None,
) -> dict[str, Any]:
    """Validate a Turnstile challenge token against Cloudflare's siteverify API.

    Returns a dict with ``success``, ``error-codes``, and challenge metadata.
    When ``secret_key`` is empty the caller should skip validation entirely.
    """

    if not secret_key or not token:
        return {"success": False, "error-codes": ["missing-input-response"]}

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                "https://challenges.cloudflare.com/turnstile/v0/siteverify",
                data={
                    "secret": secret_key,
                    "response": token,
                    "remoteip": remote_ip or "",
                },
            )
            response.raise_for_status()
            return response.json()
    except Exception as exc:  # pragma: no cover - best-effort validation
        logger.warning("Turnstile siteverify request failed: %s", exc)
        return {"success": False, "error-codes": ["invalid-input-response"]}
