from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass
from time import monotonic


@dataclass(frozen=True, slots=True)
class CacheStats:
    hits: int
    misses: int
    size: int
    max_items: int
    ttl_seconds: float


class TTLCache[K, V]:
    """Small bounded TTL cache optimized for event-loop-local use."""

    def __init__(self, *, max_items: int, ttl_seconds: float) -> None:
        if max_items < 1:
            raise ValueError("max_items must be positive")
        if ttl_seconds <= 0:
            raise ValueError("ttl_seconds must be positive")
        self._max_items = max_items
        self._ttl_seconds = ttl_seconds
        self._values: OrderedDict[K, tuple[float, V]] = OrderedDict()
        self._hits = 0
        self._misses = 0

    def get(self, key: K) -> V | None:
        entry = self._values.get(key)
        if entry is None:
            self._misses += 1
            return None

        expires_at, value = entry
        if expires_at <= monotonic():
            del self._values[key]
            self._misses += 1
            return None

        self._values.move_to_end(key)
        self._hits += 1
        return value

    def set(self, key: K, value: V) -> None:
        self._values[key] = (monotonic() + self._ttl_seconds, value)
        self._values.move_to_end(key)
        while len(self._values) > self._max_items:
            self._values.popitem(last=False)

    def clear(self) -> None:
        self._values.clear()

    @property
    def stats(self) -> CacheStats:
        return CacheStats(
            hits=self._hits,
            misses=self._misses,
            size=len(self._values),
            max_items=self._max_items,
            ttl_seconds=self._ttl_seconds,
        )
