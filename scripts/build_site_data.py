#!/usr/bin/env python3
"""Compile runs/*/analysis.json into one payload the static site reads.

Deliberately a build step rather than a runtime API: the site is then a pile of
static files served from an edge with no server, no database, and no way for a
visitor to trigger an adapter call. That is what makes it free to host and
impossible to run up a bill on. The published data is exactly what is committed
in runs/, so anything on the page traces back to a run directory in the repo.

The payload is shaped around the decision, not around the factor list: for each
site and each profile it carries the brief (decision, blockers, sensitivity,
verification queue) plus every measurement with its full provenance. Anything the
page cannot show honestly is left out rather than summarized.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from dcgeo.cli import _load  # noqa: E402
from dcgeo.diligence import briefs  # noqa: E402
from dcgeo.registry import load_factors, load_profiles, load_sources  # noqa: E402

OUT = ROOT / "site" / "data"

# How much of each brief reaches the browser. The tails are long and repetitive;
# these caps keep the payload a single static file without hiding a category.
MAX_BLOCKERS = 14
MAX_SWINGS = 16
MAX_QUEUE = 8


def _trim_brief(b: dict, reason_pool: dict) -> dict:
    """One profile's brief, cut down to what the page renders."""
    swings = b.get("swing_factors", [])
    # Keep the biggest movers plus everything that can flip the verdict, since a
    # flipping factor is the entire point of the section even when its swing is
    # not in the top few.
    flipping = [s for s in swings if s.get("flips_verdict")]
    keep, seen = [], set()
    for s in (swings[:MAX_SWINGS] + flipping):
        if s["factor_id"] in seen:
            continue
        seen.add(s["factor_id"])
        keep.append({
            "factor_id": s["factor_id"], "name": s["name"], "domain": s["domain"],
            "known": s["known"], "tier": s["tier"], "swing": s["swing"],
            "flips": s["flips_verdict"], "worst": s["verdict_if_worst"],
            "best": s["verdict_if_best"], "gate": s["gate_critical"],
        })
    keep.sort(key=lambda s: -s["swing"])

    return {
        "decision": b["decision"],
        "headline": b["headline"],
        "score": b["score"],
        "band": b["band"],
        "confidence": b["confidence"],
        "measured_fraction": b["measured_fraction"],
        "verdict": b["verdict"],
        "can_profit": b["can_answer_profitability"],
        "profit_basis": b["profitability_basis"],
        "domain_coverage": b.get("domain_coverage", {}),
        "blocker_counts": {
            sev: sum(1 for x in b["blockers"] if x["severity"] == sev)
            for sev in ("fatal", "major", "minor")
        },
        "blockers": [
            {
                "kind": x["kind"], "severity": x["severity"], "title": x["title"],
                "why": x["why"], "resolve": x["resolve"], "owner": x["owner"],
                "factor_id": x["factor_id"], "domain": x["domain"],
                "pts": x["points_at_risk"], "weeks": x["typical_weeks"],
            }
            for x in b["blockers"][:MAX_BLOCKERS]
        ],
        "swings": keep,
        "queue": [
            {
                "rank": v["rank"], "factor_id": v["factor_id"], "question": v["question"],
                "owner": v["owner"], "artifact": v["artifact"], "pts": v["points_at_risk"],
                "gate": v["gate_critical"], "weeks": v["typical_weeks"], "note": v["note"],
            }
            for v in b["verification_queue"][:MAX_QUEUE]
        ],
    }


def build() -> dict:
    factors = load_factors()

    # Unmeasured entries share few distinct reasons. Interning them keeps the
    # payload small enough to stay a single static file.
    reasons: list[str] = []
    reason_index: dict[str, int] = {}

    def intern(text: str) -> int:
        if text not in reason_index:
            reason_index[text] = len(reasons)
            reasons.append(text)
        return reason_index[text]

    profiles = load_profiles()
    sites = []

    for run_dir in sorted((ROOT / "runs").glob("run_*")):
        f = run_dir / "analysis.json"
        if not f.exists():
            continue
        d = json.loads(f.read_text())
        site = d["site"]

        # Provenance per factor comes off the scored factors, which already carry
        # source, retrieval date and freshness alongside the value.
        prov: dict[str, dict] = {}
        primary = next(iter(d["profiles"].values()), None)
        for fs in (primary or {}).get("factor_scores", []):
            prov[fs["factor_id"]] = fs

        measurements, unmeasured = [], []
        for m in d["measurements"]:
            spec = factors.get(m["factor_id"])
            if not spec:
                continue
            if m["value"] is None:
                unmeasured.append({
                    "factor_id": m["factor_id"], "name": spec["name"],
                    "domain": spec["domain"],
                    "reason_id": intern((m.get("unknown_reason") or "")[:180]),
                })
                continue
            p = prov.get(m["factor_id"], {})
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
                "retrieved": (m.get("retrieved") or "")[:10],
                "age_days": p.get("age_days"),
                "freshness": p.get("freshness", "undated"),
                "confidence": p.get("evidence_weight"),
                "notes": m.get("notes"),
            })

        # Briefs are derived, not stored — recompute them here so the published
        # page can never show a decision the current code would not reach.
        dil = {k: v.to_dict() for k, v in briefs(_load(run_dir.name)).items()}
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
                    "score": v["score"], "band": v["band"], "confidence": v["confidence"],
                    "measured_fraction": v["measured_fraction"], "verdict": v["verdict"],
                    "capped_by": v.get("capped_by"), "domain_scores": v["domain_scores"],
                }
                for k, v in d["profiles"].items()
            },
            "briefs": {k: _trim_brief(v, reason_index) for k, v in dil.items()},
            "gates": [
                {"gate_id": g["gate_id"], "name": g["name"], "outcome": g["outcome"],
                 "reason": g["reason"], "low_confidence": g.get("low_confidence", False)}
                for g in d["gates"]
            ],
            "measurements": measurements,
            "unmeasured": unmeasured,
            "red_team": d.get("red_team", []),
        })

    # Corpus-wide honesty counters.
    tier_counts: dict[str, int] = {}
    fresh_counts: dict[str, int] = {}
    for s in sites:
        for m in s["measurements"]:
            tier_counts[m["tier"]] = tier_counts.get(m["tier"], 0) + 1
            fresh_counts[m["freshness"]] = fresh_counts.get(m["freshness"], 0) + 1
        tier_counts["unknown"] = tier_counts.get("unknown", 0) + len(s["unmeasured"])

    srcs = load_sources()
    return {
        "reasons": reasons,
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
            "freshness_counts": fresh_counts,
            "verdict_thresholds": profiles["verdict_thresholds"],
            "repo": "https://github.com/not-vibhu/datacenter-geo",
        },
    }


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    payload = build()
    # Minified: this file is read by the browser, not by people. The human-readable
    # source of truth is the per-run analysis.json committed under runs/.
    (OUT / "sites.json").write_text(json.dumps(payload, separators=(",", ":"), default=str))
    n = len(payload["sites"])
    nm = sum(len(s["measurements"]) for s in payload["sites"])
    kb = (OUT / "sites.json").stat().st_size / 1024
    print(f"wrote site/data/sites.json — {n} sites, {nm} measured, "
          f"tiers {payload['meta']['tier_counts']}, {kb:.0f} KB")
