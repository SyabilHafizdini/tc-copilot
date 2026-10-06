#!/usr/bin/env python3
"""Shared SIT render driver — one engine, one validated data spec per story.

Replaces the per-story `render_<story>_sit.py` copies. Each of those was ~460
lines: ~136 of machinery that was byte-identical between them, and ~325 of a
positional 15-field tuple table. Copying that to open a new scope meant
reproducing the machinery correctly and editing a tuple whose fields are
identified only by position — where a single shifted comma silently writes
`steps` into `expected` with no error anywhere.

Now the machinery lives here once, and a scope contributes only DATA at
`tools/sit_specs/<STORY>.yaml` with NAMED keys, validated in full before a
single file is written. Unknown keys, missing keys, bad techniques/priorities,
duplicate (ac, seq) pairs, and AC/rule ids that do not exist in the story are
all reported together, with spelling suggestions, and abort the run.

Run:
    py tools/render_sit.py --story US-XXXX [--force]

Byte-compatible with the renderers it replaces: same TC ids, same scenario ids,
same file bodies. `smoke.py` asserts it (re-render on an unchanged wiki must
report `rendered 0`).

Spec shape (see tools/sit_specs/<STORY>.yaml):

    story: /stories/US-XXXX.md      module: /modules/<module>.md
    figma: <figma-page>             out: testcases/sit/<module>
    ac_prefix: "1.1.3.1.1"          # prepended to a bare "AC5"
    scenario_id: "SC-XXXX-{ac}-{seq:02d}"      # {ac} bare, {ac_id} full
    generator_version: "1.1.0"
    pre_common: |-                  # tc-style R5: shared verbatim by every TC
      1. ...
    post_default: "No system state changed (read-only verification)."
    entry_state: portal-home        # the state every `start` test case begins at
    states:                         # named screen states; one sentence each,
      portal-home: "Portal home page, not logged in."       # printed after
      step1-done: "Step 1 completed; Step 2 is the ongoing task."  # Continue from
    profiles:                       # named data profiles (the persona / data set)
      main: "Scenario 1 - a first-time user."
    test_cases:
      - ac: AC1                     # bare ("AC1") or full ("1.1.3.3.2-AC1")
        seq: 1
        technique: UC               # UC EP BVA DT ST ERR PW
        priority: P1                # P1 P2 P3
        area: Header & Filters
        title: ...
        objective: ...
        steps: |-
          1. ...
        expected: |-
          1. ...
        data: "**Field** = value"   # optional, default "-"
        pre_extra: "1+ open MO ..."  # optional, ONE line, auto-numbered after
                                     # pre_common (never re-state pre_common)
        post: "..."                  # optional, default post_default
        extra_covers: []             # optional AC ids also covered
        rules: [BR-XXXX-01]          # optional business rule ids
        terms: [serviceability]      # optional glossary slugs
        section: "Step 1 - Details"  # sheet section; same-section entries
                                     # must be contiguous, in run order
        continue_from: AC1/1         # <ac>/<seq> of the test case whose end
                                     # state this one starts from, or `start`
        run: Main                    # the run (worksheet) the case belongs to
        starts_at: step1-done        # declared state the case starts at; for a
                                     # `start` case it must be entry_state; else
                                     # it must equal the predecessor's ends_at
        ends_at: step1-done          # declared state the case leaves the app in
                                     # (a refusal / read-only check == starts_at)
        profile: main                # declared data profile of the case
        fresh_run: true              # optional: the predecessor's end state is
                                     # re-established by a replay (a fork)
        element_block: false         # optional (default true): false leaves off
                                     # the lettered element-verification block,
                                     # for an observation that does not visit
                                     # the AC's form
        confidence:                  # High | Medium | Low PER PART - how far
          scenario: High             # each workbook column is stated by the
          steps: High                # source rather than inferred
          data: Medium
          expected: Low
        remarks:                     # per part; required for Medium / Low,
          scenario: "Source: AC1."   # recommended evidence for High
          data: "Inferred: ... Verify: ..."
          expected: "Inferred: ... Verify: ..."
"""
import difflib
import os
import re
import subprocess
import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).parent))
from wiki import (ROOT, concept_text, fragment_hash_map, load_manifest,
                  prd_label, prd_versions_for, read_concept, refuse_if_schema1,
                  write_concept)
from wiki_coverage import (ELEMENT_BLOCK_LEAD, element_verification_block_multi,
                           load_coverage)

