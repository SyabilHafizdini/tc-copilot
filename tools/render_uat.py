#!/usr/bin/env python3
"""Shared UAT render driver - one engine, one validated data spec per flow.

Replaces the per-flow `render_<flow>_uat.py` copies. One test case per journey
entry of a flow, each starting exactly where the previous one ended. The
journey is the asserted `journey:` of flows/<FLOW>.md; the spec
`tools/uat_specs/<FLOW>.yaml` contributes WORDING only (area, priority, title,
objective, steps, expected) and never decides which entries exist. The spec
declares top-level `profiles` (name: description of the data set) and every
entry names its `profile`; an entry that continues its predecessor
(`continue_from`, else the previous entry) with another profile, or a state a
second entry already continues, must carry `fresh_run: true`: the run is
replayed to that point and the precondition is worded
`Continue from TC-<id> (fresh run replayed to this point)`. That one value
also sets the frontmatter `fresh_run`.
A journey `end_state` written as a place ("the Orders page") is worded
`user is at the Orders page.`; one written as a sentence (ending in a full
stop) is carried verbatim.
Re-running on an unchanged wiki prints `rendered 0`.

`module` is optional. A test case with a module lands on that module's
workbook sheet; without one it lands on its flow's sheet, so omit `module`
for one sheet per flow.

`confidence` and `remarks` on an entry are accepted and shape-checked but NOT
rendered: this base has no confidence machinery. They are kept in the format
so a spec written here stays valid on a platform that renders them.

Run:
    py tools/render_uat.py --flow <FLOW-ID> [--force]

Fences (tc-generate-uat hard rules):
  * every member story must be `coverage_status: confirmed` - the element
    lists in Expected Results are read straight from the confirmed
    coverage_map, so an uncorrected map would become tester-facing text;
  * the flow must carry a `journey:` (proposed and asserted in tc-align).

TC_UAT_FIXTURE_DIR (smoke.py only) points at a directory holding flow.md and
story.md; every story ref then resolves to that story.md so the fence can be
proven in any bundle. TC_UAT_SPEC_DIR overrides the spec directory.
"""
import os
import re
import subprocess
import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).parent))
from wiki import (ROOT, covmap_hash, fragment_hash_map, load_config,
                  load_manifest, read_concept, resolve_ref, write_concept)
from wiki_coverage import element_verification_block, load_coverage
from render_sit import provenance_only_change

SPEC_DIR = Path(os.environ.get("TC_UAT_SPEC_DIR") or Path(__file__).parent / "uat_specs")
SPEC_REQUIRED = ("flow", "out", "story_num", "scenario_id",
                 "generator_version", "profiles", "entries")
SPEC_OPTIONAL = ("module",)
ENTRY_REQUIRED = ("area", "priority", "title", "objective", "steps", "expected",
                  "profile")
ENTRY_OPTIONAL = ("alts", "continue_from", "fresh_run", "confidence", "remarks")
CONF_PARTS = ("scenario", "steps", "data", "expected")
CONF_LEVELS = ("High", "Medium", "Low")
PRIORITIES = {"P1", "P2", "P3"}
TEST_DATA = "-"   # tc-style: the chained precondition fills Field / Values


# ---------------------------------------------------------------- engine
def _fail(msg):
    print(msg, file=sys.stderr)
    sys.exit(1)


def load_scope(flow_ref):
    """(flow_fm, story_loader) honouring TC_UAT_FIXTURE_DIR for smoke.py."""
    fixture = os.environ.get("TC_UAT_FIXTURE_DIR")
    if fixture:
        fdir = ROOT / fixture
        flow_fm, _ = read_concept(fdir / "flow.md")

        def story_of(ref):
            fm, _b = read_concept(fdir / "story.md")
            return resolve_ref(ref)[0], fm
    else:
        flow_fm, _ = read_concept(ROOT / flow_ref.lstrip("/"))

        def story_of(ref):
            rel = resolve_ref(ref)[0]
            p = ROOT / (rel + ".md")
            fm, _b = read_concept(p) if p.exists() else (None, "")
            return rel, fm
    return flow_fm, story_of


def tc_id(cfg, story_num, ac_id, seq):
    m = re.search(r"AC(\d+)$", ac_id) or re.search(r"(\d+)$", ac_id)
    if not m:
        _fail(f"render UAT: cannot derive an id from AC {ac_id!r}")
    return cfg["ids"]["tc_format_uat"].format(story_num=story_num,
                                              ac_num=int(m.group(1)), seq=seq)


def display_id(wiki_id):
    return "TC-" + wiki_id.removeprefix("UAT-")


