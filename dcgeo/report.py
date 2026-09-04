"""Report rendering. Investment committee first, dashboard second.

The document answers one question in its first paragraph — can this site support
a profitable data center, and what must be verified next — and spends the rest of
its length showing its work. The score appears after the reasoning, never before
it, because a number at the top of a page gets quoted without the page.
"""
from __future__ import annotations

from .diligence import build_brief
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
        L.append("**Assumptions applied:** " +
                 ", ".join(f"`{k}={v}`" for k, v in a.assumptions.items()))
    L.append("")

    # ── the answer, before anything else ─────────────────────────────────────
    primary_profile = next(iter(a.profiles), None)
    brief = build_brief(a, primary_profile) if primary_profile else None

    if brief:
        L.append("## Decision")
        L.append("")
        L.append(f"### {brief.decision}")
        L.append("")
        L.append(brief.headline)
        L.append("")
        L.append(f"*For profile `{brief.profile}`. "
                 f"Score {'—' if brief.score is None else f'{brief.score:.0f} ± {brief.band:.0f}'}, "
                 f"confidence {brief.confidence:.2f}, "
                 f"{brief.measured_fraction:.0%} of decision weight measured.*")
        L.append("")

        dark = [d for d, c in brief.domain_coverage.items() if not c["in_score"]]
        if dark:
            L.append(f"> **{len(dark)} domain(s) contributed nothing to this score** — "
                     f"{', '.join(dark)}. The headline is a weighted mean over the domains "
                     f"that had data, not over the whole model.")
            L.append("")

        # ── blockers ─────────────────────────────────────────────────────────
        if brief.blockers:
            L.append("## Decision blockers")
            L.append("")
            L.append("What stands between this evidence and a decision. Ranked by severity, "
                     "then by the score points each one puts at risk.")
            L.append("")
            L.append("| | Blocker | At risk | Who can close it |")
            L.append("|---|---|---|---|")
            for b in brief.blockers[:14]:
                pts = f"{b.points_at_risk:.0f} pts" if b.points_at_risk else "—"
                L.append(f"| **{b.severity.upper()}** | {b.title} | {pts} | {b.owner} |")
            if len(brief.blockers) > 14:
                L.append(f"| | *… {len(brief.blockers) - 14} more* | | |")
            L.append("")
            for b in brief.blockers[:6]:
                L.append(f"**{b.title}**")
                L.append("")
                L.append(f"{b.why}")
                L.append("")
                L.append(f"- *Closes with:* {b.resolve}")
                L.append(f"- *Ask:* {b.owner}"
                         + (f" · typically {b.typical_weeks[0]}–{b.typical_weeks[1]} weeks"
                            if b.typical_weeks else ""))
                L.append("")

        # ── sensitivity ──────────────────────────────────────────────────────
        flip = [s for s in brief.swing_factors if s.flips_verdict]
        L.append("## What could flip the verdict")
        L.append("")
        if flip:
            L.append(f"{len(flip)} factor(s) can move the score across a verdict threshold "
                     f"on their own. Each row is the real scorer re-run with that one factor "
                     f"resolved at its best and worst plausible value, everything else held.")
            L.append("")
            L.append("| Factor | State | Swing | Worst case | Best case |")
            L.append("|---|---|---|---|---|")
            for sw in flip[:12]:
                state = "unmeasured" if not sw.known else f"tier {sw.tier}"
                L.append(f"| {sw.name} <br>`{sw.factor_id}` | {state} | "
                         f"±{sw.swing:.0f} | {sw.verdict_if_worst} | {sw.verdict_if_best} |")
            L.append("")
        else:
            L.append("No single factor can move the score across a verdict threshold. "
                     "The verdict is robust to any one measurement being wrong.")
            L.append("")

        # ── verification queue ───────────────────────────────────────────────
        if brief.verification_queue:
            L.append("## Verify next")
            L.append("")
            L.append("Ordered by how much of the decision each answer settles. Gate-critical "
                     "items come first regardless of points, because a knockout check that "
                     "cannot be evaluated can make everything below it irrelevant.")
            L.append("")
            for v in brief.verification_queue:
                mark = " **[gate]**" if v.gate_critical else ""
                wk = (f" · {v.typical_weeks[0]}–{v.typical_weeks[1]} weeks"
                      if v.typical_weeks else "")
                L.append(f"{v.rank}.{mark} **{v.question}**")
                L.append(f"   - `{v.factor_id}` · {v.points_at_risk:.0f} points at risk{wk}")
                L.append(f"   - **Ask:** {v.owner}")
                L.append(f"   - **Get:** {v.artifact}")
                if v.note:
                    L.append(f"   - *{v.note}*")
            L.append("")

    # ── verdict table ────────────────────────────────────────────────────────
    L.append("## Scores by profile")
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
        L.append("| Factor | Value | Unit | Score | Weight | Evidence | Source | Retrieved |")
        L.append("|---|---|---|---|---|---|---|---|")
        for fs in primary.factor_scores:
            name = factors.get(fs.factor_id, {}).get("name", fs.factor_id)
            val = "—" if fs.raw_value is None else str(fs.raw_value)
            norm = "—" if fs.normalized is None else f"{fs.normalized:.0f}"
            src = f"`{fs.source}`" if fs.source and fs.normalized is not None else "—"
            when = "—"
            if fs.retrieved:
                age = f" ({fs.age_days:.0f}d)" if fs.age_days is not None else ""
                flag = "" if fs.freshness == "fresh" else f" **{fs.freshness}**"
                when = f"{fs.retrieved[:10]}{age}{flag}"
            L.append(f"| {name} <br>`{fs.factor_id}` | {val} | {fs.unit} | {norm} | "
                     f"{fs.weight:.0f} | {TIER_LABEL[fs.tier]} | {src} | {when} |")
        L.append("")
        L.append("*Every row carries where the number came from and when it was retrieved. "
                 "A value marked `aging` or `stale` is past its source's declared refresh "
                 "window and is discounted in the confidence figure accordingly.*")
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
