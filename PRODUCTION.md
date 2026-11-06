# Voice Assistant — Taking It to Production Scale

How to evolve the current v1 demo into a multi-tenant product that real
e-commerce businesses can plug into. This document is organized by concern, from
the biggest architectural shifts down to operations and go-to-market.

The current build is a solid single-tenant vertical slice: browser widget →
LiveKit → agent (Deepgram STT, Cartesia TTS, Silero VAD, OpenAI reasoning with
tools) → FastAPI backend → Postgres/pgvector. Everything below builds on that
foundation rather than replacing it.

---

## 1. The core gap: single-tenant → multi-tenant

Today there is one store ("Northwind"), one mock database, and one agent
persona. A real product serves many businesses from one platform. This is the
single largest change and everything else depends on it.

### 1.1 Tenant model
- Introduce a `tenants` table (one row per business) and add a `tenant_id`
  foreign key to every domain table (`orders`, `customers`, `returns`,
  `policy_documents`, `sessions`).
- Scope **every** query by `tenant_id`. Enforce it at the ORM layer (a session
  that always filters by tenant) so a missing filter can't leak another
  business's data. Postgres Row-Level Security (RLS) is the belt-and-suspenders
  backstop.
- Per-tenant configuration: agent persona/name/greeting, voice (TTS voice id),
  business hours, supported intents, escalation rules, branding for the widget.

### 1.2 Tenant resolution
- The widget embed carries a public `tenant_key`. `POST /api/voice/session`
  resolves it to a tenant, and the LiveKit room + agent dispatch carry the
  tenant id as metadata so the agent loads the right config and data scope.
- Room naming becomes `support-{tenant}-{session}`.

### 1.3 Data isolation options (pick per compliance needs)
- **Shared schema + `tenant_id` + RLS** — cheapest, scales to thousands of
  small tenants. Default choice.
- **Schema-per-tenant** — stronger isolation, more operational overhead.
- **Database-per-tenant** — for enterprise customers with strict data-residency
  or contractual isolation requirements. Support this as a premium tier.

---

## 2. Real data: replace the mock DB with live integrations

The mock `orders`/`customers` tables must become a **read path into the
business's real systems**. The agent's four tools stay the same shape; only what
they call underneath changes.

### 2.1 Integration adapters
Build a provider-adapter layer behind the existing tool interface:
- **Shopify** — Admin API (orders, fulfillments, customers, returns via the
  Returns API). OAuth app, webhooks for order updates.
- **WooCommerce** — REST API with consumer key/secret.
- **BigCommerce, Magento, custom** — each an adapter implementing the same
  `OrderProvider` protocol (`get_order`, `get_customer_orders`,
  `create_return`, ...).
- **Generic REST/webhook** — for businesses with a custom backend, let them
  configure endpoint URLs + auth and map their fields to our schema.

### 2.2 Sync vs. live lookup
- **Live lookup** (call the store's API per request) is simplest and always
  fresh, but adds latency and is subject to the provider's rate limits.
- **Cache/sync** frequently-read data (order status) into our Postgres with
  short TTLs or webhook-driven invalidation, falling back to live lookup on a
  miss. Recommended for latency (the <1.5s round-trip target) and resilience.

### 2.3 Knowledge base (RAG) per tenant
- Each business uploads its own policy docs, FAQs, and product info. Store with
  `tenant_id`; embed on upload.
- Support common source formats: pasted text, PDF/DOCX upload, a help-center URL
  crawl, or a Zendesk/Intercom knowledge-base sync.
- Re-embed on document change (a background job, not inline).
- Consider a managed vector store (e.g. a dedicated pgvector instance, or
  Pinecone/Weaviate) if a single tenant's KB grows large.

---

## 3. Real customer identity & verification

The demo looks customers up by a plaintext email/phone. Production needs care:
- **Verification** before revealing order details — one-time code to the email/
  phone on file, or authenticated session if the widget is embedded behind the
  store's own login (pass a signed customer token in the LiveKit token grant).
- **PII minimization** — never speak full order IDs, addresses, or payment
  details unless verified; redact in logs and transcripts.
- **Consent & recording notice** — announce recording where legally required.

---

## 4. Telephony (the obvious expansion)

v1 is web-widget only. The biggest real-world channel is the phone. LiveKit
supports SIP, so:
- Add a **SIP trunk** (Twilio, Telnyx) → LiveKit SIP → the same agent.
- Inbound: a phone number per tenant routes into a tenant-scoped room.
- Outbound + IVR fallback, DTMF handling, and call transfer to a human line.
- This reuses the entire agent pipeline — only the media ingress changes.

---

## 5. Human escalation (flagged as a v1 stretch goal)

Real support must hand off to people:
- Detect escalation intent or repeated low-confidence turns → transfer.
- **Warm handoff**: a human agent joins the LiveKit room; the AI summarizes the
  conversation so far into the agent console.
- Integrate with existing helpdesks (Zendesk, Intercom, Salesforce) — create a
  ticket with the transcript when unresolved.
- Live queue + availability awareness (business hours, agent presence).

---

## 6. Infrastructure & scale

The current `docker compose` (postgres + backend + agent) is right for one box.
For production:

### 6.1 Orchestration
- **Kubernetes** (EKS/GKE/AKS) or a managed platform (ECS Fargate, Fly.io,
  Render).
- **Backend**: stateless, horizontally autoscaled behind a load balancer.
  Already async FastAPI — scales well.
- **Agent workers**: the scaling-critical tier. Each concurrent call needs a
  worker job. LiveKit Agents supports a worker pool that autoscales on load;
  run it as its own deployment scaled on active-session metrics. Plan for
  CPU/memory headroom for Silero VAD and audio processing.
- **Postgres**: managed (RDS/Cloud SQL/Neon) with read replicas; pgvector is
  supported by most managed Postgres now. Connection pooling (PgBouncer).

### 6.2 LiveKit
- LiveKit Cloud handles SFU scaling; or self-host the SFU on Kubernetes for
  cost/control at high volume. Pick based on concurrency and margin.

### 6.3 Statelessness & sessions
- Move the in-memory session store (currently a process dict) fully to Postgres
  or Redis so any backend replica can serve any request.

### 6.4 Latency budget (the product-defining metric)
- Keep the STT→LLM→TTS round trip under ~1.5s. Regionalize: run agent workers
  and LiveKit close to users; use low-latency model tiers (e.g. a small fast LLM
  for most turns, escalating to a larger model only when needed); enable
  streaming everywhere (already done) and preemptive generation.

---

## 7. Security & compliance

Non-negotiable for handling customer data at scale:
- **Secrets management**: move from `.env` files to a secrets manager (AWS
  Secrets Manager, GCP Secret Manager, Vault). Rotate keys.
- **Internal API auth**: the shared-secret header (M7) becomes per-service mTLS
  or signed service tokens (JWT with short TTL) in a real network.
- **Transport**: TLS everywhere; the internal APIs never exposed publicly.
- **PII/PCI**: never touch card data (already out of scope — keep it that way).
  Encrypt PII at rest, minimize what's stored, define retention windows for
  transcripts.
- **Compliance**: GDPR/CCPA data-subject requests (export/delete per customer),
  SOC 2 for selling to mid-market+, data-processing agreements per tenant.
- **Data residency**: EU tenants' data stays in EU regions (ties back to the
  database-per-tenant option in §1.3).
