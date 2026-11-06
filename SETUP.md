# Voice Assistant — Setup Guide

## Quick Start (Local Development)

### 1. Prerequisites

| Tool | Version | Notes |
|------|---------|-------|
| Python | ≥ 3.11 | Required for backend and agent |
| [`uv`](https://docs.astral.sh/uv/) | latest | Python package manager |
| Node.js | ≥ 18 | Required for frontend |
| Docker | any | Required for Postgres + pgvector |

### 2. External API Keys

You will need accounts and API keys for:

| Service | Purpose | URL |
|---------|---------|-----|
| LiveKit | Real-time audio (WebRTC) | https://cloud.livekit.io |
| Deepgram | Speech-to-text (STT) | https://deepgram.com |
| Cartesia | Text-to-speech (TTS) | https://cartesia.ai |
| OpenAI | LLM reasoning + embeddings | https://platform.openai.com |

### 3. Environment Configuration

```bash
cp .env.example .env
```

Edit `.env` and fill in:

```env
# Required
LIVEKIT_URL=wss://your-project.livekit.cloud
LIVEKIT_API_KEY=your_livekit_api_key
LIVEKIT_API_SECRET=your_livekit_api_secret
DEEPGRAM_API_KEY=your_deepgram_api_key
CARTESIA_API_KEY=your_cartesia_api_key
OPENAI_API_KEY=your_openai_api_key
```

### 4. Database

```bash
docker compose up -d postgres
```

This starts Postgres with the pgvector extension. The backend creates tables automatically on first startup.

Seed demo data (orders, customers, policy docs):
```bash
cd backend
uv sync --extra dev
uv run python -m app.db.seed
```

### 5. Backend

```bash
cd backend
uv run uvicorn app.main:app --reload --port 8000
```

Verify: `curl http://localhost:8000/api/health`

### 6. Agent Worker

```bash
cd agent
uv sync
uv run python -m voice_assistant_agent.worker start
```

The worker registers with LiveKit and waits for dispatched jobs.

### 7. Frontend Widget

```bash
cd frontend
npm install
npm run dev
```

Open http://localhost:5173, click **Start call**, and allow microphone access.

---

## Docker Full-Stack Deployment

```bash
cp .env.example .env    # fill in all API keys
docker compose up -d    # starts postgres + backend + agent
docker compose exec backend uv run python -m app.db.seed   # seed once
```

Frontend runs separately (dev or static build):
```bash
cd frontend && npm run dev    # or npm run build for static files
```

Rebuild after code changes:
```bash
docker compose build && docker compose up -d
```

---

## Demo Script

After starting all services, try these voice interactions:

1. **Order status**: "What's the status of order 4521?"
2. **Customer lookup**: "My email is ada@example.com, what orders do I have?"
3. **Return request**: "I want to return order 4522. The item was damaged."
4. **Policy question**: "What's your return policy?"

Demo data includes orders for three customers: Ada, Grace, and Alan.

---

## Production Hardening Checklist

Before deploying to production, complete these steps:

- [ ] Set `INTERNAL_API_SECRET` to a random 32+ character string in both backend and agent environments
- [ ] Set `BACKEND_CORS_ORIGINS` to only your widget's production domain
- [ ] Set `TOKEN_TTL_SECONDS` appropriately for your use case (default: 600)
- [ ] Configure `RATE_LIMIT_SESSION` to suit your expected traffic
- [ ] Use managed Postgres in production (not the Docker container)
- [ ] Store all API keys in a secrets manager (not in `.env` files on the server)
- [ ] Enable HTTPS/TLS termination in front of the backend
- [ ] Review LiveKit server capacity for expected concurrent calls

See [`PRODUCTION.md`](PRODUCTION.md) for detailed production deployment instructions.

---

## Troubleshooting

### "LiveKit not configured" error
Ensure `LIVEKIT_URL`, `LIVEKIT_API_KEY`, and `LIVEKIT_API_SECRET` are all set in `.env`.

### Agent doesn't respond
Check that `AGENT_NAME` matches between backend and agent (default: `voice-assistant-agent`). Check the agent worker logs for connection errors.

### No speech output (agent transcribes but doesn't speak)
Ensure `CARTESIA_API_KEY` is set. The agent degrades gracefully to STT-only without it.

### No LLM responses (agent greets but doesn't answer)
Ensure `OPENAI_API_KEY` is set. The agent degrades gracefully to a greeting-only mode without it.

### Database errors on startup
Ensure Postgres is running: `docker compose up -d postgres`. The backend degrades gracefully if Postgres is unavailable (token issuance still works).

### Policy search returns no results
Run the seed script with `OPENAI_API_KEY` set so policy documents are embedded. Without embeddings, semantic search is unavailable.
