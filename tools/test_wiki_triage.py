#!/usr/bin/env python3
"""Plain-assert tests for the triage classifier and command
(run: py tools/test_wiki_triage.py). No pytest -- matches tools/smoke.py.

Every test builds a throwaway root under build/_triage_t/ so nothing here
can touch the real inputs/ tree or dirty the working copy."""
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
from wiki_triage import classify

TMP = ROOT / "build/_triage_t"
# A second location, to prove a card survives the repo moving.
TMP2 = ROOT / "build/_triage_t2"

EMPTY = {"schema_version": 2, "prds": {}}
ONE = {"schema_version": 2, "prds": {
    "rental": {"title": "RENTAL", "adopted_version": 1, "staged_version": None}}}
TWO = {"schema_version": 2, "prds": {
    "rental-application": {"title": "A", "adopted_version": 1, "staged_version": None},
    "rental-payment": {"title": "P", "adopted_version": 2, "staged_version": None}}}


def _root(files=(), existing=()):
    """A fake repo root with a dump holding `files` and inputs/ holding
    `existing` (paths relative to the root)."""
    if TMP.exists():
        shutil.rmtree(TMP)
    (TMP / "PUT_FILES_HERE").mkdir(parents=True)
    for name in files:
        p = TMP / "PUT_FILES_HERE" / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(b"x")
    for rel in existing:
        p = TMP / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(b"x")
    return TMP


def _one(name, manifest=None, files=None, existing=()):
    root = _root(files or [name], existing)
    return classify(root / "PUT_FILES_HERE" / name,
                    manifest or EMPTY, root)


def test_pptx_routes_to_decks():
    d = _one("kickoff.pptx")
    assert d["action"] == "route" and d["kind"] == "deck", d
    assert d["dest"].as_posix().endswith("inputs/decks/kickoff.pptx"), d["dest"]


def test_png_with_a_stable_stem_routes_to_figma():
    d = _one("order-list-screen.png")
    assert d["action"] == "route" and d["kind"] == "figma", d
    assert d["dest"].as_posix().endswith("inputs/figma/order-list-screen.png"), d["dest"]


def test_png_with_a_junk_stem_is_refused():
    d = _one("Screenshot 2026-08-24 143022.png")
    assert d["action"] == "refuse", d
    assert "permanent" in d["reason"], d["reason"]


def test_png_with_spaces_is_refused():
    d = _one("order list screen.png")
    assert d["action"] == "refuse", d


def test_png_with_an_underscored_camera_stem_is_refused():
    d = _one("IMG_20240101_120000.png")
    assert d["action"] == "refuse", d
    assert "permanent" in d["reason"], d["reason"]


def test_collect_plan_covers_every_file_including_nested():
    from wiki_triage import collect_plan
    root = _root(["spec.pdf", "sub/deck.pptx", "notes.txt"])
    plan = collect_plan(root, EMPTY)
    assert len(plan) == 3, plan
    # spec.pdf and notes.txt are both questions now (prd-candidate / reference
    # respectively) -- neither is ever "unknown".
    assert {d["action"] for d in plan} == {"route", "ask"}, plan


def test_collect_plan_ignores_the_readme():
    from wiki_triage import collect_plan
    root = _root(["README.md", "deck.pptx"])
    plan = collect_plan(root, EMPTY)
    assert [d["src"].name for d in plan] == ["deck.pptx"], plan


def test_apply_moves_routed_files_and_leaves_refusals_in_place():
    from wiki_triage import apply_plan, collect_plan
    root = _root(["deck.pptx", "Screenshot 1.png", "notes.txt"])
    plan = collect_plan(root, EMPTY)
    moved = apply_plan(plan)
    assert moved == 1, moved
    assert (root / "inputs/decks/deck.pptx").exists()
    assert (root / "PUT_FILES_HERE/Screenshot 1.png").exists(), "refusal must stay"
    assert (root / "PUT_FILES_HERE/notes.txt").exists(), "ask (reference) must stay"
    assert not (root / "PUT_FILES_HERE/deck.pptx").exists()


def test_collect_plan_alone_moves_nothing():
    from wiki_triage import collect_plan
    root = _root(["spec.pdf"])
    collect_plan(root, EMPTY)
    assert (root / "PUT_FILES_HERE/spec.pdf").exists(), "dry run must not move"
    assert not (root / "inputs").exists(), "dry run must not create inputs/"


def test_png_with_a_legitimate_underscored_stem_still_routes():
    d = _one("order_list_screen.png")
    assert d["action"] == "route", d
    assert d["dest"].as_posix().endswith("inputs/figma/order_list_screen.png"), d["dest"]


def test_png_route_has_replaces_false_when_destination_missing():
    d = _one("stable-name.png")
    assert d["action"] == "route", d
    assert "replaces" in d, d
    assert d["replaces"] is False, d


def test_png_route_has_replaces_true_when_destination_exists():
    d = _one("stable-name.png", existing=["inputs/figma/stable-name.png"])
    assert d["action"] == "route", d
    assert "replaces" in d, d
    assert d["replaces"] is True, d


def test_pptx_route_has_replaces_false_when_destination_missing():
    d = _one("deck.pptx")
    assert d["action"] == "route", d
    assert "replaces" in d, d
    assert d["replaces"] is False, d


def test_pptx_route_has_replaces_true_when_destination_exists():
    d = _one("deck.pptx", existing=["inputs/decks/deck.pptx"])
    assert d["action"] == "route", d
    assert "replaces" in d, d
    assert d["replaces"] is True, d