# Overridable so the gate/validation tests can point at fixture specs without
# adding fixtures to the real spec dir (which drives smoke's render loop).
SPEC_DIR = Path(os.environ.get("TC_SIT_SPEC_DIR")
                or Path(__file__).parent / "sit_specs")

SPEC_REQUIRED = ("story", "module", "figma", "out", "ac_prefix", "scenario_id",
                 "generator_version", "pre_common", "post_default",
                 "states", "entry_state", "profiles", "test_cases")
TC_REQUIRED = ("ac", "seq", "technique", "priority", "area", "title",
               "objective", "steps", "expected",
               # the flow contract: every test case sits in a sheet SECTION and
               # says which test case it continues from (or "start")
               "section", "continue_from",
               # the checkable chain: the run (worksheet) the case belongs to,
               # the declared state it starts and ends at, and its data profile
               "run", "starts_at", "ends_at", "profile",
               # the review contract: how far the expected result is grounded
               # in the source, so testers know where to look hardest
               "confidence")
TC_OPTIONAL = ("data", "pre_extra", "post", "extra_covers", "rules", "terms",
               "coverage_items", "fresh_run", "remarks", "element_block")
CONFIDENCE = ("High", "Medium", "Low")
CHAIN_START = "start"
CHAIN_KEYS = ("run", "starts_at", "ends_at", "profile")
_CHAIN_RE = re.compile(r"^(?P<ac>.+)/(?P<seq>\d+)$")
# Confidence is rated PER PART of a test case - one level and one remark for
# each workbook column a tester reviews (tc-style R7). The test case's overall
# level is the lowest of the four.
CONF_PARTS = ("scenario", "steps", "data", "expected")
CONF_LABELS = {"scenario": "Scenario", "steps": "Test Steps",
               "data": "Field / Values", "expected": "Expected Results"}
_CONF_RANK = {"Low": 0, "Medium": 1, "High": 2}


def confidence_errors(conf, rem, where):
    """Error strings for one test case's `confidence` / `remarks` mappings."""
    errs = []
    if not isinstance(conf, dict):
        return [f"{where}: confidence must map each of {list(CONF_PARTS)} to "
                f"High | Medium | Low, got {type(conf).__name__}"]
    if rem is not None and not isinstance(rem, dict):
        errs.append(f"{where}: remarks must be a mapping keyed by part "
                    f"{list(CONF_PARTS)}, got {type(rem).__name__}")
        rem = {}
    rem = rem or {}
    for k in list(conf) + list(rem):
        if k not in CONF_PARTS:
            errs.append(f"{where}: unknown confidence part '{k}'"
                        f"{_suggest(k, CONF_PARTS)}")
    for part in CONF_PARTS:
        lvl = conf.get(part)
        if lvl not in CONFIDENCE:
            errs.append(f"{where}: confidence.{part} is {lvl!r}, must be one of "
                        f"{list(CONFIDENCE)}")
        elif lvl != "High" and not str(rem.get(part) or "").strip():
            errs.append(f"{where}: confidence.{part} is {lvl} and needs "
                        f"remarks.{part} - what was inferred and what the "
                        f"tester must verify")
    return errs


def overall_confidence(conf):
    """The lowest part level: one weak part is where the review must go."""
    return min((conf[p] for p in CONF_PARTS), key=_CONF_RANK.__getitem__)


def confidence_parts(conf, rem):
    """{part: {level, remark}} in column order - the frontmatter form the
    export reads to build the AI Remarks cell."""
    rem = rem or {}
    return {p: {"level": conf[p], "remark": str(rem.get(p) or "").strip()}
            for p in CONF_PARTS}


def confidence_block(conf, rem):
    """The `# Confidence` section: overall level, then one line per part."""
    rem = rem or {}
    lines = [f"**{overall_confidence(conf)}** (lowest of the four parts)", ""]
    for p in CONF_PARTS:
        remark = str(rem.get(p) or "").strip() or "stated by the source."
        lines.append(f"- **{CONF_LABELS[p]}**: {conf[p]} - {remark}")
    return "\n".join(lines)
TECHNIQUES = {"UC", "EP", "BVA", "DT", "ST", "ERR", "PW"}
PRIORITIES = {"P1", "P2", "P3"}


def _show(path):
    """Repo-relative when possible — a spec dir can be pointed elsewhere via
    TC_SIT_SPEC_DIR, and relative_to() raises on anything outside ROOT."""
    try:
        return Path(path).relative_to(ROOT).as_posix()
    except ValueError:
        return str(path)


def _suggest(key, known):
    near = difflib.get_close_matches(str(key), [str(k) for k in known], n=1, cutoff=0.6)
    return f" — did you mean '{near[0]}'?" if near else ""


