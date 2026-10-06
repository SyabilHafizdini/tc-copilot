#!/usr/bin/env python3
"""Two PRDs in one project, driven through the real CLI
(run: py tools/test_wiki_multi_prd.py). No pytest - matches tools/smoke.py.

Every test builds its own scratch root under build/_mprd_<name>/ from the
fixture in tools/fixtures/multi_prd/, so nothing here touches the real wiki."""
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
from testkit import add_story, cli, multi_prd_root, put_prd
import wiki
from wiki import read_concept

APP, PAY = "rental-application", "rental-payment"
_ROOTS = []


def _root(name):
    r = multi_prd_root(f"mprd_{name}")
    _ROOTS.append(r)
    return r


def _manifest(root):
    return json.loads((root / "manifest.json").read_text(encoding="utf-8"))


def _ingest(root, prd_id, version, title=None, flag=True):
    put_prd(root, prd_id, version, f"{prd_id}-v{version}.md")
    argv = ["ingest-prd"] + (["--prd", prd_id] if flag else [])
    if title:
        argv += ["--title", title]
    return cli(root, *argv)


def _ok(r):
    assert r.returncode == 0, r.stdout + r.stderr
    return r.stdout + r.stderr


def _both_v1(root):
    _ok(_ingest(root, APP, 1, "Rental application"))
    _ok(_ingest(root, PAY, 1, "Rental payment"))


def test_first_ingest_of_a_new_prd_registers_and_adopts_it():
    root = _root("first")
    out = _ok(_ingest(root, APP, 1, "Rental application"))
    assert "PRD rental-application v1" in out, out
    m = _manifest(root)
    assert m["schema_version"] == 2, m
    assert "adopted_prd_version" not in m and "staged_prd_version" not in m, m
    assert m["prds"] == {APP: {"title": "Rental application", "adopted_version": 1,
                               "staged_version": None}}, m["prds"]
    fm, body = read_concept(root / f"sources/prd/{APP}/1-1.md")
    assert fm["id"] == f"prd#{APP}/1-1", fm
    assert fm["prd"] == APP and fm["prd_version"] == 1, fm
    assert fm["source_file"] == f"/inputs/prd/{APP}/v1/{APP}-v1.md", fm
    assert "at least 21 years old" in body, body
    assert m["sources"][f"prd#{APP}/1-1"] == {
        "content_hash": fm["content_hash"], "prd_version": 1, "prd": APP}, m["sources"]
    assert not list((root / "sources/prd").glob("*.md")), "no flat section files"


def test_a_new_id_without_a_title_is_refused():
    root = _root("notitle")
    r = _ingest(root, APP, 1)
    out = r.stdout + r.stderr
    assert r.returncode != 0, out
    assert "--title" in out and APP in out, out
    assert not (root / "sources").exists(), sorted(root.rglob("*"))
    assert not (root / "manifest.json").exists(), "a refusal writes nothing"


def test_a_malformed_id_is_refused():
    root = _root("badid")
    r = cli(root, "ingest-prd", "--prd", "Rental_App", "--title", "x")
    assert r.returncode != 0 and "lowercase-hyphen" in r.stdout + r.stderr, r


def test_one_registered_prd_needs_no_flag_and_a_newer_version_stages():
    root = _root("oneflagless")
    _ok(_ingest(root, APP, 1, "Rental application"))
    out = _ok(_ingest(root, APP, 2, flag=False))
    assert "staged PRD rental-application v2" in out and "CR-001" in out, out
    m = _manifest(root)
    assert m["prds"][APP] == {"title": "Rental application", "adopted_version": 1,
                              "staged_version": 2}, m["prds"]
    staged = json.loads((root / f"staging/{APP}/prd-v2.json").read_text(encoding="utf-8"))
    assert staged["prd"] == APP and staged["version"] == 2, staged
    cfm, _b = read_concept(root / f"changereports/{APP}/CR-001.md")
    assert cfm["prd"] == APP and cfm["status"] == "pending", cfm
    assert (cfm["from_version"], cfm["to_version"]) == (1, 2), cfm
    fm, body = read_concept(root / f"sources/prd/{APP}/1-1.md")
    assert fm["prd_version"] == 1 and "21 years" in body, "adopted content untouched"


def test_two_prds_without_the_flag_is_refused_and_lists_both():
    root = _root("twoflagless")
    _both_v1(root)
    put_prd(root, PAY, 2, f"{PAY}-v2.md")
    r = cli(root, "ingest-prd")
    out = r.stdout + r.stderr
    assert r.returncode != 0, out
    assert APP in out and PAY in out and "--prd" in out, out
    assert _manifest(root)["prds"][PAY]["staged_version"] is None, "nothing staged"


def test_same_slug_in_two_prds_does_not_collide():
    root = _root("slug")
    _both_v1(root)
    a, abody = read_concept(root / f"sources/prd/{APP}/1-1.md")
    p, pbody = read_concept(root / f"sources/prd/{PAY}/1-1.md")
    assert "21 years" in abody and "42 dollars" in pbody, (abody, pbody)
    assert a["id"] != p["id"], (a["id"], p["id"])
    m = _manifest(root)
    assert len([k for k in m["sources"] if k.startswith("prd#")]) == 4, sorted(m["sources"])


