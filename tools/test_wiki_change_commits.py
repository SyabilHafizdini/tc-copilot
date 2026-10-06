#!/usr/bin/env python3
"""approve-cr and reject-cr on the REAL committing path
(run: py tools/test_wiki_change_commits.py).

Every other test drives the CLI with --no-commit. These build a throwaway git
repository in a temp directory (never this checkout), drive this checkout's
tools/wiki.py at it through TC_ROOT_OVERRIDE, and let the commands commit. The
point: the one commit that introduces `asserted_by:` must carry an
Assertion-Event trailer, the tree must be clean afterwards, and lint (L10) must
stay at 0 errors.

Slow (real commits, lint on each): smoke runs it in the full tier only.
"""
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
from testkit import FIXTURES, add_story

APP = "rental-application"
_DIRS = []


def _git(scratch, *args):
    r = subprocess.run(["git", *args], cwd=scratch, capture_output=True,
                       text=True, encoding="utf-8", errors="replace")
    assert r.returncode == 0, (args, r.stdout, r.stderr)
    return r.stdout


def _wiki(scratch, *argv):
    env = dict(os.environ, TC_ROOT_OVERRIDE=str(scratch))
    return subprocess.run([sys.executable, str(ROOT / "tools/wiki.py"), *argv],
                          cwd=ROOT, env=env, capture_output=True, text=True,
                          encoding="utf-8", errors="replace")


def _scratch_repo():
    scratch = Path(tempfile.mkdtemp(prefix="tc_change_commits_"))
    _DIRS.append(scratch)
    _git(scratch, "init", "-q")
    for k, v in (("user.name", "tc-agent"), ("user.email", "tc-agent@internal"),
                 ("commit.gpgsign", "false")):
        _git(scratch, "config", k, v)
    shutil.copyfile(FIXTURES / "multi_prd/config.yaml", scratch / "config.yaml")
    _git(scratch, "add", "-A")
    _git(scratch, "commit", "-q", "-m", "scratch base")
    return scratch


def _put(scratch, version):
    dest = scratch / f"inputs/prd/{APP}/v{version}" / f"{APP}-v{version}.md"
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(FIXTURES / f"multi_prd/prds/{APP}-v{version}.md", dest)


def _staged_scratch():
    """v1 adopted, an aligned story citing 1.1, v2 staged as CR-001, all
    committed."""
    scratch = _scratch_repo()
    _put(scratch, 1)
    r = _wiki(scratch, "ingest-prd", "--prd", APP, "--title", "Rental application")
    assert r.returncode == 0, r.stdout + r.stderr
    add_story(scratch, "US-CM-1", [f"/sources/prd/{APP}/1-1.md"])
    _git(scratch, "add", "-A")
    _git(scratch, "commit", "-q", "-m", "fixture story\n\nAssertion-Event: fixture")
    r = _wiki(scratch, "manifest")
    assert r.returncode == 0, r.stdout + r.stderr
    _put(scratch, 2)
    r = _wiki(scratch, "ingest-prd", "--prd", APP)
    assert r.returncode == 0, r.stdout + r.stderr
    assert not _git(scratch, "status", "--porcelain").strip(), "staging left a dirty tree"
    return scratch


def _check_committed(scratch, subject_prefix, before_head):
    assert not _git(scratch, "status", "--porcelain").strip(), \
        _git(scratch, "status", "--porcelain")
    new = _git(scratch, "rev-list", f"{before_head}..HEAD").split()
    assert new, "nothing was committed"
    introducing = []
    for h in new:
        msg = _git(scratch, "show", "-s", "--format=%B", h)
        diff = _git(scratch, "show", "--format=", "-U0", h)
        if any(ln.startswith("+") and "asserted_by:" in ln for ln in diff.splitlines()):
            introducing.append((h, msg))
    assert len(introducing) == 1, introducing
    assert "Assertion-Event:" in introducing[0][1], introducing
    assert introducing[0][1].startswith(subject_prefix), introducing[0][1]
    assert len(new) == 1, f"expected exactly one commit, got {len(new)}: " + \
        _git(scratch, "log", "--format=%s", f"{before_head}..HEAD")
    r = _wiki(scratch, "lint")
    assert r.returncode == 0 and "0 error(s)" in r.stdout, r.stdout + r.stderr


def test_approve_cr_commits_once_with_an_assertion_event():
    scratch = _staged_scratch()
    head = _git(scratch, "rev-parse", "HEAD").strip()
    r = _wiki(scratch, "approve-cr", "CR-001", "--by", "tester", "--prd", APP)
    assert r.returncode == 0, r.stdout + r.stderr
    assert "needs-review" in r.stdout, "the cascade should have flagged the story"
    _check_committed(scratch, "approve-cr(CR-001)", head)


def test_reject_cr_commits_once_with_an_assertion_event():
    scratch = _staged_scratch()
    head = _git(scratch, "rev-parse", "HEAD").strip()
    r = _wiki(scratch, "reject-cr", "CR-001", "--by", "tester", "--prd", APP)
    assert r.returncode == 0, r.stdout + r.stderr
    _check_committed(scratch, "reject-cr(CR-001)", head)


if __name__ == "__main__":
    try:
        for name, fn in sorted(globals().items()):
            if name.startswith("test_") and callable(fn):
                fn()
                print(f"[PASS] {name}")
        print("test_wiki_change_commits OK")
    finally:
        for d in _DIRS:
            shutil.rmtree(d, ignore_errors=True)
