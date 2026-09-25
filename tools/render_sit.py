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
"""
import difflib
import os
import re
import subprocess
import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).parent))
from wiki import (ROOT, fragment_hash_map, load_manifest, read_concept,
                  write_concept)
from wiki_coverage import element_verification_block_multi, load_coverage

# Overridable so the gate/validation tests can point at fixture specs without
# adding fixtures to the real spec dir (which drives smoke's render loop).
SPEC_DIR = Path(os.environ.get("TC_SIT_SPEC_DIR")
                or Path(__file__).parent / "sit_specs")

SPEC_REQUIRED = ("story", "module", "figma", "out", "ac_prefix", "scenario_id",
                 "generator_version", "pre_common", "post_default", "test_cases")
TC_REQUIRED = ("ac", "seq", "technique", "priority", "area", "title",
               "objective", "steps", "expected")
TC_OPTIONAL = ("data", "pre_extra", "post", "extra_covers", "rules", "terms",
               "coverage_items")
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
    return ac if "-AC" in str(ac) else f"{spec['ac_prefix']}-{ac}"


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
    tcs = spec.get("test_cases")
    if not isinstance(tcs, list) or not tcs:
        errs.append("test_cases must be a non-empty list")
        tcs = []
    known_tc = TC_REQUIRED + TC_OPTIONAL
    seen = {}
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
        key = (tc.get("ac"), tc.get("seq"))
        if key in seen:
            errs.append(f"{where}: duplicate (ac, seq) — already used by "
                        f"test_cases[{seen[key]}]")
        seen[key] = i
    if errs:
        _fail(f"SPEC INVALID: {_show(path)}", errs)


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


def build_pre(spec, tc):
    """tc-style R5: pre_common verbatim on every TC (so the export lifts it into
    the sheet's single blue block), plus at most one auto-numbered extra."""
    pre = spec["pre_common"]
    extra = tc.get("pre_extra")
    if extra:
        return f"{pre}\n{len(pre.splitlines()) + 1}. {extra}"
    return pre


def with_element_block(story_fm, expected, ac_ids):
    """Append the org-style element-verification block as the final numbered
    Expected item, covering the union of the story ACs this TC covers."""
    block = element_verification_block_multi(story_fm, ac_ids)
    if not block:
        return expected
    nums = [int(x) for x in re.findall(r"(?m)^(\d+)\.", expected)]
    n = (max(nums) + 1) if nums else 1
    return (f"{expected}\n{n}. The following elements are displayed and "
            f"labelled correctly:\n{block}")


def build_tc(spec, story_fm, tc, tc_id, sc_id, ac_id, generated_from, wiki_commit):
    """(fm, body) of one rendered SIT test case, with `wiki_commit` as its
    provenance (in `generated_from.wiki_commit` and the Traceability line).
    Takes the commit as a parameter so a forced re-render can compare against
    the file on disk under the file's OWN commit (see provenance_only_change).
    `generated_from` is copied, never mutated."""
    story_ref = spec["story"]
    xcov = list(tc.get("extra_covers") or [])
    rules = list(tc.get("rules") or [])
    terms = list(tc.get("terms") or [])
    covers = [f"{story_ref}#{ac_id}"] + [f"{story_ref}#{x}" for x in xcov]
    gen = dict(generated_from, wiki_commit=wiki_commit)
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
        "generated_from": gen,
        "stale_because": [],
    }
    trace = "- Covers: " + ", ".join(covers)
    if rules:
        trace += "\n- Verifies rules: " + ", ".join(rules)
    trace += (f"\n- Scenario: {sc_id} · Technique: {tc['technique']} · "
              f"PRD v{gen['prd_version']} · wiki {wiki_commit}")
    body = (f"# Objective\n\n{tc['objective']}\n\n"
            f"# Preconditions\n\n{build_pre(spec, tc)}\n\n"
            f"# Test Data\n\n{tc.get('data') or '-'}\n\n"
            f"# Steps\n\n{tc['steps']}\n\n"
            f"# Expected Results\n\n"
            f"{with_element_block(story_fm, tc['expected'], [ac_id] + xcov)}\n\n"
            f"# Postconditions\n\n{tc.get('post') or spec['post_default']}\n\n"
            f"# Traceability\n\n{trace}\n")
    return fm, body