def test_a_second_version_of_one_prd_stages_and_reports_only_for_it():
    root = _root("stageone")
    _both_v1(root)
    add_story(root, "US-MP-APP", [f"/sources/prd/{APP}/1-1.md"])
    add_story(root, "US-MP-PAY", [f"/sources/prd/{PAY}/1-1.md"])
    add_story(root, "US-MP-BOTH", [f"/sources/prd/{APP}/1-1.md",
                                   f"/sources/prd/{PAY}/1-1.md"])
    out = _ok(_ingest(root, PAY, 2))
    assert "staged PRD rental-payment v2" in out, out
    m = _manifest(root)
    assert m["prds"][PAY] == {"title": "Rental payment", "adopted_version": 1,
                              "staged_version": 2}, m["prds"]
    assert m["prds"][APP] == {"title": "Rental application", "adopted_version": 1,
                              "staged_version": None}, m["prds"]
    assert not (root / f"staging/{APP}").exists()
    assert not (root / f"changereports/{APP}").exists()
    cfm, cbody = read_concept(root / f"changereports/{PAY}/CR-001.md")
    assert cfm["title"] == "CR-001: PRD rental-payment v1 -> v2", cfm
    line = [ln for ln in cbody.splitlines() if ln.startswith("- affected stories")][0]
    assert "US-MP-PAY" in line and "US-MP-BOTH" in line, line
    assert "US-MP-APP" not in line, "a story citing only the other PRD is not affected"


def test_change_report_numbers_are_unique_across_prds():
    root = _root("crnum")
    _both_v1(root)
    _ok(_ingest(root, PAY, 2))
    _ok(_ingest(root, APP, 2))
    assert (root / f"changereports/{PAY}/CR-001.md").exists()
    assert (root / f"changereports/{APP}/CR-002.md").exists()


def test_a_version_lower_than_the_adopted_one_is_refused():
    root = _root("older")
    put_prd(root, APP, 2, f"{APP}-v2.md")
    _ok(cli(root, "ingest-prd", "--prd", APP, "--title", "Rental application"))
    shutil.rmtree(root / f"inputs/prd/{APP}/v2")
    put_prd(root, APP, 1, f"{APP}-v1.md")
    r = cli(root, "ingest-prd")
    out = r.stdout + r.stderr
    assert r.returncode != 0 and "v2 is already adopted" in out, out
    assert not (root / "staging").exists(), sorted(root.rglob("*"))


def test_index_lists_each_prd_directory():
    root = _root("index")
    _both_v1(root)
    _ok(cli(root, "index"))
    top = (root / "sources/prd/index.md").read_text(encoding="utf-8")
    assert f"[{APP}/](/sources/prd/{APP}/index.md)" in top, top
    sub = (root / f"sources/prd/{PAY}/index.md").read_text(encoding="utf-8")
    assert "1.1 Fees" in sub and "1.2 Refunds" in sub, sub


def _status(root, sid):
    return read_concept(root / f"stories/{sid}.md")[0]["status"]


def _staged_payment(name):
    """Both PRDs at v1, four aligned stories, rental-payment v2 staged as CR-001."""
    root = _root(name)
    _both_v1(root)
    add_story(root, "US-MP-APP", [f"/sources/prd/{APP}/1-1.md"])
    add_story(root, "US-MP-PAY", [f"/sources/prd/{PAY}/1-1.md"])
    add_story(root, "US-MP-PAY2", [f"/sources/prd/{PAY}/1-2.md"])
    add_story(root, "US-MP-BOTH", [f"/sources/prd/{APP}/1-1.md",
                                   f"/sources/prd/{PAY}/1-1.md"])
    _ok(cli(root, "manifest"))
    _ok(_ingest(root, PAY, 2))
    return root


def test_approving_one_prd_flags_only_stories_citing_its_changed_sections():
    root = _staged_payment("approve")
    app_before = (root / f"sources/prd/{APP}/1-1.md").read_bytes()
    out = _ok(cli(root, "approve-cr", "CR-001", "--by", "tester", "--prd", PAY))
    assert "CR-001 approved by tester: adopted rental-payment v2" in out, out
    m = _manifest(root)
    assert m["prds"][PAY] == {"title": "Rental payment", "adopted_version": 2,
                              "staged_version": None}, m["prds"]
    assert m["prds"][APP]["adopted_version"] == 1, m["prds"]
    fm, body = read_concept(root / f"sources/prd/{PAY}/1-1.md")
    assert fm["prd_version"] == 2 and fm["prd"] == PAY, fm
    assert "50 dollars" in body and "# Superseded (v1)" in body, body
    assert (root / f"sources/prd/{APP}/1-1.md").read_bytes() == app_before, \
        "the other PRD's section with the same slug must not be touched"
    assert _status(root, "US-MP-PAY") == "needs-review"
    assert _status(root, "US-MP-BOTH") == "needs-review"
    assert _status(root, "US-MP-APP") == "aligned", "cites only the other PRD"
    assert _status(root, "US-MP-PAY2") == "aligned", "cites an unchanged section"
    cfm, _b = read_concept(root / f"changereports/{PAY}/CR-001.md")
    assert cfm["status"] == "approved" and cfm["asserted_by"] == "tester", cfm


def test_approve_without_the_flag_is_refused_with_two_prds():
    root = _staged_payment("approvenoflag")
    r = cli(root, "approve-cr", "CR-001", "--by", "tester")
    out = r.stdout + r.stderr
    assert r.returncode != 0 and APP in out and PAY in out, out
    assert _manifest(root)["prds"][PAY]["adopted_version"] == 1, "nothing adopted"


def test_approve_with_the_wrong_prd_names_the_right_one():
    root = _staged_payment("approvewrong")
    r = cli(root, "approve-cr", "CR-001", "--by", "tester", "--prd", APP)
    out = r.stdout + r.stderr
    assert r.returncode != 0, out
    assert "CR-001 belongs to PRD rental-payment" in out and f"--prd {PAY}" in out, out