def _fail(header, errs):
    print(header, file=sys.stderr)
    for e in errs:
        print("  ERROR", e, file=sys.stderr)
    print(f"\n  {len(errs)} problem(s). Nothing was written.", file=sys.stderr)
    sys.exit(1)


def ac_id_of(spec, ac):
    """A bare 'AC5' takes the spec's ac_prefix; a full '1.1.3.3.2-AC1' is used
    as-is. Reproduces both legacy renderers exactly."""
    ac = str(ac)
    # Only a BARE PRD-style id ("AC5") takes the prefix. Any other id -- a full
    # PRD id ("1.1.3.3.2-AC1"), a human-stated "HS-01" or an interpreted
    # "4-1-1-3-AC01" -- names the story fragment as-is (lint L13 id shapes).
    return f"{spec['ac_prefix']}-{ac}" if re.fullmatch(r"AC\d+", ac) else ac


def validate_spec(spec, path):
    """Structural validation. Everything that can be checked without the wiki."""
    errs = []
    if not isinstance(spec, dict):
        _fail(f"SPEC INVALID: {path.name}", ["top level must be a mapping"])
    for k in spec:
        if k not in SPEC_REQUIRED:
            errs.append(f"unknown top-level key '{k}'{_suggest(k, SPEC_REQUIRED)}")
    for k in SPEC_REQUIRED:
        if k not in spec:
            errs.append(f"missing required top-level key '{k}'")
    states, profiles = spec.get("states"), spec.get("profiles")
    for name, val in (("states", states), ("profiles", profiles)):
        if name in spec and (not isinstance(val, dict) or not val):
            errs.append(f"{name} must be a non-empty mapping of name to text")
    states = states if isinstance(states, dict) else {}
    profiles = profiles if isinstance(profiles, dict) else {}
    es = spec.get("entry_state")
    if "entry_state" in spec and not isinstance(es, str):
        errs.append("entry_state must be the name of a declared state")
    elif "entry_state" in spec and es not in states:
        errs.append(f"entry_state '{spec['entry_state']}' is not declared in "
                    f"`states`{_suggest(spec['entry_state'], states)}")
    tcs = spec.get("test_cases")
    if not isinstance(tcs, list) or not tcs:
        errs.append("test_cases must be a non-empty list")
        tcs = []
    known_tc = TC_REQUIRED + TC_OPTIONAL
    seen = {}
    consumed = {}   # predecessor index -> index of the entry that linearly continued it
    for i, tc in enumerate(tcs):
        if not isinstance(tc, dict):
            errs.append(f"test_cases[{i}]: must be a mapping with named keys, "
                        f"not {type(tc).__name__}")
            continue
        where = f"test_cases[{i}] ({tc.get('ac', '?')}/seq {tc.get('seq', '?')})"
        for k in tc:
            if k not in known_tc:
                errs.append(f"{where}: unknown key '{k}'{_suggest(k, known_tc)}")
        for k in TC_REQUIRED:
            if k not in tc or tc[k] in (None, ""):
                errs.append(f"{where}: missing required key '{k}'")
        if tc.get("technique") and tc["technique"] not in TECHNIQUES:
            errs.append(f"{where}: technique '{tc['technique']}' not one of "
                        f"{sorted(TECHNIQUES)}{_suggest(tc['technique'], TECHNIQUES)}")
        if tc.get("priority") and tc["priority"] not in PRIORITIES:
            errs.append(f"{where}: priority '{tc['priority']}' not one of "
                        f"{sorted(PRIORITIES)}")
        if "seq" in tc and not isinstance(tc["seq"], int):
            errs.append(f"{where}: seq must be an integer, got {tc['seq']!r}")
        for lk in ("extra_covers", "rules", "terms", "coverage_items"):
            if lk in tc and tc[lk] is not None and not isinstance(tc[lk], list):
                errs.append(f"{where}: {lk} must be a list, got {type(tc[lk]).__name__}")
        if isinstance(tc.get("pre_extra"), str) and "\n" in tc["pre_extra"]:
            errs.append(f"{where}: pre_extra must be ONE line (tc-style R5: terse, "
                        f"data-critical setup only)")
        if isinstance(tc.get("pre_extra"), str) and re.match(r"^\s*\d+\.", tc["pre_extra"]):
            errs.append(f"{where}: pre_extra must NOT be numbered — the driver "
                        f"numbers it after pre_common")
        if tc.get("confidence") is not None:
            errs.extend(confidence_errors(tc["confidence"], tc.get("remarks"),
                                          where))
        if "fresh_run" in tc and not isinstance(tc["fresh_run"], bool):
            errs.append(f"{where}: fresh_run must be true or false")
        if "element_block" in tc and not isinstance(tc["element_block"], bool):
            errs.append(f"{where}: element_block must be true or false")
        for dk in ("starts_at", "ends_at"):
            if tc.get(dk) is not None and not isinstance(tc[dk], str):
                errs.append(f"{where}: {dk} must be a state name")
        cf = tc.get("continue_from")
        if cf is not None and cf != CHAIN_START and not _CHAIN_RE.match(str(cf)):
            errs.append(f"{where}: continue_from must be `{CHAIN_START}` or "
                        f"`<ac>/<seq>` of an earlier test case, got {cf!r}")
        key = (tc.get("ac"), tc.get("seq"))
        if key in seen:
            errs.append(f"{where}: duplicate (ac, seq) — already used by "
                        f"test_cases[{seen[key]}]")
        seen[key] = i
    # The chain: a test case continues from one that appears EARLIER in the
    # spec (spec order is run order), and a section's entries are contiguous
    # so the sheet can separate sections with one header row each.
    closed, cur = set(), None
    runs_closed, cur_run = set(), object()
    for i, tc in enumerate(tcs):
        if not isinstance(tc, dict):
            continue
        where = f"test_cases[{i}] ({tc.get('ac', '?')}/seq {tc.get('seq', '?')})"
        run = tc.get("run")
        if run != cur_run:
            # a run is one sheet: its entries sit together and its FIRST entry
            # starts from the beginning (later entries of a run may be further
            # starts, e.g. the single-case `Standalone checks` sheet)
            if run in runs_closed:
                errs.append(f"{where}: run '{run}' is not contiguous - its test "
                            f"cases must sit together, in run order")
            runs_closed.add(cur_run)
            cur_run = run
            if isinstance(run, str) and tc.get("continue_from") != CHAIN_START:
                errs.append(f"{where}: run '{run}' must begin with "
                            f"`continue_from: {CHAIN_START}` - each sheet is one "
                            f"flow and starts from the beginning")
        sec = (run, tc.get("section"))
        if sec != cur:
            if sec in closed:
                errs.append(f"{where}: section '{sec[1]}' is not contiguous - its "
                            f"test cases must sit together, in run order")
            closed.add(cur)
            cur = sec
        for key in ("starts_at", "ends_at"):
            if isinstance(tc.get(key), str) and tc[key] not in states:
                errs.append(f"{where}: {key} '{tc[key]}' is not declared in "
                            f"`states`{_suggest(tc[key], states)}")
        if tc.get("profile") is not None and not isinstance(tc["profile"], str):
            errs.append(f"{where}: profile must be a profile name")
        elif isinstance(tc.get("profile"), str) and tc["profile"] not in profiles:
            errs.append(f"{where}: profile '{tc['profile']}' is not declared in "
                        f"`profiles`{_suggest(tc['profile'], profiles)}")
        if tc.get("continue_from") == CHAIN_START:
            if tc.get("starts_at") != spec.get("entry_state"):
                errs.append(f"{where}: a `start` test case must begin at the "
                            f"spec's entry_state '{spec.get('entry_state')}', "
                            f"not '{tc.get('starts_at')}'")
        m = _CHAIN_RE.match(str(tc.get("continue_from") or ""))
        if m:
            ref = (m.group("ac"), int(m.group("seq")))
            j = seen.get(ref)
            if j is None:
                errs.append(f"{where}: continue_from '{tc['continue_from']}' "
                            f"names no test case in this spec")
            elif j >= i:
                errs.append(f"{where}: continue_from '{tc['continue_from']}' "
                            f"must appear EARLIER in the spec (run order)")
            else:
                pred = tcs[j]
                if pred.get("run") != tc.get("run"):
                    errs.append(f"{where}: continue_from {tc['continue_from']} is in "
                                f"run '{pred.get('run')}' - a flow never continues "
                                f"from another sheet; use start and walk this flow "
                                f"from the beginning")
                if pred.get("ends_at") != tc.get("starts_at"):
                    errs.append(f"{where}: continue_from {tc['continue_from']} "
                                f"ends at '{pred.get('ends_at')}' but this test "
                                f"case starts at '{tc.get('starts_at')}'")
                if not tc.get("fresh_run"):
                    if j in consumed:
                        o = tcs[consumed[j]]
                        errs.append(f"{where}: {tc['continue_from']} is already "
                                    f"continued by {o.get('ac')}/{o.get('seq')} - a "
                                    f"second test case from the same state needs "
                                    f"`fresh_run: true`")
                    else:
                        consumed[j] = i
                    if pred.get("profile") != tc.get("profile"):
                        errs.append(f"{where}: profile '{tc.get('profile')}' differs "
                                    f"from {tc['continue_from']}'s "
                                    f"'{pred.get('profile')}' - a different data set "
                                    f"needs `fresh_run: true` or `continue_from: start`")
    if any(isinstance(t, dict) and all(k not in t or t[k] in (None, "")
                                       for k in CHAIN_KEYS) for t in tcs):
        errs.append("this spec predates declared states: declare top-level "
                    "`states`, `profiles` and `entry_state`, and add `run`, "
                    "`starts_at`, `ends_at` and `profile` to every test case "
                    "(see the module docstring)")
    if errs:
        _fail(f"SPEC INVALID: {_show(path)}", errs)


