#!/usr/bin/env python3
"""Rubric engine - scores test cases against standards/rubric/tc-rubric-v1.yaml.

LLM-FREE BY DESIGN. This file scores the mechanical dimensions itself
(`mech_bands`) and MERGES judge verdicts into the same score via `combine`,
`tier_score` and `scope_score`. Same inputs plus same verdicts produce an
identical score, which is what makes gating legitimate. `score_scope` takes a
`judgments` dict as its seam for those verdicts; a later plan wires it to the
JSON files subagent judges will write - this file already reports correctly
with or without them. `main` is the CLI (`py tools/eval_rubric.py --story
<id> [--strict]`) and writes the result to build/rubric/<scope>-score.json.

A missing judge verdict yields NOT ASSESSED - never band 0. A skipped judge run
must never be indistinguishable from a quality failure. The one exception is a
mechanical ceiling of 0, which no judge verdict could raise; see `combine`.

The invariant behind several of the rules here: NO PATH MAY RAISE A SCORE BY
FAILING TO MEASURE SOMETHING IT WAS ABLE TO MEASURE. A defect the engine can
name must cost something, or the engine rewards the defect.
"""
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

NOT_ASSESSED = "NOT ASSESSED"
NOT_ASSESSABLE = "NOT ASSESSABLE"

# Tokens that name a value without identifying one (29119-4 5.2.2.3 b) requires
# input VALUES to be identified).
VAGUE_DATA = frozenset({
    "tbd", "tba", "todo", "n/a", "na", "any", "valid data", "invalid data",
    "some text", "some value", "valid value", "invalid value", "test data",
    "as required", "appropriate value", "dummy", "xxx", "placeholder",
})

_INVALID_MARK = re.compile(r"\(\s*invalid\s*\)", re.I)

# The '**Field** =' marker that opens one Test Data field. Fields are split on
# THIS boundary rather than on ',' because values legitimately contain commas
# ("**Address** = 12 Jalan Ampang, Kuala Lumpur"), and splitting on the comma
# would shred one value into two rather than separating two fields.
_DATA_FIELD = re.compile(r"\*\*[^*]+\*\*\s*=\s*")

# render_sit.py writes this when a test case declares no `data:` at all. It
# means "this case has no input variables" (a read-only verification, a
# navigation-only UAT step), which is NOT the same defect as "inputs were
# specified badly" - see T1.3 in mech_bands.
NO_DATA_PLACEHOLDER = "-"


def body_section(body, heading):
    """Text under '# <heading>' up to the next '# ' heading, stripped."""
    m = re.search(rf"(?m)^#\s+{re.escape(heading)}\s*$(.*?)(?=^#\s|\Z)",
                  body or "", re.S)
    return (m.group(1).strip() if m else "")


def _data_values(body):
    """The right-hand sides of every '**Field** = value' field in Test Data.

    A single line may carry several fields - `**Amount** = -1 (invalid),
    **Date** = 32/13 (invalid)` is a natural authoring shape, because
    render_sit.py's `data:` key is one free-text string. Anchoring to
    end-of-line would return that whole line as ONE value, which defeats both
    T1.3 (a vague field hides behind a concrete neighbour) and T1.9 (two
    invalid inputs read as one). Both errors run in the flattering direction,
    so each line is split on the field marker first.
    """
    sec = body_section(body, "Test Data")
    if not sec or sec.strip() == NO_DATA_PLACEHOLDER:
        return []
    out = []
    for line in sec.splitlines():
        marks = list(_DATA_FIELD.finditer(line))
        for n, m in enumerate(marks):
            end = marks[n + 1].start() if n + 1 < len(marks) else len(line)
            val = line[m.end():end].strip().rstrip(",").strip()
            if val:
                out.append(val)
    return out


def _no_input_data(body):
    """True when Test Data is the explicit '-' placeholder.

    Distinct from an unparseable section: a section that holds text but yields
    no field value is a malformed test case (band 0), while '-' is a test case
    that correctly declares it has no input variables (NOT ASSESSED).
    """
    sec = body_section(body, "Test Data")
    return sec.strip() == NO_DATA_PLACEHOLDER


def _own_fragments(refs, scope_rel):
    """Fragment ids from `refs` that belong to THIS scope.

    AC, business-rule and journey ids are unique WITHIN a story or flow, not
    globally: /stories/US-A.md#AC1 and /stories/US-B.md#AC1 are two different
    requirements. `_tc_records` admits a test case when ANY of its `covers`
    resolves to this scope, so a multi-story test case brings its foreign refs
    in with it - comparing bare suffixes would let another story's AC1 satisfy
    ours. Filter by concept, not by suffix.

    `scope_rel` None means "do not filter" (the caller has no scope to compare
    against, e.g. a foreign workbook).
    """
    from wiki import resolve_ref
    out = []
    for ref in refs or []:
        rel, frag = resolve_ref(str(ref))
        if frag is None:
            continue
        if scope_rel is not None and rel != scope_rel:
            continue
        out.append(frag)
    return out