- **Abuse & cost controls**: the per-IP rate limit (M7) plus per-tenant quotas,
  budget caps on LLM/TTS spend, and anomaly alerts.

---

## 8. Observability & quality

- **Tracing**: end-to-end spans per turn (STT latency, LLM tokens/latency, tool
  calls, TTS) — OpenTelemetry → Datadog/Grafana. The metrics hooks from M6 are
  the seed of this.
- **Call analytics**: intent distribution, resolution rate, escalation rate,
  average handle time, containment (calls resolved without a human).
- **Transcript review + eval**: sample calls, score groundedness and helpfulness
  (LLM-as-judge + human review), catch hallucinations. Regression test the
  agent against a fixed set of scenarios before each prompt/model change.
- **Alerting**: on latency SLO breaches, provider errors (Deepgram/OpenAI/
  Cartesia outages), and dispatch failures.
- **Provider fallbacks**: secondary STT/LLM/TTS providers to fail over to when
  one has an outage — the plugin architecture already makes this a config swap.

---

## 9. The onboarding / self-serve product

For businesses to "plug in," they need a dashboard, not a code checkout:
- **Sign-up + tenant provisioning** (automated).
- **Connect your store** — OAuth to Shopify/Woo/etc. in a few clicks.
- **Upload your policies** — the knowledge base UI (§2.3).
- **Configure the agent** — name, voice, greeting, tone, escalation rules,
  business hours; preview/test in-dashboard before going live.
- **Get your embed snippet** — a `<script>` tag or npm component with the
  tenant key; the widget is themeable to the store's brand.
- **Analytics dashboard** — the metrics from §8, per tenant.
- **Billing** — usage-based (per minute of conversation and/or per resolved
  call), tiered plans, Stripe integration, spend caps.

---

## 10. Widget hardening

The current widget is a demo page. To embed in real storefronts:
- Ship as a proper embeddable (isolated via Shadow DOM or iframe so it can't
  clash with the host site's CSS/JS).
- Robust reconnection, network-drop handling, and mobile/Safari audio quirks
  (iOS autoplay is already partially handled).
- Accessibility (WCAG): keyboard operation, screen-reader labels, captions on by
  default (the transcript panel already helps here). Full WCAG conformance
  requires manual testing with assistive technologies and expert review.
- Localization / multi-language (v1 is English only; Deepgram + the LLM + a
  multilingual TTS voice make this a config expansion).

---

## 11. Suggested rollout sequence

A pragmatic order that de-risks and gets to revenue fastest:

1. **Multi-tenancy foundation** (§1) — nothing else ships without it.
2. **One real integration** (§2, Shopify first — largest market) end to end,
   with a single design-partner business.
3. **Identity/verification + PII hardening** (§3, §7) — table stakes before real
   customer data.
4. **Onboarding dashboard MVP** (§9) — connect store, upload policies, get embed.
5. **Observability + eval harness** (§8) — so quality doesn't regress as you add
   tenants.
6. **Managed infra + autoscaling** (§6) — when concurrency justifies it.
7. **Telephony** (§4) and **human escalation** (§5) — the expansion that turns it
   from a widget into a full support channel.
8. **Second/third integrations, multi-language, SOC 2** — scale the market.

Start with 2–3 design-partner businesses on a shared-schema multi-tenant build
with the Shopify adapter, measure containment and latency against real calls,
and let those numbers drive the infra and provider investments.
