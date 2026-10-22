"""SQLite-backed raw response cache for S2."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sqlite3
from datetime import datetime, timezone
from typing import Any


def make_cache_key(provider: str, request: dict[str, Any]) -> str:
    """Generate a deterministic SHA256 cache key from provider name and request payload."""
    payload = {
        "provider": provider,
        "request": request,
    }
    serialized = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


class SQLiteCache:
    """Stores raw API responses in an SQLite database."""

    def __init__(self, database_path: str | Path) -> None:
        self.database_path = str(database_path)
        if self.database_path != ":memory:":
            Path(self.database_path).parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(self.database_path)
        self._create_table()

    def _create_table(self) -> None:
        self.connection.execute(
            """
            CREATE TABLE IF NOT EXISTS environment_cache (
                cache_key TEXT PRIMARY KEY,
                provider TEXT NOT NULL,
                request_json TEXT NOT NULL,
                response_json TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )
        self.connection.commit()

    def get(self, key: str) -> dict[str, Any] | None:
        cursor = self.connection.execute(
            """
            SELECT response_json FROM environment_cache WHERE cache_key = ?
            """,
            (key,),
        )
        row = cursor.fetchone()
        if row is None:
            return None
        return json.loads(row[0])

    def set(
        self,
        key: str,
        provider: str,
        request: dict[str, Any],
        response: dict[str, Any],
    ) -> None:
        self.connection.execute(
            """
            INSERT OR REPLACE INTO environment_cache (
                cache_key,
                provider,
                request_json,
                response_json,
                created_at
            ) VALUES (?, ?, ?, ?, ?)
            """,
            (
                key,
                provider,
                json.dumps(request, sort_keys=True),
                json.dumps(response),
                datetime.now(timezone.utc).isoformat(),
            ),
        )
        self.connection.commit()

    def close(self) -> None:
        self.connection.close()
