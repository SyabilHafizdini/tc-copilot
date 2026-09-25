#!/usr/bin/env python3
"""Plain-assert tests for Tier 1 mechanical scoring
(run: py tools/test_eval_rubric.py).
Matches the tools/smoke.py idiom - no pytest in this repo.

Synthetic test-case dicts; the wiki is never read.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from eval_rubric import NOT_ASSESSED, mech_bands


def _ctx(**kw):
    d = {"model_ids": {"BVA-01", "BVA-02", "EP-01"},
         "ac_ids": {"1.1-AC1"}, "br_ids": {"BR01"}, "journey_ids": set(),
         "story_rel": "stories/US-FAKE",
         "technique_fit": {"BVA": ["boundary"], "EP": ["partition"],
                           "UC": ["scenario"]},
         "kind_of": {"BVA-01": "boundary", "BVA-02": "boundary",
                     "EP-01": "partition"}}
    d.update(kw)
    return d


def _tc(**kw):
    d = {"id": "TC-1", "technique": "BVA",
         "covers": ["/stories/US-FAKE.md#1.1-AC1"],
         "verifies_rules": [], "coverage_items": ["BVA-01"],
         "body": ("# Test Data\n\n**Amount** = 100\n\n"
                  "# Steps\n\n1. Enter the amount.\n\n"
                  "# Expected Results\n\n1. The amount is accepted.\n")}
    d.update(kw)
    return d


# ------------------------------------------------------------------ T1.1
def test_t11_full_band_when_every_item_resolves():
    assert mech_bands(_tc(), _ctx())["T1.1"] == 4


def test_t11_zero_when_no_coverage_items():
    assert mech_bands(_tc(coverage_items=[]), _ctx())["T1.1"] == 0


def test_t11_one_when_an_item_does_not_resolve():
    b = mech_bands(_tc(coverage_items=["BVA-01", "GHOST"]), _ctx())
    assert b["T1.1"] == 1, "a dangling ref is a defect, not a partial credit"


# ------------------------------------------------------------------ T1.2
def test_t12_full_band_for_a_real_ac():
    assert mech_bands(_tc(), _ctx())["T1.2"] == 4


def test_t12_zero_when_it_traces_to_nothing():
    assert mech_bands(_tc(covers=[]), _ctx())["T1.2"] == 0


def test_t12_one_when_the_ac_does_not_exist_in_the_story():
    tc = _tc(covers=["/stories/US-FAKE.md#1.1-AC99"])
    assert mech_bands(tc, _ctx())["T1.2"] == 1


def test_t12_accepts_a_business_rule_as_basis():
    tc = _tc(covers=[], verifies_rules=["/stories/US-FAKE.md#BR01"])
    assert mech_bands(tc, _ctx())["T1.2"] == 4


def test_t12_accepts_a_journey_entry_as_basis_for_a_flow():
    """A flow carries neither acceptance_criteria nor business_rules - its
    test basis is the asserted journey. Scoring flows off an AC/rule-only
    known set gave every UAT test case T1.2 = 1 against an empty set."""
    ctx = _ctx(ac_ids=set(), br_ids=set(), journey_ids={"J01"},
               story_rel="flows/FL-FAKE")
    tc = _tc(covers=["/flows/FL-FAKE.md#J01"])
    assert mech_bands(tc, ctx)["T1.2"] == 4


def test_t12_ignores_a_basis_ref_that_belongs_to_another_scope():
    """AC ids are per-story, not global. A multi-story test case's
    /stories/US-OTHER.md#1.1-AC1 must not satisfy THIS story's 1.1-AC1."""
    tc = _tc(covers=["/stories/US-OTHER.md#1.1-AC1"])
    assert mech_bands(tc, _ctx())["T1.2"] == 0, "a foreign ref is not a basis"


# ------------------------------------------------------------------ T1.3
def test_t13_full_band_for_concrete_data():
    assert mech_bands(_tc(), _ctx())["T1.3"] == 4


def test_t13_is_not_assessed_when_test_data_is_the_dash_placeholder():
    """render_sit writes '-' when a test case declares no `data:` at all. A
    read-only verification case and a navigation-only UAT step genuinely have
    no input variables; band 0 = 'absent' would collapse 'no inputs to
    specify' into 'inputs specified badly'."""
    body = _tc()["body"].replace("**Amount** = 100", "-")
    assert mech_bands(_tc(body=body), _ctx())["T1.3"] == NOT_ASSESSED


