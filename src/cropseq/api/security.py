"""API key check for write endpoints.

1. Read `API_KEY` from config at call time (not import time).
2. If it is empty, the API is open. That is only for local development.
3. Otherwise require `X-API-Key` and compare it in constant time.
4. Return 401 with a plain message; the frontend shows it as-is.
"""

import secrets

from fastapi import Header, HTTPException

from ..config import config


def require_api_key(
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
) -> None:
    """FastAPI dependency guarding POST routes when API_KEY is configured."""
    if not config.api_key:
        return
    if x_api_key is None or not secrets.compare_digest(x_api_key, config.api_key):
        raise HTTPException(status_code=401, detail="Invalid or missing API key.")
