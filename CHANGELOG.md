# Changelog

All notable changes to Voice Assistant are documented here.

## [1.0.0] — Initial Release

### Added

**Backend**
- FastAPI application with async Postgres (SQLAlchemy + asyncpg + pgvector)
- LiveKit access-token issuance with per-room scoping and TTL control
- Explicit agent dispatch via LiveKit Dispatch API
- Voice session lifecycle: create, persist, end (in-memory + Postgres)
- Internal API authentication via `X-Internal-Secret` header
- Rate limiting on session creation (slowapi, configurable per IP)
- Order APIs: fetch by ID, list by customer email/phone, initiate return
- Semantic policy search using pgvector RAG (OpenAI embeddings)
- Health check endpoint with LiveKit configuration status
- Database seed script with mock orders, customers, and policy documents
- Graceful startup degradation when Postgres is unavailable

**Agent (LiveKit Agents worker)**
- Full voice pipeline: Deepgram STT → Silero VAD → OpenAI LLM → Cartesia TTS
- VAD-based turn detection with configurable end-of-turn silence and barge-in
- Function tools: `get_order_status`, `get_customer_orders`, `get_return_policy` (RAG), `initiate_return`
- Grounded reasoning: all order/policy facts sourced from backend APIs, never hallucinated
- Per-turn latency metrics (LLM TTFT, TTS TTFB) and end-of-session usage summary
- Graceful degradation: missing STT key → logs error; missing TTS → STT-only; missing LLM → greeting-only

**Frontend (React + Vite)**
- Embeddable voice widget with LiveKit WebRTC audio
- Live transcript panel with interim and final segments, role-labelled turns
- Orb animation reflecting agent/user speech state
- Mute/unmute, hang-up, barge-in support
- Audio context unlock flow for browser autoplay policy compliance
- Configurable backend URL via `VITE_BACKEND_URL`

**Infrastructure**
- Docker Compose stack: Postgres + pgvector + backend + agent worker
- Backend and agent Dockerfiles with multi-stage builds and minimal runtime images
- Environment template (`.env.example`) covering all configuration variables

### Configuration Defaults

| Variable | Default |
|---|---|
| `AGENT_NAME` | `voice-assistant-agent` |
| `LLM_MODEL` | `gpt-4.1-mini` |
| `STT_MODEL` | `nova-3` |
| `TTS_MODEL` | `sonic-3` |
| `TURN_ENDPOINTING_DELAY` | `0.7` s |
| `TURN_MAX_DELAY` | `3.0` s |
| `INTERRUPTIONS_ENABLED` | `true` |
| `TOKEN_TTL_SECONDS` | `600` |
| `RATE_LIMIT_SESSION` | `10/minute` |