def test_t13_zero_when_test_data_holds_text_but_identifies_no_value():
    """The '-' exemption must not become a hiding place for malformed data.
    A section with content that yields no '**Field** = value' is still a
    defect."""
    body = _tc()["body"].replace("**Amount** = 100", "Amount is about 100")
    assert mech_bands(_tc(body=body), _ctx())["T1.3"] == 0


def test_t13_one_when_a_vague_field_shares_a_line_with_a_concrete_one():
    """render_sit's `data:` is one free-text string, so comma-joined fields
    are a natural authoring shape. Anchored to end-of-line the whole line read
    as ONE value, never matched VAGUE_DATA, and scored 4 instead of 1."""
    body = _tc()["body"].replace("**Amount** = 100",
                                 "**A** = 1, **B** = TBD")
    assert mech_bands(_tc(body=body), _ctx())["T1.3"] == 1


def test_t13_one_for_vague_placeholder_data():
    body = _tc()["body"].replace("**Amount** = 100", "**Amount** = valid data")
    assert mech_bands(_tc(body=body), _ctx())["T1.3"] == 1


def test_t13_one_for_a_tbd_placeholder():
    body = _tc()["body"].replace("**Amount** = 100", "**Amount** = TBD")
    assert mech_bands(_tc(body=body), _ctx())["T1.3"] == 1


# ------------------------------------------- T1.4 ceiling (presence only)
def test_t14_ceiling_is_four_when_an_expected_result_exists():
    assert mech_bands(_tc(), _ctx())["T1.4"] == 4


def test_t14_ceiling_is_zero_when_expected_results_are_empty():
    body = _tc()["body"].replace("1. The amount is accepted.", "")
    assert mech_bands(_tc(body=body), _ctx())["T1.4"] == 0


# ------------------------------------------------------------------ T1.7
def test_t17_ceiling_is_four_when_preconditions_exist():
    body = _tc()["body"] + "\n# Preconditions\n\n1. Logged in.\n"
    assert mech_bands(_tc(body=body), _ctx())["T1.7"] == 4


def test_t17_ceiling_is_one_when_preconditions_are_absent():
    assert mech_bands(_tc(), _ctx())["T1.7"] == 1


# ------------------------------------------------------------------ T1.8
def test_t18_full_band_when_technique_matches_item_kind():
    assert mech_bands(_tc(), _ctx())["T1.8"] == 4


def test_t18_one_when_technique_does_not_fit_the_item_kind():
    """BVA tagged on a partition is a mis-applied technique. This scores FIT,
    not the merit of BVA versus EP - Annex F forbids ranking techniques."""
    tc = _tc(technique="BVA", coverage_items=["EP-01"])
    assert mech_bands(tc, _ctx())["T1.8"] == 1


def test_t18_is_not_assessed_without_coverage_items():
    b = mech_bands(_tc(coverage_items=[]), _ctx())
    assert b["T1.8"] == NOT_ASSESSED, "no items means fit cannot be judged"


# ------------------------------------------------------------------ T1.9
def test_t19_full_band_for_a_positive_case():
    assert mech_bands(_tc(), _ctx())["T1.9"] == 4


def test_t19_full_band_for_one_invalid_input():
    body = ("# Test Data\n\n**Amount** = -1 (invalid)\n\n"
            "# Expected Results\n\n1. Rejected.\n")
    assert mech_bands(_tc(body=body), _ctx())["T1.9"] == 4


def test_t19_zero_for_two_invalid_inputs():
    """29119-4 5.1: one invalid value per negative case, so a fault cannot be
    masked by another."""
    body = ("# Test Data\n\n**Amount** = -1 (invalid)\n"
            "**Date** = 32/13/2026 (invalid)\n\n"
            "# Expected Results\n\n1. Rejected.\n")
    assert mech_bands(_tc(body=body), _ctx())["T1.9"] == 0


def test_t19_zero_for_two_invalid_inputs_on_one_line():
    """Two invalid fields comma-joined onto a single line is the shape
    render_sit's free-text `data:` key produces. Read as one value it scored
    4 - the flattering direction, on a defect the engine had the evidence to
    catch."""
    body = ("# Test Data\n\n"
            "**Amount** = -1 (invalid), **Date** = 32/13/2026 (invalid)\n\n"
            "# Expected Results\n\n1. Rejected.\n")
    assert mech_bands(_tc(body=body), _ctx())["T1.9"] == 0


def test_t19_does_not_split_a_value_that_merely_contains_a_comma():
    """Fields split on the '**' marker, not on ',' - an address is one value."""
    from eval_rubric import _data_values
    body = "# Test Data\n\n**Address** = 12 Jalan Ampang, Kuala Lumpur\n"
    assert _data_values(body) == ["12 Jalan Ampang, Kuala Lumpur"]


