# Voice Assistant — Demo Data & Agent Capabilities

This file documents the seeded mock dataset and what you can ask the agent.
Re-seed anytime with: `docker compose exec backend python -m app.db.seed`

---

## Customers

| Name | Email | Phone |
|---|---|---|
| Ada Lovelace | ada@example.com | +15551230001 |
| Grace Hopper | grace@example.com | +15551230002 |
| Alan Turing | alan@example.com | +15551230003 |

---

## Orders

| Order # | Customer | Status | Items | Total |
|---|---|---|---|---|
| **4521** | Ada Lovelace | shipped | Wireless Headphones (×1) | $89.99 |
| **4522** | Ada Lovelace | delivered | USB-C Cable 2m (×2), Phone Stand (×1) | $40.00 |
| **4530** | Grace Hopper | placed (not yet shipped) | Mechanical Keyboard (×1) | $129.00 |
| **4531** | Grace Hopper | returned | Laptop Sleeve 14" (×1) | $24.99 |
| **4540** | Alan Turing | shipped | Bluetooth Mouse (×1), Mouse Pad XL (×1) | $54.98 |

Tracking numbers follow the pattern `1Z-VD-{order}-US`. Orders 4521 and 4540
have an estimated delivery of "in 2 days" and "in 4 days" respectively.

---

## Returns

| Return ID | Order | Reason | Status |
|---|---|---|---|
| ret-4531 | 4531 | Item was too small. | completed |

---

## Policy Documents (for RAG)

| Document | Category |
|---|---|
| Returns and Refunds Policy | returns |
| Shipping and Delivery | shipping |
| Sizing, Colors, and Product Variations | product |
| Warranty and Defective Items | product |

> **Note:** Policy documents need to be embedded with OpenAI before the agent
> can answer policy questions. Run:
> ```bash
> docker compose exec backend python -m app.rag embed
> ```

---

## What You Can Ask the Agent

### 1. Order status
Look up by order number or by the customer's email / phone:

> *"Where is my order 4521?"*
> *"What's the status of order four five two one?"*
> *"What orders do I have? My email is ada@example.com"*
> *"Can you look up my orders? My phone is +15551230002"*

### 2. Start a return
The agent will confirm the order number and reason, then create the request:

> *"I want to return order 4521."*
> *"I'd like to return my headphones — they don't fit."*
> *"Can I return the keyboard from order 4530?"*

### 3. Policy and product questions
Answered from the embedded policy documents (requires `app.rag embed` to have
been run with a valid `OPENAI_API_KEY`):

> *"What's your return policy?"*
> *"How long does standard shipping take?"*
> *"My item arrived damaged — what do I do?"*
> *"Does this come in a different size?"*
> *"Is there a warranty on electronics?"*

### Out of scope (agent will say so)
- Payment processing or refunds
- Changing or cancelling an order
- Human agent escalation (flagged as a future feature in the spec)
