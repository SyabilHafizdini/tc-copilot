#!/usr/bin/env python3
"""`wiki triage` -- route files dumped in PUT_FILES_HERE/ into the typed
intake tree (spec: intake triage design, 2026-08-24).

Deterministic and LLM-free. Classification is a pure function of the
filename and the current manifest; the command layer (cmd_triage) is the
only part that touches the filesystem.

Why refusals matter more than routing here: a Figma PNG's filename stem
becomes the page's PERMANENT concept id (figma#<stem>), and a PRD's folder
name IS its version. Guessing either wrong writes an identity that later
concepts reference forever, so an ambiguous name is refused, never guessed.
"""
import hashlib
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from wiki import FURNITURE, ROOT, sha256

# A stem that is a real page name, not a camera/clipboard artefact -- or a
# Figma default node name nobody renamed (Frame 12, Group3, Rectangle 5, ...).
# These become permanent ids, so the bar is "a human chose this word".
_JUNK_STEM = re.compile(
    r"^(screenshot|screen[ _-]?shot|pasted|paste|image|img|unnamed|untitled|"
    r"document|new file|frame|group|rectangle|ellipse|component|vector|slice)"
    r"[\s_\-]*[\d()\[\]\-_. ]*$", re.IGNORECASE)

# Documents a PRD reader can parse. Whether one IS the PRD is a semantic
# question (does it carry acceptance criteria?), so these are always asked,
# never auto-routed.
PRD_EXT = {".pdf", ".md", ".docx"}

# Formats that cannot be a PRD but hint at a better-supported sibling. The
# file still becomes reference material; the hint just says how to do better.
_HINTS = {
    ".jpg": "if this is a Figma page, convert to .png and re-run",
    ".jpeg": "if this is a Figma page, convert to .png and re-run",
    ".doc": "legacy .doc has no text reader -- save as .docx for a readable PRD",
    ".ppt": "legacy .ppt has no text reader -- save as .pptx for deck slides",
}

_PRD_OPTIONS = ["prd", "reference", "ignore"]
_REF_OPTIONS = ["reference", "ignore"]


def next_prd_version(manifest):
    """v1 when nothing is adopted, else adopted+1 (a newer PRD stages a
    change report -- see wiki_change.stage_prd_version)."""
    adopted = manifest.get("adopted_prd_version")
    return 1 if not adopted else int(adopted) + 1


def classify(path, manifest, root=ROOT, prd_version=None):
    """One dumped file -> a routing decision. Pure: never writes.

    Three outcomes. 'route' is decidable from the extension alone (png ->
    figma, pptx -> decks). 'ask' is a question for the human: a document that
    might be the PRD, or anything that cannot be a PRD and so is reference
    material by the project's own rule. 'refuse' is reserved for the cases
    where answering would write a permanent identity we cannot trust.
    """
    path = Path(path)
    ext = path.suffix.lower()
    out = {"src": path, "kind": None, "action": "ask", "dest": None,
           "reason": "", "proposed": "reference", "options": _REF_OPTIONS,
           "hint": _HINTS.get(ext, "")}

    # Ingest globs (rglob/glob "*.pdf" / "*.docx" / "*.png" / "*.pptx") are
    # LITERAL lowercase patterns. path.suffix.lower() above is only used to
    # pick the routing branch -- the file itself would be moved under its
    # original-case name. On Windows that happens to still glob-match
    # (case-insensitive filesystem); on POSIX it would not, so triage would
    # report success while ingest silently found nothing. Refuse rather than
    # silently rename -- the stem is a permanent identity.
    if path.suffix and path.suffix != ext and ext in (PRD_EXT | {".png", ".pptx"}):
        out["action"] = "refuse"
        out["reason"] = (f"'{path.name}' has a non-lowercase extension "
                         f"('{path.suffix}') -- ingest globs match a literal "
                         f"lowercase '*{ext}' and would silently find nothing "
                         f"on a case-sensitive filesystem; rename to "
                         f"'{path.stem}{ext}'")
        return out

    if ext in PRD_EXT:
        out["kind"] = "prd-candidate"
        out["options"] = _PRD_OPTIONS
        out["proposed"] = "prd" if not manifest.get("adopted_prd_version") else "reference"
        return out

    if ext == ".png":
        stem = path.stem
        out["kind"] = "figma"
        if " " in stem or "\t" in stem or _JUNK_STEM.match(stem):
            out["action"] = "refuse"
            out["reason"] = (f"'{stem}' is not a stable page name, and the stem "
                             f"becomes the page's permanent id (figma#{stem}) "
                             f"-- rename the file first, e.g. order-list-screen.png")
        else:
            out["action"] = "route"
            out["dest"] = root / "inputs/figma" / path.name
            out["replaces"] = out["dest"].exists()
        return out

    if ext == ".pptx":
        out["kind"] = "deck"
        out["action"] = "route"
        out["dest"] = root / "inputs/decks" / path.name
        out["replaces"] = out["dest"].exists()
        return out

    # Not a PRD-readable document, not figma, not a deck -> reference
    # material by the project's rule ("if it is not a PRD it is reference").
    out["kind"] = "reference"
    return out


