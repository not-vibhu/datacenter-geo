"""dcgeo CLI. The agent layer drives everything through this, never through raw HTTP —
it handles caching, rate limits, retries, and evidence recording."""
from __future__ import annotations

import dataclasses
import json
import re
from datetime import datetime
from pathlib import Path

import click
from rich.console import Console
from rich.table import Table

from . import cache as cachemod
from . import compare as compare_mod
from . import diligence
from . import measure as measure_mod
from . import report as report_mod
from .boundary import load_boundary
from .gates import evaluate_gates, validate_gate_coverage
from .geo import bbox_around, parse_latlon, tile_region
from .models import (
    Analysis,
    Claim,
    FactorScore,
    GateResult,
    Measurement,
    ProfileScore,
    Recommendation,
    Site,
)
from .registry import (
    ROOT,
    load_factors,
    load_gates,
    load_profiles,
    load_sources,
    profile_names,
    resolve_source,
    validate,
)
from .scoring import apply_gates_to_scores, score_profile

console = Console()
RUNS = ROOT / "runs"


def _next_run_id() -> str:
    RUNS.mkdir(exist_ok=True)
    existing = [int(m.group(1)) for p in RUNS.iterdir()
                if (m := re.match(r"run_(\d+)$", p.name))]
    return f"run_{max(existing, default=0) + 1:04d}"


def _save(analysis: Analysis) -> Path:
    d = RUNS / analysis.run_id
    d.mkdir(parents=True, exist_ok=True)
    (d / "analysis.json").write_text(analysis.to_json())
    (d / "report.md").write_text(report_mod.markdown(analysis))
    (d / "site.geojson").write_text(json.dumps(
        {"type": "FeatureCollection", "features": [analysis.site.to_geojson()]}, indent=2))
    return d


def _load(run: str) -> Analysis:
    path = Path(run)
    if not path.exists():
        path = RUNS / run
    if path.is_dir():
        path = path / "analysis.json"
    if not path.exists():
        raise click.ClickException(f"no analysis found at {run}")
    d = json.loads(path.read_text())

    def only_known(cls, raw: dict) -> dict:
        """Drop fields this version of the model no longer has.

        Runs are committed and outlive the code that wrote them, so loading must
        tolerate a schema that has moved on. Unknown keys are dropped rather than
        raising — a run from an older release stays readable, and re-scoring it
        writes it back in the current shape.
        """
        allowed = {f.name for f in dataclasses.fields(cls)}
        return {k: v for k, v in raw.items() if k in allowed}

    site = Site(**{**d["site"], "centroid": tuple(d["site"]["centroid"])})
    a = Analysis(
        run_id=d["run_id"], site=site, created=d["created"], parent_run=d.get("parent_run"),
        assumptions=d.get("assumptions", {}), weight_overrides=d.get("weight_overrides", {}),
        cooling_assumption=d.get("cooling_assumption", "hybrid_adiabatic"),
        red_team=d.get("red_team", []),
    )
    for m in d["measurements"]:
        a.measurements.append(Measurement(**only_known(Measurement, m)))
    for claim in d.get("claims", []):
        a.claims.append(Claim(**only_known(Claim, claim)))

    # Restore derived state so a loaded analysis round-trips losslessly. Without
    # this, anything reading a saved run sees it as unscored.
    for g in d.get("gates", []):
        a.gates.append(GateResult(**only_known(GateResult, g)))
    for name, ps in d.get("profiles", {}).items():
        fs = [FactorScore(**only_known(FactorScore, f))
              for f in ps.pop("factor_scores", [])]
        a.profiles[name] = ProfileScore(
            **{**only_known(ProfileScore, ps), "factor_scores": fs})
    for r in d.get("recommendations", []):
        if isinstance(r.get("timeline_months"), list):
            r["timeline_months"] = tuple(r["timeline_months"])
        a.recommendations.append(Recommendation(**only_known(Recommendation, r)))
    return a