def test_reject_keeps_the_adopted_version_of_that_prd():
    root = _staged_payment("reject")
    out = _ok(cli(root, "reject-cr", "CR-001", "--by", "tester", "--prd", PAY))
    assert "CR-001 rejected by tester" in out, out
    m = _manifest(root)
    assert m["prds"][PAY]["adopted_version"] == 1, m["prds"]
    cfm, _b = read_concept(root / f"changereports/{PAY}/CR-001.md")
    assert cfm["status"] == "rejected", cfm
    assert _status(root, "US-MP-PAY") == "aligned", "a rejection flags nothing"


def test_diff_is_per_prd():
    root = _staged_payment("diff")
    out = _ok(cli(root, "diff", "--prd", PAY))
    assert "PRD rental-payment v1 (adopted) vs v2 (staged):" in out, out
    assert "modified  1.1 Fees" in out and "unchanged 1" in out, out
    r = cli(root, "diff", "--prd", APP)
    assert r.returncode != 0 and "no staged version for PRD rental-application" in \
        r.stdout + r.stderr, r
    r = cli(root, "diff", "--prd")
    out = r.stdout + r.stderr
    assert r.returncode != 0 and APP in out and PAY in out, out
    assert "Traceback" not in out, out


def test_one_prd_needs_no_flag_for_diff_or_approve():
    root = _root("oneapprove")
    _ok(_ingest(root, APP, 1, "Rental application"))
    add_story(root, "US-MP-APP", [f"/sources/prd/{APP}/1-1.md"])
    _ok(_ingest(root, APP, 2, flag=False))
    assert "modified  1.1 Eligibility" in _ok(cli(root, "diff", "--prd"))
    _ok(cli(root, "approve-cr", "CR-001", "--by", "tester"))
    assert _manifest(root)["prds"][APP]["adopted_version"] == 2
    assert _status(root, "US-MP-APP") == "needs-review"


def _snapshot(root):
    """Every file under the root and its bytes: a refusal must leave this equal."""
    return {p.relative_to(root).as_posix(): p.read_bytes()
            for p in sorted(root.rglob("*")) if p.is_file()}


def _dirs(root):
    return sorted(p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_dir())


def _put_text(root, prd_id, version, name, text):
    dest = root / f"inputs/prd/{prd_id}/v{version}" / name
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(text, encoding="utf-8", newline="\n")
    return dest


def _put_docx(root, prd_id, version, name, headings):
    from docx import Document
    d = Document()
    for h in headings:
        d.add_heading(h, level=1)
        d.add_paragraph(f"Body of {h}.")
    dest = root / f"inputs/prd/{prd_id}/v{version}" / name
    dest.parent.mkdir(parents=True, exist_ok=True)
    d.save(str(dest))
    return dest


def _refused(r, *needles):
    out = r.stdout + r.stderr
    assert r.returncode != 0, out
    for n in needles:
        assert n in out, (n, out)
    assert "Traceback" not in out, out
    return out


def test_rerunning_ingest_on_a_staged_version_changes_nothing():
    root = _root("rerun")
    _ok(_ingest(root, APP, 1, "Rental application"))
    _ok(_ingest(root, APP, 2))
    before, dirs = _snapshot(root), _dirs(root)
    out = _ok(cli(root, "ingest-prd", "--prd", APP))
    assert "already staged" in out and "CR-001" in out, out
    assert _snapshot(root) == before and _dirs(root) == dirs
    assert [p.name for p in (root / f"changereports/{APP}").glob("*.md")] == ["CR-001.md"]


def test_rerunning_ingest_with_different_content_is_refused_naming_the_report():
    root = _root("rerundiff")
    _ok(_ingest(root, APP, 1, "Rental application"))
    _ok(_ingest(root, APP, 2))
    doc = root / f"inputs/prd/{APP}/v2/{APP}-v2.md"
    doc.write_text(doc.read_text(encoding="utf-8").replace("18", "25"),
                   encoding="utf-8", newline="\n")
    before = _snapshot(root)
    _refused(cli(root, "ingest-prd", "--prd", APP), "CR-001", "pending")
    assert _snapshot(root) == before


def test_a_section_named_index_or_log_is_refused_on_the_adopt_path():
    for heading in ("Index", "Log"):
        root = _root(f"reserved_{heading.lower()}")
        _put_docx(root, APP, 1, "doc.docx", ["Scope", heading])
        before, dirs = _snapshot(root), _dirs(root)
        _refused(cli(root, "ingest-prd", "--prd", APP, "--title", "Rental application"),
                 heading, "reserved")
        assert _snapshot(root) == before and _dirs(root) == dirs, "a refusal writes nothing"


def test_a_section_named_index_is_refused_on_the_stage_path():
    root = _root("reservedstage")
    _ok(_ingest(root, APP, 1, "Rental application"))
    _put_docx(root, APP, 2, "doc.docx", ["Scope", "Index"])
    before, dirs = _snapshot(root), _dirs(root)
    _refused(cli(root, "ingest-prd", "--prd", APP), "Index", "reserved")
    assert _snapshot(root) == before and _dirs(root) == dirs


def test_an_empty_document_is_refused_before_anything_is_touched():
    root = _root("empty")
    _put_text(root, APP, 1, "doc.md", "\n\n")
    before, dirs = _snapshot(root), _dirs(root)
    _refused(cli(root, "ingest-prd", "--prd", APP, "--title", "Rental application"),
             "no sections")
    assert _snapshot(root) == before and _dirs(root) == dirs
    assert not (root / "manifest.json").exists() and not (root / "sources").exists()