def question_id(kind, rel):
    """Path-derived, stable, readable in the --answer flag.

    The readable slug alone is NOT injective: every non-alphanumeric run
    collapses to one hyphen, so 'L/a rules.yml' and 'L/a-rules.yml' would
    share an id, the card would carry two questions under it, and one of two
    legitimate files would become unanswerable. A short digest of the EXACT
    relative path restores injectivity without costing readability, and stays
    stable across runs because it depends on nothing but the path.
    """
    slug = re.sub(r"[^A-Za-z0-9]+", "-", rel).strip("-")
    digest = hashlib.sha256(rel.encode("utf-8")).hexdigest()[:6]
    return f"q-{kind}-{slug}-{digest}"


def plan_hash(plan, dump):
    """Fingerprint of what the human was shown. If the dump changes after the
    card is emitted, the answers describe a different reality.

    Paths are relative to the dump root: an absolute path would invalidate
    every emitted card the moment the repo is cloned or moved, even though
    the dump itself is identical.

    Includes the proposed classification, not just path and action: a card's
    `accept` answer means "take the proposed value", and a .pdf's proposal
    flips from prd to reference once a PRD version gets adopted. Without
    `proposed` in the fingerprint, that flip would go undetected -- the dump
    is unchanged, the hash still matches, and `accept` would silently resolve
    to a different classification than the human was shown."""
    dump = Path(dump)
    inv = sorted(f"{d['src'].relative_to(dump).as_posix()}:{d['action']}:"
                 f"{d.get('proposed')}" for d in plan)
    return sha256("\n".join(inv))


def folder_groups(plan, dump):
    """{folder relpath: [decisions]} for every directory that DIRECTLY holds
    askable files. A parent's answer never reaches into a subfolder -- one
    answer settling files three levels down is exactly the blanket approval
    this design exists to prevent. The dump root is never a group: files
    sitting loose at the top level are unrelated by construction.
    """
    groups = {}
    for d in plan:
        if d["action"] != "ask":
            continue
        rel = d["src"].relative_to(dump)
        parent = rel.parent.as_posix()
        if parent in (".", ""):
            continue
        groups.setdefault(parent, []).append(d)
    return groups


def build_card(plan, dump):
    """The triage card: one question per askable file, plus one per directory
    that directly holds askable files. Folder and member questions ship in the
    SAME card so answering is a single round with no stored state."""
    groups = folder_groups(plan, dump)
    parent_of = {}
    questions = []
    for folder in sorted(groups):
        members = groups[folder]
        fid = question_id("folder", folder)
        # A folder proposes "prd" only when EVERY member is itself a PRD
        # candidate. A folder mixing a document with rule files is mixed
        # material, and the project's rule is "if it is not a PRD it is
        # reference" -- so a non-uniform folder must propose the safe
        # (reference) classification, not sweep everything into inputs/prd/.
        proposed = ("prd" if all(m["proposed"] == "prd" for m in members)
                    else "reference")
        options = ["prd", "reference", "split", "ignore"]
        questions.append({"id": fid, "kind": "folder", "item": folder,
                          "members": len(members), "proposed": proposed,
                          "options": options})
        for m in members:
            parent_of[m["src"]] = fid
    for d in plan:
        if d["action"] != "ask":
            continue
        rel = d["src"].relative_to(dump).as_posix()
        q = {"id": question_id("file", rel), "kind": "file", "item": rel,
             "proposed": d["proposed"], "options": list(d["options"])}
        if d["src"] in parent_of:
            q["parent"] = parent_of[d["src"]]
        if d.get("hint"):
            q["hint"] = d["hint"]
        questions.append(q)
    return {"scope": "triage", "plan_hash": plan_hash(plan, dump),
            "open_questions": questions}


