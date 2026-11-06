# ── Build stage ──────────────────────────────────────────────────────────────
FROM python:3.12-slim AS builder

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app
COPY pyproject.toml uv.lock README.md ./
COPY voice_assistant_agent/ voice_assistant_agent/

RUN uv sync --frozen --no-dev

# ── Runtime stage ─────────────────────────────────────────────────────────────
FROM python:3.12-slim AS runtime

WORKDIR /app

RUN useradd --create-home --uid 1000 appuser
USER appuser

COPY --from=builder --chown=appuser /app/.venv /app/.venv
COPY --from=builder --chown=appuser /app/voice_assistant_agent /app/voice_assistant_agent

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

CMD ["python", "-m", "voice_assistant_agent.worker", "start"]
