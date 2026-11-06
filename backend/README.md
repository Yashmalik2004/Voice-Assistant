# Voice Assistant Backend

FastAPI service providing LiveKit access-token issuance, session lifecycle
management, and the internal order/customer/return and policy-search APIs
used by the AI voice agent.

**Data store:** Postgres with the pgvector extension for policy embeddings (RAG).

## Endpoints

| Method | Path | Auth | Purpose |
|--------|------|------|---------|
| `POST` | `/api/voice/session` | Public (rate-limited) | Create session, return LiveKit token + room |
| `DELETE` | `/api/voice/session/{id}` | Public | End a session |
| `GET` | `/api/orders/{order_id}` | Internal secret | Fetch an order (agent tool) |
| `GET` | `/api/customers/{id}/orders` | Internal secret | List orders by email/phone (agent tool) |
| `POST` | `/api/orders/{order_id}/return` | Internal secret | Create a return request |
| `GET` | `/api/policy/search?q=` | Internal secret | Semantic policy search via RAG |
| `GET` | `/api/health` | Public | Health + LiveKit configuration status |

Interactive docs: http://localhost:8000/docs

## Setup

```bash
cd backend
uv sync --extra dev
```

Copy the repo-root `.env.example` to `.env` and fill in credentials.

## Database

Start Postgres + pgvector (from the repo root):

```bash
docker compose up -d postgres
```

Tables and the `vector` extension are created automatically on backend startup.

Seed the demo dataset (customers, orders, returns, policy docs + embeddings):

```bash
uv run python -m app.db.seed
```

To re-embed policy documents (requires `OPENAI_API_KEY`):

```bash
uv run python -m app.rag embed
```

## Run

```bash
uv run uvicorn app.main:app --reload --port 8000
```

The backend degrades gracefully if Postgres is unreachable on startup —
token issuance and health checks continue to work; order/policy APIs return
errors until the database is reachable.

## Demo Data

| Order | Customer | Status |
|-------|---------|--------|
| `4521` | Ada | Shipped (Wireless Headphones) |
| `4522` | Ada | Delivered |
| `4530` | Grace | Placed (not yet shipped) |
| `4531` | Grace | Returned |
| `4540` | Alan | Shipped |

Customer emails: `ada@example.com`, `grace@example.com`, `alan@example.com`
(also reachable by phone: `+15551230001`, etc.)

## Configuration

| Variable | Default | Purpose |
|----------|---------|---------|
| `LIVEKIT_URL` | — | LiveKit server URL |
| `LIVEKIT_API_KEY` | — | LiveKit API key |
| `LIVEKIT_API_SECRET` | — | LiveKit API secret |
| `DATABASE_URL` | (docker compose) | Async Postgres connection URL |
| `OPENAI_API_KEY` | — | For RAG embeddings |
| `AGENT_NAME` | `voice-assistant-agent` | Must match agent worker's `AGENT_NAME` |
| `INTERNAL_API_SECRET` | `` | Shared secret for internal APIs (empty = skip check) |
| `TOKEN_TTL_SECONDS` | `600` | LiveKit token lifetime in seconds |
| `RATE_LIMIT_SESSION` | `10/minute` | Per-IP rate limit for session creation |
| `BACKEND_CORS_ORIGINS` | `http://localhost:5173` | Allowed widget origins |