def test_judge_only_dimension_is_absent_from_mech_bands():
    """T1.5 is judge-only. mech_bands must not invent a band for it."""
    assert "T1.5" not in mech_bands(_tc(), _ctx())


# --------------------------------------------------- assembly (Task 6)
from eval_rubric import combine, scope_score, tier_score


def _dims(*specs):
    return [{"id": i, "tier": 1, "weight": w, "scored": s}
            for i, w, s in specs]


def test_combine_takes_the_lower_of_ceiling_and_judge():
    assert combine(4, 2) == 2
    assert combine(1, 4) == 1, "judge must never exceed the mechanical ceiling"


def test_combine_without_a_judge_verdict_is_not_assessed():
    """The single most important behaviour in this plan: a skipped judge run
    must never look like a quality failure."""
    assert combine(4, None) == NOT_ASSESSED


def test_combine_never_substitutes_the_ceiling_as_a_band():
    assert combine(4, None) != 4


def test_a_missing_expected_result_is_band_zero_even_without_a_judge():
    """A ceiling of 0 is the one ceiling that is also a measurement:
    min(0, j) == 0 for every legal band j, so no judge verdict could raise it.
    Returning NOT ASSESSED here dropped T1.4 from BOTH the numerator and the
    denominator, and a test case with no expected result at all scored a
    perfect 100.0."""
    assert combine(0, None) == 0


def test_combine_keeps_a_non_zero_ceiling_not_assessed_without_a_judge():
    """Ceilings 1-3 are upper bounds the judge can still move within, so they
    stay unmeasured. The exception is exactly and only 0."""
    assert combine(1, None) == NOT_ASSESSED
    assert combine(2, None) == NOT_ASSESSED
    assert combine(3, None) == NOT_ASSESSED


def test_combine_ceiling_zero_exception_does_not_fire_on_not_assessed():
    assert combine(NOT_ASSESSED, None) == NOT_ASSESSED
    assert combine(None, None) == NOT_ASSESSED


def test_combine_mech_only_dimension_passes_through():
    assert combine(3, "mech-only") == 3


def test_tier_score_weights_bands_to_100():
    dims = _dims(("T1.1", 50, ["mech"]), ("T1.2", 50, ["mech"]))
    score, partial = tier_score({"T1.1": 4, "T1.2": 4}, dims)
    assert score == 100.0 and partial is False


def test_tier_score_half_bands_give_half_marks():
    dims = _dims(("T1.1", 50, ["mech"]), ("T1.2", 50, ["mech"]))
    score, _ = tier_score({"T1.1": 2, "T1.2": 2}, dims)
    assert score == 50.0


def test_not_assessed_is_excluded_from_the_denominator():
    """Excluding it keeps the score honest; scoring it 0 would punish the
    project for not having run the judges."""
    dims = _dims(("T1.1", 50, ["mech"]), ("T1.5", 50, ["judge"]))
    score, partial = tier_score({"T1.1": 4, "T1.5": NOT_ASSESSED}, dims)
    assert score == 100.0
    assert partial is True


def test_mechanical_not_assessed_does_not_mark_the_score_partial():
    """T2.4 with no infeasible item, T1.3 on a no-input case: nothing a judge
    could add, so the score is complete, not PARTIAL (spec 6.3 names JUDGE
    dimensions only)."""
    dims = [{"id": "T1.1", "weight": 1, "scored": ["mech"]},
            {"id": "T1.3", "weight": 1, "scored": ["mech"]}]
    score, partial = tier_score({"T1.1": 4, "T1.3": NOT_ASSESSED}, dims)
    assert score == 100.0 and partial is False


def test_all_not_assessed_gives_none_not_zero():
    dims = _dims(("T1.5", 100, ["judge"]))
    score, partial = tier_score({"T1.5": NOT_ASSESSED}, dims)
    assert score is None and partial is True


def test_scope_score_blends_tiers():
    assert scope_score(100.0, 50.0, {"tier1": 40, "tier2": 60}) == 70.0


def test_scope_score_with_a_missing_tier_uses_the_other():
    assert scope_score(None, 80.0, {"tier1": 40, "tier2": 60}) == 80.0
    assert scope_score(90.0, None, {"tier1": 40, "tier2": 60}) == 90.0


def test_scope_score_with_no_tiers_is_none():
    assert scope_score(None, None, {"tier1": 40, "tier2": 60}) is None