def test_collect_plan_refuses_colliding_destinations():
    from wiki_triage import collect_plan
    root = _root(["deck.pptx", "sub/deck.pptx"])
    plan = collect_plan(root, EMPTY)
    assert len(plan) == 2, plan
    assert {d["action"] for d in plan} == {"refuse"}, plan
    # Each entry's reason must NAME its competitor specifically -- checking
    # only "both route to" (the literal message prefix, present on every
    # collision regardless of which files are involved) or the collision
    # dest path (which trivially contains "deck.pptx" for both entries too)
    # would pass even if the competing filename were wrong. Pin the actual
    # parenthesized "(<competitor>)" clause instead.
    dump = root / "PUT_FILES_HERE"
    by_src = {d["src"].relative_to(dump).as_posix(): d for d in plan}
    assert "(sub/deck.pptx)" in by_src["deck.pptx"]["reason"], \
        by_src["deck.pptx"]["reason"]
    assert "(deck.pptx)" in by_src["sub/deck.pptx"]["reason"], \
        by_src["sub/deck.pptx"]["reason"]


def test_uppercase_pdf_extension_is_refused_not_silently_moved():
    d = _one("SPEC.PDF")
    assert d["action"] == "refuse", d
    assert "lowercase" in d["reason"], d["reason"]
    assert d["dest"] is None, d


def test_uppercase_png_extension_is_refused_not_silently_moved():
    d = _one("PAGE.PNG")
    assert d["action"] == "refuse", d
    assert "lowercase" in d["reason"], d["reason"]


def test_mixed_case_pptx_extension_is_refused():
    d = _one("kickoff.PPTX")
    assert d["action"] == "refuse", d
    assert "lowercase" in d["reason"], d["reason"]


def test_lowercase_extension_still_routes_normally():
    # The case check must not false-positive on the common (lowercase) case.
    d = _one("kickoff.pptx")
    assert d["action"] == "route", d


def test_png_figma_default_frame_name_without_space_is_refused():
    # Frame12.png has no space, so the old space-only check missed it -- it
    # would have routed straight to the permanent id figma#Frame12.
    d = _one("Frame12.png")
    assert d["action"] == "refuse", d
    assert "permanent" in d["reason"], d["reason"]


def test_png_figma_default_names_are_refused():
    for name in ("Frame 12.png", "Group3.png", "Rectangle 5.png",
                 "Ellipse7.png", "Component 1.png", "Vector2.png",
                 "Slice 4.png"):
        d = _one(name)
        assert d["action"] == "refuse", (name, d)
        assert "permanent" in d["reason"], (name, d["reason"])


def test_png_name_merely_containing_frame_word_still_routes():
    # Must not over-match: a real page name that happens to start with one
    # of the Figma default words but continues with letters is legitimate.
    d = _one("frameworks-overview.png")
    assert d["action"] == "route", d


def test_triage_cli_rejects_non_integer_prd_version_cleanly():
    import subprocess
    r = subprocess.run(
        [sys.executable, str(ROOT / "tools" / "wiki.py"), "triage",
         "--prd-version", "abc"],
        cwd=ROOT, capture_output=True, text=True)
    assert r.returncode != 0, (r.returncode, r.stdout, r.stderr)
    assert "Traceback" not in r.stderr, r.stderr
    assert "ValueError" not in r.stderr, r.stderr
    assert "--prd-version" in r.stdout or "--prd-version" in r.stderr


def test_docx_becomes_a_question_not_an_auto_route():
    d = _one("spec.docx")
    assert d["action"] == "ask", d
    assert d["kind"] == "prd-candidate", d
    assert d["proposed"] == "prd", d
    assert set(d["options"]) == {"prd", "reference", "ignore"}, d


def test_pdf_is_a_question_proposing_prd_when_nothing_is_adopted():
    d = _one("requirements.pdf")
    assert d["action"] == "ask", d
    assert d["proposed"] == "prd", d


def test_pdf_proposes_reference_once_a_prd_version_is_adopted():
    d = _one("annex.pdf", manifest=ONE)
    assert d["action"] == "ask", d
    assert d["proposed"] == "reference", d


def test_yml_is_a_reference_question_never_unknown():
    d = _one("param-control-rules.yml")
    assert d["action"] == "ask", d
    assert d["kind"] == "reference", d
    assert d["proposed"] == "reference", d
    assert "prd" not in d["options"], d


def test_xlsx_is_a_reference_question():
    d = _one("test cases 0.2.xlsx")
    assert d["action"] == "ask", d
    assert d["proposed"] == "reference", d


def test_jpg_is_reference_with_a_png_conversion_hint():
    d = _one("order-list.jpg")
    assert d["action"] == "ask", d
    assert d["proposed"] == "reference", d
    assert ".png" in d["hint"], d


def test_png_still_routes_to_figma_untouched():
    d = _one("order-list-screen.png")
    assert d["action"] == "route", d
    assert d["dest"].as_posix().endswith("inputs/figma/order-list-screen.png"), d


def test_pptx_still_routes_to_decks_untouched():
    d = _one("kickoff.pptx")
    assert d["action"] == "route", d
    assert d["dest"].as_posix().endswith("inputs/decks/kickoff.pptx"), d


def test_no_classification_is_ever_unknown():
    for name in ("a.yml", "b.xlsx", "c.docx", "d.pdf", "e.png", "f.pptx",
                 "g.weirdext", "h.doc", "i.ppt"):
        d = _one(name)
        assert d["action"] in ("route", "ask", "refuse"), (name, d)


