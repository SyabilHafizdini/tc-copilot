#!/usr/bin/env python3
"""`wiki export`: one scope (story or flow) -> the org workbook, twice.

  --draft   right after the first seal: marked DRAFT round 0 in the header,
            a snapshot kept for the later diff, no rubric gate BECAUSE the
            workbook says so (spec 4.1). Refuses a set that already has a
            round score: a graded set is not a first cut (amendment A2).
  (final)   refuses unless a non-PARTIAL, at-threshold score exists for the
            currently sealed set and the improve round ran (spec 4.2). Fills
            the Change Log sheet from build/rubric/<scope>-changes.json.

Zero LLM calls. Writes under build/ and commits as tc-agent.
"""
import json
import shutil
import subprocess
import sys
from datetime import datetime

from wiki import (ROOT, agent_commit, all_concepts, arg_after, load_config,
                  load_manifest, refuse_if_unsealed)
from wiki_rubric import SCOPE_TC_KIND, scope_tc_rels, sealed_digest, tc_record

_KIND = {"story": ("stories", "sit", "SIT", "--story"),
         "flow": ("flows", "uat", "UAT", "--flow")}


def scope_of(args):
    if "--story" in args:
        return "story", arg_after(args, "--story")
    if "--flow" in args:
        return "flow", arg_after(args, "--flow")
    sys.exit("export: one of --story <id> or --flow <stem> is required")


def select_scope_tcs(concepts, kind, scope):
    """(scope_rel, scope_fm, [(rel, fm, body)]) - ACTIVE test cases of the
    scope's kind (SIT for a story, UAT for a flow) whose `covers` resolve to
    the scope, in workbook order. Membership is wiki_rubric.scope_tc_rels,
    the selector --diff and `wiki next` share."""
    from wiki_suite import tc_sort_key
    scope_rel = f"{_KIND[kind][0]}/{scope}"
    if scope_rel not in concepts:
        sys.exit(f"export: no concept for {scope!r} ({scope_rel}.md)")
    sfm = concepts[scope_rel][0]
    tcs = [(rel, concepts[rel][0], concepts[rel][1])
           for rel in scope_tc_rels(concepts, scope_rel, SCOPE_TC_KIND[kind])]
    tcs.sort(key=lambda t: tc_sort_key(t[1]))
    return scope_rel, sfm, tcs


def head_commit():
    r = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT,
                       capture_output=True, text=True)
    return r.stdout.strip() or None


def write_draft_snapshot(scope, kind, tcs, manifest, workbook_rel, seal_commit,
                         rubric_version, path, score=None):
    """`score` is the current score of this sealed set at draft time, if any
    (under A2 a graded set refuses the draft, so in practice None)."""
    h = manifest.get("tc_hashes") or {}
    snap = {"scope": scope, "kind": kind,
            "exported_at": datetime.now().astimezone().isoformat(timespec="seconds"),
            "workbook": workbook_rel, "seal_commit": seal_commit,
            "sealed_digest": sealed_digest(h, [rel for rel, _f, _b in tcs]),
            "rubric_version": rubric_version, "score": score,
            "test_cases": {fm["id"]: tc_record(rel, fm, body, h)
                           for rel, fm, body in tcs}}
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(snap, indent=2, sort_keys=True) + "\n",
                    encoding="utf-8")
    return snap


def graded_round_for(digest, state):
    """The highest round whose score was computed on exactly this sealed set
    (a rubric_state() dict), else None. A graded set is not a first cut
    (spec 4.1 step 2, amendment A2)."""
    hits = [n for n, r in (state.get("rounds") or {}).items()
            if (r or {}).get("digest") == digest]
    return max(hits) if hits else None


def draft_refusal(scope, kind, rnd, name):
    flag = _KIND[kind][3]
    return (f"export refused: the sealed set of {scope} was graded in round "
            f"{rnd}; a graded set is not a first cut.\n"
            f"  Next: py tools/eval_rubric.py {flag} {scope} --diff, then "
            f"py tools/wiki.py export {flag} {scope} --name {name}")


