from __future__ import annotations

from collections.abc import Sequence
from typing import Any

import asyncpg


class Database:
    def __init__(
        self,
        dsn: str,
        *,
        min_size: int = 2,
        max_size: int = 20,
        statement_timeout_ms: int = 15_000,
        connect_timeout_seconds: float = 10.0,
        max_queries_per_connection: int = 50_000,
        max_idle_seconds: float = 300.0,
    ) -> None:
        self._dsn = dsn
        self._min_size = min_size
        self._max_size = max_size
        self._statement_timeout_ms = statement_timeout_ms
        self._connect_timeout_seconds = connect_timeout_seconds
        self._max_queries_per_connection = max_queries_per_connection
        self._max_idle_seconds = max_idle_seconds
        self._pool: asyncpg.Pool | None = None

    async def connect(self) -> None:
        if self._pool is None:
            self._pool = await asyncpg.create_pool(
                dsn=self._dsn,
                min_size=self._min_size,
                max_size=self._max_size,
                timeout=self._connect_timeout_seconds,
                command_timeout=self._statement_timeout_ms / 1000,
                max_queries=self._max_queries_per_connection,
                max_inactive_connection_lifetime=self._max_idle_seconds,
                statement_cache_size=1024,
                server_settings={
                    "application_name": "pogeo",
                    "statement_timeout": str(self._statement_timeout_ms),
                    "jit": "off",
                },
            )

    async def close(self) -> None:
        if self._pool is not None:
            await self._pool.close()
            self._pool = None

    def _require_pool(self) -> asyncpg.Pool:
        if self._pool is None:
            raise RuntimeError("Database pool is not initialized")
        return self._pool

    async def fetch(self, query: str, *args: Any) -> Sequence[asyncpg.Record]:
        return await self._require_pool().fetch(query, *args)

    async def fetchrow(self, query: str, *args: Any) -> asyncpg.Record | None:
        return await self._require_pool().fetchrow(query, *args)

    async def fetchval(self, query: str, *args: Any) -> Any:
        return await self._require_pool().fetchval(query, *args)

    async def ping(self) -> bool:
        return bool(await self.fetchval("SELECT TRUE"))