def _basis_ids(tc, scope_rel=None):
    """AC, business-rule and journey ids this TC claims IN THIS SCOPE."""
    return (_own_fragments(tc.get("covers"), scope_rel)
            + _own_fragments(tc.get("verifies_rules"), scope_rel))


def mech_bands(tc, ctx):
    """Bands 0-4 for the MECH-scoreable Tier 1 dimensions of one test case.

    Judge-only dimensions (T1.5) are absent from the result entirely - this
    function must never invent a band for something it cannot measure.
    For MECH+JUDGE dimensions the value returned is a CEILING (spec 4).
    """
    body = tc.get("body") or ""
    out = {}

    # ---- T1.1 coverage-item linkage --------------------------------------
    items = list(tc.get("coverage_items") or [])
    if not items:
        out["T1.1"] = 0
    elif any(i not in ctx["model_ids"] for i in items):
        out["T1.1"] = 1
    else:
        out["T1.1"] = 4

    # ---- T1.2 test-basis traceability ------------------------------------
    # A flow's test cases trace to JOURNEY entries, which carry neither an
    # acceptance_criteria nor a business_rules id. wiki.py:232 already treats
    # `journey` as a first-class fragment key (lint L12 validates its refs);
    # omitting it here scored every UAT test case T1.2 = 1 against an empty
    # known set.
    known = ctx["ac_ids"] | ctx["br_ids"] | ctx.get("journey_ids", set())
    basis = _basis_ids(tc, ctx.get("story_rel"))
    if not basis:
        out["T1.2"] = 0
    elif any(b not in known for b in basis):
        out["T1.2"] = 1
    else:
        out["T1.2"] = 4

    # ---- T1.3 input data specificity -------------------------------------
    values = _data_values(body)
    if _no_input_data(body):
        # "No inputs to specify" is not "inputs specified badly". A read-only
        # verification case and a navigation-only UAT step genuinely have no
        # input variables; scoring them 0 = absent collapses the very
        # distinction this rubric exists to keep open.
        out["T1.3"] = NOT_ASSESSED
    elif not values:
        out["T1.3"] = 0
    elif any(v.strip().lower().strip(".") in VAGUE_DATA for v in values):
        out["T1.3"] = 1
    else:
        out["T1.3"] = 4

    # ---- T1.4 expected-result determinacy (ceiling) ----------------------
    out["T1.4"] = 4 if body_section(body, "Expected Results") else 0

    # ---- T1.7 input and state completeness (ceiling) ---------------------
    out["T1.7"] = 4 if body_section(body, "Preconditions") else 1

    # ---- T1.8 technique fit (ceiling) ------------------------------------
    if not items:
        out["T1.8"] = NOT_ASSESSED
    else:
        allowed = ctx["technique_fit"].get(tc.get("technique")) or []
        kinds = [ctx["kind_of"].get(i) for i in items]
        out["T1.8"] = 4 if all(k in allowed for k in kinds) else 1

    # ---- T1.9 one invalid input per negative case ------------------------
    invalid = [v for v in values if _INVALID_MARK.search(v)]
    out["T1.9"] = 4 if len(invalid) <= 1 else 0

    return out


def combine(mech, judge):
    """Final band from a mechanical ceiling and a judge verdict (spec 4).

    band = min(ceiling, judge). A mechanical failure is objective evidence, so
    a judge cannot rate a test case above what the structure allows.

    `judge` is the sentinel string "mech-only" for a dimension no judge scores.
    When a judge IS expected and its verdict is missing, the result is
    NOT_ASSESSED - the ceiling is an upper bound, not a measurement.

    ONE EXCEPTION: a ceiling of 0. `min(0, j) == 0` for every legal band j, so
    a judge cannot change the answer - the evidence is already decided, and a
    ceiling of 0 is therefore a measurement, not merely a bound. Without this,
    a test case with NO expected result at all leaves T1.4 out of both the
    numerator and the denominator and scores the same 100.0 as one that has
    it: the defect the engine just detected costs nothing. Ceilings 1-3 keep
    returning NOT_ASSESSED - there the judge really can still move the band,
    and substituting the bound would score a test case on evidence nobody
    gathered. See spec 4.
    """
    if judge == "mech-only":
        return mech
    if judge is None:
        if isinstance(mech, int) and not isinstance(mech, bool) and mech == 0:
            return 0
        return NOT_ASSESSED
    if not isinstance(mech, int):
        return judge
    return min(mech, judge)