def _kv(pairs: tuple[str, ...]) -> dict:
    out = {}
    for p in pairs:
        if "=" not in p:
            raise click.ClickException(f"expected key=value, got {p!r}")
        k, v = p.split("=", 1)
        try:
            out[k] = json.loads(v)
        except json.JSONDecodeError:
            out[k] = v
    return out


@click.group()
@click.version_option(package_name="dcgeo")
def cli() -> None:
    """AI data center site suitability analysis."""


# ── doctor ───────────────────────────────────────────────────────────────────

@cli.command()
@click.option("--probe/--no-probe", default=False, help="Actually call the live endpoints.")
def doctor(probe: bool) -> None:
    """Validate the registry and report which data sources are reachable."""
    console.print("[bold]Registry[/bold]")
    problems = validate() + validate_gate_coverage()
    if problems:
        for p in problems:
            console.print(f"  [red]x[/red] {p}")
        console.print(f"\n[red]{len(problems)} problem(s)[/red]")
    else:
        f, g, s = len(load_factors()), len(load_gates()), len(load_sources())
        console.print(f"  [green]ok[/green] {f} factors, {g} gates (all implemented), {s} sources")

    t = Table(title="Data sources", show_lines=False)
    for c in ("source", "tier", "auth", "adapter", "status"):
        t.add_column(c)
    for name, spec in sorted(load_sources().items()):
        auth = spec.get("auth", "?")
        key = spec.get("enabled_by")
        if auth == "paid":
            import os
            status = "[green]key present[/green]" if key and os.environ.get(key) else "[dim]stubbed (no key)[/dim]"
        elif auth in ("free_key", "free_registration"):
            status = "[yellow]needs registration[/yellow]"
        else:
            status = "[green]open[/green]"
        t.add_row(name, spec.get("tier", "?"), auth, "-", status)
    console.print(t)

    st = cachemod.stats()
    console.print(f"\ncache: {st['entries']} entries, {st['bytes']/1e6:.1f} MB")
    if probe:
        console.print("\n[bold]Probing live endpoints[/bold] (Ashburn VA test point)")
        for dom in ("climate", "power", "connectivity"):
            ms = measure_mod.measure(39.0437, -77.4875, [dom])
            ok = sum(1 for m in ms if m.is_known)
            console.print(f"  {dom:14} {ok}/{len(ms)} measured")


# ── factors / sources ────────────────────────────────────────────────────────

@cli.command()
@click.option("--domain", help="Filter to one domain.")
@click.option("--profile", default="hyperscale_training", help="Show weights for this profile.")
def factors(domain: str | None, profile: str) -> None:
    """List the factor registry."""
    t = Table(title=f"Factors — weights for {profile}")
    for c in ("id", "name", "unit", "tier", "wt", "gate"):
        t.add_column(c)
    for fid, spec in load_factors().items():
        if domain and spec["domain"] != domain:
            continue
        t.add_row(fid, spec["name"][:44], spec.get("unit", ""), spec.get("best_tier", ""),
                  str(spec["weights"].get(profile, "")), spec.get("gate", "") or "")
    console.print(t)


@cli.command()
def sources() -> None:
    """List the data source registry."""
    t = Table(title="Data sources")
    for c in ("source", "tier", "auth", "coverage", "ttl_days"):
        t.add_column(c)
    for name, spec in sorted(load_sources().items()):
        t.add_row(name, spec.get("tier", ""), spec.get("auth", ""),
                  str(spec.get("coverage", ""))[:40], str(spec.get("ttl_days", "")))
    console.print(t)


# ── measure ──────────────────────────────────────────────────────────────────

