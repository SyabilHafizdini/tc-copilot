#!/usr/bin/env python3
"""Change management (tc-copilot-spec §12): PRD re-ingestion staging,
change reports, approval/rejection, on-demand diff.

Staging is write-only until human approval: `sources/prd/<id>/` concepts and
that PRD's adopted version are untouched by ingestion of a newer version (spec
§5.1.5). Approval is per-report, as a unit, human-gated. Classification of
each change (editorial|material) is LLM/agent-proposed by EDITING the CR
before approval — this module writes 'unclassified'.
"""
import difflib
import json
import re
import sys

from wiki import (ROOT, adopted_version, agent_commit, append_log, arg_after,
                  load_all, load_manifest, now_iso, read_concept,
                  reports_for_prd, resolve_prd_arg, resolve_ref, save_manifest,
                  set_prd_versions, staged_version, write_concept)


def staging_file(prd_id, version):
    return ROOT / "staging" / prd_id / f"prd-v{version}.json"


def cr_file(prd_id, cr_id):
    return ROOT / "changereports" / prd_id / f"{cr_id}.md"


def next_cr_number():
    """CR numbers are unique across the project, whichever PRD they belong
    to, so a report id never needs its PRD to be unambiguous."""
    base = ROOT / "changereports"
    nums = [int(m.group(1)) for p in base.rglob("CR-*.md")
            if (m := re.match(r"CR-(\d+)", p.stem))] if base.exists() else []
    return max(nums, default=0) + 1


def read_staged(prd_id, version, cmd):
    """The staged sections file, or a refusal naming it."""
    sf = staging_file(prd_id, version)
    if not sf.exists():
        sys.exit(f"{cmd} refused: the staged file {sf.relative_to(ROOT).as_posix()} "
                 f"is missing, so v{version} of PRD {prd_id} cannot be read.\n"
                 f"  Re-run ingest-prd for that version to stage it again.")
    return json.loads(sf.read_text(encoding="utf-8"))


def current_prd_sections(prd_id):
    out = {}
    for p in sorted((ROOT / "sources/prd" / prd_id).glob("*.md")):
        if p.name in ("index.md", "log.md"):
            continue
        fm, body = read_concept(p)
        if fm:
            # strip superseded history from the comparable body
            live = re.split(r"^# Superseded \(v\d+\)\s*$", body,
                            flags=re.MULTILINE)[0].strip()
            out[p.stem] = {"slug": p.stem, "num": fm.get("title", "").split(" ")[0]
                           if fm.get("heading_path") else None,
                           "title": fm["title"], "hash": fm["content_hash"],
                           "body": live, "prd_version": fm.get("prd_version"),
                           "removed_in": fm.get("removed_in")}
    return out


def compute_diff(old, new_sections):
    """old: {slug: {...}}, new_sections: list from parse_prd.
    -> dict with added/removed/modified/moved/unchanged lists."""
    new = {s["slug"]: s for s in new_sections}
    added, removed, modified, moved, unchanged = [], [], [], [], []
    matched_new = set()
    for slug, o in old.items():
        if slug in new:
            n = new[slug]
            matched_new.add(slug)
            (unchanged if n["content_hash"] == o["hash"] else modified).append(
                {"slug": slug, "old": o, "new": n})
        elif not o.get("removed_in"):
            removed.append({"slug": slug, "old": o})
    for slug, n in new.items():
        if slug not in matched_new:
            added.append({"slug": slug, "new": n})
    # moved detection: identical content hash between a removed and an added
    still_removed, still_added = [], list(added)
    for r in removed:
        hit = next((a for a in still_added
                    if a["new"]["content_hash"] == r["old"]["hash"]), None)
        if hit:
            moved.append({"old_slug": r["slug"], "new_slug": hit["slug"],
                          "old": r["old"], "new": hit["new"]})
            still_added.remove(hit)
        else:
            # renumber+edit: fuzzy title match >= 0.85 counts as modified-moved
            fuzzy = next((a for a in still_added if difflib.SequenceMatcher(
                None, r["old"]["title"].lower(),
                (a["new"]["num"] or "") .lower() + " " + a["new"]["title"].lower()
            ).ratio() >= 0.85), None)
            if fuzzy:
                modified.append({"slug": r["slug"], "old": r["old"],
                                 "new": fuzzy["new"], "renumbered": True})
                still_added.remove(fuzzy)
            else:
                still_removed.append(r)
    return {"added": still_added, "removed": still_removed, "modified": modified,
            "moved": moved, "unchanged": unchanged}


