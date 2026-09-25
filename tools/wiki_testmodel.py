#!/usr/bin/env python3
"""`wiki testmodel` - propose and show a scope's 29119-4 test model.

    py tools/wiki.py testmodel --story <id> --propose [--force]
    py tools/wiki.py testmodel --flow  <id> --propose [--force]
    py tools/wiki.py testmodel --story <id>            # show + coverage

The proposal is a deterministic SCAFFOLD, in the spirit of `coverage
--propose`: it writes `test_model: {status: proposed, items: [...]}` from what
the frontmatter already states, and expects the agent to correct and enrich
it on the coverage card before the human confirms. It never sets `confirmed`
- `wiki assert story|flow --card <coverage card carrying test_model>` does
that, and only at a human's instruction.

Heuristics (all cite where the item came from, so a reviewer can delete
what does not belong):
  UC   one `scenario` item per active acceptance criterion    (5.2.9)
  DT   one `rule` item per business rule                       (5.2.6)
  BVA  one `boundary` item per AC whose text states a bound   (5.2.3)
  EP   one `partition` item per AC whose text enumerates
       permitted values or an exclusive set                    (5.2.2)
  ST   one `transition` item per AC whose text is a state
       change (clear / restore / persist / while ... until)    (5.2.7)
For a flow: SC-MAIN over the whole journey (5.2.9.1); alternative scenarios
are the agent's to propose - the scaffold prints the INCOMPLETE MODEL
warning rather than inventing them.
"""
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from wiki import (ROOT, agent_commit, append_log, arg_after, read_concept,
                  write_concept)
from wiki_rubric import (coverage_by_technique, load_test_model,
                         model_warnings, validate_test_model)

_BOUND = re.compile(
    r"\b(or greater|or more|or less|less than|greater than|at least|at most|"
    r"more than|up to|within \d|per page|maximum|minimum|no more than|"
    r"between \d)\b", re.I)
_NUMBER = re.compile(r"\b\d[\d,]*(?:\.\d+)?\b")
_PARTITION = re.compile(
    r"\b(exactly one of|only the|lists only|lists every|no value where|"
    r"one of the values|either|permitted values|in my role's|"
    r"outside that scope|with no (?:row|platform|value))\b", re.I)
_TRANSITION = re.compile(
    r"\b(clears?|restores?|persists?|retains?|removes? the .* row|"
    r"until|while no|disables? .* while|redisplays?|"
    r"navigate away and return|closes? the drawer)\b", re.I)


def _short(text, n=110):
    t = " ".join(str(text or "").split())
    return t if len(t) <= n else t[: n - 1].rstrip() + "…"


def _ac_num(ac_id):
    m = re.search(r"AC(\d+)$", str(ac_id))
    return int(m.group(1)) if m else 0


def propose_story_model(fm):
    """Scaffold items for a story from its ACs and business rules."""
    items = []
    acs = [a for a in fm.get("acceptance_criteria") or []
           if isinstance(a, dict) and a.get("id")
           and a.get("status") not in ("voided", "retired")]
    acs.sort(key=lambda a: _ac_num(a.get("id")))
    n_bva = n_ep = n_st = 0
    for a in acs:
        aid = a["id"]
        num = _ac_num(aid)
        text = str(a.get("text") or "")
        items.append({
            "id": f"SC-{num:02d}", "technique": "UC", "kind": "scenario",
            "subject": _short(a.get("scenario") or aid, 60),
            "desc": _short(text), "basis": [aid], "feasible": True})
        if _BOUND.search(text) and _NUMBER.search(text):
            n_bva += 1
            nums = ", ".join(dict.fromkeys(_NUMBER.findall(text)))
            items.append({
                "id": f"BVA-{n_bva:02d}", "technique": "BVA",
                "kind": "boundary",
                "subject": _short(a.get("scenario") or aid, 60),
                "desc": f"boundaries around {nums} - "
                        f"{_short(_BOUND.search(text).group(0), 40)}",
                "basis": [aid], "feasible": True})
        if _PARTITION.search(text):
            n_ep += 1
            items.append({
                "id": f"EP-{n_ep:02d}", "technique": "EP", "kind": "partition",
                "subject": _short(a.get("scenario") or aid, 60),
                "desc": f"valid and invalid partitions of: "
                        f"{_short(_PARTITION.search(text).group(0), 40)}",
                "basis": [aid], "feasible": True})
        if _TRANSITION.search(text):
            n_st += 1
            items.append({
                "id": f"ST-{n_st:02d}", "technique": "ST", "kind": "transition",
                "subject": _short(a.get("scenario") or aid, 60),
                "desc": f"state transition: "
                        f"{_short(_TRANSITION.search(text).group(0), 40)}",
                "basis": [aid], "feasible": True})
    for i, r in enumerate(fm.get("business_rules") or [], start=1):
        if not isinstance(r, dict) or not r.get("id"):
            continue
        basis = [r["id"]] + [v for v in (r.get("verified_by") or [])
                             if any(a.get("id") == v for a in acs)]
        items.append({
            "id": f"RULE-{i:02d}", "technique": "DT", "kind": "rule",
            "subject": _short(r.get("title") or r["id"], 60),
            "desc": _short(r.get("text")), "basis": basis, "feasible": True})
    return items