def tier_score(bands, dims):
    """(score 0-100 or None, partial) for one tier.

    NOT ASSESSED dimensions leave both the numerator and the denominator, so
    the score reports what was actually measured. `partial` is True whenever
    a JUDGE dimension was excluded (spec 6.3: a skipped judge run must never
    read as a full score). A MECHANICAL dimension that had nothing to measure
    - T1.3 on a case that declares no inputs, T1.8 on a case naming no items,
    T2.4 on a model with no infeasible item - is excluded silently: no judge
    could ever supply it, so flagging it would make every honest score
    PARTIAL forever and turn --allow-partial into the default.
    """
    num = den = 0
    partial = False
    for d in dims:
        b = bands.get(d["id"])
        if b is None or not isinstance(b, int):
            if "judge" in d.get("scored", ()):
                partial = True
            continue
        num += b * d["weight"]
        den += 4 * d["weight"]
    if not den:
        return None, True
    return round(num / den * 100, 2), partial


def scope_score(t1, t2, blend):
    """Blended scope score. A tier that measured nothing is dropped and the
    other carries full weight, rather than being counted as zero."""
    parts = [(t1, blend.get("tier1", 40)), (t2, blend.get("tier2", 60))]
    live = [(v, w) for v, w in parts if v is not None]
    if not live:
        return None
    total_w = sum(w for _v, w in live)
    return round(sum(v * w for v, w in live) / total_w, 2)


def _tc_records(concepts, story_rel, kind=None):
    """(fm, body) for every ACTIVE test case generated from `story_rel`.

    `generated_from` (written by render_sit.py) carries prd_version,
    figma_hashes, wiki_commit and generator_version - NOT a story ref. Story
    membership is instead read the way tools/wiki_suite.py already does it
    (see _subgroup_of/tc_sort_key there): resolve every `covers` ref and match
    its concept path against the scope. Retired TCs are excluded: a retired
    scenario is not part of the set being measured, and counting it would drag
    the score down for work correctly withdrawn.

    `kind` ('sit' for a story, 'uat' for a flow) keeps only test cases of
    that kind, the rule wiki_rubric.scope_tc_rels applies for export, --diff
    and `wiki next`: a story's set must not move when its flow's UAT chain
    is re-rendered. A test case without a `kind` key is kept (legacy
    fixtures); kind=None keeps every kind.
    """
    from wiki import resolve_ref
    out = []
    for _rel, (fm, body, _p) in sorted(concepts.items()):
        if not fm or fm.get("type") != "Test Case":
            continue
        if fm.get("status") == "retired":
            continue
        if kind and fm.get("kind") not in (kind, None):
            continue
        covers = fm.get("covers") or []
        if story_rel and not any(
                resolve_ref(ref)[0] == story_rel for ref in covers):
            continue
        rec = dict(fm)
        rec["body"] = body or ""
        rec["rel"] = _rel
        out.append(rec)
    return out


_KIND_DIR = {"story": "stories", "flow": "flows"}


