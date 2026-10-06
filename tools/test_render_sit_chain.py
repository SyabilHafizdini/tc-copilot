#!/usr/bin/env python3
"""Plain-assert tests for the SIT chain validator (run: py tools/test_render_sit_chain.py)."""
import contextlib, io, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import render_sit

HIGH = {"scenario": "High", "steps": "High", "data": "High", "expected": "High"}


def _tc(ac, seq, cont, starts, ends, profile="p1", **kw):
    d = {"ac": ac, "seq": seq, "technique": "UC", "priority": "P1", "area": "A",
         "title": "t", "objective": "o", "steps": "1. Do.", "expected": "1. Done.",
         "run": "Main", "section": "S", "continue_from": cont, "starts_at": starts,
         "ends_at": ends, "profile": profile, "confidence": dict(HIGH)}
    d.update(kw)
    return d


def _spec(tcs):
    return {"story": "/stories/US-X.md", "module": "/modules/m.md", "figma": None,
            "out": "testcases/sit/m", "ac_prefix": "1.1.3.1.1",
            "scenario_id": "SC-{ac}-{seq:02d}", "generator_version": "1.0.0",
            "pre_common": "1. Logged in.", "post_default": "No change.",
            "states": {"home": "Portal home, not logged in.", "s1": "Step 1 completed.",
                       "s2": "Step 2 completed."},
            "entry_state": "home", "profiles": {"p1": "persona 1", "p2": "persona 2"},
            "test_cases": tcs}


def _errors(spec):
    buf = io.StringIO()
    with contextlib.redirect_stderr(buf):
        try:
            render_sit.validate_spec(spec, Path("x.yaml"))
        except SystemExit:
            return buf.getvalue()
    return ""


def test_valid_chain_passes_with_prd_style_ac_ids():
    ok = [_tc("AC1", 1, "start", "home", "s1"), _tc("AC2", 1, "AC1/1", "s1", "s2")]
    assert _errors(_spec(ok)) == ""
    full = [_tc("1.1.3.1.1-AC5", 1, "start", "home", "s1"),
            _tc("1.1.3.1.1-AC6", 1, "1.1.3.1.1-AC5/1", "s1", "s2")]
    assert _errors(_spec(full)) == ""
    bad = [full[0], dict(full[1], starts_at="s2", ends_at="s2")]
    e = _errors(_spec(bad))
    assert "ends at 's1' but this test case starts at 's2'" in e, e
    assert "1.1.3.1.1-AC5/1" in e, e


def test_element_block_must_be_boolean():
    for v in (True, False):
        assert _errors(_spec([_tc("AC1", 1, "start", "home", "s1", element_block=v)])) == ""
    e = _errors(_spec([_tc("AC1", 1, "start", "home", "s1", element_block="no")]))
    assert "element_block must be true or false" in e, e


def test_element_block_false_omits_the_block_and_default_keeps_it():
    orig = render_sit.element_verification_block_multi
    render_sit.element_verification_block_multi = lambda fm, ids: "   a. **Name** textbox"
    try:
        tc = _tc("AC1", 1, "start", "home", "s1")
        kept = render_sit.expected_results({}, tc, ["AC1"])
        assert "2. The following elements are displayed" in kept and "**Name**" in kept, kept
        off = render_sit.expected_results({}, dict(tc, element_block=False), ["AC1"])
        assert off == "1. Done.", off
        on = render_sit.expected_results({}, dict(tc, element_block=True), ["AC1"])
        assert on == kept
    finally:
        render_sit.element_verification_block_multi = orig


def test_predecessor_must_end_where_successor_starts():
    bad = [_tc("AC1", 1, "start", "home", "s1"), _tc("AC2", 1, "AC1/1", "s2", "s2")]
    assert "ends at 's1' but this test case starts at 's2'" in _errors(_spec(bad))


def test_start_must_begin_at_the_entry_state():
    assert "entry_state" in _errors(_spec([_tc("AC1", 1, "start", "s1", "s2")]))


def test_undeclared_state_and_profile_are_named():
    e = _errors(_spec([_tc("AC1", 1, "start", "home", "nowhere", profile="p9")]))
    assert "ends_at 'nowhere'" in e and "profile 'p9'" in e


def test_old_spec_without_the_keys_names_them():
    old = _tc("AC1", 1, "start", "home", "s1")
    for k in ("starts_at", "ends_at", "profile", "run"):
        del old[k]
    e = _errors(_spec([old]))
    assert all(f"missing required key '{k}'" in e for k in ("starts_at", "ends_at", "profile", "run"))


