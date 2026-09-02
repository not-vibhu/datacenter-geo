"""Adapter contract.

An adapter measures. It never judges, never scores, and never raises past the
caller — a dead API returns an unknown Measurement so a 59-factor analysis is not
aborted by one bad endpoint.
"""
from __future__ import annotations

import os
from typing import Any

import httpx

from ..cache import get as cache_get, put as cache_put
from ..geo import geohash
from ..models import Measurement, Tier

USER_AGENT = "datacenter-geo/0.1 (+https://github.com/datacenter-geo/datacenter-geo)"
DEFAULT_TIMEOUT = 30.0


class SourceUnavailable(Exception):
    """Raised inside an adapter; converted to an unknown Measurement by the caller."""


def unknown(factor_id: str, source: str, reason: str, unit: str = "") -> Measurement:
    return Measurement(
        factor_id=factor_id, value=None, unit=unit, tier="unknown",
        source=source, unknown_reason=reason,
    )


def measured(
    factor_id: str,
    value: Any,
    unit: str,
    tier: Tier,
    source: str,
    *,
    lat: float | None = None,
    lon: float | None = None,
    source_url: str | None = None,
    raw: dict | None = None,
    notes: str | None = None,
) -> Measurement:
    return Measurement(
        factor_id=factor_id, value=value, unit=unit, tier=tier, source=source,
        source_url=source_url, raw=raw, notes=notes,
        geometry_ref=f"geohash:{geohash(lat, lon)}" if lat is not None and lon is not None else None,
    )


def http_get(url: str, params: dict | None = None, timeout: float = DEFAULT_TIMEOUT, **kw) -> Any:
    """GET returning parsed JSON. Raises SourceUnavailable on any failure."""
    try:
        r = httpx.get(
            url, params=params, timeout=timeout,
            headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
            follow_redirects=True, **kw,
        )
        r.raise_for_status()
        return r.json()
    except httpx.HTTPStatusError as e:
        raise SourceUnavailable(f"HTTP {e.response.status_code} from {url}") from e
    except Exception as e:  # network, timeout, malformed JSON
        raise SourceUnavailable(f"{type(e).__name__}: {e}") from e


def http_post(url: str, data: Any = None, timeout: float = 90.0, **kw) -> Any:
    try:
        r = httpx.post(
            url, data=data, timeout=timeout,
            headers={"User-Agent": USER_AGENT}, follow_redirects=True, **kw,
        )
        r.raise_for_status()
        return r.json()
    except httpx.HTTPStatusError as e:
        raise SourceUnavailable(f"HTTP {e.response.status_code} from {url}") from e
    except Exception as e:
        raise SourceUnavailable(f"{type(e).__name__}: {e}") from e


def cached(factor_id: str, source: str, lat: float, lon: float, params: dict | None = None):
    """Decorator-free cache helper. Returns (hit_or_None, store_fn)."""
    geo = geohash(lat, lon)
    hit = cache_get(factor_id, source, geo, params)

    def store(payload: dict) -> None:
        cache_put(factor_id, source, geo, payload, params)

    return hit, store


def require_key(env_var: str) -> str | None:
    """Paid and keyed adapters call this. Returns None when the key is absent, which
    the adapter must convert into an unknown Measurement rather than an error."""
    return os.environ.get(env_var) or None