def score_scope(kind, scope_id, judgments=None, load_all=None,
                scope_judgments=None):
    """Score one story or flow. `kind` is 'story' or 'flow' - the same
    contract cmd_gate (tools/wiki.py:1355-1372) uses to turn a bare CLI id
    into a concept key: `f"{kind}s/{scope_id}"`, not resolve_ref(scope_id).

    resolve_ref is for ref STRINGS that already carry a directory (its own
    docstring example is '/stories/US-x.md#AC-1'); a bare CLI id like
    'US-1.2.3.4' has no directory for it to strip, so resolve_ref(scope_id)
    returns scope_id unchanged - never a key load_all() actually has.

    `load_all` defaults to wiki.load_all; tests inject a synthetic
    (concepts, manifest) pair here instead of monkeypatching the module.
    """
    from rubric import dimensions, load_rubric, rubric_hash
    from wiki import load_all as _real_load_all, load_config
    from wiki_rubric import (coverage_by_technique, load_test_model,
                             model_warnings, sealed_digest, unknown_item_refs,
                             validate_test_model)
    load_all = load_all or _real_load_all

    cfg = (load_config().get("rubric") or {})
    version = cfg.get("version", "v1")
    rub = load_rubric(version)
    concepts, manifest = load_all()
    tc_hashes = (manifest or {}).get("tc_hashes") or {}

    rel = f"{_KIND_DIR[kind]}/{scope_id}"
    if rel not in concepts:
        sys.exit(f"eval_rubric: no concept for {scope_id!r}")
    fm, _body, _p = concepts[rel]

    items, status = load_test_model(fm)

    # The model is hand-authored YAML that nothing else enforces yet, so
    # malformed input is the EXPECTED case during migration. Validate before
    # consuming it: without this, a bare-string item raises AttributeError and
    # an item missing `technique` puts a None key into the coverage dict and
    # then blows up inside json.dumps(sort_keys=True). A raw traceback is not
    # a refusal.
    model_errs = validate_test_model(fm, scope_id)
    if model_errs:
        detail = "\n".join(f"    - {e}" for e in model_errs)
        sys.exit(
            f"eval_rubric REFUSED: {scope_id} test_model is not valid.\n"
            f"{detail}\n"
            f"  A malformed model cannot be scored: every Tier 2 denominator\n"
            f"  is read from it, so guessing past a broken item would produce\n"
            f"  a number with nothing behind it.\n"
            f"  Next: fix the test_model block in {rel}.md, then re-run.")

    if status != "confirmed":
        sys.exit(
            f"eval_rubric REFUSED: {scope_id} test_model status is "
            f"'{status or 'absent'}', not 'confirmed'.\n"
            f"  Tier 2 has no denominator without an asserted test model, and\n"
            f"  a proposed model is the agent's guess, not the human's answer.\n"
            f"  Next: propose the model on the coverage card, then\n"
            f"        py tools/wiki.py assert story {scope_id} --by <user>")

    if not items:
        # A confirmed-but-empty model is worse than an absent one: it looks
        # asserted, so nothing refuses it, and T2.1/T2.4/T2.7 all fall out of
        # the denominator - leaving Tier 2 carried entirely by T2.2, the one
        # check this platform already had before the rubric existed. The whole
        # 29119-4 contribution evaporates and the score goes UP.
        sys.exit(
            f"eval_rubric REFUSED: {scope_id} test_model is confirmed but "
            f"identifies no coverage items.\n"
            f"  Tier 2 has no denominator: with items: [] every per-technique\n"
            f"  C is undefined, so the scope would be scored on requirements\n"
            f"  coverage alone and read as a clean, complete number.\n"
            f"  Next: propose the coverage items on the coverage card, then\n"
            f"        py tools/wiki.py assert {kind} {scope_id} --by <user>")

    from wiki_rubric import SCOPE_TC_KIND
    tcs = _tc_records(concepts, rel, kind=SCOPE_TC_KIND[kind])
    covered = set()
    for tc in tcs:
        covered.update(tc.get("coverage_items") or [])

    ctx = {
        "model_ids": {i.get("id") for i in items},
        "ac_ids": {a.get("id") for a in fm.get("acceptance_criteria") or []},
        "br_ids": {r.get("id") for r in fm.get("business_rules") or []},
        # A flow has no ACs and no business rules - its test basis is the
        # asserted journey (wiki.py fragment_ids treats `journey` the same way).
        "journey_ids": {j.get("id") for j in fm.get("journey") or []
                        if isinstance(j, dict)},
        "story_rel": rel,
        "technique_fit": rub.get("technique_fit") or {},
        "kind_of": {i.get("id"): i.get("kind") for i in items},
    }

    judgments = judgments or {}
    scope_judgments = scope_judgments or {}
    t1_dims = dimensions(rub, tier=1)
    per_tc = []
    mech_by_tc = {}
    for tc in tcs:
        mech = mech_bands(tc, ctx)
        mech_by_tc[tc.get("id")] = mech
        bands = {}
        for d in t1_dims:
            takes_judge = "judge" in d["scored"]
            verdict = (judgments.get(tc.get("id"), {}).get(d["id"])
                       if takes_judge else "mech-only")
            ceiling = mech.get(d["id"])
            if ceiling is None and not takes_judge:
                continue
            bands[d["id"]] = combine(ceiling, verdict)
        score, partial = tier_score(bands, t1_dims)
        per_tc.append({"id": tc.get("id"), "bands": bands,
                       "score": score, "partial": partial,
                       "sealed_hash": tc_hashes.get(tc.get("rel"))})

    cov = coverage_by_technique(
        items, covered, count_infeasible=bool(cfg.get("count_infeasible")))
    t1_scores = [r["score"] for r in per_tc if r["score"] is not None]
    tier1 = round(sum(t1_scores) / len(t1_scores), 2) if t1_scores else None

    # Tier 2 bands: T2.1/T2.2/T2.4/T2.7 from the arithmetic above; T2.5 and
    # T2.6 take a judge verdict from lens D (tools/rubric_judge.py), capped by
    # the mechanical ceiling where one exists. No verdict -> NOT ASSESSED.
    from rubric_judge import t25_ceiling
    warnings = model_warnings(items)
    t2_bands = {}
    t2_bands["T2.1"] = _t21_band(cov, warnings)
    t2_bands["T2.2"] = _band_from_pct(_ac_coverage_pct(fm, tcs, rel))
    t2_bands["T2.4"] = _t24_band(items)
    t25 = t25_ceiling(tcs)
    t2_bands["T2.5"] = combine(t25, scope_judgments.get("T2.5"))
    t2_bands["T2.6"] = combine(None, scope_judgments.get("T2.6"))
    t2_bands["T2.7"] = _redundancy_band(tcs)
    tier2, t2_partial = tier_score(t2_bands, dimensions(rub, tier=2))

    if _tier2_is_vacuous(t2_bands):
        tier2, t2_partial = None, True

    blend = cfg.get("blend") or {"tier1": 40, "tier2": 60}
    overall = scope_score(tier1, tier2, blend)
    partial = t2_partial or any(r["partial"] for r in per_tc)

    return {
        "scope": scope_id,
        "rubric_version": version,
        "rubric_hash": rubric_hash(version),
        "standard": rub.get("standard"),
        "score": overall,
        "tier1": tier1,
        "tier2": tier2,
        "partial": partial,
        "threshold": cfg.get("threshold", 70),
        "coverage": cov,
        "model_warnings": warnings,
        "unknown_item_refs": unknown_item_refs(items, covered),
        "tier2_bands": t2_bands,
        "t25_ceiling": t25,
        "test_cases": per_tc,
        "sealed_digest": sealed_digest(
            tc_hashes, [t["rel"] for t in tcs if t.get("status") == "active"]),
        # Not serialised by main(): the packs and the gap report read these.
        "_tcs": tcs,
        "_fm": fm,
        "_rub": rub,
        "_mech_by_tc": mech_by_tc,
        "_tc_hashes": tc_hashes,
    }


