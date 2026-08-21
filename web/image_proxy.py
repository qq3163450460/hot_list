from __future__ import annotations

import ipaddress
import socket
from urllib.parse import urljoin, urlsplit

import httpx
from fastapi import HTTPException, status
from fastapi.responses import Response

ALLOWED_IMAGE_HOSTS = frozenset({
    "i0.hdslb.com",
    "i1.hdslb.com",
    "i2.hdslb.com",
    "picx.zhimg.com",
    "pic1.zhimg.com",
    "pic2.zhimg.com",
    "pic3.zhimg.com",
    "pic4.zhimg.com",
})
ALLOWED_IMAGE_CONTENT_TYPES = frozenset({
    "image/avif",
    "image/gif",
    "image/jpeg",
    "image/png",
    "image/webp",
})
MAX_IMAGE_BYTES = 5 * 1024 * 1024
MAX_REDIRECTS = 3


def _validate_image_url(value: str) -> str:
    parsed = urlsplit(value)
    hostname = (parsed.hostname or "").lower().rstrip(".")
    if parsed.scheme not in {"http", "https"} or hostname not in ALLOWED_IMAGE_HOSTS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Image URL is not allowed",
        )
    if (
        parsed.username is not None
        or parsed.password is not None
        or parsed.port not in {None, 80, 443}
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Image URL contains unsupported authority data",
        )
    return value


def _ensure_public_host(hostname: str) -> None:
    try:
        addresses = socket.getaddrinfo(hostname, None, type=socket.SOCK_STREAM)
    except socket.gaierror as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Image host could not be resolved",
        ) from exc

    for address in addresses:
        ip = ipaddress.ip_address(address[4][0])
        if not ip.is_global:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Image host resolved to a non-public address",
            )


async def fetch_proxied_image(url: str) -> Response:
    current_url = _validate_image_url(url)
    headers = {
        "Accept": "image/avif,image/webp,image/png,image/jpeg,image/gif,*/*;q=0.8",
        "Referer": "https://www.bilibili.com/",
        "User-Agent": "Mozilla/5.0 hot-list-image-proxy/0.1",
    }

    async with httpx.AsyncClient(timeout=10.0, follow_redirects=False) as client:
        for _ in range(MAX_REDIRECTS + 1):
            parsed = urlsplit(current_url)
            hostname = parsed.hostname
            if hostname is None:
                raise HTTPException(status_code=400, detail="Image URL has no host")
            _ensure_public_host(hostname)

            try:
                async with client.stream("GET", current_url, headers=headers) as upstream:
                    if upstream.status_code in {301, 302, 303, 307, 308}:
                        location = upstream.headers.get("location")
                        if not location:
                            raise HTTPException(status_code=502, detail="Invalid image redirect")
                        current_url = _validate_image_url(urljoin(current_url, location))
                        continue

                    if upstream.status_code != status.HTTP_200_OK:
                        raise HTTPException(
                            status_code=status.HTTP_502_BAD_GATEWAY,
                            detail=f"Image origin returned HTTP {upstream.status_code}",
                        )

                    content_type = upstream.headers.get("content-type", "").split(";", 1)[0].lower()
                    if content_type not in ALLOWED_IMAGE_CONTENT_TYPES:
                        raise HTTPException(
                            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                            detail="Image origin returned an unsupported content type",
                        )

                    body = bytearray()
                    async for chunk in upstream.aiter_bytes():
                        body.extend(chunk)
                        if len(body) > MAX_IMAGE_BYTES:
                            raise HTTPException(
                                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                                detail="Image exceeds the proxy size limit",
                            )

                    return Response(
                        content=bytes(body),
                        media_type=content_type,
                        headers={
                            "Cache-Control": "public, max-age=3600",
                            "X-Content-Type-Options": "nosniff",
                        },
                    )
            except httpx.RequestError as exc:
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail="Image origin request failed",
                ) from exc

    raise HTTPException(
        status_code=status.HTTP_502_BAD_GATEWAY,
        detail="Image origin redirected too many times",
    )
