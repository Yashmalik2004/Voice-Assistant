"""Voice session endpoints: token issuance and session lifecycle."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Request, status

from ..config import Settings, get_settings
from ..limiter import limiter
from ..livekit_service import LiveKitConfigError, dispatch_agent, issue_access_token
from ..schemas import CreateSessionRequest, CreateSessionResponse, SessionEndedResponse
from ..sessions import persist_session_end, persist_session_start, store

logger = logging.getLogger("Voice Assistant.voice")

router = APIRouter(prefix="/api/voice", tags=["voice"])


@router.post(
    "/session",
    response_model=CreateSessionResponse,
    status_code=status.HTTP_201_CREATED,
)
@limiter.limit(get_settings().rate_limit_session or "10/minute")
async def create_session(
    request: Request,  # required by slowapi for IP extraction
    body: CreateSessionRequest | None = None,
    settings: Settings = Depends(get_settings),
) -> CreateSessionResponse:
    """Create a voice session and return a LiveKit token scoped to a fresh room.

    Rate-limited per IP (RATE_LIMIT_SESSION, default 10/minute).
    OPTIONS preflight requests are handled by the CORS middleware before this
    handler is reached, so the limiter only fires on real POST calls.
    """
    body = body or CreateSessionRequest()
    session = store.create(customer_name=body.customer_name)
    display_name = body.customer_name or "Customer"

    try:
        token, expires_at = issue_access_token(
            settings,
            room_name=session.room_name,
            identity=session.participant_identity,
            display_name=display_name,
        )
    except LiveKitConfigError as exc:
        # Roll back the session we just created so we don't leak inactive entries.
        store.end(session.session_id)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
        ) from exc

    # Best-effort agent dispatch; safe to ignore failures for now.
    await dispatch_agent(settings, room_name=session.room_name)

    # Persist session to Postgres (best-effort; non-blocking on DB failure).
    await persist_session_start(session)

    logger.info("Created session %s (room %s)", session.session_id, session.room_name)
    return CreateSessionResponse(
        session_id=session.session_id,
        room_name=session.room_name,
        participant_identity=session.participant_identity,
        token=token,
        livekit_url=settings.livekit_url,
        expires_at=expires_at,
    )


@router.delete("/session/{session_id}", response_model=SessionEndedResponse)
async def end_session(session_id: str) -> SessionEndedResponse:
    """End a session. Idempotent-ish: returns ended=False if unknown/already ended."""
    ended = store.end(session_id)
    if not ended and store.get(session_id) is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Unknown session"
        )
    # Persist to Postgres (best-effort).
    session = store.get(session_id)
    if session:
        await persist_session_end(session)
    logger.info("Ended session %s (ended=%s)", session_id, ended)
    return SessionEndedResponse(session_id=session_id, ended=ended)
