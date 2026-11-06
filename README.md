# Voice Assistant — Real-Time Voice Support Agent

Production-grade, real-time voice AI customer support agent for e-commerce order
support. Customers speak to a browser widget about order status, returns, and
product questions and get spoken, context-grounded answers in real time, powered
by [LiveKit](https://livekit.io) for audio transport and turn-taking.

See [`Voice Assistant-spec.md`](./Voice Assistant-spec.md) for the full technical spec.

> **Status: Milestone 7 — production hardening. All milestones complete.**
> Voice Assistant is fully built: voice widget → STT → grounded LLM reasoning with
> order/policy tools → TTS, with VAD turn-taking, barge-in, rate limiting,
> internal API auth, session persistence, and a full Docker Compose stack.

## Architecture (this milestone)

```
Browser Widget  ──HTTP──►  FastAPI backend  ──dispatch──►  LiveKit server
 (React + Vite)             token + order/policy APIs           ▲
      │  ▲                        ▲     │                       │
      │  │ transcripts + speech   │     ▼                       │
      │  │                   ┌────┴──────────────┐              │
      └──┴─ WebRTC (audio) ──┼─ Postgres +       │              │
                             │  pgvector (RAG)   │              │
                             └────▲──────────────┘              │
                                  │ tool calls (HTTP)           │
                        Agent worker (livekit-agents)  ──join───┘
                        AgentSession: Deepgram STT + Silero VAD +
                        Cartesia TTS + OpenAI LLM (function tools + RAG)
```

## Project layout

| Path        | What it is                                                                |
| ----------- | ------------------------------------------------------------------------- |
| `backend/`  | FastAPI — token issuance, session lifecycle, order/policy APIs, Postgres  |
| `agent/`    | LiveKit Agents worker — STT + TTS + VAD + LLM reasoning with tools & RAG   |
| `frontend/` | React + Vite embeddable voice widget with live transcript panel           |
| `docker-compose.yml` | Postgres + pgvector for order data and policy embeddings         |
| `.env.example` | Shared environment template (copy to `.env`)                           |

## Prerequisites

- **Python** ≥ 3.11 and [`uv`](https://docs.astral.sh/uv/)
- **Node.js** ≥ 18 and npm
- A **LiveKit** project — [LiveKit Cloud](https://cloud.livekit.io) (free tier is
  fine) or a self-hosted server. You need `LIVEKIT_URL`, `LIVEKIT_API_KEY`, and
  `LIVEKIT_API_SECRET`.
- A **Deepgram** API key (`DEEPGRAM_API_KEY`) for speech-to-text —
  [deepgram.com](https://deepgram.com).
- A **Cartesia** API key (`CARTESIA_API_KEY`) for text-to-speech —
  [cartesia.ai](https://cartesia.ai).
- An **OpenAI** API key (`OPENAI_API_KEY`) for the reasoning LLM and policy
  embeddings — [platform.openai.com](https://platform.openai.com).
- **Docker** (for the Postgres + pgvector container).

## Setup

1. **Environment**

   ```bash
   cp .env.example .env
   # edit .env and fill in LIVEKIT_URL / LIVEKIT_API_KEY / LIVEKIT_API_SECRET
   ```

2. **Database** (Postgres + pgvector)

   ```bash
   docker compose up -d postgres
   ```

3. **Backend**

   ```bash
   cd backend
   uv sync --extra dev
   uv run python -m app.db.seed   # seed mock orders + policy docs
   ```

4. **Agent worker**

   ```bash
   cd agent
   uv sync
   ```

5. **Frontend**

   ```bash
   cd frontend
   npm install
   ```

## Running

Start the database once (`docker compose up -d postgres`), then run these three
in separate terminals:

```bash
# 1) Backend  (http://localhost:8000)
cd backend && uv run uvicorn app.main:app --reload --port 8000

# 2) Agent worker  (registers with LiveKit, waits for dispatches)
cd agent && uv run python -m Voice Assistant_agent.worker start

# 3) Widget  (http://localhost:5173)
cd frontend && npm run dev
```

Open http://localhost:5173, click **Start call**, and allow microphone access.
The agent greets you, then you can ask about an order ("What's the status of
order 4521?"), start a return, or ask a policy question — it answers from the
seeded database and policy documents.

## Docker full-stack (Milestone 7)

Run the backend, agent worker, and Postgres in containers with one command:

```bash
cp .env.example .env          # fill in all API keys
docker compose up -d          # starts postgres + backend + agent
docker compose exec backend python -m app.db.seed   # seed data once
```

Then start the widget locally as before:

```bash
cd frontend && npm run dev    # http://localhost:5173
```

To rebuild after code changes:

```bash
docker compose build && docker compose up -d
```

## Verifying without a browser

```bash
# backend health (no LiveKit creds needed)
curl -s localhost:8000/api/health
# -> {"status":"ok","livekit_configured":true|false}

# create a session (needs LiveKit creds in .env)
curl -s -X POST localhost:8000/api/voice/session \
  -H 'content-type: application/json' -d '{"customer_name":"Ada"}'
# -> { session_id, room_name, participant_identity, token, livekit_url, expires_at }
```

Interactive API docs: http://localhost:8000/docs

## Configuration reference

All configuration lives in the repo-root `.env` (see `.env.example`). Through
Milestone 3:

| Variable                | Purpose                                          | Required (M3) |
| ----------------------- | ------------------------------------------------ | ------------- |
| `LIVEKIT_URL`           | LiveKit server ws/wss URL                        | yes           |
| `LIVEKIT_API_KEY`       | LiveKit API key                                  | yes           |
| `LIVEKIT_API_SECRET`    | LiveKit API secret                               | yes           |
| `DEEPGRAM_API_KEY`      | Deepgram streaming STT key                       | yes           |
| `CARTESIA_API_KEY`      | Cartesia streaming TTS key                       | yes           |
| `OPENAI_API_KEY`        | OpenAI key — reasoning LLM + policy embeddings   | yes           |
| `DATABASE_URL`          | Async Postgres URL (default: docker compose)     | yes           |
| `LLM_MODEL`             | Reasoning model (default `gpt-4.1-mini`)         | no            |
| `BACKEND_URL`           | Backend URL the agent tools call                 | no            |
| `EMBEDDING_MODEL`       | Embedding model (default `text-embedding-3-small`)| no           |
| `STT_MODEL`             | Deepgram model (default `nova-3`)                | no            |
| `STT_LANGUAGE`          | STT language (default `en-US`)                   | no            |
| `TTS_MODEL`             | Cartesia model (default `sonic-3`)               | no            |
| `TTS_VOICE`             | Cartesia voice id                                | no            |
| `TTS_LANGUAGE`          | TTS language (default `en`)                      | no            |
| `AGENT_GREETING`        | Spoken greeting on connect                       | no            |
| `TURN_ENDPOINTING_DELAY`| End-of-turn silence in seconds (default `0.7`)   | no            |
| `TURN_MAX_DELAY`        | Max turn wait in seconds (default `3.0`)         | no            |
| `INTERRUPTIONS_ENABLED` | Allow barge-in (default `true`)                  | no            |
| `MIN_INTERRUPTION_DURATION` | Min speech (s) to interrupt (default `0.5`)  | no            |
| `TOKEN_TTL_SECONDS`     | Access-token lifetime (default 600)              | no            |
| `AGENT_NAME`            | Agent worker name for explicit dispatch          | no            |
| `BACKEND_CORS_ORIGINS`  | Comma-separated allowed widget origins           | no            |
| `VITE_BACKEND_URL`      | Backend URL the widget calls                     | no            |

`AGENT_NAME` must match between backend and agent (default `Voice Assistant-agent`) so
explicit dispatch targets the right worker.

## Roadmap

Milestones 1–7 are complete. Voice Assistant v1 is done.

- [x] 1. LiveKit fundamentals (token issuance, room join, two-way audio)
- [x] 2. STT pipeline (Deepgram streaming) + live transcript in the widget
- [x] 3. TTS pipeline (Cartesia streaming) — agent greets and responds
- [x] 4. VAD & turn-taking + barge-in
- [x] 5. Reasoning layer (OpenAI tool-calling + RAG, pgvector)
- [x] 6. End-to-end grounded conversation loop
- [x] 7. Production hardening (rate limiting, internal auth, session persistence, Docker)
