"""Registry integrity. These run in CI and catch malformed factor specs before a
2000-site sweep discovers them the expensive way."""
from dcgeo.gates import validate_gate_coverage
from dcgeo.registry import (
    domains,
    load_factors,
    load_gates,
    load_profiles,
    resolve_source,
    validate,
)


def test_registry_validates_clean():
    assert validate() == []


def test_every_gate_declared_is_implemented():
    assert validate_gate_coverage() == []


def test_all_domains_present():
    expected = {"power", "water", "climate", "land", "connectivity",
                "regulatory", "community", "economics"}
    assert set(domains()) == expected


def test_every_factor_has_weights_for_every_profile():
    profiles = set(load_profiles()["profiles"])
    for fid, spec in load_factors().items():
        assert profiles <= set(spec["weights"]), f"{fid} missing profile weights"


def test_every_factor_source_resolves():
    for fid, spec in load_factors().items():
        for s in spec.get("sources", []):
            assert resolve_source(s) is not None, f"{fid}: unresolved source {s}"


def test_gates_reference_real_factors():
    """A gate whose logic mentions a factor id that doesn't exist is a silent no-op."""
    known = set(load_factors())
    for g in load_gates():
        for token in g.get("logic", "").split():
            cleaned = token.strip("()<>=!\"',")
            if "." in cleaned and cleaned.split(".")[0] in {
                "pwr", "wtr", "clm", "lnd", "cnx", "reg", "com", "eco"
            }:
                assert cleaned in known, f"{g['id']} references unknown factor {cleaned}"
