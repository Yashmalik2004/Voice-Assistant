# Voice Assistant Agent Worker

LiveKit Agents worker process. Registers with the LiveKit server under an
explicit `agent_name` and accepts per-room job dispatches from the backend.

**Milestone 5 scope:** the worker runs the full grounded conversation loop via
LiveKit Agents' `AgentSession`:

- Deepgram streaming STT transcribes the customer (M2), forwarded to the widget
  over the `lk.transcription` text stream.
- Cartesia streaming TTS speaks responses back (M3).
- Silero-VAD turn detection + barge-in (M4).
- An OpenAI LLM with function tools is the reasoning layer (M5). It classifies
  intent and calls tools — `get_order_status`, `get_customer_orders`,
  `get_return_policy` (RAG), `initiate_return` — against the backend's internal
  APIs, so every spoken order/policy fact is grounded in real data, never
  invented. See `Voice Assistant_agent/support_agent.py`.

The backend must be running (and Postgres seeded) for the tools to work — the
agent reaches it at `BACKEND_URL` (default `http://localhost:8000`).

## Setup

```bash
cd agent
uv sync --extra ai   # STT + VAD (core) plus TTS/LLM plugins
```

The Deepgram (STT) and Silero (VAD) plugins are core dependencies. The Cartesia
(TTS) and OpenAI (LLM) plugins live in the `ai` extra, so from Milestone 3
onward run `uv sync --extra ai`.

Populate the repo-root `.env` with:

- `LIVEKIT_URL`, `LIVEKIT_API_KEY`, `LIVEKIT_API_SECRET`
- `DEEPGRAM_API_KEY` — speech-to-text (https://deepgram.com)
- `CARTESIA_API_KEY` — text-to-speech (https://cartesia.ai)

`AGENT_NAME` must match the backend's `AGENT_NAME` (default `Voice Assistant-agent`).
Optional tuning:

- STT: `STT_MODEL` (`nova-3`), `STT_LANGUAGE` (`en-US`)
- TTS: `TTS_MODEL` (`sonic-3`), `TTS_VOICE`, `TTS_LANGUAGE` (`en`)
- Turn-taking: `TURN_ENDPOINTING_DELAY` (`0.7`s end-of-turn silence),
  `TURN_MAX_DELAY` (`3.0`s), `INTERRUPTIONS_ENABLED` (`true`),
  `MIN_INTERRUPTION_DURATION` (`0.5`s)
- Reasoning: `OPENAI_API_KEY` (required for answers), `LLM_MODEL`
  (`gpt-4.1-mini`), `BACKEND_URL` (`http://localhost:8000`)
- Persona: `AGENT_PERSONA_NAME`, `STORE_NAME`, `AGENT_GREETING`

## Run

```bash
# connect to LiveKit and wait for dispatched jobs
uv run python -m Voice Assistant_agent.worker start
```

The `start` subcommand is provided by the LiveKit Agents CLI. On a call the
agent greets the caller, then for each final transcript logs `FINAL [...]:
<text>` and `REPLY: <text>` and speaks the reply (DEBUG level also shows interim
transcripts). Agent state transitions are logged as `agent state: X -> Y`
(`listening`/`thinking`/`speaking`); a jump from `speaking` back to `listening`
mid-reply is a successful barge-in.

Tool calls are logged (`tool get_order_status(...)`), and per-turn latency
(LLM/TTS) plus an end-of-session usage summary are logged via the metrics hooks.

Graceful degradation:

- Without `DEEPGRAM_API_KEY` the worker logs an error, connects, and produces no
  transcripts rather than crashing.
- Without `CARTESIA_API_KEY` the worker logs a warning and runs STT-only (it
  transcribes but does not speak).
- Without `OPENAI_API_KEY` there is no reasoning LLM: the agent greets and says
  it can't answer questions right now, rather than guessing.