def test_an_empty_newer_version_is_refused_on_the_stage_path():
    root = _root("emptystage")
    _ok(_ingest(root, APP, 1, "Rental application"))
    _put_text(root, APP, 2, "doc.md", "\n")
    before, dirs = _snapshot(root), _dirs(root)
    _refused(cli(root, "ingest-prd", "--prd", APP), "no sections")
    assert _snapshot(root) == before and _dirs(root) == dirs


def test_only_canonical_version_directories_count():
    root = _root("vdirs")
    _put_text(root, APP, 0, "doc.md", "1.1 Scope\nSome text here.\n")
    before, dirs = _snapshot(root), _dirs(root)
    _refused(cli(root, "ingest-prd", "--prd", APP, "--title", "Rental application"), "vN")
    assert _snapshot(root) == before and _dirs(root) == dirs, "v0 is not a version"
    _put_text(root, APP, "01", "doc.md", "1.1 Scope\nSome text here.\n")
    before, dirs = _snapshot(root), _dirs(root)
    _refused(cli(root, "ingest-prd", "--prd", APP, "--title", "Rental application"), "vN")
    assert _snapshot(root) == before and _dirs(root) == dirs, "v01 is not a version"
    put_prd(root, APP, 1, f"{APP}-v1.md")
    out = _ok(cli(root, "ingest-prd", "--prd", APP, "--title", "Rental application"))
    assert "PRD rental-application v1" in out, out


def test_two_documents_in_one_version_directory_are_refused_listing_both():
    root = _root("twodocs")
    put_prd(root, APP, 1, f"{APP}-v1.md")
    _put_text(root, APP, 1, "other.md", "1.1 Other\nText.\n")
    before, dirs = _snapshot(root), _dirs(root)
    _refused(cli(root, "ingest-prd", "--prd", APP, "--title", "Rental application"),
             f"{APP}-v1.md", "other.md")
    assert _snapshot(root) == before and _dirs(root) == dirs


def _pay_v3_over_pending_v2(name):
    """rental-payment v2 staged (CR-001), then a different v3 staged (CR-002)."""
    root = _staged_payment(name)
    _put_text(root, PAY, 3, "doc.md",
              "1.1 Fees\nThe application fee is 60 dollars.\n\n"
              "1.2 Refunds\nA rejected application is refunded in full.\n")
    _ok(cli(root, "ingest-prd", "--prd", PAY))
    return root


def test_an_older_report_cannot_be_approved_over_a_newer_staged_version():
    root = _pay_v3_over_pending_v2("superseded")
    before = _snapshot(root)
    r = cli(root, "approve-cr", "CR-001", "--by", "tester", "--prd", PAY)
    _refused(r, "CR-001", "CR-002", "staged is v3")
    assert _snapshot(root) == before, "a refusal writes nothing"
    _ok(cli(root, "approve-cr", "CR-002", "--by", "tester", "--prd", PAY))
    assert _manifest(root)["prds"][PAY]["adopted_version"] == 3
    before = _snapshot(root)
    _refused(cli(root, "approve-cr", "CR-001", "--by", "tester", "--prd", PAY),
             "CR-001", "v3 is already adopted", "superseded")
    assert _snapshot(root) == before
    assert _manifest(root)["prds"][PAY]["adopted_version"] == 3


def test_staging_a_newer_version_says_the_older_pending_report_is_superseded():
    root = _staged_payment("supersedenote")
    _put_text(root, PAY, 3, "doc.md", "1.1 Fees\nThe fee is 60 dollars.\n")
    out = _ok(cli(root, "ingest-prd", "--prd", PAY))
    assert "CR-001" in out and "superseded" in out and "can no longer be approved" in out, out
    m = _manifest(root)
    assert m["prds"][PAY]["staged_version"] == 3, m["prds"]
    out = _ok(cli(root, "diff", "--prd", PAY))
    assert "v3 (staged)" in out, out


def test_a_pending_report_for_a_staged_version_is_never_duplicated():
    root = _pay_v3_over_pending_v2("nodupe")
    before = _snapshot(root)
    out = _ok(cli(root, "ingest-prd", "--prd", PAY))
    assert "already staged as CR-002" in out, out
    assert _snapshot(root) == before
    pend = [p.name for p in (root / f"changereports/{PAY}").glob("*.md")
            if read_concept(p)[0]["status"] == "pending"]
    assert sorted(pend) == ["CR-001.md", "CR-002.md"], pend


def test_a_pending_report_is_found_even_when_the_registry_lost_the_staged_version():
    root = _pay_v3_over_pending_v2("lostreg")
    m = _manifest(root)
    m["prds"][PAY]["staged_version"] = None
    (root / "manifest.json").write_text(json.dumps(m, indent=1), encoding="utf-8")
    before = _snapshot(root)
    out = _ok(cli(root, "ingest-prd", "--prd", PAY))
    assert "already staged as CR-002" in out, out
    assert _snapshot(root) == before


