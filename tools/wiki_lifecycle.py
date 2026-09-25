#!/usr/bin/env python3
"""TC lifecycle (tc-copilot-spec §13): retire / void-ac / unretire / release / revert.

All entry points are HUMAN-GATED (--by required): run them only at explicit
human instruction, from a confirmed card. The system never retires on its own —
except the sanctioned §13.3 void cascade, whose authority is the single human
AC-void assertion it inherits.

Files never move; `status: retired` IS the archive. IDs are never reused.
"""
import subprocess
import sys

from wiki import (ROOT, agent_commit, append_log, arg_after, load_manifest,
                  now_iso, read_concept, resolve_ref, save_manifest, sha256,
                  write_concept, load_all)


def find_tc(tc_id, concepts):
    for rel, (fm, body, p) in concepts.items():
        if fm and fm.get("type") == "Test Case" and fm.get("id") == tc_id:
            return rel, fm, body, p
    sys.exit(f"test case {tc_id} not found")


def require(args, flag):
    return arg_after(args, flag)


def sync_binding(manifest, rel, status):
    for sc, b in manifest.get("bindings", {}).items():
        if b["tc"] == rel:
            b["status"] = status
    if rel in manifest.get("concepts", {}):
        manifest["concepts"][rel]["status"] = status


def cmd_retire(args):
    tc_id = args[0]
    by = require(args, "--by")
    reason = require(args, "--reason")
    concepts, manifest = load_all()
    rel, fm, body, p = find_tc(tc_id, concepts)
    if fm.get("status") == "retired":
        sys.exit(f"{tc_id} is already retired")
    ret = {"reason": reason, "asserted_by": by, "asserted_at": now_iso()}
    if "--note" in args:
        ret["note"] = arg_after(args, "--note")

    if reason == "superseded":
        succ_id = require(args, "--superseded-by")
        srel, sfm, sbody, sp = find_tc(succ_id, concepts)
        if sfm.get("status") != "active":
            sys.exit(f"retire refused: successor {succ_id} is "
                     f"'{sfm.get('status')}', must be active (L5)")
        mine = set(fm.get("covers") or [])
        voided = set()
        for r, (cfm, _b, _p) in concepts.items():
            if cfm and cfm.get("type") == "User Story":
                for ac in cfm.get("acceptance_criteria") or []:
                    if ac.get("status") == "voided":
                        voided.add(f"/{r}.md#{ac['id']}")
        active_mine = {c for c in mine if c not in voided}
        theirs = set(sfm.get("covers") or [])
        missing = active_mine - theirs
        if missing:
            sys.exit(f"retire refused (L5): successor {succ_id} does not cover "
                     f"{sorted(missing)}")
        ret["superseded_by"] = f"/{srel}.md"
        # reciprocal supersedes on successor, same commit (L9 / §13.2)
        sup = sfm.get("supersedes") or []
        sup = [sup] if isinstance(sup, str) else sup
        if f"/{rel}.md" not in sup:
            sfm["supersedes"] = sup + [f"/{rel}.md"]
            write_concept(sp, sfm, sbody)
            manifest["tc_hashes"][srel] = sha256(sp.read_bytes())
    elif reason == "voided":
        ret["caused_by"] = require(args, "--caused-by")
        ret["cause_version"] = int(require(args, "--cause-version"))
    else:
        sys.exit("--reason must be voided|superseded (closed vocabulary, §13.2)")

    fm["status"] = "retired"
    fm["retirement"] = ret
    write_concept(p, fm, body)
    manifest["tc_hashes"][rel] = sha256(p.read_bytes())
    sync_binding(manifest, rel, "retired")
    save_manifest(manifest)
    link = ret.get("superseded_by") or f"{ret.get('caused_by')} v{ret.get('cause_version')}"
    append_log(f"**Retirement ({by})**: {tc_id} {reason} — {link}")
    print(f"retired {tc_id} ({reason}) by {by}")
    agent_commit(f"retire({tc_id}): {reason} by {by}\n\n"
                 f"Assertion-Event: cli-retire {tc_id} by {by} at {now_iso()}")


