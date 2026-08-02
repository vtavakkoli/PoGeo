from __future__ import annotations

from collections.abc import Sequence
from typing import Any

import asyncpg


class Database:
    def __init__(self, dsn: str) -> None:
        self._dsn = dsn
        self._pool: asyncpg.Pool | None = None

    async def connect(self) -> None:
        if self._pool is None:
            self._pool = await asyncpg.create_pool(
                dsn=self._dsn,
                min_size=1,
                max_size=10,
                command_timeout=30,
                server_settings={
                    "application_name": "pogeo",
                    "statement_timeout": "30000",
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
