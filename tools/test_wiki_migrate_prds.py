#!/usr/bin/env python3
"""`wiki migrate-prds` on throwaway schema-1 projects
(run: py tools/test_wiki_migrate_prds.py). No pytest - matches tools/smoke.py.

Each project is a real git repo in a temp directory, driven through the real
CLI with TC_ROOT_OVERRIDE, so the commit and the lint gate inside
agent_commit are exercised for real. Nothing touches this checkout."""
import json
import os
import shutil
import stat
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import wiki
from wiki import read_concept, sha256, write_concept

SEC = {"1-1": ("1.1 Fees", "The application fee is 42 dollars."),
       "1-2": ("1.2 Refunds", "A rejected application is refunded in full.")}
TC_REL = "testcases/sit/m/1.1-AC01-01"
_ROOTS = []


def _git(d, *args):
    r = subprocess.run(["git", *args], cwd=d, capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    assert r.returncode == 0, f"git {args}: {r.stdout}{r.stderr}"
    return r.stdout


def _rm(path):
    """rmtree that also removes read-only .git objects (Windows)."""
    def onexc(func, p, _exc):
        os.chmod(p, stat.S_IWRITE)
        func(p)
    try:
        shutil.rmtree(path, onexc=onexc)
    except OSError:
        pass


def _snap(d):
    """Every file's bytes and every directory under `d`, minus .git."""
    files, dirs = {}, set()
    for p in sorted(d.rglob("*")):
        rel = p.relative_to(d).as_posix()
        if rel == ".git" or rel.startswith(".git/"):
            continue
        if p.is_dir():
            dirs.add(rel)
        else:
            files[rel] = p.read_bytes()
    return files, dirs


def _cli(d, *argv, **env_extra):
    env = dict(os.environ, TC_ROOT_OVERRIDE=str(d), **env_extra)
    return subprocess.run(
        [sys.executable, str(ROOT / "tools" / "wiki.py"), *argv], cwd=ROOT,
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        env=env)


def _commit_as_fixture(d, msg):
    _git(d, "add", "-A")
    _git(d, "commit", "-qm", msg)


def _manifest(d):
    return json.loads((d / "manifest.json").read_text(encoding="utf-8"))


def _staged_section(slug, num, title, body):
    return {"num": num, "slug": slug, "title": title,
            "heading_path": [f"{num} {title}"], "body": body,
            "content_hash": sha256(wiki.normalize(body))}


def _tc(prd_version):
    fm = {"type": "Test Case", "id": "1.1-AC01-01", "title": "Pay the fee",
          "description": "Fixture test case.", "kind": "sit",
          "module": "/modules/m.md", "status": "active",
          "covers": ["/stories/US-M1.md#AC1"], "scenario_id": "SC-M1-AC1-01",
          "priority": "P1",
          "generated_from": {"prd_version": prd_version, "figma_hashes": {},
                             "wiki_commit": "abc1234",
                             "generator_version": "1.0.0"},
          "stale_because": []}
    trace = ("- Covers: /stories/US-M1.md#AC1\n- Scenario: SC-M1-AC1-01 · "
             f"Technique: UC · PRD v{prd_version} · wiki abc1234")
    body = "\n".join(f"# {s}\n\n{trace if s == 'Traceability' else 'Fixture.'}\n"
                     for s in wiki.TC_SECTIONS)
    return fm, body


def _repo(with_prd=True, removed=False):
    """A schema-1 project in the flat layout, committed by a non-agent author
    so lint L10 (which reads tc-agent commits) sees only the migration."""
    d = Path(tempfile.mkdtemp(prefix="migrate-prds-")).resolve()
    _ROOTS.append(d)
    shutil.copyfile(ROOT / "tools/fixtures/multi_prd/config.yaml", d / "config.yaml")
    write_concept(d / "modules/m.md", {"type": "Module", "id": "m",
                  "title": "Module M", "description": "Fixture module."}, "# Module\n")
    story = {"type": "User Story", "id": "US-M1", "title": "Pay",
             "description": "Fixture story.", "status": "aligned",
             "asserted_by": "tester", "module": "/modules/m.md",
             "acceptance_criteria": [{"id": "AC1", "text": "Fixture criterion."}]}
    sources = {}
    if with_prd:
        for slug, (title, body) in SEC.items():
            h = sha256(wiki.normalize(body))
            write_concept(d / f"sources/prd/{slug}.md", {
                "type": "PRD Section", "id": f"prd#{slug}", "title": title,
                "description": f"PRD v1 section: {title.split(' ', 1)[1]}",
                "prd_version": 1, "content_hash": h,
                "source_file": "/inputs/prd/v1/spec.md",
                "heading_path": [title]}, body + "\n")
            sources[f"prd#{slug}"] = {"content_hash": h, "prd_version": 1}
        for v in (1, 2):
            p = d / f"inputs/prd/v{v}/spec.md"
            p.parent.mkdir(parents=True)
            p.write_text("1.1 Fees\nThe application fee is 42 dollars.\n",
                         encoding="utf-8", newline="\n")
        (d / "staging").mkdir()
        (d / "staging/prd-v2.json").write_text(json.dumps(
            {"version": 2, "source_file": "/inputs/prd/v2/spec.md",
             "staged_at": "2026-01-01T00:00:00+08:00", "sections": [
                 _staged_section("1-1", "1.1", "Fees",
                                 "The application fee is 50 dollars."),
                 _staged_section("1-2", "1.2", "Refunds", SEC["1-2"][1])]},
            indent=1, ensure_ascii=False),
            encoding="utf-8", newline="\n")
        write_concept(d / "changereports/CR-001.md", {
            "type": "Change Report", "id": "CR-001", "title": "CR-001: PRD v1 -> v1",
            "description": "0 modified", "from_version": 1, "to_version": 1,
            "status": "approved", "asserted_by": "tester",
            "asserted_at": "2026-01-01T00:00:00+08:00"},
            "# Summary\n\nPRD v1 -> v1: 0 section(s) modified.\n")
        write_concept(d / "changereports/CR-002.md", {
            "type": "Change Report", "id": "CR-002", "title": "CR-002: PRD v1 -> v2",
            "description": "1 modified", "from_version": 1, "to_version": 2,
            "status": "pending"},
            "# Summary\n\nPRD v1 -> v2: 1 section(s) modified.\n")
        story.update(provenance="prd-verbatim",
                     derived_from=["/sources/prd/1-1.md"],
                     source_pins={"prd#1-1": sources["prd#1-1"]["content_hash"]})
        story_body = "# Story\n\nSee [the refund rule](/sources/prd/1-2.md).\n"
        if removed:
            _make_removed(d, sources, story)
    else:
        story.update(provenance="human-stated")
        story_body = "# Story\n\nFixture.\n"
        (d / "inputs/prd/v1").mkdir(parents=True)
        (d / "inputs/prd/v1/.gitkeep").write_text("", encoding="utf-8")
        write_concept(d / "resolutions/R-M1-01.md", {
            "type": "Resolution", "id": "R-M1-01", "title": "AC1 as stated",
            "description": "Fixture resolution.", "status": "asserted",
            "asserted_by": "tester", "resolves": ["/stories/US-M1.md#AC1"]},
            "# Resolution\n\nFixture.\n")
    write_concept(d / "stories/US-M1.md", story, story_body)
    fm, body = _tc(1 if with_prd else None)
    tcp = d / f"{TC_REL}.md"
    write_concept(tcp, fm, body)
    manifest = {"schema_version": 1,
                "adopted_prd_version": (2 if removed else 1) if with_prd else None,
                "staged_prd_version": (None if removed else 2) if with_prd else None,
                "id_config_frozen": True,
                "id_format": "{story_num}-AC{ac_num:02d}-{seq:02d}",
                "counters": {"sit:m": 1}, "sources": sources, "concepts": {},
                "bindings": {"SC-M1-AC1-01": {"tc": TC_REL, "status": "active",
                                              "fragment_pins": {}}},
                "tc_hashes": {TC_REL: sha256(tcp.read_bytes())}, "edges": []}
    (d / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n",
                                     encoding="utf-8", newline="\n")
    _git(d, "init", "-q")
    _git(d, "config", "user.name", "fixture")
    _git(d, "config", "user.email", "fixture@internal")
    _git(d, "config", "commit.gpgsign", "false")
    _git(d, "config", "core.autocrlf", "false")
    _commit_as_fixture(d, "base")
    return d


def _make_removed(d, sources, story):
    """v2 was approved and dropped 1.2: the section keeps its text, carries
    removed_in, the story that cites it is pinned `<hash>@removed-v2`, and
    nothing is staged any more."""
    sec = d / "sources/prd/1-2.md"
    fm, body = read_concept(sec)
    fm["removed_in"] = 2
    write_concept(sec, fm, body)
    sources["prd#1-2"]["removed_in"] = 2
    story.update(
        derived_from=["/sources/prd/1-1.md", "/sources/prd/1-2.md"],
        source_pins={"prd#1-1": sources["prd#1-1"]["content_hash"],
                     "prd#1-2": sources["prd#1-2"]["content_hash"]
                     + "@removed-v2"})
    cr = d / "changereports/CR-002.md"
    cfm, cbody = read_concept(cr)
    cfm.update(status="approved", asserted_by="tester",
               asserted_at="2026-01-02T00:00:00+08:00")
    write_concept(cr, cfm, cbody)
    write_concept(d / "stories/US-M2.md", {
        "type": "User Story", "id": "US-M2", "title": "Refund",
        "description": "Fixture story.", "status": "needs-review",
        "provenance": "prd-verbatim", "module": "/modules/m.md",
        "derived_from": ["/sources/prd/1-2.md"],
        "source_pins": {"prd#1-2": sources["prd#1-2"]["content_hash"]},
        "review_because": [{"cause": "prd#1-2 removed in v2",
                            "at": "2026-01-02T00:00:00+08:00"}],
        "acceptance_criteria": [{"id": "AC1", "text": "Fixture criterion."}]},
        "# Story\n\nFixture.\n")
    write_concept(d / "glossary/fee.md", {
        "type": "Glossary Term", "id": "fee", "title": "Fee",
        "description": "Fixture term.", "status": "aligned",
        "asserted_by": "tester", "defined_in": ["/sources/prd/1-1.md"]},
        "# Definition\n\nFixture.\n")


def _commits(d):
    return int(_git(d, "rev-list", "--count", "HEAD"))


def _changed_lines(d, path):
    """(removed, added) content lines of HEAD's diff for one path."""
    out = _git(d, "show", "--format=", "--unified=0", "HEAD", "--", path)
    lines = [ln for ln in out.splitlines()
             if ln[:1] in "+-" and ln[:3] not in ("+++", "---")]
    return ([ln[1:] for ln in lines if ln[0] == "-"],
            [ln[1:] for ln in lines if ln[0] == "+"])


_MIGRATED = []
_BEFORE_SNAP = []


def _migrated():
    """One migrated single-PRD project, shared by the read-only assertions."""
    if not _MIGRATED:
        d = _repo()
        before = _commits(d)
        _BEFORE_SNAP.append(_snap(d))
        r = _cli(d, "migrate-prds", "--id", "legacy", "--title", "Legacy PRD")
        _MIGRATED.extend([d, before, r])
    return _MIGRATED


def test_single_prd_project_migrates_in_one_tc_agent_commit():
    d, before, r = _migrated()
    assert r.returncode == 0, r.stdout + r.stderr
    assert _commits(d) == before + 1, "exactly one commit"
    assert _git(d, "log", "-1", "--format=%an <%ae>").strip() == \
        "tc-agent <tc-agent@internal>"
    assert _git(d, "status", "--porcelain").strip() == "", "tree left clean"


def test_manifest_is_schema_2_with_the_prd_registered():
    d, _b, _r = _migrated()
    m = _manifest(d)
    assert m["schema_version"] == 2, m
    assert "adopted_prd_version" not in m and "staged_prd_version" not in m, m
    assert m["prds"] == {"legacy": {"title": "Legacy PRD", "adopted_version": 1,
                                    "staged_version": 2}}, m["prds"]
    assert sorted(m["sources"]) == ["prd#legacy/1-1", "prd#legacy/1-2"], m["sources"]
    assert m["sources"]["prd#legacy/1-1"]["prd"] == "legacy", m["sources"]
    assert "sources/prd/legacy/1-1" in m["concepts"], sorted(m["concepts"])
    assert "sources/prd/1-1" not in m["concepts"], sorted(m["concepts"])
    assert ["stories/US-M1", "derived_from", "sources/prd/legacy/1-1"] in m["edges"]


def test_files_move_one_level_down_and_carry_the_prd():
    d, _b, _r = _migrated()
    for gone in ("sources/prd/1-1.md", "inputs/prd/v1", "staging/prd-v2.json",
                 "changereports/CR-001.md"):
        assert not (d / gone).exists(), gone
    fm, body = read_concept(d / "sources/prd/legacy/1-1.md")
    assert fm["id"] == "prd#legacy/1-1" and fm["prd"] == "legacy", fm
    assert fm["source_file"] == "/inputs/prd/legacy/v1/spec.md", fm
    assert body == SEC["1-1"][1] + "\n", body
    assert (d / "inputs/prd/legacy/v1/spec.md").exists()
    assert (d / "inputs/prd/legacy/v2/spec.md").exists()
    staged = json.loads((d / "staging/legacy/prd-v2.json").read_text(encoding="utf-8"))
    assert staged["prd"] == "legacy", staged
    assert staged["source_file"] == "/inputs/prd/legacy/v2/spec.md", staged
    for cr, status in (("CR-001", "approved"), ("CR-002", "pending")):
        cfm, _body = read_concept(d / f"changereports/legacy/{cr}.md")
        assert cfm["prd"] == "legacy" and cfm["status"] == status, cfm


def test_story_references_are_rewritten_and_nothing_else():
    d, _b, _r = _migrated()
    fm, body = read_concept(d / "stories/US-M1.md")
    assert fm["derived_from"] == ["/sources/prd/legacy/1-1.md"], fm
    assert list(fm["source_pins"]) == ["prd#legacy/1-1"], fm["source_pins"]
    assert "(/sources/prd/legacy/1-2.md)" in body, body
    assert fm["status"] == "aligned" and fm["asserted_by"] == "tester", fm
    removed, added = _changed_lines(d, "stories/US-M1.md")
    assert len(removed) == 3 and len(added) == 3, (removed, added)
    assert all("sources/prd/" in ln or "prd#" in ln for ln in removed + added), \
        (removed, added)


def test_test_case_carries_prd_versions_and_is_resealed():
    d, _b, _r = _migrated()
    fm, body = read_concept(d / f"{TC_REL}.md")
    gf = fm["generated_from"]
    assert gf["prd_versions"] == {"legacy": 1} and "prd_version" not in gf, gf
    assert gf["wiki_commit"] == "abc1234", "a migration is not a re-render"
    assert list(gf)[0] == "prd_versions", "key order kept"
    assert "· PRD legacy v1 · wiki abc1234" in body, body
    assert _manifest(d)["tc_hashes"][TC_REL] == \
        sha256((d / f"{TC_REL}.md").read_bytes())
    orig = _git_bytes(d, f"HEAD~1:{TC_REL}.md").decode("utf-8")
    expect = orig.replace("  prd_version: 1\n", "  prd_versions:\n    legacy: 1\n") \
        .replace(" · PRD v1 · wiki", " · PRD legacy v1 · wiki")
    assert (d / f"{TC_REL}.md").read_bytes().decode("utf-8") == expect, \
        "only the two spots changed, every other byte is kept"
    assert "1 test case(s) rewritten and re-sealed" in _migrated()[2].stdout
    removed, added = _changed_lines(d, f"{TC_REL}.md")
    assert removed == ["  prd_version: 1", "- Scenario: SC-M1-AC1-01 · Technique: "
                       "UC · PRD v1 · wiki abc1234"], removed
    assert added == ["  prd_versions:", "    legacy: 1", "- Scenario: SC-M1-AC1-01 "
                     "· Technique: UC · PRD legacy v1 · wiki abc1234"], added


def test_the_diff_is_confined_to_the_expected_paths():
    d, _b, _r = _migrated()
    names = [n for n in _git(d, "show", "--format=", "--name-only", "-M",
                             "HEAD").splitlines() if n.strip()]
    allowed = ("manifest.json", "log.md", "stories/US-M1.md", f"{TC_REL}.md",
               "sources/prd/", "inputs/prd/", "staging/", "changereports/")
    stray = [n for n in names
             if not n.startswith(allowed) and not n.endswith("index.md")]
    assert not stray, stray
    assert "modules/m.md" not in names, "a concept with no PRD ref is untouched"


def test_lint_is_clean_after_migrating():
    d, _b, _r = _migrated()
    r = _cli(d, "lint", "--no-commit")
    assert r.returncode == 0 and "lint: 0 error(s)" in r.stdout, r.stdout + r.stderr


def test_migrating_twice_changes_nothing():
    d, before, _r = _migrated()
    r = _cli(d, "migrate-prds", "--id", "legacy", "--title", "Legacy PRD")
    assert r.returncode == 0 and "already migrated" in r.stdout, r.stdout + r.stderr
    assert _commits(d) == before + 1, "no second commit"
    assert _git(d, "status", "--porcelain").strip() == ""


def test_the_migrated_project_needs_no_prd_flag():
    d, _b, _r = _migrated()
    r = _cli(d, "diff", "--prd", "--no-commit")
    assert r.returncode == 0, r.stdout + r.stderr
    assert "PRD legacy v1 (adopted) vs v2 (staged):" in r.stdout, r.stdout


def _refused(d, *argv):
    r = _cli(d, "migrate-prds", *argv)
    out = r.stdout + r.stderr
    assert r.returncode != 0, out
    assert "Traceback" not in out, out
    assert _manifest(d)["schema_version"] == 1, "a refusal converts nothing"
    assert _git(d, "status", "--porcelain").strip() == "", "a refusal writes nothing"
    return out


def test_a_project_with_a_prd_needs_an_id():
    out = _refused(_repo())
    assert "--id <id>" in out and "--title" in out, out
    assert "2 section(s)" in out and "adopted v1" in out, out


def test_a_malformed_id_or_a_missing_title_is_refused():
    d = _repo()
    assert "lowercase-hyphen" in _refused(d, "--id", "Legacy PRD", "--title", "x")
    assert "--title" in _refused(d, "--id", "legacy")


def test_a_no_prd_project_migrates_with_no_arguments():
    d = _repo(with_prd=False)
    before = _commits(d)
    r = _cli(d, "migrate-prds")
    assert r.returncode == 0, r.stdout + r.stderr
    assert _commits(d) == before + 1
    m = _manifest(d)
    assert m["schema_version"] == 2 and m["prds"] == {}, m
    fm, body = read_concept(d / f"{TC_REL}.md")
    assert fm["generated_from"]["prd_versions"] == {}, fm["generated_from"]
    assert "· no PRD · wiki abc1234" in body and "PRD vNone" not in body, body
    removed, added = _changed_lines(d, f"{TC_REL}.md")
    assert added == ["  prd_versions: {}", "- Scenario: SC-M1-AC1-01 · Technique: "
                     "UC · no PRD · wiki abc1234"], added
    assert not (d / "inputs/prd/v1").exists()
    assert (d / "inputs/prd/.gitkeep").exists()
    r = _cli(d, "lint", "--no-commit")
    assert r.returncode == 0, r.stdout + r.stderr


def test_an_id_with_no_prd_to_name_is_refused():
    out = _refused(_repo(with_prd=False), "--id", "legacy", "--title", "Legacy PRD")
    assert "no PRD" in out and "without arguments" in out, out


def test_an_uningested_document_blocks_the_no_argument_form():
    d = _repo(with_prd=False)
    (d / "inputs/prd/v1/spec.md").write_text("1.1 Fees\nText.\n", encoding="utf-8")
    _commit_as_fixture(d, "a PRD nobody ingested")
    out = _refused(d)
    assert "1 document(s) under inputs/prd/vN/" in out and "--id <id>" in out, out


def test_hand_edit_drift_is_refused():
    d = _repo()
    p = d / f"{TC_REL}.md"
    p.write_text(p.read_text(encoding="utf-8") + "\nHand edit.\n",
                 encoding="utf-8", newline="\n")
    _commit_as_fixture(d, "hand edit")
    out = _refused(d, "--id", "legacy", "--title", "Legacy PRD")
    assert "not sealed" in out and TC_REL in out, out
    # release, revert and seal all refuse on schema 1: the refusal must not
    # send the reader round that circle.
    assert "platform revision the project last ran on" in out, out
    assert "upgrade and re-run migrate-prds" in out, out
    assert "tc-lifecycle" not in out and "py tools/wiki.py seal" not in out, out


def _in_place(d, rel, before):
    """The migration commit changed `rel` only where a moved section is
    named: the file is `before` with those references given the PRD id."""
    after = (d / rel).read_text(encoding="utf-8")
    expect = before.replace("/sources/prd/1-", "/sources/prd/legacy/1-") \
        .replace("prd#1-", "prd#legacy/1-")
    assert after == expect, after
    removed, added = _changed_lines(d, rel)
    assert removed and len(removed) == len(added), (removed, added)
    assert all("sources/prd/" in ln or "prd#" in ln for ln in removed + added), \
        (removed, added)
    diff = _git(d, "show", "--format=", "-M", "--unified=0", "-p", "HEAD")
    assert not wiki._l10_touches_assertion(diff), "an assertion line was added"


def test_a_non_canonical_asserted_file_is_edited_in_place():
    """`asserted_by: 'tester'` loads the same but write_concept would emit it
    unquoted - a NEW `asserted_by:` line in the diff, which lint L10 reads as
    an assertion made by tc-agent. The references are substituted where they
    stand instead, and the quoted line is not touched."""
    d = _repo()
    p = d / "stories/US-M1.md"
    raw = p.read_text(encoding="utf-8")
    assert "asserted_by: tester" in raw, raw
    p.write_text(raw.replace("asserted_by: tester", "asserted_by: 'tester'"),
                 encoding="utf-8", newline="\n")
    before = p.read_text(encoding="utf-8")
    _commit_as_fixture(d, "hand-formatted story")
    r = _cli(d, "migrate-prds", "--id", "legacy", "--title", "Legacy PRD")
    assert r.returncode == 0, r.stdout + r.stderr
    assert "asserted_by: 'tester'" in p.read_text(encoding="utf-8")
    _in_place(d, "stories/US-M1.md", before)
    out = _cli(d, "lint", "--no-commit")
    assert out.returncode == 0 and "lint: 0 error(s)" in out.stdout, out.stdout


def _escaped_ref(d):
    """A reference written with a YAML escape: it loads as the flat ref, but
    its text is nowhere in the file, so it cannot be substituted in place."""
    p = d / "stories/US-M1.md"
    raw = p.read_text(encoding="utf-8")
    assert "- /sources/prd/1-1.md" in raw, raw
    p.write_text(raw.replace("- /sources/prd/1-1.md",
                             '- "/sources/prd/1\\x2D1.md"'),
                 encoding="utf-8", newline="\n")
    assert read_concept(p)[0]["derived_from"] == ["/sources/prd/1-1.md"]


def test_a_reference_that_cannot_be_rewritten_in_place_is_refused():
    d = _repo()
    _escaped_ref(d)
    _commit_as_fixture(d, "a ref written with an escape")
    out = _refused(d, "--id", "legacy", "--title", "Legacy PRD")
    assert "stories/US-M1" in out and "canonical" in out, out
    assert "could not be rewritten in place" in out, out
    assert "platform revision the project last ran on" in out, out
    assert "re-assert" not in out, "assert refuses on schema 1 too"
    assert (d / "sources/prd/1-1.md").exists(), "nothing moved"


_REMOVED = []


def _migrated_removed():
    if not _REMOVED:
        d = _repo(removed=True)
        before = _commits(d)
        r = _cli(d, "migrate-prds", "--id", "legacy", "--title", "Legacy PRD")
        _REMOVED.extend([d, before, r])
    return _REMOVED


def test_a_removed_section_keeps_its_pin_and_cascade_flags_nothing():
    d, before, r = _migrated_removed()
    assert r.returncode == 0, r.stdout + r.stderr
    m = _manifest(d)
    assert m["prds"]["legacy"] == {"title": "Legacy PRD", "adopted_version": 2,
                                   "staged_version": None}, m["prds"]
    src = m["sources"]["prd#legacy/1-2"]
    assert src["removed_in"] == 2 and src["prd"] == "legacy", src
    fm, _b = read_concept(d / "sources/prd/legacy/1-2.md")
    assert fm["removed_in"] == 2 and fm["prd"] == "legacy", fm
    sfm, _b = read_concept(d / "stories/US-M1.md")
    pins = sfm["source_pins"]
    assert list(pins) == ["prd#legacy/1-1", "prd#legacy/1-2"], pins
    assert pins["prd#legacy/1-2"] == wiki.source_pin(src), "pin value unchanged"
    assert pins["prd#legacy/1-2"].endswith("@removed-v2"), pins
    assert pins["prd#legacy/1-1"] == wiki.source_pin(m["sources"]["prd#legacy/1-1"])
    r = _cli(d, "cascade", "--no-commit")
    assert r.returncode == 0 and "cascade: 0 item(s) flagged" in r.stdout, \
        r.stdout + r.stderr
    assert _git(d, "status", "--porcelain").strip() == "", "cascade wrote nothing"
    r = _cli(d, "lint", "--no-commit")
    assert r.returncode == 0 and "lint: 0 error(s)" in r.stdout, r.stdout + r.stderr


def test_free_text_causes_and_term_refs_are_rewritten_once():
    d, _b, _r = _migrated_removed()
    fm, _body = read_concept(d / "stories/US-M2.md")
    assert fm["review_because"][0]["cause"] == "prd#legacy/1-2 removed in v2", fm
    assert list(fm["source_pins"]) == ["prd#legacy/1-2"], fm["source_pins"]
    assert fm["status"] == "needs-review", fm
    tfm, _body = read_concept(d / "glossary/fee.md")
    assert tfm["defined_in"] == ["/sources/prd/legacy/1-1.md"], tfm
    assert tfm["status"] == "aligned" and tfm["asserted_by"] == "tester", tfm
    for rel in ("stories/US-M1.md", "stories/US-M2.md", "glossary/fee.md"):
        assert "legacy/legacy" not in (d / rel).read_text(encoding="utf-8"), rel


def test_a_report_matches_what_stage_prd_version_writes():
    d, _b, _r = _migrated()
    cfm, body = read_concept(d / "changereports/legacy/CR-002.md")
    assert list(cfm)[:6] == ["type", "id", "title", "description", "prd",
                             "from_version"], list(cfm)
    assert cfm["title"] == "CR-002: PRD legacy v1 -> v2", cfm["title"]
    assert body.startswith("# Summary\n\nPRD legacy v1 -> v2:"), body
    staged = json.loads((d / "staging/legacy/prd-v2.json").read_text(encoding="utf-8"))
    assert list(staged)[:3] == ["prd", "version", "source_file"], list(staged)


def test_no_assertion_line_is_added_anywhere():
    for d, _b, _r in (_migrated(), _migrated_removed()):
        diff = _git(d, "show", "--format=", "-M", "--unified=0", "-p", "HEAD")
        assert not wiki._l10_touches_assertion(diff), "an assertion line was added"
        added = [ln for ln in diff.splitlines()
                 if ln.startswith("+") and not ln.startswith("+++")]
        assert not [ln for ln in added if "confidence" in ln
                    or "coverage_status" in ln or "test_model" in ln], added


def _git_bytes(d, spec):
    return subprocess.run(["git", "show", spec], cwd=d, capture_output=True,
                          check=True).stdout


def test_files_with_no_prd_ref_are_byte_identical():
    d, _b, _r = _migrated()
    for rel in ("modules/m.md", "config.yaml"):
        assert (d / rel).read_bytes() == _git_bytes(d, f"HEAD~1:{rel}"), rel
    removed, added = _changed_lines(d, f"{TC_REL}.md")
    assert not [ln for ln in removed + added if "wiki_commit" in ln], \
        "a migration is not a re-render"


def test_a_staged_version_and_report_work_after_migrating():
    d = _repo()
    r = _cli(d, "migrate-prds", "--id", "legacy", "--title", "Legacy PRD")
    assert r.returncode == 0, r.stdout + r.stderr
    r = _cli(d, "diff", "--prd", "legacy", "--no-commit")
    assert r.returncode == 0 and "modified  1.1 Fees" in r.stdout, r.stdout + r.stderr
    r = _cli(d, "approve-cr", "CR-002", "--by", "tester", "--prd", "legacy")
    assert r.returncode == 0, r.stdout + r.stderr
    assert _manifest(d)["prds"]["legacy"]["adopted_version"] == 2
    fm, body = read_concept(d / "sources/prd/legacy/1-1.md")
    assert fm["prd_version"] == 2 and "50 dollars" in body, fm
    r = _cli(d, "lint", "--no-commit")
    assert r.returncode == 0 and "lint: 0 error(s)" in r.stdout, r.stdout + r.stderr


def test_an_unregistered_leftover_document_migrates_under_the_id():
    d = _repo(with_prd=False)
    (d / "inputs/prd/v1/spec.md").write_text("1.1 Fees\nText.\n", encoding="utf-8")
    _commit_as_fixture(d, "a PRD nobody ingested")
    r = _cli(d, "migrate-prds", "--id", "later", "--title", "Later PRD")
    assert r.returncode == 0, r.stdout + r.stderr
    assert (d / "inputs/prd/later/v1/spec.md").exists()
    assert _manifest(d)["prds"]["later"]["adopted_version"] is None


def test_an_id_that_collides_with_a_path_is_refused():
    d = _repo()
    assert "collides" in _refused(d, "--id", "v1", "--title", "x")


def test_a_dirty_tree_is_refused():
    d = _repo()
    (d / "stray.txt").write_text("x", encoding="utf-8")
    r = _cli(d, "migrate-prds", "--id", "legacy", "--title", "Legacy PRD")
    assert r.returncode != 0 and "uncommitted" in r.stdout + r.stderr
    assert _manifest(d)["schema_version"] == 1
    assert (d / "sources/prd/1-1.md").exists(), "nothing moved"


def test_the_workbook_note_is_printed():
    _d, _b, r = _migrated()
    assert "recompile the suites" in r.stdout, r.stdout


# ------------------------------------------------------------------ fix round 1

def _renames(d):
    out = _git(d, "show", "--format=", "--name-status", "-M", "HEAD")
    return {ln.split("\t")[-1]: ln.split("\t")[0] for ln in out.splitlines()
            if ln.strip()}


def test_acted_on_reports_are_only_given_a_prd_and_lint_stays_clean():
    d = _repo()
    long_line = "PRD v1 -> v1: " + "A long narrative the agent wrote. " * 40
    cr = d / "changereports/CR-001.md"
    cfm, _b = read_concept(cr)
    write_concept(cr, cfm, f"# Summary\n\n{long_line}\n")
    write_concept(d / "changereports/CR-003.md", {
        "type": "Change Report", "id": "CR-003", "title": "CR-003: PRD v1 -> v3",
        "description": "1 modified", "from_version": 1, "to_version": 3,
        "status": "rejected", "asserted_by": "tester",
        "asserted_at": "2026-01-03T00:00:00+08:00"},
        "# Summary\n\nPRD v1 -> v3: 1 section(s) modified.\n")
    _commit_as_fixture(d, "long approved report and a rejected one")
    r = _cli(d, "migrate-prds", "--id", "legacy", "--title", "Legacy PRD")
    assert r.returncode == 0, r.stdout + r.stderr
    kinds = _renames(d)
    for cr_id in ("CR-001", "CR-003"):
        assert kinds[f"changereports/legacy/{cr_id}.md"].startswith("R"), kinds
    fm, body = read_concept(d / "changereports/legacy/CR-001.md")
    assert fm["title"] == "CR-001: PRD v1 -> v1", "an acted-on report keeps its title"
    assert body == f"# Summary\n\n{long_line}\n", "and its summary"
    assert fm["prd"] == "legacy" and fm["status"] == "approved", fm
    fm3, _b3 = read_concept(d / "changereports/legacy/CR-003.md")
    assert fm3["title"] == "CR-003: PRD v1 -> v3" and fm3["status"] == "rejected"
    out = _cli(d, "lint", "--no-commit")
    assert out.returncode == 0 and "lint: 0 error(s)" in out.stdout, out.stdout
    assert "ERROR L10" not in out.stdout


def _unpairable(d, refs=20):
    """An approved report whose frontmatter is dominated by refs to moved
    sections and whose body is one line: once those refs gain the PRD id too
    few of its lines survive for git to pair it with its old path."""
    cr = d / "changereports/CR-001.md"
    cfm, _b = read_concept(cr)
    cfm["touched"] = ["/sources/prd/1-1.md"] * refs
    write_concept(cr, cfm, "# Summary\n\nx\n")
    _commit_as_fixture(d, "a report that cites many sections")


def _shorten(d):
    cr = d / "changereports/CR-001.md"
    cfm, body = read_concept(cr)
    cfm.pop("touched")
    write_concept(cr, cfm, body)
    _commit_as_fixture(d, "a human shortened the record")


def test_a_report_git_cannot_pair_is_refused_with_a_way_forward():
    d = _repo()
    _unpairable(d)
    out = _fails_then_succeeds(d, lambda: _shorten(d))
    assert "L10" in out and "changereports/legacy/CR-001.md" in out, out
    assert "cannot pair" in out and "shortens" in out, out
    assert "git status is clean" in out, out
    assert "Assertion-Event" not in _git(d, "log", "-1", "--format=%B")


def _git_cfg(d, key, value):
    _git(d, "config", key, value)


def test_the_self_check_holds_under_user_diff_settings():
    for key in ("diff.mnemonicPrefix", "diff.noprefix"):
        d = _repo()
        _unpairable(d)
        _git_cfg(d, key, "true")
        before, head = _snap(d), _git(d, "rev-parse", "HEAD")
        r = _cli(d, "migrate-prds", "--id", "legacy", "--title", "Legacy PRD")
        out = r.stdout + r.stderr
        assert r.returncode != 0 and "L10" in out, (key, out)
        _assert_untouched(d, before, head)


def test_a_normal_migration_commits_under_user_diff_settings():
    d = _repo()
    _git_cfg(d, "diff.mnemonicPrefix", "true")
    _git_cfg(d, "diff.noprefix", "true")
    r = _cli(d, "migrate-prds", "--id", "legacy", "--title", "Legacy PRD")
    assert r.returncode == 0, r.stdout + r.stderr
    out = _cli(d, "lint", "--no-commit")
    assert out.returncode == 0 and "lint: 0 error(s)" in out.stdout, out.stdout


def _assert_untouched(d, before, head):
    assert _snap(d) == before, "the tree is byte-identical, directories included"
    assert _git(d, "rev-parse", "HEAD") == head, "HEAD did not move"
    assert _git(d, "status", "--porcelain").strip() == ""
    assert _manifest(d)["schema_version"] == 1


def _fails_then_succeeds(d, fix, **env):
    before, head = _snap(d), _git(d, "rev-parse", "HEAD")
    r = _cli(d, "migrate-prds", "--id", "legacy", "--title", "Legacy PRD", **env)
    out = r.stdout + r.stderr
    assert r.returncode != 0 and "Traceback" not in out, out
    assert "already migrated" not in out, out
    _assert_untouched(d, before, head)
    fix()
    r = _cli(d, "migrate-prds", "--id", "legacy", "--title", "Legacy PRD")
    assert r.returncode == 0 and "already migrated" not in r.stdout, \
        r.stdout + r.stderr
    assert _manifest(d)["schema_version"] == 2
    assert _git(d, "rev-parse", "HEAD") != head
    return out


def test_a_lint_failure_that_only_exists_after_the_move_is_rolled_back():
    """A nested sources/prd/old/ passes schema-1 lint; once the manifest is
    schema 2, L13 says PRD 'old' is not registered."""
    d = _repo()
    h = sha256(wiki.normalize("Old text."))
    write_concept(d / "sources/prd/old/9-9.md", {
        "type": "PRD Section", "id": "prd#old/9-9", "title": "9.9 Old",
        "description": "PRD v1 section: Old", "prd": "old", "prd_version": 1,
        "content_hash": h, "source_file": "/inputs/prd/old/v1/x.md",
        "heading_path": ["9.9 Old"]}, "Old text.\n")
    sfm, sbody = read_concept(d / "stories/US-M1.md")
    sfm["derived_from"] = sfm["derived_from"] + ["/sources/prd/old/9-9.md"]
    write_concept(d / "stories/US-M1.md", sfm, sbody)
    _commit_as_fixture(d, "a story citing a nested PRD folder")
    assert _cli(d, "lint", "--no-commit").returncode == 0, "passes at schema 1"

    def fix():
        _rm(d / "sources/prd/old")
        sfm["derived_from"].pop()
        write_concept(d / "stories/US-M1.md", sfm, sbody)
        _commit_as_fixture(d, "dropped the nested folder")
    out = _fails_then_succeeds(d, fix)
    assert "L13" in out, out


def test_a_failing_pre_commit_hook_is_rolled_back():
    d = _repo()
    hook = d / ".git/hooks/pre-commit"
    hook.write_text("#!/bin/sh\nexit 1\n", encoding="utf-8", newline="\n")
    out = _fails_then_succeeds(d, lambda: hook.unlink())
    assert "did not go through" in out, out


def test_an_exception_mid_rewrite_is_rolled_back():
    d = _repo()
    out = _fails_then_succeeds(d, lambda: None, TC_MIGRATE_PRDS_FAULT="raise:6")
    assert "injected fault" in out and "restored" in out, out


def test_a_schema_2_manifest_with_a_dirty_tree_is_not_already_migrated():
    d, _b, _r = _migrated()
    stray = d / "stray.txt"
    stray.write_text("x", encoding="utf-8")
    try:
        r = _cli(d, "migrate-prds", "--id", "legacy", "--title", "Legacy PRD")
        out = r.stdout + r.stderr
        assert r.returncode != 0 and "stopped halfway" in out, out
        assert "already migrated" not in out, out
    finally:
        stray.unlink()


def test_no_commit_and_allow_lint_errors_are_refused():
    d = _repo()
    for flag in ("--no-commit", "--allow-lint-errors"):
        out = _refused(d, "--id", "legacy", "--title", "Legacy PRD", flag)
        assert "not accepted" in out, out


def test_a_lint_crash_reads_as_a_refusal():
    d = _repo()
    (d / "config.yaml").write_text("project: [unclosed\n", encoding="utf-8")
    _commit_as_fixture(d, "broken config")
    out = _refused(d, "--id", "legacy", "--title", "Legacy PRD")
    assert "lint" in out, out


def _canon_story_with(d, mutate):
    p = d / "stories/US-M1.md"
    fm, body = read_concept(p)
    mutate(fm)
    write_concept(p, fm, body)
    return p


def test_a_hand_formatted_story_with_assertion_fields_keeps_them_byte_for_byte():
    d = _repo()
    p = _canon_story_with(d, lambda fm: fm.update(
        asserted_at="2026-01-01T00:00:00+08:00", coverage_status="confirmed"))
    p.write_text(p.read_text(encoding="utf-8")
                 .replace("coverage_status: confirmed", "coverage_status: 'confirmed'"),
                 encoding="utf-8", newline="\n")
    before = p.read_text(encoding="utf-8")
    _commit_as_fixture(d, "hand-formatted")
    r = _cli(d, "migrate-prds", "--id", "legacy", "--title", "Legacy PRD")
    assert r.returncode == 0, r.stdout + r.stderr
    assert "coverage_status: 'confirmed'" in p.read_text(encoding="utf-8")
    _in_place(d, "stories/US-M1.md", before)


def test_a_commented_file_keeps_its_comment_and_a_flow_list_is_rewritten():
    d = _repo()
    write_concept(d / "modules/m2.md", {
        "type": "Module", "id": "m2", "title": "Module M2",
        "description": "Fixture module.",
        "derived_from": ["/sources/prd/1-1.md"]}, "# Module\n")
    p = d / "modules/m2.md"
    p.write_text(p.read_text(encoding="utf-8").replace(
        "id: m2", "id: m2  # keep this note").replace(
        "derived_from:\n- /sources/prd/1-1.md",
        "derived_from: [/sources/prd/1-1.md, '/sources/prd/1-2.md']"),
        encoding="utf-8", newline="\n")
    before = p.read_text(encoding="utf-8")
    assert "derived_from: [" in before, before
    _commit_as_fixture(d, "module with a comment and a flow-style list")
    r = _cli(d, "migrate-prds", "--id", "legacy", "--title", "Legacy PRD")
    assert r.returncode == 0, r.stdout + r.stderr
    _in_place(d, "modules/m2.md", before)
    assert "# keep this note" in p.read_text(encoding="utf-8")
    fm, _b = read_concept(p)
    assert fm["derived_from"] == ["/sources/prd/legacy/1-1.md",
                                  "/sources/prd/legacy/1-2.md"], fm


def test_a_description_that_quotes_a_section_id_is_not_rewritten():
    """Only what the plan rewrites is substituted: free text that happens to
    hold a section id (a description, not a `cause`) is left as it is."""
    d = _repo()
    p = d / "stories/US-M1.md"
    raw = p.read_text(encoding="utf-8")
    p.write_text(raw.replace("description: Fixture story.",
                             "description: 'See prd#1-1 for the fee.'"),
                 encoding="utf-8", newline="\n")
    _commit_as_fixture(d, "a quoted description naming a section id")
    r = _cli(d, "migrate-prds", "--id", "legacy", "--title", "Legacy PRD")
    assert r.returncode == 0, r.stdout + r.stderr
    fm, _b = read_concept(p)
    assert fm["description"] == "See prd#1-1 for the fee.", fm["description"]
    assert list(fm["source_pins"]) == ["prd#legacy/1-1"], fm["source_pins"]
    assert "stories/US-M1.md still names the flat 'prd#1-1'" in r.stdout, r.stdout


def test_a_non_canonical_moved_report_gains_its_prd_in_place():
    d = _repo()
    for cr in ("CR-001", "CR-002"):
        p = d / f"changereports/{cr}.md"
        p.write_text(p.read_text(encoding="utf-8").replace(
            f"id: {cr}", f"id: {cr}  # filed"), encoding="utf-8", newline="\n")
    _commit_as_fixture(d, "commented reports")
    r = _cli(d, "migrate-prds", "--id", "legacy", "--title", "Legacy PRD")
    assert r.returncode == 0, r.stdout + r.stderr
    done = (d / "changereports/legacy/CR-001.md").read_text(encoding="utf-8")
    assert "id: CR-001  # filed" in done, done
    assert "description: 0 modified\nprd: legacy\nfrom_version: 1" in done, done
    assert "title: 'CR-001: PRD v1 -> v1'" in done, "an acted-on report keeps its title"
    fm, body = read_concept(d / "changereports/legacy/CR-002.md")
    assert fm["prd"] == "legacy" and fm["title"] == "CR-002: PRD legacy v1 -> v2", fm
    assert body.startswith("# Summary\n\nPRD legacy v1 -> v2:"), body
    assert _renames(d)["changereports/legacy/CR-001.md"].startswith("R")
    out = _cli(d, "lint", "--no-commit")
    assert out.returncode == 0 and "lint: 0 error(s)" in out.stdout, out.stdout


# ---- a voided AC: retirement.caused_by, voided.caused_by and fragment pins ----

AC2 = "/stories/US-M1.md#AC2"
RETIRED_REL = "testcases/sit/m/1.1-AC02-01"


def _voided(stale_pin=None):
    """AC2 was voided against PRD section 1.2 (`void-ac --caused-by`): the AC
    carries voided.caused_by, the test case that covered only AC2 was retired
    with retirement.caused_by, and the active test case covers AC1 and AC2
    and pins both fragments."""
    d = _repo()
    stamp = "2026-01-03T00:00:00+08:00"
    sp = d / "stories/US-M1.md"
    fm, body = read_concept(sp)
    fm["acceptance_criteria"].append({
        "id": "AC2", "text": "Voided criterion.", "status": "voided",
        "voided": {"caused_by": "/sources/prd/1-2.md", "cause_version": 2,
                   "asserted_by": "tester", "asserted_at": stamp}})
    write_concept(sp, fm, body)
    frags = wiki.fragment_hash_map(fm)
    tcp = d / f"{TC_REL}.md"
    tfm, tbody = read_concept(tcp)
    tfm["covers"] = ["/stories/US-M1.md#AC1", AC2]
    write_concept(tcp, tfm, tbody)
    rfm, rbody = _tc(1)
    rfm.update(id="1.1-AC02-01", scenario_id="SC-M1-AC2-01", covers=[AC2],
               status="retired", retirement={
                   "reason": "voided", "caused_by": "/sources/prd/1-2.md",
                   "cause_version": 2, "asserted_by": "tester",
                   "asserted_at": stamp, "note": f"cascaded from void of {AC2}"})
    rp = d / f"{RETIRED_REL}.md"
    write_concept(rp, rfm, rbody.replace("SC-M1-AC1-01", "SC-M1-AC2-01"))
    mf = _manifest(d)
    mf["bindings"]["SC-M1-AC1-01"]["fragment_pins"] = {
        "stories/US-M1#AC1": frags["AC1"],
        "stories/US-M1#AC2": stale_pin or frags["AC2"]}
    mf["bindings"]["SC-M1-AC2-01"] = {
        "tc": RETIRED_REL, "status": "retired",
        "fragment_pins": {"stories/US-M1#AC2": frags["AC2"]}}
    for rel, path in ((TC_REL, tcp), (RETIRED_REL, rp)):
        mf["tc_hashes"][rel] = sha256(path.read_bytes())
    (d / "manifest.json").write_text(json.dumps(mf, indent=2) + "\n",
                                     encoding="utf-8", newline="\n")
    _commit_as_fixture(d, "AC2 voided against PRD section 1.2")
    assert _cli(d, "lint", "--no-commit").returncode == 0, "passes at schema 1"
    return d, frags


def test_a_project_with_a_voided_ac_migrates_and_nothing_goes_stale():
    d, frags = _voided()
    r = _cli(d, "migrate-prds", "--id", "legacy", "--title", "Legacy PRD")
    assert r.returncode == 0, r.stdout + r.stderr
    # the retired test case: its three spots, every other byte kept
    orig = _git_bytes(d, f"HEAD~1:{RETIRED_REL}.md").decode("utf-8")
    expect = orig.replace("  prd_version: 1\n", "  prd_versions:\n    legacy: 1\n") \
        .replace(" · PRD v1 · wiki", " · PRD legacy v1 · wiki") \
        .replace("  caused_by: /sources/prd/1-2.md",
                 "  caused_by: /sources/prd/legacy/1-2.md")
    assert expect != orig
    assert (d / f"{RETIRED_REL}.md").read_bytes().decode("utf-8") == expect
    rfm, _b = read_concept(d / f"{RETIRED_REL}.md")
    assert rfm["retirement"]["caused_by"] == "/sources/prd/legacy/1-2.md", rfm
    assert rfm["status"] == "retired" and rfm["retirement"]["asserted_by"] == "tester"
    # the story's voided AC names the moved section, so its hash changed ...
    sfm, _b = read_concept(d / "stories/US-M1.md")
    ac2 = sfm["acceptance_criteria"][1]
    assert ac2["voided"]["caused_by"] == "/sources/prd/legacy/1-2.md", ac2
    now = wiki.fragment_hash_map(sfm)
    assert now["AC2"] != frags["AC2"] and now["AC1"] == frags["AC1"], now
    # ... and every pin that matched it moved with it
    m = _manifest(d)
    assert m["bindings"]["SC-M1-AC1-01"]["fragment_pins"] == {
        "stories/US-M1#AC1": now["AC1"], "stories/US-M1#AC2": now["AC2"]}, m["bindings"]
    assert m["bindings"]["SC-M1-AC2-01"]["fragment_pins"] == {
        "stories/US-M1#AC2": now["AC2"]}, m["bindings"]
    assert "2 fragment pin(s) moved" in r.stdout, r.stdout
    assert m["tc_hashes"][RETIRED_REL] == sha256((d / f"{RETIRED_REL}.md").read_bytes())
    diff = _git(d, "show", "--format=", "-M", "--unified=0", "-p", "HEAD")
    assert not wiki._l10_touches_assertion(diff), "an assertion line was added"
    r = _cli(d, "cascade", "--no-commit")
    assert r.returncode == 0 and "cascade: 0 item(s) flagged" in r.stdout, \
        r.stdout + r.stderr
    assert _git(d, "status", "--porcelain").strip() == "", "cascade wrote nothing"
    r = _cli(d, "lint", "--no-commit")
    assert r.returncode == 0 and "lint: 0 error(s)" in r.stdout, r.stdout + r.stderr


def test_a_pin_that_was_already_out_of_date_stays_out_of_date():
    d, frags = _voided(stale_pin="sha256:" + "0" * 64)
    r = _cli(d, "migrate-prds", "--id", "legacy", "--title", "Legacy PRD")
    assert r.returncode == 0, r.stdout + r.stderr
    pins = _manifest(d)["bindings"]["SC-M1-AC1-01"]["fragment_pins"]
    assert pins["stories/US-M1#AC2"] == "sha256:" + "0" * 64, pins
    assert pins["stories/US-M1#AC1"] == frags["AC1"], pins
    assert "1 fragment pin(s) moved" in r.stdout, r.stdout
    r = _cli(d, "cascade", "--no-commit")
    assert "TC 1.1-AC01-01 -> stale (stories/US-M1#AC2)" in r.stdout, r.stdout


def test_a_non_canonical_file_that_is_not_touched_does_not_block():
    d = _repo()
    m = d / "modules/m.md"
    m.write_text(m.read_text(encoding="utf-8").replace(
        "id: m\n", "id: m  # a note\n").replace("title: Module M",
                                                   "title: 'Module M'"),
        encoding="utf-8", newline="\n")
    tc = d / f"{TC_REL}.md"
    tc.write_text(tc.read_text(encoding="utf-8").replace(
        "title: Pay the fee", "title: 'Pay the fee'"), encoding="utf-8", newline="\n")
    mf = _manifest(d)
    mf["tc_hashes"][TC_REL] = sha256(tc.read_bytes())
    (d / "manifest.json").write_text(json.dumps(mf, indent=2) + "\n",
                                     encoding="utf-8", newline="\n")
    _commit_as_fixture(d, "hand-formatted but untouched")
    r = _cli(d, "migrate-prds", "--id", "legacy", "--title", "Legacy PRD")
    assert r.returncode == 0, r.stdout + r.stderr
    assert "# a note" in m.read_text(encoding="utf-8"), "untouched file kept"
    text = tc.read_text(encoding="utf-8")
    assert "title: 'Pay the fee'" in text, "test case edited at its spots only"
    assert "prd_versions:\n    legacy: 1" in text, text


def test_a_section_with_the_wrong_id_is_refused():
    d = _repo()
    p = d / "sources/prd/1-1.md"
    fm, body = read_concept(p)
    fm["id"] = "prd#something-else"
    write_concept(p, fm, body)
    _commit_as_fixture(d, "wrong id")
    out = _refused(d, "--id", "legacy", "--title", "Legacy PRD")
    assert "sources/prd/1-1.md" in out and "prd#1-1" in out, out


def test_an_id_shaped_like_a_version_directory_is_refused():
    assert "collides" in _refused(_repo(), "--id", "v2", "--title", "x")


def test_a_reserved_id_is_refused():
    assert "reserved name" in _refused(_repo(), "--id", "index", "--title", "x")


def test_the_equals_form_of_a_flag_is_refused_not_ignored():
    out = _refused(_repo(), "--id=legacy", "--title", "Legacy PRD")
    assert "'--id=legacy' is not read" in out and "--id legacy" in out, out


def test_a_schema_version_that_is_not_a_whole_number_is_a_refusal():
    d = _repo()
    m = _manifest(d)
    m["schema_version"] = "two"
    (d / "manifest.json").write_text(json.dumps(m, indent=2) + "\n",
                                     encoding="utf-8", newline="\n")
    _commit_as_fixture(d, "a manifest with a bad schema_version")
    for argv in (["status"], ["lint"], ["next"], ["migrate-prds"],
                 ["tc", "edit", "1.1-AC01-01", "--field", "title",
                  "--from", "x.txt", "--by", "tester"]):
        r = _cli(d, *argv)
        out = r.stdout + r.stderr
        assert r.returncode != 0 and "Traceback" not in out, (argv, out)
        assert "schema_version 'two'" in out and "not a whole number" in out, \
            (argv, out)
    # the app's read model shows the same text on every page (as it does for
    # schema 1) instead of failing the page
    s = _app_py(d, "import read_models; print(json.dumps(read_models.state()))")
    assert s["schema1"] is True and "not a whole number" in s["notice"], s["notice"]
    assert "migrate-prds" not in s["notice"], s["notice"]
    assert _git(d, "status", "--porcelain").strip() == "", "a refusal writes nothing"


def test_token_boundaries():
    from wiki_migrate_prds import _token
    s = _token("prd#1-2 removed; xprd#1-2; prd#1-2x; prd#legacy/1-2; "
               "(prd#1-2)", "legacy", {"1-2"})
    assert s == ("prd#legacy/1-2 removed; xprd#1-2; prd#1-2x; prd#legacy/1-2; "
                 "(prd#legacy/1-2)"), s


def test_leftover_flat_tokens_and_dropped_versions_are_noted():
    d = _repo()
    p = d / "stories/US-M1.md"
    fm, _body = read_concept(p)
    write_concept(p, fm, "# Story\n\nSee `/sources/prd/1-2.md` and "
                  "<a href=\"sources/prd/1-2\">x</a>.\n")
    write_concept(d / "stories/US-M3.md", {
        "type": "User Story", "id": "US-M3", "title": "Plain",
        "description": "Fixture story.", "status": "needs-review",
        "provenance": "human-stated", "module": "/modules/m.md",
        "acceptance_criteria": [{"id": "AC1", "text": "Fixture criterion."}]},
        "# Story\n\nFixture.\n")
    write_concept(d / "resolutions/R-M3-01.md", {
        "type": "Resolution", "id": "R-M3-01", "title": "AC1 as stated",
        "description": "Fixture resolution.", "status": "asserted",
        "asserted_by": "tester", "resolves": ["/stories/US-M3.md#AC1"]},
        "# Resolution\n\nFixture.\n")
    fm2, body2 = _tc(1)
    fm2.update(id="1.1-AC02-01", scenario_id="SC-M1-AC1-02",
               covers=["/stories/US-M3.md#AC1"])
    body2 = body2.replace("SC-M1-AC1-01", "SC-M1-AC1-02")
    write_concept(d / "testcases/sit/m/1.1-AC02-01.md", fm2, body2)
    fm3, body3 = _tc(None)
    fm3.update(id="1.1-AC03-01", scenario_id="SC-M1-AC1-03")
    fm3["generated_from"] = {"prd_versions": {}, "figma_hashes": {},
                             "wiki_commit": "abc1234", "generator_version": "1.0.0"}
    body3 = body3.replace("SC-M1-AC1-01", "SC-M1-AC1-03").replace(
        "PRD vNone", "no PRD")
    write_concept(d / "testcases/sit/m/1.1-AC03-01.md", fm3, body3)
    mf = _manifest(d)
    for tid in ("1.1-AC02-01", "1.1-AC03-01"):
        rel = f"testcases/sit/m/{tid}"
        mf["tc_hashes"][rel] = sha256((d / f"{rel}.md").read_bytes())
    (d / "manifest.json").write_text(json.dumps(mf, indent=2) + "\n",
                                     encoding="utf-8", newline="\n")
    _commit_as_fixture(d, "extra stories and test cases")
    r = _cli(d, "migrate-prds", "--id", "legacy", "--title", "Legacy PRD")
    assert r.returncode == 0, r.stdout + r.stderr
    out = r.stdout
    assert "stories/US-M1.md still names the flat 'sources/prd/1-2'" in out, out
    assert "1 test case(s) carried a PRD version but their story cites no PRD" in out \
        and "1.1-AC02-01 (v1)" in out, out
    assert "already have prd_versions {} although their story cites the PRD" in out \
        and "1.1-AC03-01" in out, out
    assert "2 test case(s) rewritten and re-sealed" in out, out


def test_the_whole_tree_diff_is_exactly_the_expected_list():
    d, _b, _r = _migrated()
    bf, bd = _BEFORE_SNAP[0]
    af, ad = _snap(d)
    changed = {k for k in bf if k in af and bf[k] != af[k]}
    removed = {k for k in bf if k not in af}
    added = {k for k in af if k not in bf}
    same = {k for k in bf if k in af and bf[k] == af[k]}
    idx = lambda s: {k for k in s if k.endswith("index.md")}
    assert changed - idx(changed) == {"manifest.json", "stories/US-M1.md",
                                      f"{TC_REL}.md"}, changed
    assert removed == {"sources/prd/1-1.md", "sources/prd/1-2.md",
                       "inputs/prd/v1/spec.md", "inputs/prd/v2/spec.md",
                       "staging/prd-v2.json", "changereports/CR-001.md",
                       "changereports/CR-002.md"}, removed
    assert added - idx(added) == {
        "sources/prd/legacy/1-1.md", "sources/prd/legacy/1-2.md",
        "inputs/prd/legacy/v1/spec.md", "inputs/prd/legacy/v2/spec.md",
        "staging/legacy/prd-v2.json", "changereports/legacy/CR-001.md",
        "changereports/legacy/CR-002.md", "log.md"}, added
    assert {"config.yaml", "modules/m.md"} <= same, same
    assert "sources/prd/legacy/index.md" in added
    for k in same:
        assert bf[k] == af[k]
    # the moved uploads kept their bytes
    assert af["inputs/prd/legacy/v1/spec.md"] == bf["inputs/prd/v1/spec.md"]

def _reseal(d, rel, msg):
    mf = _manifest(d)
    mf["tc_hashes"][rel] = sha256((d / f"{rel}.md").read_bytes())
    (d / "manifest.json").write_text(json.dumps(mf, indent=2) + "\n",
                                     encoding="utf-8", newline="\n")
    _commit_as_fixture(d, msg)


def test_the_traceability_edit_is_anchored_to_its_own_section():
    d = _repo()
    tc = d / f"{TC_REL}.md"
    raw = tc.read_text(encoding="utf-8")
    tc.write_text(raw.replace("# Objective\n\nFixture.",
                              "# Objective\n\nSee x · PRD v1 · wiki zzz sample.", 1),
                  encoding="utf-8", newline="\n")
    assert "x · PRD v1 · wiki zzz" in tc.read_text(encoding="utf-8")
    _reseal(d, TC_REL, "an earlier section quotes the same text")
    r = _cli(d, "migrate-prds", "--id", "legacy", "--title", "Legacy PRD")
    assert r.returncode == 0, r.stdout + r.stderr
    text = tc.read_text(encoding="utf-8")
    assert "See x · PRD v1 · wiki zzz sample." in text, "earlier section untouched"
    assert "· PRD legacy v1 · wiki abc1234" in text, text


def test_both_kinds_of_offender_are_listed_together():
    d = _repo()
    tc = d / f"{TC_REL}.md"
    tc.write_text(tc.read_text(encoding="utf-8").replace(
        " · PRD v1 · wiki abc1234", ""), encoding="utf-8", newline="\n")
    _reseal(d, TC_REL, "a test case with no PRD tail")
    _escaped_ref(d)
    _commit_as_fixture(d, "a ref written with an escape")
    out = _refused(d, "--id", "legacy", "--title", "Legacy PRD")
    assert TC_REL in out and "stories/US-M1" in out, out


def test_untracked_files_under_a_version_directory_are_left_alone():
    d = _repo(with_prd=False)
    (d / ".gitignore").write_text("Thumbs.db\n", encoding="utf-8", newline="\n")
    _commit_as_fixture(d, "ignore Thumbs.db")
    (d / "inputs/prd/v1/Thumbs.db").write_bytes(b"precious")
    r = _cli(d, "migrate-prds")
    assert r.returncode == 0, r.stdout + r.stderr
    assert (d / "inputs/prd/v1/Thumbs.db").read_bytes() == b"precious"
    assert "inputs/prd/v1/Thumbs.db" in r.stdout and "left in place" in r.stdout
    assert not (d / "inputs/prd/v1/.gitkeep").exists(), "the tracked file went"
    assert (d / "inputs/prd/.gitkeep").exists()
    assert _git(d, "status", "--porcelain").strip() == ""


def test_a_post_commit_hook_that_dirties_the_tree_is_reported_not_undone():
    d = _repo()
    hook = d / ".git/hooks/post-commit"
    hook.write_text("#!/bin/sh\necho x > post-hook.txt\n", encoding="utf-8",
                    newline="\n")
    head = _git(d, "rev-parse", "HEAD")
    r = _cli(d, "migrate-prds", "--id", "legacy", "--title", "Legacy PRD")
    assert r.returncode == 0, r.stdout + r.stderr
    assert "IS committed" in r.stdout and "post-hook.txt" in r.stdout, r.stdout
    assert _git(d, "rev-parse", "HEAD") != head
    assert _manifest(d)["schema_version"] == 2


def test_an_interrupt_during_the_roll_back_finishes_it_and_is_reported():
    import wiki_migrate_prds as mod
    seen = []

    class _Ok:
        returncode = 0

    real = mod._git
    mod._git = lambda *a, **k: _Ok()
    try:
        j = mod.Journal()

        def boom():
            raise KeyboardInterrupt()
        j.undo = [lambda: seen.append("first"), boom,
                  lambda: seen.append("last")]
        failed = j.restore()
    finally:
        mod._git = real
    assert seen == ["last", "first"], "every undo ran despite the interrupt"
    assert j.interrupted and failed, failed


# ---- the schema-1 refusal: everything but migrate-prds, status and lint ----

def test_schema1_refusal_names_migrate_prds():
    d = _repo()
    for argv in (["next"], ["gate", "--story", "US-M1"], ["seal"], ["manifest"],
                 ["index"], ["cascade"], ["rtm"], ["suite", "compile", "x"],
                 ["ingest-prd"], ["diff", "--prd"], ["triage"], ["doubts"],
                 ["card", "--story", "US-M1"], ["export", "x"],
                 ["doubts", "card", "--story", "US-M1"],
                 ["doubts", "answer", "--card", "x.json", "--by", "tester"],
                 ["doubts", "observe", "--workbook", "x.xlsx", "--by", "tester"],
                 ["flow-draft", "x.json"]):
        r = _cli(d, *argv, "--no-commit")
        out = r.stdout + r.stderr
        assert r.returncode != 0, (argv, out)
        assert f"{argv[0]} refused: manifest.json is schema 1" in out, (argv, out)
        assert "py tools/wiki.py migrate-prds" in out, (argv, out)
    assert _git(d, "status", "--porcelain").strip() == "", "a refusal writes nothing"


def test_status_and_lint_still_run_on_schema1():
    d = _repo()
    r = _cli(d, "status")
    assert r.returncode == 0, r.stdout + r.stderr
    assert "US-M1" in r.stdout, r.stdout
    assert "manifest schema 1" in r.stdout and "migrate-prds" in r.stdout, r.stdout
    r = _cli(d, "lint", "--no-commit")
    assert r.returncode == 0 and "lint: 0 error(s)" in r.stdout, r.stdout + r.stderr
    assert "W10 manifest.json: schema 1" in r.stdout, r.stdout


def test_status_and_lint_say_nothing_about_schema1_once_migrated():
    d = _repo(with_prd=False)
    r = _cli(d, "migrate-prds")
    assert r.returncode == 0, r.stdout + r.stderr
    r = _cli(d, "status")
    assert r.returncode == 0 and "schema 1" not in r.stdout, r.stdout + r.stderr
    assert "PRD: none registered" in r.stdout, r.stdout
    r = _cli(d, "lint", "--no-commit")
    # W10 is the schema-1 warning. W9 belongs to the doubts work (a confirmed
    # doubt not rendered) and may fire on its own, so it is not asserted on.
    assert r.returncode == 0 and "W10" not in r.stdout \
        and "schema 1" not in r.stdout, r.stdout + r.stderr
    r = _cli(d, "next", "--no-commit")
    assert "schema 1" not in r.stdout + r.stderr, r.stdout + r.stderr


def test_renderers_refuse_on_schema1():
    d = _repo()
    env = dict(os.environ, TC_ROOT_OVERRIDE=str(d))
    for script, flag in (("render_sit.py", "--story"), ("render_uat.py", "--flow")):
        r = subprocess.run([sys.executable, str(ROOT / "tools" / script), flag, "X"],
                           cwd=ROOT, capture_output=True, text=True,
                           encoding="utf-8", errors="replace", env=env)
        out = r.stdout + r.stderr
        assert r.returncode != 0 and "migrate-prds" in out, (script, out)
        assert f"{script[:-3]} refused: manifest.json is schema 1" in out, (script, out)
    assert _git(d, "status", "--porcelain").strip() == "", "a refusal writes nothing"


def test_tc_edit_refuses_on_schema1_before_it_writes_and_consumes_its_text_file():
    """`tc edit` makes the check itself, after it has read (and so deleted) the
    one-shot text file the app hands it and before the spec is written."""
    d = _repo()
    src = d / "build/edits/reword.txt"
    src.parent.mkdir(parents=True)
    src.write_text("A new title", encoding="utf-8")
    before = _snap(d)[0]
    r = _cli(d, "tc", "edit", "1.1-AC01-01", "--field", "title",
             "--from", "build/edits/reword.txt", "--by", "tester")
    out = r.stdout + r.stderr
    assert r.returncode != 0, out
    assert "tc edit refused: manifest.json is schema 1" in out, out
    assert "py tools/wiki.py migrate-prds" in out, out
    assert not src.exists(), "the one-shot text file is consumed on a refusal"
    after = _snap(d)[0]
    before.pop("build/edits/reword.txt")
    assert after == before, "nothing else was written"
    assert _git(d, "status", "--porcelain").strip() == ""


def _app_py(d, code):
    """Run `code` with the operator app's modules importable, against `d`."""
    head = ("import sys, json; sys.path[:0] = [r'%s', r'%s']; "
            % (ROOT / "tools", ROOT / "tools" / "app"))
    r = subprocess.run([sys.executable, "-c", head + code], cwd=ROOT,
                       capture_output=True, text=True, encoding="utf-8",
                       errors="replace",
                       env=dict(os.environ, TC_ROOT_OVERRIDE=str(d)))
    assert r.returncode == 0, r.stdout + r.stderr
    return json.loads(r.stdout)


def test_the_app_read_model_reads_a_schema1_project_and_says_so():
    """The refusal is for commands. The operator app's views are in-process
    reads, so a schema-1 project can still be looked at. The state says it is
    schema 1 and carries the migrate text the refusals print, because its PRD
    list is empty there even though a version is adopted and one is staged."""
    d = _repo()
    s = _app_py(d, "import read_models; print(json.dumps(read_models.state()))")
    assert [x["id"] for x in s["stories"]] == ["US-M1"], s["stories"]
    assert s["schema1"] is True, s.get("schema1")
    assert s["prds"] == [], "schema 1 has no registry to list"
    assert s["notice"] == wiki.schema1_message(), s.get("notice")
    assert "py tools/wiki.py migrate-prds" in s["notice"], s["notice"]
    r = _cli(d, "gate", "--story", "US-M1")
    assert s["notice"] in r.stdout + r.stderr, "one wording for both"
    assert _git(d, "status", "--porcelain").strip() == "", "a read writes nothing"


def test_the_app_read_model_has_no_notice_once_migrated():
    d = _repo()
    r = _cli(d, "migrate-prds", "--id", "legacy", "--title", "Legacy PRD")
    assert r.returncode == 0, r.stdout + r.stderr
    s = _app_py(d, "import read_models; print(json.dumps(read_models.state()))")
    assert s["schema1"] is False and s["notice"] is None, (s["schema1"], s["notice"])
    assert [p["id"] for p in s["prds"]] == ["legacy"], s["prds"]


def test_an_app_action_is_refused_on_schema1_with_the_migrate_message():
    """Every action the app runs is a wiki.py subprocess through runner.run,
    so it meets main()'s check like a command typed in a terminal."""
    d = _repo()
    for argv in (["gate", "--story", "US-M1"], ["next", "--json"],
                 ["suite", "compile", "x"]):
        res = _app_py(d, "import runner; print(json.dumps(runner.run(%r)))" % argv)
        out = res["stdout"] + res["stderr"]
        assert res["rc"] == 1, (argv, res)
        assert f"{argv[0]} refused: manifest.json is schema 1" in out, (argv, out)
        assert "py tools/wiki.py migrate-prds" in out, (argv, out)
    for argv in (["status"], ["lint"]):
        res = _app_py(d, "import runner; print(json.dumps(runner.run(%r)))" % argv)
        assert res["rc"] == 0, (argv, res)
    assert _git(d, "status", "--porcelain").strip() == "", "a refusal writes nothing"


def test_a_manifest_with_no_schema_version_key_is_refused_like_schema1():
    d = _repo()
    m = _manifest(d)
    del m["schema_version"]
    (d / "manifest.json").write_text(json.dumps(m, indent=2) + "\n",
                                     encoding="utf-8", newline="\n")
    _commit_as_fixture(d, "manifest without a schema_version key")
    for argv in (["next"], ["gate", "--story", "US-M1"], ["seal"],
                 ["suite", "compile", "x"], ["ingest-prd"]):
        r = _cli(d, *argv, "--no-commit")
        out = r.stdout + r.stderr
        assert r.returncode != 0, (argv, out)
        assert f"{argv[0]} refused: manifest.json is schema 1" in out, (argv, out)
        assert "py tools/wiki.py migrate-prds" in out, (argv, out)
    r = _cli(d, "status")
    assert r.returncode == 0 and "manifest schema 1" in r.stdout, r.stdout + r.stderr
    assert _git(d, "status", "--porcelain").strip() == "", "a refusal writes nothing"


def test_tc_without_edit_prints_its_usage_on_schema1_and_writes_nothing():
    """`tc` is not checked in main(): `tc edit` makes the check itself. Any
    other `tc` word stops at the usage text, before anything is read."""
    d = _repo()
    for argv in (["tc"], ["tc", "list"], ["tc", "render", "1.1-AC01-01"],
                 ["tc", "edit"], ["tc", "edit", "--field", "title"]):
        r = _cli(d, *argv)
        out = r.stdout + r.stderr
        assert r.returncode != 0, (argv, out)
        assert "usage: wiki tc edit <id> --field" in out, (argv, out)
    assert _git(d, "status", "--porcelain").strip() == "", "a usage error writes nothing"


def test_eval_rubric_apply_patch_refuses_on_schema1_and_leaves_the_spec():
    """--apply-patch rewrites a tracked spec, and the forced render it then
    asks for is refused on schema 1: the edit would be stranded in a dirty
    tree, which migrate-prds itself refuses."""
    import yaml
    d = _repo()
    spec = d / "tools/sit_specs/US-M1.yaml"
    spec.parent.mkdir(parents=True)
    spec.write_text(yaml.safe_dump({"story": "/stories/US-M1.md", "test_cases": [
        {"ac": "AC1", "seq": 1, "expected": "1. old"}]}, sort_keys=False),
        encoding="utf-8", newline="\n")
    patch = d / "build/rubric/US-M1-r1-patch.json"
    patch.parent.mkdir(parents=True)
    patch.write_text(json.dumps({"scope": "US-M1", "round": 1, "patches": [
        {"op": "set", "ac": "AC1", "seq": 1, "field": "expected",
         "value": "1. new", "closes": "G1"}]}), encoding="utf-8")
    before = spec.read_bytes()
    r = subprocess.run(
        [sys.executable, str(ROOT / "tools/eval_rubric.py"), "--story", "US-M1",
         "--apply-patch", "build/rubric/US-M1-r1-patch.json"], cwd=ROOT,
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        env=dict(os.environ, TC_ROOT_OVERRIDE=str(d)))
    assert r.returncode != 0, r.stdout + r.stderr
    assert "eval_rubric refused: manifest.json is schema 1" in r.stderr, r.stderr
    assert "py tools/wiki.py migrate-prds" in r.stderr, r.stderr
    assert spec.read_bytes() == before, "the spec is untouched"


def test_a_root_with_no_manifest_is_not_refused():
    d = Path(tempfile.mkdtemp(prefix="migrate-prds-empty-")).resolve()
    _ROOTS.append(d)
    r = _cli(d, "next", "--no-commit")
    assert "schema 1" not in r.stdout + r.stderr, r.stdout + r.stderr



if __name__ == "__main__":
    try:
        for name, fn in sorted(globals().items()):
            if name.startswith("test_") and callable(fn):
                fn()
                print(f"[PASS] {name}")
        print("test_wiki_migrate_prds OK")
    finally:
        for _d in _ROOTS:
            _rm(_d)
