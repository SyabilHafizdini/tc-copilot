#!/usr/bin/env python3
"""Plain-assert tests for reference-material ingest
(run: py tools/test_wiki_reference.py). No pytest -- matches tools/smoke.py."""
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
from wiki import extract_reference_text, reference_slug

TMP = ROOT / "build/_ref_t"


def _tmp():
    if TMP.exists():
        shutil.rmtree(TMP)
    TMP.mkdir(parents=True)
    return TMP


def test_slug_is_the_kebab_cased_relative_path():
    assert reference_slug("L/L/control/event-control-rules.yml") == \
        "L-L-control-event-control-rules"


def test_slug_disambiguates_repeated_filenames_across_folders():
    a = reference_slug("control/config.yml")
    b = reference_slug("data/config.yml")
    assert a != b, (a, b)


def test_yml_is_extracted_verbatim():
    d = _tmp()
    p = d / "rules.yml"
    p.write_text("a: 1\nb: 2\n", encoding="utf-8", newline="\n")
    assert "a: 1" in extract_reference_text(p)


def test_xlsx_sheets_render_as_markdown_tables():
    import openpyxl
    d = _tmp()
    p = d / "cases.xlsx"
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "TCs"
    ws.append(["ID", "Title"])
    ws.append(["TC-1", "Login works"])
    wb.save(str(p))
    text = extract_reference_text(p)
    assert "## TCs" in text, text
    assert "| ID | Title |" in text, text
    assert "TC-1" in text, text


def test_an_unreadable_binary_records_the_honest_fallback():
    d = _tmp()
    p = d / "legacy.doc"
    p.write_bytes(b"\x00\x01binary")
    assert extract_reference_text(p) == "_(no extractable text)_"


def _fake_root(files):
    """A throwaway root with inputs/reference/<files> and an empty manifest."""
    import json
    root = _tmp()
    for rel, text in files.items():
        p = root / "inputs/reference" / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8", newline="\n")
    (root / "manifest.json").write_text(
        json.dumps({"schema_version": 1, "adopted_prd_version": None,
                    "staged_prd_version": None, "id_config_frozen": False,
                    "counters": {}, "sources": {}, "concepts": {},
                    "bindings": {}, "tc_hashes": {}, "edges": []}),
        encoding="utf-8", newline="\n")
    return root


def _cli(root, *argv):
    import os
    import subprocess
    env = dict(os.environ, TC_ROOT_OVERRIDE=str(root))
    return subprocess.run(
        [sys.executable, str(ROOT / "tools" / "wiki.py"), *argv, "--no-commit"],
        cwd=ROOT, capture_output=True, text=True, env=env)


def test_ingest_writes_a_hashed_concept():
    import json
    root = _fake_root({"L/control/a-rules.yml": "key: value\n"})
    r = _cli(root, "ingest-reference")
    assert r.returncode == 0, r.stdout + r.stderr
    out = root / "sources/reference/L-control-a-rules.md"
    assert out.exists(), sorted((root / "sources").rglob("*"))
    text = out.read_text(encoding="utf-8")
    assert "type: Reference Document" in text, text
    assert "content_hash: sha256:" in text, text
    m = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    assert "reference#L-control-a-rules" in m["sources"], m["sources"]


def test_editing_a_reference_file_changes_its_manifest_hash():
    import json
    root = _fake_root({"L/control/a-rules.yml": "key: value\n"})
    assert _cli(root, "ingest-reference").returncode == 0
    first = json.loads((root / "manifest.json").read_text(
        encoding="utf-8"))["sources"]["reference#L-control-a-rules"]["content_hash"]
    (root / "inputs/reference/L/control/a-rules.yml").write_text(
        "key: CHANGED\n", encoding="utf-8", newline="\n")
    assert _cli(root, "ingest-reference").returncode == 0
    second = json.loads((root / "manifest.json").read_text(
        encoding="utf-8"))["sources"]["reference#L-control-a-rules"]["content_hash"]
    assert first != second, (first, second)


def test_cascade_flags_a_story_pinned_to_a_changed_reference_doc():
    """The spec's claim that cascade 'comes free' for reference material is
    only true if a story's source_pins can name a reference# id. Prove it."""
    import json
    root = _fake_root({"L/control/a-rules.yml": "key: value\n"})
    assert _cli(root, "ingest-reference").returncode == 0
    pinned = json.loads((root / "manifest.json").read_text(
        encoding="utf-8"))["sources"]["reference#L-control-a-rules"]["content_hash"]
    story = root / "stories/US-1.md"
    story.parent.mkdir(parents=True, exist_ok=True)
    story.write_text(
        "---\n"
        "type: User Story\nid: US-1\ntitle: Demo\nstatus: aligned\n"
        "provenance: human-stated\n"
        f"source_pins:\n  reference#L-control-a-rules: {pinned}\n"
        "---\nbody\n", encoding="utf-8", newline="\n")
    (root / "inputs/reference/L/control/a-rules.yml").write_text(
        "key: CHANGED\n", encoding="utf-8", newline="\n")
    assert _cli(root, "ingest-reference").returncode == 0
    r = _cli(root, "cascade")
    assert r.returncode == 0, r.stdout + r.stderr
    assert "needs-review" in story.read_text(encoding="utf-8"), \
        story.read_text(encoding="utf-8")


