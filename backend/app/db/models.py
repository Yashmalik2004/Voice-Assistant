"""SQLAlchemy ORM models (spec section 5.2).

Tables: customers, orders, returns, policy_documents (with pgvector embedding),
and sessions. Kept intentionally small for the v1 mock dataset.
"""

from __future__ import annotations

import enum
import uuid
from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    DateTime,
    Enum,
    ForeignKey,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from ..config import get_settings

_EMBED_DIM = get_settings().embedding_dim


class Base(DeclarativeBase):
    pass


def _uuid() -> str:
    return str(uuid.uuid4())


class OrderStatus(str, enum.Enum):
    placed = "placed"
    shipped = "shipped"
    delivered = "delivered"
    returned = "returned"


class ReturnStatus(str, enum.Enum):
    requested = "requested"
    approved = "approved"
    rejected = "rejected"
    completed = "completed"


class Customer(Base):
    __tablename__ = "customers"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    email: Mapped[str | None] = mapped_column(String(200), unique=True, nullable=True)
    phone: Mapped[str | None] = mapped_column(String(40), unique=True, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    orders: Mapped[list["Order"]] = relationship(back_populates="customer")


class Order(Base):
    __tablename__ = "orders"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    customer_id: Mapped[str] = mapped_column(ForeignKey("customers.id"), nullable=False)
    status: Mapped[OrderStatus] = mapped_column(
        Enum(OrderStatus, name="order_status"), nullable=False, default=OrderStatus.placed
    )
    # List of {name, qty, price} dicts.
    items: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    total: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False, default=0)
    # Optional courier tracking info for shipped orders.
    tracking_number: Mapped[str | None] = mapped_column(String(80), nullable=True)
    estimated_delivery: Mapped[str | None] = mapped_column(String(80), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    customer: Mapped["Customer"] = relationship(back_populates="orders")
    returns: Mapped[list["Return"]] = relationship(back_populates="order")


class Return(Base):
    __tablename__ = "returns"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    order_id: Mapped[str] = mapped_column(ForeignKey("orders.id"), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[ReturnStatus] = mapped_column(
        Enum(ReturnStatus, name="return_status"),
        nullable=False,
        default=ReturnStatus.requested,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    order: Mapped["Order"] = relationship(back_populates="returns")


class PolicyDocument(Base):
    __tablename__ = "policy_documents"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    category: Mapped[str] = mapped_column(String(60), nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    # Nullable so seeding can insert docs even before embeddings are computed
    # (e.g. when OPENAI_API_KEY is absent). RAG search skips unembedded rows.
    embedding: Mapped[list[float] | None] = mapped_column(Vector(_EMBED_DIM), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class Session(Base):
    __tablename__ = "sessions"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    room_name: Mapped[str] = mapped_column(String(120), nullable=False)
    # Nullable — the caller may be anonymous until identified mid-call.
    customer_id: Mapped[str | None] = mapped_column(
        ForeignKey("customers.id"), nullable=True
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # Optional transcript log for QA/debugging.
    transcript_log: Mapped[list | None] = mapped_column(JSONB, nullable=True)
