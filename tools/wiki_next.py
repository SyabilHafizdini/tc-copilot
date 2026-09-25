#!/usr/bin/env python3
"""`wiki next` — the deterministic next-action advisor.

`status` reports STATE; deciding what to DO with that state previously meant
running status + gate + reading each story's frontmatter for coverage_status +
counting open-question bullets, then reasoning across all four. This collapses
that into one read-only call that prints, per story and flow, the literal next
command and the skill that owns it.

Read-only, LLM-free, never commits. Precedence within a scope is strict and
top-down: the first unmet precondition wins, so the printed command is always
the one that unblocks everything after it.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from wiki import (ROOT, all_concepts, arg_after, body_section, load_config,
                  load_manifest, resolve_ref, sha256, story_tc_stats)
from wiki_coverage import load_coverage


def open_questions(body):
    oq = body_section(body, "Open Questions") or ""
    return len([ln for ln in oq.splitlines() if ln.strip().startswith("-")])


def suite_for(kind):
    """A real suite name of this kind to suggest, or a placeholder."""
    import yaml
    for p in sorted((ROOT / "suites").glob("*.yaml")):
        y = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
        if y.get("kind") == kind:
            return p.stem
    return f"<{kind}-suite>"


def pending_cards(root=ROOT):
    """Emitted cards with no human_response, oldest first.

    An interrupted session leaves exactly this trace: the card was written
    and presented, the human never answered. Without surfacing it, `next`
    says "emit a card" and the session gets redone from scratch -- so this
    is the resume signal, not a nicety. The operator app's inbox() reads the
    same list (one implementation, two surfaces).
    """
    d = Path(root) / "build/cards"
    out = []
    if not d.exists():
        return out
    for p in sorted(d.glob("*.json")):
        try:
            c = json.loads(p.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        if c.get("human_response"):
            continue
        # A CLI-emitted triage card carries `scope`, not `card_type`. The
        # operator app builds each inbox row's title from card_type, so a
        # None here throws during render and takes the whole Inbox page down
        # -- fall back to the scope rather than surface a null.
        out.append({"file": p.name,
                    "card_type": c.get("card_type") or c.get("scope"),
                    "story": c.get("story"), "session": c.get("session"),
                    "card": c})
    return out


PHASE_LABELS = ["Ingested", "In alignment", "Ready for generation", "Generated"]


def phase_from_stories(stories):
    """Aggregate 4-phase position from dashboard-shaped story dicts:
    0 Ingested, 1 In alignment, 2 Ready for generation, 3 Generated.
    Highest phase any story has reached.

    This is the single implementation -- the operator app's
    read_models._project_phase() delegates here so the CLI header and the
    project card can never disagree.
    """
    phase = 0
    for s in stories:
        tc = s.get("tc") or {}
        if tc.get("active"):
            phase = max(phase, 3)
        elif s.get("status") in ("aligned", "asserted") and not s.get("open_questions"):
            phase = max(phase, 2)
        elif s.get("status") in ("in-alignment", "proposed", "draft", "pending"):
            phase = max(phase, 1)
    return phase


def phase_rollup(concepts, manifest):
    """{phase, label, counts} for the whole bundle. Read-only."""
    shaped, counts = [], {}
    tcs = {"active": 0, "stale": 0, "retired": 0}
    for rel, (fm, body, _p) in concepts.items():
        if not fm or fm.get("type") != "User Story":
            continue
        status = fm.get("status", "?")
        counts[status] = counts.get(status, 0) + 1
        shaped.append({"status": status,
                       "open_questions": open_questions(body),
                       "tc": story_tc_stats(manifest, rel)})
    # Keyed on the path prefix, not a "type" field: manifest concept entries
    # are not guaranteed to carry one (flow_next counts UAT TCs the same way).
    for rel, entry in manifest.get("concepts", {}).items():
        if rel.startswith("testcases/") and entry.get("status") in tcs:
            tcs[entry["status"]] += 1
    phase = phase_from_stories(shaped)
    return {"phase": phase, "label": PHASE_LABELS[phase],
            "counts": {"stories": counts, "tcs": tcs}}


def scope_digest(manifest, scope_rel, concepts=None):
    """Digest of the scope's ACTIVE sealed test cases of the scope's kind
    (SIT for a story, UAT for a flow). With `concepts` the members are read
    from the concept files by the selector export and --diff use
    (wiki_rubric.scope_tc_rels), so a test case sealed since the last `wiki
    manifest` counts the same everywhere. Without it, the manifest's
    concepts/edges are the fallback."""
    from wiki_rubric import (SCOPE_TC_KIND, active_rels_from_manifest,
                             scope_tc_rels, sealed_digest)
    if concepts is not None:
        kind = SCOPE_TC_KIND["flow" if scope_rel.startswith("flows/") else "story"]
        rels = scope_tc_rels(concepts, scope_rel, kind)
    else:
        rels = active_rels_from_manifest(manifest, scope_rel)
    return sealed_digest(manifest.get("tc_hashes") or {}, rels)


def rubric_state_for(scope_id, digest):
    from rubric_judge import rubric_state
    rc = load_config().get("rubric") or {}
    return rubric_state(scope_id, digest, rc.get("threshold", 70), rc.get("version", "v1"))


def _json_field_matches(path, key, digest):
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return False
    return isinstance(data, dict) and data.get(key) == digest


def draft_current(scope_id, digest, round_digests=()):
    """The first cut is delivered (spec 4.5 step 1, amendment A1): a draft
    snapshot exists and its digest is either the current sealed set's or
    that of some round score - a draft that grading has started on stays
    delivered when the improve round moves the set."""
    from rubric_judge import draft_path
    path = draft_path(scope_id)
    if _json_field_matches(path, "sealed_digest", digest):
        return True
    return any(d and _json_field_matches(path, "sealed_digest", d)
               for d in set(round_digests))


def changes_current(scope_id, digest):
    from rubric_judge import changes_path
    return _json_field_matches(changes_path(scope_id), "to_digest", digest)


def delivery_next(scope_id, flag, name, manifest, scope_rel, active, skill_gen,
                  concepts=None):
    """Shared tail of story_next / flow_next once a rendered set exists: the
    six-step delivery precedence (spec 4.5). All build/ readers are module
    functions so tests can stub them."""
    digest = scope_digest(manifest, scope_rel, concepts)
    st = rubric_state_for(scope_id, digest)
    round_digests = {r.get("digest") for r in st["rounds"].values()} - {None}
    if not draft_current(scope_id, digest, round_digests):
        return (f"rendered · {active} active TC(s) - first cut NOT delivered",
                f"py tools/wiki.py export {flag} {scope_id} --name {name} --draft",
                f"{skill_gen} (step 4a: draft export - the human reviews while "
                f"the grade loop runs)")
    if 1 not in st["rounds"]:
        return (f"draft delivered · {active} active TC(s) - NOT graded",
                f"py tools/eval_rubric.py {flag} {scope_id} --round 1 --pack",
                "tc-rubric (grade loop: 4 judge lenses, gap report, one "
                "improve round)")
    if not st["improve_round_ran"]:
        if st["rounds"][1].get("digest") == digest:
            return ("graded round 1 - improve round NOT run",
                    f"py tools/eval_rubric.py {flag} {scope_id} --round 1",
                    "tc-rubric (merge; improver patch, --apply-patch, render --force, "
                    "seal, --round 2 --pack)")
        # The improver patch was applied, re-rendered and sealed: the set
        # moved on from round 1. It is round 2's input, not a new first cut.
        return ("graded round 1 · set improved - round 2 NOT packed",
                f"py tools/eval_rubric.py {flag} {scope_id} --round 2 --pack",
                "tc-rubric (pack round 2 - unchanged cases carry forward - then "
                "run the lenses and merge with --round 2 --strict)")
    if st["current"] is None:
        # The gate is the round whose score is on this sealed set: round 2,
        # or round 1 when round 2 regressed and round 1 was restored.
        on_set = [n for n, r in st["rounds"].items() if r.get("digest") == digest]
        rnd = max(on_set) if on_set else st["highest"]
        return ("graded - no strict score on the current sealed set",
                f"py tools/eval_rubric.py {flag} {scope_id} --round {rnd} --strict",
                "tc-rubric (re-merge on the current set; a regression keeps round 1)")
    cur = st["current"]
    if not changes_current(scope_id, digest):
        return (f"graded r{cur['round']} {cur['score']} - change log NOT built",
                f"py tools/eval_rubric.py {flag} {scope_id} --diff",
                f"{skill_gen} (step 6: diff draft -> final)")
    return (f"graded r{cur['round']} {cur['score']} - ready to export",
            f"py tools/wiki.py export {flag} {scope_id} --name {name}",
            "tc-suite-author (final export; suite compile for a multi-scope workbook)")


def story_next(sid, fm, body, manifest, story_rel, concepts=None):
    """(state, command, skill) — first unmet precondition wins. `concepts`
    (collect_next passes them) makes the scope digest read the concept files
    rather than the manifest's concepts/edges."""
    status = fm.get("status", "?")
    oq = open_questions(body)
    _cmap, _disp, cov = load_coverage(fm)
    t = story_tc_stats(manifest, story_rel)

    if status == "draft":
        return ("draft — no ACs asserted yet",
                None, "tc-align (start the alignment session)")
    if status == "in-alignment":
        return (f"in-alignment · {oq} open question(s)",
                None, "tc-align (close open questions, emit card, human asserts)")
    if status == "needs-review":
        return ("needs-review — a pinned source changed",
                None, "tc-align (re-align) or tc-change-report (if a CR is pending)")
    if status != "aligned":
        return (f"status '{status}'", None, "tc-align")

    # aligned from here
    if oq:
        return (f"aligned but {oq} open question(s) remain", None, "tc-align")
    if cov != "confirmed":
        return (f"aligned · coverage_status '{cov or 'absent'}' — NOT confirmed",
                f"py tools/wiki.py coverage --story {sid} --propose",
                "tc-generate-sit (step 2: correct the map, emit the coverage "
                "card, human confirms)")
    tm_status = (fm.get("test_model") or {}).get("status") \
        if isinstance(fm.get("test_model"), dict) else None
    if tm_status != "confirmed":
        return (f"aligned · coverage confirmed · test_model "
                f"'{tm_status or 'absent'}' — NOT confirmed",
                f"py tools/wiki.py testmodel --story {sid} --propose",
                "tc-generate-sit (step 2: enrich the 29119-4 test model on the "
                "coverage card, human confirms)")
    if t["stale"]:
        return (f"aligned · coverage confirmed · {t['stale']} STALE TC(s)",
                f"py tools/render_sit.py --story {sid} && py tools/wiki.py seal",
                "tc-generate-sit (regenerate staled TCs)")
    if not t["active"]:
        return ("aligned · coverage confirmed · 0 TCs",
                f"py tools/render_sit.py --story {sid} && py tools/wiki.py seal",
                "tc-generate-sit (render)")
    return delivery_next(sid, "--story", f"{sid}-sit", manifest, story_rel,
                         t["active"], "tc-generate-sit", concepts=concepts)


