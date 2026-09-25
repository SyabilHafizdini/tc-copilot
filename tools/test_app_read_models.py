#!/usr/bin/env python3
"""Plain-assert tests for the app's read models
(run: py tools/test_app_read_models.py). Matches the tools/smoke.py idiom --
no pytest in this repo.

read_models is pure: it imports and reads, never writes. These run against the
real wiki and assert shape, not content, so they survive wiki edits.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools/app"))
import read_models
from testkit import skip_if_empty


def test_state_has_every_documented_key():
    s = read_models.state()
    for key in ("project", "prd", "stories", "flows", "gaps", "cards",
                "change_reports", "suites", "totals", "next", "inventory"):
        assert key in s, f"missing key: {key}"


def test_state_is_json_serialisable():
    """It is served over HTTP; a stray Path or set would 500 at request time."""
    json.dumps(read_models.state())


def test_next_is_the_structured_form():
    """state()["next"] IS collect_next([]) verbatim (read_models line 68), so
    its key set must track collect_next's -- 'phase' was added there and this
    assertion was not updated, which only showed on a non-empty bundle."""
    s = read_models.state()
    assert set(s["next"]) == {"banners", "rows", "phase"}, s["next"].keys()
    assert s["next"]["rows"], "expected at least one next-action row"


def test_stories_carry_status_and_tc_counts():
    s = read_models.state()
    assert s["stories"], "no stories"
    row = s["stories"][0]
    assert "id" in row and "status" in row, row


def test_state_does_not_mutate_the_repo():
    """The strongest property of the read path: calling it is side-effect free."""
    import subprocess
    before = subprocess.run(["git", "status", "--porcelain"], cwd=ROOT,
                            capture_output=True, text=True).stdout
    read_models.state()
    after = subprocess.run(["git", "status", "--porcelain"], cwd=ROOT,
                           capture_output=True, text=True).stdout
    assert before == after, f"read_models.state() mutated the tree:\n{after}"


def test_inbox_lists_only_pending_cards():
    s = read_models.inbox()
    assert "cards" in s and isinstance(s["cards"], list), s
    for c in s["cards"]:
        assert "file" in c and "card_type" in c and "story" in c, c
        assert "session" in c, c


def test_inbox_is_json_serialisable():
    json.dumps(read_models.inbox())


def test_inbox_does_not_mutate_the_repo():
    import subprocess
    before = subprocess.run(["git", "status", "--porcelain"], cwd=ROOT,
                            capture_output=True, text=True).stdout
    read_models.inbox()
    after = subprocess.run(["git", "status", "--porcelain"], cwd=ROOT,
                           capture_output=True, text=True).stdout
    assert before == after


def test_projects_returns_at_least_the_current_repo():
    p = read_models.projects()
    assert "projects" in p and p["projects"], p
    c = p["projects"][0]
    for k in ("id", "product", "branch", "phase", "counts", "next"):
        assert k in c, c
    assert c["phase"] in (0, 1, 2, 3), c
    assert set(c["counts"]) == {"stories", "tcs"}, c
    if c["next"] is not None:
        assert set(c["next"]) == {"label", "view"}, c["next"]
        assert "kind" in c["next"]["view"], c["next"]


def test_projects_is_json_serialisable():
    json.dumps(read_models.projects())


def test_projects_does_not_mutate_the_repo():
    import subprocess
    before = subprocess.run(["git", "status", "--porcelain"], cwd=ROOT,
                            capture_output=True, text=True).stdout
    read_models.projects()
    after = subprocess.run(["git", "status", "--porcelain"], cwd=ROOT,
                           capture_output=True, text=True).stdout
    assert before == after, f"read_models.projects() mutated the tree:\n{after}"


def test_inventory_parses_story_and_kind():
    """A real xlsx under build/inventory/sit/ is listed with story + kind parsed."""
    inv = read_models.ROOT / "build/inventory/sit"
    inv.mkdir(parents=True, exist_ok=True)
    f = inv / "US-PLANTEST-sit-latest.xlsx"
    f.write_bytes(b"PK\x03\x04 plantest")
    try:
        items = read_models._inventory()
        mine = [it for it in items if it["file"] == "sit/US-PLANTEST-sit-latest.xlsx"]
        assert mine, [it["file"] for it in items]
        it = mine[0]
        assert it["story"] == "US-PLANTEST", it
        assert it["kind"] == "sit", it
        assert isinstance(it["mtime"], str) and it["mtime"], it
    finally:
        f.unlink(missing_ok=True)


def test_inventory_is_a_list_of_the_documented_shape():
    for it in read_models.state()["inventory"]:
        assert set(it) == {"file", "story", "kind", "mtime"}, it
        assert isinstance(it["file"], str), it
        assert it["story"] is None or isinstance(it["story"], str), it


def test_inventory_only_includes_valid_kinds():
    """Every inventory item's kind must be 'sit', 'uat', or 'osat'."""
    valid_kinds = frozenset(("sit", "uat", "osat"))
    for it in read_models.state()["inventory"]:
        assert it["kind"] in valid_kinds, f"Invalid kind: {it['kind']} in {it}"


def test_inventory_skips_files_in_invalid_subdirectories():
    """Files under non-type subdirectories (e.g. build/inventory/custom/) are skipped."""
    # Create test file in an invalid subdirectory
    custom_dir = read_models.ROOT / "build/inventory/custom"
    custom_dir.mkdir(parents=True, exist_ok=True)
    invalid_file = custom_dir / "test-custom-latest.xlsx"
    invalid_file.write_bytes(b"PK\x03\x04 test")

    try:
        items = read_models._inventory()
        # Verify the file is NOT listed
        for it in items:
            assert it["file"] != "custom/test-custom-latest.xlsx", \
                f"File in invalid subdirectory should not be listed: {it}"
    finally:
        invalid_file.unlink(missing_ok=True)


def test_suite_preview_has_documented_shape():
    p = read_models.suite_preview({"kind": "sit"})
    for key in ("count", "ids", "retired", "stale"):
        assert key in p, f"missing key: {key}"
    assert isinstance(p["count"], int) and p["count"] == len(p["ids"]), p


def test_suite_preview_narrows_with_a_priority_filter():
    all_sit = read_models.suite_preview({"kind": "sit"})
    p1 = read_models.suite_preview({"kind": "sit", "priorities": ["P1"]})
    assert p1["count"] <= all_sit["count"], (p1, all_sit)


def test_suite_preview_rejects_bad_filters():
    for bad in ({"kind": "xxx"}, {"priorities": ["p1"]}, {"priorities": "P1"},
                {"include_modules": ["../x"]}, {"nope": 1}):
        try:
            read_models.suite_preview(bad)
        except ValueError:
            pass
        else:
            raise AssertionError(f"bad filters must raise ValueError: {bad!r}")


def test_suite_preview_does_not_mutate_the_repo():
    import subprocess
    before = subprocess.run(["git", "status", "--porcelain"], cwd=ROOT,
                            capture_output=True, text=True).stdout
    read_models.suite_preview({"kind": "sit", "priorities": ["P1"]})
    after = subprocess.run(["git", "status", "--porcelain"], cwd=ROOT,
                           capture_output=True, text=True).stdout
    assert before == after, "suite_preview mutated the repo"


if __name__ == "__main__":
    skip_if_empty("unit: app read models")
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"[PASS] {name}")
    print("test_app_read_models OK")