@cli.command()
@click.option("--at", "at", required=True, help="lat,lon")
@click.option("--domain", "domains", multiple=True, help="Repeatable. Default: all.")
@click.option("--json", "as_json", is_flag=True)
def measure(at: str, domains: tuple[str, ...], as_json: bool) -> None:
    """Run adapters for a coordinate and print the measurements."""
    lat, lon = parse_latlon(at)
    doms = list(domains) or None
    ms = measure_mod.measure(lat, lon, doms,
                             on_progress=lambda dom, step: console.print(f"[dim]  {dom}/{step}…[/dim]"))
    if as_json:
        click.echo(json.dumps([m.to_dict() for m in ms], indent=2, default=str))
        return
    t = Table(title=f"Measurements at {lat},{lon}")
    for c in ("factor", "value", "unit", "tier", "source"):
        t.add_column(c)
    for m in sorted(ms, key=lambda x: (not x.is_known, x.factor_id)):
        t.add_row(m.factor_id, "—" if m.value is None else str(m.value)[:24],
                  m.unit[:22], m.tier, m.source)
    console.print(t)
    console.print(f"{sum(1 for m in ms if m.is_known)}/{len(ms)} measured")


# ── analyze ──────────────────────────────────────────────────────────────────

@cli.command()
@click.option("--at", "at", help="lat,lon; mutually exclusive with --boundary.")
@click.option("--boundary", type=click.Path(exists=True, dir_okay=False, path_type=Path),
              help="One WGS84 GeoJSON Polygon/MultiPolygon. Preserves the exact boundary.")
@click.option("--name", default=None)
@click.option("--radius", default=10.0, help="AOI radius km.")
@click.option("--profile", "profiles", multiple=True, help="Repeatable. Default: all.")
@click.option("--domain", "domains", multiple=True, help="Limit measurement to these domains.")
@click.option("--cooling", default="hybrid_adiabatic",
              type=click.Choice(["hybrid_adiabatic", "air_cooled", "evaporative", "closed_loop"]))
@click.option("--assume", "assumes", multiple=True, help="key=value, repeatable.")
@click.option("--weight", "weights", multiple=True, help="factor_or_domain=multiplier, repeatable.")
def analyze(at, boundary, name, radius, profiles, domains, cooling, assumes, weights) -> None:
    """Full run: resolve context, measure, gate, score, report."""
    if bool(at) == bool(boundary):
        raise click.UsageError("pass exactly one of --at or --boundary")
    geometry = None
    try:
        if boundary:
            geometry, (lat, lon), boundary_name = load_boundary(boundary)
            name = name or boundary_name
        else:
            lat, lon = parse_latlon(at)
    except (ValueError, OSError, TypeError) as error:
        raise click.ClickException(f"invalid site input: {error}") from error
    if boundary:
        console.print("[dim]Exact boundary retained. Current adapters measure around an interior "
                      "reference point; this is not a polygon-wide hazard or capacity assessment.[/dim]")
    console.print(f"[bold]Resolving[/bold] {lat},{lon}")
    ctx = measure_mod.resolve_context(lat, lon)
    if ctx.get("error"):
        console.print(f"  [yellow]context unresolved: {ctx['error']}[/yellow]")
    else:
        console.print(f"  {ctx.get('admin2') or '?'}, {ctx.get('admin1') or '?'}, "
                      f"{ctx.get('country') or '?'} · market: {ctx.get('market') or '?'}")
        for g in ctx.get("guidance", []):
            console.print(f"  [dim]{g}[/dim]")

    site = Site(
        site_id=f"site_{abs(hash((round(lat,4), round(lon,4)))) % 100000:05d}",
        name=name or ctx.get("display_name") or f"{lat},{lon}",
        centroid=(lat, lon), radius_km=radius,
        geometry=geometry,
        country=ctx.get("country"), admin1=ctx.get("admin1"), admin2=ctx.get("admin2"),
        market=ctx.get("market"), origin="manual",
        notes=("User-supplied GeoJSON boundary; unverified. Centroid field is an interior "
               "reference point for current point-based adapters. Exact geometry is preserved."
               if boundary else None),
    )

    analysis = Analysis(
        run_id=_next_run_id(), site=site, cooling_assumption=cooling,
        assumptions=_kv(assumes), weight_overrides=_kv(weights),
    )

    console.print("[bold]Measuring[/bold]")
    analysis.measurements = measure_mod.measure(
        lat, lon, list(domains) or None,
        on_progress=lambda dom, step: console.print(f"[dim]  {dom}/{step}…[/dim]"))
    known = sum(1 for m in analysis.measurements if m.is_known)
    console.print(f"  {known}/{len(analysis.measurements)} measured")

    _finish(analysis, list(profiles) or profile_names())


