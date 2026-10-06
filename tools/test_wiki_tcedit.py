#!/usr/bin/env python3
"""Plain-assert tests for the `tc edit` resolver and spec rewriter
(run: py tools/test_wiki_tcedit.py). No git, no render: pure functions over
text. The command itself is proven in tools/test_wiki_tcedit_e2e.py."""
import sys
import tempfile
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import render_sit
import render_uat
import wiki_tcedit as t

SIT = """story: /stories/US-X.md
scenario_id: SC-X-{ac}-{seq:02d}
ac_prefix: '1.1'
states:
  home: "Home page, not logged in."
test_cases:
- ac: HS-01
  seq: 1
  priority: P1
  title: Log in
  objective: 'Verify: the user can log in.'
  steps: |-
    1. Open the page.
    2. Click **Login**.
  expected: 1. The page opens.
  data: |-
    **User** = tenant

    **Role** = member
  terms:
  - login
  confidence:
    steps: High
- ac: HS-02
  seq: 1
  priority: P2
  title: Second
  objective: Second objective.
  steps: 1. Do it.
  expected: |-
    1. Done.
  post: Saved.
"""

UAT = """flow: /flows/F.md
scenario_id: SC-UAT-{jid}
entries:
  J01:
    area: Login
    priority: P1
    title: Log in
    objective: The tenant logs in.
    steps: |-
      1. Open the portal.
    expected: 1. The page opens.
    confidence:
      steps: High
  J02:
    area: Next
    priority: P1
    title: Next
    objective: Next.
    steps: 1. Go on.
    expected: 1. Done.
"""


def _changed_lines(old, new):
    """(first differing line index, lines removed, lines added)."""
    a, b = old.split("\n"), new.split("\n")
    i = 0
    while i < min(len(a), len(b)) and a[i] == b[i]:
        i += 1
    j = 0
    while j < min(len(a), len(b)) - i and a[-1 - j] == b[-1 - j]:
        j += 1
    return i, a[i:len(a) - j], b[i:len(b) - j]


def _refused(fn, *args):
    try:
        fn(*args)
    except t.Refused as e:
        return str(e)
    raise AssertionError("expected a refusal")


def test_clean_text_normalises_line_ends_and_edges():
    assert t.clean_text("\r\n1. A.  \r\n\r\n2. B.\t\n\n") == "1. A.\n\n2. B."
    assert t.clean_text("   ") == ""


def test_block_scalar_is_replaced_in_place_and_nothing_else_moves():
    new = t.apply_edit(SIT, "sit", 0, "steps", "1. Open it.\n2. Click **Go**.\n3. Wait.")
    at, gone, came = _changed_lines(SIT, new)
    assert gone == ["    1. Open the page.", "    2. Click **Login**."], gone
    assert came == ["    1. Open it.", "    2. Click **Go**.", "    3. Wait."], came
    assert SIT.split("\n")[at - 1] == "  steps: |-"


def test_one_line_value_becomes_a_block_scalar_when_text_has_lines():
    new = t.apply_edit(SIT, "sit", 0, "expected", "1. The page opens.\n2. A banner shows.")
    _at, gone, came = _changed_lines(SIT, new)
    assert gone == ["  expected: 1. The page opens."], gone
    assert came == ["  expected: |-", "    1. The page opens.", "    2. A banner shows."], came


def test_block_scalar_becomes_one_line_and_blank_lines_inside_it_go_with_it():
    new = t.apply_edit(SIT, "sit", 0, "data", "**User** = landlord")
    _at, gone, came = _changed_lines(SIT, new)
    assert gone == ["  data: |-", "    **User** = tenant", "", "    **Role** = member"], gone
    assert came == ["  data: '**User** = landlord'"], came


def test_text_yaml_would_misread_is_quoted_not_corrupted():
    for text in ("Tenant's value: 100% #1", "- starts with a dash", "yes", "123",
                 "{not: a map}", "café 大 - ok", "a: b\nc: d # e",
                 "  indented first line\nsecond"):
        clean = t.clean_text(text)
        new = t.apply_edit(SIT, "sit", 1, "objective", clean)
        assert yaml.safe_load(new)["test_cases"][1]["objective"] == clean, text