def _band_from_pct(pct):
    """A percentage to a 0-4 band. None stays NOT ASSESSED."""
    if pct is None:
        return NOT_ASSESSED
    for cut, band in ((100, 4), (90, 3), (75, 2), (50, 1)):
        if pct >= cut:
            return band
    return 0


def _ac_coverage_pct(fm, tcs, scope_rel=None):
    """29119-4 6.2.12: atomic requirements covered / atomic requirements.

    VOIDED ACs are excluded from the denominator. The rubric's own obligation
    says "every ACTIVE acceptance criterion", and voiding an AC cascades its
    test cases to retired (wiki_lifecycle.cmd_void_ac), which `_tc_records`
    correctly drops - so counting the AC would permanently lower T2.2 with no
    possible remedy.

    Only refs that resolve to THIS scope count. AC ids are per-story, so a
    multi-story test case's /stories/US-OTHER.md#AC1 must not satisfy our AC1.
    """
    acs = {a.get("id") for a in fm.get("acceptance_criteria") or []
           if isinstance(a, dict) and a.get("status") != "voided"}
    if not acs:
        return None
    hit = set()
    for tc in tcs:
        hit.update(_own_fragments(tc.get("covers"), scope_rel))
    return len(acs & hit) / len(acs) * 100


# Tier 2 dimensions whose value is read from the test model. T2.2 is not one
# of them: it is scored from the story's ACs and would still produce a number
# with no model at all.
_MODEL_DEPENDENT_T2 = ("T2.1", "T2.4", "T2.7")


def _tier2_is_vacuous(t2_bands):
    """True when NOTHING read from the test model was measured.

    Tier 2 would then be T2.2 alone wearing Tier 2's name, published as a
    clean number: the entire 29119-4 contribution gone, and the score carried
    by the one requirements-coverage check this platform already had before
    the rubric existed. Reporting `tier2: None` says so instead.

    A confirmed model with `items: []` is the common cause and `score_scope`
    refuses it outright; this is the independent guard for every other route
    to the same emptiness.
    """
    return all(not isinstance(t2_bands.get(d), int)
               for d in _MODEL_DEPENDENT_T2)

# Highest band T2.1 may reach when the model itself is flagged incomplete.
# Band 2 is "adequate" - the highest band that does not assert the coverage is
# good. You cannot claim good coverage of a model that omits the scenarios
# most likely to fail, and the size of what it omits is unknown, so the cap is
# a ceiling on the claim rather than a penalty proportional to nothing.
T21_INCOMPLETE_MODEL_CAP = 2


