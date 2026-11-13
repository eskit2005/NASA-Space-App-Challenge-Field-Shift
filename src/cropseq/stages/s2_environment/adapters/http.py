"""Shared HTTP client for S2 adapters.

1. The real implementation lives in `cropseq.http`.
2. This module re-exports `HttpClient` so existing S2 imports keep working.
"""

from cropseq.http import HttpClient

__all__ = ["HttpClient"]
