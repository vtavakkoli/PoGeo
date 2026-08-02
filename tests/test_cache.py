from time import sleep

from pogeo.cache import TTLCache


def test_ttl_cache_tracks_hits_and_evicts_oldest_item() -> None:
    cache: TTLCache[str, bytes] = TTLCache(max_items=2, ttl_seconds=60)
    cache.set("one", b"1")
    cache.set("two", b"2")

    assert cache.get("one") == b"1"
    cache.set("three", b"3")

    assert cache.get("two") is None
    assert cache.get("one") == b"1"
    assert cache.stats.hits == 2
    assert cache.stats.misses == 1
    assert cache.stats.size == 2


def test_ttl_cache_expires_values() -> None:
    cache: TTLCache[str, str] = TTLCache(max_items=1, ttl_seconds=0.001)
    cache.set("key", "value")
    sleep(0.01)

    assert cache.get("key") is None
    assert cache.stats.size == 0
