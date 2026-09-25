#!/usr/bin/env python3
"""Plain-assert tests for the viewer-bundle freshness check
(run: py tools/test_bundle_check.py). Matches the tools/smoke.py idiom -- no
pytest in this repo.

Only the first test reads the committed manifest; the rest pass synthetic
records, so a failure can never leave the workspace half-mutated.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "app"))
import bundle_check


def test_committed_bundle_is_in_sync():
    assert bundle_check.check() == [], \
        "committed bundle is stale -- run: cd tools/app/web && npm run build:viewer"


def test_changed_sources_are_detected():
    real = bundle_check.bundle_digest()
    errs = bundle_check.check({"sources": "deadbeef", "viewer_html": real})
    assert any("sources changed" in e for e in errs), errs


def test_modified_bundle_is_detected():
    real = bundle_check.source_digest()
    errs = bundle_check.check({"sources": real, "viewer_html": "deadbeef"})
    assert any("modified" in e for e in errs), errs


def test_source_digest_is_stable():
    assert bundle_check.source_digest() == bundle_check.source_digest(), \
        "digest must not depend on iteration order"


def test_entrypoints_are_build_inputs():
    files = bundle_check.source_files()
    for expected in ("src/main.tsx", "src/App.tsx", "index.html",
                     "package-lock.json"):
        assert expected in files, f"{expected} must invalidate the bundle"


def test_harness_scripts_are_not_bundle_inputs():
    """scripts/*.mjs affect baking, not the bundle -- editing one must not
    report the committed viewer.html as stale."""
    assert [f for f in bundle_check.source_files()
            if f.startswith("scripts/")] == []


def test_test_files_are_not_bundle_inputs():
    """Editing a test must not invalidate a build artifact it cannot affect."""
    assert [f for f in bundle_check.source_files()
            if ".test." in f] == []


def test_app_entrypoints_are_build_inputs():
    files = bundle_check.app_source_files()
    for expected in ("src/app/main.tsx", "src/app/App.tsx", "src/app/api.ts",
                      "app.html"):
        assert expected in files, f"{expected} must invalidate the app bundle"


def test_app_test_files_are_not_bundle_inputs():
    """Editing api.test.ts must not invalidate the committed app bundle."""
    files = bundle_check.app_source_files()
    assert "src/app/api.test.ts" not in files
    assert [f for f in files if ".test." in f] == []


def test_viewer_source_files_exclude_app_subtree():
    """src/app/** belongs to sub-project B; it must not invalidate the viewer."""
    app_only = [f for f in bundle_check.source_files()
                if f.startswith("src/app/")]
    assert app_only == [], app_only


def test_app_inputs_are_a_superset_of_the_viewer_non_app_inputs():
    """The app's src glob is deliberately wider than src/app/ alone: a later
    sub-project is expected to import vendored graph components from
    src/components/ or src/lib/ into the app, and under-covering that
    silently would be a permanent false pass. Over-covering (the app also
    reacting to a viewer-only src/ edit) is the safe failure direction, so
    what must be pinned is that the app's src/ inputs never cover LESS than
    the viewer's -- not that the two file sets match overall (each still has
    its own non-shared entrypoint/config: index.html + vite.viewer.config.ts
    for the viewer, app.html + vite.app.config.ts for the app)."""
    viewer_src = {f for f in bundle_check.source_files() if f.startswith("src/")}
    app_src = {f for f in bundle_check.app_source_files() if f.startswith("src/")}
    missing = viewer_src - app_src
    assert missing == set(), \
        f"viewer src/ inputs missing from the app's glob (false-pass risk): {missing}"


def test_changed_app_sources_are_detected():
    record = {
        "sources": bundle_check.source_digest(),
        "viewer_html": bundle_check.bundle_digest(),
        "app_sources": "deadbeef",
        "app_html": bundle_check.app_bundle_digest(),
    }
    errs = bundle_check.check(record)
    assert any("app sources changed" in e for e in errs), errs


def test_modified_app_bundle_is_detected():
    record = {
        "sources": bundle_check.source_digest(),
        "viewer_html": bundle_check.bundle_digest(),
        "app_sources": bundle_check.app_source_digest(),
        "app_html": "deadbeef",
    }
    errs = bundle_check.check(record)
    assert any("dist-app/index.html was modified" in e for e in errs), errs


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"[PASS] {name}")
    print("test_bundle_check OK")