def impact_analysis(changed_slugs, concepts, manifest, prd_id):
    """Deterministic traversal: changed sections -> stories -> TCs -> suites."""
    changed_rels = {f"sources/prd/{prd_id}/{s}" for s in changed_slugs}
    stories = []
    for rel, (fm, _b, _p) in concepts.items():
        if fm and fm.get("type") == "User Story":
            if any(resolve_ref(d)[0] in changed_rels
                   for d in fm.get("derived_from") or []):
                stories.append((rel, fm))
    story_rels = {rel for rel, _ in stories}
    tcs = []
    for rel, (fm, _b, _p) in concepts.items():
        if fm and fm.get("type") == "Test Case" and fm.get("status") != "retired":
            if any(resolve_ref(c)[0] in story_rels for c in fm.get("covers") or []):
                tcs.append(fm["id"])
    conflicts = []
    for rel, (fm, _b, _p) in concepts.items():
        if fm and fm.get("type") == "Resolution" and fm.get("status") == "asserted":
            for rref in fm.get("resolves") or []:
                if resolve_ref(rref)[0] in story_rels:
                    conflicts.append((fm["id"], rref, fm.get("asserted_at", "?")))
                    break
    return stories, sorted(set(tcs)), conflicts


def excerpt(text, n=400):
    t = (text or "").strip()
    return t[:n] + ("…" if len(t) > n else "")


