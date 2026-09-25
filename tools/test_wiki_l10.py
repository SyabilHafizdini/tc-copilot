#!/usr/bin/env python3
"""Plain-assert tests for wiki._l10_touches_assertion (run: py tools/test_wiki_l10.py).
Matches the tools/smoke.py idiom - no pytest in this repo.

Uses SYNTHETIC diff strings (no git needed) shaped like `git log -p --unified=0`
output: a `+++ b/<path>` header line followed by `+<line>` additions."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import wiki


def test_asserted_by_in_story_md_is_true():
    diff = (
        "diff --git a/stories/US-X.md b/stories/US-X.md\n"
        "--- a/stories/US-X.md\n"
        "+++ b/stories/US-X.md\n"
        "@@ -1,0 +2 @@\n"
        "+asserted_by: syabz\n"
    )
    assert wiki._l10_touches_assertion(diff) is True


def test_status_aligned_in_story_md_is_true():
    diff = (
        "diff --git a/stories/US-X.md b/stories/US-X.md\n"
        "--- a/stories/US-X.md\n"
        "+++ b/stories/US-X.md\n"
        "@@ -1,0 +2 @@\n"
        "+status: aligned\n"
    )
    assert wiki._l10_touches_assertion(diff) is True


def test_status_retired_in_testcase_md_is_true():
    diff = (
        "diff --git a/testcases/sit/x/T.md b/testcases/sit/x/T.md\n"
        "--- a/testcases/sit/x/T.md\n"
        "+++ b/testcases/sit/x/T.md\n"
        "@@ -1,0 +2 @@\n"
        "+status: retired\n"
    )
    assert wiki._l10_touches_assertion(diff) is True


def test_asserted_by_in_ts_test_mock_is_false():
    diff = (
        "diff --git a/tools/app/web/src/app/explorer/ExplorerPage.test.tsx "
        "b/tools/app/web/src/app/explorer/ExplorerPage.test.tsx\n"
        "--- a/tools/app/web/src/app/explorer/ExplorerPage.test.tsx\n"
        "+++ b/tools/app/web/src/app/explorer/ExplorerPage.test.tsx\n"
        "@@ -1,0 +2 @@\n"
        "+      asserted_by: null, stale: false }\n"
    )
    assert wiki._l10_touches_assertion(diff) is False


def test_asserted_by_in_plan_doc_is_false():
    diff = (
        "diff --git a/docs/superpowers/plans/x.md b/docs/superpowers/plans/x.md\n"
        "--- a/docs/superpowers/plans/x.md\n"
        "+++ b/docs/superpowers/plans/x.md\n"
        "@@ -1,0 +2 @@\n"
        "+asserted_by: null\n"
    )
    assert wiki._l10_touches_assertion(diff) is False


def test_asserted_by_in_ts_types_is_false():
    diff = (
        "diff --git a/tools/app/web/src/app/explorer/types.ts "
        "b/tools/app/web/src/app/explorer/types.ts\n"
        "--- a/tools/app/web/src/app/explorer/types.ts\n"
        "+++ b/tools/app/web/src/app/explorer/types.ts\n"
        "@@ -1,0 +2 @@\n"
        "+  asserted_by: string | null\n"
    )
    assert wiki._l10_touches_assertion(diff) is False


def _run():
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print(f"[PASS] {fn.__name__}")
    print(f"{len(fns)} passed")


if __name__ == "__main__":
    _run()