def test_a_story_citing_a_removed_section_is_flagged_by_the_cascade():
    root = _root("removed")
    _both_v1(root)
    add_story(root, "US-MP-APP", [f"/sources/prd/{APP}/1-1.md"])
    add_story(root, "US-MP-APP2", [f"/sources/prd/{APP}/1-2.md"])
    add_story(root, "US-MP-PAY", [f"/sources/prd/{PAY}/1-1.md"])
    add_story(root, "US-MP-PAY2", [f"/sources/prd/{PAY}/1-2.md"])
    _put_text(root, PAY, 2, "doc.md", "1.1 Fees\nThe application fee is 50 dollars.\n")
    _ok(cli(root, "manifest"))
    _ok(cli(root, "ingest-prd", "--prd", PAY))
    app2 = (root / "stories/US-MP-APP2.md").read_bytes()
    _ok(cli(root, "approve-cr", "CR-001", "--by", "tester", "--prd", PAY))
    fm, _b = read_concept(root / "stories/US-MP-PAY2.md")
    assert fm["status"] == "needs-review", fm["status"]
    cause = fm["review_because"][0]["cause"]
    assert f"prd#{PAY}/1-2" in cause and "removed in v2" in cause, cause
    assert (root / "stories/US-MP-APP2.md").read_bytes() == app2, \
        "the same slug in the other PRD is untouched"
    assert _status(root, "US-MP-APP") == "aligned"


def _removed_root(name):
    """Both PRDs at v1; rental-payment v2 (CR-001) drops 1.2 and is approved. Two
    stories cite the removed section's slug in each PRD, a third cites 1.1."""
    root = _root(name)
    _both_v1(root)
    add_story(root, "US-MP-APP2", [f"/sources/prd/{APP}/1-2.md"])
    add_story(root, "US-MP-PAY2", [f"/sources/prd/{PAY}/1-2.md"])
    _put_text(root, PAY, 2, "doc.md", "1.1 Fees\nThe application fee is 50 dollars.\n")
    _ok(cli(root, "manifest"))
    _ok(cli(root, "ingest-prd", "--prd", PAY))
    _ok(cli(root, "approve-cr", "CR-001", "--by", "tester", "--prd", PAY))
    return root


def _reassert(root, sid, ref):
    """What a human `wiki assert story` does to the pins, in a scratch root:
    re-pin from the section as it now is."""
    add_story(root, sid, [ref])


def test_a_removal_flags_once_and_survives_other_prds_approvals():
    root = _removed_root("removedonce")
    fm, _b = read_concept(root / "stories/US-MP-PAY2.md")
    assert fm["status"] == "needs-review" and len(fm["review_because"]) == 1, fm
    _reassert(root, "US-MP-PAY2", f"/sources/prd/{PAY}/1-2.md")
    story = (root / "stories/US-MP-PAY2.md").read_bytes()
    _ok(_ingest(root, APP, 2))
    out = _ok(cli(root, "approve-cr", "CR-002", "--by", "tester", "--prd", APP))
    assert "US-MP-PAY2" not in out, out
    assert (root / "stories/US-MP-PAY2.md").read_bytes() == story, \
        "an unrelated PRD's approval touched the re-asserted story"


def test_cascade_answers_the_same_before_and_after_a_manifest_rebuild():
    root = _removed_root("removedrebuild")
    _reassert(root, "US-MP-PAY2", f"/sources/prd/{PAY}/1-2.md")
    story = (root / "stories/US-MP-PAY2.md").read_bytes()
    first = _ok(cli(root, "cascade"))
    assert "cascade: 0 item(s) flagged" in first, first
    _ok(cli(root, "manifest"))
    m = _manifest(root)
    assert m["sources"][f"prd#{PAY}/1-2"].get("removed_in") == 2, m["sources"]
    second = _ok(cli(root, "cascade"))
    assert "cascade: 0 item(s) flagged" in second, second
    assert (root / "stories/US-MP-PAY2.md").read_bytes() == story


def test_a_story_pinned_before_the_removal_is_flagged_once_across_rebuilds():
    root = _root("removedpinned")
    _both_v1(root)
    add_story(root, "US-MP-PAY2", [f"/sources/prd/{PAY}/1-2.md"])
    _put_text(root, PAY, 2, "doc.md", "1.1 Fees\nThe application fee is 50 dollars.\n")
    _ok(cli(root, "manifest"))
    _ok(cli(root, "ingest-prd", "--prd", PAY))
    out = _ok(cli(root, "approve-cr", "CR-001", "--by", "tester", "--prd", PAY))
    assert "story US-MP-PAY2 -> needs-review" in out, out
    _ok(cli(root, "manifest"))
    for _i in range(2):
        assert "cascade: 0 item(s) flagged" in _ok(cli(root, "cascade"))
    fm, _b = read_concept(root / "stories/US-MP-PAY2.md")
    assert len(fm["review_because"]) == 1, fm["review_because"]


def test_restoring_a_removed_section_clears_the_removed_state():
    root = _removed_root("restored")
    _reassert(root, "US-MP-PAY2", f"/sources/prd/{PAY}/1-2.md")
    _put_text(root, PAY, 3, "doc.md",
              "1.1 Fees\nThe application fee is 50 dollars.\n\n"
              "1.2 Refunds\nA rejected application is refunded in full.\n")
    out = _ok(cli(root, "ingest-prd", "--prd", PAY))
    assert "v3" in out, out
    out = _ok(cli(root, "approve-cr", "CR-002", "--by", "tester", "--prd", PAY))
    fm, body = read_concept(root / f"sources/prd/{PAY}/1-2.md")
    assert "removed_in" not in fm, fm
    assert "removed_in" not in _manifest(root)["sources"][f"prd#{PAY}/1-2"]
    story, _b = read_concept(root / "stories/US-MP-PAY2.md")
    assert not any("removed" in c["cause"] for c in story.get("review_because", [])), story
    # the removed-state pin no longer matches: the ordinary comparison flags it
    assert story["status"] == "needs-review", story["status"]
    again = _ok(cli(root, "cascade"))
    assert "cascade: 0 item(s) flagged" in again, again


