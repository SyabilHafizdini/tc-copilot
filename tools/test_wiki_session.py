#!/usr/bin/env python3
"""Plain-assert tests for `wiki session revert` (run: py tools/test_wiki_session.py).
Matches the tools/smoke.py / tools/test_wiki_card.py idiom -- no pytest.

`wiki.py` always does its git plumbing with `cwd=ROOT`, where `ROOT` is a
module-global computed from the script's own on-disk location (a deliberate,
codebase-wide convention -- every git call site in wiki.py uses it, not just
this verb). Subprocessing wiki.py against a different `cwd` therefore does
NOT redirect its git operations; they would still land on the real checkout.

So instead of subprocessing, every test here imports `wiki` directly and
temporarily repoints the module global `wiki.ROOT` at a throwaway temp git
repo before calling `wiki.cmd_session([...])` in-process. Because
`cmd_session` (and `agent_commit`, which it calls) look up `ROOT` by name at
call time, this genuinely redirects every git subprocess call into the temp
repo -- real isolation, not subprocess-cwd isolation. `wiki.ROOT` (and
`sys.argv`, where touched) is always restored in a `finally` so tests never
leak state to each other or to the real repo. No test here ever runs git, or
wiki's lint gate, against the real checkout.
"""
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import wiki


def _git(cwd, *args, check=True):
    r = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True)
    if check and r.returncode != 0:
        raise AssertionError(f"git {args} failed: {r.stdout}{r.stderr}")
    return r


def _mk_repo(d):
    """A throwaway repo with the provenance config agent_commit needs, and
    one base commit."""
    _git(d, "init", "-q")
    _git(d, "config", "user.name", "tc-agent")
    _git(d, "config", "user.email", "tc-agent@internal")
    (d / "config.yaml").write_text(
        "provenance:\n  agent_git_name: tc-agent\n"
        "  agent_git_email: tc-agent@internal\n  human: tester\n",
        encoding="utf-8")
    _git(d, "add", "-A"); _git(d, "commit", "-qm", "base")


def test_revert_undoes_a_sessions_commit():
    with tempfile.TemporaryDirectory() as d:
        d = Path(d)
        _mk_repo(d)
        # A commit tagged with a session id, as the agent would produce.
        (d / "story.md").write_text("draft\n", encoding="utf-8")
        _git(d, "add", "-A")
        _git(d, "commit", "-qm", "feat(story): draft US-XTST-001")
        assert (d / "story.md").exists()

        old_root, old_argv = wiki.ROOT, sys.argv
        try:
            wiki.ROOT = d
            # agent_commit reads --allow-lint-errors straight from sys.argv,
            # regardless of how cmd_session's own `args` list is shaped. Set
            # it here so the REAL agent_commit path runs (git add/commit),
            # just skipping the lint subprocess on this throwaway repo.
            sys.argv = ["wiki.py", "session", "revert", "US-XTST-001",
                        "--by", "tester", "--allow-lint-errors"]
            wiki.cmd_session(["revert", "US-XTST-001", "--by", "tester"])
        finally:
            wiki.ROOT, sys.argv = old_root, old_argv

        assert not (d / "story.md").exists(), "revert must undo the file"
        log = _git(d, "log", "--oneline").stdout
        assert "revert" in log.lower(), log


def test_revert_refuses_unknown_session():
    with tempfile.TemporaryDirectory() as d:
        d = Path(d)
        _mk_repo(d)

        old_root = wiki.ROOT
        try:
            wiki.ROOT = d
            try:
                wiki.cmd_session(["revert", "US-NOPE-001", "--by", "tester"])
                assert False, "expected SystemExit for an unmatched session"
            except SystemExit as e:
                msg = str(e.code)
                assert "no commits matched" in msg.lower(), msg
        finally:
            wiki.ROOT = old_root


