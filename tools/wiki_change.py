#!/usr/bin/env python3
"""Change management (tc-copilot-spec §12): PRD re-ingestion staging,
change reports, approval/rejection, on-demand diff.

Staging is write-only until human approval: `sources/prd/` concepts and
`adopted_prd_version` are untouched by ingestion of a newer version (spec
§5.1.5). Approval is per-report, as a unit, human-gated. Classification of
each change (editorial|material) is LLM/agent-proposed by EDITING the CR
before approval — this module writes 'unclassified'.
"""
import difflib
import json
import re
import sys

from wiki import (ROOT, agent_commit, append_log, load_all, load_manifest,
                  now_iso, read_concept, resolve_ref, save_manifest,
                  write_concept)


def next_cr_number():
    nums = [int(m.group(1)) for p in (ROOT / "changereports").glob("CR-*.md")
            if (m := re.match(r"CR-(\d+)", p.stem))] if \
        (ROOT / "changereports").exists() else []
    return max(nums, default=0) + 1


def current_prd_sections():
    out = {}
    for p in sorted((ROOT / "sources/prd").glob("*.md")):
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
                           "body": live, "prd_version": fm.get("prd_version")}
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
        else:
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


def impact_analysis(changed_slugs, concepts, manifest):
    """Deterministic traversal: changed sections -> stories -> TCs -> suites."""
    changed_rels = {f"sources/prd/{s}" for s in changed_slugs}
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