def test_a_superseded_report_hint_never_says_vnone_or_suggests_ingest():
    root = _pay_v3_over_pending_v2("hintnone")
    _ok(cli(root, "approve-cr", "CR-002", "--by", "tester", "--prd", PAY))
    before = _snapshot(root)
    out = _refused(cli(root, "approve-cr", "CR-001", "--by", "tester", "--prd", PAY),
                   "CR-001", "adopted", "reject")
    assert "vNone" not in out and "ingest-prd" not in out, out
    assert _snapshot(root) == before
    out = _ok(cli(root, "reject-cr", "CR-001", "--by", "tester", "--prd", PAY))
    assert "adopted stays v3" in out and "staged v2" not in out, out


def test_duplicate_headings_are_refused_on_the_stage_path():
    root = _root("dupstage")
    _ok(_ingest(root, APP, 1, "Rental application"))
    _put_text(root, APP, 2, "doc.md",
              "1.1 Eligibility\nAdults only.\n\n1.3 Extra\nOne.\n\n1.3 More\nTwo.\n")
    before, dirs = _snapshot(root), _dirs(root)
    _refused(cli(root, "ingest-prd", "--prd", APP), "1.3 Extra", "1.3 More")
    assert _snapshot(root) == before and _dirs(root) == dirs


def test_a_rejected_version_is_not_resubmitted_unchanged():
    root = _staged_payment("rejectrerun")
    _ok(cli(root, "reject-cr", "CR-001", "--by", "tester", "--prd", PAY))
    before = _snapshot(root)
    out = _ok(cli(root, "ingest-prd", "--prd", PAY))
    assert "rejected in CR-001" in out and "nothing changed" in out, out
    assert _snapshot(root) == before, "no fresh pending report"
    doc = root / f"inputs/prd/{PAY}/v2/{PAY}-v2.md"
    doc.write_text(doc.read_text(encoding="utf-8").replace("50", "55"),
                   encoding="utf-8", newline="\n")
    out = _ok(cli(root, "ingest-prd", "--prd", PAY))
    assert "CR-001" in out and "rejected" in out and "CR-002" in out, out
    assert read_concept(root / f"changereports/{PAY}/CR-002.md")[0]["status"] == "pending"


def test_next_banner_follows_the_report_that_can_be_acted_on():
    sys.path.insert(0, str(ROOT / "tools"))
    import wiki_next
    root = _pay_v3_over_pending_v2("banner")
    env = {"TC_ROOT_OVERRIDE": str(root)}
    import os
    import subprocess
    def banner():
        r = subprocess.run([sys.executable, str(ROOT / "tools/wiki.py"), "next", "--json"],
                           cwd=ROOT, capture_output=True, text=True, encoding="utf-8",
                           env=dict(os.environ, **env))
        assert r.returncode == 0, r.stdout + r.stderr
        return json.loads(r.stdout)["banners"][0][key]
    key = "state"
    state = banner()
    assert "CR-002" in state and "CR-001" in state and "superseded" in state, state
    _ok(cli(root, "reject-cr", "CR-002", "--by", "tester", "--prd", PAY))
    _ok(cli(root, "reject-cr", "CR-001", "--by", "tester", "--prd", PAY))
    state = banner()
    assert "rejected in CR-002" in state and "corrected document" in state, state
    assert "approve" not in state, state
    # the directory already holds the rejected document: it is REPLACED
    key = "command"
    command = banner()
    assert f"after replacing the document under inputs/prd/{PAY}/v3/" in command, \
        command
    assert "after placing" not in command, command


def test_by_and_report_id_are_validated_and_nothing_is_written():
    root = _staged_payment("validate")
    before = _snapshot(root)
    _refused(cli(root, "reject-cr", "CR-001", "--by", "--prd", PAY), "--by")
    _refused(cli(root, "reject-cr", "CR-001", "--by"), "--by")
    _refused(cli(root, "approve-cr", "../../stories/US-MP-PAY", "--by", "t", "--prd", PAY),
             "CR-NNN")
    assert _snapshot(root) == before


def test_a_missing_staging_file_is_a_refusal_not_a_traceback():
    root = _staged_payment("nostaging")
    (root / f"staging/{PAY}/prd-v2.json").unlink()
    before = _snapshot(root)
    _refused(cli(root, "approve-cr", "CR-001", "--by", "t", "--prd", PAY), "prd-v2.json")
    _refused(cli(root, "diff", "--prd", PAY), "prd-v2.json")
    assert _snapshot(root) == before


def test_a_wrong_prd_adopts_nothing_and_a_reject_leaves_sources_alone():
    root = _staged_payment("strict")
    before = _snapshot(root)
    _refused(cli(root, "approve-cr", "CR-001", "--by", "tester", "--prd", APP),
             "CR-001 belongs to PRD rental-payment")
    assert _snapshot(root) == before, "registry, sections, reports all untouched"
    src = {k: v for k, v in before.items() if k.startswith("sources/")}
    _ok(cli(root, "reject-cr", "CR-001", "--by", "tester", "--prd", PAY))
    after = _snapshot(root)
    assert {k: v for k, v in after.items() if k.startswith("sources/")} == src
    assert f"staging/{PAY}/prd-v2.json" in after
    assert _manifest(root)["prds"][PAY]["staged_version"] == 2