def test_a_junk_stem_is_refused():
    root = _fake_root({"L/screenshot.yml": "a: 1\n"})
    r = _cli(root, "ingest-reference")
    out = r.stdout + r.stderr
    assert r.returncode != 0, out
    assert "screenshot" in out, out
    ref_dir = root / "sources/reference"
    assert not ref_dir.exists() or not list(ref_dir.glob("*.md")), \
        sorted((root / "sources").rglob("*"))


def test_a_slug_collision_is_refused():
    # reference_slug collapses every non-alnum run to a single hyphen, so
    # these two distinct paths collide on the same id -- verified directly
    # below rather than assumed.
    a, b = "L/a-rules.yml", "L-a/rules.yml"
    assert reference_slug(a) == reference_slug(b) == "L-a-rules", \
        (reference_slug(a), reference_slug(b))
    root = _fake_root({a: "first: 1\n", b: "second: 2\n"})
    r = _cli(root, "ingest-reference")
    out = r.stdout + r.stderr
    assert r.returncode != 0, out
    assert ("L-a-rules" in out) or (a in out and b in out), out
    concept = root / "sources/reference/L-a-rules.md"
    if concept.exists():
        text = concept.read_text(encoding="utf-8")
        assert "second: 2" not in text, \
            f"second file silently overwrote the first's concept:\n{text}"


def test_a_corrupt_docx_refuses_instead_of_recording_an_empty_body():
    """.docx HAS a reader. Recording `_(no extractable text)_` for one that
    failed to parse, then hashing and committing it, is the same silent
    corruption the headingless-docx guard exists to prevent. The fallback is
    reserved for formats with no reader at all."""
    d = _tmp()
    p = d / "interface-spec.docx"
    p.write_bytes(b"PK\x03\x04 not really a docx")
    try:
        extract_reference_text(p)
    except SystemExit as e:
        assert "interface-spec.docx" in str(e), str(e)
    else:
        assert False, "expected SystemExit for an unreadable docx"


def test_a_corrupt_xlsx_refuses_too():
    d = _tmp()
    p = d / "cases.xlsx"
    p.write_bytes(b"PK\x03\x04 not really a workbook")
    try:
        extract_reference_text(p)
    except SystemExit as e:
        assert "cases.xlsx" in str(e), str(e)
    else:
        assert False, "expected SystemExit for an unreadable xlsx"


def test_a_corrupt_pdf_refuses_too():
    d = _tmp()
    p = d / "annex.pdf"
    p.write_bytes(b"%PDF-1.4 truncated")
    try:
        extract_reference_text(p)
    except SystemExit as e:
        assert "annex.pdf" in str(e), str(e)
    else:
        assert False, "expected SystemExit for an unreadable pdf"


def test_ingest_refuses_a_corrupt_document_through_the_cli():
    root = _fake_root({"a-rules.yml": "a: 1\n"})
    bad = root / "inputs/reference/interface-spec.docx"
    bad.write_bytes(b"PK\x03\x04 not really a docx")
    r = _cli(root, "ingest-reference")
    out = r.stdout + r.stderr
    assert r.returncode != 0, out
    assert "interface-spec.docx" in out, out
    refdir = root / "sources/reference"
    assert not refdir.exists() or not list(refdir.glob("*.md")), \
        sorted(refdir.rglob("*"))


def test_a_refusal_writes_no_partial_concepts():
    """Concepts were written inside the ingest loop while save_manifest ran
    only after it, so a refusal on file N left N-1 orphan concepts on disk
    behind an untouched manifest. Every name is validated first."""
    root = _fake_root({"a-rules.yml": "a: 1\n", "z/screenshot.yml": "b: 2\n"})
    r = _cli(root, "ingest-reference")
    out = r.stdout + r.stderr
    assert r.returncode != 0, out
    assert "screenshot" in out, out
    refdir = root / "sources/reference"
    assert not refdir.exists() or not list(refdir.glob("*.md")), \
        sorted(refdir.rglob("*"))


def test_a_late_slug_collision_writes_no_partial_concepts():
    root = _fake_root({"aaa.yml": "a: 1\n",
                       "L/a-rules.yml": "b: 2\n", "L-a/rules.yml": "c: 3\n"})
    r = _cli(root, "ingest-reference")
    out = r.stdout + r.stderr
    assert r.returncode != 0, out
    refdir = root / "sources/reference"
    assert not refdir.exists() or not list(refdir.glob("*.md")), \
        sorted(refdir.rglob("*"))


def test_dump_furniture_is_not_ingested_as_a_reference_document():
    root = _fake_root({"L/.gitkeep": "", "L/a-rules.yml": "a: 1\n"})
    r = _cli(root, "ingest-reference")
    out = r.stdout + r.stderr
    assert r.returncode == 0, out
    assert "reference documents ingested: 1" in out, out
    assert (root / "sources/reference/L-a-rules.md").exists(), \
        sorted((root / "sources/reference").glob("*"))
    assert len(list((root / "sources/reference").glob("*.md"))) == 1, \
        sorted((root / "sources/reference").glob("*"))


def test_readme_and_ds_store_are_furniture_too():
    root = _fake_root({"README.md": "# notes\n", ".DS_Store": "junk\n",
                       "a-rules.yml": "a: 1\n"})
    r = _cli(root, "ingest-reference")
    out = r.stdout + r.stderr
    assert r.returncode == 0, out
    assert "reference documents ingested: 1" in out, out


if __name__ == "__main__":
    try:
        for name, fn in sorted(globals().items()):
            if name.startswith("test_") and callable(fn):
                fn()
                print(f"[PASS] {name}")
        print("test_wiki_reference OK")
    finally:
        if TMP.exists():
            shutil.rmtree(TMP)