# ------------------------------------------------ tier 2 helpers (Task 6)
from eval_rubric import _ac_coverage_pct, _band_from_pct, _redundancy_band


def test_band_from_pct_boundaries():
    assert _band_from_pct(100) == 4
    assert _band_from_pct(99.99) == 3
    assert _band_from_pct(90) == 3
    assert _band_from_pct(89.9) == 2
    assert _band_from_pct(75) == 2
    assert _band_from_pct(74.9) == 1
    assert _band_from_pct(50) == 1
    assert _band_from_pct(49.9) == 0
    assert _band_from_pct(0) == 0


def test_band_from_pct_none_is_not_assessed():
    """Undefined coverage must not collapse to band 0."""
    assert _band_from_pct(None) == NOT_ASSESSED


def test_ac_coverage_counts_covered_acs():
    fm = {"acceptance_criteria": [{"id": "AC1"}, {"id": "AC2"}]}
    tcs = [{"covers": ["/stories/US-F.md#AC1"]}]
    assert _ac_coverage_pct(fm, tcs) == 50.0


def test_ac_coverage_is_none_without_acs():
    assert _ac_coverage_pct({"acceptance_criteria": []}, []) is None


def test_ac_coverage_ignores_refs_to_other_stories_acs():
    """AC ids are per-story, not globally unique, so the ref must be filtered
    by CONCEPT and not by suffix. US-OTHER's AC1 is a different requirement
    from ours and must not cover it. (With a non-colliding id like #AC9 this
    test would pass on the non-collision instead of on the filtering.)"""
    fm = {"acceptance_criteria": [{"id": "AC1"}]}
    tcs = [{"covers": ["/stories/US-OTHER.md#AC1"]}]
    assert _ac_coverage_pct(fm, tcs, "stories/US-MINE") == 0.0


def test_ac_coverage_counts_a_ref_to_this_scope():
    fm = {"acceptance_criteria": [{"id": "AC1"}]}
    tcs = [{"covers": ["/stories/US-MINE.md#AC1"]}]
    assert _ac_coverage_pct(fm, tcs, "stories/US-MINE") == 100.0


def test_ac_coverage_excludes_voided_acs_from_the_denominator():
    """Voiding an AC cascades its test cases to retired, which _tc_records
    drops. Counting the AC anyway would lower T2.2 permanently with no
    possible remedy - the rubric obligation says every ACTIVE AC."""
    fm = {"acceptance_criteria": [{"id": "AC1"},
                                  {"id": "AC2", "status": "voided"}]}
    tcs = [{"covers": ["/stories/US-MINE.md#AC1"]}]
    assert _ac_coverage_pct(fm, tcs, "stories/US-MINE") == 100.0


def test_ac_coverage_is_none_when_every_ac_is_voided():
    fm = {"acceptance_criteria": [{"id": "AC1", "status": "voided"}]}
    assert _ac_coverage_pct(fm, [], "stories/US-MINE") is None


def test_redundancy_band_full_when_every_set_is_distinct():
    tcs = [{"coverage_items": ["BVA-01"]}, {"coverage_items": ["BVA-02"]}]
    assert _redundancy_band(tcs) == 4


def test_redundancy_band_drops_on_a_duplicate_set():
    tcs = [{"coverage_items": ["BVA-01"]}, {"coverage_items": ["BVA-01"]}]
    assert _redundancy_band(tcs) < 4


def test_redundancy_band_ignores_order():
    tcs = [{"coverage_items": ["A", "B"]}, {"coverage_items": ["B", "A"]}]
    assert _redundancy_band(tcs) < 4, "same items in another order is the same set"


def test_redundancy_band_is_not_assessed_without_coverage_items():
    assert _redundancy_band([{"coverage_items": []}]) == NOT_ASSESSED


# ------------------------------------------------------- T2.1 (incl. the cap)
from eval_rubric import T21_INCOMPLETE_MODEL_CAP, _t21_band


def test_t21_band_is_the_unweighted_mean_of_per_technique_C():
    cov = {"BVA": {"C": 100.0}, "EP": {"C": 50.0}}
    assert _t21_band(cov, []) == _band_from_pct(75.0)


def test_t21_band_ignores_a_technique_with_undefined_coverage():
    cov = {"BVA": {"C": 100.0}, "ST": {"C": None}}
    assert _t21_band(cov, []) == 4


def test_t21_band_is_not_assessed_when_no_technique_has_a_denominator():
    assert _t21_band({"ST": {"C": None}}, []) == NOT_ASSESSED