# The provenance token of the Traceability line: "... · wiki <sha>" at its end.
_WIKI_TOKEN = re.compile(r"(?m)^(- Scenario: .* · wiki )(\S*)$")


def _without_provenance(fm, body):
    fm = dict(fm)
    fm["generated_from"] = dict(fm.get("generated_from") or {}, wiki_commit=None)
    return fm, _WIKI_TOKEN.sub(r"\g<1>", body or "")


def provenance_only_change(prev_fm, prev_body, new_fm, new_body):
    """True when (prev_fm, prev_body) and (new_fm, new_body) differ at most in
    their provenance: `generated_from.wiki_commit` and the `wiki <sha>` token
    of the Traceability line. Such a test case is NOT rewritten by a forced
    re-render: HEAD moves between renders (seal, draft export and patch all
    commit), and rewriting only the commit would move every sealed hash - no
    carry-forward, every case "Changed Traceability" in the diff, and a
    regression restore that never reproduces round 1's digest."""
    if not isinstance(prev_fm, dict) or not isinstance(new_fm, dict):
        return False
    return _without_provenance(prev_fm, prev_body) == \
        _without_provenance(new_fm, new_body)


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
    generated_from = {
        "prd_version": manifest["adopted_prd_version"],
        # `figma: null` is legitimate: a batch story has no screen to pin.
        "figma_hashes": (
            {figma_stem: manifest["sources"][f"figma#{figma_stem}"]["image_hash"]}
            if figma_stem else {}),
        "wiki_commit": wiki_commit,
        "generator_version": spec["generator_version"],
    }

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

    count = skipped = 0
    suppressed = []
    for tc in spec["test_cases"]:
        ac, seq = tc["ac"], tc["seq"]
        ac_id = ac_id_of(spec, ac)
        sc_id = spec["scenario_id"].format(ac=ac, ac_id=ac_id, seq=seq)
        b = binding_of(sc_id)
        # spec §7.4-2: an existing scenario binding owns the TC ID permanently
        tc_id = (Path(b["tc"]).name if b else
                 f"{ac_id.rsplit('-AC', 1)[0]}-AC"
                 f"{int(ac_id.rsplit('-AC', 1)[1]):02d}-{seq:02d}")
        if b and b.get("status") == "retired":
            # spec §7.4-4: never resurrect — requires explicit `wiki unretire`
            suppressed.append(f"{sc_id} suppressed — prior TC {tc_id} retired")
            continue
        if not force and fragments_unchanged(sc_id):
            skipped += 1
            continue

        fm, body = build_tc(spec, story_fm, tc, tc_id, sc_id, ac_id,
                            generated_from, wiki_commit)
        path = out / f"{tc_id}.md"
        if path.exists():
            # An unchanged test case is not rewritten, forced or not: built
            # under the file's own commit it would equal the file, so only
            # the provenance would move - and with it the sealed hash.
            prev_fm, prev_body = read_concept(path)
            if provenance_only_change(prev_fm, prev_body, fm, body):
                skipped += 1
                continue
        write_concept(path, fm, body)
        count += 1

    for s in suppressed:
        print("SUPPRESSED", s)
    print(f"rendered {count}, untouched {skipped} (fragments or content "
          f"unchanged), suppressed {len(suppressed)} -> {out.relative_to(ROOT)}")


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if "--story" not in argv:
        have = sorted(p.stem for p in SPEC_DIR.glob("*.yaml"))
        sys.exit("usage: py tools/render_sit.py --story <STORY-ID> [--force] "
                 "[--allow-unconfirmed-coverage]\n"
                 f"  specs available: {', '.join(have) or '(none)'}")
    story_id = argv[argv.index("--story") + 1]
    render(story_id,
           force="--force" in argv,
           allow_unconfirmed="--allow-unconfirmed-coverage" in argv)


if __name__ == "__main__":
    main()