def write_card(card, root=ROOT):
    """Next-numbered build/cards/triage-NNN.json."""
    cdir = Path(root) / "build/cards"
    cdir.mkdir(parents=True, exist_ok=True)
    used = [int(m.group(1)) for p in cdir.glob("triage-*.json")
            if (m := re.match(r"triage-(\d+)\.json$", p.name))]
    path = cdir / f"triage-{max(used, default=0) + 1:03d}.json"
    path.write_text(json.dumps(card, indent=1, ensure_ascii=False) + "\n",
                    encoding="utf-8", newline="\n")
    return path


def collect_plan(root, manifest, prd_version=None):
    """Every file under root/PUT_FILES_HERE (recursively) -> a decision.
    Read-only. README.md, .gitkeep and friends are the dump's own
    furniture (wiki.FURNITURE), skipped."""
    dump = Path(root) / "PUT_FILES_HERE"
    if not dump.exists():
        return []
    plan = []
    for p in sorted(dump.rglob("*")):
        if not p.is_file():
            continue
        if p.name in FURNITURE:
            continue
        plan.append(classify(p, manifest, Path(root), prd_version))

    # Detect collisions: multiple routed files to the same destination
    dest_to_entries = {}
    for d in plan:
        if d["action"] == "route" and d["dest"]:
            if d["dest"] not in dest_to_entries:
                dest_to_entries[d["dest"]] = []
            dest_to_entries[d["dest"]].append(d)

    # Mark all entries in a collision as refuse
    for dest, entries in dest_to_entries.items():
        if len(entries) > 1:
            for d in entries:
                d["action"] = "refuse"
                other_src = ", ".join([e["src"].relative_to(dump).as_posix() for e in entries if e is not d])
                d["reason"] = f"two dumped files both route to {dest.relative_to(Path(root)).as_posix()} ({other_src}) -- rename one"

    return plan


def resolve_destinations(plan, resolved, card, dump, manifest, root=ROOT,
                         prd_version=None):
    """Turn each answered 'ask' decision into a concrete route (or ignore).

    A folder answer settles its members unless it is 'split', in which case
    each member's own answer applies.

    An unresolvable decision EXITS. Falling through to the reference route
    would classify a file the human never answered -- which is the one thing
    the card exists to prevent -- so 'no answer' is a refusal, never a
    default.
    """
    questions = {q["id"]: q for q in card.get("open_questions") or []}
    by_item = {}
    for q in questions.values():
        if q["kind"] == "file":
            by_item[q["item"]] = q
    claimed_prd = []

    for d in plan:
        if d["action"] != "ask":
            continue
        rel = d["src"].relative_to(dump).as_posix()
        q = by_item.get(rel)
        if q is None:
            sys.exit(f"triage --apply refused: '{rel}' is waiting in "
                     f"PUT_FILES_HERE/ but the card asks no question about "
                     f"it, so nothing classifies it.\n"
                     f"  Re-run: py tools/wiki.py triage, then answer the "
                     f"new card.")
        answer = None
        parent = q.get("parent")
        if parent and resolved.get(parent) not in (None, "split"):
            answer = resolved[parent]
        else:
            answer = resolved.get(q["id"])
        if answer is None:
            why = (f" (its folder question {parent} answered 'split', so this "
                   f"file needs its own answer)" if parent else "")
            sys.exit(f"triage --apply refused: no answer resolves '{rel}'"
                     f"{why} -- question {q['id']} is unanswered, and a file "
                     f"is never classified by default.\n"
                     f"  Answer it: py tools/wiki.py card revise <card> "
                     f"--by <you> --answer {q['id']}=accept")
        if answer == "ignore":
            d["action"] = "ignore"
            d["kind"] = None
            continue
        if answer == "prd":
            v = int(prd_version) if prd_version else next_prd_version(manifest)
            dest_dir = root / f"inputs/prd/v{v}"
            occupied = [p for p in dest_dir.glob("*")
                        if p.suffix.lower() in PRD_EXT] if dest_dir.exists() else []
            if occupied:
                sys.exit(
                    f"triage --apply refused: inputs/prd/v{v}/ already holds "
                    f"{occupied[0].name} -- ingest-prd reads one document per "
                    f"version.\n  Pass --prd-version N for a different "
                    f"version, or remove the existing document first.")
            # Two files answered 'prd' would both land in v{v}, and
            # latest_prd_input() picks files[0] -- one PRD would be ingested
            # and the other silently ignored. Refuse instead.
            if claimed_prd:
                sys.exit(
                    f"triage --apply refused: '{claimed_prd[0]}' and "
                    f"'{rel}' are both answered 'prd' for v{v} -- ingest-prd "
                    f"reads one document per version and would silently "
                    f"ingest only one.\n  Answer one of them 'reference', or "
                    f"apply them separately with --prd-version N.")
            claimed_prd.append(rel)
            d["kind"] = "prd"
            d["action"] = "route"
            d["dest"] = dest_dir / d["src"].name
            continue
        # reference: preserve the dumped subfolder structure. Grouping is
        # meaningful and flattening would collide repeated filenames.
        # `replaces` is set for the same reason the figma/deck routes set it:
        # the README promises nothing is ever deleted, and re-dumping a file
        # over an already-routed one must SAY so rather than clobber quietly.
        d["kind"] = "reference"
        d["action"] = "route"
        d["dest"] = root / "inputs/reference" / rel
        d["replaces"] = d["dest"].exists()