def test_t21_band_is_capped_when_the_model_itself_is_incomplete():
    """Spec 5.1: a flow whose model is the main scenario only scores
    C = 1/1 = 100% on an incomplete model, and that "must not be silently
    rounded up to a clean 100%". The warning printed but touched no band."""
    cov = {"UC": {"C": 100.0}}
    assert _t21_band(cov, []) == 4
    assert _t21_band(cov, ["INCOMPLETE MODEL - main scenario only"]) == \
        T21_INCOMPLETE_MODEL_CAP


def test_t21_cap_never_raises_an_already_lower_band():
    cov = {"UC": {"C": 10.0}}
    assert _t21_band(cov, ["INCOMPLETE MODEL - main scenario only"]) == 0


def test_an_incomplete_model_scores_strictly_less_than_a_complete_one():
    """Comparative guard: the warning must COST something. Two identical
    coverage results, one flagged incomplete, must not tie."""
    cov = {"UC": {"C": 100.0}}
    assert _t21_band(cov, ["INCOMPLETE MODEL - main scenario only"]) < \
        _t21_band(cov, [])


# ------------------------------------------------ CLI resolution (review fix)
from eval_rubric import _t24_band, _tc_records, score_scope


def _story_fm(story_id="US-FAKE", items=None, acs=None):
    return {
        "type": "User Story",
        "id": story_id,
        "acceptance_criteria": acs if acs is not None else [{"id": "1.1-AC1"}],
        "business_rules": [],
        "test_model": {"status": "confirmed", "items": items or []},
    }


def _tc_fm(tc_id, story_id, status="active", coverage_items=None):
    return {
        "type": "Test Case",
        "id": tc_id,
        "status": status,
        "technique": "BVA",
        "covers": [f"/stories/{story_id}.md#1.1-AC1"],
        "verifies_rules": [],
        "coverage_items": coverage_items if coverage_items is not None else ["BVA-01"],
        "body": ("# Test Data\n\n**Amount** = 100\n\n"
                 "# Steps\n\n1. Enter the amount.\n\n"
                 "# Expected Results\n\n1. The amount is accepted.\n"),
    }


def _model_item(item_id="BVA-01", technique="BVA", kind="boundary",
                 basis=None, feasible=True, justification=None):
    d = {"id": item_id, "technique": technique, "kind": kind,
         "basis": basis or ["1.1-AC1"], "feasible": feasible}
    if justification is not None:
        d["justification"] = justification
    return d


def test_tc_records_selects_only_the_requested_story():
    concepts = {
        "stories/US-1": (_story_fm("US-1"), "", None),
        "testcases/TC-1": (_tc_fm("TC-1", "US-1"), "body1", None),
        "testcases/TC-2": (_tc_fm("TC-2", "US-2"), "body2", None),
    }
    out = _tc_records(concepts, "stories/US-1")
    assert [r["id"] for r in out] == ["TC-1"]


def test_tc_records_does_not_substring_match_similar_story_ids():
    """US-1.1 must not pick up test cases belonging to US-1.10 (or vice
    versa) just because one id is a substring of the other."""
    concepts = {
        "stories/US-1.1": (_story_fm("US-1.1"), "", None),
        "testcases/TC-A": (_tc_fm("TC-A", "US-1.1"), "bodyA", None),
        "testcases/TC-B": (_tc_fm("TC-B", "US-1.10"), "bodyB", None),
    }
    out = _tc_records(concepts, "stories/US-1.1")
    assert [r["id"] for r in out] == ["TC-A"]


def test_tc_records_excludes_retired_test_cases():
    concepts = {
        "stories/US-1": (_story_fm("US-1"), "", None),
        "testcases/TC-1": (_tc_fm("TC-1", "US-1", status="active"), "b1", None),
        "testcases/TC-2": (_tc_fm("TC-2", "US-1", status="retired"), "b2", None),
    }
    out = _tc_records(concepts, "stories/US-1")
    assert [r["id"] for r in out] == ["TC-1"]


def test_tc_records_keeps_only_the_scope_kind():
    """I5: a story's rubric set is its SIT cases, a flow's is its UAT cases -
    a UAT case covering the story's AC is not part of the story's set. A
    record without a `kind` (legacy fixture) is kept."""
    sit = dict(_tc_fm("TC-1", "US-1"), kind="sit")
    uat = dict(_tc_fm("TC-2", "US-1"), kind="uat")
    legacy = _tc_fm("TC-3", "US-1")
    concepts = {
        "stories/US-1": (_story_fm("US-1"), "", None),
        "testcases/TC-1": (sit, "b1", None),
        "testcases/TC-2": (uat, "b2", None),
        "testcases/TC-3": (legacy, "b3", None),
    }
    assert [r["id"] for r in _tc_records(concepts, "stories/US-1", kind="sit")] == ["TC-1", "TC-3"]
    assert [r["id"] for r in _tc_records(concepts, "stories/US-1", kind="uat")] == ["TC-2", "TC-3"]
    assert [r["id"] for r in _tc_records(concepts, "stories/US-1")] == ["TC-1", "TC-2", "TC-3"]