def _finish(analysis: Analysis, profs: list[str]) -> None:
    console.print("[bold]Gating and scoring[/bold]")
    seen: dict[str, object] = {}
    for p in profs:
        analysis.profiles[p] = score_profile(analysis, p, analysis.weight_overrides)
        for g in evaluate_gates(analysis, p):
            seen.setdefault(g.gate_id, g)
    analysis.gates = list(seen.values())          # type: ignore[arg-type]
    apply_gates_to_scores(analysis)

    d = _save(analysis)
    t = Table(title=f"{analysis.run_id} — {analysis.site.name[:60]}")
    for c in ("profile", "verdict", "score", "conf", "measured"):
        t.add_column(c)
    for p, ps in analysis.profiles.items():
        t.add_row(p, ps.verdict, "—" if ps.score is None else f"{ps.score:.0f} ± {ps.band:.0f}",
                  f"{ps.confidence:.2f}", f"{ps.measured_fraction:.0%}")
    console.print(t)

    unpub = [n for n, ps in analysis.profiles.items() if not ps.publishable]
    if unpub:
        floor = load_profiles()["aggregation"]["min_measured_fraction"]
        console.print(f"\n[yellow]PROVISIONAL[/yellow] — measured fraction is below the "
                      f"{floor:.0%} floor for {', '.join(unpub)}. These scores are not "
                      f"publishable as findings; dispatch the domain analysts to research the "
                      f"unmeasured factors (see the 'Unmeasured' section of report.md).")

    for g in analysis.gates:
        if g.outcome != "PASS":
            colour = "red" if g.outcome == "FAIL" else "yellow"
            console.print(f"  [{colour}]{g.outcome}[/{colour}] {g.name}: {g.reason[:150]}")

    # The brief is derived, not stored: it reads the gated scores and is recomputed
    # wherever it is shown, so it can never drift from the code that produces it.
    lead = diligence.build_brief(analysis, profs[0])
    console.print(f"\n[bold]{lead.decision}[/bold] — {lead.headline[:220]}")
    if lead.verification_queue:
        console.print("  verify next: "
                      + ", ".join(v.factor_id for v in lead.verification_queue[:3])
                      + f"   [dim](dcgeo brief {analysis.run_id})[/dim]")
    console.print(f"\nwritten to [bold]{d}[/bold]")


# ── score / report / rerun ───────────────────────────────────────────────────

@cli.command()
@click.argument("run")
@click.option("--profile", "profiles", multiple=True)
def score(run: str, profiles: tuple[str, ...]) -> None:
    """Re-run gates and scoring over an existing analysis."""
    a = _load(run)
    _finish(a, list(profiles) or profile_names())


@cli.command()
@click.argument("run")
def report(run: str) -> None:
    """Print the markdown report for a run."""
    click.echo(report_mod.markdown(_load(run)))


@cli.command()
@click.argument("run")
@click.option("--assume", "assumes", multiple=True, help="key=value, repeatable.")
@click.option("--weight", "weights", multiple=True, help="factor_or_domain=multiplier.")
@click.option("--cooling", default=None)
@click.option("--profile", "profiles", multiple=True)
def rerun(run, assumes, weights, cooling, profiles) -> None:
    """Re-score with new assumptions. Creates a child run and diffs against the parent.

    Assumptions are injected as synthetic Tier-D measurements, labeled as assumed
    rather than measured, and propagate through gates and scoring.
    """
    parent = _load(run)
    child = Analysis(
        run_id=_next_run_id(), site=parent.site, parent_run=parent.run_id,
        cooling_assumption=cooling or parent.cooling_assumption,
        assumptions={**parent.assumptions, **_kv(assumes)},
        weight_overrides={**parent.weight_overrides, **_kv(weights)},
        measurements=list(parent.measurements),
    )

    known_factors = set(load_factors())
    for k, v in _kv(assumes).items():
        if k in known_factors:
            child.measurements.append(Measurement(
                factor_id=k, value=v, unit=load_factors()[k].get("unit", ""), tier="D",
                source="user_assumption",
                notes="ASSUMED, NOT MEASURED — supplied via --assume on this run.",
            ))
            console.print(f"  [yellow]assumed[/yellow] {k} = {v} (Tier D)")

    _finish(child, list(profiles) or list(parent.profiles) or profile_names())

    for p, cps in child.profiles.items():
        pps = parent.profiles.get(p)
        if pps and pps.score is not None and cps.score is not None:
            delta = cps.score - pps.score
            console.print(f"  {p}: {pps.score:.0f} -> {cps.score:.0f} ({delta:+.1f}) · "
                          f"{pps.verdict} -> {cps.verdict}")