def test_card_asks_one_question_per_directory_that_holds_files():
    from wiki_triage import build_card, collect_plan
    root = _root(["top.xlsx",
                  "L/L/control-config.yml",
                  "L/L/control/a-rules.yml", "L/L/control/b-rules.yml",
                  "L/L/data/c-rules.yml"])
    plan = collect_plan(root, EMPTY)
    card = build_card(plan, root / "PUT_FILES_HERE")
    folders = {q["item"] for q in card["open_questions"] if q["kind"] == "folder"}
    assert folders == {"L/L", "L/L/control", "L/L/data"}, folders


def test_folder_question_members_match_its_direct_files_only():
    from wiki_triage import build_card, collect_plan
    root = _root(["L/L/control-config.yml",
                  "L/L/control/a-rules.yml", "L/L/control/b-rules.yml"])
    plan = collect_plan(root, EMPTY)
    card = build_card(plan, root / "PUT_FILES_HERE")
    q = [q for q in card["open_questions"]
         if q["kind"] == "folder" and q["item"] == "L/L"][0]
    assert q["members"] == 1, q
    kids = [x for x in card["open_questions"] if x.get("parent") == q["id"]]
    assert len(kids) == 1, kids
    assert kids[0]["item"] == "L/L/control-config.yml", kids


def test_top_level_files_get_file_questions_and_no_root_folder_question():
    from wiki_triage import build_card, collect_plan
    root = _root(["a.xlsx", "b.docx"])
    plan = collect_plan(root, EMPTY)
    card = build_card(plan, root / "PUT_FILES_HERE")
    assert not [q for q in card["open_questions"] if q["kind"] == "folder"]
    assert len(card["open_questions"]) == 2, card["open_questions"]
    assert all("parent" not in q for q in card["open_questions"])


def test_folder_question_offers_split_and_file_questions_do_not():
    from wiki_triage import build_card, collect_plan
    root = _root(["L/a-rules.yml", "L/b-rules.yml"])
    plan = collect_plan(root, EMPTY)
    card = build_card(plan, root / "PUT_FILES_HERE")
    folder = [q for q in card["open_questions"] if q["kind"] == "folder"][0]
    member = [q for q in card["open_questions"] if q["kind"] == "file"][0]
    assert "split" in folder["options"], folder
    assert "split" not in member["options"], member


def test_card_scope_and_plan_hash_are_present():
    from wiki_triage import build_card, collect_plan, plan_hash
    root = _root(["a.yml"])
    plan = collect_plan(root, EMPTY)
    card = build_card(plan, root / "PUT_FILES_HERE")
    assert card["scope"] == "triage", card
    assert card["plan_hash"] == plan_hash(plan, root / "PUT_FILES_HERE"), card


def test_plan_hash_changes_when_a_file_is_added():
    from wiki_triage import collect_plan, plan_hash
    m = EMPTY
    h1 = plan_hash(collect_plan(_root(["a.yml"]), m), TMP / "PUT_FILES_HERE")
    h2 = plan_hash(collect_plan(_root(["a.yml", "b.yml"]), m),
                   TMP / "PUT_FILES_HERE")
    assert h1 != h2


def test_routed_and_refused_files_are_not_questions():
    from wiki_triage import build_card, collect_plan
    root = _root(["order-list-screen.png", "Screenshot 2026-08-24.png", "a.yml"])
    plan = collect_plan(root, EMPTY)
    card = build_card(plan, root / "PUT_FILES_HERE")
    items = {q["item"] for q in card["open_questions"]}
    assert items == {"a.yml"}, items


def test_a_mixed_folder_proposes_reference_not_prd():
    from wiki_triage import build_card, collect_plan
    root = _root(["L/spec.docx", "L/a-rules.yml"])
    plan = collect_plan(root, EMPTY)
    card = build_card(plan, root / "PUT_FILES_HERE")
    folder = [q for q in card["open_questions"] if q["kind"] == "folder"][0]
    assert folder["proposed"] == "reference", folder


def test_plan_hash_changes_when_the_proposal_changes():
    from wiki_triage import collect_plan, plan_hash
    dump = TMP / "PUT_FILES_HERE"
    h1 = plan_hash(collect_plan(_root(["spec.pdf"]),
                                EMPTY), dump)
    h2 = plan_hash(collect_plan(_root(["spec.pdf"]),
                                ONE), dump)
    assert h1 != h2


def _answered_card(root, answers, plan_hash_override=None):
    """Emit a card for root's dump and stamp human answers into it."""
    import json
    from wiki_triage import build_card, collect_plan
    dump = root / "PUT_FILES_HERE"
    plan = collect_plan(root, EMPTY)
    card = build_card(plan, dump)
    if plan_hash_override:
        card["plan_hash"] = plan_hash_override
    card["human_response"] = {
        "answer": "revise", "by": "tester", "at": "2026-08-25T00:00:00+08:00",
        "answers": {qid: ({"decision": "accept", "value": None} if v == "accept"
                          else {"decision": "correct", "value": v})
                    for qid, v in answers.items()}}
    cpath = root / "card.json"
    cpath.write_text(json.dumps(card, indent=1), encoding="utf-8", newline="\n")
    return cpath, card