def test_missing_optional_key_is_inserted_after_its_anchor():
    new = t.apply_edit(SIT, "sit", 0, "pre_extra", "Tenant is logged in.")
    _at, gone, came = _changed_lines(SIT, new)
    assert gone == [] and came == ["  pre_extra: Tenant is logged in."], (gone, came)
    lines = new.split("\n")
    assert lines[lines.index(came[0]) - 1] == "    **Role** = member", "not after `data`"
    new = t.apply_edit(SIT, "sit", 1, "data", "**A** = 1")
    lines = new.split("\n")
    assert lines[lines.index("  data: '**A** = 1'") - 1] == "    1. Done.", "not after `expected`"


def test_none_removes_an_optional_key_and_only_it():
    new = t.apply_edit(SIT, "sit", 1, "post", None)
    _at, gone, came = _changed_lines(SIT, new)
    assert gone == ["  post: Saved."] and came == [], (gone, came)
    assert t.apply_edit(SIT, "sit", 0, "post", None) == SIT, "absent key: no change"


def test_last_key_of_a_file_with_no_final_newline():
    raw = SIT.rstrip("\n")
    new = t.apply_edit(raw, "sit", 1, "post", "Saved twice.")
    assert new == raw[:-len("Saved.")] + "Saved twice.\n"
    new = t.apply_edit(raw.replace("\n  post: Saved.", ""), "sit", 1, "post", "Late.")
    assert yaml.safe_load(new)["test_cases"][1]["post"] == "Late."


def test_crlf_file_keeps_crlf():
    raw = SIT.replace("\n", "\r\n")
    new = t.apply_edit(raw, "sit", 0, "steps", "1. A.\n2. B.")
    assert "\n" not in new.replace("\r\n", ""), "a bare LF was written into a CRLF file"
    assert yaml.safe_load(new)["test_cases"][0]["steps"] == "1. A.\n2. B."


def test_uat_entry_is_addressed_by_journey_id():
    new = t.apply_edit(UAT, "uat", "J02", "steps", "1. Go on.\n2. Stop.")
    _at, gone, came = _changed_lines(UAT, new)
    assert gone == ["    steps: 1. Go on."], gone
    assert came == ["    steps: |-", "      1. Go on.", "      2. Stop."], came
    assert yaml.safe_load(new)["entries"]["J01"] == yaml.safe_load(UAT)["entries"]["J01"]


def test_a_non_text_value_is_refused():
    assert "not a text value" in _refused(t.apply_edit, SIT, "sit", 0, "terms", "x")


def test_a_comment_inside_an_edited_keys_region_is_never_silently_deleted():
    own = SIT.replace("  expected: 1. The page opens.\n",
                      "  expected: 1. The page opens.\n      # keep: reviewer note\n")
    other = SIT.replace("  steps: 1. Do it.\n", "  steps: 1. Do it. # trailing note\n")
    hdr = SIT.replace("  steps: |-\n    1. Open the page.",
                      "  steps: |- # header note\n    1. Open the page.")
    for raw, field, key, note in ((own, "expected", 0, "keep: reviewer note"),
                                  (other, "steps", 1, "trailing note"),
                                  (hdr, "steps", 0, "header note")):
        for text in ("1. New.", "1. New.\n2. More."):
            try:
                new = t.apply_edit(raw, "sit", key, field, text)
            except t.Refused as e:
                assert note in str(e), str(e)
            else:
                assert note in new, (field, "comment was deleted")


def test_hash_lines_inside_a_block_scalar_are_text_and_editable():
    raw = SIT.replace("    2. Click **Login**.\n", "    2. Click **Login**.\n    # not a comment\n")
    assert yaml.safe_load(raw)["test_cases"][0]["steps"].endswith("# not a comment")
    new = t.apply_edit(raw, "sit", 0, "steps", "1. Fresh.")
    _at, gone, came = _changed_lines(raw, new)
    assert "    # not a comment" in gone and came == ["  steps: 1. Fresh."], (gone, came)


