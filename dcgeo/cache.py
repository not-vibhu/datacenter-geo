"""On-disk measurement cache.

Scanning thousands of sites is only tractable if measurements are reused. Keyed by
(factor, source, geohash, params) and expired per the TTL in config/sources.yaml.
"""
from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path
from typing import Any

from .registry import ROOT, load_sources, resolve_source

CACHE_DIR = ROOT / "data" / "cache"


def _key(factor_id: str, source: str, geo: str, params: dict[str, Any] | None) -> str:
    blob = json.dumps(params or {}, sort_keys=True, default=str)
    h = hashlib.sha256(f"{factor_id}|{source}|{geo}|{blob}".encode()).hexdigest()[:16]
    return f"{source}__{factor_id.replace('.', '_')}__{geo}__{h}.json"


def _ttl_seconds(source: str) -> float:
    canonical = resolve_source(source) or source
    spec = load_sources().get(canonical, {})
    return float(spec.get("ttl_days", 30)) * 86400


def get(factor_id: str, source: str, geo: str, params: dict | None = None) -> dict | None:
    path = CACHE_DIR / _key(factor_id, source, geo, params)
    if not path.exists():
        return None
    if time.time() - path.stat().st_mtime > _ttl_seconds(source):
        return None
    try:
        return json.loads(path.read_text())
    except json.JSONDecodeError:
        path.unlink(missing_ok=True)
        return None


def put(factor_id: str, source: str, geo: str, payload: dict, params: dict | None = None) -> None:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    (CACHE_DIR / _key(factor_id, source, geo, params)).write_text(
        json.dumps(payload, indent=2, default=str)
    )


def clear(older_than_days: float | None = None) -> int:
    if not CACHE_DIR.exists():
        return 0
    n = 0
    cutoff = time.time() - (older_than_days or 0) * 86400
    for p in CACHE_DIR.glob("*.json"):
        if older_than_days is None or p.stat().st_mtime < cutoff:
            p.unlink()
            n += 1
    return n


def stats() -> dict[str, Any]:
    if not CACHE_DIR.exists():
        return {"entries": 0, "bytes": 0}
    files = list(CACHE_DIR.glob("*.json"))
    return {"entries": len(files), "bytes": sum(f.stat().st_size for f in files)}
