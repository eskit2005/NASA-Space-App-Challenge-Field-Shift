"""Shared HTTP client used by stage adapters.

1. `get_json()` sends a GET request and returns JSON.
2. Each request has a configurable timeout (15s by default).
3. Failed requests are retried up to 3 times.
4. Only temporary failures are retried: timeouts, network errors, 429 and 5xx.
5. Other errors (e.g. 400) are raised immediately.
6. `empty_statuses` lets an adapter treat 204/404 as "no data" instead of an error.
"""

from __future__ import annotations

from typing import Any

import httpx
from tenacity import (
    retry,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential,
)


def _is_retryable_error(exc: BaseException) -> bool:
    if isinstance(
        exc, (httpx.TimeoutException, httpx.NetworkError, httpx.RemoteProtocolError)
    ):
        return True
    if isinstance(exc, httpx.HTTPStatusError):
        # Retry on rate limit (429) or transient server errors (5xx)
        return exc.response.status_code in {429, 500, 502, 503, 504}
    return False


class HttpClient:
    """HTTP client with timeout and exponential backoff retry."""

    def __init__(self, *, timeout: float = 15.0, max_attempts: int = 3) -> None:
        self.timeout = timeout
        self.max_attempts = max_attempts

    async def get_json(
        self,
        url: str,
        *,
        params: Any = None,
        headers: dict[str, str] | None = None,
        empty_statuses: set[int] | None = None,
    ) -> Any:
        """GET `url` and return JSON, or None for an allowed empty status."""
        empty = empty_statuses or set()

        @retry(
            retry=retry_if_exception(_is_retryable_error),
            wait=wait_exponential(multiplier=0.1, min=0.1, max=1.0),
            stop=stop_after_attempt(self.max_attempts),
            reraise=True,
        )
        async def _fetch() -> Any:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(url, params=params, headers=headers)
                if response.status_code in empty:
                    return None
                response.raise_for_status()
                return response.json()

        return await _fetch()