@cli.command()
@click.argument("runs", nargs=-1, required=True)
@click.option("--profile", default="hyperscale_training")
@click.option("--json", "as_json", is_flag=True)
def compare(runs: tuple[str, ...], profile: str, as_json: bool) -> None:
    """Compare sites by why they win and lose, not by rank alone.

    Refuses to present an ordering when the confidence bands overlap — in that
    case the win/lose reasons are the only honest output.
    """
    c = compare_mod.compare([_load(r) for r in runs], profile)
    if as_json:
        click.echo(json.dumps(c.to_dict(), indent=2, default=str))
        return

    t = Table(title=f"Comparison — {profile}")
    for col in ("run", "site", "decision", "score", "conf", "measured"):
        t.add_column(col)
    for s_ in c.sites:
        t.add_row(s_.run_id, s_.name[:32], s_.decision,
                  "—" if s_.score is None else f"{s_.score:.0f} ± {s_.band:.0f}",
                  f"{s_.confidence:.2f}", f"{s_.measured_fraction:.0%}")
    console.print(t)

    colour = "green" if c.separable else "yellow"
    console.print(f"[{colour}]{'Separable' if c.separable else 'Not separable'}:[/{colour}] "
                  f"{c.separability_note}\n")

    for s_ in c.sites:
        console.print(f"[bold]{s_.name[:60]}[/bold]")
        for e in s_.wins[:4]:
            console.print(f"  [green]+[/green] {e.name[:44]:46} "
                          f"{e.delta:+6.0f} vs field  {e.contribution:+.2f} pts  [dim]{e.site_tier}[/dim]")
        for e in s_.loses[:4]:
            console.print(f"  [red]-[/red] {e.name[:44]:46} "
                          f"{e.delta:+6.0f} vs field  {e.contribution:+.2f} pts  [dim]{e.site_tier}[/dim]")
        for b in s_.unique_blockers[:2]:
            console.print(f"    [dim]only here:[/dim] {b['title'][:76]}")
        console.print("")

    if c.shared_blind_spots:
        console.print(f"[yellow]Shared blind spots[/yellow] — unmeasured for every site, so the "
                      f"comparison assumes them away equally "
                      f"({c.comparable_fraction:.0%} of decision weight is comparable):")
        for b in c.shared_blind_spots[:8]:
            console.print(f"  · {b['name']} [dim]({b['factor_id']}, weight {b['weight']:.0f})[/dim]")


