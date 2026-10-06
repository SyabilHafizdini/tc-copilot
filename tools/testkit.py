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


# ---- scratch bundle roots ---------------------------------------------------
# A throwaway repo root under build/ (git-ignored), driven through the real CLI
# with TC_ROOT_OVERRIDE. Nothing here can touch the tracked wiki.
import os
import shutil
import subprocess

# The tracked repository, derived from this file's own location. wiki.ROOT is
# not used for the guards: it follows TC_ROOT_OVERRIDE and so can be a scratch.
REPO_ROOT = Path(__file__).resolve().parent.parent
FIXTURES = REPO_ROOT / "tools/fixtures"


def scratch_root(name):
    """An empty bundle root at build/_<name>/, recreated on every call. It has
    no manifest.json, so the CLI starts from load_manifest()'s default. `name`
    must be a plain name: anything that could point elsewhere is refused
    before a directory is removed or created."""
    if (not isinstance(name, str) or not name or name in (".", "..")
            or ".." in name or "/" in name or "\\" in name
            or Path(name).name != name):
        raise ValueError(f"scratch_root: {name!r} is not a plain name "
                         f"(no separators, no '..')")
    root = REPO_ROOT / "build" / f"_{name}"
    if root.parent != REPO_ROOT / "build":
        raise ValueError(f"scratch_root: {name!r} resolves outside build/")
    if root.exists():
        shutil.rmtree(root)
    root.mkdir(parents=True)
    return root


def multi_prd_root(name):
    """A scratch root carrying the two-PRD fixture's config.yaml. PRD documents
    are placed one version at a time with put_prd()."""
    root = scratch_root(name)
    shutil.copyfile(FIXTURES / "multi_prd/config.yaml", root / "config.yaml")
    return root


def put_prd(root, prd_id, version, filename):
    """Copy tools/fixtures/multi_prd/prds/<filename> to
    <root>/inputs/prd/<prd_id>/v<version>/<filename>."""
    dest = root / f"inputs/prd/{prd_id}/v{version}" / filename
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(FIXTURES / "multi_prd/prds" / filename, dest)
    return dest


def add_story(root, sid, refs, status="aligned"):
    """A prd-verbatim story citing `refs` (ingested section refs), with
    source_pins taken from those sections as `wiki assert story` would write
    them. Fixture content only - no real story is asserted this way."""
    from wiki import read_concept, resolve_ref, source_pin, write_concept
    pins = {}
    for ref in refs:
        fm, _body = read_concept(root / (resolve_ref(ref)[0] + ".md"))
        pins[fm["id"]] = source_pin(fm)
    path = root / f"stories/{sid}.md"
    write_concept(path, {
        "type": "User Story", "id": sid, "title": f"{sid} title",
        "description": "Fixture story.", "status": status,
        "provenance": "prd-verbatim", "derived_from": list(refs),
        "acceptance_criteria": [{"id": "AC1", "text": "Fixture criterion."}],
        "source_pins": pins}, "# Story\n\nFixture.\n")
    return path


def cli(root, *argv):
    """Run the real `wiki.py` against a scratch root, never committing. The root
    must be an absolute path that is not the repository itself: an empty or
    relative one would resolve to the tracked wiki."""
    if not str(root) or not Path(root).is_absolute():
        raise ValueError(f"cli: root {str(root)!r} is not an absolute path")
    if Path(root).resolve() == REPO_ROOT:
        raise ValueError("cli: root is the tracked repository; use a scratch root")
    env = dict(os.environ, TC_ROOT_OVERRIDE=str(root))
    return subprocess.run(
        [sys.executable, str(REPO_ROOT / "tools" / "wiki.py"), *argv, "--no-commit"],
        cwd=REPO_ROOT, capture_output=True, text=True, encoding="utf-8",
        errors="replace", env=env)
