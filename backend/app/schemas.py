"""Pydantic request/response models for the API."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class CreateSessionRequest(BaseModel):
    """Optional hints the widget may send when starting a call."""

    # An optional display name for the customer participant. Not PII-sensitive;
    # defaults to a generic label when omitted.
    customer_name: str | None = Field(default=None, max_length=80)


class CreateSessionResponse(BaseModel):
    """Everything the widget needs to join the LiveKit room."""

    session_id: str
    room_name: str
    participant_identity: str
    token: str
    livekit_url: str
    expires_at: datetime


class HealthResponse(BaseModel):
    status: str
    livekit_configured: bool


class SessionEndedResponse(BaseModel):
    session_id: str
    ended: bool


# ── Order / customer / return models (Milestone 5) ──


class OrderItem(BaseModel):
    name: str
    qty: int
    price: float


class OrderResponse(BaseModel):
    id: str
    customer_id: str
    status: str
    items: list[OrderItem]
    total: float
    tracking_number: str | None = None
    estimated_delivery: str | None = None
    created_at: datetime
    updated_at: datetime


class CustomerOrdersResponse(BaseModel):
    customer_id: str
    customer_name: str
    orders: list[OrderResponse]


class ReturnRequest(BaseModel):
    reason: str = Field(min_length=1, max_length=500)


class ReturnResponse(BaseModel):
    id: str
    order_id: str
    reason: str
    status: str
    created_at: datetime


class PolicyMatch(BaseModel):
    id: str
    category: str
    title: str
    content: str
    score: float


class PolicySearchResponse(BaseModel):
    query: str
    results: list[PolicyMatch]
    # False when embeddings aren't configured (no OpenAI key); the agent then
    # avoids answering policy questions rather than guessing.
    rag_available: bool