@cli.command()
@click.argument("run")
@click.option("--profile", default="hyperscale_training")
@click.option("--json", "as_json", is_flag=True)
def brief(run: str, profile: str, as_json: bool) -> None:
    """The decision brief: can this site support a profitable data center, and what next?"""
    a = _load(run)
    b = diligence.build_brief(a, profile)
    if as_json:
        click.echo(json.dumps(b.to_dict(), indent=2, default=str))
        return

    colour = {"NO-GO": "red", "NOT PROVEN": "yellow",
              "PROCEED WITH CONDITIONS": "cyan", "PROCEED": "green"}.get(b.decision, "white")
    console.print(f"\n[bold {colour}]{b.decision}[/bold {colour}] — {a.site.name}  "
                  f"[dim]{profile}[/dim]")
    console.print(f"\n{b.headline}\n")
    console.print(f"score {'—' if b.score is None else f'{b.score:.0f} ± {b.band:.0f}'} · "
                  f"confidence {b.confidence:.2f} · "
                  f"{b.measured_fraction:.0%} of decision weight measured")

    dark = [d for d, c_ in b.domain_coverage.items() if not c_["in_score"]]
    if dark:
        console.print(f"[yellow]Excluded from the score entirely:[/yellow] {', '.join(dark)}")

    console.print("\n[bold]Decision blockers[/bold]")
    for bl in b.blockers[:10]:
        c_ = {"fatal": "red", "major": "yellow", "minor": "dim"}[bl.severity]
        pts = f"{bl.points_at_risk:.0f} pts" if bl.points_at_risk else "—"
        console.print(f"  [{c_}]{bl.severity.upper():5}[/{c_}] {bl.title[:78]}")
        console.print(f"        [dim]{pts} at risk · ask: {bl.owner}[/dim]")
    if len(b.blockers) > 10:
        console.print(f"  [dim]… {len(b.blockers) - 10} more[/dim]")

    console.print("\n[bold]Could flip the verdict[/bold]")
    flip = [s_ for s_ in b.swing_factors if s_.flips_verdict][:8]
    for s_ in flip:
        state = "unmeasured" if not s_.known else f"measured, tier {s_.tier}"
        console.print(f"  {s_.name[:44]:46} ±{s_.swing:5.1f} pts  "
                      f"[dim]{s_.verdict_if_worst} → {s_.verdict_if_best} · {state}[/dim]")
    if not flip:
        console.print("  [dim]No single factor can move the verdict across a threshold.[/dim]")

    console.print("\n[bold]Verify next[/bold]")
    for v in b.verification_queue:
        mark = "[red]gate[/red]" if v.gate_critical else "    "
        wk = f"{v.typical_weeks[0]}-{v.typical_weeks[1]}w" if v.typical_weeks else "—"
        console.print(f"  {v.rank}. {mark} {v.factor_id:32} {v.points_at_risk:5.1f} pts  {wk:>7}")
        console.print(f"        [dim]{v.owner} → {v.artifact[:96]}[/dim]")
    console.print("")


# ── scan ─────────────────────────────────────────────────────────────────────

@cli.command()
@click.option("--bbox", help="south,west,north,east")
@click.option("--at", help="lat,lon centre (used with --radius)")
@click.option("--radius", default=50.0)
@click.option("--step", default=10.0, help="Tile size km.")
@click.option("--max-tiles", default=60)
@click.option("--min-kv", default=230.0)
def scan(bbox, at, radius, step, max_tiles, min_kv) -> None:
    """Coarse prospecting pass: tile a region and cheaply rank tiles.

    Arithmetic, not LLM work. Scores tiles on the factors that are globally available
    and kill sites most often, so candidates die early and cheaply.
    """
    if bbox:
        s, w, n, e = [float(x) for x in bbox.split(",")]
    elif at:
        lat, lon = parse_latlon(at)
        s, w, n, e = bbox_around(lat, lon, radius)
    else:
        raise click.ClickException("pass --bbox or --at")

    tiles = list(tile_region(s, w, n, e, step))
    if len(tiles) > max_tiles:
        console.print(f"[yellow]{len(tiles)} tiles exceeds --max-tiles {max_tiles}; "
                      f"sampling evenly.[/yellow]")
        stride = len(tiles) // max_tiles + 1
        tiles = tiles[::stride][:max_tiles]

    console.print(f"[bold]Coarse pass[/bold] over {len(tiles)} tiles ({step} km)")
    from .adapters import overpass, terrain
    from .scoring import normalize
    specs = load_factors()

    results = []
    for i, (tlat, tlon) in enumerate(tiles, 1):
        console.print(f"[dim]  tile {i}/{len(tiles)} {tlat},{tlon}[/dim]")
        parts, notes = {}, []
        for ms in (overpass.nearest_transmission(tlat, tlon, 40.0, min_kv),
                   terrain.slope_stats(tlat, tlon, 2.0)):
            for m in ms:
                if m.is_known:
                    parts[m.factor_id] = normalize(specs[m.factor_id], m.value)
                    notes.append(f"{m.factor_id}={m.value}{m.unit}")
        if parts:
            results.append({
                "lat": tlat, "lon": tlon,
                "coarse_score": round(sum(parts.values()) / len(parts), 1),
                "components": parts, "notes": "; ".join(notes),
            })

    results.sort(key=lambda r: -r["coarse_score"])
    t = Table(title="Coarse candidates")
    for c in ("rank", "lat,lon", "coarse", "detail"):
        t.add_column(c)
    for i, r in enumerate(results[:20], 1):
        t.add_row(str(i), f"{r['lat']:.4f},{r['lon']:.4f}", f"{r['coarse_score']:.0f}", r["notes"][:70])
    console.print(t)

    out = RUNS / f"scan_{datetime.now():%Y%m%d_%H%M%S}.json"
    RUNS.mkdir(exist_ok=True)
    out.write_text(json.dumps({"bbox": [s, w, n, e], "step_km": step, "results": results}, indent=2))
    console.print(f"\n{len(results)} tiles scored, written to [bold]{out}[/bold]")
    console.print("[dim]Coarse scores rank tiles for further work. They are NOT site scores — "
                  "promote the top candidates to `dcgeo analyze`.[/dim]")


