#!/usr/bin/env python3
"""The test-model artifact and the coverage arithmetic over it.

29119-4 defines every technique in three steps: TD1 create test model, TD2
identify test coverage items, TD3 derive test cases. tc-copilot had TD3 (the
rendered test cases) and no TD1, which left coverage measurement with no
denominator. This module supplies TD1/TD2 as an asserted artifact.

The model is PROPOSED by the agent and ASSERTED by the human on the existing
coverage card - there is no second gate (spec 5).
"""
# Kinds of test coverage item, one per technique family that this platform
# generates for. Structure-based kinds (statement, branch, MCDC) are out of
# scope: they need source code, and this platform works from requirements.
KINDS = {"partition", "boundary", "transition", "rule", "pair", "scenario"}
TECHNIQUES = {"UC", "EP", "BVA", "DT", "ST", "ERR", "PW"}
STATUSES = {"proposed", "confirmed"}
ROLES = {"main", "alternative"}

ITEM_REQUIRED = ("id", "technique", "kind", "basis", "feasible")


def load_test_model(fm):
    """(items, status) from a story/flow frontmatter. ([], None) when absent."""
    tm = (fm or {}).get("test_model")
    if not isinstance(tm, dict):
        return [], None
    items = tm.get("items")
    return (list(items) if isinstance(items, list) else []), tm.get("status")


def validate_test_model(fm, scope_id):
    """Pure structural validation of a scope's test_model. Error strings.

    An ABSENT test_model is not an error: it means the scope has not been
    migrated yet, and the engine refuses on it at its own boundary. Failing
    lint here would break every unmigrated story on a project branch.
    """
    fm = fm or {}
    tm = fm.get("test_model")
    if tm is None:
        return []
    errs = []
    if not isinstance(tm, dict):
        return [f"{scope_id}: test_model must be a mapping, "
                f"got {type(tm).__name__}"]

    status = tm.get("status")
    if status not in STATUSES:
        errs.append(f"{scope_id}: test_model status {status!r} must be one of "
                    f"{sorted(STATUSES)}")

    items = tm.get("items")
    if not isinstance(items, list):
        errs.append(f"{scope_id}: test_model items must be a list")
        return errs

    ac_ids = {a.get("id") for a in fm.get("acceptance_criteria") or []
              if isinstance(a, dict)}
    br_ids = {r.get("id") for r in fm.get("business_rules") or []
              if isinstance(r, dict)}
    # A FLOW's test basis is its journey: a flow carries no acceptance_criteria
    # and no business_rules at all, so a known set built from those two alone
    # is empty and rejects every legal journey ref - including the canonical
    # UAT scenario model in spec 5.1. wiki.py fragment_ids already treats
    # `journey` as a first-class fragment key and lint L12 validates its refs.
    journey_ids = {j.get("id") for j in fm.get("journey") or []
                   if isinstance(j, dict)}
    known = ac_ids | br_ids | journey_ids

    seen = set()
    mains = 0
    for i, it in enumerate(items):
        if not isinstance(it, dict):
            errs.append(f"{scope_id}: test_model items[{i}] must be a mapping")
            continue
        iid = it.get("id")
        where = f"{scope_id}: test_model item {iid or f'[{i}]'}"
        for k in ITEM_REQUIRED:
            if k not in it:
                errs.append(f"{where}: missing required key '{k}'")
        # `iid` is None when 'id' is missing, which the loop above already
        # reported. Keying duplicate detection on None would add a spurious
        # "duplicate id 'None'" beside the real error on the second such item.
        if iid is not None:
            if iid in seen:
                errs.append(f"{scope_id}: duplicate test_model item id {iid!r}")
            seen.add(iid)

        if it.get("technique") not in TECHNIQUES:
            errs.append(f"{where}: technique {it.get('technique')!r} not one of "
                        f"{sorted(TECHNIQUES)}")
        if it.get("kind") not in KINDS:
            errs.append(f"{where}: kind {it.get('kind')!r} not one of "
                        f"{sorted(KINDS)}")

        basis = it.get("basis")
        if not isinstance(basis, list) or not basis:
            errs.append(f"{where}: basis must be a non-empty list of AC or "
                        f"business-rule ids")
        else:
            for b in basis:
                if b not in known:
                    errs.append(f"{where}: basis {b!r} is neither an AC nor a "
                                f"business rule nor a journey entry of "
                                f"{scope_id}")

        feasible = it.get("feasible")
        if not isinstance(feasible, bool):
            errs.append(f"{where}: feasible must be true or false, "
                        f"got {feasible!r}")
        elif feasible is False:
            # 29119-4 6.1: a discounted coverage item's justification is
            # recorded. Silently dropping one inflates C.
            j = it.get("justification")
            if not (isinstance(j, str) and j.strip()):
                errs.append(f"{where}: feasible: false requires a non-empty "
                            f"justification (29119-4 6.1)")

        role = it.get("role")
        if role is not None:
            if role not in ROLES:
                errs.append(f"{where}: role {role!r} must be one of "
                            f"{sorted(ROLES)}")
            elif role == "main":
                mains += 1

    if mains > 1:
        errs.append(f"{scope_id}: test_model has more than one item with "
                    f"role: main - 29119-4 5.2.9.1 identifies one main scenario")
    return errs


def model_warnings(items):
    """Non-fatal warnings about the MODEL itself, not about the test cases.

    A scenario model with a main scenario and no alternatives is incomplete
    (29119-4 5.2.9.1 requires both). Left unflagged it would score C = 1/1 =
    100% and read as fully covered.
    """
    scenarios = [i for i in items
                 if isinstance(i, dict) and i.get("kind") == "scenario"]
    # Only a FLOW-style scenario model declares a main scenario (5.2.9.1). A
    # story's model carries one un-roled scenario per acceptance criterion,
    # and its exception paths are separate ACs - it is not "main only".
    if not any(s.get("role") == "main" for s in scenarios):
        return []
    if not any(s.get("role") == "alternative" for s in scenarios):
        return ["INCOMPLETE MODEL - main scenario only; 29119-4 5.2.9.1 also "
                "requires alternative scenarios (abnormal use, exceptions, "
                "error handling)"]
    return []