def tc_id_for(spec, ac_id, seq):
    """config ids.tc_format shape `<story_num>-AC<nn>-<seq>`. A PRD-style id
    supplies its own story number ("1.1.3.3.2-AC1" -> "1.1.3.3.2-AC01-01",
    byte-identical to the legacy renderers). An id with no "-AC" segment
    (human-stated "HS-01", lint L13) takes the spec's ac_prefix as the story
    number and its trailing digits as the AC ordinal ("1.1-AC01-01")."""
    m = re.search(r"-AC(\d+)$", ac_id)
    if m:
        return f"{ac_id[:m.start()]}-AC{int(m.group(1)):02d}-{seq:02d}"
    m = re.search(r"(\d+)$", ac_id)
    if not m:
        sys.exit(f"render_sit: cannot derive a TC id from AC id {ac_id!r} "
                 f"(no trailing number)")
    return f"{spec['ac_prefix']}-AC{int(m.group(1)):02d}-{seq:02d}"


def validate_against_story(spec, story_fm, story_id):
    """Every AC / rule / extra_cover id the spec names must exist in the story.
    lint L2 would catch these later; catching them here names the offending
    test_cases index and suggests the correct id."""
    ac_ids = {a["id"] for a in story_fm.get("acceptance_criteria") or []}
    br_ids = {r["id"] for r in story_fm.get("business_rules") or []}
    errs = []
    for i, tc in enumerate(spec["test_cases"]):
        where = f"test_cases[{i}] ({tc.get('ac')}/seq {tc.get('seq')})"
        aid = ac_id_of(spec, tc["ac"])
        if aid not in ac_ids:
            errs.append(f"{where}: AC '{aid}' does not exist in {story_id}"
                        f"{_suggest(aid, ac_ids)}")
        for r in tc.get("rules") or []:
            if r not in br_ids:
                errs.append(f"{where}: rule '{r}' does not exist in {story_id}"
                            f"{_suggest(r, br_ids)}")
        for x in tc.get("extra_covers") or []:
            if x not in ac_ids and x not in br_ids:
                errs.append(f"{where}: extra_covers '{x}' is neither an AC nor a "
                            f"business rule of {story_id}{_suggest(x, ac_ids | br_ids)}")
    if errs:
        _fail(f"SPEC does not match {story_id}", errs)