def stage_prd_version(sections, version, src_rel, manifest, prd_id):
    sfile = staging_file(prd_id, version)
    sfile.parent.mkdir(parents=True, exist_ok=True)
    sfile.write_text(
        json.dumps({"prd": prd_id, "version": version, "source_file": src_rel,
                    "staged_at": now_iso(), "sections": sections},
                   indent=1, ensure_ascii=False),
        encoding="utf-8", newline="\n")
    old = current_prd_sections(prd_id)
    diff = compute_diff(old, sections)
    concepts, _m = load_all()
    changed = [m["slug"] for m in diff["modified"]] + \
              [r["slug"] for r in diff["removed"]]
    stories, tcs, conflicts = impact_analysis(changed, concepts, manifest, prd_id)

    adopted = adopted_version(manifest, prd_id)
    crn = next_cr_number()
    cr_id = f"CR-{crn:03d}"
    fm = {"type": "Change Report", "id": cr_id,
          "title": f"{cr_id}: PRD {prd_id} v{adopted} -> v{version}",
          "description": f"{len(diff['modified'])} modified, {len(diff['added'])} "
                         f"added, {len(diff['removed'])} removed, "
                         f"{len(diff['moved'])} moved",
          "prd": prd_id, "from_version": adopted,
          "to_version": version, "status": "pending"}
    L = ["# Summary", "",
         f"PRD {prd_id} v{fm['from_version']} -> v{version}: "
         f"{len(diff['modified'])} section(s) modified, {len(diff['added'])} added, "
         f"{len(diff['removed'])} removed, {len(diff['moved'])} moved, "
         f"{len(diff['unchanged'])} unchanged. Agent narrative to be refined on "
         "review.", "",
         "# Conflicts", "",
         "_Changes contradicting ASSERTED resolutions — review these first._", ""]
    if conflicts:
        for rid, rref, at in conflicts:
            L.append(f"- **{rid}** (asserted {at}) resolves `{rref}` inside an "
                     f"affected story — verify the new text does not contradict it.")
    else:
        L.append("_None detected._")
    L += ["", "# Section Changes", ""]
    for m in diff["modified"]:
        tag = " (renumbered)" if m.get("renumbered") else ""
        L += [f"## modified{tag}: {m['old']['title']}",
              f"- classification: **unclassified** _(agent proposes editorial|material "
              "before approval)_", "",
              "**Old:**", "> " + excerpt(m["old"]["body"]).replace("\n", "\n> "), "",
              "**New:**", "> " + excerpt(m["new"]["body"]).replace("\n", "\n> "), ""]
    for a in diff["added"]:
        L += [f"## added: {a['new']['num']} {a['new']['title']}",
              "> " + excerpt(a["new"]["body"]).replace("\n", "\n> "), ""]
    for r in diff["removed"]:
        L += [f"## removed: {r['old']['title']}", ""]
    for mv in diff["moved"]:
        L += [f"## moved: {mv['old']['title']} -> {mv['new']['num']} "
              f"{mv['new']['title']} (content identical; concept keeps its ID with "
              "also_known_as)", ""]
    L += ["# Impact Analysis", "",
          f"- affected stories ({len(stories)}): " +
          (", ".join(fm2["id"] for _r, fm2 in stories) or "none"),
          f"- affected TCs ({len(tcs)}): " + (", ".join(tcs) or "none"),
          "- suites: every suite selecting the affected TCs "
          "(recompile after approval)", "",
          "# Recommended Actions", "",
          "_Agent proposal only — the human decides:_", ""]
    for _r, fm2 in stories:
        L.append(f"- re-align {fm2['id']} after approval (cascade will drop it to "
                 "needs-review)")
    if not stories:
        L.append("- none: no aligned content is affected")
    crp = cr_file(prd_id, cr_id)
    crp.parent.mkdir(parents=True, exist_ok=True)
    write_concept(crp, fm, "\n".join(L) + "\n")
    set_prd_versions(manifest, prd_id, staged=version)
    save_manifest(manifest)
    append_log(f"**Change Report (agent)**: {cr_id} staged ({prd_id} "
               f"v{fm['from_version']} -> v{version}); adopted version unchanged")
    print(f"staged PRD {prd_id} v{version}; {cr_id} written "
          f"({fm['description']}); adopted stays v{fm['from_version']} until "
          f"approval")
    for r in reports_for_prd(prd_id):
        if r.get("status") == "pending" and r["id"] != cr_id \
                and r.get("to_version") != version:
            print(f"note: {r['id']} (v{r.get('to_version')}) is superseded by "
                  f"this staging and can no longer be approved; act on {cr_id}, "
                  f"or reject {r['id']}")
    agent_commit(f"ingest(prd): stage {prd_id} v{version} + {cr_id}")


def _pending_cr(cmd, args):
    """Shared front half of approve-cr / reject-cr: the report, the human, the
    PRD, and the proof that the report belongs to that PRD and is pending."""
    if not args or args[0].startswith("--"):
        sys.exit(f"usage: wiki {cmd} CR-NNN --by <user> [--prd <id>]")
    cr_id = args[0]
    if not re.fullmatch(r"CR-\d+", cr_id):
        sys.exit(f"{cmd}: '{cr_id}' is not a report id (expected CR-NNN)")
    by = arg_after(args, "--by") if "--by" in args else None
    if not by or by.strip() == "" or by.startswith("--"):
        sys.exit(f"{cmd}: --by <user> required (human-gated); "
                 f"got {by!r}")
    manifest = load_manifest()
    prd_id = resolve_prd_arg(manifest, args)
    crp = cr_file(prd_id, cr_id)
    if not crp.exists():
        base = ROOT / "changereports"
        owner = next((p.parent.name for p in sorted(base.rglob(f"{cr_id}.md"))),
                     None) if base.exists() else None
        if owner:
            sys.exit(f"{cmd} refused: {cr_id} belongs to PRD {owner}, not "
                     f"{prd_id}.\n  Re-run with --prd {owner}.")
        sys.exit(f"{cmd}: {cr_id} not found under changereports/{prd_id}/")
    cfm, cbody = read_concept(crp)
    if cfm.get("status") != "pending":
        sys.exit(f"{cr_id} is '{cfm.get('status')}', not pending")
    return cr_id, by, prd_id, manifest, crp, cfm, cbody