def _apply(root, card_path=None, *extra):
    """Run the real CLI's triage --apply against a fake root."""
    import os
    import subprocess
    argv = [sys.executable, str(ROOT / "tools" / "wiki.py"), "triage",
            "--apply", "--no-commit", *extra]
    if card_path:
        argv += ["--card", str(card_path)]
    env = dict(os.environ, TC_ROOT_OVERRIDE=str(root))
    return subprocess.run(argv, cwd=ROOT, capture_output=True, text=True, env=env)


def test_apply_without_a_card_is_refused():
    root = _root(["a.yml"])
    r = _apply(root)
    assert r.returncode != 0, r.stdout + r.stderr
    assert "--card" in (r.stdout + r.stderr)


def test_apply_with_a_stale_plan_hash_is_refused():
    root = _root(["a.yml"])
    cpath, card = _answered_card(root, {q["id"]: "accept"
                                        for q in _questions(root)},
                                 plan_hash_override="sha256:deadbeef")
    r = _apply(root, cpath)
    assert r.returncode != 0, r.stdout + r.stderr
    assert "plan_hash" in (r.stdout + r.stderr) or "re-run" in (r.stdout + r.stderr)


def test_apply_with_one_unanswered_question_is_refused():
    root = _root(["a.yml", "b.yml"])
    qs = _questions(root)
    partial = {qs[0]["id"]: "accept"}
    cpath, _ = _answered_card(root, partial)
    r = _apply(root, cpath)
    assert r.returncode != 0, r.stdout + r.stderr
    assert "unanswered" in (r.stdout + r.stderr).lower()


def test_apply_with_an_out_of_set_answer_is_refused():
    root = _root(["a.yml"])
    qs = _questions(root)
    cpath, _ = _answered_card(root, {q["id"]: "banana" for q in qs})
    r = _apply(root, cpath)
    assert r.returncode != 0, r.stdout + r.stderr
    assert "banana" in (r.stdout + r.stderr)


def test_apply_with_an_unanswered_card_is_refused():
    import json
    root = _root(["a.yml"])
    from wiki_triage import build_card, collect_plan
    plan = collect_plan(root, EMPTY)
    card = build_card(plan, root / "PUT_FILES_HERE")
    cpath = root / "card.json"
    cpath.write_text(json.dumps(card, indent=1), encoding="utf-8", newline="\n")
    r = _apply(root, cpath)
    assert r.returncode != 0, r.stdout + r.stderr
    assert "human_response" in (r.stdout + r.stderr) or "not answered" in (r.stdout + r.stderr).lower()


def _questions(root):
    from wiki_triage import build_card, collect_plan
    plan = collect_plan(root, EMPTY)
    return build_card(plan, root / "PUT_FILES_HERE")["open_questions"]


def test_folder_accept_settles_every_member_to_reference():
    from wiki_triage import (build_card, collect_plan, resolve_destinations)
    root = _root(["L/a-rules.yml", "L/b-rules.yml"])
    dump = root / "PUT_FILES_HERE"
    plan = collect_plan(root, EMPTY)
    card = build_card(plan, dump)
    resolved = {q["id"]: q["proposed"] for q in card["open_questions"]
                if q["kind"] == "folder"}
    resolve_destinations(plan, resolved, card, dump,
                         EMPTY, root, None)
    for d in plan:
        assert d["action"] == "route", d
        assert "inputs/reference/L/" in d["dest"].as_posix(), d


def test_split_folder_uses_each_member_answer():
    from wiki_triage import (build_card, collect_plan, resolve_destinations)
    root = _root(["L/a-rules.yml", "L/keep.yml"])
    dump = root / "PUT_FILES_HERE"
    plan = collect_plan(root, EMPTY)
    card = build_card(plan, dump)
    folder = [q for q in card["open_questions"] if q["kind"] == "folder"][0]
    resolved = {folder["id"]: "split"}
    for q in card["open_questions"]:
        if q["kind"] == "file":
            resolved[q["id"]] = "ignore" if q["item"].endswith("keep.yml") else "reference"
    resolve_destinations(plan, resolved, card, dump,
                         EMPTY, root, None)
    by_name = {d["src"].name: d for d in plan}
    assert by_name["a-rules.yml"]["action"] == "route", by_name
    assert by_name["keep.yml"]["action"] == "ignore", by_name


def _prd_plan(root, manifest):
    """A plan whose every question is answered 'prd'."""
    from wiki_triage import build_card, collect_plan
    dump = root / "PUT_FILES_HERE"
    plan = collect_plan(root, manifest)
    card = build_card(plan, dump)
    resolved = {q["id"]: "prd" for q in card["open_questions"]}
    return plan, resolved, card, dump


def _refusal(manifest, root, *answers):
    """The SystemExit text of resolve_destinations, or None if it routed."""
    from wiki_triage import resolve_destinations
    plan, resolved, card, dump = _prd_plan(root, manifest)
    try:
        resolve_destinations(plan, resolved, card, dump, manifest, root, *answers)
    except SystemExit as e:
        return str(e)
    return None


def test_a_prd_answer_routes_under_the_named_prd_and_version():
    from wiki_triage import resolve_destinations
    root = _root(["spec.docx"])
    plan, resolved, card, dump = _prd_plan(root, EMPTY)
    resolve_destinations(plan, resolved, card, dump, EMPTY, root,
                         1, "rental-fees", "Rental fees")
    assert plan[0]["dest"].as_posix().endswith(
        "inputs/prd/rental-fees/v1/spec.docx"), plan[0]
    assert plan[0]["kind"] == "prd" and plan[0]["prd"] == "rental-fees", plan[0]