def coverage_item_errors(spec, story_fm, story_id):
    """Every coverage_items id must exist in the story's asserted test_model.

    A story with no test_model yet is NOT an error here: it has not been
    migrated, and the engine refuses on it at its own boundary. Failing the
    render would block generation on every unmigrated story.

    A story that HAS a test_model is checked even when its item list is empty.
    Skipping on an empty `known` set conflated "not migrated yet" with "the
    model identifies nothing", so a spec naming BVA-01 against
    `test_model: {items: []}` rendered silently. The presence of the block, not
    the size of the list, is what says the refs are checkable.
    """
    from wiki_rubric import load_test_model
    items, _status = load_test_model(story_fm)
    has_model = isinstance((story_fm or {}).get("test_model"), dict)
    known = {i.get("id") for i in items if isinstance(i, dict)}
    errs = []
    for i, tc in enumerate(spec["test_cases"]):
        where = f"test_cases[{i}] ({tc.get('ac')}/seq {tc.get('seq')})"
        ci = tc.get("coverage_items")
        if ci is None:
            continue
        if not isinstance(ci, list):
            errs.append(f"{where}: coverage_items must be a list, "
                        f"got {type(ci).__name__}")
            continue
        if not has_model:
            continue
        for c in ci:
            if c not in known:
                errs.append(f"{where}: coverage_items '{c}' is not in the "
                            f"test_model of {story_id}{_suggest(c, known)}")
    return errs