def apply_plan(plan):
    """Move every routed file to its destination. Returns the count moved.
    Refusals and ignored files are left exactly where they are."""
    import shutil
    moved = 0
    for d in plan:
        if d["action"] != "route":
            continue
        d["dest"].parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(d["src"]), str(d["dest"]))
        moved += 1
    return moved


_FOLLOW_UP = {"prd": "py tools/wiki.py ingest-prd",
              "figma": "py tools/wiki.py ingest-figma",
              "deck": "py tools/wiki.py ingest-decks",
              "reference": "py tools/wiki.py ingest-reference"}


# Re-running `triage` is the fix for every card-level refusal below: the card
# is derived from the dump, so a card that does not match the dump is stale by
# definition, and hand-editing it back into shape is exactly what the gate
# exists to stop.
_RETRIAGE = "  Re-run: py tools/wiki.py triage, then answer the new card."

# The fields a human's answer actually depends on. Compared field by field
# against a card recomputed from the CURRENT plan, so a hand-edited disk card
# cannot flip a proposal, widen an option set, or delete a question outright.
_Q_FIELDS = ("kind", "item", "parent", "members", "proposed", "options")


def _fingerprint(q):
    return {k: (list(q[k]) if isinstance(q.get(k), list) else q.get(k))
            for k in _Q_FIELDS}