def cmd_void_ac(args):
    """§13.3: human voids the AC; TCs whose covers ⊆ voided ACs cascade to
    retired:voided (inherited authority); mixed-coverage TCs go stale."""
    frag_ref = args[0]                     # /stories/US-X.md#AC-...
    by = require(args, "--by")
    caused_by = require(args, "--caused-by")
    cause_version = int(require(args, "--cause-version"))
    note = arg_after(args, "--note") if "--note" in args else None
    concepts, manifest = load_all()
    story_rel, ac_id = resolve_ref(frag_ref)
    if story_rel not in concepts:
        sys.exit(f"story {story_rel} not found")
    sfm, sbody, sp = concepts[story_rel]
    hit = None
    for ac in sfm.get("acceptance_criteria") or []:
        if ac["id"] == ac_id:
            hit = ac
    if not hit:
        sys.exit(f"AC {ac_id} not found in {story_rel}")
    if hit.get("status") == "voided":
        sys.exit(f"AC {ac_id} is already voided")
    hit["status"] = "voided"
    hit["voided"] = {"caused_by": caused_by, "cause_version": cause_version,
                     "asserted_by": by, "asserted_at": now_iso()}
    if note:
        hit["voided"]["note"] = note
    write_concept(sp, sfm, sbody)

    # recompute the full voided set including this one
    voided = set()
    for r, (cfm, _b, _p) in concepts.items():
        if cfm and cfm.get("type") == "User Story":
            for ac in cfm.get("acceptance_criteria") or []:
                if ac.get("status") == "voided":
                    voided.add(f"/{r}.md#{ac['id']}")
    voided.add(frag_ref)

    cascaded, staled = [], []
    for rel, (fm, body, p) in concepts.items():
        if not fm or fm.get("type") != "Test Case" or fm.get("status") not in \
                ("active", "stale"):
            continue
        covers = set(fm.get("covers") or [])
        if not covers or frag_ref not in covers:
            continue
        if covers <= voided:
            fm["status"] = "retired"
            fm["retirement"] = {
                "reason": "voided", "caused_by": caused_by,
                "cause_version": cause_version, "asserted_by": by,
                "asserted_at": now_iso(),
                "note": f"cascaded from void of {frag_ref} (spec §13.3; authority "
                        "inherited from the single human AC-void assertion)"}
            write_concept(p, fm, body)
            manifest["tc_hashes"][rel] = sha256(p.read_bytes())
            sync_binding(manifest, rel, "retired")
            cascaded.append(fm["id"])
        else:
            fm["status"] = "stale"
            fm.setdefault("stale_because", []).append(
                {"cause": f"ac-voided:{frag_ref}", "at": now_iso()})
            write_concept(p, fm, body)
            manifest["tc_hashes"][rel] = sha256(p.read_bytes())
            sync_binding(manifest, rel, "stale")
            staled.append(fm["id"])
    save_manifest(manifest)
    append_log(f"**Void ({by})**: {frag_ref} voided (cause {caused_by} "
               f"v{cause_version}); cascaded retired: {cascaded or 'none'}; "
               f"staled: {staled or 'none'}")
    print(f"voided {frag_ref}; retired(voided): {cascaded or '[]'}; "
          f"stale (mixed coverage, human decision pending): {staled or '[]'}")
    agent_commit(f"void-ac({ac_id}): by {by}, cascade retired {len(cascaded)}, "
                 f"staled {len(staled)}\n\n"
                 f"Assertion-Event: cli-void-ac {frag_ref} by {by} at {now_iso()}")


