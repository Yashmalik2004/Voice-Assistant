"""Agent worker configuration, loaded from the repo-root .env when present."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

# Load repo-root .env (agent/ is one level below the repo root), then a local
# .env if present. Values already in the environment take precedence.
_REPO_ROOT_ENV = Path(__file__).resolve().parents[2] / ".env"
if _REPO_ROOT_ENV.exists():
    load_dotenv(_REPO_ROOT_ENV)
load_dotenv()  # local .env, if any


AGENT_NAME = os.getenv("AGENT_NAME", "Voice Assistant-agent")

# Greeting persona (placeholder — finalize in spec section 6.4 / Milestone 6).
AGENT_PERSONA_NAME = os.getenv("AGENT_PERSONA_NAME", "Riley")
STORE_NAME = os.getenv("STORE_NAME", "Northwind")

# ── Backend (Milestone 5) ──
# Base URL of the FastAPI backend the agent's tools call for order/policy data.
BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000").rstrip("/")
# Shared secret sent in X-Internal-Secret on backend API calls (Milestone 7).
INTERNAL_API_SECRET = os.getenv("INTERNAL_API_SECRET", "")

# ── STT (Milestone 2) ──
DEEPGRAM_API_KEY = os.getenv("DEEPGRAM_API_KEY", "")
# Deepgram model + language. nova-3 is the current streaming default.
STT_MODEL = os.getenv("STT_MODEL", "nova-3")
STT_LANGUAGE = os.getenv("STT_LANGUAGE", "en-US")


def stt_configured() -> bool:
    """True when a Deepgram API key is present."""
    return bool(DEEPGRAM_API_KEY)


# ── TTS (Milestone 3) ──
CARTESIA_API_KEY = os.getenv("CARTESIA_API_KEY", "")
# Cartesia model + voice. sonic-3 is the current streaming default; the voice id
# is Cartesia's default English voice. Override TTS_VOICE to pick a persona voice.
TTS_MODEL = os.getenv("TTS_MODEL", "sonic-3")
TTS_VOICE = os.getenv("TTS_VOICE", "f786b574-daa5-4673-aa0c-cbe3e8534c02")
TTS_LANGUAGE = os.getenv("TTS_LANGUAGE", "en")

# Greeting spoken when the agent joins a call (spec section 6.4 placeholder).
GREETING = os.getenv(
    "AGENT_GREETING",
    f"Hi, I'm {AGENT_PERSONA_NAME} from {STORE_NAME} support. "
    "How can I help with your order today?",
)


def tts_configured() -> bool:
    """True when a Cartesia API key is present."""
    return bool(CARTESIA_API_KEY)


# ── LLM / reasoning (Milestone 5) ──
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
LLM_MODEL = os.getenv("LLM_MODEL", "gpt-4.1-mini")


def llm_configured() -> bool:
    """True when an OpenAI API key is present for the reasoning LLM."""
    return bool(OPENAI_API_KEY)


def _env_float(name: str, default: float) -> float:
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        return float(raw)
    except ValueError:
        return default


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in ("1", "true", "yes", "on")


# ── Turn-taking & barge-in (Milestone 4) ──
# End-of-turn detection uses the Silero VAD. TURN_ENDPOINTING_DELAY is how long
# (seconds) of silence after speech before the customer's turn is considered
# complete. Spec target: ~0.7–1.0s. Lower feels snappier but risks cutting off
# mid-thought; higher feels more patient but adds latency.
TURN_ENDPOINTING_DELAY = _env_float("TURN_ENDPOINTING_DELAY", 0.7)
# Maximum time to wait before force-ending a turn even if speech continues.
TURN_MAX_DELAY = _env_float("TURN_MAX_DELAY", 3.0)

# Barge-in: whether the customer can interrupt the agent mid-response.
INTERRUPTIONS_ENABLED = _env_bool("INTERRUPTIONS_ENABLED", True)
# Minimum speech length (seconds) that counts as an interruption, to avoid
# short noises (a cough, "uh-huh") cancelling the agent's speech.
MIN_INTERRUPTION_DURATION = _env_float("MIN_INTERRUPTION_DURATION", 0.5)
