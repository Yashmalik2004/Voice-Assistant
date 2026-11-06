# Voice Assistant — Real-Time Voice Support Agent
## Technical Specification & Development Handoff Document

**Version:** 1.0
**Status:** Ready for development
**Owner:** Oladimeji Balogun

---

## 1. Project Overview

### 1.1 Summary
Voice Assistant is a production-grade, real-time voice AI customer support agent for e-commerce/retail order support. Customers interact via a browser-based voice widget — speaking naturally about order status, returns, and product questions — and receive spoken, context-grounded responses in real time. The system uses LiveKit for real-time audio transport and orchestration (STT/TTS/turn-taking), with a retrieval-augmented reasoning layer grounding responses in real order data and store policy.

### 1.2 Problem Statement
E-commerce support is typically either slow (ticket queues, chat wait times) or robotic (rigid IVR phone trees). Customers want to ask a question in plain speech and get an accurate, immediate spoken answer — without typing, without holding, without navigating menus.

### 1.3 Business Use Case
E-commerce/retail order support, covering three core intents:
- **Order status** — "Where is my order #4521?"
- **Returns/refunds** — "I want to return this item, what's the process?"
- **Product Q&A** — "Does this come in a different size/color?", policy questions

### 1.4 Explicit Scope Boundaries
- **In scope:** Web widget voice interaction (browser microphone) only.
- **Out of scope (v1):** Telephony/SIP/PSTN calling, outbound calling, multi-language support (English only for v1), payment processing, human agent handoff/escalation (flag as a stretch goal, not required for v1).

### 1.5 Success Criteria (Definition of Done for v1)
- End-to-end voice conversation loop works: speak → transcribe → reason/retrieve → respond → speak.
- Barge-in (user interrupting mid-response) correctly cancels agent speech and re-listens.
- STT→LLM→TTS round-trip latency stays under ~1.5s under normal conditions (measured, not assumed).
- Order-status and return-policy answers are grounded in actual (seeded/mock) data — no hallucinated order details.
- System handles low-confidence transcription and unresolved intent gracefully (asks for clarification, does not crash or go silent).
- Fully containerized (Docker) and runnable end-to-end from a documented setup process.

---

## 2. System Architecture

### 2.1 High-Level Architecture

```
┌─────────────────┐         WebRTC (LiveKit)        ┌──────────────────────┐
│  Browser Widget   │◄────────────────────────────►│   LiveKit Cloud/SFU   │
│  (React + LiveKit  │                                │   (media routing)     │
│   client SDK)      │                                └───────────┬──────────┘
└────────┬───────────┘                                            │
         │ HTTPS (token request)                                  │ Agent joins room
         ▼                                                        ▼
┌──────────────────────┐                           ┌───────────────────────────┐
│   FastAPI Backend      │                           │  LiveKit Agent (Python)    │
│  - Token issuance       │                           │  - STT (Deepgram, streaming)│
│  - Agent dispatch        │                           │  - VAD / turn-taking       │
│  - Order/session APIs    │                           │  - Orchestration loop      │
└──────────┬────────────┘                           │  - TTS (streaming)          │
           │                                          └───────────┬────────────────┘
           ▼                                                      │
┌──────────────────────┐                                          ▼
│   PostgreSQL            │◄─────────────────────────┐  ┌───────────────────────┐
│  - orders, customers      │                           │  Reasoning Layer (LangGraph)│
│  - policy docs (for RAG)   │                          │  - Intent routing          │
└──────────────────────┘                             │  - RAG over policy docs      │
                                                        │  - Tool calls (order lookup) │
                                                        └───────────────────────────┘
```

### 2.2 Component Responsibilities

| Component | Responsibility | Technology |
|---|---|---|
| Voice Widget | Capture mic audio, join LiveKit room, play back agent audio, show live transcript/status | React, `livekit-client` |
| Token Server | Issue short-lived LiveKit access tokens per session | FastAPI, `livekit-server-sdk` |
| LiveKit Agent | Join room as participant, run STT/TTS/VAD pipeline, manage turn-taking and interruptions | Python, `livekit-agents` |
| Reasoning Layer | Classify intent, retrieve relevant policy content, call tools, generate response text | LangGraph (or LangChain), LLM (Groq/OpenAI) |
| Order Service | Provide order/customer data via tool-callable functions | FastAPI + SQLAlchemy over Postgres |
| Policy Store | Store returns/shipping/product policy docs for RAG retrieval | Postgres + pgvector or ChromaDB |