def flow_next(fid, fm, body, concepts, manifest, flow_rel=None):
    status = fm.get("status", "?")
    oq = open_questions(body)
    journey = fm.get("journey") or []

    if status in ("draft", "in-alignment") or oq:
        return (f"{status} · {oq} open question(s)", None,
                "tc-align (flow session — must end with a proposed journey)")
    if status != "aligned":
        return (f"status '{status}'", None, "tc-align")
    if not journey:
        return ("aligned but has NO journey", None,
                "tc-align (propose the journey; UAT cannot render without it)")

    unconfirmed = []
    for sref in fm.get("stories") or []:
        srel, _ = resolve_ref(sref)
        sfm = concepts.get(srel, ({}, "", None))[0] or {}
        _c, _d, cov = load_coverage(sfm)
        if cov != "confirmed":
            unconfirmed.append(f"{sfm.get('id', srel)}({cov or 'absent'})")
    if unconfirmed:
        return (f"aligned · journey {len(journey)} entries · member coverage "
                f"NOT confirmed: {', '.join(unconfirmed)}",
                f"py tools/wiki.py coverage --story {unconfirmed[0].split('(')[0]} --propose",
                "tc-generate-sit (confirm member coverage first — it is UAT "
                "test content)")

    uat = {"active": 0, "stale": 0, "retired": 0}
    for rel, entry in manifest["concepts"].items():
        if rel.startswith("testcases/uat/") and entry.get("status") in uat:
            uat[entry["status"]] += 1
    if uat["stale"]:
        return (f"aligned · journey {len(journey)} entries · {uat['stale']} STALE UAT TC(s)",
                f"py tools/render_production_monitoring_uat.py --force && py tools/wiki.py seal",
                "tc-generate-uat (re-render; --force because coverage_map sits "
                "outside AC fragment pins)")
    if not uat["active"]:
        return (f"aligned · journey {len(journey)} entries · 0 UAT TCs",
                "py tools/render_production_monitoring_uat.py && py tools/wiki.py seal",
                "tc-generate-uat (render the chain)")
    stem = Path(flow_rel).stem if flow_rel else fid
    # collect_next always passes flow_rel; the f"flows/{stem}" fallback only
    # serves a direct caller and must match the concept's real rel.
    return delivery_next(stem, "--flow", f"{stem}-uat", manifest,
                         flow_rel or f"flows/{stem}", uat["active"], "tc-generate-uat",
                         concepts=concepts)