def test_real_specs_survive_an_edit_with_every_other_byte_intact():
    """The spec's promise, against the project's own files: a same-text edit
    reproduces the file byte for byte, and a new-text edit changes one
    contiguous run of lines."""
    done = 0
    for kind, d, fields in (("sit", ROOT / "tools/sit_specs", ("steps", "title")),
                            ("uat", ROOT / "tools/uat_specs", ("expected", "title"))):
        for path in sorted(d.glob("*.yaml")) if d.exists() else []:
            raw = path.read_bytes().decode("utf-8")
            spec = yaml.safe_load(raw)
            keys = (list(range(len(spec["test_cases"]))) if kind == "sit"
                    else list(spec["entries"]))
            for key in (keys[0], keys[len(keys) // 2], keys[-1]):
                entry = spec["test_cases"][key] if kind == "sit" else spec["entries"][key]
                for field in fields:
                    assert t.rewrite_key(raw, kind, key, field, entry[field]) == raw, \
                        (path.name, key, field)
                new = t.apply_edit(raw, kind, key, fields[0], "1. One.\n\n2. Two: 'x' # y")
                at, gone, came = _changed_lines(raw, new)
                assert came[1:] == ["1. One.", "", "2. Two: 'x' # y"] or \
                    [ln.strip() for ln in came][-3:] == ["1. One.", "", "2. Two: 'x' # y"], came
                assert raw.split("\n")[:at] == new.split("\n")[:at]
                done += 1
    if not done:
        print("[SKIP] test_real_specs_survive_an_edit: bundle has no specs")


def _with_spec_dirs(fn):
    """Point both renderers' SPEC_DIR at a temp dir holding the two fixtures."""
    with tempfile.TemporaryDirectory() as d:
        d = Path(d)
        (d / "sit").mkdir(); (d / "uat").mkdir()
        (d / "sit/US-X.yaml").write_text(SIT, encoding="utf-8", newline="\n")
        (d / "uat/F.yaml").write_text(UAT, encoding="utf-8", newline="\n")
        saved = render_sit.SPEC_DIR, render_uat.SPEC_DIR
        render_sit.SPEC_DIR, render_uat.SPEC_DIR = d / "sit", d / "uat"
        try:
            return fn(d)
        finally:
            render_sit.SPEC_DIR, render_uat.SPEC_DIR = saved


def test_a_test_case_resolves_to_its_spec_entry_by_scenario_id():
    def check(d):
        index = t.spec_index()
        assert set(index) == {"SC-X-HS-01-01", "SC-X-HS-02-01",
                              "SC-UAT-J01", "SC-UAT-J02"}, sorted(index)
        kind, path, key, entry = t.resolve(
            {"kind": "sit", "scenario_id": "SC-X-HS-02-01"}, index)
        assert (kind, path.name, key, entry["title"]) == ("sit", "US-X.yaml", 1, "Second")
        kind, path, key, entry = t.resolve(
            {"kind": "uat", "scenario_id": "SC-UAT-J02"}, index)
        assert (kind, path.name, key, entry["title"]) == ("uat", "F.yaml", "J02", "Next")
        assert t.resolve({"kind": "sit", "scenario_id": "SC-NOPE"}, index) is None
        # a SIT test case never resolves to a UAT entry that shares its scenario id
        assert t.resolve({"kind": "sit", "scenario_id": "SC-UAT-J01"}, index) is None
    _with_spec_dirs(check)


def test_editable_fields_follow_level_and_status():
    def check(d):
        index = t.spec_index()
        sit = {"kind": "sit", "scenario_id": "SC-X-HS-01-01", "status": "active"}
        uat = {"kind": "uat", "scenario_id": "SC-UAT-J01", "status": "active"}
        assert t.editable_fields(sit, index) == list(t.SIT_FIELDS)
        assert t.editable_fields(uat, index) == list(t.UAT_FIELDS)
        assert "data" not in t.UAT_FIELDS and "post" not in t.UAT_FIELDS
        for bad in (dict(sit, status="retired"), dict(sit, status="stale"),
                    dict(sit, scenario_id="SC-NOPE")):
            assert t.editable_fields(bad, index) == [], bad
        for never in ("confidence", "remarks", "ac", "seq", "technique",
                      "coverage_items", "run", "section", "continue_from"):
            assert never not in t.SIT_FIELDS + t.UAT_FIELDS, never
    _with_spec_dirs(check)


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"[PASS] {name}")
    print("test_wiki_tcedit OK")
