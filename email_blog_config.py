"""Validate exposure and authentication configuration."""

from __future__ import annotations

import ipaddress
import secrets
from urllib.parse import urlparse

from aiohttp import web

CONTENT_SECURITY_POLICY = "default-src 'none'; style-src 'unsafe-inline'; base-uri 'self';"
DEFAULT_MAX_EMAIL_BYTES = 1_048_576
DEFAULT_MAX_BODY_CHARS = 100_000


def request_has_token(request: web.Request, expected_token: str) -> bool:
    """Return whether a request presents the configured access token."""
    auth_header = request.headers.get("Authorization", "")
    candidates = [
        auth_header.removeprefix("Bearer ").strip(),
        request.headers.get("X-Blog-Token", ""),
        request.query.get("token", ""),
    ]
    return any(secrets.compare_digest(token, expected_token) for token in candidates if token)


def validate_public_url(public_url: str | None) -> str | None:
    """Validate and normalize a configured public base URL."""
    if not public_url:
        return None
    parsed = urlparse(public_url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("PUBLIC_URL must be an absolute http(s) URL")
    return public_url.rstrip("/")


def validate_exposure(
    host: str,
    access_token: str | None,
    allow_public_bind: bool,
    allow_public_without_auth: bool,
) -> None:
    """Reject accidental public binding without explicit exposure settings."""
    if not is_public_bind(host):
        return
    if not allow_public_bind:
        raise ValueError("Public HOST binding requires ALLOW_PUBLIC_BIND=true")
    if not access_token and not allow_public_without_auth:
        raise ValueError(
            "Public HOST binding requires BLOG_ACCESS_TOKEN or ALLOW_PUBLIC_WITHOUT_AUTH=true"
        )


def is_public_bind(host: str) -> bool:
    """Return whether a host binding is reachable beyond loopback."""
    if host in {"", "0.0.0.0", "::"}:
        return True
    if host.lower() == "localhost":
        return False
    try:
        return not ipaddress.ip_address(host).is_loopback
    except ValueError:
        return True