def test_testkit_refuses_roots_and_names_that_could_reach_the_tracked_wiki():
    import testkit

    def refused(fn, *a):
        try:
            fn(*a)
        except ValueError as e:
            return str(e)
        raise AssertionError(f"{fn.__name__}{a} was not refused")

    repo = Path(testkit.__file__).resolve().parent.parent
    assert testkit.REPO_ROOT == repo, "derived from the file, not from wiki.ROOT"
    for bad in ("", ".", "build/_x", repo, repo / "tools" / ".."):
        refused(testkit.cli, bad, "status")
    for bad in ("a/b", "a\\b", "..", "", "/abs"):
        refused(testkit.scratch_root, bad)
    assert not (repo / "build" / "_a").exists(), "a refused name creates nothing"
    r = testkit.scratch_root("guard_ok")
    try:
        assert r == repo / "build" / "_guard_ok" and r.is_dir()
        assert testkit.cli(r, "status").returncode == 0
    finally:
        shutil.rmtree(r, ignore_errors=True)


def _real_assert(root, sid, n):
    """The real `wiki assert story` with an emitted-style card, inside the
    scratch root only (the card is the human's recorded answer)."""
    card = root / f"build/cards/{sid}-{n}.json"
    card.parent.mkdir(parents=True, exist_ok=True)
    card.write_text(json.dumps({"story": f"stories/{sid}", "human_response": None}),
                    encoding="utf-8", newline="\n")
    out = _ok(cli(root, "assert", "story", sid, "--by", "tester", "--card", str(card)))
    assert f"asserted story {sid} by tester" in out, out


def test_a_story_asserted_by_the_real_command_survives_a_removal_and_other_prds():
    ref =f"/sources/prd/{PAY}/1-2.md"
    key = f"prd#{PAY}/1-2"
    root = _root("realassert")
    _both_v1(root)
    add_story(root, "US-MP-REAL", [ref], status="draft")
    _ok(cli(root, "manifest"))
    _real_assert(root, "US-MP-REAL", 1)
    fm, _b = read_concept(root / "stories/US-MP-REAL.md")
    assert fm["status"] == "aligned" and fm["asserted_by"] == "tester", fm
    assert fm["source_pins"] == {key: wiki.source_pin(_manifest(root)["sources"][key])}
    _put_text(root, PAY, 2, "doc.md", "1.1 Fees\nThe application fee is 50 dollars.\n")
    _ok(cli(root, "ingest-prd", "--prd", PAY))
    _ok(cli(root, "approve-cr", "CR-001", "--by", "tester", "--prd", PAY))
    fm, _b = read_concept(root / "stories/US-MP-REAL.md")
    assert fm["status"] == "needs-review", fm["status"]
    assert len(fm["review_because"]) == 1, fm
    assert f"{key} removed in v2" in fm["review_because"][0]["cause"], fm
    _ok(cli(root, "manifest"))
    entry = _manifest(root)["sources"][key]
    assert entry.get("removed_in") == 2, entry
    _real_assert(root, "US-MP-REAL", 2)
    fm, _b = read_concept(root / "stories/US-MP-REAL.md")
    assert fm["status"] == "aligned", fm["status"]
    assert fm["source_pins"] == {key: wiki.source_pin(entry)}, fm["source_pins"]
    assert "@removed-v2" in fm["source_pins"][key], fm["source_pins"]
    # Pinned behaviour: the real assert re-pins and re-aligns but leaves the
    # old review_because entry in the file as history; it does not clear it.
    assert len(fm["review_because"]) == 1 and \
        "removed in v2" in fm["review_because"][0]["cause"], fm["review_because"]
    story = (root / "stories/US-MP-REAL.md").read_bytes()
    _ok(_ingest(root, APP, 2))
    _ok(cli(root, "approve-cr", "CR-002", "--by", "tester", "--prd", APP))
    out = _ok(cli(root, "cascade"))
    assert "cascade: 0 item(s) flagged" in out and "US-MP-REAL" not in out, out
    assert (root / "stories/US-MP-REAL.md").read_bytes() == story, \
        "the other PRD's approval and the cascade touched the re-asserted story"


def test_the_module_docstring_documents_the_triage_prd_flags():
    doc = wiki.__doc__
    block = doc[doc.index("  triage"):doc.index("  index ")]
    for needle in ("--prd <id>", '--prd-title "<title>"', "--prd-version N",
                   "--card <card>", "inputs/{prd/<id>/vN,figma,decks}/",
                   "no PRD or", "occupied PRD version"):
        assert needle in block, (needle, block)


def test_dashboard_feed_carries_both_prds_and_the_report_of_the_staged_one():
    root = _staged_payment("dashboard")
    _ok(cli(root, "dashboard"))
    dash = json.loads((root / "build/status/dashboard.json").read_text(encoding="utf-8"))
    assert "prd" not in dash, sorted(dash)
    assert dash["prds"] == [
        {"id": APP, "title": "Rental application", "adopted": 1, "staged": None},
        {"id": PAY, "title": "Rental payment", "adopted": 1, "staged": 2}], dash["prds"]
    assert dash["change_reports"] == [
        {"id": "CR-001", "status": "pending", "prd": PAY, "from": 1, "to": 2}], \
        dash["change_reports"]
    assert dash["totals"]["prd_sections"] == 4, dash["totals"]
    # the static page never prints `vnull` for a PRD with nothing adopted
    html = (root / "build/status/dashboard.html").read_text(encoding="utf-8")
    assert "p.adopted == null ? 'no adopted version'" in html, "summary line"
    assert "</b> v${p.adopted}`" not in html, "an unguarded version in the summary"


