#!/usr/bin/env python3
"""Plain-assert tests for the rubric loader (run: py tools/test_rubric.py).
Matches the tools/smoke.py idiom - no pytest in this repo.

Uses synthetic rubric dicts, so the shipped rubric is never mutated.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from rubric import (BANDS, SOURCES, dimensions, load_rubric, rubric_hash,
                    validate_rubric)


def _dim(did, tier, weight, source="standard", clause="6.1", scored=None):
    return {"id": did, "tier": tier, "name": f"dim {did}", "source": source,
            "clause": clause, "scored": scored or ["mech"], "weight": weight,
            "obligation": "something must hold"}


def _rubric(dims):
    return {"version": "v1", "standard": "ISO/IEC/IEEE 29119-4:2021",
            "dimensions": dims,
            "technique_fit": {"BVA": ["boundary"], "EP": ["partition"]}}


def test_valid_rubric_has_no_errors():
    r = _rubric([_dim("T1.1", 1, 100), _dim("T2.1", 2, 100)])
    assert validate_rubric(r, "synthetic") == []


def test_weights_must_sum_to_100_per_tier():
    r = _rubric([_dim("T1.1", 1, 60), _dim("T2.1", 2, 100)])
    errs = validate_rubric(r, "synthetic")
    assert any("tier 1 weights sum to 60" in e for e in errs), errs


def test_house_source_is_rejected():
    r = _rubric([_dim("T1.1", 1, 100, source="house"),
                 _dim("T2.1", 2, 100)])
    errs = validate_rubric(r, "synthetic")
    assert any("source 'house'" in e for e in errs), errs


def test_standard_source_requires_a_clause():
    r = _rubric([_dim("T1.1", 1, 100, source="standard", clause=None),
                 _dim("T2.1", 2, 100)])
    errs = validate_rubric(r, "synthetic")
    assert any("clause is required" in e for e in errs), errs


def test_derived_source_may_omit_a_clause_only_if_explicitly_null():
    """A derived dimension still cites the clause it operationalises; the
    validator does not force it, so this must NOT error."""
    r = _rubric([_dim("T1.1", 1, 100, source="derived", clause=None),
                 _dim("T2.1", 2, 100)])
    assert validate_rubric(r, "synthetic") == []


def test_duplicate_dimension_ids_are_rejected():
    r = _rubric([_dim("T1.1", 1, 50), _dim("T1.1", 1, 50),
                 _dim("T2.1", 2, 100)])
    errs = validate_rubric(r, "synthetic")
    assert any("duplicate dimension id 'T1.1'" in e for e in errs), errs


def test_two_dimensions_missing_their_id_do_not_report_a_duplicate_none():
    """Keying duplicate detection on a missing id emitted a spurious
    "duplicate dimension id 'None'" beside the real missing-key error."""
    a, b = _dim("T1.1", 1, 50), _dim("T1.2", 1, 50)
    del a["id"]
    del b["id"]
    errs = validate_rubric(_rubric([a, b, _dim("T2.1", 2, 100)]), "synthetic")
    assert not any("duplicate" in e for e in errs), errs
    assert sum("missing required key 'id'" in e for e in errs) == 2, errs


def test_unknown_scored_mode_is_rejected():
    r = _rubric([_dim("T1.1", 1, 100, scored=["vibes"]),
                 _dim("T2.1", 2, 100)])
    errs = validate_rubric(r, "synthetic")
    assert any("scored 'vibes'" in e for e in errs), errs


def test_dimensions_filters_by_tier():
    r = _rubric([_dim("T1.1", 1, 100), _dim("T2.1", 2, 100)])
    assert [d["id"] for d in dimensions(r, tier=1)] == ["T1.1"]
    assert [d["id"] for d in dimensions(r)] == ["T1.1", "T2.1"]


def test_bands_are_zero_to_four():
    assert sorted(BANDS) == [0, 1, 2, 3, 4]
    assert BANDS[0] == "absent" and BANDS[4] == "exemplary"


def test_shipped_rubric_loads_and_validates():
    """The real standards/rubric/tc-rubric-v1.yaml must be valid."""
    r = load_rubric("v1")
    assert r["version"] == "v1"
    assert validate_rubric(r, "shipped") == []
    t1 = sum(d["weight"] for d in dimensions(r, tier=1))
    t2 = sum(d["weight"] for d in dimensions(r, tier=2))
    assert t1 == 100 and t2 == 100, (t1, t2)


def test_shipped_rubric_has_no_house_dimensions():
    for d in dimensions(load_rubric("v1")):
        assert d["source"] in SOURCES, f"{d['id']}: source {d['source']!r}"


def test_rubric_hash_is_stable_and_prefixed():
    h1, h2 = rubric_hash("v1"), rubric_hash("v1")
    assert h1 == h2
    assert h1.startswith("sha256:") and len(h1) == 71, h1


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"[PASS] {name}")
    print("test_rubric OK")