def test_a_prd_answer_into_an_occupied_version_is_refused():
    root = _root(["spec.docx"], existing=["inputs/prd/rental/v2/old.pdf"])
    msg = _refusal(ONE, root, 2)
    assert msg and "old.pdf" in msg and "inputs/prd/rental/v2/" in msg, msg
    # the tool and the tc-intake protocol say the same thing: the next free
    # version, or the human moves the old document; nothing is ever deleted
    assert "next free version is v3" in msg and "--prd-version 3" in msg, msg
    assert "move the old document out yourself" in msg, msg
    assert "remove the existing" not in msg, msg
    assert (root / "inputs/prd/rental/v2/old.pdf").exists()
    assert (root / "PUT_FILES_HERE/spec.docx").exists(), "a refusal moves nothing"


def test_the_next_free_version_skips_an_occupied_one():
    root = _root(["spec.docx"], existing=["inputs/prd/rental/v2/old.pdf",
                                          "inputs/prd/rental/v3/older.md",
                                          "inputs/prd/rental/v4/.gitkeep"])
    msg = _refusal(ONE, root, 2)
    assert msg and "next free version is v4" in msg, msg


def test_a_reserved_or_version_shaped_prd_id_is_refused():
    root = _root(["spec.docx"])
    for bad, why in (("v2", "collides with the version directory names"),
                     ("index", "reserved name"), ("log", "reserved name")):
        msg = _refusal(EMPTY, root, 1, bad, "T")
        assert msg and why in msg, (bad, msg)
    assert not (root / "inputs").exists()


def test_a_prd_title_without_a_prd_is_refused():
    """A title names a NEW PRD. Without --prd it used to be dropped and the
    file went to the single registered PRD."""
    root = _root(["spec.docx"])
    qs = _questions(root)
    cpath, _ = _answered_card(root, {qs[0]["id"]: "prd"})
    r = _apply(root, cpath, "--prd-title", "Rental fees", "--prd-version", "1")
    out = r.stdout + r.stderr
    assert r.returncode != 0 and "Traceback" not in out, out
    assert "--prd-title was given without --prd" in out, out
    assert (root / "PUT_FILES_HERE/spec.docx").exists(), "a refusal moves nothing"
    assert not (root / "inputs").exists()


def test_two_files_answered_prd_for_one_version_are_refused():
    root = _root(["a.docx", "b.pdf"])
    msg = _refusal(ONE, root, 2)
    assert msg and "one document per version" in msg, msg


def test_a_prd_file_with_no_prd_answer_is_refused_when_two_are_registered():
    root = _root(["spec.docx"])
    msg = _refusal(TWO, root, 3)
    assert msg and "rental-application" in msg and "rental-payment" in msg, msg
    assert "--prd <id>" in msg and "never guesses" in msg, msg
    assert not (root / "inputs").exists(), "a refusal moves nothing"
    assert (root / "PUT_FILES_HERE/spec.docx").exists()


def test_one_registered_prd_is_the_default_prd_answer():
    from wiki_triage import resolve_destinations
    root = _root(["spec.docx"])
    plan, resolved, card, dump = _prd_plan(root, ONE)
    resolve_destinations(plan, resolved, card, dump, ONE, root, 2)
    assert plan[0]["dest"].as_posix().endswith("inputs/prd/rental/v2/spec.docx"), plan[0]
    assert plan[0]["prd"] == "rental", plan[0]


def test_no_prd_registered_and_none_named_is_refused():
    root = _root(["spec.docx"])
    msg = _refusal(EMPTY, root, 1)
    assert msg and "--prd <id>" in msg and "--prd-title" in msg, msg


def test_a_new_prd_id_without_a_title_is_refused():
    root = _root(["spec.docx"])
    msg = _refusal(ONE, root, 1, "rental-fees")
    assert msg and "rental-fees" in msg and "--prd-title" in msg, msg
    assert "Registered: rental" in msg, msg


def test_a_malformed_prd_id_is_refused():
    root = _root(["spec.docx"])
    msg = _refusal(EMPTY, root, 1, "Rental Fees", "Rental fees")
    assert msg and "lowercase-hyphen" in msg, msg
    for bad in ("../x", "a/b", "a\\b", "..", "x"):
        msg = _refusal(EMPTY, root, 1, bad, "T")
        assert msg and "lowercase-hyphen" in msg, (bad, msg)
    assert not (root / "inputs").exists()


def test_a_prd_answer_without_a_version_is_refused_and_names_the_next_one():
    root = _root(["spec.docx"])
    msg = _refusal(ONE, root)
    assert msg and "--prd-version 2" in msg, msg
    assert "rental" in msg and "adopted v1" in msg, msg
    msg = _refusal(EMPTY, root, None, "rental-fees", "Rental fees")
    assert msg and "--prd-version 1" in msg, msg


def test_a_version_ingest_prd_would_not_accept_is_refused():
    root = _root(["spec.docx"])
    for bad in (0, -1, "01", "x"):
        msg = _refusal(ONE, root, bad)
        assert msg and "whole number from 1" in msg, (bad, msg)
    msg = _refusal(TWO, root, 1, "rental-payment")
    assert msg and "already adopted" in msg and "--prd-version 3" in msg, msg
    assert not (root / "inputs").exists()


