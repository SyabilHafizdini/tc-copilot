#!/usr/bin/env python3
"""The Flow Builder's backend: the read model its page stitches from, and
`wiki flow-draft <file>`, which turns a drawing into a DRAFT flow concept.

The human drew the journey; that makes it a proposal, not an assertion. The
flow is written at `status: draft` and still goes through tc-align (the card,
the scenario model, `assert flow --card`) before any UAT test case can be
generated from it. This command never writes `aligned` and never replaces a
flow that has been asserted.
"""
import json
import re
from pathlib import Path

from wiki import (ROOT, agent_commit, append_log, body_section, fragment_ids,
                  load_all, resolve_ref, write_concept)

ID_OK = re.compile(r"^[A-Za-z0-9][A-Za-z0-9-]*$")


class Refusal(Exception):
    """The draft cannot become a flow; the message says what to fix."""


def builder_model(concepts, cfg):
    """What the app's Flow Builder page stitches from: every story's criteria
    with the SIT test cases behind each, and the existing flows' journeys.
    Read-only and pure over the loaded concepts."""
    stories, flows, sit = {}, {}, {}
    for rel, (fm, body, _p) in concepts.items():
        if not fm:
            continue
        if fm.get("type") == "User Story":
            stories[rel] = fm
        elif fm.get("type") == "Flow":
            flows[rel] = fm
        elif (fm.get("type") == "Test Case" and fm.get("kind") != "uat"
              and fm.get("status") != "retired"):
            sit[rel] = (fm, body or "")
    covering, tcs, tc_id = {}, {}, {}
    for rel, (fm, body) in sorted(sit.items()):
        tc_id[rel] = fm["id"]
        acs = []
        for ref in fm.get("covers") or []:
            tgt, frag = resolve_ref(ref)
            covering.setdefault(f"{tgt}#{frag}", []).append(fm["id"])
            if tgt in stories and frag:
                acs.append(f"{stories[tgt]['id']}#{frag}")
        tcs[fm["id"]] = {"id": fm["id"], "title": fm.get("title"), "acs": acs,
                         "sections": {"Postconditions":
                                      body_section(body, "Postconditions") or ""}}
    story_rows = [{
        "id": fm["id"], "title": fm.get("title"), "status": fm.get("status"),
        "acs": [{"id": ac["id"], "title": ac.get("title"), "text": ac.get("text"),
                 "status": ac.get("status"),
                 "tcs": sorted(covering.get(f"{rel}#{ac['id']}", []))}
                for ac in fm.get("acceptance_criteria") or []],
    } for rel, fm in sorted(stories.items())]
    flow_rows = []
    for rel, fm in sorted(flows.items()):
        branches = {b["id"]: b for b in fm.get("branches") or []}
        journey = []
        for j in fm.get("journey") or []:
            srel, sfrag = resolve_ref(j.get("ref") or "")
            sfm = stories.get(srel)
            b = branches.get(resolve_ref(j["branch"])[1]) if j.get("branch") else None
            journey.append({
                "id": j["id"], "end_state": j.get("end_state"), "note": j.get("note"),
                "ac_ref": f"{sfm['id']}#{sfrag}" if sfm and sfrag else None,
                "source_tc": tc_id.get(resolve_ref(j["source_tc"])[0])
                if j.get("source_tc") else None,
                "branch": {"id": b["id"], "title": b.get("title")} if b else None})
        flow_rows.append({"id": fm["id"], "title": fm.get("title"),
                          "status": fm.get("status"),
                          "entry_condition": fm.get("entry_condition"),
                          "journey": journey})
    return {"project": cfg["project"]["name"], "code": cfg["project"].get("code"),
            "stories": story_rows, "flows": flow_rows, "tcs": tcs}


OVERVIEW_GLOBAL = "__TC_FLOW_OVERVIEW__"


def overview_html(model, bundle):
    """The app bundle with the flows baked in: one file that opens straight to
    the Flow Overview with no server behind it. Carries only what that page
    draws: criteria, journeys, the page title and each journey entry's own
    test case row (`journey_tcs`), never the test cases behind a criterion.
    Pure."""
    data = {"project": model["project"], "code": model.get("code"),
            "stories": [{**s, "acs": [{**ac, "tcs": []} for ac in s["acs"]]}
                        for s in model["stories"]],
            "flows": [{**f, "journey": [{**j, "source_tc": None} for j in f["journey"]]}
                      for f in model["flows"]],
            "tcs": {},
            "overview_title": model.get("overview_title"),
            "journey_tcs": model.get("journey_tcs") or {}}
    # "<" is escaped so no text in a flow can close the script element
    payload = json.dumps(data, ensure_ascii=False).replace("<", "\\u003c")
    head = re.search(r"<head[^>]*>", bundle, re.I)
    if not head:
        raise Refusal("the app bundle has no <head> to carry the flows")
    return (bundle[:head.end()] + f"<script>window.{OVERVIEW_GLOBAL} = {payload};</script>"
            + bundle[head.end():])