def read_answers(card_path, plan, dump):
    """Validate the card against the CURRENT plan and return
    {question id -> resolved answer}. Exits non-zero on any gate failure.

    Every check here is a refusal rather than a warning: this is the only
    place a human's per-file decision is verified, and the whole point of the
    design is that no prose in SKILL.md is load-bearing (spec P3).

    The card on disk is never trusted to describe its own questions.
    `plan_hash` fingerprints the PLAN, not the card, so a card whose
    open_questions were emptied (or edited) still carries a matching hash --
    and an empty question list demands nothing, which routes every file on a
    card nobody answered. So the card is recomputed from the current plan and
    the disk copy must match it question for question before any answer is
    read.
    """
    path = Path(card_path)
    if not path.is_absolute():
        path = ROOT / path
    if not path.exists():
        sys.exit(f"triage --apply refused: card not found: {card_path}\n"
                 f"  Emit one: py tools/wiki.py triage")
    try:
        card = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        sys.exit(f"triage --apply refused: {path.name} is not valid JSON "
                 f"({e}).\n  Delete it and re-run: py tools/wiki.py triage")
    if not isinstance(card, dict) or card.get("scope") != "triage":
        scope = card.get("scope") if isinstance(card, dict) else None
        sys.exit(f"triage --apply refused: {path.name} is for '{scope}', not "
                 f"'triage'.\n  Pass the card `py tools/wiki.py triage` wrote "
                 f"under build/cards/triage-NNN.json, or re-run it to emit "
                 f"one.")
    hr = card.get("human_response")
    if not hr:
        sys.exit(f"triage --apply refused: {path.name} has no human_response "
                 f"-- it was never answered.\n"
                 f"  Run: py tools/wiki.py card revise "
                 f"{path.relative_to(ROOT).as_posix()} --by <you> --answer ...")
    current = plan_hash(plan, dump)
    if card.get("plan_hash") != current:
        sys.exit(f"triage --apply refused: plan_hash mismatch -- "
                 f"PUT_FILES_HERE/ changed since {path.name} was emitted, so "
                 f"the answers describe a different set of files.\n"
                 f"{_RETRIAGE}")

    # --- the card's OWN questions must be the questions triage asks today ---
    expected = {q["id"]: q for q in build_card(plan, dump)["open_questions"]}
    disk = card.get("open_questions")
    if not isinstance(disk, list):
        sys.exit(f"triage --apply refused: {path.name} has no open_questions "
                 f"list.\n{_RETRIAGE}")
    on_disk = {}
    for q in disk:
        if not isinstance(q, dict) or not isinstance(q.get("id"), str):
            sys.exit(f"triage --apply refused: {path.name} holds a question "
                     f"with no id.\n{_RETRIAGE}")
        gaps = [k for k in ("kind", "item", "proposed", "options") if k not in q]
        if gaps:
            sys.exit(f"triage --apply refused: question '{q['id']}' in "
                     f"{path.name} is missing {', '.join(gaps)} -- the card no "
                     f"longer describes a question triage can resolve.\n"
                     f"{_RETRIAGE}")
        if q["id"] in on_disk:
            sys.exit(f"triage --apply refused: {path.name} carries two "
                     f"questions with the id '{q['id']}'.\n{_RETRIAGE}")
        on_disk[q["id"]] = q
    extra = sorted(set(on_disk) - set(expected))
    absent = sorted(set(expected) - set(on_disk))
    if extra or absent:
        detail = ""
        if extra:
            detail += f"  in the card but not asked: {', '.join(extra[:5])}\n"
        if absent:
            detail += ("  asked but not in the card: "
                       + ", ".join(f"{m} ({expected[m]['item']})"
                                   for m in absent[:5]) + "\n")
        sys.exit(f"triage --apply refused: {path.name} carries "
                 f"{len(on_disk)} question(s); this dump asks "
                 f"{len(expected)}.\n{detail}{_RETRIAGE}")
    for qid in sorted(expected):
        want, got = _fingerprint(expected[qid]), _fingerprint(on_disk[qid])
        if want != got:
            drift = "; ".join(
                f"{k}: the card says {got[k]!r}, triage asks {want[k]!r}"
                for k in _Q_FIELDS if want[k] != got[k])
            sys.exit(f"triage --apply refused: question {qid} in {path.name} "
                     f"was edited -- {drift}.\n{_RETRIAGE}")

    given = hr.get("answers")
    if not isinstance(given, dict):
        sys.exit(f"triage --apply refused: {path.name} has a human_response "
                 f"with no answers map.\n"
                 f"  Run: py tools/wiki.py card revise "
                 f"{path.relative_to(ROOT).as_posix()} --by <you> --answer ...")
    # `expected`, not the disk copy: the two are proven identical above, and
    # resolving `accept` against the RECOMPUTED question keeps the trusted
    # value the one that decides where a file lands.
    questions = expected
    resolved = {}
    for qid, q in questions.items():
        a = given.get(qid)
        if a is None:
            continue
        if not isinstance(a, dict):
            sys.exit(f"triage --apply refused: the answer to {qid} in "
                     f"{path.name} is not an answer object.\n"
                     f"  Answer via: py tools/wiki.py card revise "
                     f"{path.relative_to(ROOT).as_posix()} --by <you> "
                     f"--answer {qid}=accept")
        value = q["proposed"] if a.get("decision") == "accept" else a.get("value")
        if value not in q["options"]:
            sys.exit(f"triage --apply refused: answer '{value}' for {qid} is "
                     f"not one of {q['options']}.\n"
                     f"  Re-answer it: py tools/wiki.py card revise "
                     f"{path.relative_to(ROOT).as_posix()} --by <you> "
                     f"--answer {qid}=<{'|'.join(q['options'])}>")
        resolved[qid] = value

    # Folder answers settle their members; only a 'split' folder makes its
    # member questions mandatory.
    required = set()
    for qid, q in questions.items():
        if q["kind"] == "folder":
            required.add(qid)
    for qid, q in questions.items():
        if q["kind"] != "file":
            continue
        parent = q.get("parent")
        if parent is None or resolved.get(parent) == "split":
            required.add(qid)
    missing = sorted(required - set(resolved))
    if missing:
        shown = "\n".join(f"    {m}  ({questions[m]['item']})" for m in missing[:8])
        more = f"\n    ... and {len(missing) - 8} more" if len(missing) > 8 else ""
        sys.exit(f"triage --apply refused: {len(missing)} unanswered "
                 f"question(s) in {path.name}:\n{shown}{more}\n"
                 f"  Every file gets its own answer -- that is the point.\n"
                 f"  Answer them: py tools/wiki.py card revise "
                 f"{path.relative_to(ROOT).as_posix()} --by <you> "
                 f"--answer <id>=accept ...")
    return resolved


