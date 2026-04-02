"""Prometheus gauges for SQLAlchemy connection pool (when METRICS_ENABLED)."""

from __future__ import annotations

from prometheus_client import Gauge

from database.session import engine

_pool_metrics_registered = False


def _pool_in_use() -> float:
    pool = engine.pool
    try:
        if hasattr(pool, "checkedout"):
            return float(pool.checkedout())
    except Exception:
        pass
    return 0.0


def _pool_size() -> float:
    pool = engine.pool
    try:
        if hasattr(pool, "size"):
            return float(pool.size())
    except Exception:
        pass
    return 0.0


def register_db_pool_metrics() -> None:
    """Register pool gauges once per process."""
    global _pool_metrics_registered
    if _pool_metrics_registered:
        return
    in_use = Gauge(
        "db_pool_connections_in_use",
        "Database connections currently checked out from the pool",
    )
    in_use.set_function(_pool_in_use)
    size = Gauge(
        "db_pool_size",
        "Configured database pool size",
    )
    size.set_function(_pool_size)
    _pool_metrics_registered = True