# ---- final review: one rule for ids, flags and the adopted version ----------

def test_reingesting_the_adopted_version_changes_nothing_or_is_refused():
    """The newest directory IS the adopted version: the same document is a
    no-op, a changed one would rewrite adopted sections with no change report
    and no approval, so it is refused and v(adopted+1) is named."""
    root = _root("readopt")
    _both_v1(root)
    before = _snapshot(root)
    out = _ok(cli(root, "ingest-prd", "--prd", APP))
    assert "v1 is already adopted" in out and "nothing changed" in out, out
    assert _snapshot(root) == before, "an unchanged re-ingest wrote something"
    doc = next((root / f"inputs/prd/{APP}/v1").glob("*.md"))
    doc.write_text(doc.read_text(encoding="utf-8")
                   + "\n1.9 Waiver\nThe fee is waived for veterans.\n",
                   encoding="utf-8", newline="\n")
    before = _snapshot(root)
    r = cli(root, "ingest-prd", "--prd", APP)
    out = r.stdout + r.stderr
    assert r.returncode != 0 and "Traceback" not in out, out
    assert "differs from the adopted sections" in out, out
    assert f"inputs/prd/{APP}/v2/" in out, out
    assert _snapshot(root) == before, "a refusal wrote something"
    assert not (root / f"sources/prd/{APP}/1-9.md").exists()


def test_a_reserved_or_version_shaped_id_cannot_be_registered():
    root = _root("reservedid")
    for bad, why in (("v2", "collides with the version directory names"),
                     ("index", "reserved name"), ("log", "reserved name")):
        put_prd(root, bad, 1, f"{APP}-v1.md")
        r = cli(root, "ingest-prd", "--prd", bad, "--title", "X")
        out = r.stdout + r.stderr
        assert r.returncode != 0 and why in out, (bad, out)
        assert "Traceback" not in out, out
        assert not (root / "manifest.json").exists(), bad
        assert not (root / "sources").exists(), bad


def test_the_equals_form_of_a_flag_is_refused_not_ignored():
    """`--prd=x` used to be skipped, so the command acted on the default PRD
    (or asked for one); `--by=x` named nobody."""
    root = _staged_payment("equalsform")
    before = _snapshot(root)
    for argv, flag in ((["diff", f"--prd={PAY}"], "--prd"),
                       (["ingest-prd", f"--prd={APP}"], "--prd"),
                       (["ingest-prd", "--prd", APP, "--title=X"], "--title"),
                       (["approve-cr", "CR-001", "--by=tester", "--prd", PAY],
                        "--by"),
                       (["triage", "--prd-version=2"], "--prd-version")):
        r = cli(root, *argv)
        out = r.stdout + r.stderr
        assert r.returncode != 0 and "is not read" in out, (argv, out)
        assert f"{argv[0]} refused" in out and f"{flag} " in out, (argv, out)
    assert _snapshot(root) == before, "a refusal wrote something"


def _realign(root, sid):
    """Back to aligned with pins taken from the sections as they are now,
    keeping review_because: what a human re-assert leaves in the file."""
    p = root / f"stories/{sid}.md"
    fm, body = read_concept(p)
    sources = _manifest(root)["sources"]
    fm["status"] = "aligned"
    fm["source_pins"] = {k: wiki.source_pin(sources[k]) for k in fm["source_pins"]}
    wiki.write_concept(p, fm, body)


def test_a_second_change_to_the_same_source_is_recorded_again():
    root = _root("secondchange")
    _both_v1(root)
    add_story(root, "US-MP-PAY", [f"/sources/prd/{PAY}/1-1.md"])
    _ok(cli(root, "manifest"))
    src = f"prd#{PAY}/1-1"
    for version, fee, cr in ((2, 50, "CR-001"), (3, 60, "CR-002")):
        _put_text(root, PAY, version, "doc.md",
                  f"1.1 Fees\nThe application fee is {fee} dollars.\n\n"
                  "1.2 Refunds\nA rejected application is refunded in full.\n")
        _ok(cli(root, "ingest-prd", "--prd", PAY))
        out = _ok(cli(root, "approve-cr", cr, "--by", "tester", "--prd", PAY))
        assert "story US-MP-PAY -> needs-review" in out, out
        fm, _b = read_concept(root / "stories/US-MP-PAY.md")
        because = fm["review_because"]
        assert len(because) == version - 1, because
        assert because[-1]["cause"] == src, because
        assert because[-1]["pin"] == _manifest(root)["sources"][src]["content_hash"]
        if version == 2:
            _realign(root, "US-MP-PAY")
    assert because[0]["pin"] != because[1]["pin"], because
    # the same change, met again without a re-pin, is not a third entry
    p = root / "stories/US-MP-PAY.md"
    fm, body = read_concept(p)
    fm["status"] = "aligned"
    wiki.write_concept(p, fm, body)
    out = _ok(cli(root, "cascade"))
    assert "story US-MP-PAY -> needs-review" in out, out
    fm, _b = read_concept(p)
    assert len(fm["review_because"]) == 2, fm["review_because"]


if __name__ == "__main__":
    try:
        for name, fn in sorted(globals().items()):
            if name.startswith("test_") and callable(fn):
                fn()
                print(f"[PASS] {name}")
        print("test_wiki_multi_prd OK")
    finally:
        for _d in _ROOTS:
            if _d.exists():
                shutil.rmtree(_d, ignore_errors=True)