def _t21_band(cov, warnings):
    """Band for per-technique coverage C = (N/T) x 100 (29119-4 6.1).

    The percentage fed to the band is the UNWEIGHTED MEAN of each technique's
    C. This is a deliberate choice, and it has a cost: a technique with one
    trivially covered item offsets a technique with twenty uncovered
    boundaries, because both contribute one term. The alternative - pooling N
    and T across techniques - makes the technique with the most coverage items
    dominate the score, which would let a large EP model bury a wholly
    uncovered ST model. 6.1 defines C per technique, so the per-technique
    figure is the one the standard actually specifies; averaging them keeps
    every technique visible and keeps the reported `coverage` rows (which are
    per technique) reconcilable with the band. Techniques whose C is undefined
    (T == 0) contribute nothing either way.

    A model that `model_warnings` flags as incomplete is CAPPED. A flow whose
    model is the main scenario only scores C = 1/1 = 100% on a model that is
    itself incomplete; spec 5.1 says that must not be silently rounded up to a
    clean 100%. The warning alone touched no band, so the letter was satisfied
    and the score was not.
    """
    live = [r["C"] for r in cov.values() if r["C"] is not None]
    band = _band_from_pct(sum(live) / len(live) if live else None)
    if warnings and isinstance(band, int):
        return min(band, T21_INCOMPLETE_MODEL_CAP)
    return band


def _t24_band(items):
    """29119-4 6.1: a discounted (feasible: false) coverage item must carry a
    non-empty justification. `validate_test_model` is not wired into `wiki
    lint` yet (a later task), so this is the only place that actually checks
    the claim for a T2.4 score - it must not be a constant.

    NOT ASSESSED when the model has no feasible: false items: there is
    nothing to discount and nothing for this dimension to judge, so it stays
    unmeasured rather than reporting a trivial exemplary.
    """
    infeasible = [i for i in items if isinstance(i, dict)
                  and i.get("feasible") is False]
    if not infeasible:
        return NOT_ASSESSED
    if all(str(i.get("justification") or "").strip() for i in infeasible):
        return 4
    return 0


def _redundancy_band(tcs):
    """A TC whose coverage-item set duplicates another's adds nothing to N."""
    seen, dupes = set(), 0
    for tc in tcs:
        key = tuple(sorted(tc.get("coverage_items") or []))
        if not key:
            continue
        if key in seen:
            dupes += 1
        seen.add(key)
    if not seen:
        return NOT_ASSESSED
    return _band_from_pct((1 - dupes / (len(seen) + dupes)) * 100)


