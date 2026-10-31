"""SQLite-backed response cache with TTL (FR-54). Status: stub — task 3.5.

Storage lives in the ``online_cache`` table created by ``frameshot.database``.
"""

from __future__ import annotations

from frameshot.database import Database


class ResponseCache:
    def __init__(self, database: Database) -> None:
        self._database = database

    def get(self, cache_key: str) -> str | None:
        raise NotImplementedError("tasks.md 3.5")

    def put(
        self, cache_key: str, source: str, response_json: str, ttl_seconds: int = 604_800
    ) -> None:
        raise NotImplementedError("tasks.md 3.5")

    def purge_expired(self) -> int:
        raise NotImplementedError("tasks.md 3.5")
