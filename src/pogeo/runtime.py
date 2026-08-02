from __future__ import annotations

from dataclasses import dataclass

from pogeo.catalog import Catalog
from pogeo.config import Settings
from pogeo.database import Database
from pogeo.geospatial import GeoService


@dataclass(slots=True)
class Runtime:
    settings: Settings
    catalog: Catalog
    database: Database
    geo: GeoService


_runtime: Runtime | None = None


def set_runtime(runtime: Runtime | None) -> None:
    global _runtime
    _runtime = runtime


def get_runtime() -> Runtime:
    if _runtime is None:
        raise RuntimeError("PoGeo runtime is not initialized")
    return _runtime