def propose_flow_model(fm):
    """SC-MAIN over the journey. Alternatives are proposed by the agent."""
    journey = [j.get("id") for j in fm.get("journey") or []
               if isinstance(j, dict) and j.get("id")]
    if not journey:
        return []
    return [{"id": "SC-MAIN", "technique": "UC", "kind": "scenario",
             "role": "main", "subject": "main scenario",
             "desc": "the typical expected sequence through the journey",
             "basis": journey, "feasible": True}]


def _covered_ids(scope_rel):
    from wiki import load_all
    from eval_rubric import _tc_records
    concepts, _m = load_all()
    covered = set()
    for tc in _tc_records(concepts, scope_rel):
        covered.update(tc.get("coverage_items") or [])
    return covered


def show(kind, ident, fm):
    items, status = load_test_model(fm)
    print(f"test_model of {ident}: status {status or 'ABSENT'}, "
          f"{len(items)} item(s)")
    errs = validate_test_model(fm, ident)
    for e in errs:
        print(f"  INVALID: {e}")
    for w in model_warnings(items):
        print(f"  WARNING {w}")
    covered = _covered_ids(f"{'stories' if kind == 'story' else 'flows'}/{ident}")
    for it in items:
        if not isinstance(it, dict):
            continue
        mark = "x" if it.get("id") in covered else " "
        feas = "" if it.get("feasible", True) else " (infeasible)"
        print(f"  [{mark}] {it.get('id'):<10} {it.get('technique'):<4} "
              f"{it.get('kind'):<10} {it.get('subject', '')}{feas}")
    if items:
        cov = coverage_by_technique(items, covered)
        for tech, row in sorted(cov.items()):
            c = "undefined" if row["C"] is None else f"{row['C']}%"
            print(f"  {tech}: C = {row['N']}/{row['T']} = {c}")
    return errs


def cmd_testmodel(args):
    kind = "story" if "--story" in args else "flow" if "--flow" in args else None
    if not kind:
        sys.exit("testmodel: one of --story <id> or --flow <id> is required")
    ident = arg_after(args, f"--{kind}")
    p = ROOT / ("stories" if kind == "story" else "flows") / f"{ident}.md"
    if not p.exists():
        sys.exit(f"testmodel: {kind} {ident} not found")
    fm, body = read_concept(p)
    if "--propose" in args:
        tm = fm.get("test_model") or {}
        if tm.get("status") == "confirmed":
            sys.exit("testmodel: model is confirmed - correcting a confirmed "
                     "model is human-gated (card flow); refusing regardless "
                     "of --force")
        if tm.get("items") and "--force" not in args:
            sys.exit(f"testmodel: {ident} already has a proposed test_model "
                     f"(use --force to overwrite the PROPOSED model)")
        if kind == "story":
            items = propose_story_model(fm)
            if not fm.get("acceptance_criteria"):
                sys.exit(f"testmodel: {ident} has no acceptance criteria - "
                         f"there is nothing to model (tc-align first)")
        else:
            items = propose_flow_model(fm)
            if not items:
                sys.exit(f"testmodel: {ident} has no journey - the journey is "
                         f"proposed and asserted in tc-align first")
        fm["test_model"] = {"status": "proposed", "items": items}
        errs = validate_test_model(fm, ident)
        if errs:
            sys.exit("testmodel: the scaffold does not validate (bug):\n  "
                     + "\n  ".join(errs))
        write_concept(p, fm, body)
        append_log(f"**Test model (agent)**: scaffold of {len(items)} coverage "
                   f"item(s) proposed for {ident}")
        print(f"proposed test_model written to {ident} ({len(items)} items, "
              f"status proposed)")
        print("  Enrich it on the coverage card (EP partitions, BVA "
              "boundaries, DT rules, ST transitions the scaffold missed;\n"
              "  delete what does not belong; mark infeasible items with a "
              "justification). The human confirms the card.")
        agent_commit(f"testmodel({ident}): propose {len(items)} coverage "
                     f"item(s)")
    errs = show(kind, ident, fm)
    if errs:
        sys.exit(1)
