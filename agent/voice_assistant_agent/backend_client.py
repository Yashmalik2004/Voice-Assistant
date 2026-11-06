"""Thin async HTTP client for the Voice Assistant backend's internal APIs.

Sends X-Internal-Secret when INTERNAL_API_SECRET is set (Milestone 7 hardening).
"""

from __future__ import annotations

import logging
import os

import httpx

from . import config

logger = logging.getLogger("Voice Assistant.backend")

_TIMEOUT = httpx.Timeout(8.0)


def _headers() -> dict[str, str]:
    secret = os.getenv("INTERNAL_API_SECRET", "")
    if secret:
        return {"X-Internal-Secret": secret}
    return {}


async def _get(path: str, params: dict | None = None) -> httpx.Response | None:
    url = f"{config.BACKEND_URL}{path}"
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            return await client.get(url, params=params, headers=_headers())
    except httpx.HTTPError as exc:
        logger.warning("Backend GET %s failed: %s", path, exc)
        return None


async def _post(path: str, json: dict) -> httpx.Response | None:
    url = f"{config.BACKEND_URL}{path}"
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            return await client.post(url, json=json, headers=_headers())
    except httpx.HTTPError as exc:
        logger.warning("Backend POST %s failed: %s", path, exc)
        return None


async def get_order(order_id: str) -> dict | None:
    """Fetch a single order. Returns None if not found or on error."""
    resp = await _get(f"/api/orders/{order_id}")
    if resp is None or resp.status_code != 200:
        return None
    return resp.json()


async def get_customer_orders(identifier: str) -> dict | None:
    """Fetch a customer's orders by email or phone. None if not found."""
    resp = await _get(f"/api/customers/{identifier}/orders")
    if resp is None or resp.status_code != 200:
        return None
    return resp.json()


async def search_policy(query: str, limit: int = 3) -> dict | None:
    """Semantic policy search. Returns the response dict (may have empty
    results / rag_available False) or None on transport error."""
    resp = await _get("/api/policy/search", params={"q": query, "limit": limit})
    if resp is None or resp.status_code != 200:
        return None
    return resp.json()


async def create_return(order_id: str, reason: str) -> dict | None:
    """Create a return request. None if the order isn't found or on error."""
    resp = await _post(f"/api/orders/{order_id}/return", json={"reason": reason})
    if resp is None or resp.status_code != 201:
        return None
    return resp.json()
