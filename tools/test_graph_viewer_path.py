#!/usr/bin/env python3
"""Plain-assert tests for the in-repo graph-viewer bridge
(run: py tools/test_graph_viewer_path.py).

The viewer used to live at an absolute path that existed on exactly one
machine. These tests keep it in-tree. (This file deliberately avoids writing
that path out, so the scan below can search for it without matching itself.)
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import wiki_graph
from wiki import ROOT

SELF = Path(__file__).name


def test_viewer_repo_is_inside_this_repo():
    assert wiki_graph.VIEWER_REPO.is_relative_to(ROOT), \
        f"VIEWER_REPO escapes the repo: {wiki_graph.VIEWER_REPO}"


def test_harness_scripts_exist():
    for rel in ("scripts/validate.mjs", "scripts/bake.mjs"):
        assert (wiki_graph.VIEWER_REPO / rel).exists(), f"missing {rel}"


def test_bake_template_exists():
    """bake.mjs resolves its template as <repo>/dist/viewer.html."""
    assert (wiki_graph.VIEWER_REPO / "dist/viewer.html").exists(), \
        "run: cd tools/app/web && npm run build:viewer"


def test_no_absolute_machine_paths_in_tools():
    needle = "C:" + chr(92) + "Apps"
    offenders = sorted(
        p.relative_to(ROOT).as_posix()
        for p in (ROOT / "tools").rglob("*.py")
        if p.name != SELF and needle in p.read_text(encoding="utf-8"))
    assert offenders == [], f"absolute machine paths in: {offenders}"


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"[PASS] {name}")
    print("test_graph_viewer_path OK")
