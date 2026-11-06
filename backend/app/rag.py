"""Retrieval-augmented generation over policy documents (spec section 4.3).

Policy documents are embedded with OpenAI and stored in the pgvector column on
``policy_documents``. At query time we embed the question and do a cosine
similarity search. All of this degrades gracefully when ``OPENAI_API_KEY`` is
absent: embedding becomes a no-op and search returns nothing (the agent then
tells the caller it can't answer rather than guessing).

Commands:
    uv run python -m app.rag embed     # (re)embed all policy documents
"""

from __future__ import annotations

import asyncio
import logging
import sys

from openai import AsyncOpenAI
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .config import get_settings
from .db.models import PolicyDocument
from .db.session import SessionLocal, engine, init_db

logger = logging.getLogger("Voice Assistant.rag")

_settings = get_settings()


def _client() -> AsyncOpenAI | None:
    if not _settings.embeddings_configured:
        return None
    return AsyncOpenAI(api_key=_settings.openai_api_key)


async def embed_text(text: str) -> list[float] | None:
    """Embed a single string. Returns None when embeddings aren't configured."""
    client = _client()
    if client is None:
        logger.warning("OPENAI_API_KEY not set; cannot embed text.")
        return None
    resp = await client.embeddings.create(model=_settings.embedding_model, input=text)
    return resp.data[0].embedding


async def embed_policies(db: AsyncSession) -> int:
    """Embed every policy document that doesn't yet have an embedding.

    Returns the number of documents embedded. Batches all docs in one API call
    for efficiency. No-op (returns 0) when embeddings aren't configured.
    """
    client = _client()
    if client is None:
        logger.warning("OPENAI_API_KEY not set; skipping policy embedding.")
        return 0

    docs = (await db.execute(select(PolicyDocument))).scalars().all()
    pending = [d for d in docs if d.embedding is None]
    if not pending:
        logger.info("All policy documents already embedded.")
        return 0

    # Embed the title + content together so category/topic terms are captured.
    inputs = [f"{d.title}\n\n{d.content}" for d in pending]
    resp = await client.embeddings.create(model=_settings.embedding_model, input=inputs)
    for doc, item in zip(pending, resp.data, strict=True):
        doc.embedding = item.embedding
    await db.commit()
    logger.info("Embedded %d policy documents.", len(pending))
    return len(pending)


async def search_policies(
    db: AsyncSession, query: str, limit: int = 3
) -> list[dict]:
    """Return the most relevant policy documents for a query.

    Uses pgvector cosine distance. Rows without an embedding are skipped.
    Returns an empty list when embeddings aren't configured.
    """
    qvec = await embed_text(query)
    if qvec is None:
        return []

    distance = PolicyDocument.embedding.cosine_distance(qvec)
    stmt = (
        select(PolicyDocument, distance.label("distance"))
        .where(PolicyDocument.embedding.is_not(None))
        .order_by(distance)
        .limit(limit)
    )
    rows = (await db.execute(stmt)).all()
    return [
        {
            "id": doc.id,
            "category": doc.category,
            "title": doc.title,
            "content": doc.content,
            # Cosine similarity in [0,1]-ish for readability; 1.0 == identical.
            "score": round(1.0 - float(dist), 4),
        }
        for doc, dist in rows
    ]


async def _run_embed() -> None:
    await init_db()
    async with SessionLocal() as db:
        await embed_policies(db)
    await engine.dispose()


def main() -> None:
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s"
    )
    cmd = sys.argv[1] if len(sys.argv) > 1 else "embed"
    if cmd == "embed":
        asyncio.run(_run_embed())
    else:
        print(f"Unknown command: {cmd}. Available: embed")
        raise SystemExit(2)


if __name__ == "__main__":
    main()