@cli.command("add-measurement")
@click.argument("run")
@click.option("--factor", required=True, help="factor_id from the registry")
@click.option("--value", required=True, help="JSON scalar, or a category string")
@click.option("--tier", required=True, type=click.Choice(["A", "B", "C", "D"]))
@click.option("--source", required=True, help="source id from config/sources.yaml")
@click.option("--url", "source_url", default=None, help="Citation URL. Required for tier C.")
@click.option("--notes", default=None)
def add_measurement(run, factor, value, tier, source, source_url, notes) -> None:
    """Append a researched measurement to a run's evidence ledger.

    This is how domain analysts contribute Tier B/C/D findings that no adapter can
    produce. Every value must carry a source; Tier C additionally requires a URL.
    """
    specs = load_factors()
    if factor not in specs:
        raise click.ClickException(f"unknown factor '{factor}'. Run `dcgeo factors` to list.")
    spec = specs[factor]

    if resolve_source(source) is None:
        raise click.ClickException(
            f"unregistered source '{source}'. Add it to config/sources.yaml or use an "
            f"existing one — an uncited measurement is not admissible.")
    if tier == "C" and not source_url:
        raise click.ClickException("Tier C requires --url. A synthesized claim without a "
                                   "citation cannot enter the ledger.")

    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        parsed = value

    if spec.get("direction") == "categorical":
        cats = spec.get("categories", {})
        if parsed not in cats:
            raise click.ClickException(
                f"'{parsed}' is not a valid category for {factor}. Valid: {list(cats)}")
    elif not isinstance(parsed, (int, float)):
        raise click.ClickException(
            f"{factor} is numeric ({spec.get('unit')}); got {parsed!r}")

    a = _load(run)
    a.measurements.append(Measurement(
        factor_id=factor, value=parsed, unit=spec.get("unit", ""), tier=tier,
        source=source, source_url=source_url, notes=notes,
        geometry_ref=f"site:{a.site.site_id}",
    ))
    _save(a)
    console.print(f"[green]recorded[/green] {factor} = {parsed} (tier {tier}, {source})")
    console.print(f"[dim]{sum(1 for m in a.measurements if m.is_known)}/"
                  f"{len(a.measurements)} factors now measured. Re-run `dcgeo score {run}`.[/dim]")


@cli.command("red-team")
@click.argument("run")
@click.option("--finding", "findings", multiple=True, required=True)
def red_team(run: str, findings: tuple[str, ...]) -> None:
    """Attach adversarial findings to a run."""
    a = _load(run)
    a.red_team.extend(findings)
    _save(a)
    console.print(f"[green]recorded[/green] {len(findings)} red-team finding(s)")


@cli.command()
def docs() -> None:
    """Regenerate docs/ from the factor, source, and gate registries."""
    from .docs_gen import generate
    for p in generate():
        console.print(f"  wrote {p.relative_to(ROOT)}")


