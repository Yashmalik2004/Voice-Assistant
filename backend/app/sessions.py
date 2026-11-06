"""Session registry: in-memory for request-time state + Postgres persistence.

The in-memory `SessionStore` handles fast synchronous lookups needed during the
request/response cycle. The async `persist_*` functions write durably to the
``sessions`` table in Postgres (spec section 5.2). Persistence failures are
logged but don't break token issuance.
"""

from __future__ import annotations

import logging
import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone

logger = logging.getLogger("Voice Assistant.sessions")


@dataclass
class Session:
    session_id: str
    room_name: str
    participant_identity: str
    started_at: datetime
    ended_at: datetime | None = field(default=None)

    @property
    def is_active(self) -> bool:
        return self.ended_at is None


class SessionStore:
    """Thread-safe in-memory store of active voice sessions."""

    def __init__(self) -> None:
        self._sessions: dict[str, Session] = {}
        self._lock = threading.Lock()

    def create(self, customer_name: str | None = None) -> Session:
        session_id = str(uuid.uuid4())
        room_name = f"support-{session_id}"
        identity = f"customer-{session_id[:8]}"
        session = Session(
            session_id=session_id,
            room_name=room_name,
            participant_identity=identity,
            started_at=datetime.now(timezone.utc),
        )
        with self._lock:
            self._sessions[session_id] = session
        return session

    def get(self, session_id: str) -> Session | None:
        with self._lock:
            return self._sessions.get(session_id)

    def end(self, session_id: str) -> bool:
        with self._lock:
            session = self._sessions.get(session_id)
            if session is None or not session.is_active:
                return False
            session.ended_at = datetime.now(timezone.utc)
            return True


# Module-level singleton used by the API layer.
store = SessionStore()


# ── Postgres persistence (Milestone 7) ──

async def persist_session_start(session: Session) -> None:
    """Write a new session row to Postgres. Best-effort: never raises."""
    try:
        from .db.models import Session as DBSession
        from .db.session import SessionLocal

        async with SessionLocal() as db:
            db.add(
                DBSession(
                    id=session.session_id,
                    room_name=session.room_name,
                    started_at=session.started_at,
                )
            )
            await db.commit()
        logger.debug("Persisted session start %s", session.session_id)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Could not persist session start %s: %s", session.session_id, exc)


async def persist_session_end(session: Session) -> None:
    """Write ended_at to the Postgres session row. Best-effort: never raises."""
    try:
        from datetime import timezone

        from sqlalchemy import update

        from .db.models import Session as DBSession
        from .db.session import SessionLocal

        async with SessionLocal() as db:
            await db.execute(
                update(DBSession)
                .where(DBSession.id == session.session_id)
                .values(ended_at=datetime.now(timezone.utc))
            )
            await db.commit()
        logger.debug("Persisted session end %s", session.session_id)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Could not persist session end %s: %s", session.session_id, exc)