def _feasible(item, count_infeasible):
    return count_infeasible or item.get("feasible") is not False


def coverage_by_technique(items, covered_ids, count_infeasible=False):
    """C = (N / T) x 100 per technique (29119-4 6.1).

    N: coverage items of that technique covered by at least one test case.
    T: coverage items of that technique identified by the model.

    Infeasible items are discounted from T by default. 6.1 requires the choice
    between counting and discounting to be DEFINED; discounting is what makes
    100% an achievable target (Annex F). A covered-but-discounted item does not
    count toward N either - it is outside the measurement entirely.

    C is None when T == 0. Undefined coverage must never render as 0% or 100%.
    """
    covered = set(covered_ids)
    out = {}
    for it in items:
        if not isinstance(it, dict):
            continue
        tech = it.get("technique")
        iid = it.get("id")
        row = out.setdefault(tech, {"N": 0, "T": 0, "C": None, "covered": [],
                                    "uncovered": [], "discounted": []})
        if not _feasible(it, count_infeasible):
            row["discounted"].append(iid)
            continue
        row["T"] += 1
        if iid in covered:
            row["N"] += 1
            row["covered"].append(iid)
        else:
            row["uncovered"].append(iid)
    for row in out.values():
        row["C"] = round(row["N"] / row["T"] * 100, 2) if row["T"] else None
    return out


def unknown_item_refs(items, covered_ids):
    """Coverage-item ids named by test cases that the model does not define.

    Sorted for determinism: the same inputs must produce the same report.
    """
    known = {i.get("id") for i in items if isinstance(i, dict)}
    return sorted(set(covered_ids) - known)


# ------------------------------------------------ sealed digest + records
import hashlib
import re

# Frontmatter fields the draft -> final diff compares (spec 4.4). Body
# sections are compared by heading and need no listing here.
DIFF_FIELDS = ("title", "technique", "priority", "coverage_items", "covers",
               "verifies_rules")

_HEADING_SPLIT = re.compile(r"^# (.+?)[ \t]*$", re.MULTILINE)


def sealed_digest(tc_hashes, rels):
    """One hash over a scope's sealed test cases: sorted '<rel> <hash>' lines.
    Same active files with the same content -> same digest. Recorded in every
    score JSON, the draft snapshot and the changes file, and compared by
    export, --diff and `wiki next` (spec 5.3). ACTIVE rels only, by contract
    of every caller."""
    lines = sorted(f"{rel} {tc_hashes.get(rel) or ''}" for rel in rels)
    return "sha256:" + hashlib.sha256("\n".join(lines).encode("utf-8")).hexdigest()


def tc_record(rel, fm, body, tc_hashes):
    """The diffable view of one rendered test case (spec 5.1). `sections`
    holds every `# Heading` of the body verbatim, so the diff never hardcodes
    the section list."""
    fm = fm or {}
    parts = _HEADING_SPLIT.split(body or "")
    sections = {parts[i].strip(): parts[i + 1].strip()
                for i in range(1, len(parts) - 1, 2)}
    return {"id": fm.get("id"), "rel": rel, "hash": tc_hashes.get(rel),
            "status": fm.get("status"),
            "retirement_reason": (fm.get("retirement") or {}).get("reason"),
            "title": fm.get("title") or "",
            "technique": fm.get("technique"), "priority": fm.get("priority"),
            "coverage_items": list(fm.get("coverage_items") or []),
            "covers": list(fm.get("covers") or []),
            "verifies_rules": list(fm.get("verifies_rules") or []),
            "sections": sections}


def active_rels_from_manifest(manifest, scope_rel):
    """Active test-case rels covering `scope_rel`, from the manifest alone
    (no concept read) - the same walk story_tc_stats in wiki.py does."""
    out = []
    for rel, entry in (manifest.get("concepts") or {}).items():
        if not rel.startswith("testcases/") or entry.get("status") != "active":
            continue
        if any(s == rel and k == "covers" and str(t).startswith(scope_rel + "#")
               for s, k, t in manifest.get("edges") or []):
            out.append(rel)
    return sorted(out)


# A story scope is its SIT test cases; a flow scope is its UAT test cases.
SCOPE_TC_KIND = {"story": "sit", "flow": "uat"}


def scope_tc_rels(concepts, scope_rel, kind, active_only=True):
    """Sorted rels of the test cases of `scope_rel` read from the concept
    files: `type: Test Case`, a `covers` ref resolving to `scope_rel`, and
    `kind` equal to `kind` ('sit' for a story, 'uat' for a flow; a test case
    without a `kind` is kept for legacy fixtures). ACTIVE only unless
    `active_only=False` (the diff needs retired cases to report them).

    The ONE selector export, `--diff` and `wiki next` share, so their
    digests agree - and agree with the rubric's own set (eval_rubric
    `_tc_records` applies the same kind rule). `concepts` values are
    (fm, body[, path]) tuples."""
    from wiki import resolve_ref
    out = []
    for rel, entry in concepts.items():
        fm = entry[0]
        if not fm or fm.get("type") != "Test Case":
            continue
        if active_only and fm.get("status") != "active":
            continue
        if fm.get("kind") not in (kind, None):
            continue
        if any(resolve_ref(c)[0] == scope_rel for c in fm.get("covers") or []):
            out.append(rel)
    return sorted(out)
