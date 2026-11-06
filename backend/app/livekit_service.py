"""LiveKit integration: access-token issuance and agent dispatch.

Uses the `livekit-api` package (builder-pattern AccessToken + LiveKitAPI for
server-side calls such as agent dispatch).
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from livekit import api

from .config import Settings

logger = logging.getLogger("Voice Assistant.livekit")


class LiveKitConfigError(RuntimeError):
    """Raised when LiveKit credentials are missing at request time."""


def issue_access_token(
    settings: Settings,
    *,
    room_name: str,
    identity: str,
    display_name: str,
) -> tuple[str, datetime]:
    """Create a short-lived, room-scoped access token for a customer participant.

    Returns the JWT and its absolute expiry time.
    """
    if not settings.livekit_configured:
        raise LiveKitConfigError(
            "LiveKit credentials are not configured. Set LIVEKIT_URL, "
            "LIVEKIT_API_KEY and LIVEKIT_API_SECRET."
        )

    ttl = timedelta(seconds=settings.token_ttl_seconds)
    grants = api.VideoGrants(
        room_join=True,
        room=room_name,
        can_publish=True,
        can_subscribe=True,
        can_publish_data=True,
    )
    token = (
        api.AccessToken(settings.livekit_api_key, settings.livekit_api_secret)
        .with_identity(identity)
        .with_name(display_name)
        .with_grants(grants)
        .with_ttl(ttl)
        .to_jwt()
    )
    expires_at = datetime.now(timezone.utc) + ttl
    return token, expires_at


async def dispatch_agent(settings: Settings, *, room_name: str) -> bool:
    """Explicitly dispatch the agent worker into a room.

    Returns True on success. Failures are logged and swallowed so a missing/only
    partly-configured agent does not break token issuance during early milestones.
    """
    if not settings.livekit_configured:
        return False

    lkapi = api.LiveKitAPI(
        url=settings.livekit_url,
        api_key=settings.livekit_api_key,
        api_secret=settings.livekit_api_secret,
    )
    try:
        await lkapi.agent_dispatch.create_dispatch(
            api.CreateAgentDispatchRequest(
                agent_name=settings.agent_name,
                room=room_name,
            )
        )
        logger.info("Dispatched agent '%s' to room %s", settings.agent_name, room_name)
        return True
    except Exception as exc:  # noqa: BLE001 - best-effort during early milestones
        logger.warning(
            "Agent dispatch to room %s failed (continuing anyway): %s", room_name, exc
        )
        return False
    finally:
        await lkapi.aclose()
