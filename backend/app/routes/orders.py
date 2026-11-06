"""Order, customer, and return endpoints (spec section 5.1).

These are internal APIs consumed by the agent's function tools. They query the
seeded mock Postgres database so the agent's spoken answers are grounded in real
data (never hallucinated).
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..auth import require_internal
from ..config import get_settings
from ..db.models import Customer, Order, Return
from ..db.session import get_db
from ..rag import search_policies
from ..schemas import (
    CustomerOrdersResponse,
    OrderResponse,
    PolicySearchResponse,
    ReturnRequest,
    ReturnResponse,
)

logger = logging.getLogger("Voice Assistant.orders")

router = APIRouter(
    prefix="/api",
    tags=["orders"],
    # All order/customer/policy routes require the internal secret when configured.
    dependencies=[Depends(require_internal)],
)


def _order_to_response(order: Order) -> OrderResponse:
    return OrderResponse(
        id=order.id,
        customer_id=order.customer_id,
        status=order.status.value,
        items=order.items or [],
        total=float(order.total),
        tracking_number=order.tracking_number,
        estimated_delivery=order.estimated_delivery,
        created_at=order.created_at,
        updated_at=order.updated_at,
    )


@router.get("/orders/{order_id}", response_model=OrderResponse)
async def get_order(order_id: str, db: AsyncSession = Depends(get_db)) -> OrderResponse:
    """Fetch a single order by id."""
    order = await db.get(Order, order_id)
    if order is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")
    return _order_to_response(order)


@router.get("/customers/{identifier}/orders", response_model=CustomerOrdersResponse)
async def get_customer_orders(
    identifier: str, db: AsyncSession = Depends(get_db)
) -> CustomerOrdersResponse:
    """List orders for a customer, looked up by email or phone.

    ``identifier`` is matched against both email and phone so the agent can use
    whichever the caller provides.
    """
    stmt = (
        select(Customer)
        .where((Customer.email == identifier) | (Customer.phone == identifier))
        .options(selectinload(Customer.orders))
    )
    customer = (await db.execute(stmt)).scalar_one_or_none()
    if customer is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Customer not found"
        )

    orders = sorted(customer.orders, key=lambda o: o.created_at, reverse=True)
    return CustomerOrdersResponse(
        customer_id=customer.id,
        customer_name=customer.name,
        orders=[_order_to_response(o) for o in orders],
    )


@router.post(
    "/orders/{order_id}/return",
    response_model=ReturnResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_return(
    order_id: str, body: ReturnRequest, db: AsyncSession = Depends(get_db)
) -> ReturnResponse:
    """Create a return request for an order.

    v1 records the *request* only — fulfillment is out of scope (spec section 10).
    """
    order = await db.get(Order, order_id)
    if order is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")

    ret = Return(order_id=order_id, reason=body.reason)
    db.add(ret)
    await db.commit()
    await db.refresh(ret)

    logger.info("Created return %s for order %s", ret.id, order_id)
    return ReturnResponse(
        id=ret.id,
        order_id=ret.order_id,
        reason=ret.reason,
        status=ret.status.value,
        created_at=ret.created_at,
    )


@router.get("/policy/search", response_model=PolicySearchResponse)
async def policy_search(
    q: str, limit: int = 3, db: AsyncSession = Depends(get_db)
) -> PolicySearchResponse:
    """Semantic search over policy documents for the agent's policy tool.

    Returns an empty result set (with rag_available=False) when embeddings are
    not configured, so the agent can gracefully decline rather than hallucinate.
    """
    results = await search_policies(db, q, limit=limit)
    return PolicySearchResponse(
        query=q,
        results=results,  # type: ignore[arg-type]
        rag_available=get_settings().embeddings_configured,
    )