def cmd_unretire(args):
    """§7.4-4: explicit human resurrection permit. Retirement history is kept
    (append-only); the TC returns as stale for regeneration under its
    ORIGINAL ID."""
    tc_id = args[0]
    by = require(args, "--by")
    concepts, manifest = load_all()
    rel, fm, body, p = find_tc(tc_id, concepts)
    if fm.get("status") != "retired":
        sys.exit(f"{tc_id} is not retired")
    hist = fm.get("retirement_history") or []
    hist.append(fm.pop("retirement"))
    fm["retirement_history"] = hist
    fm["status"] = "stale"
    fm.setdefault("stale_because", []).append(
        {"cause": f"unretired by {by}", "at": now_iso()})
    # drop dangling reciprocal supersedes on the old successor if present
    last = hist[-1]
    if last.get("superseded_by"):
        srel, _f = resolve_ref(last["superseded_by"])
        if srel in concepts:
            sfm, sbody, sp = concepts[srel]
            sup = sfm.get("supersedes") or []
            sup = [sup] if isinstance(sup, str) else sup
            sfm["supersedes"] = [x for x in sup if resolve_ref(x)[0] != rel] or None
            if not sfm["supersedes"]:
                sfm.pop("supersedes")
            write_concept(sp, sfm, sbody)
            manifest["tc_hashes"][srel] = sha256(sp.read_bytes())
    write_concept(p, fm, body)
    manifest["tc_hashes"][rel] = sha256(p.read_bytes())
    sync_binding(manifest, rel, "stale")
    save_manifest(manifest)
    append_log(f"**Unretire ({by})**: {tc_id} — resurrection permitted, pending regen")
    print(f"unretired {tc_id}; status=stale — regenerate to recreate under the same ID")
    agent_commit(f"unretire({tc_id}): by {by}\n\n"
                 f"Assertion-Event: cli-unretire {tc_id} by {by} at {now_iso()}")


def cmd_release(args):
    """§7.4-5: accept a hand-edit — re-hash, mark human-stated overlay."""
    tc_id = args[0]
    by = require(args, "--by")
    concepts, manifest = load_all()
    rel, fm, body, p = find_tc(tc_id, concepts)
    cur = sha256(p.read_bytes())
    if manifest["tc_hashes"].get(rel) == cur:
        sys.exit(f"{tc_id} has no drift — nothing to release")
    fm["origin"] = "human-stated"
    fm["released"] = {"by": by, "at": now_iso(),
                      "note": "hand-edit accepted via wiki release; regeneration "
                              "will overwrite unless re-edited"}
    write_concept(p, fm, body)
    manifest["tc_hashes"][rel] = sha256(p.read_bytes())
    save_manifest(manifest)
    append_log(f"**Release ({by})**: {tc_id} hand-edit accepted, re-hashed")
    print(f"released {tc_id}: drift accepted, manifest re-hashed")
    agent_commit(f"release({tc_id}): drift accepted by {by}\n\n"
                 f"Assertion-Event: cli-release {tc_id} by {by} at {now_iso()}")


def cmd_revert(args):
    """§7.4-5: discard a hand-edit — restore the file to HEAD."""
    tc_id = args[0]
    concepts, manifest = load_all()
    rel, fm, body, p = find_tc(tc_id, concepts)
    cur = sha256(p.read_bytes())
    if manifest["tc_hashes"].get(rel) == cur:
        sys.exit(f"{tc_id} has no drift — nothing to revert")
    subprocess.run(["git", "checkout", "HEAD", "--", rel + ".md"],
                   cwd=ROOT, check=True)
    restored = sha256((ROOT / (rel + ".md")).read_bytes())
    if manifest["tc_hashes"].get(rel) != restored:
        sys.exit(f"revert: HEAD content still differs from manifest hash for "
                 f"{tc_id} — the drift was committed; resolve manually or release")
    print(f"reverted {tc_id}: file restored to manifest-sealed content")


def cmd_lifecycle(cmd, args):
    {"retire": cmd_retire, "void-ac": cmd_void_ac, "unretire": cmd_unretire,
     "release": cmd_release, "revert": cmd_revert}[cmd](args)