def test_score_scope_resolves_a_bare_story_id_to_the_concept_key():
    """The Critical fix: a bare CLI id like 'US-FAKE' must resolve to the
    'stories/US-FAKE' concept key (cmd_gate's convention), not be handed to
    resolve_ref (which only strips '/' and '.md' and would leave it
    unchanged, matching nothing in concepts)."""
    items = [_model_item()]
    concepts = {
        "stories/US-FAKE": (_story_fm("US-FAKE", items=items), "", None),
        "testcases/TC-1": (_tc_fm("TC-1", "US-FAKE"), "body1", None),
    }

    def fake_load_all():
        return concepts, {}

    result = score_scope("story", "US-FAKE", load_all=fake_load_all)
    assert isinstance(result, dict)
    assert result["scope"] == "US-FAKE"
    assert result["score"] is not None


def test_score_scope_no_concept_exits_cleanly_not_a_traceback():
    def fake_load_all():
        return {}, {}
    try:
        score_scope("story", "US-NOPE", load_all=fake_load_all)
        assert False, "expected SystemExit"
    except SystemExit as e:
        assert "no concept for" in str(e)


def test_t24_band_not_assessed_when_nothing_was_discounted():
    items = [_model_item(feasible=True)]
    assert _t24_band(items) == NOT_ASSESSED


def test_t24_band_full_when_every_discount_is_justified():
    items = [_model_item(feasible=False, justification="Hardware cannot reach it.")]
    assert _t24_band(items) == 4


def test_t24_band_zero_when_a_discount_is_unjustified():
    items = [_model_item(feasible=False, justification=None)]
    assert _t24_band(items) == 0


def test_t24_band_zero_when_justification_is_blank():
    items = [_model_item(feasible=False, justification="   ")]
    assert _t24_band(items) == 0


# ============================================================================
# THE INVARIANT: no path may RAISE a score by failing to measure something it
# was able to measure. Every test below is comparative - a scope missing X must
# score STRICTLY LESS than an otherwise-identical scope that has X. Asserting
# only that a NOT ASSESSED marker appears cannot catch a dimension that quietly
# left the denominator, which is how C-1, C-2, I-5 and I-6 all shipped.
# ============================================================================

_BODY_FULL = ("# Test Data\n\n**Amount** = 100\n\n"
              "# Steps\n\n1. Enter the amount.\n\n"
              "# Expected Results\n\n1. The amount is accepted.\n")
_BODY_NO_EXPECTED = ("# Test Data\n\n**Amount** = 100\n\n"
                     "# Steps\n\n1. Enter the amount.\n")


def _scored(story_fm, tc_fms):
    """score_scope over a synthetic one-story wiki."""
    concepts = {"stories/US-FAKE": (story_fm, "", None)}
    for n, tc in enumerate(tc_fms, start=1):
        concepts[f"testcases/TC-{n}"] = (tc, tc.get("body", ""), None)
    return score_scope("story", "US-FAKE", load_all=lambda: (concepts, {}))


def test_a_test_case_with_no_expected_result_scores_less_than_one_with_it():
    """C-1 end to end. Before the ceiling-of-0 fix BOTH sides scored a perfect
    100.0: T1.4's computed ceiling of 0 became NOT ASSESSED and left the
    denominator, so the missing expected result cost exactly nothing."""
    items = [_model_item()]
    good = _scored(_story_fm(items=items),
                   [_tc_fm("TC-1", "US-FAKE") | {"body": _BODY_FULL}])
    bad = _scored(_story_fm(items=items),
                  [_tc_fm("TC-1", "US-FAKE") | {"body": _BODY_NO_EXPECTED}])
    assert bad["tier1"] < good["tier1"], (bad["tier1"], good["tier1"])
    assert bad["score"] < good["score"], (bad["score"], good["score"])