def draft_to_flow(draft, concepts):
    """(rel, frontmatter, body) for the draft, or raise Refusal. Pure."""
    if draft.get("kind") != "flow-draft":
        raise Refusal("not a Flow Builder drawing (kind is not 'flow-draft')")
    fid = (draft.get("id") or "").strip()
    if not ID_OK.match(fid):
        raise Refusal(f"flow id {fid!r} may use letters, digits and hyphens only")
    title = (draft.get("title") or "").strip()
    if not title:
        raise Refusal("the flow has no title")
    rel = f"flows/{fid}"
    existing = concepts.get(rel, (None, None, None))[0]
    if existing and existing.get("status") not in ("draft", "in-alignment"):
        raise Refusal(
            f"{fid} already exists and is '{existing.get('status')}'. A drawing "
            "never replaces an asserted flow: export it under a new id, or "
            "correct the asserted one through tc-align / tc-correct.")
    story_rel = {fm["id"]: r for r, (fm, _b, _p) in concepts.items()
                 if fm and fm.get("type") == "User Story"}
    # live SIT test cases a step may stitch in: id -> (rel, refs it covers)
    sit = {fm["id"]: (r, {"#".join(resolve_ref(c)) for c in fm.get("covers") or []
                          if "#" in c})
           for r, (fm, _b, _p) in concepts.items()
           if fm and fm.get("type") == "Test Case" and fm.get("kind") != "uat"
           and fm.get("status") != "retired"}
    journey_in = draft.get("journey") or []
    if not journey_in:
        raise Refusal("the journey is empty")
    branch_ids = {b.get("id") for b in draft.get("branches") or []}
    journey, stories, seen = [], [], set()
    for e in journey_in:
        jid = e.get("id")
        if not jid or jid in seen:
            raise Refusal(f"journey entry id {jid!r} is missing or repeated")
        seen.add(jid)
        sid, _, frag = (e.get("ref") or "").partition("#")
        srel = story_rel.get(sid)
        if not srel or frag not in fragment_ids(concepts[srel][0]):
            raise Refusal(f"{jid}: section {e.get('ref')!r} does not exist in the wiki")
        if not (e.get("end_state") or "").strip():
            raise Refusal(f"{jid}: no end state (every journey step needs one)")
        row = {"id": jid, "ref": f"/{srel}.md#{frag}", "end_state": e["end_state"].strip()}
        if e.get("source_tc"):
            tc_rel, covered = sit.get(e["source_tc"], (None, set()))
            if not tc_rel:
                raise Refusal(f"{jid}: test case {e['source_tc']!r} does not exist "
                              "(or is UAT or retired)")
            if f"{srel}#{frag}" not in covered:
                raise Refusal(f"{jid}: test case {e['source_tc']} does not cover "
                              f"{e['ref']}")
            row["source_tc"] = f"/{tc_rel}.md"
        if e.get("note"):
            row["note"] = e["note"]
        if e.get("branch"):
            if e["branch"] not in branch_ids:
                raise Refusal(f"{jid}: branch {e['branch']} is not defined")
            row["branch"] = f"/{rel}.md#{e['branch']}"
        journey.append(row)
        if f"/{srel}.md" not in stories:
            stories.append(f"/{srel}.md")
    stitched = sum(1 for r in journey if r.get("source_tc"))
    fm = {"type": "Flow", "id": fid, "title": title,
          "description": f"Journey drawn in the flow builder: {len(journey)} steps"
                         + (f", {len(branch_ids)} branches" if branch_ids else "") + ".",
          "status": "draft", "origin": "human-drafted"}
    if (draft.get("entry_condition") or "").strip():
        fm["entry_condition"] = draft["entry_condition"].strip()
    fm["stories"] = stories
    fm["journey"] = journey
    if draft.get("branches"):
        fm["branches"] = [{"id": b["id"], "title": b.get("title") or b["id"],
                           "text": b.get("text") or ""} for b in draft["branches"]]
    paths = draft.get("paths") or []
    body = ("\n# Summary\n\n"
            f"Drawn by a human in the flow builder; {len(journey)} journey entries, "
            f"{stitched} stitched from a SIT test case (`source_tc`). "
            "Not yet aligned: the journey and its scenario model are confirmed on "
            "the alignment card.\n\n"
            "# Possible paths\n\n"
            + ("".join(f"- {'main' if i == 0 else f'alt {i}'}: {' > '.join(p)}\n"
                       for i, p in enumerate(paths)) or "_(single path)_\n")
            + "\n# Open Questions\n\n"
            "- Confirm the journey, the branches and the scenario model on the "
            "alignment card (tc-align).\n")
    return rel, fm, body


def cmd_flow_draft(args):
    files = [a for a in args if not a.startswith("--")]
    if not files:
        raise SystemExit("usage: wiki flow-draft <flow-draft-ID.json>")
    path = Path(files[0])
    try:
        draft = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        raise SystemExit(f"flow-draft: cannot read {path}: {e}")
    concepts, _manifest = load_all()
    try:
        rel, fm, body = draft_to_flow(draft, concepts)
    except Refusal as e:
        raise SystemExit(f"flow-draft: REFUSED - {e}")
    write_concept(ROOT / f"{rel}.md", fm, body)
    append_log(f"flow-draft: {fm['id']} drafted from the flow builder "
               f"({len(fm['journey'])} journey entries)")
    print(f"flow-draft: wrote {rel}.md at status draft "
          f"({len(fm['journey'])} journey entries, {len(fm.get('branches') or [])} branches)")
    print("  next: `wiki manifest`, `wiki index`, then align it (tc-align) - the "
          "card, the scenario model, the human's assert. Nothing generates "
          "from a draft.")
    agent_commit(f"flow-draft({fm['id']}): journey drawn in the flow builder (draft)")
