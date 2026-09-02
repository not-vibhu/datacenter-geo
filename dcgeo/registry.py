"""Loads the factor specs and config. Single source of truth for what a metric means.

The factor layer is the contract between agents and measurements: agents read it to
know what to research, the scoring engine reads it to know how to normalize, and the
docs generator reads it to write the methodology page.
"""
from __future__ import annotations

import functools
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parent.parent
FACTOR_DIR = ROOT / "factors"
CONFIG_DIR = ROOT / "config"


class RegistryError(Exception):
    pass


@functools.lru_cache(maxsize=1)
def load_factors() -> dict[str, dict[str, Any]]:
    """factor_id -> spec (with `domain` and `domain_weight` injected)."""
    factors: dict[str, dict[str, Any]] = {}
    for path in sorted(FACTOR_DIR.glob("*.yaml")):
        doc = yaml.safe_load(path.read_text())
        domain = doc["domain"]
        dweight = doc.get("domain_weight", {})
        for spec in doc["factors"]:
            fid = spec["id"]
            if fid in factors:
                raise RegistryError(f"duplicate factor id {fid} in {path}")
            spec["domain"] = domain
            spec["domain_weight"] = dweight
            spec["_source_file"] = path.name
            factors[fid] = spec
    if not factors:
        raise RegistryError(f"no factors found in {FACTOR_DIR}")
    return factors


@functools.lru_cache(maxsize=1)
def load_profiles() -> dict[str, Any]:
    return yaml.safe_load((CONFIG_DIR / "profiles.yaml").read_text())


@functools.lru_cache(maxsize=1)
def load_gates() -> list[dict[str, Any]]:
    return yaml.safe_load((CONFIG_DIR / "gates.yaml").read_text())["gates"]


@functools.lru_cache(maxsize=1)
def _sources_doc() -> dict[str, Any]:
    return yaml.safe_load((CONFIG_DIR / "sources.yaml").read_text())


@functools.lru_cache(maxsize=1)
def load_sources() -> dict[str, Any]:
    return _sources_doc()["sources"]


@functools.lru_cache(maxsize=1)
def load_source_aliases() -> dict[str, str]:
    """Readable per-dataset names used in factor specs -> canonical source id.

    Factor specs say `gem_retired_plants` rather than `gem_trackers` on purpose:
    it documents which part of a source a measurement came from, which is what you
    need when a number looks wrong.
    """
    return _sources_doc().get("aliases", {}) or {}


def resolve_source(name: str) -> str | None:
    """Canonical source id for a name used in a factor spec, or None if unknown."""
    if name == "derived":
        return "derived"
    srcs = load_sources()
    if name in srcs:
        return name
    return load_source_aliases().get(name)


def domains() -> dict[str, dict[str, Any]]:
    """domain -> {weight: {...}, factors: [...]}"""
    out: dict[str, dict[str, Any]] = {}
    for fid, spec in load_factors().items():
        d = out.setdefault(spec["domain"], {"weight": spec["domain_weight"], "factors": []})
        d["factors"].append(fid)
    return out


def factors_for_domain(domain: str) -> list[dict[str, Any]]:
    return [s for s in load_factors().values() if s["domain"] == domain]


def profile_names() -> list[str]:
    return list(load_profiles()["profiles"].keys())


def validate() -> list[str]:
    """Structural checks. Returns a list of problems; empty means healthy.

    Run by `dcgeo doctor` and by CI. Catching a malformed scale here is far cheaper
    than discovering it halfway through a 2000-site sweep.
    """
    problems: list[str] = []
    factors = load_factors()
    profiles = load_profiles()
    pnames = set(profiles["profiles"])
    gate_ids = {g["id"] for g in load_gates()}

    for fid, spec in factors.items():
        for key in ("name", "question", "unit", "direction", "best_tier", "weights"):
            if key not in spec:
                problems.append(f"{fid}: missing required key '{key}'")

        missing_w = pnames - set(spec.get("weights", {}))
        if missing_w:
            problems.append(f"{fid}: no weight for profile(s) {sorted(missing_w)}")

        if spec.get("direction") == "categorical":
            if "categories" not in spec:
                problems.append(f"{fid}: categorical factor with no categories")
        elif "scale" in spec:
            pts = spec["scale"].get("points", [])
            if len(pts) < 2:
                problems.append(f"{fid}: scale needs >= 2 points")
            xs = [p[0] for p in pts]
            if xs != sorted(xs):
                problems.append(f"{fid}: scale points must ascend by x")
            for _, y in pts:
                if not 0 <= y <= 100:
                    problems.append(f"{fid}: scale y value {y} outside 0-100")
        elif "composite_of" not in spec:
            problems.append(f"{fid}: no scale, categories, or composite_of")

        if (g := spec.get("gate")) and g not in gate_ids:
            problems.append(f"{fid}: references unknown gate '{g}'")

        for s in spec.get("sources", []):
            if resolve_source(s) is None:
                problems.append(f"{fid}: references unregistered source '{s}'")

    for alias, target in load_source_aliases().items():
        if target not in load_sources():
            problems.append(f"alias '{alias}' points at unregistered source '{target}'")
        if alias in load_sources():
            problems.append(f"alias '{alias}' shadows a real source of the same name")

    for g in load_gates():
        for p in g.get("applies_to_profiles", []):
            if p not in pnames:
                problems.append(f"{g['id']}: applies to unknown profile '{p}'")

    return problems