def test_a_test_case_covering_a_foreign_ac_scores_less_than_one_covering_ours():
    """I-1 end to end. _tc_records admits a multi-story test case if ANY of
    its covers resolves here, so its foreign refs came along; comparing bare
    suffixes let US-OTHER's AC1 satisfy ours and inflated T2.2."""
    items = [_model_item()]
    acs = [{"id": "1.1-AC1"}, {"id": "1.1-AC2"}]
    ours = _tc_fm("TC-1", "US-FAKE")
    ours["covers"] = ["/stories/US-FAKE.md#1.1-AC2",
                      "/stories/US-FAKE.md#1.1-AC1"]
    foreign = _tc_fm("TC-1", "US-FAKE")
    foreign["covers"] = ["/stories/US-FAKE.md#1.1-AC2",
                         "/stories/US-OTHER.md#1.1-AC1"]
    good = _scored(_story_fm(items=items, acs=acs), [ours])
    bad = _scored(_story_fm(items=items, acs=acs), [foreign])
    assert bad["tier2"] < good["tier2"], (bad["tier2"], good["tier2"])


def test_a_test_case_with_no_input_data_scores_at_least_one_with_vague_data():
    """I-6 must raise the right score and only the right one. '-' means the
    case has no input variables (NOT ASSESSED); a section that names a vague
    value is still a defect and must stay strictly worse."""
    items = [_model_item()]
    dash = _tc_fm("TC-1", "US-FAKE")
    dash["body"] = _BODY_FULL.replace("**Amount** = 100", "-")
    vague = _tc_fm("TC-1", "US-FAKE")
    vague["body"] = _BODY_FULL.replace("**Amount** = 100", "**Amount** = TBD")
    a = _scored(_story_fm(items=items), [dash])
    b = _scored(_story_fm(items=items), [vague])
    assert b["tier1"] < a["tier1"], (b["tier1"], a["tier1"])


def test_a_multi_field_line_with_a_vague_value_scores_less_than_a_concrete_one():
    """I-5 end to end. Anchored to end-of-line both bodies produced ONE value
    that never matched VAGUE_DATA, so they tied at band 4."""
    items = [_model_item()]
    concrete = _tc_fm("TC-1", "US-FAKE")
    concrete["body"] = _BODY_FULL.replace("**Amount** = 100",
                                          "**A** = 1, **B** = 2")
    vague = _tc_fm("TC-1", "US-FAKE")
    vague["body"] = _BODY_FULL.replace("**Amount** = 100",
                                       "**A** = 1, **B** = TBD")
    good = _scored(_story_fm(items=items), [concrete])
    bad = _scored(_story_fm(items=items), [vague])
    assert bad["tier1"] < good["tier1"], (bad["tier1"], good["tier1"])


# --------------------------------------------- C-2: the vacuous test model
def test_score_scope_refuses_a_confirmed_model_with_no_items():
    """C-2. items: [] leaves T2.1/T2.4/T2.7 all NOT ASSESSED, so Tier 2 became
    T2.2 alone reported as a clean 100.0 - and the whole 29119-4 contribution
    evaporated while the headline score went UP."""
    try:
        _scored(_story_fm(items=[]), [_tc_fm("TC-1", "US-FAKE")])
        assert False, "expected SystemExit"
    except SystemExit as e:
        msg = str(e)
        assert "REFUSED" in msg and "identifies no coverage items" in msg, msg
        assert "Next:" in msg, "a refusal must name the remedy"


def test_tier2_is_vacuous_when_every_model_dimension_is_unmeasured():
    """Belt and braces for C-2: reached by any route, Tier 2 must not be
    published as a clean number derived from T2.2 alone. T2.2 is deliberately
    excluded from the check - it is scored from the story's ACs and would
    still produce a number with no test model at all."""
    from eval_rubric import _MODEL_DEPENDENT_T2, _tier2_is_vacuous
    assert _MODEL_DEPENDENT_T2 == ("T2.1", "T2.4", "T2.7")
    vacuous = {"T2.1": NOT_ASSESSED, "T2.2": 4, "T2.4": NOT_ASSESSED,
               "T2.7": NOT_ASSESSED}
    assert _tier2_is_vacuous(vacuous) is True
    assert _tier2_is_vacuous(dict(vacuous, **{"T2.7": 4})) is False
    assert _tier2_is_vacuous({"T2.2": 4}) is True, "absent counts as unmeasured"


# ------------------------------- I-4: an unvalidated model is not consumed
def test_score_scope_refuses_a_bare_string_model_item():
    """Hand-authored frontmatter is the expected case during migration. This
    used to raise AttributeError: 'str' object has no attribute 'get'."""
    try:
        _scored(_story_fm(items=["BVA-01"]), [_tc_fm("TC-1", "US-FAKE")])
        assert False, "expected SystemExit"
    except SystemExit as e:
        assert "REFUSED" in str(e) and "must be a mapping" in str(e), str(e)
    except AttributeError:
        assert False, "must not raise a raw AttributeError"


