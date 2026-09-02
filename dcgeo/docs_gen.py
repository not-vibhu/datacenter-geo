"""Generate docs from the registry so they cannot drift out of sync with the specs.

Run: uv run dcgeo docs
"""
from __future__ import annotations

from pathlib import Path

from .registry import ROOT, load_factors, load_gates, load_profiles, load_source_aliases, load_sources

DOCS = ROOT / "docs"


def _factor_page(domain: str, specs: list[dict]) -> str:
    L = [f"# {domain.title()} factors", "",
         f"*Generated from `factors/{domain}.yaml` — edit the YAML, not this file.*", ""]
    profiles = list(load_profiles()["profiles"])
    L.append("| Factor | Unit | Best tier | " + " | ".join(p.split("_")[0] for p in profiles) + " | Gate |")
    L.append("|---|---|---|" + "---|" * len(profiles) + "---|")
    for s in specs:
        w = " | ".join(str(s["weights"].get(p, "")) for p in profiles)
        L.append(f"| `{s['id']}` {s['name']} | {s.get('unit','')} | {s.get('best_tier','')} "
                 f"| {w} | {s.get('gate','') or ''} |")
    L.append("")
    for s in specs:
        L.append(f"## {s['name']}")
        L.append("")
        L.append(f"`{s['id']}` · **{s.get('unit','')}** · {s.get('direction','')} · "
                 f"best obtainable tier **{s.get('best_tier','')}**")
        L.append("")
        L.append(f"> {s.get('question','')}")
        L.append("")
        if "scale" in s:
            pts = s["scale"]["points"]
            L.append("**Normalization curve** (value → score):")
            L.append("")
            L.append("| " + " | ".join(str(p[0]) for p in pts) + " |")
            L.append("|" + "---|" * len(pts))
            L.append("| " + " | ".join(str(p[1]) for p in pts) + " |")
            L.append("")
        if "categories" in s:
            L.append("**Categories:**")
            L.append("")
            for k, v in s["categories"].items():
                L.append(f"- `{k}` → {v if v is not None else '—'}")
            L.append("")
        if "composite_of" in s:
            L.append("**Composite of:**")
            L.append("")
            for k, v in s["composite_of"].items():
                L.append(f"- `{k}` (weight {v.get('weight')}, better={v.get('better')})")
            L.append("")
        srcs = s.get("sources", [])
        if srcs:
            L.append("**Sources:** " + ", ".join(f"`{x}`" for x in srcs))
            L.append("")
        if s.get("notes"):
            L.append(s["notes"].strip())
            L.append("")
    return "\n".join(L)


def generate() -> list[Path]:
    written: list[Path] = []
    (DOCS / "factors").mkdir(parents=True, exist_ok=True)

    by_domain: dict[str, list[dict]] = {}
    for spec in load_factors().values():
        by_domain.setdefault(spec["domain"], []).append(spec)

    for domain, specs in by_domain.items():
        p = DOCS / "factors" / f"{domain}.md"
        p.write_text(_factor_page(domain, specs))
        written.append(p)

    # Source catalog
    srcs = load_sources()
    aliases = load_source_aliases()
    rev: dict[str, list[str]] = {}
    for a, t in aliases.items():
        rev.setdefault(t, []).append(a)

    L = ["# Data source catalog", "",
         "*Generated from `config/sources.yaml`.*", "",
         f"{len(srcs)} sources, {len(aliases)} dataset aliases. ",
         f"{sum(1 for s in srcs.values() if s.get('auth') == 'none')} require no key at all.", "",
         "| Source | Tier | Auth | Coverage | TTL (d) |", "|---|---|---|---|---|"]
    for name, s in sorted(srcs.items()):
        L.append(f"| `{name}` | {s.get('tier','')} | {s.get('auth','')} | "
                 f"{str(s.get('coverage',''))[:52]} | {s.get('ttl_days','')} |")
    L.append("")
    L.append("## Detail")
    L.append("")
    for name, s in sorted(srcs.items()):
        L.append(f"### `{name}` — {s.get('name', name)}")
        L.append("")
        L.append(f"Tier **{s.get('tier','')}** · auth `{s.get('auth','')}` · "
                 f"TTL {s.get('ttl_days','')} d · license: {s.get('license','unstated')}")
        L.append("")
        if s.get("base_url"):
            L.append(f"`{s['base_url']}`")
            L.append("")
        if s.get("serves"):
            L.append("**Serves:** " + ", ".join(f"`{x}`" for x in s["serves"]))
            L.append("")
        if rev.get(name):
            L.append("**Aliases:** " + ", ".join(f"`{a}`" for a in sorted(rev[name])))
            L.append("")
        if s.get("notes"):
            L.append(s["notes"].strip())
            L.append("")
    p = DOCS / "data-sources.md"
    p.write_text("\n".join(L))
    written.append(p)

    # Gate catalog
    L = ["# Gates", "", "*Generated from `config/gates.yaml`.*", "",
         "Gates are evaluated before scoring and short-circuit. A `FAIL` sets the verdict",
         "to NO-GO regardless of score; a `CONDITIONAL` caps the score and becomes a",
         "mandatory recommendation. A gate that fails on Tier C/D evidence is reported as",
         "`NO-GO (unverified)` and flagged for human verification — we do not kill sites on",
         "the strength of a news article.", ""]
    for g in load_gates():
        L.append(f"## `{g['id']}` — {g['name']}")
        L.append("")
        L.append(f"Severity **{g.get('severity','')}** · "
                 f"applies to: {', '.join(g.get('applies_to_profiles', []))}")
        if g.get("capped_score_if_conditional"):
            L.append(f" · caps at **{g['capped_score_if_conditional']}** when CONDITIONAL")
        L.append("")
        L.append("```")
        L.append(g.get("logic", "").strip())
        L.append("```")
        L.append("")
        if g.get("rationale"):
            L.append(g["rationale"].strip())
            L.append("")
        if g.get("remediation_hint"):
            L.append(f"**Remediation:** {g['remediation_hint']}")
            L.append("")
    p = DOCS / "gates.md"
    p.write_text("\n".join(L))
    written.append(p)
    return written
