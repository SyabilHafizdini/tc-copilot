#!/usr/bin/env python3
"""Judge verdicts, judge packs, the gap report and the improve-round patch.

The engine (tools/eval_rubric.py) is LLM-free. Everything an LLM contributes
to a score arrives through this module as a FILE, so the same inputs plus the
same files always give the same number (spec 6):

  build/rubric/packs/<scope>-r<N>-<lens>.md        what each judge lens sees
  build/rubric/judgments/<scope>-r<N>-<lens>.json  what each judge decided
  build/rubric/<scope>-r<N>-gaps.md                what the improver reads
  build/rubric/<scope>-r<N>-patch.json             what the improver proposes
                                                   (applied to the sit_spec by
                                                   `eval_rubric --apply-patch`)

Four lenses, never per test case (spec 7.1). A lens may only judge the
dimensions it owns, and only dimensions the rubric marks `judge`; a verdict on
anything else is REJECTED with every error listed - never silently dropped.
"""
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

ROOT = Path(__file__).resolve().parent.parent
RUBRIC_BUILD = ROOT / "build/rubric"
PACK_DIR = RUBRIC_BUILD / "packs"
JUDGMENT_DIR = RUBRIC_BUILD / "judgments"

# Lens -> the dimensions it judges. Derived from spec 7.1, restricted to the
# dimensions the rubric actually marks `judge`: T1.3 and T1.9 are mechanical
# (their evidence is SHOWN to lens B, but B does not band them).
LENSES = {
    "A": {"name": "expected-result", "dims": ["T1.4", "T1.5"]},
    "B": {"name": "input-completeness", "dims": ["T1.7"]},
    "C": {"name": "technique-fit", "dims": ["T1.8"]},
    "D": {"name": "set-level", "dims": ["T2.5", "T2.6"]},
}
SCOPE_TC = "scope"          # the `tc` value a Tier 2 verdict carries
BANDS = {0: "absent", 1: "poor", 2: "adequate", 3: "good", 4: "exemplary"}


# ------------------------------------------------------------------ helpers
def _sec(body, heading):
    from eval_rubric import body_section
    return body_section(body, heading)


def _rel(p):
    """Path shown to the operator: repo-relative when under ROOT, else as-is
    (tests redirect the build dirs outside the repo)."""
    try:
        return Path(p).relative_to(ROOT).as_posix()
    except ValueError:
        return Path(p).as_posix()


def judgment_path(scope, rnd, lens):
    return JUDGMENT_DIR / f"{scope}-r{rnd}-{lens}.json"


def pack_path(scope, rnd, lens):
    return PACK_DIR / f"{scope}-r{rnd}-{lens}.md"


def score_path(scope, rnd=None):
    return RUBRIC_BUILD / (f"{scope}-r{rnd}-score.json" if rnd
                           else f"{scope}-score.json")


def gaps_path(scope, rnd):
    return RUBRIC_BUILD / f"{scope}-r{rnd}-gaps.md"


def patch_path(scope, rnd):
    return RUBRIC_BUILD / f"{scope}-r{rnd}-patch.json"


def packed_path(scope, rnd):
    """What the round-rnd judges were handed: {scope, round, sealed_digest,
    hashes {tc_id: sealed_hash}}, written by `--round N --pack`."""
    return RUBRIC_BUILD / f"{scope}-r{rnd}-packed.json"


def load_json_object(path, what="file"):
    """A JSON object from `path`, or a refusal naming the file - never a
    traceback. `wiki next` reads these for every scope."""
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        sys.exit(f"REFUSED: {what} {_rel(path)} is not valid JSON ({e}).\n"
                 f"  Next: delete or regenerate {_rel(path)}, then re-run.")
    if not isinstance(data, dict):
        sys.exit(f"REFUSED: {what} {_rel(path)} is not a JSON object.\n"
                 f"  Next: delete or regenerate {_rel(path)}, then re-run.")
    return data


