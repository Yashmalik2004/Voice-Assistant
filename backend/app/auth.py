"""FastAPI dependencies for protecting internal APIs (Milestone 7).

The internal order/customer/policy routes are only meant to be called by the
agent worker. They're protected by a shared secret sent in the
``X-Internal-Secret`` header.

When ``INTERNAL_API_SECRET`` is empty (the dev default) the check is skipped so
local development works without any configuration. In production, set the
variable to a long random string in both the backend and agent ``.env``.
"""

from __future__ import annotations

import logging
import secrets

from fastapi import Depends, Header, HTTPException, status

from .config import Settings, get_settings

logger = logging.getLogger("Voice Assistant.auth")


async def require_internal(
    x_internal_secret: str | None = Header(default=None, alias="X-Internal-Secret"),
    settings: Settings = Depends(get_settings),
) -> None:
    """FastAPI dependency that validates the X-Internal-Secret header.

    Raises 403 when a non-empty ``INTERNAL_API_SECRET`` is configured and the
    header is absent or wrong. Uses ``secrets.compare_digest`` to prevent
    timing attacks.
    """
    configured = settings.internal_api_secret
    if not configured:
        # Secret not set — skip auth (local/dev convenience).
        return

    if not x_internal_secret or not secrets.compare_digest(
        x_internal_secret, configured
    ):
        logger.warning("Rejected request with invalid X-Internal-Secret")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid or missing internal API secret.",
        )