def test_apply_routes_a_prd_and_prints_the_ingest_command_for_it():
    root = _root(["spec.docx"])
    qs = _questions(root)
    cpath, _ = _answered_card(root, {qs[0]["id"]: "prd"})
    r = _apply(root, cpath, "--prd", "rental-fees", "--prd-title", "Rental fees",
               "--prd-version", "1")
    out = r.stdout + r.stderr
    assert r.returncode == 0, out
    assert (root / "inputs/prd/rental-fees/v1/spec.docx").exists(), out
    assert not (root / "PUT_FILES_HERE/spec.docx").exists(), out
    assert 'next: py tools/wiki.py ingest-prd --prd rental-fees --title "Rental fees"' in out, out


def test_apply_refusal_for_a_missing_answer_leaves_the_file_in_the_dump():
    root = _root(["spec.docx"])
    qs = _questions(root)
    cpath, _ = _answered_card(root, {qs[0]["id"]: "prd"})
    r = _apply(root, cpath)
    out = r.stdout + r.stderr
    assert r.returncode != 0 and "--prd <id>" in out, out
    assert (root / "PUT_FILES_HERE/spec.docx").exists(), out
    assert not (root / "inputs").exists(), out


def test_reference_preserves_the_dumped_subfolder_structure():
    from wiki_triage import (build_card, collect_plan, resolve_destinations)
    root = _root(["L/L/control/a-rules.yml"])
    dump = root / "PUT_FILES_HERE"
    plan = collect_plan(root, EMPTY)
    card = build_card(plan, dump)
    resolved = {q["id"]: "reference" for q in card["open_questions"]}
    resolve_destinations(plan, resolved, card, dump,
                         EMPTY, root, None)
    assert plan[0]["dest"].as_posix().endswith(
        "inputs/reference/L/L/control/a-rules.yml"), plan[0]


# ---------------------------------------------------------------- card gate
# The card is the ONLY gate: no prose in SKILL.md is load-bearing, so a
# tampered card must be caught here or the whole feature is decorative.


def _raw_card(root, mutate):
    """Emit the real card for root's dump, let `mutate` tamper with it (and
    return the answers to stamp), then write it. -> card path."""
    import json
    from wiki_triage import build_card, collect_plan
    dump = root / "PUT_FILES_HERE"
    plan = collect_plan(root, EMPTY)
    card = build_card(plan, dump)
    answers = mutate(card) or {}
    card["human_response"] = {
        "answer": "revise", "by": "tester", "at": "2026-08-25T00:00:00+08:00",
        "answers": answers}
    cpath = root / "card.json"
    cpath.write_text(json.dumps(card, indent=1), encoding="utf-8", newline="\n")
    return cpath


def test_apply_refuses_a_card_whose_open_questions_were_emptied():
    # The bypass: keep the matching plan_hash, delete every question, answer
    # nothing. Without a structural re-check the gate has nothing to require.
    root = _root(["spec.docx", "a.yml"])

    def _empty(card):
        card["open_questions"] = []
        return {}

    r = _apply(root, _raw_card(root, _empty))
    out = r.stdout + r.stderr
    assert r.returncode != 0, out
    assert (root / "PUT_FILES_HERE/spec.docx").exists(), out
    assert (root / "PUT_FILES_HERE/a.yml").exists(), out
    assert not (root / "inputs").exists(), sorted(root.rglob("*"))


def test_apply_refuses_a_card_with_a_tampered_proposal():
    # A .yml can never be a PRD. Rewriting its proposed/options on disk and
    # answering `accept` would route it into inputs/prd/vN.
    root = _root(["a.yml"])

    def _tamper(card):
        q = card["open_questions"][0]
        q["proposed"] = "prd"
        q["options"] = ["prd", "reference", "ignore"]
        return {q["id"]: {"decision": "accept", "value": None}}

    r = _apply(root, _raw_card(root, _tamper))
    out = r.stdout + r.stderr
    assert r.returncode != 0, out
    assert not (root / "inputs/prd").exists(), sorted(root.rglob("*"))
    assert (root / "PUT_FILES_HERE/a.yml").exists(), out


def test_apply_refuses_a_card_with_a_widened_option_set():
    root = _root(["a.yml"])

    def _widen(card):
        q = card["open_questions"][0]
        q["options"] = ["prd", "reference", "ignore"]
        return {q["id"]: {"decision": "correct", "value": "prd"}}

    r = _apply(root, _raw_card(root, _widen))
    out = r.stdout + r.stderr
    assert r.returncode != 0, out
    assert not (root / "inputs/prd").exists(), sorted(root.rglob("*"))


def test_apply_refuses_a_card_with_an_invented_question():
    root = _root(["a.yml"])

    def _invent(card):
        extra = {"id": "q-file-made-up", "kind": "file", "item": "made-up.yml",
                 "proposed": "reference", "options": ["reference", "ignore"]}
        card["open_questions"].append(extra)
        return {q["id"]: {"decision": "accept", "value": None}
                for q in card["open_questions"]}

    r = _apply(root, _raw_card(root, _invent))
    out = r.stdout + r.stderr
    assert r.returncode != 0, out


def test_apply_refuses_a_card_whose_question_lost_its_proposed_key():
    root = _root(["a.yml"])

    def _drop(card):
        q = card["open_questions"][0]
        qid = q["id"]
        del q["proposed"]
        return {qid: {"decision": "accept", "value": None}}

    r = _apply(root, _raw_card(root, _drop))
    out = r.stdout + r.stderr
    assert r.returncode != 0, out
    assert "Traceback" not in r.stderr, r.stderr
    assert "KeyError" not in out, out
    assert "proposed" in out, out