@cli.command("validate-set")
@click.option("--country", default=None, help="Filter: US, CN, IN")
@click.option("--profile", default=None, help="Override each case's stated profile")
def validate_set(country: str | None, profile: str | None) -> None:
    """Backtest scored runs against data/reference/known_datacenters.yaml.

    Matches existing runs to reference cases by proximity, then reports agreement
    AND discrimination. Discrimination is the metric that matters: a model that
    scores everything 70-80 has high agreement on positives and is useless.
    """
    import yaml

    from .geo import haversine_km

    ref_path = ROOT / "data" / "reference" / "known_datacenters.yaml"
    cases = yaml.safe_load(ref_path.read_text())["cases"]
    if country:
        cases = [c for c in cases if c["country"] == country.upper()]

    runs = []
    for d in sorted(RUNS.glob("run_*")):
        try:
            runs.append(_load(d.name))
        except Exception:
            continue

    t = Table(title="Validation against known outcomes")
    for c in ("case", "class", "expected", "predicted", "conf", "agree"):
        t.add_column(c)

    positives, negatives, agreed, evaluated = [], [], 0, 0
    for case in cases:
        clat, clon = case["coord"]
        match = min(
            (r for r in runs if haversine_km(r.site.centroid, (clat, clon)) < 25),
            key=lambda r: haversine_km(r.site.centroid, (clat, clon)), default=None)
        if match is None:
            t.add_row(case["id"], case["class"], case["expected_verdict"],
                      "[dim]not analyzed[/dim]", "—", "—")
            continue

        prof = profile or case.get("profile", "hyperscale_training")
        ps = match.profiles.get(prof)
        if ps is None or ps.score is None:
            t.add_row(case["id"], case["class"], case["expected_verdict"],
                      "[dim]unscored[/dim]", "—", "—")
            continue

        evaluated += 1
        good = {"strong-candidate", "viable"}
        bad = {"conditional", "weak", "poor", "NO-GO", "NO-GO (unverified)"}
        if case["expected_verdict"] == "viable_or_better":
            ok = ps.verdict in good
            positives.append(ps.score)
        else:
            ok = ps.verdict in bad
            negatives.append(ps.score)
        agreed += ok

        t.add_row(case["id"], case["class"], case["expected_verdict"],
                  f"{ps.verdict} ({ps.score:.0f}±{ps.band:.0f})", f"{ps.confidence:.2f}",
                  "[green]yes[/green]" if ok else "[red]no[/red]")
    console.print(t)

    if not evaluated:
        console.print("[yellow]No reference cases have been analyzed yet. "
                      "Run `dcgeo analyze` at the case coordinates first.[/yellow]")
        return

    console.print(f"\nAgreement: {agreed}/{evaluated}")
    if positives and negatives:
        pm, nm = sum(positives)/len(positives), sum(negatives)/len(negatives)
        sep = pm - nm
        console.print(f"Discrimination: positives mean {pm:.1f}, negatives mean {nm:.1f}, "
                      f"separation {sep:+.1f}")
        if sep < 8:
            console.print("[red]Model is NOT discriminating.[/red] Built and rejected sites "
                          "score alike. Agreement rate is misleading — check whether the "
                          "community, regulatory and land factors were actually measured, "
                          "since those are what separate these cases.")
        else:
            console.print("[green]Model separates built from rejected sites.[/green]")
    else:
        console.print("[yellow]Need both positive and negative controls scored to measure "
                      "discrimination. Negative controls are the ones that matter.[/yellow]")


@cli.command("cache")
@click.option("--clear", is_flag=True)
@click.option("--older-than", type=float, default=None, help="Days.")
def cache_cmd(clear: bool, older_than: float | None) -> None:
    """Inspect or clear the measurement cache."""
    if clear:
        console.print(f"cleared {cachemod.clear(older_than)} entries")
    st = cachemod.stats()
    console.print(f"cache: {st['entries']} entries, {st['bytes']/1e6:.2f} MB")


if __name__ == "__main__":
    cli()
