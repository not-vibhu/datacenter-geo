"""Report rendering. Investment committee first, dashboard second.

Lead with the verdict and the deal-killers. Score comes after the reasoning.
"""
from __future__ import annotations

from .models import Analysis
from .registry import load_factors

TIER_LABEL = {
    "A": "A (machine API)", "B": "B (bulk/structured)", "C": "C (researched)",
    "D": "D (modeled)", "unknown": "— (unmeasured)",
}


def markdown(analysis: Analysis) -> str:
    a = analysis
    s = a.site
    factors = load_factors()
    L: list[str] = []

    L.append(f"# Site analysis — {s.name}")
    L.append("")
    loc = ", ".join(x for x in [s.admin2, s.admin1, s.country] if x) or "unresolved"
    L.append(f"**{loc}** · `{s.centroid[0]:.4f}, {s.centroid[1]:.4f}` · "
             f"AOI radius {s.radius_km:.0f} km")
    if s.market:
        L.append(f"**Market:** {s.market}")
    L.append(f"**Run:** `{a.run_id}` · {a.created}"
             + (f" · child of `{a.parent_run}`" if a.parent_run else ""))
    L.append(f"**Cooling assumption:** {a.cooling_assumption}")
    if a.assumptions:
        L.append(f"**Assumptions applied:** " +
                 ", ".join(f"`{k}={v}`" for k, v in a.assumptions.items()))
    L.append("")

    # ── verdict first ────────────────────────────────────────────────────────
    L.append("## Verdict")
    L.append("")
    L.append("| Profile | Verdict | Score | Confidence | Measured |")
    L.append("|---|---|---|---|---|")
    for name, ps in a.profiles.items():
        score = "—" if ps.score is None else f"{ps.score:.0f} ± {ps.band:.0f}"
        cap = f" *(capped by {ps.capped_by})*" if ps.capped_by else ""
        L.append(f"| `{name}` | **{ps.verdict}**{cap} | {score} | {ps.confidence:.2f} | "
                 f"{ps.measured_fraction:.0%} |")
    L.append("")

    unpublishable = [n for n, p in a.profiles.items() if not p.publishable]
    if unpublishable:
        L.append(f"> **Insufficient evidence to publish a headline score** for "
                 f"{', '.join('`'+u+'`' for u in unpublishable)} — measured fraction is below the "
                 f"configured minimum. Treat the numbers above as provisional.")
        L.append("")

    # ── gates ────────────────────────────────────────────────────────────────
    L.append("## Gates")
    L.append("")
    fails = [g for g in a.gates if g.outcome == "FAIL"]
    conds = [g for g in a.gates if g.outcome == "CONDITIONAL"]
    passes = [g for g in a.gates if g.outcome == "PASS"]

    if fails:
        L.append("### Deal-killers")
        L.append("")
        for g in fails:
            flag = " ⚠︎ *decided on low-confidence evidence — verify before acting*" if g.low_confidence else ""
            L.append(f"- **{g.name}** — {g.reason}{flag}")
            if g.remediation_hint:
                L.append(f"  - *Remediation:* {g.remediation_hint}")
        L.append("")
    if conds:
        L.append("### Conditions")
        L.append("")
        for g in conds:
            cap = f" (caps score at {g.capped_score:.0f})" if g.capped_score else ""
            L.append(f"- **{g.name}**{cap} — {g.reason}")
            if g.remediation_hint:
                L.append(f"  - *Remediation:* {g.remediation_hint}")
        L.append("")
    if passes:
        L.append("### Cleared")
        L.append("")
        for g in passes:
            L.append(f"- {g.name} — {g.reason}")
        L.append("")

    # ── red team ─────────────────────────────────────────────────────────────
    if a.red_team:
        L.append("## Red team")
        L.append("")
        L.append("*Findings from the adversarial pass, whose only job is to kill the site.*")
        L.append("")
        for f in a.red_team:
            L.append(f"- {f}")
        L.append("")

    # ── domains ──────────────────────────────────────────────────────────────
    primary = next(iter(a.profiles.values()), None)
    if primary:
        L.append(f"## Domain scores — `{primary.profile}`")
        L.append("")
        L.append("| Domain | Score |")
        L.append("|---|---|")
        for d, sc in sorted(primary.domain_scores.items(),
                            key=lambda kv: (kv[1] is None, kv[1] or 0)):
            L.append(f"| {d} | {'—' if sc is None else f'{sc:.0f}'} |")
        L.append("")

        L.append("## Evidence ledger")
        L.append("")
        L.append("Every scored factor, its measured value, and the tier of evidence behind it. "
                 "A high score on Tier C/D evidence is a hypothesis, not a finding.")
        L.append("")
        L.append("| Factor | Value | Unit | Score | Weight | Evidence |")
        L.append("|---|---|---|---|---|---|")
        for fs in primary.factor_scores:
            name = factors.get(fs.factor_id, {}).get("name", fs.factor_id)
            val = "—" if fs.raw_value is None else str(fs.raw_value)
            norm = "—" if fs.normalized is None else f"{fs.normalized:.0f}"
            L.append(f"| {name} <br>`{fs.factor_id}` | {val} | {fs.unit} | {norm} | "
                     f"{fs.weight:.0f} | {TIER_LABEL[fs.tier]} |")
        L.append("")

    # ── unknowns ─────────────────────────────────────────────────────────────
    unknowns = [m for m in a.measurements if not m.is_known]
    if unknowns:
        L.append(f"## Unmeasured ({len(unknowns)})")
        L.append("")
        L.append("These lowered the confidence score. Each is a specific, actionable research task.")
        L.append("")
        for m in sorted(unknowns, key=lambda x: x.factor_id):
            nm = factors.get(m.factor_id, {}).get("name", m.factor_id)
            L.append(f"- **{nm}** (`{m.factor_id}`) — {m.unknown_reason}")
        L.append("")

    # ── recommendations ──────────────────────────────────────────────────────
    if a.recommendations:
        L.append("## Recommendations")
        L.append("")
        L.append("Ranked by leverage — score points gained per $10M spent.")
        L.append("")
        L.append("| Intervention | Gap | Cost (USD) | Timeline | Gain | Leverage | Actor |")
        L.append("|---|---|---|---|---|---|---|")
        ranked = sorted(a.recommendations, key=lambda r: -(r.leverage or 0))
        for r in ranked:
            if r.cost_low_usd is None and r.cost_high_usd is None:
                cost = "not costed"
            else:
                cost = f"${(r.cost_low_usd or 0)/1e6:.1f}–{(r.cost_high_usd or 0)/1e6:.1f}M"
            tl = f"{r.timeline_months[0]}–{r.timeline_months[1]} mo" if r.timeline_months else "—"
            gain = f"+{r.score_gain:.0f}" if r.score_gain else "—"
            lev = f"{r.leverage:.2f}" if r.leverage else "—"
            L.append(f"| {r.intervention} | {r.gap} | {cost} | {tl} | {gain} | {lev} | {r.actor} |")
        L.append("")
        L.append("*Costs are ranges with a stated basis. A point estimate for a transmission build "
                 "is a fiction.*")
        L.append("")

    # ── provenance ───────────────────────────────────────────────────────────
    L.append("## Provenance")
    L.append("")
    tiers: dict[str, int] = {}
    for m in a.measurements:
        tiers[m.tier] = tiers.get(m.tier, 0) + 1
    L.append("| Tier | Measurements |")
    L.append("|---|---|")
    for t in ("A", "B", "C", "D", "unknown"):
        if t in tiers:
            L.append(f"| {TIER_LABEL[t]} | {tiers[t]} |")
    L.append("")
    srcs = sorted({m.source for m in a.measurements if m.is_known})
    L.append(f"**Sources used:** {', '.join(f'`{s}`' for s in srcs) or 'none'}")
    L.append("")
    L.append("---")
    L.append("")
    L.append("*Generated by [datacenter-geo](https://github.com/datacenter-geo/datacenter-geo). "
             "This is a screening tool. It tells you which sites deserve due diligence and what to "
             "ask when you get there. It does not replace due diligence.*")
    return "\n".join(L)
