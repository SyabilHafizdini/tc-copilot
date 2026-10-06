#!/usr/bin/env python3
"""Plain-assert tests for the shared UAT engine (run: py tools/test_render_uat.py)."""
import contextlib, io, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import render_uat

HIGH = {"scenario": "High", "steps": "High", "data": "High", "expected": "High"}


def _spec(**entry):
    e = {"area": "A", "priority": "P1", "title": "t", "objective": "o",
         "steps": "1. Do it.", "expected": "1. Done.", "profile": "p1"}
    e.update(entry)
    return {"flow": "/flows/F.md", "out": "testcases/uat",
            "story_num": "1.1", "scenario_id": "SC-{jid}", "generator_version": "1.0.0",
            "profiles": {"p1": "couple 1"}, "entries": {"J01": e}}


def _errors(spec):
    buf = io.StringIO()
    with contextlib.redirect_stderr(buf):
        try:
            render_uat.validate_uat_spec(spec, Path("x.yaml"))
        except SystemExit:
            return buf.getvalue()
    return ""


def test_valid_linear_spec_has_no_errors():
    assert _errors(_spec()) == ""


def test_module_is_optional():
    spec = _spec()
    assert _errors(spec) == ""
    spec["module"] = "/modules/m.md"
    assert _errors(spec) == ""


def test_confidence_is_optional_but_shape_checked():
    assert _errors(_spec(confidence=dict(HIGH))) == ""
    bad = _spec(confidence={"scenario": "High", "steps": "High", "data": "High"})
    assert "confidence.expected" in _errors(bad)
    assert "must be one of" in _errors(_spec(confidence=dict(HIGH, data="Sure")))


def test_low_part_without_remark_is_refused():
    bad = _spec(confidence=dict(HIGH, data="Low"))
    assert "remarks.data" in _errors(bad)
    assert _errors(_spec(confidence=dict(HIGH, data="Low"),
                         remarks={"data": "value not stated"})) == ""


def test_unknown_entry_key_is_refused():
    assert "unknown key 'stepz'" in _errors(_spec(stepz="x"))


def test_bad_priority_and_alts_are_refused():
    assert "priority must be one of" in _errors(_spec(priority="P9"))
    assert "alts must be a list" in _errors(_spec(alts="SC-ALT-01"))


def test_alts_must_be_alternative_scenarios_of_the_flow_model():
    flow = {"test_model": {"items": [
        {"id": "SC-MAIN", "role": "main"}, {"id": "SC-ALT-01", "role": "alternative"}]}}
    ok = {"J01": {"alts": ["SC-ALT-01"]}}
    assert render_uat.alt_errors(ok, flow, "F") == []
    errs = render_uat.alt_errors({"J01": {"alts": ["SC-MAIN", "SC-ALT-09"]}}, flow, "F")
    assert len(errs) == 2 and "SC-ALT-09" in errs[1], errs


def test_branch_entry_with_another_profile_must_be_marked_fresh():
    spec = _spec()
    spec["profiles"] = {"p1": "couple 1", "p2": "couple 2"}
    spec["entries"]["J01"]["profile"] = "p1"
    spec["entries"]["J02"] = dict(spec["entries"]["J01"], profile="p2", continue_from="J01")
    assert "profile 'p2' differs from J01's 'p1'" in _errors(spec)
    spec["entries"]["J02"]["fresh_run"] = True
    assert _errors(spec) == ""


def test_undeclared_profile_is_named():
    assert "profile 'zz' is not declared in `profiles`" in _errors(_spec(profile="zz"))


def test_missing_profile_and_profiles_are_named_not_raised():
    old = _spec()
    del old["entries"]["J01"]["profile"]
    del old["profiles"]
    errs = _errors(old)
    assert "missing required key 'profile'" in errs
    assert "missing required top-level key 'profiles'" in errs


def test_wrong_typed_profile_values_are_spec_errors():
    assert "profile must be a profile name" in _errors(_spec(profile=["p1"]))
    bad = _spec()
    bad["profiles"] = ["p1"]
    assert "profiles must be a non-empty mapping" in _errors(bad)


def test_continue_from_must_name_an_earlier_entry():
    assert "continue_from 'J09' is not an earlier entry" in _errors(
        _spec(continue_from="J09"))


def _chain(*shape):
    """shape: (jid, profile, extras) in spec order."""
    spec = _spec()
    spec["profiles"] = {"p1": "a", "p2": "b"}
    base = spec["entries"]["J01"]
    spec["entries"] = {j: dict(base, profile=p, **x) for j, p, x in shape}
    return spec


def test_implicit_link_profile_change_needs_fresh_run():
    spec = _chain(("J01", "p1", {}), ("J02", "p2", {}))
    assert "profile 'p2' differs from J01's 'p1'" in _errors(spec)
    spec["entries"]["J02"]["fresh_run"] = True
    assert _errors(spec) == ""


def test_second_linear_successor_needs_fresh_run():
    spec = _chain(("J01", "p1", {}), ("J02", "p1", {}),
                  ("J03", "p1", {"continue_from": "J01"}))
    assert "J01 is already continued by J02" in _errors(spec)
    spec["entries"]["J03"]["fresh_run"] = True
    assert _errors(spec) == ""


def test_fresh_fork_does_not_consume_its_predecessor():
    spec = _chain(("J05", "p1", {}),
                  ("J06", "p2", {"fresh_run": True}),
                  ("J07", "p2", {"fresh_run": True, "continue_from": "J05"}),
                  ("J08", "p1", {"continue_from": "J05"}))
    assert _errors(spec) == ""


def test_purely_linear_spec_validates():
    spec = _chain(("J01", "p1", {}), ("J02", "p1", {}), ("J03", "p1", {}))
    assert _errors(spec) == ""


def test_ids_derive_from_ac_number_or_trailing_number():
    cfg = {"ids": {"tc_format_uat": "UAT-{story_num}-AC{ac_num:02d}-{seq:02d}"}}
    assert render_uat.tc_id(cfg, "1.1", "1.1-AC5", 1) == "UAT-1.1-AC05-01"
    assert render_uat.tc_id(cfg, "ROM-SC01", "HS-04", 2) == "UAT-ROM-SC01-AC04-02"
    assert render_uat.display_id("UAT-1.1-AC05-01") == "TC-1.1-AC05-01"


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn(); print(f"[PASS] {name}")
    print("test_render_uat OK")
