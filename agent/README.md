# Voice Assistant Agent Worker

LiveKit Agents worker process for the Voice Assistant. Registers with the LiveKit
server under an explicit `agent_name` and accepts per-room job dispatches from
the backend.

## Full Voice Pipeline

The worker runs a complete grounded conversation loop via LiveKit Agents' `AgentSession`:

| Component | Service | Purpose |
|-----------|---------|---------|
| STT | Deepgram (`nova-3`) | Streams customer speech to text |
| VAD | Silero | Detects end-of-turn, enables barge-in |
| LLM | OpenAI (`gpt-4.1-mini`) | Reasons over tools, generates replies |
| TTS | Cartesia (`sonic-3`) | Streams text responses as speech |

## Function Tools (Grounded Reasoning)

All order and policy facts come from backend APIs — the LLM never invents them:

| Tool | Purpose |
|------|---------|
| `get_order_status` | Look up a specific order by number |
| `get_customer_orders` | List orders by customer email or phone |
| `get_return_policy` | Semantic policy search via RAG |
| `initiate_return` | Start a return request |

## Setup

```bash
cd agent
uv sync
```

Configure the repo-root `.env`:

```env
# Required
LIVEKIT_URL=wss://your-project.livekit.cloud
LIVEKIT_API_KEY=your_livekit_api_key
LIVEKIT_API_SECRET=your_livekit_api_secret
DEEPGRAM_API_KEY=your_deepgram_api_key   # STT — required
CARTESIA_API_KEY=your_cartesia_api_key   # TTS — required for speech output
OPENAI_API_KEY=your_openai_api_key       # LLM — required for answers
```

## Run

```bash
uv run python -m voice_assistant_agent.worker start
```

The `start` subcommand is provided by the LiveKit Agents CLI. The worker
registers under `AGENT_NAME` (default: `voice-assistant-agent`) and waits for
dispatched jobs from the backend.

## Logging

On a call, the worker logs:

- `FINAL [...]: <text>` — final customer transcript per turn
- `agent state: X -> Y` — state transitions (listening/thinking/speaking)
- `tool <name>(...)` — each function tool call
- Per-turn LLM/TTS latency + end-of-session usage summary

## Graceful Degradation

| Missing credential | Behaviour |
|---|---|
| `DEEPGRAM_API_KEY` | Logs error, connects but produces no transcripts |
| `CARTESIA_API_KEY` | Logs warning, runs STT-only (transcribes, does not speak) |
| `OPENAI_API_KEY` | Logs warning, greets caller but cannot answer questions |

## Configuration Reference

| Variable | Default | Purpose |
|----------|---------|---------|
| `AGENT_NAME` | `voice-assistant-agent` | Must match backend's `AGENT_NAME` |
| `AGENT_PERSONA_NAME` | `Riley` | Agent's spoken name |
| `STORE_NAME` | `Northwind` | Store name in agent persona |
| `AGENT_GREETING` | (auto) | Customise the opening greeting |
| `STT_MODEL` | `nova-3` | Deepgram model |
| `STT_LANGUAGE` | `en-US` | STT language |
| `TTS_MODEL` | `sonic-3` | Cartesia model |
| `TTS_VOICE` | (default) | Cartesia voice ID |
| `LLM_MODEL` | `gpt-4.1-mini` | OpenAI model for reasoning |
| `BACKEND_URL` | `http://localhost:8000` | Backend base URL |
| `INTERNAL_API_SECRET` | `` | Shared secret for internal APIs |
| `TURN_ENDPOINTING_DELAY` | `0.7` | Seconds of silence = end of turn |
| `TURN_MAX_DELAY` | `3.0` | Max seconds before forcing turn end |
| `INTERRUPTIONS_ENABLED` | `true` | Allow customer barge-in |
| `MIN_INTERRUPTION_DURATION` | `0.5` | Min speech (s) to count as interruption |
