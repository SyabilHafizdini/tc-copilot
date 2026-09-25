#!/usr/bin/env python3
"""Shared guards for the plain-assert test scripts (no pytest in this repo).

Several test files assert against the *project content* of a populated bundle
-- that there is a story to advise on, a flow to walk, a sealed TC to hash.
On the empty base branch (`master`) there is none, and those asserts would
fail for the one reason that is not a defect: nothing to test yet.

This module gives them a single, honest predicate for that. The rule it exists
to enforce:

    skip on "this bundle has no content", NEVER on "the assertion failed".

`skip_if_empty()` is deliberately narrow -- it looks only at whether the wiki
holds any concepts at all, and cannot be reached by a test whose subject
exists but misbehaves. A populated bundle therefore runs every assertion
exactly as before, and a real regression there still fails loudly.

Matches the [SKIP] idiom tools/smoke.py already uses for absent optional
toolchains (npm, bun, fastapi, Playwright), so a skip reads the same way
whether the missing thing is a binary or a body of content.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from wiki import ROOT, all_concepts


def bundle_concept_counts():
    """{type: n} over every parseable concept in the wiki. Read-only."""
    counts = {}
    for _rel, fm, _body, _p in all_concepts():
        if fm:
            counts[fm.get("type")] = counts.get(fm.get("type"), 0) + 1
    return counts


def bundle_is_empty():
    """True when the wiki holds no concepts at all -- a fresh/base bundle.

    Not "no stories": a bundle mid-ingest (PRD sections present, no stories
    authored yet) is a real state a test may legitimately want to assert on,
    so this is the strictest possible reading of 'nothing here'.
    """
    return not bundle_concept_counts()


def skip_if_empty(name):
    """Print a [SKIP] line and exit 0 when the bundle has no content.

    Call at the top of a test script's __main__ block. Returns normally (so
    the tests run) whenever the bundle holds anything.
    """
    if bundle_is_empty():
        print(f"[SKIP] {name}: empty bundle -- no project content to assert "
              f"against (this is the base branch's normal state)")
        sys.exit(0)


class SkipTest(Exception):
    """Raised by a single test that has no subject in this bundle.

    require() below exits the whole script, which is right when the file has
    one subject. A file asserting on several concept types needs to skip just
    the test whose type is absent -- a bundle with stories but no flows is a
    normal state, and failing there reports a content gap as a code defect.
    A runner that does not catch this still fails loudly rather than passing.
    """


def need(kind, why=None):
    """Raise SkipTest unless the bundle holds a concept of `kind`."""
    if not bundle_concept_counts().get(kind):
        raise SkipTest(why or "bundle has no %s concept to assert against" % kind)


def require(kind, name):
    """Skip when the bundle holds no concept of `kind` (e.g. "User Story").

    For a test whose subject is one concept type: a bundle can be non-empty
    yet still have no flow to walk. Same rule -- absence of the subject, never
    a failed assertion about it.
    """
    if not bundle_concept_counts().get(kind):
        print(f"[SKIP] {name}: bundle has no {kind} concept to assert against")
        sys.exit(0)