def state_clause(end_state):
    """The chained-precondition wording of a journey end_state: a sentence
    (ends in a full stop) verbatim, a place as `user is at <place>.`."""
    s = str(end_state or "").strip()
    return s if s.endswith(".") else f"user is at {s}."


def state_sentence(end_state):
    """The Postconditions wording: the end_state with exactly one full stop."""
    s = str(end_state or "").strip()
    return s if s.endswith(".") else f"{s}."


def prd_label(version):
    return f"PRD v{version}" if version is not None else "no PRD"


def with_element_block(story_fm, expected, ac_id):
    block = element_verification_block(story_fm, ac_id)
    if not block:
        return expected
    nums = [int(x) for x in re.findall(r"(?m)^(\d+)\.", expected)]
    n = (max(nums) + 1) if nums else 1
    return (f"{expected}\n{n}. The following elements are displayed and "
            f"labelled correctly:\n{block}")


def confidence_errors(conf, rem, where):
    """Shape check only - the levels are not rendered on this base."""
    errs = []
    if not isinstance(conf, dict):
        return [f"{where}: confidence must be a mapping of "
                f"{', '.join(CONF_PARTS)} to {' | '.join(CONF_LEVELS)}"]
    rem = rem if isinstance(rem, dict) else {}
    for p in CONF_PARTS:
        if p not in conf:
            errs.append(f"{where}: missing confidence.{p}")
        elif conf[p] not in CONF_LEVELS:
            errs.append(f"{where}: confidence.{p} must be one of "
                        f"{' | '.join(CONF_LEVELS)}, got {conf[p]!r}")
        elif conf[p] != "High" and not str(rem.get(p) or "").strip():
            errs.append(f"{where}: confidence.{p} is {conf[p]} - say why in "
                        f"remarks.{p}")
    for p in conf:
        if p not in CONF_PARTS:
            errs.append(f"{where}: unknown confidence part '{p}'")
    return errs


def validate_uat_spec(spec, path):
    errs = []
    if not isinstance(spec, dict):
        errs.append("spec is not a mapping")
        spec = {}
    for k in spec:
        if k not in SPEC_REQUIRED + SPEC_OPTIONAL:
            errs.append(f"unknown top-level key '{k}'")
    for k in SPEC_REQUIRED:
        if k not in spec:
            errs.append(f"missing required top-level key '{k}'")
    entries = spec.get("entries") or {}
    if not isinstance(entries, dict):
        errs.append("entries is not a mapping")
        entries = {}
    profiles = spec.get("profiles")
    if "profiles" in spec and not (isinstance(profiles, dict) and profiles):
        errs.append("profiles must be a non-empty mapping of profile name to "
                    "description")
        profiles = {}
    profiles = profiles or {}
    seen = {}   # entries already walked, in spec order
    consumed = {}   # predecessor id -> entry that linearly continued it
    prev_id = None
    for jid, e in entries.items():
        where = f"entries.{jid}"
        if not isinstance(e, dict):
            errs.append(f"{where}: not a mapping")
            continue
        for k in e:
            if k not in ENTRY_REQUIRED + ENTRY_OPTIONAL:
                errs.append(f"{where}: unknown key '{k}'")
        for k in ENTRY_REQUIRED:
            if not e.get(k):
                errs.append(f"{where}: missing required key '{k}'")
        if e.get("priority") and e["priority"] not in PRIORITIES:
            errs.append(f"{where}: priority must be one of "
                        f"{', '.join(sorted(PRIORITIES))}")
        if e.get("confidence") is not None:
            errs.extend(confidence_errors(e["confidence"], e.get("remarks"), where))
        if "alts" in e and not (isinstance(e["alts"], list)
                                and all(isinstance(a, str) for a in e["alts"])):
            errs.append(f"{where}: alts must be a list of test_model item ids")
        prof = e.get("profile")
        if prof and not isinstance(prof, str):
            errs.append(f"{where}: profile must be a profile name")
        elif prof and profiles and prof not in profiles:
            errs.append(f"{where}: profile '{prof}' is not declared in "
                        f"`profiles`")
        if "fresh_run" in e and not isinstance(e["fresh_run"], bool):
            errs.append(f"{where}: fresh_run must be true or false")
        cont = e.get("continue_from")
        pred = None   # effective predecessor: explicit continue_from, else the previous entry
        if cont is not None:
            if not isinstance(cont, str):
                errs.append(f"{where}: continue_from must be an entry id")
            elif cont not in seen:
                errs.append(f"{where}: continue_from '{cont}' is not an "
                            f"earlier entry of this spec")
            else:
                pred = cont
        else:
            pred = prev_id
        if pred is not None and e.get("fresh_run") is not True:
            pp = seen[pred].get("profile")
            if isinstance(prof, str) and isinstance(pp, str) and prof != pp:
                errs.append(f"{where}: profile '{prof}' differs from "
                            f"{pred}'s '{pp}' - mark the branch entry "
                            f"`fresh_run: true`")
            if pred in consumed:
                errs.append(f"{where}: {pred} is already continued by "
                            f"{consumed[pred]} - a second entry from the same "
                            f"state needs `fresh_run: true`")
            else:
                consumed[pred] = jid
        seen[jid] = e
        prev_id = jid
    if errs:
        print(f"UAT SPEC INVALID: {path.name}", file=sys.stderr)
        for x in errs:
            print("  ERROR", x, file=sys.stderr)
        sys.exit(1)


