# Contributing to Voice Assistant

Thank you for your interest in contributing to Voice Assistant!

## Development Setup

### Prerequisites

- Python ≥ 3.11 and [`uv`](https://docs.astral.sh/uv/)
- Node.js ≥ 18 and npm
- Docker (for Postgres + pgvector)
- A LiveKit project (Cloud or self-hosted)

### Quick Start

```bash
# 1. Clone the repository
git clone https://github.com/Yashmalik2004/Voice-Assistant.git
cd Voice-Assistant

# 2. Configure environment
cp .env.example .env
# Edit .env and fill in your API keys

# 3. Start database
docker compose up -d postgres

# 4. Backend
cd backend
uv sync --extra dev
uv run python -m app.db.seed

# 5. Agent
cd ../agent
uv sync

# 6. Frontend
cd ../frontend
npm install
```

## Component Architecture

### Frontend ↔ Backend Integration

The React frontend communicates with the FastAPI backend over HTTP:

- `POST /api/voice/session` — creates a LiveKit room, issues a scoped token, dispatches the agent
- `DELETE /api/voice/session/{id}` — ends the session cleanly

Frontend API client: [`frontend/src/api.ts`](frontend/src/api.ts)

### Backend ↔ Agent Integration

The agent worker calls the backend's internal APIs using a shared secret (`INTERNAL_API_SECRET`):

- `GET /api/orders/{id}` — fetch a specific order
- `GET /api/customers/{identifier}/orders` — list customer orders by email/phone
- `POST /api/orders/{id}/return` — initiate a return
- `GET /api/policy/search?q=` — semantic policy search (RAG)

Agent client: [`agent/voice_assistant_agent/backend_client.py`](agent/voice_assistant_agent/backend_client.py)

### Agent ↔ LiveKit Integration

The agent worker connects to LiveKit using `WorkerOptions` with the `AGENT_NAME` matching the backend's dispatch configuration. Both must use the same `AGENT_NAME` environment variable (default: `voice-assistant-agent`).

## Code Style

- **Python**: [`ruff`](https://docs.astral.sh/ruff/) for linting and formatting (line-length=100, target=py311)
- **TypeScript**: Standard TypeScript/React conventions with strict mode enabled

Run checks:
```bash
# Python (backend or agent)
uv run ruff check .
uv run ruff format .

# TypeScript
cd frontend && npx tsc --noEmit
```

## Project Structure

```
voice-assistant/
├── backend/                    # FastAPI service
│   ├── app/
│   │   ├── main.py             # App entrypoint
│   │   ├── config.py           # Settings (pydantic-settings)
│   │   ├── auth.py             # Internal API auth
│   │   ├── livekit_service.py  # Token issuance + agent dispatch
│   │   ├── rag.py              # RAG/pgvector policy search
│   │   ├── sessions.py         # Session lifecycle
│   │   ├── schemas.py          # Pydantic request/response models
│   │   ├── limiter.py          # Rate limiting (slowapi)
│   │   ├── routes/             # API route handlers
│   │   └── db/                 # SQLAlchemy models + session + seed
│   └── pyproject.toml
├── agent/                      # LiveKit Agents worker
│   ├── voice_assistant_agent/
│   │   ├── worker.py           # Worker entrypoint + AgentSession setup
│   │   ├── support_agent.py    # Agent persona + function tools
│   │   ├── backend_client.py   # HTTP client for backend APIs
│   │   └── config.py           # Agent configuration
│   └── pyproject.toml
├── frontend/                   # React + Vite widget
│   ├── src/
│   │   ├── App.tsx             # Demo page
│   │   ├── VoiceWidget.tsx     # Main widget component
│   │   ├── useVoiceSession.ts  # LiveKit session hook
│   │   ├── api.ts              # Backend API client
│   │   └── types.ts            # TypeScript types
│   └── package.json
├── docker-compose.yml          # Full stack (Postgres + backend + agent)
└── .env.example                # Environment template
```

## Pull Request Guidelines

1. Fork the repository and create a feature branch
2. Make focused, well-scoped changes
3. Test your changes end-to-end (voice call → transcript → response)
4. Update documentation if needed
5. Submit a pull request with a clear description

## Environment Variables

See [`.env.example`](.env.example) for all available configuration variables.

For security, never commit real API keys or secrets. The `.gitignore` excludes `.env` files.
