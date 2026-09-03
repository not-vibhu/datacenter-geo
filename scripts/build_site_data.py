#!/usr/bin/env python3
"""Compile runs/*/analysis.json into one payload the static site can read.

Deliberately a build step rather than a runtime API: the site is then a pile of
static files that Vercel serves from its edge with no server, no database, and no
way for a visitor to trigger an adapter call. The published data is exactly what
is committed in runs/, so anything on the site can be traced back to a run
directory in the repo.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from dcgeo.registry import load_factors, load_profiles, load_sources  # noqa: E402

OUT = ROOT / "site" / "data"

# Measurements worth surfacing to a non-technical reader, in reading order.
HEADLINE = [
    "wtr.wetbulb_profile",
    "clm.dry_bulb_profile",
    "pwr.transmission_proximity",
    "cnx.ixp_proximity",
    "lnd.contiguous_area",
    "lnd.slope",
    "wtr.reclaimed_availability",
    "pwr.onsite_generation_potential",
]


def build() -> dict:
    factors = load_factors()
    profiles = load_profiles()
    sites = []

    for run_dir in sorted((ROOT / "runs").glob("run_*")):
        f = run_dir / "analysis.json"
        if not f.exists():
            continue
        d = json.loads(f.read_text())
        site = d["site"]

        measurements = []
        for m in d["measurements"]:
            spec = factors.get(m["factor_id"])
            if not spec:
                continue
            measurements.append({
                "factor_id": m["factor_id"],
                "name": spec["name"],
                "domain": spec["domain"],
                "question": spec["question"],
                "value": m["value"],
                "unit": m["unit"],
                "tier": m["tier"],
                "source": m["source"],
                "source_url": m.get("source_url"),
                "notes": m.get("notes"),
                "unknown_reason": m.get("unknown_reason"),
                "headline": m["factor_id"] in HEADLINE,
            })

        sites.append({
            "run_id": d["run_id"],
            "created": d["created"],
            "name": site["name"],
            "lat": site["centroid"][0],
            "lon": site["centroid"][1],
            "country": site.get("country"),
            "admin1": site.get("admin1"),
            "admin2": site.get("admin2"),
            "market": site.get("market"),
            "cooling_assumption": d.get("cooling_assumption"),
            "profiles": {
                k: {
                    "score": v["score"],
                    "band": v["band"],
                    "confidence": v["confidence"],
                    "measured_fraction": v["measured_fraction"],
                    "verdict": v["verdict"],
                    "capped_by": v.get("capped_by"),
                    "domain_scores": v["domain_scores"],
                }
                for k, v in d["profiles"].items()
            },
            "gates": [
                {"gate_id": g["gate_id"], "name": g["name"], "outcome": g["outcome"],
                 "reason": g["reason"], "low_confidence": g.get("low_confidence", False)}
                for g in d["gates"]
            ],
            "measurements": measurements,
            "red_team": d.get("red_team", []),
            "recommendations": d.get("recommendations", []),
        })

    # Tier counts across the whole corpus — the honesty dashboard.
    tier_counts: dict[str, int] = {}
    for s in sites:
        for m in s["measurements"]:
            tier_counts[m["tier"]] = tier_counts.get(m["tier"], 0) + 1

    srcs = load_sources()
    return {
        "generated": max((s["created"] for s in sites), default=""),
        "sites": sites,
        "meta": {
            "factor_count": len(factors),
            "domain_count": len({s["domain"] for s in factors.values()}),
            "source_count": len(srcs),
            "keyless_source_count": sum(1 for v in srcs.values() if v.get("auth") == "none"),
            "profiles": {
                k: {"label": v["label"], "description": v["description"].strip()}
                for k, v in profiles["profiles"].items()
            },
            "tier_weights": profiles["tier_weights"],
            "tier_counts": tier_counts,
            "verdict_thresholds": profiles["verdict_thresholds"],
        },
    }


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    payload = build()
    (OUT / "sites.json").write_text(json.dumps(payload, indent=2, default=str))
    n = len(payload["sites"])
    nm = sum(len(s["measurements"]) for s in payload["sites"])
    print(f"wrote site/data/sites.json — {n} sites, {nm} measurements, "
          f"tiers {payload['meta']['tier_counts']}")