def stage_prd_version(sections, version, src_rel, manifest):
    staging = ROOT / "staging"
    staging.mkdir(exist_ok=True)
    (staging / f"prd-v{version}.json").write_text(
        json.dumps({"version": version, "source_file": src_rel,
                    "staged_at": now_iso(), "sections": sections},
                   indent=1, ensure_ascii=False),
        encoding="utf-8", newline="\n")
    old = current_prd_sections()
    diff = compute_diff(old, sections)
    concepts, _m = load_all()
    changed = [m["slug"] for m in diff["modified"]] + \
              [r["slug"] for r in diff["removed"]]
    stories, tcs, conflicts = impact_analysis(changed, concepts, manifest)

    crn = next_cr_number()
    cr_id = f"CR-{crn:03d}"
    fm = {"type": "Change Report", "id": cr_id,
          "title": f"{cr_id}: PRD v{manifest['adopted_prd_version']} -> v{version}",
          "description": f"{len(diff['modified'])} modified, {len(diff['added'])} "
                         f"added, {len(diff['removed'])} removed, "
                         f"{len(diff['moved'])} moved",
          "from_version": manifest["adopted_prd_version"],
          "to_version": version, "status": "pending"}
    L = ["# Summary", "",
         f"PRD v{fm['from_version']} -> v{version}: "
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
    (ROOT / "changereports").mkdir(exist_ok=True)
    write_concept(ROOT / "changereports" / f"{cr_id}.md", fm, "\n".join(L) + "\n")
    manifest["staged_prd_version"] = version
    save_manifest(manifest)
    append_log(f"**Change Report (agent)**: {cr_id} staged (v{fm['from_version']} -> "
               f"v{version}); adopted version unchanged")
    print(f"staged PRD v{version}; {cr_id} written "
          f"({fm['description']}); adopted stays v{fm['from_version']} until approval")
    agent_commit(f"ingest(prd): stage v{version} + {cr_id}")


def cmd_approve(args):
    cr_id = args[0]
    by = args[args.index("--by") + 1] if "--by" in args else None
    if not by:
        sys.exit("approve-cr: --by <user> required (human-gated)")
    crp = ROOT / "changereports" / f"{cr_id}.md"
    cfm, cbody = read_concept(crp)
    if cfm.get("status") != "pending":
        sys.exit(f"{cr_id} is '{cfm.get('status')}', not pending")
    to_v = cfm["to_version"]
    staged = json.loads((ROOT / "staging" / f"prd-v{to_v}.json")
                        .read_text(encoding="utf-8"))
    manifest = load_manifest()
    old = current_prd_sections()
    diff = compute_diff(old, staged["sections"])
    outdir = ROOT / "sources/prd"
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
        write_concept(p, fm, new_body)
        manifest["sources"][fm["id"]] = {"content_hash": fm["content_hash"],
                                         "prd_version": to_v}
    for a in diff["added"]:
        n = a["new"]
        fm = {"type": "PRD Section", "id": f"prd#{n['slug']}",
              "title": (f"{n['num']} {n['title']}" if n["num"] else n["title"]),
              "description": f"PRD v{to_v} section: {n['title']}",
              "prd_version": to_v, "content_hash": n["content_hash"],
              "source_file": staged["source_file"],
              "heading_path": n["heading_path"]}
        write_concept(outdir / f"{n['slug']}.md", fm, n["body"] + "\n")
        manifest["sources"][fm["id"]] = {"content_hash": n["content_hash"],
                                         "prd_version": to_v}
    for r in diff["removed"]:
        p = outdir / f"{r['slug']}.md"
        fm, body = read_concept(p)
        fm["removed_in"] = to_v
        write_concept(p, fm, body)
    for mv in diff["moved"]:
        p = outdir / f"{mv['old_slug']}.md"
        fm, body = read_concept(p)
        aka = fm.get("also_known_as") or []
        fm["also_known_as"] = aka + [mv["new_slug"]]
        fm["prd_version"] = to_v
        write_concept(p, fm, body)
        manifest["sources"][fm["id"]]["prd_version"] = to_v

    manifest["adopted_prd_version"] = to_v
    manifest["staged_prd_version"] = None
    cfm["status"] = "approved"
    cfm["asserted_by"] = by
    cfm["asserted_at"] = now_iso()
    write_concept(crp, cfm, cbody)
    save_manifest(manifest)
    append_log(f"**Approval ({by})**: {cr_id} approved — PRD v{to_v} adopted; "
               "cascade fired")
    print(f"{cr_id} approved by {by}: adopted v{to_v} "
          f"({len(diff['modified'])} updated, {len(diff['added'])} added, "
          f"{len(diff['removed'])} removed-flagged, {len(diff['moved'])} aliased)")
    # spec §12.3: approval fires the staleness cascade
    from wiki import cmd_cascade
    cmd_cascade()
    agent_commit(f"approve-cr({cr_id}): adopt PRD v{to_v} by {by}\n\n"
                 f"Assertion-Event: cli-approve-cr {cr_id} by {by} at {now_iso()}")


def cmd_reject(args):
    cr_id = args[0]
    by = args[args.index("--by") + 1] if "--by" in args else None
    if not by:
        sys.exit("reject-cr: --by <user> required")
    crp = ROOT / "changereports" / f"{cr_id}.md"
    cfm, cbody = read_concept(crp)
    if cfm.get("status") != "pending":
        sys.exit(f"{cr_id} is '{cfm.get('status')}', not pending")
    cfm["status"] = "rejected"
    cfm["asserted_by"] = by
    cfm["asserted_at"] = now_iso()
    write_concept(crp, cfm, cbody)
    append_log(f"**Rejection ({by})**: {cr_id} rejected — staged version remains "
               "ingested-but-not-adopted; generation stays pinned")
    print(f"{cr_id} rejected by {by}; staged v{cfm['to_version']} kept, "
          f"adopted stays v{cfm['from_version']}")
    agent_commit(f"reject-cr({cr_id}): by {by}\n\n"
                 f"Assertion-Event: cli-reject-cr {cr_id} by {by} at {now_iso()}")


def cmd_diff(args):
    """wiki diff --prd : adopted vs staged, printed (no side effects)."""
    manifest = load_manifest()
    staged_v = manifest.get("staged_prd_version")
    if not staged_v:
        sys.exit("diff: no staged PRD version")
    staged = json.loads((ROOT / "staging" / f"prd-v{staged_v}.json")
                        .read_text(encoding="utf-8"))
    diff = compute_diff(current_prd_sections(), staged["sections"])
    print(f"PRD v{manifest['adopted_prd_version']} (adopted) vs v{staged_v} (staged):")
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