def collect_next(args):
    """Structured next-action state. Read-only; never writes.

    Returns {"banners": [...], "rows": [...]}, each entry a dict with
    state/command/skill (rows also carry id). `cmd_next` prints this; the
    operator app serves it as JSON.
    """
    only = arg_after(args, "--story") if "--story" in args else None
    concepts = {rel: (fm, body, p) for rel, fm, body, p in all_concepts()}
    manifest = load_manifest()

    banners = []
    staged = manifest.get("staged_prd_version")
    if staged and staged != manifest.get("adopted_prd_version"):
        banners.append({
            "state": (f"PRD v{staged} is STAGED but not adopted (adopted: "
                      f"v{manifest.get('adopted_prd_version')})"),
            "command": "py tools/wiki.py diff --prd",
            "skill": ("tc-change-report (classify the CR, present conflicts, "
                      "human approves or rejects)")})
    pend = pending_cards()
    if pend:
        first = pend[0]
        scope = first.get("story") or first.get("session") or "?"
        banners.append({
            "state": (f"{len(pend)} card(s) awaiting your answer -- first: "
                      f"{first['file']} ({first.get('card_type') or 'card'}, "
                      f"{scope})"),
            "command": (f"py tools/wiki.py assert story <id> --by <user> "
                        f"--card build/cards/{first['file']}"
                        f"   # or: card revise|discard build/cards/{first['file']} --by <user>"),
            "skill": ("tc-align (present the card that already exists -- do NOT "
                      "redo the session)")})
    dump = ROOT / "PUT_FILES_HERE"
    dumped = [p for p in dump.rglob("*")
              if p.is_file() and p.name not in ("README.md", ".gitkeep", ".gitignore")] \
        if dump.exists() else []
    if dumped:
        banners.append({
            "state": (f"{len(dumped)} file(s) waiting in PUT_FILES_HERE/ "
                      f"(first: {dumped[0].name})"),
            "command": "py tools/wiki.py triage   # then: triage --apply",
            "skill": ("tc-intake (resolve any refusal with the human, apply, "
                      "then ingest)")})
    # --brief skips the drift scan, which hashes every TC file. The opencode
    # plugin calls `next --brief` on every agent turn; the full scan is for
    # humans and for `smoke`.
    brief = "--brief" in args
    drift = [] if brief else [
        rel for rel, h in manifest.get("tc_hashes", {}).items()
        if (ROOT / (rel + ".md")).exists()
        and sha256((ROOT / (rel + ".md")).read_bytes()) != h]
    if drift:
        banners.append({
            "state": f"{len(drift)} TC file(s) hand-edited since seal (lint W4)",
            "command": (f"py tools/wiki.py release {Path(drift[0]).name} --by <user>"
                        f"   # or: revert {Path(drift[0]).name}"),
            "skill": ("tc-lifecycle (accept the hand-edit or restore the "
                      "sealed content — human decides)")})

    rows = []
    for rel, (fm, body, _p) in concepts.items():
        if not fm:
            continue
        if fm.get("type") == "User Story":
            if only and fm["id"] != only:
                continue
            state, cmd, skill = story_next(fm["id"], fm, body, manifest, rel,
                                           concepts=concepts)
            # scope/arg carry what the write path (actions.build) needs: a
            # story's id doubles as its own gate identifier.
            rows.append({"id": fm["id"], "state": state,
                         "command": cmd, "skill": skill,
                         "scope": "story", "arg": fm["id"]})
        elif fm.get("type") == "Flow" and not only:
            state, cmd, skill = flow_next(fm["id"], fm, body, concepts, manifest, flow_rel=rel)
            # `gate --flow` keys on the flow's FILE STEM (e.g.
            # "<name>-e2e"), not its id (e.g.
            # "FLOW-<name>") -- derive the stem from this
            # concept's own relative path rather than hardcoding it.
            rows.append({"id": fm["id"], "state": state,
                         "command": cmd, "skill": skill,
                         "scope": "flow", "arg": Path(rel).stem})

    if not rows and only:
        sys.exit(f"next: no story matching '{only}'")
    if not rows:
        # A fresh bundle legitimately has no stories or flows yet, so the next
        # action is to ingest a source -- not an error. Exiting here would also
        # take out the operator app: read_models.state()/projects() call this,
        # and server.py turns SystemExit into a 500, so a brand-new project
        # would open onto a crash instead of onto its first step.
        banners.append({
            "state": "empty bundle -- no stories or flows yet",
            "command": ("py tools/wiki.py ingest-prd"
                        "   # place the PRD under inputs/prd/v1/ first"),
            "skill": ("tc-align (align the first story once the PRD is "
                      "ingested)")})
    return {"banners": banners, "rows": rows,
            "phase": phase_rollup(concepts, manifest)}


def cmd_next(args):
    out = collect_next(args)
    if "--json" in args:
        print(json.dumps(out, indent=1))
        return
    ph = out["phase"]
    story_counts = ", ".join(f"{n} {s}" for s, n in sorted(ph["counts"]["stories"].items()))
    print(f"PHASE {ph['phase']}/3 — {ph['label']}"
          + (f"  ·  stories: {story_counts}" if story_counts else "")
          + f"  ·  TCs: {ph['counts']['tcs']['active']} active, "
            f"{ph['counts']['tcs']['stale']} stale\n")
    for b in out["banners"]:
        print(f"! {b['state']}")
        if b["command"]:
            print(f"    next: {b['command']}")
        print(f"    skill: {b['skill']}\n")
    for r in out["rows"]:
        print(f"{r['id']}  {r['state']}")
        if r["command"]:
            print(f"    next:  {r['command']}")
        print(f"    skill: {r['skill']}")
    print("\n(read-only; nothing was written. `wiki status` for raw state.)")