def _refuse_if_not_current(cr_id, cfm, manifest, prd_id):
    """Only the report for the PRD's staged version, written against the
    version now adopted, may be approved. Anything else would move the adopted
    version sideways or backwards. Refuses before anything is written."""
    staged_v = staged_version(manifest, prd_id)
    adopted = adopted_version(manifest, prd_id)
    to_v, from_v = cfm.get("to_version"), cfm.get("from_version")
    if to_v == staged_v and adopted is not None and to_v > adopted \
            and from_v == adopted:
        return
    live = [r["id"] for r in reports_for_prd(prd_id)
            if r.get("status") == "pending" and r["id"] != cr_id
            and r.get("to_version") == staged_v
            and r.get("from_version") == adopted]
    if staged_v is None:
        sys.exit(f"approve-cr refused: {cr_id} (PRD {prd_id} v{from_v} -> "
                 f"v{to_v}) was superseded: v{adopted} is already adopted and "
                 f"nothing is staged.\n  It can only be rejected: "
                 f"reject-cr {cr_id} --by <user> --prd {prd_id}")
    hint = (f"Act on {live[-1]} instead (v{adopted} -> v{staged_v})." if live else
            f"No pending report matches the staged v{staged_v}.")
    sys.exit(f"approve-cr refused: {cr_id} (PRD {prd_id} v{from_v} -> v{to_v}) "
             f"can no longer be approved: adopted is v{adopted}, staged is "
             f"v{staged_v}.\n  {hint}\n  Reject {cr_id} if it is no longer "
             f"wanted.")


def cmd_approve(args):
    cr_id, by, prd_id, manifest, crp, cfm, cbody = _pending_cr("approve-cr", args)
    to_v = cfm["to_version"]
    _refuse_if_not_current(cr_id, cfm, manifest, prd_id)
    staged = read_staged(prd_id, to_v, "approve-cr")
    old = current_prd_sections(prd_id)
    diff = compute_diff(old, staged["sections"])
    outdir = ROOT / "sources/prd" / prd_id
    for m in diff["modified"]:
        p = outdir / f"{m['slug']}.md"
        fm, body = read_concept(p)
        old_v = fm["prd_version"]
        live, *hist = re.split(r"(^# Superseded \(v\d+\)\s*$)", body,
                               flags=re.MULTILINE)
        new_body = (m["new"]["body"] + "\n\n" + f"# Superseded (v{old_v})\n\n" +
                    live.strip() + ("\n" + "".join(hist) if hist else "") + "\n")
        fm["prd_version"] = to_v
        fm["content_hash"] = m["new"]["content_hash"]
        fm["source_file"] = staged["source_file"]
        fm["heading_path"] = m["new"]["heading_path"]
        fm.pop("removed_in", None)
        write_concept(p, fm, new_body)
        manifest["sources"][fm["id"]] = {"content_hash": fm["content_hash"],
                                         "prd_version": to_v, "prd": prd_id}
    for a in diff["added"]:
        n = a["new"]
        fm = {"type": "PRD Section", "id": f"prd#{prd_id}/{n['slug']}",
              "title": (f"{n['num']} {n['title']}" if n["num"] else n["title"]),
              "description": f"PRD v{to_v} section: {n['title']}",
              "prd": prd_id,
              "prd_version": to_v, "content_hash": n["content_hash"],
              "source_file": staged["source_file"],
              "heading_path": n["heading_path"]}
        write_concept(outdir / f"{n['slug']}.md", fm, n["body"] + "\n")
        manifest["sources"][fm["id"]] = {"content_hash": n["content_hash"],
                                         "prd_version": to_v, "prd": prd_id}
    for u in diff["unchanged"]:
        if u["old"].get("removed_in"):      # restored unchanged: no longer removed
            p = outdir / f"{u['slug']}.md"
            fm, body = read_concept(p)
            fm.pop("removed_in", None)
            write_concept(p, fm, body)
            manifest["sources"].get(fm["id"], {}).pop("removed_in", None)
    for r in diff["removed"]:
        p = outdir / f"{r['slug']}.md"
        fm, body = read_concept(p)
        fm["removed_in"] = to_v
        write_concept(p, fm, body)
        manifest["sources"].setdefault(fm["id"], {
            "content_hash": fm["content_hash"],
            "prd_version": fm["prd_version"], "prd": prd_id})["removed_in"] = to_v
    for mv in diff["moved"]:
        p = outdir / f"{mv['old_slug']}.md"
        fm, body = read_concept(p)
        aka = fm.get("also_known_as") or []
        fm["also_known_as"] = aka + [mv["new_slug"]]
        fm["prd_version"] = to_v
        write_concept(p, fm, body)
        manifest["sources"][fm["id"]]["prd_version"] = to_v

    set_prd_versions(manifest, prd_id, adopted=to_v)
    if staged_version(manifest, prd_id) == to_v:
        set_prd_versions(manifest, prd_id, staged=None)
    cfm["status"] = "approved"
    cfm["asserted_by"] = by
    cfm["asserted_at"] = now_iso()
    write_concept(crp, cfm, cbody)
    save_manifest(manifest)
    append_log(f"**Approval ({by})**: {cr_id} approved — PRD {prd_id} v{to_v} "
               "adopted; cascade fired")
    print(f"{cr_id} approved by {by}: adopted {prd_id} v{to_v} "
          f"({len(diff['modified'])} updated, {len(diff['added'])} added, "
          f"{len(diff['removed'])} removed-flagged, {len(diff['moved'])} aliased)")
    # spec §12.3: approval fires the staleness cascade. It compares every
    # aligned story's source_pins with the manifest's source hashes, so only
    # stories citing a section this approval changed are flagged.
    # (no commit of its own: the one commit below carries the Assertion-Event)
    from wiki import cmd_cascade
    cmd_cascade(commit=False)
    agent_commit(f"approve-cr({cr_id}): adopt PRD {prd_id} v{to_v} by {by}\n\n"
                 f"Assertion-Event: cli-approve-cr {cr_id} by {by} at {now_iso()}")