def test_resolve_destinations_exits_when_a_member_answer_is_missing():
    from wiki_triage import build_card, collect_plan, resolve_destinations
    root = _root(["L/a-rules.yml"])
    dump = root / "PUT_FILES_HERE"
    plan = collect_plan(root, EMPTY)
    card = build_card(plan, dump)
    folder = [q for q in card["open_questions"] if q["kind"] == "folder"][0]
    resolved = {folder["id"]: "split"}      # member deliberately unanswered
    try:
        resolve_destinations(plan, resolved, card, dump,
                             EMPTY, root, None)
    except SystemExit as e:
        assert "a-rules.yml" in str(e), str(e)
    else:
        assert False, "expected SystemExit for an unanswered member"
    assert plan[0]["dest"] is None, plan[0]


def test_card_not_found_refusal_names_the_fix():
    root = _root(["a.yml"])
    r = _apply(root, root / "no-such-card.json")
    out = r.stdout + r.stderr
    assert r.returncode != 0, out
    assert "no-such-card.json" in out, out
    assert "py tools/wiki.py triage" in out, out


def test_invalid_json_card_refusal_names_the_fix():
    root = _root(["a.yml"])
    cpath = root / "card.json"
    cpath.write_text("{not json", encoding="utf-8", newline="\n")
    r = _apply(root, cpath)
    out = r.stdout + r.stderr
    assert r.returncode != 0, out
    assert "py tools/wiki.py triage" in out, out


def test_wrong_scope_card_refusal_names_the_fix():
    import json
    root = _root(["a.yml"])
    cpath = root / "card.json"
    cpath.write_text(json.dumps({"scope": "alignment", "open_questions": []}),
                     encoding="utf-8", newline="\n")
    r = _apply(root, cpath)
    out = r.stdout + r.stderr
    assert r.returncode != 0, out
    assert "alignment" in out, out
    assert "py tools/wiki.py triage" in out, out


def test_plan_hash_is_independent_of_where_the_repo_lives():
    """A card must survive a clone or a move. Absolute paths in the
    fingerprint would invalidate every emitted card the moment the repo
    changes location, even though the dump is byte-identical."""
    import shutil as _sh
    from wiki_triage import collect_plan, plan_hash
    m = EMPTY
    root_a = _root(["L/a.yml", "b.docx"])
    h1 = plan_hash(collect_plan(root_a, m), root_a / "PUT_FILES_HERE")
    if TMP2.exists():
        _sh.rmtree(TMP2)
    _sh.copytree(root_a, TMP2)
    h2 = plan_hash(collect_plan(TMP2, m), TMP2 / "PUT_FILES_HERE")
    assert h1 == h2, (h1, h2)


# ------------------------------------------------------- question id identity


def test_question_ids_are_unique_for_paths_differing_only_by_punctuation():
    # 'a rules.yml' and 'a-rules.yml' both collapse to the same readable slug.
    # One shared id means the card carries two questions under it, both dict
    # lookups dedupe, and one legitimate file becomes unanswerable.
    from wiki_triage import build_card, collect_plan
    root = _root(["L/a rules.yml", "L/a-rules.yml"])
    plan = collect_plan(root, EMPTY)
    card = build_card(plan, root / "PUT_FILES_HERE")
    files = [q for q in card["open_questions"] if q["kind"] == "file"]
    assert len(files) == 2, files
    ids = [q["id"] for q in card["open_questions"]]
    assert len(ids) == len(set(ids)), ids


def test_question_ids_stay_readable_and_stable():
    from wiki_triage import question_id
    a = question_id("file", "L/L/control/event-control-rules.yml")
    assert a.startswith("q-file-L-L-control-event-control-rules-yml-"), a
    assert a == question_id("file", "L/L/control/event-control-rules.yml"), a
    assert question_id("folder", "L/L") != question_id("file", "L/L")


def test_two_paths_differing_only_by_punctuation_are_answered_independently():
    from wiki_triage import build_card, collect_plan, resolve_destinations
    root = _root(["L/a rules.yml", "L/a-rules.yml"])
    dump = root / "PUT_FILES_HERE"
    plan = collect_plan(root, EMPTY)
    card = build_card(plan, dump)
    folder = [q for q in card["open_questions"] if q["kind"] == "folder"][0]
    resolved = {folder["id"]: "split"}
    for q in card["open_questions"]:
        if q["kind"] == "file":
            resolved[q["id"]] = ("ignore" if q["item"].endswith("a rules.yml")
                                 else "reference")
    resolve_destinations(plan, resolved, card, dump,
                         EMPTY, root, None)
    by_name = {d["src"].name: d for d in plan}
    assert by_name["a rules.yml"]["action"] == "ignore", by_name
    assert by_name["a-rules.yml"]["action"] == "route", by_name


# ------------------------------------------------------- reference clobbering


def test_a_reference_route_over_an_existing_file_is_marked_replaces():
    from wiki_triage import build_card, collect_plan, resolve_destinations
    root = _root(["L/a-rules.yml"], existing=["inputs/reference/L/a-rules.yml"])
    dump = root / "PUT_FILES_HERE"
    plan = collect_plan(root, EMPTY)
    card = build_card(plan, dump)
    resolved = {q["id"]: "reference" for q in card["open_questions"]}
    resolve_destinations(plan, resolved, card, dump,
                         EMPTY, root, None)
    assert plan[0].get("replaces") is True, plan[0]