def load_changes(path, flag, scope):
    """The changes JSON object, None when the file is absent, or a refusal
    naming the file when it is not a JSON object - never a traceback."""
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        data, why = None, f"is not valid JSON ({e})"
    else:
        why = "is not a JSON object"
    if not isinstance(data, dict):
        try:
            shown = path.relative_to(ROOT).as_posix()
        except ValueError:
            shown = path.as_posix()
        sys.exit(f"export refused: the changes file {shown} {why}.\n"
                 f"  Next: py tools/eval_rubric.py {flag} {scope} --diff   "
                 f"(rewrites it)")
    return data


def changes_for(digest, changes):
    """The changes dict only when it was computed on this sealed set."""
    if changes and changes.get("to_digest") == digest:
        return changes
    return None


def export_gate(scope, kind, digest, cfg):
    """(current score, None) when the final export may proceed, else
    (None, refusal text). The prose rule '--round 2 --strict is the export
    gate' promoted into the CLI (spec 4.2)."""
    from rubric_judge import rubric_state
    rc = cfg.get("rubric") or {}
    threshold, version = rc.get("threshold", 70), rc.get("version", "v1")
    flag = _KIND[kind][3]
    st = rubric_state(scope, digest, threshold, version)
    hint = (f"  A first cut without the gate is: py tools/wiki.py export "
            f"{flag} {scope} --name <n> --draft")
    if not st["rounds"]:
        return None, (f"export refused: {scope} has not been graded.\n"
                      f"  Next: py tools/eval_rubric.py {flag} {scope} --round 1 --pack\n{hint}")
    if not st["improve_round_ran"]:
        return None, (f"export refused: {scope} has a round 1 score only - the "
                      f"improve round has not run.\n"
                      f"  Next: py tools/eval_rubric.py {flag} {scope} --round 1   "
                      f"(merge; then the improver patch, --apply-patch, render "
                      f"--force, seal, --round 2 --pack)\n{hint}")
    if st["current"]:
        return st["current"], None
    hi = st["highest"]
    r = st["rounds"][hi]
    if r["rubric_version"] != version:
        why = (f"The latest score (round {hi}) was computed under rubric "
               f"{r['rubric_version']}; config.yaml says {version}.")
        nxt = f"py tools/eval_rubric.py {flag} {scope} --round {hi} --pack   (re-judge under the current rubric)"
    elif r["digest"] != digest:
        why = (f"The latest score (round {hi}, {r['score']}) was computed on a "
               f"different sealed set.")
        nxt = (f"py tools/eval_rubric.py {flag} {scope} --round {hi}   (re-merge on "
               f"the current set; if round 1 was restored after a regression, --round 1)")
    elif r["partial"]:
        why = f"The latest score (round {hi}) is PARTIAL - a judge lens is missing."
        nxt = (f"run the missing lens from build/rubric/packs/, then "
               f"py tools/eval_rubric.py {flag} {scope} --round {hi}")
    else:
        why = (f"The latest score (round {hi}, {r['score']}) is below the "
               f"threshold {threshold}.")
        nxt = (f"py tools/eval_rubric.py {flag} {scope} --round {hi} --strict   "
               f"(the set does not pass; the draft stays the deliverable)")
    return None, (f"export refused: {scope} has no score on the currently sealed "
                  f"set.\n  {why}\n  Next: {nxt}\n{hint}")


def _write_md(md_ts, md_latest, name, scope, manifest, tcs, label):
    md = ["<!-- generated by wiki export — reproducible from manifest + wiki; do not edit -->",
          f"# Inventory: {name}", "",
          f"- scope: {scope} · PRD v{manifest.get('adopted_prd_version')} · "
          f"TCs: {len(tcs)} · {label}", ""]
    for _rel, fm, _body in tcs:
        md.append(f"- **{fm['id']}** — {fm['title']} "
                  f"(covers {', '.join(fm.get('covers') or [])})")
    md_ts.write_text("\n".join(md) + "\n", encoding="utf-8", newline="\n")
    shutil.copyfile(md_ts, md_latest)


