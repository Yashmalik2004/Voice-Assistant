"""Shared slowapi rate-limiter instance."""

from __future__ import annotations

from slowapi import Limiter
from slowapi.util import get_remote_address
from starlette.requests import Request


def _key_func(request: Request) -> str:
    # Don't rate-limit CORS preflight requests — they come before the actual
    # POST and would consume quota (or return 400) for no-op requests.
    if request.method == "OPTIONS":
        return "exempt-preflight"
    return get_remote_address(request)


limiter = Limiter(key_func=_key_func)