def main(argv=None):
    import json
    from wiki import ROOT, arg_after
    from rubric_judge import (LENSES, apply_patch, carried_counts, carry_forward,
                              load_judgments, refuse_if_packed_changed,
                              round_delta, score_path, write_gaps, write_packed,
                              write_packs)
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv or "--help" in argv:
        print("usage: py tools/eval_rubric.py --story <ID> | --flow <ID> "
              "[--round N] [--pack] [--strict [--allow-partial]]\n"
              "       py tools/eval_rubric.py --story <ID> --apply-patch "
              "build/rubric/<ID>-r1-patch.json\n"
              "       py tools/eval_rubric.py --story <ID> --diff        "
              "(draft snapshot -> current sealed set)\n"
              "  --round N       which round's judgments to merge (default 1);\n"
              "                  writes <ID>-rN-score.json + <ID>-rN-gaps.md and,\n"
              "                  for N >= 2, the round-over-round delta\n"
              "  --pack          also write one judge pack per lens under\n"
              "                  build/rubric/packs/ (what each judge reads) and\n"
              "                  <ID>-rN-packed.json; a later merge of round N\n"
              "                  refuses if the sealed set moved since\n"
              "  --apply-patch   apply an improver patch to the sit_spec and stop")
        return 0
    kind = scope = None
    for k, flag in (("story", "--story"), ("flow", "--flow")):
        if flag in argv:
            kind, scope = k, arg_after(argv, flag)
    if not scope:
        sys.exit("eval_rubric: one of --story or --flow is required")
    rnd = int(arg_after(argv, "--round")) if "--round" in argv else 1
    if rnd < 1:
        sys.exit("eval_rubric: --round must be 1 or more")

    if "--diff" in argv:
        from rubric_judge import (changes_path, draft_path, patch_path,
                                  patch_tc_index, rubric_state, write_changes)
        from rubric_judge import load_json_object
        from wiki import load_all, load_config
        from wiki_rubric import (SCOPE_TC_KIND, scope_tc_rels, sealed_digest,
                                 tc_record)
        dp = draft_path(scope)
        if not dp.exists():
            sys.exit(f"eval_rubric --diff refused: no draft snapshot for {scope}.\n"
                     f"  A diff needs a 'from' side - the draft export writes it.\n"
                     f"  Next: py tools/wiki.py export --{kind} {scope} --name <n> --draft")
        snapshot = load_json_object(dp, "draft snapshot")
        concepts, manifest = load_all()
        rel = f"{_KIND_DIR[kind]}/{scope}"
        if rel not in concepts:
            sys.exit(f"eval_rubric: no concept for {scope!r}")
        tc_hashes = manifest.get("tc_hashes") or {}
        tc_kind = SCOPE_TC_KIND[kind]
        current = {}
        for crel in scope_tc_rels(concepts, rel, tc_kind, active_only=False):
            fm, body = concepts[crel][0], concepts[crel][1]
            current[fm["id"]] = tc_record(crel, fm, body, tc_hashes)
        digest = sealed_digest(tc_hashes, scope_tc_rels(concepts, rel, tc_kind))
        cfg = load_config()
        rc = cfg.get("rubric") or {}
        state = rubric_state(scope, digest, rc.get("threshold", 70), rc.get("version", "v1"))
        pp = patch_path(scope, 1)
        patch = json.loads(pp.read_text(encoding="utf-8")) if pp.exists() else None
        jp, mp = write_changes(scope, kind, snapshot, current, state,
                               patch_tc_index(scope, kind, patch, cfg), digest,
                               rc.get("threshold", 70), rc.get("version", "v1"))
        doc = json.loads(jp.read_text(encoding="utf-8"))
        c = doc["counts"]
        print(f"{scope}: {c['added']} added, {c['changed']} changed, "
              f"{c['removed']} removed, {c['unchanged']} unchanged "
              f"(draft r0 -> {doc['to']['label']})")
        print(f"  -> {mp.relative_to(ROOT).as_posix()}\n  -> {jp.relative_to(ROOT).as_posix()}")
        if state["current"] is None:
            print("  NOTE: no current strict score on this sealed set - the final "
                  "export will refuse until one exists")
        return 0

    if "--apply-patch" in argv:
        if kind != "story":
            sys.exit("eval_rubric --apply-patch: only SIT specs "
                     "(tools/sit_specs/<STORY>.yaml) are patchable; a flow's "
                     "UAT chain is re-rendered from its journey")
        spec_path = ROOT / "tools/sit_specs" / f"{scope}.yaml"
        if not spec_path.exists():
            sys.exit(f"eval_rubric --apply-patch: no spec at "
                     f"{spec_path.relative_to(ROOT).as_posix()}")
        pf = Path(arg_after(argv, "--apply-patch"))
        if not pf.is_absolute():
            pf = ROOT / pf
        if not pf.exists():
            sys.exit(f"eval_rubric --apply-patch: patch not found: {pf}")
        n, errs = apply_patch(spec_path, pf)
        if errs:
            detail = "\n".join(f"    - {e}" for e in errs)
            sys.exit(f"eval_rubric --apply-patch REFUSED (nothing written):\n"
                     f"{detail}")
        print(f"applied {n} patch(es) to "
              f"{spec_path.relative_to(ROOT).as_posix()}\n"
              f"  Next: py tools/render_sit.py --story {scope} --force && "
              f"(--force: a spec edit does not move the pinned AC fragments, "
              f"so an unforced render skips every file)\n        "
              f"py tools/wiki.py seal\n"
              f"        py tools/eval_rubric.py --story {scope} --round "
              f"{rnd + 1} --pack")
        return 0

    # First pass without verdicts: the TC id set and rubric hash gate which
    # verdict files are even admissible.
    from rubric import dimensions, load_rubric
    base = score_scope(kind, scope)
    # A stubbed score_scope (tests) may omit the private carriers.
    rub = base.get("_rub") or load_rubric(base.get("rubric_version", "v1"))
    judge_dims = {d["id"] for d in dimensions(rub) if "judge" in d["scored"]}
    tc_ids = [tc.get("id") for tc in base.get("_tcs") or []]
    tc_hashes = base.get("_tc_hashes") or {}
    current_hashes = {tc.get("id"): tc_hashes.get(tc.get("rel"))
                      for tc in base.get("_tcs") or []}
    carried = {}
    if "--pack" not in argv:
        # Bind verdicts to the content the judges read: a merge on a set
        # that moved since `--round N --pack` refuses (no packed file, as in
        # rounds packed before this check existed, skips it).
        refuse_if_packed_changed(scope, rnd, f"--{kind}", current_hashes)
    if "--pack" in argv and rnd >= 2:
        carried = carry_forward(scope, rnd, base.get("_tcs") or [], tc_hashes,
                                base["rubric_hash"], judge_dims)
    per_tc, per_scope, notes, present = load_judgments(
        scope, rnd, base["rubric_hash"], tc_ids, judge_dims,
        current_hashes=current_hashes)
    result = (score_scope(kind, scope, judgments=per_tc,
                          scope_judgments=per_scope)
              if (per_tc or per_scope) else base)
    result["round"] = rnd
    result["judges_present"] = sorted(present)
    result["judges_missing"] = sorted(set(LENSES) - present)
    result["carried"] = carried_counts(notes)

    outdir = ROOT / "build/rubric"
    outdir.mkdir(parents=True, exist_ok=True)
    public = {k: v for k, v in result.items() if not k.startswith("_")}
    payload = json.dumps(public, indent=2, sort_keys=True) + "\n"
    out_r = score_path(scope, rnd)
    out_r.write_text(payload, encoding="utf-8")
    score_path(scope).write_text(payload, encoding="utf-8")

    flag = " (PARTIAL - some dimensions NOT ASSESSED)" if result["partial"] else ""
    print(f"{scope}: round {rnd} score {result['score']}{flag}")
    print(f"  tier1 {result['tier1']}  tier2 {result['tier2']}")
    for tech, row in sorted(result["coverage"].items()):
        c = "undefined" if row["C"] is None else f"{row['C']}%"
        print(f"  {tech}: C = {row['N']}/{row['T']} = {c}")
    for w in result["model_warnings"]:
        print(f"  WARNING {w}")
    # A test case naming a coverage item the model does not define is an
    # integrity failure; printing coverage but not this hid it from the
    # operator, who sees the CLI and not the JSON.
    for ref in result["unknown_item_refs"]:
        print(f"  UNKNOWN COVERAGE ITEM {ref} - named by a test case but not "
              f"defined in the test model")
    if result["judges_missing"]:
        print(f"  judges missing for round {rnd}: "
              f"{', '.join(result['judges_missing'])} -> their dimensions are "
              f"NOT ASSESSED (run the lenses from build/rubric/packs/)")
    if result["carried"]:
        print("  carried forward: " + ", ".join(
            f"{lens} {n}" for lens, n in sorted(result["carried"].items()))
              + f" test case(s) unchanged since round {rnd - 1}")
    print(f"  -> {out_r.relative_to(ROOT).as_posix()}")

    tcs = result.get("_tcs") or []
    fm = result.get("_fm") or {}
    mech_by_tc = result.get("_mech_by_tc") or {}
    gp = write_gaps(result, tcs, fm, notes, rnd, mech_by_tc)
    print(f"  -> {gp.relative_to(ROOT).as_posix()}")
    if "--pack" in argv:
        for pth in write_packs(result, tcs, fm, result.get("_rub") or rub,
                               rnd, mech_by_tc, exclude=carried):
            print(f"  -> {pth.relative_to(ROOT).as_posix()}")
        pp = write_packed(scope, rnd, result.get("sealed_digest"), current_hashes)
        print(f"  -> {pp.relative_to(ROOT).as_posix()}  (the merge refuses if "
              f"the sealed set moves before it)")

    delta = round_delta(scope, rnd)
    if delta:
        (outdir / f"{scope}-r{rnd}-delta.json").write_text(
            json.dumps(delta, indent=2, sort_keys=True) + "\n",
            encoding="utf-8")
        if not delta["same_rubric"]:
            print("  DELTA not comparable: rounds were scored under different "
                  "rubric hashes")
        elif delta["regression"]:
            print(f"  REGRESSION round {delta['from_round']} -> "
                  f"{delta['to_round']}: {delta['from']} -> {delta['to']} "
                  f"({delta['delta']}). Keep round {delta['from_round']}'s "
                  f"spec (spec 7.3).")
        else:
            print(f"  delta round {delta['from_round']} -> {delta['to_round']}: "
                  f"{delta['from']} -> {delta['to']} (+{delta['delta']})")

    if "--strict" in argv:
        if result["partial"] and "--allow-partial" not in argv:
            # Gating on a partial score passes a set on whichever dimensions
            # happened to be measurable, so `--strict` would compare part of
            # a rubric against the full threshold without saying so.
            sys.exit(
                f"eval_rubric --strict REFUSED: {scope} scored "
                f"{result['score']}, but that score is PARTIAL.\n"
                f"  Some dimensions were NOT ASSESSED and left the denominator\n"
                f"  entirely, so the number is not comparable to the "
                f"threshold of {result['threshold']}.\n"
                f"  Judges missing: {', '.join(result['judges_missing']) or 'none'}"
                f" - run every lens, or\n"
                f"  Next: py tools/eval_rubric.py --{kind} {scope} --strict "
                f"--allow-partial\n"
                f"        to gate on the partial score deliberately.")
        s = result["score"]
        if s is None or s < result["threshold"]:
            sys.exit(f"eval_rubric --strict: {scope} scored {s}, "
                     f"threshold is {result['threshold']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
