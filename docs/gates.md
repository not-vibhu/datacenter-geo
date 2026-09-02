# Gates

*Generated from `config/gates.yaml`.*

Gates are evaluated before scoring and short-circuit. A `FAIL` sets the verdict
to NO-GO regardless of score; a `CONDITIONAL` caps the score and becomes a
mandatory recommendation. A gate that fails on Tier C/D evidence is reported as
`NO-GO (unverified)` and flagged for human verification — we do not kill sites on
the strength of a news article.

## `gate.power_path_exists` — Credible power path to target load

Severity **fatal** · applies to: hyperscale_training, inference_edge, retrofit_colo
 · caps at **68** when CONDITIONAL

```
FAIL if (pwr.interconnect_queue_time > (target_energization_year - current_year))
        AND pwr.onsite_generation_potential < 45
CONDITIONAL if pwr.substation_headroom is unknown
        OR pwr.substation_headroom < target_load_mva * 1.15
else PASS
```

A site that cannot be energized by the target year is not a site, it is a land bank. The on-site generation escape hatch reflects the current reality that behind-the-meter gas can be deployed far faster than a grid interconnection, and that many 2025-2026 US projects are being built on exactly that basis.

**Remediation:** Evaluate behind-the-meter generation, or shift target year, or reduce target load.

## `gate.water_viable` — Water viability for the assumed cooling architecture

Severity **conditional** · applies to: hyperscale_training, retrofit_colo
 · caps at **74** when CONDITIONAL

```
PASS if cooling_assumption == "air_cooled"
FAIL if wtr.withdrawal_permitting == "unavailable"
CONDITIONAL if wtr.basin_stress > 0.8 AND cooling_assumption uses evaporative
CONDITIONAL if wtr.supply_availability < required_m3_per_day
else PASS
```

Water is almost never an absolute barrier — air-cooled designs work in deserts — but it is a design constraint with a power penalty and a political cost. The gate forces the cooling assumption to be made explicit rather than assumed away.

**Remediation:** Switch to air-cooled or closed-loop (costs 10-30% more power), or secure reclaimed water.

## `gate.flood_exclusion` — Flood exclusion

Severity **fatal** · applies to: hyperscale_training, inference_edge, retrofit_colo
 · caps at **80** when CONDITIONAL

```
FAIL if clm.flood_riverine return_period <= 100
FAIL if clm.flood_coastal freeboard_2050 < 0
CONDITIONAL if clm.flood_riverine return_period <= 500
else PASS
```

This is a financing and insurance constraint more than an engineering one. Sites can be elevated; lenders and insurers apply the exclusion categorically anyway, so treating it as engineering-solvable misprices the risk.

**Remediation:** Site the pad outside the mapped zone, or commission a local flood study — global datasets are coarse.

## `gate.land_sufficient` — Sufficient contiguous developable land

Severity **fatal** · applies to: hyperscale_training, inference_edge, retrofit_colo
 · caps at **78** when CONDITIONAL

```
FAIL if lnd.contiguous_area < profile.land_requirement_ha.min
CONDITIONAL if lnd.contiguous_area < profile.land_requirement_ha.typical
else PASS
```

Computed developable area is an upper bound on acquirable area. Failing this gate on the computed figure means the site cannot work even under the most optimistic assembly assumption.

**Remediation:** Expand the AOI, consider adjacent parcel assembly, or re-profile to a smaller build.

## `gate.entitlement_path_exists` — Entitlement path exists

Severity **fatal** · applies to: hyperscale_training, inference_edge, retrofit_colo
 · caps at **72** when CONDITIONAL

```
FAIL if lnd.zoning_status == "incompatible"
CONDITIONAL if lnd.zoning_status in ["rezoning_contested", "rezoning_routine"]
else PASS
```

A discretionary rezoning converts an engineering problem into a political one. That is survivable but it must be visible in the verdict and priced into the schedule, not discovered at the first public hearing.

**Remediation:** Pre-application meeting with planning staff; budget 9-24 months and community engagement.

## `gate.protected_exclusion` — Protected area exclusion

Severity **fatal** · applies to: hyperscale_training, inference_edge, retrofit_colo
 · caps at **82** when CONDITIONAL

```
FAIL if lnd.protected_overlap > 10
CONDITIONAL if lnd.protected_overlap > 0
else PASS
```

Includes designated protected areas, Ramsar wetlands, key biodiversity areas, and (in India) any land classified as forest, which triggers Forest Conservation Act clearance regardless of actual tree cover.

**Remediation:** Reconfigure the site boundary to avoid overlap entirely — mitigation pathways are slow and uncertain.

## `gate.no_active_moratorium` — No active data center moratorium

Severity **fatal** · applies to: hyperscale_training, inference_edge, retrofit_colo
 · caps at **65** when CONDITIONAL

```
FAIL if com.opposition_risk == "moratorium_active"
CONDITIONAL if com.opposition_risk == "organized_opposition"
else PASS
```

Moratoria are typically time-limited (6-24 months) — record the expiry date, as a moratorium expiring before the target application date may be immaterial. This gate is unusual in relying on Tier C evidence, so a FAIL here is always flagged for human verification rather than treated as final.

**Remediation:** Verify moratorium scope and expiry; some exempt by-right industrial zones or cap by megawatt.

## `gate.compute_legally_deployable` — Intended compute is legally deployable

Severity **fatal** · applies to: hyperscale_training
 · caps at **60** when CONDITIONAL

```
FAIL if reg.export_controls == "prohibited"
CONDITIONAL if reg.export_controls in ["restricted_high_end", "license_uncertain"]
else PASS
```

The gate that distinguishes an AI data center analysis from a generic one. A technically excellent site where the intended accelerators cannot be lawfully installed is not investable for frontier training, though it may be perfectly investable for domestic-accelerator or non-frontier workloads. Record the rule version and date — this input changes faster than any other in the framework.

**Remediation:** Re-profile to domestically-available accelerators, or evaluate license pathway with counsel.