def write_packed(scope, rnd, sealed_digest, hashes):
    """Record the sealed content the round-rnd packs show the judges, so the
    merge can refuse verdicts about content that has since moved."""
    p = packed_path(scope, rnd)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps({"scope": scope, "round": rnd,
                             "sealed_digest": sealed_digest,
                             "hashes": dict(hashes)},
                            indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return p


def packed_mismatch(scope, rnd, current_hashes):
    """Sorted test-case ids whose sealed hash differs between the round-rnd
    packed file and `current_hashes` (added, dropped or changed). Empty when
    they agree, and when no packed file exists (rounds packed before this
    check existed are not checked)."""
    p = packed_path(scope, rnd)
    if not p.exists():
        return []
    packed = load_json_object(p, "packed file").get("hashes")
    if not isinstance(packed, dict):
        sys.exit(f"REFUSED: packed file {_rel(p)} has no 'hashes' object.\n"
                 f"  Next: re-run --round {rnd} --pack, then re-judge.")
    current = current_hashes or {}
    return sorted(t for t in set(packed) | set(current)
                  if packed.get(t) != current.get(t))


def refuse_if_packed_changed(scope, rnd, flag, current_hashes):
    """The merge's refusal when the set moved since the packs were written:
    verdicts describe the content the judges read."""
    moved = packed_mismatch(scope, rnd, current_hashes)
    if moved:
        sys.exit(f"eval_rubric REFUSED: the sealed set of {scope} changed since "
                 f"the round {rnd} packs were written ({len(moved)} test "
                 f"case(s)). Verdicts describe the content the judges read.\n"
                 f"  Changed: {', '.join(moved[:10])}"
                 + (f" (+{len(moved) - 10} more)" if len(moved) > 10 else "") + "\n"
                 f"  Next: py tools/eval_rubric.py {flag} {scope} --round {rnd} "
                 f"--pack   (then re-judge)")


# ------------------------------------------------------------ load verdicts
def load_judgments(scope, rnd, rubric_hash, tc_ids, judge_dims,
                   judgment_dir=None, current_hashes=None):
    """Read every lens file for (scope, round), fresh and carried.

    Returns (per_tc, per_scope, notes, present_lenses):
      per_tc    {tc_id: {dim: band}}
      per_scope {dim: band}
      notes     {(tc_or_scope, dim): {"rationale", "gap", "lens", "band"
                 [, "carried_from"]}}
      present   set of lens letters whose fresh OR carried file existed

    A malformed or mismatched file is a hard refusal listing every problem.
    A MISSING file is not an error: its dimensions stay NOT ASSESSED and the
    score is marked PARTIAL, which is the honest reading of "no judge ran".

    Carried file (<scope>-r<N>-<L>.carried.json, written by carry_forward):
    same envelope, every verdict carries `carried_from: <round>`. A fresh
    verdict for the same (tc, dimension) WINS - a judge re-reading an
    untouched case is always allowed. When `current_hashes` ({tc_id: hash})
    is given, a carried verdict whose test case no longer has the sealed
    hash recorded in round `carried_from`'s score JSON is DROPPED with a
    printed note: it describes content that no longer exists.
    """
    jdir = judgment_dir or JUDGMENT_DIR
    per_tc, per_scope, notes, present = {}, {}, {}, set()
    # A fresh verdict silently wins over a carried one for the same
    # (tc, dimension); a duplicate WITHIN the fresh files or WITHIN the
    # carried files is a defect and refuses - so the two are tracked apart.
    errs, fresh_keys, carried_keys = [], set(), set()
    tc_ids = set(tc_ids)
    prev_hash_cache = {}

    def _prev_hash(from_round, tc):
        if from_round not in prev_hash_cache:
            p = score_path(scope, from_round)
            recs = (load_json_object(p, "score file").get("test_cases")
                    if p.exists() else None) or []
            prev_hash_cache[from_round] = {r.get("id"): r.get("sealed_hash") for r in recs}
        return prev_hash_cache[from_round].get(tc)

    for lens, spec in LENSES.items():
        files = ((jdir / f"{scope}-r{rnd}-{lens}.json", False),
                 (jdir / f"{scope}-r{rnd}-{lens}.carried.json", True))
        for p, carried in files:
            if not p.exists():
                continue
            present.add(lens)
            try:
                data = json.loads(p.read_text(encoding="utf-8"))
            except json.JSONDecodeError as e:
                errs.append(f"{p.name}: not valid JSON ({e})")
                continue
            if not isinstance(data, dict):
                errs.append(f"{p.name}: top level must be an object")
                continue
            if data.get("rubric_hash") != rubric_hash:
                errs.append(f"{p.name}: rubric_hash {data.get('rubric_hash')!r} "
                            f"does not match the current rubric {rubric_hash!r} "
                            f"- verdicts under another rubric are not comparable")
            if data.get("scope") != scope:
                errs.append(f"{p.name}: scope {data.get('scope')!r} is not {scope!r}")
            if data.get("lens") not in (lens, spec["name"]):
                errs.append(f"{p.name}: lens {data.get('lens')!r} is not "
                            f"{lens!r} / {spec['name']!r}")
            verdicts = data.get("verdicts")
            if not isinstance(verdicts, list):
                errs.append(f"{p.name}: verdicts must be a list")
                continue
            for i, v in enumerate(verdicts):
                where = f"{p.name} verdicts[{i}]"
                if not isinstance(v, dict):
                    errs.append(f"{where}: must be an object")
                    continue
                dim, band, tc = v.get("dimension"), v.get("band"), v.get("tc")
                if dim not in spec["dims"]:
                    errs.append(f"{where}: dimension {dim!r} is not judged by lens "
                                f"{lens} (it judges {spec['dims']})")
                    continue
                if dim not in judge_dims:
                    errs.append(f"{where}: dimension {dim!r} is not a judge "
                                f"dimension in the rubric")
                    continue
                if not (isinstance(band, int) and not isinstance(band, bool)
                        and 0 <= band <= 4):
                    errs.append(f"{where}: band {band!r} must be an integer 0-4")
                    continue
                rationale = v.get("rationale")
                if not (isinstance(rationale, str) and rationale.strip()):
                    errs.append(f"{where}: rationale is required (a band with no "
                                f"reason is not auditable)")
                    continue
                from_round = v.get("carried_from")
                if carried and not (isinstance(from_round, int)
                                    and not isinstance(from_round, bool)
                                    and 1 <= from_round < rnd):
                    errs.append(f"{where}: carried_from must be an earlier round "
                                f"number, got {from_round!r}")
                    continue
                tier2 = dim.startswith("T2.")
                if tier2:
                    key = SCOPE_TC
                    if tc not in (None, SCOPE_TC):
                        errs.append(f"{where}: a Tier 2 verdict applies to the "
                                    f"whole scope; tc must be null or 'scope'")
                        continue
                    if carried:
                        errs.append(f"{where}: a Tier 2 verdict is never carried")
                        continue
                else:
                    key = tc
                    if tc not in tc_ids:
                        errs.append(f"{where}: tc {tc!r} is not an active test "
                                    f"case of {scope}")
                        continue
                own = carried_keys if carried else fresh_keys
                if (key, dim) in own:
                    errs.append(f"{where}: duplicate verdict for ({key}, {dim})")
                    continue
                own.add((key, dim))
                if carried and (key, dim) in fresh_keys:
                    continue                # the fresh verdict already won
                if carried and current_hashes is not None:
                    if current_hashes.get(tc) != _prev_hash(from_round, tc):
                        print(f"  carried verdict dropped: {tc} {dim} changed since "
                              f"round {from_round}")
                        continue
                if tier2:
                    per_scope[dim] = band
                else:
                    per_tc.setdefault(key, {})[dim] = band
                note = {"rationale": rationale.strip(),
                        "gap": (v.get("gap") or "").strip(),
                        "lens": lens, "band": band}
                if carried:
                    note["carried_from"] = from_round
                notes[(key, dim)] = note
    if errs:
        detail = "\n".join(f"    - {e}" for e in errs)
        sys.exit(f"eval_rubric REFUSED: judge verdicts for {scope} round {rnd} "
                 f"are not acceptable.\n{detail}\n"
                 f"  A rejected verdict is never silently dropped (spec 6.3).\n"
                 f"  Next: fix the file(s) under build/rubric/judgments/ and "
                 f"re-run.")
    return per_tc, per_scope, notes, present


# ------------------------------------------------------------------- packs
_SCHEMA = """```json
{
  "rubric_hash": "%(hash)s",
  "scope": "%(scope)s",
  "round": %(round)d,
  "lens": "%(lens)s",
  "verdicts": [
    {"tc": %(tc_example)s, "dimension": "%(dim)s", "band": 0,
     "rationale": "<why this band, citing the field you read>",
     "gap": "<the one change that would raise the band, or empty>"}
  ]
}
```"""

_RULES = """## Rules for this lens

- Band every dimension listed above for EVERY test case in the material
  (Tier 1), or once for the whole set (Tier 2). A test case you do not band
  stays NOT ASSESSED and marks the score PARTIAL.
- Bands: 0 absent, 1 poor, 2 adequate, 3 good, 4 exemplary.
- Where a mechanical ceiling is shown, your band may be LOWER than the
  ceiling but the engine will cap it there. A ceiling of 0 is final.
- Judge against the OBLIGATION text, not against taste. Quote the field you
  read in `rationale`. Put the single most useful correction in `gap`.
- Never invent facts about the product. If the basis text does not say it,
  the expected result is not derived from the basis.
- Write the file EXACTLY to the path above, with the `rubric_hash` shown.
  Any other hash, scope, lens, tc id or dimension is rejected.
"""


def _tc_block(tc, ac_text, br_text, model_by_id, mech, dims, include):
    """One test case rendered for a pack. `include` selects sections."""
    lines = [f"### {tc.get('id')} - {tc.get('title', '')}",
             f"- technique: {tc.get('technique')} · priority: "
             f"{tc.get('priority')} · area: {tc.get('area')}"]
    basis = []
    for ref in (tc.get("covers") or []) + (tc.get("verifies_rules") or []):
        frag = str(ref).rsplit("#", 1)[-1] if "#" in str(ref) else None
        if frag:
            basis.append(frag)
    lines.append(f"- basis: {', '.join(basis) or '(none)'}")
    if "items" in include:
        items = tc.get("coverage_items") or []
        if items:
            lines.append("- coverage_items:")
            for i in items:
                m = model_by_id.get(i)
                if m:
                    lines.append(f"    - {i} · {m.get('technique')} / "
                                 f"{m.get('kind')} · {m.get('subject', '')}: "
                                 f"{m.get('desc', '')}")
                else:
                    lines.append(f"    - {i} · NOT IN MODEL")
        else:
            lines.append("- coverage_items: (none)")
    ceilings = {d: mech.get(d) for d in dims if d in mech}
    if ceilings:
        lines.append("- mechanical ceiling: " + ", ".join(
            f"{d} = {v}" for d, v in ceilings.items()))
    body = tc.get("body") or ""
    if "basis_text" in include:
        for b in basis:
            t = ac_text.get(b) or br_text.get(b)
            if t:
                lines.append(f"- {b}: {t}")
    for sec in ("Objective", "Preconditions", "Test Data", "Steps",
                "Expected Results"):
        if sec.lower().replace(" ", "_") in include or "all" in include:
            txt = _sec(body, sec)
            lines.append(f"\n**{sec}**\n\n{txt or '(empty)'}")
    return "\n".join(lines) + "\n"


def write_packs(result, tcs, fm, rub, rnd, mech_by_tc, lenses=None, exclude=None):
    """Write one pack per lens under build/rubric/packs/. Returns paths."""
    from rubric import dimensions
    PACK_DIR.mkdir(parents=True, exist_ok=True)
    scope = result["scope"]
    dims_by_id = {d["id"]: d for d in dimensions(rub)}
    items = (fm.get("test_model") or {}).get("items") or []
    model_by_id = {i.get("id"): i for i in items if isinstance(i, dict)}
    ac_text = {a.get("id"): a.get("text", "") for a in
               fm.get("acceptance_criteria") or [] if isinstance(a, dict)}
    br_text = {r.get("id"): r.get("text", "") for r in
               fm.get("business_rules") or [] if isinstance(r, dict)}
    journey = {j.get("id"): j.get("ref", "") for j in fm.get("journey") or []
               if isinstance(j, dict)}
    ac_text.update(journey)
    out = []
    for lens in (lenses or LENSES):
        spec = LENSES[lens]
        dims = spec["dims"]
        tier2 = dims[0].startswith("T2.")
        path = pack_path(scope, rnd, lens)
        lines = [f"# Judge pack · lens {lens} ({spec['name']}) · {scope} · "
                 f"round {rnd}", "",
                 f"Rubric {result['rubric_version']} · `{result['rubric_hash']}`"
                 f" · {result.get('standard', '')}", "",
                 "## Dimensions you band", ""]
        for d in dims:
            dd = dims_by_id[d]
            lines.append(f"- **{d} {dd['name']}** (weight {dd['weight']}, "
                         f"{dd['clause']}): {dd['obligation']}")
        lines += ["", "## Output", "",
                  f"Write `{_rel(judgment_path(scope, rnd, lens))}`:",
                  "",
                  _SCHEMA % {"hash": result["rubric_hash"], "scope": scope,
                             "round": rnd, "lens": lens, "dim": dims[0],
                             "tc_example": '"scope"' if tier2
                             else '"<test case id>"'},
                  "", _RULES, "## Material", ""]
        if lens == "A":
            include = {"basis_text", "test_data", "steps", "expected_results"}
        elif lens == "B":
            include = {"items", "preconditions", "test_data", "steps"}
        elif lens == "C":
            include = {"items", "objective", "test_data", "steps"}
        else:
            include = set()
        if lens == "D":
            lines.append("### Acceptance criteria\n")
            for a in fm.get("acceptance_criteria") or []:
                if isinstance(a, dict):
                    lines.append(f"- {a.get('id')} · {a.get('scenario', '')}"
                                 f" · priority {a.get('priority')} · risk "
                                 f"{a.get('risk')}")
            lines.append("\n### Test model\n")
            for i in items:
                lines.append(f"- {i.get('id')} · {i.get('technique')}/"
                             f"{i.get('kind')} · {i.get('subject', '')}: "
                             f"{i.get('desc', '')} · basis "
                             f"{', '.join(i.get('basis') or [])}"
                             + ("" if i.get("feasible", True) else
                                f" · INFEASIBLE: {i.get('justification')}"))
            lines.append("\n### Test cases (whole set)\n")
            lines.append("| id | technique | title | basis | coverage_items "
                         "| negative? |")
            lines.append("|---|---|---|---|---|---|")
            for tc in tcs:
                basis = [str(r).rsplit("#", 1)[-1] for r in
                         (tc.get("covers") or []) + (tc.get("verifies_rules") or [])
                         if "#" in str(r)]
                neg = "yes" if _is_negative(tc) else ""
                lines.append(f"| {tc.get('id')} | {tc.get('technique')} | "
                             f"{tc.get('title', '')} | {', '.join(basis)} | "
                             f"{', '.join(tc.get('coverage_items') or [])} | "
                             f"{neg} |")
            cov = result.get("coverage") or {}
            lines.append("\n### Mechanical evidence\n")
            for tech, row in sorted(cov.items()):
                c = "undefined" if row["C"] is None else f"{row['C']}%"
                lines.append(f"- {tech}: C = {row['N']}/{row['T']} = {c}")
            lines.append(f"- negative test cases: "
                         f"{sum(1 for t in tcs if _is_negative(t))} of {len(tcs)}"
                         f" (T2.5 mechanical ceiling "
                         f"{result.get('t25_ceiling')})")
            lines.append("- T2.6 has no mechanical evidence; read the ACs for "
                         "non-functional characteristics (performance, "
                         "security, usability, reliability, compatibility, "
                         "maintainability, portability) and judge whether the "
                         "set exercises the ones that apply.")
        else:
            skip = set((exclude or {}).get(lens) or set())
            shown = [tc for tc in tcs if tc.get("id") not in skip]
            if skip:
                lines.append(f"Carried forward from round {rnd - 1}: {len(skip)} "
                             f"test case(s) unchanged since their last verdict - "
                             f"do not band them; band only the {len(shown)} below.\n")
            if skip and not shown:
                lines.append("Nothing to judge for this lens this round; every "
                             "verdict is carried. Do not write a judgment file.\n")
            for tc in shown:
                lines.append(_tc_block(tc, ac_text, br_text, model_by_id,
                                       mech_by_tc.get(tc.get("id"), {}),
                                       dims, include))
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        out.append(path)
    return out


_NEG_WORDS = re.compile(r"\b(reject|rejects|invalid|blocks? the save|error|"
                        r"not permitted|cannot|denied|refus)", re.I)


def _is_negative(tc):
    """A negative test case: tagged ERR, carries an '(invalid)' input, or its
    title/objective is about rejection. Mechanical evidence for T2.5."""
    from eval_rubric import _INVALID_MARK, _data_values
    if tc.get("technique") == "ERR":
        return True
    if any(_INVALID_MARK.search(v) for v in _data_values(tc.get("body") or "")):
        return True
    head = f"{tc.get('title', '')} {_sec(tc.get('body') or '', 'Objective')}"
    return bool(_NEG_WORDS.search(head))


def t25_ceiling(tcs):
    """Mechanical ceiling for T2.5 valid/invalid balance.

    No negative test case at all is band 0 - a measurement, not a bound: the
    set exercises valid paths only and no judge can find an invalid partition
    that is not there. Otherwise 4: the judge decides within.
    """
    if not tcs:
        return None
    return 0 if not any(_is_negative(t) for t in tcs) else 4


# ------------------------------------------------------------- gap report
_MECH_REASON = {
    "T1.1": {0: "names no coverage_items", 1: "names a coverage item the "
             "model does not define"},
    "T1.2": {0: "covers no AC or rule of this scope", 1: "covers an id that "
             "does not exist in this scope"},
    "T1.3": {0: "Test Data holds no '**Field** = value' line",
             1: "a Test Data value is a placeholder (TBD / valid data / any)"},
    "T1.4": {0: "Expected Results section is empty"},
    "T1.7": {1: "Preconditions section is absent"},
    "T1.8": {1: "technique tag does not fit the kind of coverage item named"},
    "T1.9": {0: "more than one '(invalid)' input in one negative case"},
}


def write_gaps(result, tcs, fm, notes, rnd, mech_by_tc):
    """build/rubric/<scope>-r<N>-gaps.md - everything below band 3, ranked
    by what it costs, plus every uncovered feasible coverage item."""
    scope = result["scope"]
    path = gaps_path(scope, rnd)
    items = (fm.get("test_model") or {}).get("items") or []
    covered = set()
    for tc in tcs:
        covered.update(tc.get("coverage_items") or [])
    title = {tc.get("id"): tc.get("title", "") for tc in tcs}
    flag = " (PARTIAL)" if result["partial"] else ""
    L = [f"# Gap report · {scope} · round {rnd}", "",
         f"Score **{result['score']}**{flag} · tier1 {result['tier1']} · "
         f"tier2 {result['tier2']} · threshold {result['threshold']} · rubric "
         f"`{result['rubric_hash']}`", ""]
    # G1: uncovered coverage items - the most actionable gap there is
    L += ["## G1 · Coverage items no test case exercises (T2.1)", ""]
    n = 0
    for it in items:
        if not isinstance(it, dict) or not it.get("feasible", True):
            continue
        if it.get("id") in covered:
            continue
        n += 1
        L.append(f"- G1.{n} **{it.get('id')}** · {it.get('technique')}/"
                 f"{it.get('kind')} · {it.get('subject', '')}: "
                 f"{it.get('desc', '')} · basis {', '.join(it.get('basis') or [])}")
    if not n:
        L.append("- none")
    for tech, row in sorted((result.get("coverage") or {}).items()):
        c = "undefined" if row["C"] is None else f"{row['C']}%"
        L.append(f"  - {tech}: C = {row['N']}/{row['T']} = {c}")
    for w in result.get("model_warnings") or []:
        L.append(f"  - WARNING {w}")
    for ref in result.get("unknown_item_refs") or []:
        L.append(f"  - UNKNOWN COVERAGE ITEM {ref}")
    # G2: tier 2 dimensions below good
    L += ["", "## G2 · Set-level dimensions below band 3", ""]
    n = 0
    for dim, band in sorted((result.get("tier2_bands") or {}).items()):
        if isinstance(band, int) and band < 3:
            n += 1
            note = notes.get((SCOPE_TC, dim))
            why = (f"{note['rationale']} → {note['gap']}" if note
                   else "mechanical")
            L.append(f"- G2.{n} **{dim}** band {band} ({BANDS[band]}): {why}")
        elif not isinstance(band, int):
            judged = any(dim in spec["dims"] for spec in LENSES.values())
            why = ("no judge verdict" if judged
                   else "nothing to measure - e.g. T2.4 with no infeasible item")
            L.append(f"- {dim}: NOT ASSESSED ({why})")
    if not n:
        L.append("- none below 3")
    # G3: per test case
    L += ["", "## G3 · Test-case dimensions below band 3", ""]
    n = 0
    for rec in sorted(result["test_cases"], key=lambda r: (r["score"] or 0)):
        low = {d: b for d, b in rec["bands"].items()
               if isinstance(b, int) and b < 3}
        na = [d for d, b in rec["bands"].items() if not isinstance(b, int)]
        if not low and not na:
            continue
        n += 1
        L.append(f"### G3.{n} {rec['id']} · {title.get(rec['id'], '')} · "
                 f"score {rec['score']}")
        for d, b in sorted(low.items()):
            note = notes.get((rec["id"], d))
            if note:
                why = note["rationale"] + (f" → **{note['gap']}**"
                                           if note["gap"] else "")
            else:
                mech = mech_by_tc.get(rec["id"], {}).get(d)
                why = _MECH_REASON.get(d, {}).get(mech, "mechanical")
            L.append(f"- **{d}** band {b} ({BANDS[b]}): {why}")
        if na:
            L.append(f"- NOT ASSESSED: {', '.join(sorted(na))}")
        L.append("")
    if not n:
        L.append("- none")
    L += ["", "## How to close a gap", "",
          "- G1: add a test case (or `coverage_items` on an existing one) in "
          "`tools/sit_specs/<STORY>.yaml`, then re-render.",
          "- G2/G3: edit the named field in the spec entry `(ac, seq)`; never "
          "edit the rendered `testcases/` file (W4 drift).",
          f"- Emit the patch as `{_rel(patch_path(scope, rnd))}`"
          " and apply it with `py tools/eval_rubric.py --story <id> "
          f"--apply-patch <that file>`."]
    path.write_text("\n".join(L) + "\n", encoding="utf-8")
    return path


# ------------------------------------------------------------ round delta
def round_delta(scope, rnd):
    """Compare round N with round N-1. Returns dict or None."""
    if not rnd or rnd < 2:
        return None
    prev = score_path(scope, rnd - 1)
    cur = score_path(scope, rnd)
    if not prev.exists() or not cur.exists():
        return None
    a = json.loads(prev.read_text(encoding="utf-8"))
    b = json.loads(cur.read_text(encoding="utf-8"))
    d = {"scope": scope, "from_round": rnd - 1, "to_round": rnd,
         "from": a.get("score"), "to": b.get("score"),
         "same_rubric": a.get("rubric_hash") == b.get("rubric_hash")}
    if d["from"] is not None and d["to"] is not None:
        d["delta"] = round(d["to"] - d["from"], 2)
        d["regression"] = d["delta"] < 0
    else:
        d["delta"] = None
        d["regression"] = False
    return d


# ------------------------------------------------------ rubric state
def draft_path(scope):
    return RUBRIC_BUILD / f"{scope}-draft.json"


def changes_path(scope, ext="json"):
    return RUBRIC_BUILD / f"{scope}-changes.{ext}"


def carried_path(scope, rnd, lens):
    return JUDGMENT_DIR / f"{scope}-r{rnd}-{lens}.carried.json"


def carry_forward(scope, rnd, tcs, tc_hashes, rubric_hash, judge_dims):
    """Round rnd >= 2: for lenses A, B, C copy round rnd-1's VALIDATED,
    hash-checked verdicts for every test case whose sealed hash is unchanged
    since that round into <scope>-r<rnd>-<L>.carried.json. Returns
    {lens: sorted tc ids with EVERY dimension of the lens carried} - the ids
    `write_packs` leaves out of that lens's pack; a partly carried case stays
    in the pack. Lens D (set-level) is never carried.

    Sources verdicts from round rnd-1's own `load_judgments` merge (not the
    raw files): this both re-refuses an INVALID round rnd-1 verdict file
    (carrying a rejected verdict would launder it, spec 4.3) and drops any
    round rnd-1 carried verdict that round rnd-1 itself already found stale
    - a verdict dropped once must never be re-carried on the strength of a
    hash it no longer applies to. `carried_from` is preserved from round
    rnd-1's own note when it has one, so a chained carry's hash re-check
    always compares against the round that verdict actually judged.

    Every round-rnd carried file for A/B/C is removed up front, so a lens
    with nothing left to keep never leaves a stale file behind for the merge
    to trip over. Nothing is carried - after clearing those files - when
    round rnd-1 has no score, was scored under a different rubric (verdicts
    under another rubric are not comparable), or its records carry no
    sealed_hash (scored before this existed)."""
    if rnd < 2:
        return {}
    for lens in ("A", "B", "C"):
        carried_path(scope, rnd, lens).unlink(missing_ok=True)
    prev = score_path(scope, rnd - 1)
    if not prev.exists():
        return {}
    prev_score = load_json_object(prev, "score file")
    if prev_score.get("rubric_hash") != rubric_hash:
        return {}
    prev_recs = [r for r in prev_score.get("test_cases") or [] if isinstance(r, dict)]
    prev_hash = {r.get("id"): r.get("sealed_hash") for r in prev_recs
                 if r.get("sealed_hash")}
    if not prev_hash:
        return {}
    cur_hash = {tc.get("id"): tc_hashes.get(tc.get("rel")) for tc in tcs}
    unchanged = {t for t, h in cur_hash.items() if h and prev_hash.get(t) == h}
    # Validate against EVERY round rnd-1 test case, hashed or not: a verdict
    # for an unhashed case is valid (just never carried), not "not active".
    _pt, _ps, prev_notes, _pr = load_judgments(
        scope, rnd - 1, rubric_hash, [r.get("id") for r in prev_recs], judge_dims,
        current_hashes=prev_hash)
    JUDGMENT_DIR.mkdir(parents=True, exist_ok=True)
    out = {}
    for lens in ("A", "B", "C"):
        keep = [{"tc": tc, "dimension": dim, "band": note["band"],
                 "rationale": note["rationale"], "gap": note["gap"],
                 "carried_from": note.get("carried_from", rnd - 1)}
                for (tc, dim), note in prev_notes.items()
                if note["lens"] == lens and tc in unchanged
                and not dim.startswith("T2.")]
        if not keep:
            continue
        carried_path(scope, rnd, lens).write_text(json.dumps(
            {"rubric_hash": rubric_hash, "scope": scope, "round": rnd,
             "lens": lens, "verdicts": keep}, indent=2) + "\n", encoding="utf-8")
        # Leave the lens's pack only when EVERY one of its dimensions was
        # carried: a partly carried case is re-read (the fresh verdict wins).
        need = set(LENSES[lens]["dims"]) & set(judge_dims)
        dims_of = {}
        for v in keep:
            dims_of.setdefault(v["tc"], set()).add(v["dimension"])
        full = sorted(t for t, ds in dims_of.items() if need and need <= ds)
        if full:
            out[lens] = full
    return out


def carried_counts(notes):
    """{lens: number of distinct tc ids whose note has carried_from}, from
    the `notes` a round's `load_judgments` merge returned - i.e. only
    verdicts actually accepted into the score, never ones dropped for a
    hash that moved since."""
    out = {}
    for (tc, _dim), note in notes.items():
        if "carried_from" in note:
            out.setdefault(note["lens"], set()).add(tc)
    return {lens: len(ids) for lens, ids in out.items()}


# ------------------------------------------------------ draft -> final diff
# Improver patch field names -> the record field / body heading they change.
PATCH_FIELD_TO_RECORD = {"data": "Test Data", "expected": "Expected Results",
                         "steps": "Steps", "pre_extra": "Preconditions",
                         "post": "Postconditions", "objective": "Objective",
                         "title": "title", "technique": "technique",
                         "priority": "priority", "coverage_items": "coverage_items",
                         "extra_covers": "covers", "rules": "verifies_rules"}


def patch_tc_index(scope, kind, patch, cfg):
    """{tc_id: [{"op", "field", "closes"}]} from an improver patch. A story
    op names (ac, seq); the id follows config ids.tc_format. A flow op joins
    only when it carries a `tc` key (spec 4.4 step 3)."""
    ids = cfg.get("ids") or {}
    fmt = ids.get("tc_format", "{story_num}-AC{ac_num:02d}-{seq:02d}")
    prefix = ids.get("story_prefix", "US-")
    story_num = scope[len(prefix):] if scope.startswith(prefix) else scope
    idx = {}
    for p in (patch or {}).get("patches") or []:
        if not isinstance(p, dict):
            continue
        tid = p.get("tc")
        if not tid and kind == "story":
            entry = p.get("test_case") if p.get("op") == "add" else p
            entry = entry if isinstance(entry, dict) else {}
            m = re.search(r"AC(\d+)", str(entry.get("ac", "")))
            if m and entry.get("seq") is not None:
                tid = fmt.format(story_num=story_num, ac_num=int(m.group(1)),
                                 seq=int(entry["seq"]))
        if tid:
            idx.setdefault(tid, []).append({"op": p.get("op", "set"),
                                            "field": p.get("field"),
                                            "closes": p.get("closes", "")})
    return idx


def _closes_of(ops):
    tags = []
    for op in ops:
        for c in re.split(r",\s*", op.get("closes") or ""):
            if c and c not in tags:
                tags.append(c)
    return ", ".join(tags)


def diff_records(old, new, cause=None):
    """Compare two {tc_id: tc_record} maps (spec 4.4). Returns (changes,
    counts). A case absent from `new`, or present but not active, is
    removed - checked BEFORE 'added', so a case added after the draft but
    not active now is removed, never an addition; a case new since the draft
    is added; equal hashes are unchanged; otherwise one change per field."""
    from wiki_rubric import DIFF_FIELDS
    cause = cause or {}
    changes = []
    counts = {"added": 0, "changed": 0, "removed": 0, "unchanged": 0}
    for tid in sorted(set(old) | set(new)):
        o, n = old.get(tid), new.get(tid)
        ops = cause.get(tid) or []
        closes = _closes_of(ops)
        if n is None or n.get("status") != "active":
            counts["removed"] += 1
            changes.append({"tc": tid, "kind": "removed",
                            "reason": (n or {}).get("retirement_reason")
                            or "not in the current set"})
        elif o is None:
            counts["added"] += 1
            changes.append({"tc": tid, "kind": "added",
                            "title": n.get("title", ""), "closes": closes})
        elif o.get("hash") == n.get("hash"):
            counts["unchanged"] += 1
        else:
            fields = [(f, o.get(f), n.get(f)) for f in DIFF_FIELDS
                      if o.get(f) != n.get(f)]
            heads = sorted(set(o.get("sections") or {}) | set(n.get("sections") or {}))
            for h in heads:
                ov = (o.get("sections") or {}).get(h)
                nv = (n.get("sections") or {}).get(h)
                if ov != nv:
                    fields.append((h, ov, nv))
            if not fields:
                fields.append(("(file)", o.get("hash"), n.get("hash")))
            counts["changed"] += 1
            for f, ov, nv in fields:
                op = next((x for x in ops if x.get("field")
                           and PATCH_FIELD_TO_RECORD.get(x["field"], x["field"]) == f),
                          None)
                changes.append({"tc": tid, "kind": "changed", "field": f,
                                "old": ov, "new": nv,
                                "closes": op["closes"] if op else closes,
                                "op": op})
    return changes, counts


def _unified(old, new, cap=40):
    import difflib
    a = (old or "").splitlines() if isinstance(old, str) else [json.dumps(old)]
    b = (new or "").splitlines() if isinstance(new, str) else [json.dumps(new)]
    lines = [ln for ln in difflib.unified_diff(a, b, lineterm="", n=1)
             if not ln.startswith(("---", "+++"))]
    if len(lines) > cap:
        lines = lines[:cap] + [f"... {len(lines) - cap} more line(s)"]
    return lines


def write_changes(scope, kind, snapshot, current, state, cause, to_digest,
                  threshold, version):
    """build/rubric/<scope>-changes.json + .md (spec 5.2)."""
    changes, counts = diff_records(snapshot.get("test_cases") or {}, current, cause)
    rounds = sorted((n, r.get("score")) for n, r in (state.get("rounds") or {}).items())
    cur, hi = state.get("current"), state.get("highest")
    delta = None
    if len(rounds) >= 2 and rounds[-1][1] is not None and rounds[-2][1] is not None:
        delta = round(rounds[-1][1] - rounds[-2][1], 2)
    doc = {"scope": scope, "kind": kind,
           "from": {"label": "draft r0", "digest": snapshot.get("sealed_digest"),
                    "score": snapshot.get("score"),
                    "exported_at": snapshot.get("exported_at")},
           "to": {"label": f"round {cur['round']}" if cur else "ungraded",
                  "digest": to_digest, "score": cur["score"] if cur else None,
                  "round": cur["round"] if cur else None},
           "to_digest": to_digest,
           "rounds": [{"round": n, "score": s} for n, s in rounds],
           "delta": delta,
           "regression_restored": bool(cur and hi and cur["round"] < hi),
           "rubric_version": version, "threshold": threshold,
           "counts": counts, "changes": changes}
    RUBRIC_BUILD.mkdir(parents=True, exist_ok=True)
    jp, mp = changes_path(scope, "json"), changes_path(scope, "md")
    jp.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    L = [f"# Changes · {scope} · draft r0 -> {doc['to']['label']}", "",
         f"- scores: " + ", ".join(f"round {n} {s}" for n, s in rounds)
         + (f" · delta {delta:+}" if delta is not None else "")
         + f" · threshold {threshold} · rubric {version}",
         f"- current: {doc['to']['label']}"
         + (" (round 2 regressed; round 1 kept)" if doc["regression_restored"] else ""),
         f"- {counts['added']} added, {counts['changed']} changed, "
         f"{counts['removed']} removed, {counts['unchanged']} unchanged", ""]
    L += ["## Added", ""]
    L += [f"- **{c['tc']}** - {c['title']}" + (f" (closes {c['closes']})" if c["closes"] else "")
          for c in changes if c["kind"] == "added"] or ["- none"]
    L += ["", "## Changed", ""]
    by_tc = {}
    for c in changes:
        if c["kind"] == "changed":
            by_tc.setdefault(c["tc"], []).append(c)
    for tid, cs in by_tc.items():
        L.append(f"### {tid}")
        for c in cs:
            L.append(f"- **{c['field']}**" + (f" (closes {c['closes']})" if c["closes"] else "")
                     + (" - cause: not recorded" if not c.get("op") and not c["closes"] else ""))
            L.append("```diff")
            L += _unified(c["old"], c["new"])
            L.append("```")
        L.append("")
    if not by_tc:
        L.append("- none")
    L += ["", "## Removed", ""]
    L += [f"- **{c['tc']}** - {c['reason']}" for c in changes if c["kind"] == "removed"] or ["- none"]
    mp.write_text("\n".join(L) + "\n", encoding="utf-8")
    return jp, mp


def score_rounds(scope):
    """{N: score JSON} for every <scope>-r<N>-score.json present. A malformed
    file is a refusal naming it (load_json_object), never a traceback: `wiki
    next` calls this for every scope."""
    out = {}
    pat = re.compile(rf"^{re.escape(scope)}-r(\d+)-score\.json$")
    for p in sorted(RUBRIC_BUILD.glob(f"{scope}-r*-score.json")):
        m = pat.match(p.name)
        if m:
            out[int(m.group(1))] = load_json_object(p, "score file")
    return out


def rubric_state(scope, digest, threshold, version):
    """The one reading of a scope's grade that export, --diff and `wiki next`
    share (spec 4.2, 4.5). `current` is the highest round whose score is
    non-PARTIAL, at or above `threshold`, under rubric `version`, and computed
    on exactly the sealed set `digest` identifies."""
    rounds = score_rounds(scope)
    current = None
    for n in sorted(rounds):
        s = rounds[n]
        if (not s.get("partial") and s.get("score") is not None
                and s["score"] >= threshold
                and s.get("rubric_version") == version
                and s.get("sealed_digest") == digest):
            current = {"round": n, "score": s["score"]}
    return {"rounds": {n: {"score": s.get("score"),
                           "partial": bool(s.get("partial")),
                           "digest": s.get("sealed_digest"),
                           "rubric_version": s.get("rubric_version")}
                       for n, s in rounds.items()},
            "highest": max(rounds) if rounds else None,
            "improve_round_ran": 2 in rounds,
            "current": current}


# ----------------------------------------------------------- apply patch
PATCH_FIELDS = {"data", "expected", "steps", "pre_extra", "post", "title",
                "objective", "technique", "priority", "coverage_items",
                "rules", "terms", "extra_covers", "area"}


def apply_patch(spec_path, patch_file):
    """Apply an improver patch list to a sit_spec YAML.

    Patch file: {"scope": ..., "round": N, "patches": [
        {"op": "set", "ac": "AC03", "seq": 2, "field": "expected",
         "value": "...", "closes": "G3.4"},
        {"op": "add", "test_case": {<full sit_spec entry>}, "closes": "G1.2"}
    ]}
    The improver PROPOSES; this function is the sole writer (spec 7.2).
    Returns (applied, errors). Nothing is written when any error exists.
    """
    import yaml
    from render_sit import TC_OPTIONAL, TC_REQUIRED
    data = json.loads(Path(patch_file).read_text(encoding="utf-8"))
    patches = data.get("patches")
    if not isinstance(patches, list) or not patches:
        return 0, ["patch file has no 'patches' list"]
    spec = yaml.safe_load(Path(spec_path).read_text(encoding="utf-8"))
    tcs = spec.get("test_cases") or []
    index = {(tc.get("ac"), tc.get("seq")): tc for tc in tcs}
    errs, applied = [], 0
    allowed = set(TC_REQUIRED) | set(TC_OPTIONAL)
    for i, p in enumerate(patches):
        where = f"patches[{i}]"
        op = p.get("op", "set")
        if op == "set":
            key = (p.get("ac"), p.get("seq"))
            if key not in index:
                errs.append(f"{where}: no spec entry ({key[0]}, seq {key[1]})")
                continue
            field = p.get("field")
            if field not in PATCH_FIELDS or field not in allowed:
                errs.append(f"{where}: field {field!r} is not patchable "
                            f"(allowed: {sorted(PATCH_FIELDS & allowed)})")
                continue
            if "value" not in p:
                errs.append(f"{where}: missing 'value'")
                continue
            index[key][field] = p["value"]
            applied += 1
        elif op == "add":
            tc = p.get("test_case")
            if not isinstance(tc, dict):
                errs.append(f"{where}: 'add' needs a 'test_case' mapping")
                continue
            missing = [k for k in TC_REQUIRED if k not in tc]
            unknown = [k for k in tc if k not in allowed]
            if missing or unknown:
                errs.append(f"{where}: add test_case missing {missing}, "
                            f"unknown {unknown}")
                continue
            key = (tc.get("ac"), tc.get("seq"))
            if key in index:
                errs.append(f"{where}: ({key[0]}, seq {key[1]}) already exists")
                continue
            tcs.append(tc)
            index[key] = tc
            applied += 1
        else:
            errs.append(f"{where}: unknown op {op!r} (set|add)")
    if errs:
        return 0, errs
    # keep AC order then seq, matching the render convention
    def _k(tc):
        m = re.match(r"AC(\d+)", str(tc.get("ac", "")))
        return (int(m.group(1)) if m else 10**6, tc.get("seq", 0))
    spec["test_cases"] = sorted(tcs, key=_k)
    Path(spec_path).write_text(
        yaml.safe_dump(spec, sort_keys=False, allow_unicode=True, width=100),
        encoding="utf-8")
    return applied, []