---

## 3. LiveKit Integration Details

### 3.1 Room Model
- One LiveKit room per customer session, created on-demand when the widget initiates a call.
- Room name convention: `support-{session_id}` (UUID-based, not customer-identifying in the room name itself).
- Two participants per room: the customer (browser) and the agent (server-side Python process).
- Rooms auto-close after configurable idle timeout (e.g. 60s of silence with no activity) to control cost.

### 3.2 Token Issuance Flow
1. Widget requests a token from `POST /api/voice/session` on the FastAPI backend.
2. Backend creates a session record, generates a room name, and issues a LiveKit access token scoped to that room (customer identity, limited grants: `roomJoin`, `canPublish`, `canSubscribe`).
3. Backend dispatches the agent to that room (via LiveKit's agent dispatch API or automatic dispatch rules).
4. Widget connects to the LiveKit room using the token.

### 3.3 STT Configuration
- Provider: Deepgram (streaming, via `livekit-plugins-deepgram`).
- Interim results enabled for perceived responsiveness (optional: display live partial transcript in widget UI).
- Final transcript triggers the reasoning layer only after end-of-utterance detection (VAD-based).

### 3.4 VAD & Turn-Taking
- Use LiveKit Agents' built-in VAD (e.g. Silero VAD plugin) to detect speech start/end.
- Agent must support **barge-in**: if the user starts speaking while the agent's TTS is playing, the agent immediately stops audio playback and begins listening.
- Silence timeout for end-of-turn: configurable (target: ~700ms–1s of silence to consider turn complete — tune during testing).

### 3.5 TTS Configuration
- Provider: Cartesia or ElevenLabs, streaming mode (audio begins playing before full text-to-speech generation completes).
- Voice: single consistent voice persona for the support agent (define name/persona in section 6).

### 3.6 Agent Process Model
- Agent runs as a LiveKit Agents worker process (`livekit-agents` framework), deployed separately from the FastAPI backend.
- Worker registers with LiveKit server and accepts job dispatches per room.
- Agent lifecycle per session: join room → greet → listen/respond loop → handle end-of-call (explicit "goodbye" intent or idle timeout) → leave room.

---

## 4. Reasoning Layer Specification

### 4.1 Intent Categories (v1)
1. `order_status` — requires order ID or customer lookup by phone/email
2. `return_request` — initiate/explain return process
3. `product_question` — general product/policy Q&A (RAG-driven)
4. `clarification_needed` — ambiguous input, agent must ask a follow-up
5. `out_of_scope` — request agent cannot handle (e.g. payment disputes) — respond with a clear, honest boundary statement

### 4.2 Tool-Calling Requirements
The reasoning layer must have callable tools (not hallucinated data):
- `get_order_status(order_id: str) -> OrderStatus`
- `get_customer_orders(phone_or_email: str) -> list[Order]`
- `get_return_policy(product_category: str) -> str`
- `initiate_return(order_id: str, reason: str) -> ReturnConfirmation`

All tools query the mock Postgres order database — never invented.

### 4.3 RAG Component
- Policy documents (shipping, returns, FAQ) embedded and stored in a vector store (ChromaDB or pgvector — reuse existing ChromaDB pattern from prior projects for consistency).
- Retrieval triggered for `product_question` intent and policy-related sub-questions within other intents.

### 4.4 Response Generation Constraints
- Responses must be optimized for **speech**, not text: short sentences, no markdown, no bullet lists, avoid reading out long IDs unless necessary (spell out only when confirming).
- Agent must never state an order status or policy detail without having retrieved it via a tool call or RAG lookup in that turn.
- If required data is unavailable (e.g. order not found), agent asks for clarification or states it plainly rather than guessing.

### 4.5 Conversation State
- Maintain short-term conversation memory within a session (LangGraph state or equivalent) — order ID mentioned earlier in the call should not need to be repeated by the customer.
- No persistent memory across sessions in v1 (each call starts fresh).

---

## 5. Backend Specification (FastAPI)

### 5.1 API Endpoints

| Method | Path | Purpose |
|---|---|---|
| POST | `/api/voice/session` | Create session, return LiveKit token + room name |
| DELETE | `/api/voice/session/{session_id}` | End session, trigger cleanup |
| GET | `/api/orders/{order_id}` | (Internal, used by agent tools) fetch order |
| GET | `/api/customers/{identifier}/orders` | (Internal) list orders for a customer |
| POST | `/api/orders/{order_id}/return` | (Internal) create return record |
| GET | `/api/health` | Health check |

### 5.2 Data Models (Postgres)

**customers**: id, name, email, phone, created_at
**orders**: id, customer_id, status (enum: placed/shipped/delivered/returned), items (JSON), total, created_at, updated_at
**returns**: id, order_id, reason, status, created_at
**policy_documents**: id, category, title, content, embedding (vector)
**sessions**: id, room_name, customer_id (nullable — may be anonymous until identified mid-call), started_at, ended_at, transcript_log (JSON, optional for QA/debugging)

### 5.3 Auth & Security
- LiveKit tokens: short TTL (e.g. 10 minutes), scoped to a single room.
- No customer PII in room names or logs beyond what's needed for debugging.
- Rate limit `/api/voice/session` creation per IP to prevent abuse.
- CORS restricted to the widget's deployed origin(s).

### 5.4 Observability
- Structured logging per session: session start/end, intents resolved, tool calls made, errors.
- Latency logging at each pipeline stage (STT completion, LLM response, TTS start) to validate the <1.5s target.

---

## 6. Frontend Specification (Widget)

### 6.1 Tech Stack
React + `livekit-client` SDK (or `@livekit/components-react` for prebuilt primitives), deployable as an embeddable widget (iframe or script embed) or standalone demo page for v1.

### 6.2 UI States
1. **Idle** — "Talk to support" button/mic icon
2. **Connecting** — requesting token, joining room
3. **Listening** — mic active, visual indicator (waveform or pulsing icon) that the agent is hearing the user
4. **Agent speaking** — visual indicator agent is responding; user can interrupt by speaking
5. **Error** — connection failure, mic permission denied, etc. — clear, non-technical error messaging
6. **Ended** — call ended, option to restart

### 6.3 Functional Requirements
- Request microphone permission explicitly with a clear prompt before connecting.
- Display live partial transcript (optional but recommended for trust/accessibility).
- Visually distinguish "user turn" vs "agent turn."
- Support ending the call manually (hang up button) in addition to natural conversation end.
- Graceful handling of connection drops (reconnect attempt, then clear error state).

### 6.4 Agent Persona
- Define name, tone, and greeting script for the voice agent (e.g. "Hi, I'm [Name] from [Store] support — how can I help with your order today?"). This should be finalized before TTS voice selection.

---

## 7. Non-Functional Requirements

| Category | Requirement |
|---|---|
| Latency | STT→LLM→TTS round trip under ~1.5s (p50), degrade gracefully if exceeded |
| Reliability | Agent must not crash on malformed/ambiguous input — always resolve to a valid response or clarification |
| Scalability | v1 target: handle a small number of concurrent sessions (define load target before infra decisions — not designed for high concurrency yet) |
| Deployability | Full stack containerized via Docker Compose (FastAPI, agent worker, Postgres); LiveKit itself can use LiveKit Cloud or self-hosted server |
| Data integrity | All spoken facts about orders/policy must be traceable to a tool call or retrieval — no hallucinated specifics |

---

## 8. Development Milestones

1. **LiveKit fundamentals** — room creation, token issuance, browser client connects, raw audio flows both directions (no AI logic yet)
2. **STT pipeline** — Deepgram integrated into agent worker, live transcripts produced from real speech
3. **TTS pipeline** — agent can speak text back into the room (reverse direction)
4. **VAD & turn-taking** — silence detection, end-of-turn logic, barge-in/interruption handling
5. **Reasoning layer** — LangGraph agent with tool-calling against mock order DB + RAG over policy docs
6. **End-to-end loop** — full conversation cycle working with barge-in and grounded responses
7. **Production hardening** — auth, rate limiting, logging/observability, latency instrumentation, Docker packaging, documented setup

---

## 9. Open Decisions (to finalize before/during development)

- [ ] Specific LLM provider for reasoning layer (Groq vs OpenAI vs other — cost/latency tradeoff)
- [ ] TTS voice/provider final choice (Cartesia vs ElevenLabs — latency and voice quality comparison)
- [ ] Agent name/persona and greeting script
- [ ] Session idle-timeout duration
- [ ] Whether transcript logging is retained post-call (and for how long) for QA purposes
- [ ] Concurrent session target for v1 (affects LiveKit deployment choice: Cloud vs self-hosted)

---

## 10. Explicitly Out of Scope for v1

- Telephony/SIP integration
- Multi-language support
- Human agent escalation/handoff
- Payment processing or refund execution (return *request* only, not fulfillment)
- Persistent cross-session memory