def test_a_fresh_reference_route_is_not_marked_replaces():
    from wiki_triage import build_card, collect_plan, resolve_destinations
    root = _root(["L/a-rules.yml"])
    dump = root / "PUT_FILES_HERE"
    plan = collect_plan(root, EMPTY)
    card = build_card(plan, dump)
    resolved = {q["id"]: "reference" for q in card["open_questions"]}
    resolve_destinations(plan, resolved, card, dump,
                         EMPTY, root, None)
    assert plan[0].get("replaces") is False, plan[0]


def test_apply_reports_a_clobbering_reference_route_as_replaces():
    root = _root(["a.yml"], existing=["inputs/reference/a.yml"])
    qs = _questions(root)
    cpath, _ = _answered_card(root, {q["id"]: "accept" for q in qs})
    r = _apply(root, cpath)
    out = r.stdout + r.stderr
    assert r.returncode == 0, out
    assert "REPLACES existing" in out, out


# ------------------------------------------------------- the pasteable block


def _triage(root):
    """Run the real CLI's triage (no --apply) against a fake root."""
    import os
    import subprocess
    env = dict(os.environ, TC_ROOT_OVERRIDE=str(root))
    return subprocess.run(
        [sys.executable, str(ROOT / "tools" / "wiki.py"), "triage",
         "--no-commit"], cwd=ROOT, capture_output=True, text=True, env=env)


def test_the_emitted_answer_block_pastes_as_two_separate_commands():
    # A trailing backslash on the LAST --answer line joins the apply command
    # onto `card revise`: revise reports success and the apply never runs.
    root = _root(["a.yml", "b.yml"])
    r = _triage(root)
    assert r.returncode == 0, r.stdout + r.stderr
    lines = [ln.rstrip() for ln in r.stdout.splitlines()]
    answer_lines = [i for i, ln in enumerate(lines) if "--answer" in ln]
    assert answer_lines, r.stdout
    last = answer_lines[-1]
    assert not lines[last].endswith("\\"), lines[last]
    assert "triage --apply --card" in lines[last + 1], lines[last:last + 2]
    # every earlier line of the revise command must still continue
    for i in answer_lines[:-1]:
        assert lines[i].endswith("\\"), lines[i]


# ------------------------------------------------------- spec coverage: gate


def test_apply_refuses_when_a_split_folder_has_an_unanswered_member():
    root = _root(["L/a-rules.yml", "L/b-rules.yml"])
    qs = _questions(root)
    folder = [q for q in qs if q["kind"] == "folder"][0]
    members = sorted([q for q in qs if q.get("parent") == folder["id"]],
                     key=lambda q: q["item"])
    assert len(members) == 2, members
    answers = {folder["id"]: "split", members[0]["id"]: "reference"}
    cpath, _ = _answered_card(root, answers)
    r = _apply(root, cpath)
    out = r.stdout + r.stderr
    assert r.returncode != 0, out
    assert "unanswered" in out.lower(), out
    assert members[1]["id"] in out, out
    assert (root / "PUT_FILES_HERE/L/b-rules.yml").exists(), out
    assert not (root / "inputs").exists(), sorted(root.rglob("*"))


def test_an_accepted_card_moves_files_and_reports_every_file_by_name():
    root = _root(["top.xlsx", "notes.docx", "kickoff.pptx",
                  "order-list-screen.png",
                  "L/L/control/a-rules.yml", "L/L/control/b-rules.yml",
                  "L/L/data/c-rules.yml"])
    qs = _questions(root)
    # notes.docx proposes prd (nothing adopted); the human corrects it, the
    # way an interface spec that states no acceptance criteria is corrected.
    answers = {q["id"]: ("reference" if q["item"].endswith("notes.docx")
                         else "accept") for q in qs}
    cpath, _ = _answered_card(root, answers)
    r = _apply(root, cpath)
    out = r.stdout + r.stderr
    assert r.returncode == 0, out
    assert "moved 7 file(s)" in out, out
    for rel in ("top.xlsx", "notes.docx", "kickoff.pptx",
                "order-list-screen.png", "L/L/control/a-rules.yml",
                "L/L/control/b-rules.yml", "L/L/data/c-rules.yml"):
        assert rel in out, (rel, out)
    assert (root / "inputs/reference/notes.docx").exists(), out
    assert (root / "inputs/reference/L/L/control/a-rules.yml").exists(), out
    assert (root / "inputs/decks/kickoff.pptx").exists(), out
    assert (root / "inputs/figma/order-list-screen.png").exists(), out
    assert not (root / "inputs/prd").exists(), sorted(root.rglob("*"))
    assert not list((root / "PUT_FILES_HERE").rglob("*.yml")), out


def test_apply_leaves_ignored_files_in_the_dump():
    from wiki_triage import apply_plan
    root = _root(["a.yml"])
    plan = [{"src": root / "PUT_FILES_HERE/a.yml", "action": "ignore",
             "dest": None, "kind": "reference"}]
    assert apply_plan(plan) == 0
    assert (root / "PUT_FILES_HERE/a.yml").exists()


if __name__ == "__main__":
    try:
        for name, fn in sorted(globals().items()):
            if name.startswith("test_") and callable(fn):
                fn()
                print(f"[PASS] {name}")
        print("test_wiki_triage OK")
    finally:
        for _d in (TMP, TMP2):
            if _d.exists():
                shutil.rmtree(_d)