def cmd_export(args):
    refuse_if_unsealed("export")
    kind, scope = scope_of(args)
    _dir, kind_dir, test_type, flag = _KIND[kind]
    draft = "--draft" in args
    name = arg_after(args, "--name") if "--name" in args else f"{scope}-{kind_dir}"
    cfg = load_config()
    rubric_version = (cfg.get("rubric") or {}).get("version", "v1")
    concepts = {rel: (fm, body) for rel, fm, body, _ in all_concepts()}
    manifest = load_manifest()
    _scope_rel, sfm, tcs = select_scope_tcs(concepts, kind, scope)
    if not tcs:
        sys.exit(f"export refused: {scope} has no active test cases.\n"
                 f"  Next: render the scope, then py tools/wiki.py seal")
    digest = sealed_digest(manifest.get("tc_hashes") or {},
                           [rel for rel, _f, _b in tcs])
    from rubric_judge import changes_path, draft_path
    from wiki_suite import inventory_paths, render_xlsx
    title = sfm.get("title") or scope

    if draft:
        from rubric_judge import rubric_state
        rc = cfg.get("rubric") or {}
        state = rubric_state(scope, digest, rc.get("threshold", 70), rubric_version)
        graded = graded_round_for(digest, state)
        if graded:
            sys.exit(draft_refusal(scope, kind, graded, name))
        _o, xlsx_ts, md_ts, xlsx_latest, md_latest = inventory_paths(f"{name}-draft", kind_dir)
        render_xlsx(tcs, title, xlsx_ts, concepts=concepts, manifest=manifest,
                    test_type=test_type, draft=True)
        shutil.copyfile(xlsx_ts, xlsx_latest)
        rel_ts = xlsx_ts.relative_to(ROOT).as_posix()
        write_draft_snapshot(scope, kind, tcs, manifest, rel_ts, head_commit(),
                             rubric_version, draft_path(scope),
                             score=(state["current"] or {}).get("score"))
        _write_md(md_ts, md_latest, f"{name}-draft", scope, manifest, tcs,
                  "DRAFT round 0 - ungraded")
        print(f"exported DRAFT r0: {len(tcs)} TCs -> {rel_ts} (+ {xlsx_latest.name})\n"
              f"  snapshot: {draft_path(scope).relative_to(ROOT).as_posix()}\n"
              f"  Next: py tools/eval_rubric.py {flag} {scope} --round 1 --pack")
        agent_commit(f"export({name}-draft): {len(tcs)} TCs [draft r0]")
        return

    current, err = export_gate(scope, kind, digest, cfg)
    if err:
        sys.exit(err)
    changes = changes_for(digest, load_changes(changes_path(scope), flag, scope))
    grade = {"round": current["round"], "score": current["score"],
             "threshold": (cfg.get("rubric") or {}).get("threshold", 70),
             "version": rubric_version}
    _o, xlsx_ts, md_ts, xlsx_latest, md_latest = inventory_paths(name, kind_dir)
    render_xlsx(tcs, title, xlsx_ts, concepts=concepts, manifest=manifest,
                test_type=test_type, grade=grade, changes=changes)
    shutil.copyfile(xlsx_ts, xlsx_latest)
    _write_md(md_ts, md_latest, name, scope, manifest, tcs,
              f"graded r{current['round']} {current['score']}")
    rel_ts = xlsx_ts.relative_to(ROOT).as_posix()
    note = "" if changes else "\n  (no current change log - run --diff first to fill the Change Log sheet)"
    print(f"exported {len(tcs)} TCs, rubric r{current['round']} {current['score']} "
          f"-> {rel_ts} (+ {xlsx_latest.name}){note}")
    agent_commit(f"export({name}): {len(tcs)} TCs, rubric r{current['round']} "
                 f"{current['score']}")