def cmd_triage(args):
    from wiki import agent_commit, arg_after, load_manifest
    prd_version = arg_after(args, "--prd-version") if "--prd-version" in args else None
    if prd_version is not None:
        try:
            int(prd_version)
        except ValueError:
            sys.exit(f"triage: --prd-version must be an integer, got '{prd_version}'")
    manifest = load_manifest()
    plan = collect_plan(ROOT, manifest, prd_version)
    if not plan:
        print("PUT_FILES_HERE/ is empty -- nothing to triage.")
        return

    width = max(len(d["src"].name) for d in plan)
    for d in plan:
        name = d["src"].name.ljust(width)
        if d["action"] == "route":
            replaces_suffix = " (REPLACES existing)" if d.get("replaces") else ""
            print(f"  {name}  ->  {d['dest'].relative_to(ROOT).as_posix()}{replaces_suffix}")
        elif d["action"] == "refuse":
            print(f"  {name}  ->  REFUSED: {d['reason']}")
        else:
            hint = f"  ({d['hint']})" if d.get("hint") else ""
            print(f"  {name}  ->  ASK: {d['proposed']}?{hint}")

    dump = ROOT / "PUT_FILES_HERE"
    card = build_card(plan, dump)
    if card["open_questions"] and "--apply" not in args:
        cpath = write_card(card)
        rel = cpath.relative_to(ROOT).as_posix()
        qs = card["open_questions"]
        print(f"\n{len(qs)} question(s) -> {rel}")
        print("Answer every one, then apply:")
        # The block below is copied verbatim by whoever (or whatever) is
        # driving intake, so it has to PASTE correctly: a trailing backslash
        # on the last --answer line would swallow the apply command into the
        # `card revise` invocation, revise would report success, and the
        # apply would never run.
        print(f"  py tools/wiki.py card revise {rel} --by <you> \\")
        for i, q in enumerate(qs):
            cont = " \\" if i < len(qs) - 1 else ""
            print(f"    --answer {q['id']}=accept{cont}")
        print(f"  py tools/wiki.py triage --apply --card {rel}")
        return

    routed = [d for d in plan if d["action"] == "route"]
    if "--apply" not in args:
        print(f"\n{len(routed)} file(s) would move; nothing was written.")
        print("Re-run with --apply to move them.")
        return

    resolved = {}
    if card["open_questions"]:
        card_arg = arg_after(args, "--card") if "--card" in args else None
        if not card_arg:
            sys.exit(
                f"triage --apply refused: {len(card['open_questions'])} "
                f"file(s) need a human classification and --card was not "
                f"given.\n  Run `py tools/wiki.py triage` to emit a card, "
                f"answer it, then re-run with --card <path>.")
        resolved = read_answers(card_arg, plan, dump)

        resolve_destinations(plan, resolved, card, dump, manifest, ROOT,
                             prd_version)

    moved = apply_plan(plan)
    print(f"\nmoved {moved} file(s).")
    for d in plan:
        rel = d["src"].relative_to(dump).as_posix()
        if d["action"] == "route":
            replaces_suffix = " (REPLACES existing)" if d.get("replaces") else ""
            print(f"  {rel}  ->  "
                  f"{d['dest'].relative_to(ROOT).as_posix()}{replaces_suffix}")
        elif d["action"] == "ignore":
            print(f"  {rel}  ->  left in PUT_FILES_HERE/ (ignored)")
        elif d["action"] == "refuse":
            print(f"  {rel}  ->  REFUSED: {d['reason']}")
        else:
            # Unreachable once resolve_destinations refuses an unanswered
            # decision, but a bare "REFUSED:" with an empty reason is the
            # worst possible thing to print if it ever becomes reachable
            # again: it reads as a handled case and names no fault.
            print(f"  {rel}  ->  NOT CLASSIFIED (still '{d['action']}') -- "
                  f"left in PUT_FILES_HERE/; re-run py tools/wiki.py triage")
    if moved:
        agent_commit(f"triage: routed {moved} file(s) from PUT_FILES_HERE")
        for cmd in sorted({_FOLLOW_UP[d["kind"]] for d in plan
                           if d["action"] == "route" and d.get("kind")}):
            print(f"  next: {cmd}")