def chain_line(tc, pred_id, state_text):
    """The line that makes the set a FLOW: where this test case starts. The
    export lifts it to the top of the Test Steps cell (tc-style R6)."""
    if pred_id is None:
        return "Start of run: no test case to continue from."
    how = " (fresh run replayed to this point)" if tc.get("fresh_run") else ""
    return f"Continue from TC-{pred_id}{how}: {state_text}"


def build_pre(spec, tc, chain=None):
    """tc-style R5: pre_common verbatim on every TC (so the export lifts it into
    the sheet's single blue block), then the chain line, then at most one
    auto-numbered extra."""
    pre = spec["pre_common"]
    n = len(pre.splitlines())
    for line in (chain, tc.get("pre_extra")):
        if line:
            n += 1
            pre = f"{pre}\n{n}. {line}"
    return pre


def with_element_block(story_fm, expected, ac_ids):
    """Append the org-style element-verification block as the final numbered
    Expected item, covering the union of the story ACs this TC covers."""
    block = element_verification_block_multi(story_fm, ac_ids)
    if not block:
        return expected
    nums = [int(x) for x in re.findall(r"(?m)^(\d+)\.", expected)]
    n = (max(nums) + 1) if nums else 1
    return f"{expected}\n{n}. {ELEMENT_BLOCK_LEAD}\n{block}"


def expected_results(story_fm, tc, ac_ids):
    """The Expected Results text: the case's own items, plus the element block
    unless the entry says `element_block: false` (an observation that does not
    visit the AC's form must not list that form's controls)."""
    if tc.get("element_block") is False:
        return tc["expected"]
    return with_element_block(story_fm, tc["expected"], ac_ids)


def provenance(story_fms, manifest, figma_hashes, wiki_commit, generator_version):
    """The `generated_from` block of a rendered test case. `prd_versions`
    maps each PRD the given stories cite to its adopted version - one story
    for SIT, every story of the flow for UAT; {} when none cites a PRD."""
    return {"prd_versions": prd_versions_for(story_fms, manifest),
            "figma_hashes": figma_hashes,
            "wiki_commit": wiki_commit,
            "generator_version": generator_version}


def trace_source(generated_from, manifest=None):
    """The tail of the Traceability line: the PRDs and versions, then the
    wiki commit. With the manifest, a PRD the registry does not hold is
    named as unregistered instead of as one with nothing adopted."""
    return (f"{prd_label(generated_from['prd_versions'], manifest)} · "
            f"wiki {generated_from['wiki_commit']}")


def write_test_case(path, fm, body):
    """Write a rendered test case, unless the file already holds this text
    apart from the wiki commit it was rendered at. Returns True when written.

    A forced render stamps the current HEAD into `generated_from.wiki_commit`
    and the Traceability tail of every test case of the story or flow. Left
    like that, rewording one title would change the bytes, and so the sealed
    hash, of all of them, and every compiled workbook would report the whole
    set as changed. A file whose content did not change keeps the commit it
    was last rendered at."""
    if path.exists():
        old_fm, _old_body = read_concept(path)
        new = fm["generated_from"]["wiki_commit"]
        old = ((old_fm or {}).get("generated_from") or {}).get("wiki_commit")
        tail = f" · wiki {new}\n"
        if isinstance(old, str) and old and body.endswith(tail):
            kept = concept_text(
                dict(fm, generated_from=dict(fm["generated_from"],
                                             wiki_commit=old)),
                body[:-len(tail)] + f" · wiki {old}\n")
            if path.read_bytes() == kept.encode("utf-8"):
                return False
    write_concept(path, fm, body)
    return True