def cmd_reject(args):
    cr_id, by, prd_id, manifest, crp, cfm, cbody = _pending_cr("reject-cr", args)
    cfm["status"] = "rejected"
    cfm["asserted_by"] = by
    cfm["asserted_at"] = now_iso()
    write_concept(crp, cfm, cbody)
    adopted, staged_v = adopted_version(manifest, prd_id), staged_version(manifest, prd_id)
    state = (f"staged v{staged_v} kept, adopted stays v{adopted}" if staged_v
             else f"adopted stays v{adopted}, nothing staged")
    append_log(f"**Rejection ({by})**: {cr_id} rejected — {prd_id}: {state}; "
               "generation stays pinned")
    print(f"{cr_id} rejected by {by}; {prd_id} {state}")
    agent_commit(f"reject-cr({cr_id}): by {by}\n\n"
                 f"Assertion-Event: cli-reject-cr {cr_id} by {by} at {now_iso()}")


def cmd_diff(args):
    """wiki diff --prd [<id>] : adopted vs staged for one PRD (no side effects)."""
    manifest = load_manifest()
    prd_id = resolve_prd_arg(manifest, args)
    staged_v = staged_version(manifest, prd_id)
    if not staged_v:
        sys.exit(f"diff: no staged version for PRD {prd_id}")
    staged = read_staged(prd_id, staged_v, "diff")
    diff = compute_diff(current_prd_sections(prd_id), staged["sections"])
    print(f"PRD {prd_id} v{adopted_version(manifest, prd_id)} (adopted) vs "
          f"v{staged_v} (staged):")
    for m in diff["modified"]:
        print(f"  modified  {m['old']['title']}")
    for a in diff["added"]:
        print(f"  added     {a['new']['num']} {a['new']['title']}")
    for r in diff["removed"]:
        print(f"  removed   {r['old']['title']}")
    for mv in diff["moved"]:
        print(f"  moved     {mv['old']['title']} -> {mv['new']['num']}")
    print(f"  unchanged {len(diff['unchanged'])}")


def cmd_change(cmd, args):
    {"approve-cr": cmd_approve, "reject-cr": cmd_reject, "diff": cmd_diff}[cmd](args)