def test_old_spec_gets_one_hint_line():
    old = [_tc("AC1", 1, "start", "home", "s1"), _tc("AC2", 1, "AC1/1", "s1", "s2")]
    for tc in old:
        for k in ("starts_at", "ends_at", "profile", "run"):
            del tc[k]
    e = _errors(_spec(old))
    assert e.count("predates declared states") == 1
    assert "`states`, `profiles` and `entry_state`" in e and "`starts_at`" in e


def test_non_string_values_are_spec_errors_not_tracebacks():
    e = _errors(_spec([_tc("AC1", 1, "start", ["home"], "s1")]))
    assert "starts_at must be a state name" in e
    e = _errors(_spec([_tc("AC1", 1, "start", "home", {"a": 1})]))
    assert "ends_at must be a state name" in e
    e = _errors(_spec([_tc("AC1", 1, "start", "home", "s1", profile=["p1"])]))
    assert "profile must be a profile name" in e
    sp = _spec([_tc("AC1", 1, "start", "home", "s1")])
    sp["entry_state"] = ["home"]
    assert "entry_state must be the name" in _errors(sp)
    sp = _spec([_tc("AC1", 1, "start", "home", "s1")])
    sp["states"] = ["home"]
    sp["profiles"] = "p1"
    e = _errors(sp)
    assert "states must be a non-empty mapping" in e and "profiles must be" in e


def test_second_linear_successor_must_be_a_fresh_run():
    """A state is consumed by the test case that continues from it. A second
    test case needing the same state has to replay to it: fresh_run."""
    bad = [_tc("AC1", 1, "start", "home", "s1"),
           _tc("AC2", 1, "AC1/1", "s1", "s2"),
           _tc("AC2", 2, "AC1/1", "s1", "s2")]
    assert "already continued by AC2/1" in _errors(_spec(bad))
    ok = [bad[0], bad[1], dict(bad[2], fresh_run=True)]
    assert _errors(_spec(ok)) == ""


def test_linear_continue_cannot_change_profile():
    """The defect that reached a workbook: a scenario-1 case chained onto a
    scenario-3 case. A different data set needs a fresh run."""
    bad = [_tc("AC1", 1, "start", "home", "s1", profile="p1"),
           _tc("AC2", 1, "AC1/1", "s1", "s2", profile="p2")]
    assert "profile 'p2' differs from AC1/1's 'p1'" in _errors(_spec(bad))
    assert _errors(_spec([bad[0], dict(bad[1], fresh_run=True)])) == ""


def test_refusal_leaves_its_state_for_the_next_linear_case():
    ok = [_tc("AC1", 1, "start", "home", "home", technique="ERR"),
          _tc("AC1", 2, "AC1/1", "home", "s1")]
    assert _errors(_spec(ok)) == ""


def test_a_run_is_contiguous_and_a_section_may_repeat_across_runs():
    ok = [_tc("AC1", 1, "start", "home", "s1", run="Main flow", section="Step 1"),
          _tc("AC1", 2, "start", "home", "s1", run="Variant flow", section="Step 1", profile="p2")]
    assert _errors(_spec(ok)) == ""
    bad = ok + [_tc("AC2", 1, "AC1/1", "s1", "s2", run="Main flow", section="Step 2")]
    assert "run 'Main flow' is not contiguous" in _errors(_spec(bad))


def test_every_run_begins_with_a_start():
    """Each sheet is one flow and starts from the beginning."""
    bad = [_tc("AC1", 1, "start", "home", "s1", run="Main flow"),
           _tc("AC2", 1, "AC1/1", "s1", "s2", run="Variant flow")]
    assert "run 'Variant flow' must begin with `continue_from: start`" in _errors(_spec(bad))


def test_a_link_never_crosses_runs():
    bad = [_tc("AC1", 1, "start", "home", "s1", run="Main flow"),
           _tc("AC1", 2, "start", "home", "s1", run="Variant flow", profile="p2"),
           _tc("AC2", 1, "AC1/1", "s1", "s2", run="Variant flow", profile="p2", fresh_run=True)]
    assert "continue_from AC1/1 is in run 'Main flow'" in _errors(_spec(bad))


def test_a_run_may_hold_several_starts_after_its_first():
    ok = [_tc("AC1", 1, "start", "home", "s1", run="Standalone checks"),
          _tc("AC2", 1, "start", "home", "s1", run="Standalone checks")]
    assert _errors(_spec(ok)) == ""


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn(); print(f"[PASS] {name}")
    print("test_render_sit_chain OK")