def render(story_id, force=False, allow_unconfirmed=False):
    spec_path = SPEC_DIR / f"{story_id}.yaml"
    if not spec_path.exists():
        have = sorted(p.stem for p in SPEC_DIR.glob("*.yaml"))
        sys.exit(f"render_sit: no spec at "
                 f"{_show(spec_path)}\n"
                 f"  specs available: {', '.join(have) or '(none)'}")
    spec = yaml.safe_load(spec_path.read_text(encoding="utf-8"))
    validate_spec(spec, spec_path)

    manifest = load_manifest()
    story_rel = spec["story"].lstrip("/").removesuffix(".md")
    story_fm, _body = read_concept(ROOT / (story_rel + ".md"))
    if not story_fm:
        sys.exit(f"render_sit: story {spec['story']} not found")

    # --- the coverage fence (tc-generate-sit step 2d) ---------------------
    # Checked BEFORE content validation: authority to render at all comes first;
    # whether the content is well-formed is only interesting once it may be written.
    # Expected Results embed the element-verification block derived from the
    # coverage_map. Rendering against a map the human has not corrected bakes
    # the name-matching heuristic's mistakes into tester-facing TCs. This was
    # previously a prose "Red flag — STOP" in the skill and enforced nowhere.
    _cmap, _disp, cov_status = load_coverage(story_fm)
    if cov_status != "confirmed" and not allow_unconfirmed:
        sys.exit(
            f"render_sit REFUSED: {story_id} coverage_status is "
            f"'{cov_status or 'absent'}', not 'confirmed'.\n"
            f"  A human must confirm the coverage card before any TC is written\n"
            f"  (tc-generate-sit step 2d — the confirmation IS the assertion event).\n"
            f"  Next: py tools/wiki.py coverage --story {story_id} --propose\n"
            f"  Override only if you are NOT substituting for that confirmation:\n"
            f"    --allow-unconfirmed-coverage")

    validate_against_story(spec, story_fm, story_id)

    ci_errs = coverage_item_errors(spec, story_fm, story_id)
    if ci_errs:
        _fail(f"SPEC coverage_items do not match {story_id}'s test_model",
              ci_errs)

    out = ROOT / spec["out"]
    story_ref = spec["story"]
    figma_stem = spec["figma"]
    if figma_stem and f"figma#{figma_stem}" not in manifest["sources"]:
        known = sorted(k.split("#", 1)[1] for k in manifest["sources"]
                       if k.startswith("figma#"))
        sys.exit(
            f"REFUSED: spec figma '{figma_stem}' names no ingested Figma page.\n"
            f"  Ingested pages: {', '.join(known) if known else '(none)'}\n"
            f"  A story with no screen (a batch component) sets `figma: null`;\n"
            f"  do not invent a page name to satisfy this key.")
    wiki_commit = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT,
                                 capture_output=True, text=True).stdout.strip()
    generated_from = provenance(
        [story_fm], manifest,
        # `figma: null` is legitimate: a batch story has no screen to pin.
        ({figma_stem: manifest["sources"][f"figma#{figma_stem}"]["image_hash"]}
         if figma_stem else {}),
        wiki_commit, spec["generator_version"])

    def binding_of(scenario_id):
        return manifest.get("bindings", {}).get(scenario_id)

    def fragments_unchanged(scenario_id):
        """Spec §7.4-3: existing ACTIVE binding + unchanged fragment hashes ->
        untouched. Also keeps `generated_from.wiki_commit` from churning."""
        binding = binding_of(scenario_id)
        if not binding or binding.get("status") != "active":
            return False
        if not (ROOT / (binding["tc"] + ".md")).exists():
            return False
        for fragref, pin in binding.get("fragment_pins", {}).items():
            tgt, frag = fragref.split("#")
            tfm, _ = read_concept(ROOT / (tgt + ".md"))
            if fragment_hash_map(tfm).get(frag) != pin:
                return False
        return True

    def id_of(t):
        aid = ac_id_of(spec, t["ac"])
        b_ = binding_of(spec["scenario_id"].format(ac=t["ac"], ac_id=aid,
                                                   seq=t["seq"]))
        return Path(b_["tc"]).name if b_ else tc_id_for(spec, aid, t["seq"])

    by_key = {(str(t["ac"]), t["seq"]): t for t in spec["test_cases"]}

    # --- the raise ratchet: only a human answer raises a level ------------
    # Every entry with an existing file is checked, skipped or not, forced or
    # not, before anything is written. There is no override.
    import wiki_doubts   # lazy: wiki_doubts imports this module
    lifts = wiki_doubts.load_lifts()
    raised = []
    for tc in spec["test_cases"]:
        sid = spec["scenario_id"].format(
            ac=tc["ac"], ac_id=ac_id_of(spec, tc["ac"]), seq=tc["seq"])
        b = binding_of(sid)
        if b and b.get("status") != "retired":
            raised.extend(wiki_doubts.raise_errors(
                wiki_doubts.existing_fm(b), tc["confidence"], sid,
                story=story_id))
    if raised:
        _fail(f"render_sit REFUSED: confidence raised without a human answer "
              f"in {story_id}", raised)

    count = skipped = same = 0
    suppressed = []
    for order, tc in enumerate(spec["test_cases"], 1):
        ac, seq = tc["ac"], tc["seq"]
        m = _CHAIN_RE.match(str(tc["continue_from"]))
        pred = by_key[(m.group("ac"), int(m.group("seq")))] if m else None
        pred_id = id_of(pred) if pred else None
        state_text = spec["states"][tc["starts_at"]] if pred else None
        ac_id = ac_id_of(spec, ac)
        sc_id = spec["scenario_id"].format(ac=ac, ac_id=ac_id, seq=seq)
        b = binding_of(sc_id)
        # spec §7.4-2: an existing scenario binding owns the TC ID permanently
        tc_id = Path(b["tc"]).name if b else tc_id_for(spec, ac_id, seq)
        if b and b.get("status") == "retired":
            # spec §7.4-4: never resurrect — requires explicit `wiki unretire`
            suppressed.append(f"{sc_id} suppressed — prior TC {tc_id} retired")
            continue
        conf, rem, lifted = wiki_doubts.effective_confidence(
            tc["confidence"], tc.get("remarks"), sc_id,
            {p: wiki_doubts.part_basis("sit", tc, p) for p in CONF_PARTS},
            lifts)
        if not force and fragments_unchanged(sc_id) and not wiki_doubts.lift_changed(
                b, lifted):
            skipped += 1
            continue

        xcov = list(tc.get("extra_covers") or [])
        rules = list(tc.get("rules") or [])
        terms = list(tc.get("terms") or [])
        covers = [f"{story_ref}#{ac_id}"] + [f"{story_ref}#{x}" for x in xcov]
        fm = {
            "type": "Test Case",
            "id": tc_id,
            "title": tc["title"],
            "description": tc["objective"],
            "kind": "sit",
            "module": spec["module"],
            "area": tc["area"],
            "status": "active",
            "origin": "agent-proposed",
            "covers": covers,
            # 29119-4 test coverage items this TC exercises. Distinct from
            # `covers` above, which holds AC refs (the test basis).
            "coverage_items": list(tc.get("coverage_items") or []),
            "verifies_rules": [f"{story_ref}#{r}" for r in rules],
            "uses_terms": [f"/glossary/{t}.md" for t in terms],
            "technique": tc["technique"],
            "scenario_id": sc_id,
            "priority": tc["priority"],
            "run": tc["run"],
            "section": tc["section"],
            "order": order,
            "continue_from": pred_id,
            "fresh_run": bool(tc.get("fresh_run")),
            "confidence": overall_confidence(conf),
            "confidence_parts": wiki_doubts.merge_lifted(
                confidence_parts(conf, rem), lifted),
            "generated_from": generated_from,
            "stale_because": [],
        }
        trace = "- Covers: " + ", ".join(covers)
        if rules:
            trace += "\n- Verifies rules: " + ", ".join(rules)
        trace += (f"\n- Scenario: {sc_id} · Technique: {tc['technique']} · "
                  f"{trace_source(generated_from, manifest)}")
        body = (f"# Objective\n\n{tc['objective']}\n\n"
                f"# Preconditions\n\n"
                f"{build_pre(spec, tc, chain_line(tc, pred_id, state_text))}\n\n"
                f"# Test Data\n\n{tc.get('data') or '-'}\n\n"
                f"# Steps\n\n{tc['steps']}\n\n"
                f"# Expected Results\n\n"
                f"{expected_results(story_fm, tc, [ac_id] + xcov)}\n\n"
                f"# Postconditions\n\n{tc.get('post') or spec['post_default']}\n\n"
                f"# Confidence\n\n"
                f"{confidence_block(conf, rem)}\n\n"
                f"# Traceability\n\n{trace}\n")
        if write_test_case(out / f"{tc_id}.md", fm, body):
            count += 1
        else:
            same += 1

    for s in suppressed:
        print("SUPPRESSED", s)
    print(f"rendered {count}, untouched {skipped} (fragments unchanged), "
          + (f"unchanged {same} (same text), " if same else "")
          + f"suppressed {len(suppressed)} -> {out.relative_to(ROOT)}")


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if "--story" not in argv:
        have = sorted(p.stem for p in SPEC_DIR.glob("*.yaml"))
        sys.exit("usage: py tools/render_sit.py --story <STORY-ID> [--force] "
                 "[--allow-unconfirmed-coverage]\n"
                 f"  specs available: {', '.join(have) or '(none)'}")
    refuse_if_schema1(load_manifest(), "render_sit")
    story_id = argv[argv.index("--story") + 1]
    render(story_id,
           force="--force" in argv,
           allow_unconfirmed="--allow-unconfirmed-coverage" in argv)


if __name__ == "__main__":
    main()
