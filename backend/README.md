# Voice Assistant Backend

FastAPI service: LiveKit access-token issuance, session lifecycle, and the
internal order/customer/return + policy-search APIs the agent's tools call
(Milestone 5). Data lives in Postgres with the pgvector extension for policy
embeddings (RAG).

## Setup

```bash
cd backend
uv sync --extra dev
```

Copy the repo-root `.env.example` to `.env` and fill in credentials. For the
database, the default `DATABASE_URL` points at the docker-compose Postgres.

## Database

Start Postgres + pgvector (from the repo root):

```bash
docker compose up -d postgres
```

Tables and the `vector` extension are created automatically on backend startup.
Seed the mock dataset (customers, orders, returns, policy docs):

```bash
uv run python -m app.db.seed
```

If `OPENAI_API_KEY` is set, the seed also embeds the policy documents for RAG.
To (re)embed later:

```bash
uv run python -m app.rag embed
```

## Run

```bash
uv run uvicorn app.main:app --reload --port 8000
```

The backend degrades gracefully if Postgres is down (token issuance and health
still work; order/policy APIs return errors until the DB is reachable).

## Endpoints

| Method | Path                              | Purpose                                          |
| ------ | --------------------------------- | ------------------------------------------------ |
| POST   | `/api/voice/session`              | Create session, return LiveKit token + room name |
| DELETE | `/api/voice/session/{session_id}` | End session                                      |
| GET    | `/api/orders/{order_id}`          | Fetch an order (agent tool)                      |
| GET    | `/api/customers/{identifier}/orders` | List a customer's orders by email or phone    |
| POST   | `/api/orders/{order_id}/return`   | Create a return request                          |
| GET    | `/api/policy/search?q=`           | Semantic policy search (RAG; agent tool)         |
| GET    | `/api/health`                     | Health check                                     |

Interactive docs: http://localhost:8000/docs

## Seeded data (for demos)

Order numbers are short and human-readable so they're natural to say aloud:

- `4521` — Ada, shipped (Wireless Headphones)
- `4522` — Ada, delivered
- `4530` — Grace, placed (not yet shipped)
- `4531` — Grace, returned
- `4540` — Alan, shipped

Customers: `ada@example.com`, `grace@example.com`, `alan@example.com`
(also reachable by phone, e.g. `+15551230001`).