def test_revert_refuses_dirty_tree():
    with tempfile.TemporaryDirectory() as d:
        d = Path(d)
        _mk_repo(d)
        (d / "story.md").write_text("draft\n", encoding="utf-8")
        _git(d, "add", "-A")
        _git(d, "commit", "-qm", "feat(story): draft US-XTST-001")
        # An uncommitted change -- the tree is dirty at the moment revert is
        # requested, which cmd_session must refuse before touching git log.
        (d / "scratch.md").write_text("uncommitted\n", encoding="utf-8")

        old_root = wiki.ROOT
        try:
            wiki.ROOT = d
            try:
                wiki.cmd_session(["revert", "US-XTST-001", "--by", "tester"])
                assert False, "expected SystemExit for a dirty tree"
            except SystemExit as e:
                msg = str(e.code)
                assert "dirty" in msg.lower(), msg
        finally:
            wiki.ROOT = old_root


def test_revert_undoes_multiple_commits_as_one_commit():
    with tempfile.TemporaryDirectory() as d:
        d = Path(d)
        _mk_repo(d)
        # Three commits under the same session, each touching a distinct
        # file -- newest-first order and "single collapsed commit" are
        # otherwise unverified by the single-commit fixtures above.
        for name, content in (("a.txt", "a\n"), ("b.txt", "b\n"), ("c.txt", "c\n")):
            (d / name).write_text(content, encoding="utf-8")
            _git(d, "add", "-A")
            _git(d, "commit", "-qm", f"feat(story): add {name} US-XMUL-001")
        before = int(_git(d, "rev-list", "--count", "HEAD").stdout.strip())

        old_root, old_argv = wiki.ROOT, sys.argv
        try:
            wiki.ROOT = d
            sys.argv = ["wiki.py", "session", "revert", "US-XMUL-001",
                        "--by", "tester", "--allow-lint-errors"]
            wiki.cmd_session(["revert", "US-XMUL-001", "--by", "tester"])
        finally:
            wiki.ROOT, sys.argv = old_root, old_argv

        assert not (d / "a.txt").exists()
        assert not (d / "b.txt").exists()
        assert not (d / "c.txt").exists()
        after = int(_git(d, "rev-list", "--count", "HEAD").stdout.strip())
        assert after == before + 1, f"expected exactly +1 commit, got +{after - before}"


def test_revert_conflict_refuses_and_cleans_up():
    with tempfile.TemporaryDirectory() as d:
        d = Path(d)
        _mk_repo(d)
        # Commit A (session-tagged) adds f.txt; commit B (untagged) later
        # changes it. Reverting A now conflicts (modify/delete) because the
        # file no longer matches what A introduced.
        (d / "f.txt").write_text("v1\n", encoding="utf-8")
        _git(d, "add", "-A")
        _git(d, "commit", "-qm", "feat(story): add f.txt US-XCONF-001")
        (d / "f.txt").write_text("v2\n", encoding="utf-8")
        _git(d, "add", "-A")
        _git(d, "commit", "-qm", "chore: bump f.txt")

        old_root = wiki.ROOT
        try:
            wiki.ROOT = d
            try:
                wiki.cmd_session(["revert", "US-XCONF-001", "--by", "tester"])
                assert False, "expected SystemExit for a revert conflict"
            except SystemExit as e:
                msg = str(e.code)
                assert "conflict" in msg.lower(), msg
        finally:
            wiki.ROOT = old_root

        status = _git(d, "status", "--porcelain").stdout
        assert status.strip() == "", f"conflict cleanup left a dirty tree:\n{status}"


def test_revert_requires_by():
    try:
        wiki.cmd_session(["revert", "US-XTST-001"])
        assert False, "expected SystemExit without --by"
    except SystemExit as e:
        msg = str(e.code)
        assert "--by" in msg, msg


if __name__ == "__main__":
    fails = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn(); print(f"[PASS] {name}")
            except Exception as e:
                fails += 1; print(f"[FAIL] {name}: {e}")
    sys.exit(1 if fails else 0)