def test_score_scope_refuses_a_model_item_missing_its_technique():
    """This used to put a None key into the coverage dict and then raise
    TypeError from json.dumps(..., sort_keys=True) at write time."""
    item = _model_item()
    del item["technique"]
    try:
        _scored(_story_fm(items=[item]), [_tc_fm("TC-1", "US-FAKE")])
        assert False, "expected SystemExit"
    except SystemExit as e:
        assert "REFUSED" in str(e) and "technique" in str(e), str(e)
    except TypeError:
        assert False, "must not raise a raw TypeError"


def test_score_scope_refusal_lists_every_model_error_at_once():
    item = _model_item(technique="ZZ", kind="vibe")
    try:
        _scored(_story_fm(items=[item]), [_tc_fm("TC-1", "US-FAKE")])
        assert False, "expected SystemExit"
    except SystemExit as e:
        assert "technique" in str(e) and "kind" in str(e), str(e)


# ---------------------------------------------------------- CLI arg parsing
from eval_rubric import main as _cli_main


def test_cli_story_with_no_value_exits_cleanly_not_a_traceback():
    try:
        _cli_main(["--story"])
        assert False, "expected SystemExit"
    except SystemExit as e:
        assert "missing required --story" in str(e)
    except IndexError:
        assert False, "must not raise a raw IndexError"


def test_cli_usage_does_not_advertise_unimplemented_json_flag():
    import io
    import contextlib
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        _cli_main(["--help"])
    assert "--json" not in buf.getvalue()


# ------------------------------------------------- CLI reporting and --strict
import contextlib  # noqa: E402
import io  # noqa: E402

import eval_rubric as _er  # noqa: E402


def _fake_result(**kw):
    d = {"scope": "US-CLI", "rubric_version": "v1", "rubric_hash": "sha256:x",
         "standard": "ISO/IEC/IEEE 29119-4:2021", "score": 90.0,
         "tier1": 90.0, "tier2": 90.0, "partial": False, "threshold": 70,
         "coverage": {"BVA": {"N": 1, "T": 1, "C": 100.0}},
         "model_warnings": [], "unknown_item_refs": [], "test_cases": []}
    d.update(kw)
    return d


def _run_cli(argv, **result_kw):
    """(stdout, SystemExit or None) with score_scope stubbed out."""
    real = _er.score_scope
    _er.score_scope = lambda *a, **k: _fake_result(**result_kw)
    buf = io.StringIO()
    try:
        with contextlib.redirect_stdout(buf):
            _cli_main(argv)
        return buf.getvalue(), None
    except SystemExit as e:
        return buf.getvalue(), e
    finally:
        _er.score_scope = real


def test_cli_prints_unknown_coverage_item_refs():
    """A test case naming a coverage item the model does not define is an
    integrity failure. The CLI printed coverage and model_warnings but not
    this, so the operator - who reads the CLI, not the JSON - never saw it."""
    out, _ = _run_cli(["--story", "US-CLI"], unknown_item_refs=["GHOST-01"])
    assert "GHOST-01" in out, out


def test_strict_refuses_while_the_score_is_partial():
    """I-7. With no judges wired up, Tier 1 measures 47 of its 100 weight
    points on every run, so --strict compared roughly half a rubric against
    the full threshold and said nothing about it."""
    out, exc = _run_cli(["--story", "US-CLI", "--strict"], partial=True)
    assert exc is not None, "--strict must refuse a partial score"
    assert "PARTIAL" in str(exc), str(exc)
    assert "--allow-partial" in str(exc), "the refusal must name the remedy"


def test_strict_allow_partial_gates_on_the_partial_score():
    _out, exc = _run_cli(["--story", "US-CLI", "--strict", "--allow-partial"],
                         partial=True, score=90.0)
    assert exc is None, str(exc)


def test_strict_allow_partial_still_fails_below_the_threshold():
    _out, exc = _run_cli(["--story", "US-CLI", "--strict", "--allow-partial"],
                         partial=True, score=10.0)
    assert exc is not None and "threshold" in str(exc), str(exc)


def test_strict_still_gates_on_the_threshold_when_not_partial():
    _out, exc = _run_cli(["--story", "US-CLI", "--strict"],
                         partial=False, score=10.0)
    assert exc is not None and "threshold" in str(exc), str(exc)


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"[PASS] {name}")
    print("test_eval_rubric OK")
