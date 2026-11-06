"""Seed the mock Voice Assistant dataset.

Populates customers, orders (across all statuses), a sample return, and the
policy documents used for RAG. Idempotent: it clears the domain tables first,
so re-running gives a clean, deterministic dataset.

Order IDs are short and human-readable (e.g. "4521") because callers say them
aloud — "Where's my order 4521?" — which keeps the voice demo natural.

Policy-document embeddings are computed separately (see ``rag.py`` /
``embed_policies``); this script inserts the text with a null embedding so the
data is usable even before an OpenAI key is configured.

Run:
    uv run python -m app.db.seed
"""

from __future__ import annotations

import asyncio
import logging

from sqlalchemy import text

from .models import Customer, Order, OrderStatus, PolicyDocument, Return, ReturnStatus
from .session import SessionLocal, engine, init_db

logger = logging.getLogger("Voice Assistant.seed")


# ── Mock customers ──
CUSTOMERS = [
    {
        "id": "cust-ada",
        "name": "Ada Lovelace",
        "email": "ada@example.com",
        "phone": "+15551230001",
    },
    {
        "id": "cust-grace",
        "name": "Grace Hopper",
        "email": "grace@example.com",
        "phone": "+15551230002",
    },
    {
        "id": "cust-alan",
        "name": "Alan Turing",
        "email": "alan@example.com",
        "phone": "+15551230003",
    },
]


# ── Mock orders (short human-readable ids; various statuses) ──
ORDERS = [
    {
        "id": "4521",
        "customer_id": "cust-ada",
        "status": OrderStatus.shipped,
        "items": [{"name": "Wireless Headphones", "qty": 1, "price": 89.99}],
        "total": 89.99,
        "tracking_number": "1Z-VD-4521-US",
        "estimated_delivery": "in 2 days",
    },
    {
        "id": "4522",
        "customer_id": "cust-ada",
        "status": OrderStatus.delivered,
        "items": [
            {"name": "USB-C Cable (2m)", "qty": 2, "price": 12.50},
            {"name": "Phone Stand", "qty": 1, "price": 15.00},
        ],
        "total": 40.00,
        "tracking_number": "1Z-VD-4522-US",
        "estimated_delivery": "delivered",
    },
    {
        "id": "4530",
        "customer_id": "cust-grace",
        "status": OrderStatus.placed,
        "items": [{"name": "Mechanical Keyboard", "qty": 1, "price": 129.00}],
        "total": 129.00,
        "tracking_number": None,
        "estimated_delivery": "not yet shipped",
    },
    {
        "id": "4531",
        "customer_id": "cust-grace",
        "status": OrderStatus.returned,
        "items": [{"name": "Laptop Sleeve 14\"", "qty": 1, "price": 24.99}],
        "total": 24.99,
        "tracking_number": "1Z-VD-4531-US",
        "estimated_delivery": "delivered",
    },
    {
        "id": "4540",
        "customer_id": "cust-alan",
        "status": OrderStatus.shipped,
        "items": [
            {"name": "Bluetooth Mouse", "qty": 1, "price": 34.99},
            {"name": "Mouse Pad (XL)", "qty": 1, "price": 19.99},
        ],
        "total": 54.98,
        "tracking_number": "1Z-VD-4540-US",
        "estimated_delivery": "in 4 days",
    },
]


# ── Existing return (for order 4531, which is in returned status) ──
RETURNS = [
    {
        "id": "ret-4531",
        "order_id": "4531",
        "reason": "Item was too small.",
        "status": ReturnStatus.completed,
    },
]


# ── Policy documents for RAG (shipping / returns / FAQ) ──
POLICY_DOCUMENTS = [
    {
        "id": "policy-returns",
        "category": "returns",
        "title": "Returns and Refunds Policy",
        "content": (
            "You can return most items within 30 days of delivery for a full "
            "refund. Items must be unused and in their original packaging. "
            "Electronics can be returned within 15 days. Once we receive the "
            "returned item, refunds are processed to the original payment "
            "method within 5 to 7 business days. Final-sale and personalized "
            "items cannot be returned. To start a return, ask our support agent "
            "and we'll create the request for you."
        ),
    },
    {
        "id": "policy-shipping",
        "category": "shipping",
        "title": "Shipping and Delivery",
        "content": (
            "Standard shipping takes 3 to 5 business days and is free on orders "
            "over 35 dollars. Expedited shipping takes 1 to 2 business days for "
            "a flat 12 dollar fee. Orders placed before 2 PM ship the same "
            "business day. We ship within the United States only. You'll get a "
            "tracking number by email once your order ships."
        ),
    },
    {
        "id": "policy-sizing",
        "category": "product",
        "title": "Sizing, Colors, and Product Variations",
        "content": (
            "Most apparel and accessories come in multiple sizes and colors. If "
            "an item is available in another size or color, the option appears "
            "on the product page. If a variation is out of stock, you can sign "
            "up to be notified when it returns. Exchanges for a different size "
            "or color follow the standard return process."
        ),
    },
    {
        "id": "policy-warranty",
        "category": "product",
        "title": "Warranty and Defective Items",
        "content": (
            "Electronics include a one-year limited warranty covering "
            "manufacturing defects. If an item arrives damaged or defective, "
            "contact support within 30 days for a free replacement or refund. "
            "Accidental damage is not covered by the warranty."
        ),
    },
]


async def _clear(db) -> None:
    # Order matters for FKs; CASCADE + RESTART keeps it clean and idempotent.
    await db.execute(
        text("TRUNCATE returns, orders, customers, policy_documents RESTART IDENTITY CASCADE")
    )


async def seed() -> None:
    await init_db()
    async with SessionLocal() as db:
        await _clear(db)

        for c in CUSTOMERS:
            db.add(Customer(**c))
        for o in ORDERS:
            db.add(Order(**o))
        for r in RETURNS:
            db.add(Return(**r))
        for p in POLICY_DOCUMENTS:
            db.add(PolicyDocument(**p))

        await db.commit()

        # Best-effort: embed policy docs now if an OpenAI key is configured.
        # Without a key this is a no-op; run `uv run python -m app.rag embed`
        # later once the key is set.
        from ..rag import embed_policies

        embedded = await embed_policies(db)

    logger.info(
        "Seeded %d customers, %d orders, %d returns, %d policy documents "
        "(%d embedded)",
        len(CUSTOMERS),
        len(ORDERS),
        len(RETURNS),
        len(POLICY_DOCUMENTS),
        embedded,
    )
    await engine.dispose()


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    asyncio.run(seed())


if __name__ == "__main__":
    main()