def load_uat_spec(flow_id):
    path = SPEC_DIR / f"{flow_id}.yaml"
    if not path.exists():
        have = sorted(p.stem for p in SPEC_DIR.glob("*.yaml"))
        _fail(f"render UAT: no spec for {flow_id} at {path}\n"
              f"  specs available: {', '.join(have) or '(none)'}")
    spec = yaml.safe_load(path.read_text(encoding="utf-8"))
    validate_uat_spec(spec, path)
    return spec


def alt_errors(entries, flow_fm, flow_id):
    """Every `alts` id must be an alternative scenario of the flow's model."""
    items = ((flow_fm.get("test_model") or {}).get("items") or [])
    known = {i.get("id") for i in items
             if isinstance(i, dict) and i.get("role") == "alternative"}
    return [f"entries.{jid}: alts '{a}' is not an alternative scenario of "
            f"{flow_id}'s test_model ({', '.join(sorted(known)) or 'none defined'})"
            for jid, e in entries.items() for a in (e.get("alts") or [])
            if a not in known]


def render(flow_id, force=False):
    spec = load_uat_spec(flow_id)
    entries = spec["entries"]
    out_dir = ROOT / spec["out"]
    cfg = load_config()
    manifest = load_manifest()
    flow_fm, story_of = load_scope(spec["flow"])
    if not flow_fm:
        _fail("render UAT REFUSED: flow not found")
    journey = flow_fm.get("journey") or []
    if not journey:
        _fail(f"render UAT REFUSED: {flow_fm.get('id')} has no journey: - the "
              f"journey is proposed and asserted in tc-align, never here.")

    # --- the member-coverage fence -------------------------------------
    stories = {}
    for e in journey:
        rel, sfm = story_of(e["ref"])
        stories[rel] = sfm
    for rel, sfm in stories.items():
        _cmap, _disp, status = load_coverage(sfm or {})
        if status != "confirmed":
            _fail(f"render UAT REFUSED: member story {rel} coverage_status is "
                  f"'{status or 'absent'}', not 'confirmed'.\n"
                  f"  The coverage_map IS UAT test content (element lists). "
                  f"Confirm it on the coverage card first\n"
                  f"  (tc-generate-sit step 2), then re-run with --force.")
    if os.environ.get("TC_UAT_FIXTURE_DIR"):
        _fail("render UAT REFUSED: fixture mode never writes")

    aerrs = alt_errors(entries, flow_fm, flow_id)
    if aerrs:
        _fail(f"UAT SPEC alts do not match {flow_id}'s test_model\n"
              + "\n".join(f"  ERROR {x}" for x in aerrs))

    flow_ref = spec["flow"]
    entry_condition = flow_fm.get("entry_condition") or "Flow entry condition."
    wiki_commit = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT,
                                 capture_output=True, text=True).stdout.strip()
    generated_from = {"prd_version": manifest.get("adopted_prd_version"),
                      "figma_hashes": {},
                      "wiki_commit": wiki_commit,
                      "generator_version": spec["generator_version"]}
    by_jid = {e["id"]: e for e in journey}
    in_spec = [e["id"] for e in journey if e["id"] in entries]
    if in_spec != [k for k in entries if k in by_jid]:
        _fail(f"render UAT REFUSED: the spec entries of {flow_id} are not in "
              f"journey order - the validator reads the previous entry as the "
              f"predecessor, so list them in the journey's order.")
    ids_by_jid = {}
    seq_by_ac = {}
    for e in journey:
        ac = resolve_ref(e["ref"])[1]
        seq_by_ac[ac] = seq_by_ac.get(ac, 0) + 1
        ids_by_jid[e["id"]] = tc_id(cfg, spec["story_num"], ac, seq_by_ac[ac])

    def binding_of(sc):
        return manifest.get("bindings", {}).get(sc)

    def fragments_unchanged(sc):
        b = binding_of(sc)
        if not b or b.get("status") != "active":
            return False
        if not (ROOT / (b["tc"] + ".md")).exists():
            return False
        for fragref, pin in b.get("fragment_pins", {}).items():
            tgt, frag = fragref.split("#")
            tfm, _ = read_concept(ROOT / (tgt + ".md"))
            if frag.startswith("COVMAP:"):
                if covmap_hash(tfm, frag[len("COVMAP:"):]) != pin:
                    return False
            elif fragment_hash_map(tfm).get(frag) != pin:
                return False
        return True

    count = skipped = 0
    suppressed = []
    prev_jid = None
    for e in journey:
        jid = e["id"]
        w = entries.get(jid)
        if not w:
            _fail(f"render UAT: no wording for journey entry {jid} - add it "
                  f"to tools/uat_specs/{flow_id}.yaml")
        story_rel, ac_id = resolve_ref(e["ref"])
        story_fm = stories[story_rel]
        sc = spec["scenario_id"].format(jid=jid)
        b = binding_of(sc)
        wid = Path(b["tc"]).name if b else ids_by_jid[jid]
        if b and b.get("status") == "retired":
            suppressed.append(f"{sc} suppressed - prior TC {wid} retired")
            prev_jid = jid
            continue
        if not force and fragments_unchanged(sc):
            skipped += 1
            prev_jid = jid
            continue
        cont = w.get("continue_from") or prev_jid
        if cont is None:
            pre = f"1. Start of run: {entry_condition}"
        else:
            how = (" (fresh run replayed to this point)"
                   if w.get("fresh_run") else "")
            pre = (f"1. Continue from {display_id(ids_by_jid[cont])}{how}: "
                   f"{state_clause(by_jid[cont]['end_state'])}")
        if e.get("branch") and e.get("note"):
            # Only a branch entry departs from the chain's scenario; a note on
            # a main-walk entry is a data remark, not a starting-state change.
            pre += f"\n2. Applies to: {e['note']}."
        covers = [e["ref"], f"{flow_ref}#{jid}"]
        if e.get("branch"):
            covers.append(e["branch"])
        items = ["SC-MAIN"] + list(w.get("alts") or [])
        fm = {
            "type": "Test Case", "id": wid, "title": w["title"],
            "description": w["objective"], "kind": "uat",
        }
        if spec.get("module"):
            fm["module"] = spec["module"]
        fm.update({
            "flow": flow_ref, "area": w["area"],
            "status": "active", "origin": "agent-proposed",
            "covers": covers, "coverage_items": items,
            "verifies_rules": [], "uses_terms": [],
            "technique": "UC", "scenario_id": sc, "priority": w["priority"],
            "section": w["area"], "order": journey.index(e) + 1,
            "continue_from": (ids_by_jid[cont].removeprefix("UAT-")
                              if cont is not None else None),
            "fresh_run": bool(w.get("fresh_run")),
            "generated_from": dict(generated_from), "stale_because": [],
        })
        trace = ("- Covers: " + ", ".join(covers)
                 + f"\n- Scenario: {sc} · Technique: UC · journey {jid} of {flow_id}"
                 f" · {prd_label(generated_from['prd_version'])} · wiki {wiki_commit}")
        body = (f"# Objective\n\n{w['objective']}\n\n"
                f"# Preconditions\n\n{pre}\n\n"
                f"# Test Data\n\n{TEST_DATA}\n\n"
                f"# Steps\n\n{w['steps']}\n\n"
                f"# Expected Results\n\n"
                f"{with_element_block(story_fm, w['expected'], ac_id)}\n\n"
                f"# Postconditions\n\n{state_sentence(e['end_state'])}\n\n"
                f"# Traceability\n\n{trace}\n")
        path = out_dir / f"{wid}.md"
        if path.exists():
            # An unchanged test case is not rewritten, forced or not: only the
            # provenance would move, and with it the sealed hash.
            prev_fm, prev_body = read_concept(path)
            if provenance_only_change(prev_fm, prev_body, fm, body):
                skipped += 1
                prev_jid = jid
                continue
        write_concept(path, fm, body)
        count += 1
        prev_jid = jid
    for s in suppressed:
        print("SUPPRESSED", s)
    print(f"rendered {count}, untouched {skipped} (fragments or content "
          f"unchanged), suppressed {len(suppressed)} -> {out_dir.relative_to(ROOT)}")


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if "--flow" not in argv or argv.index("--flow") + 1 >= len(argv):
        have = sorted(p.stem for p in SPEC_DIR.glob("*.yaml")) \
            if SPEC_DIR.exists() else []
        _fail("usage: py tools/render_uat.py --flow <FLOW-ID> [--force]\n"
              f"  specs available: {', '.join(have) or '(none)'}")
    render(argv[argv.index("--flow") + 1], force="--force" in argv)


if __name__ == "__main__":
    main()
