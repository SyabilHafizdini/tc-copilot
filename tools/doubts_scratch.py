#!/usr/bin/env python3
"""Test support (no CLI): a throwaway, self-contained tc-copilot project built
from tools/fixtures/doubts/, so the answer and lift commands can be run as
subprocesses of a COPY of the tools. wiki.ROOT of the copy is the scratch
directory; the real repository is never touched."""
import atexit
import shutil
import subprocess
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
FIX = REPO / "tools" / "fixtures" / "doubts"
STORY = "US-FIXTURE-DOUBTS"
FLOW = "FLOW-FIXTURE-DOUBTS"

# fixture file -> path inside the scratch project
LAYOUT = {
    "story.md": f"stories/{STORY}.md",
    "flow.md": f"flows/{FLOW}.md",
    "resolution_01.md": f"resolutions/R-{STORY}-01.md",
    "register.yaml": f"doubts/{STORY}.yaml",
    "sit_spec.yaml": f"tools/sit_specs/{STORY}.yaml",
    "uat_spec.yaml": f"tools/uat_specs/{FLOW}.yaml",
    "manifest.json": "manifest.json",
    "tc_ac1.md": "testcases/fixture/TC-FIX-0001.md",
    "tc_ac2.md": "testcases/fixture/TC-FIX-0002.md",
}


def _git(cwd, *args):
    r = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"git {args} failed: {r.stdout}{r.stderr}")
    return r


_TEMPLATE = []


def _template():
    """One built project per process (git init and commit are slow on
    Windows); every scratch_project() call copies it."""
    if not _TEMPLATE:
        d = _build(Path(tempfile.mkdtemp(prefix="doubts-template-")))
        atexit.register(shutil.rmtree, d, True)
        _TEMPLATE.append(d)
    return _TEMPLATE[0]


def scratch_project(dest=None):
    """Build a throwaway, self-contained tc-copilot project in a temp dir and
    return its Path: a git repo (user tc-agent, commit.gpgsign false) holding a
    copy of tools/*.py and the tool sub-files they need (not node_modules, not
    tools/app), config.yaml, and the fixture content laid out as a real project,
    with an initial commit. Commands are run as subprocesses of the COPY
    (`py <scratch>/tools/wiki.py ...`). The caller removes the directory."""
    d = Path(dest) if dest is not None else Path(
        tempfile.mkdtemp(prefix="doubts-scratch-"))
    shutil.copytree(_template(), d, dirs_exist_ok=True)
    return d


def _build(d):
    d.mkdir(parents=True, exist_ok=True)
    (d / "tools").mkdir(exist_ok=True)
    for p in (REPO / "tools").glob("*.py"):
        if not p.name.startswith("test_"):
            shutil.copy(p, d / "tools" / p.name)
    shutil.copy(REPO / "config.yaml", d / "config.yaml")
    for src, rel in LAYOUT.items():
        out = d / rel
        out.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(FIX / src, out)
    (d / ".gitignore").write_text("build/\n__pycache__/\n", encoding="utf-8")
    _git(d, "init", "-q")
    _git(d, "config", "user.name", "tc-agent")
    _git(d, "config", "user.email", "tc-agent@internal")
    _git(d, "config", "commit.gpgsign", "false")
    _git(d, "add", "-A")
    _git(d, "commit", "-qm", "scratch: initial fixture project\n\n"
         "Assertion-Event: scratch-fixture " + STORY)
    return d


# ------------------------------------------------- a project that can RENDER
RFIX = REPO / "tools" / "fixtures" / "doubts_render"
RSTORY = "US-LIFT-FIX"
RFLOW = "FLOW-LIFT-FIX"
RLAYOUT = {
    "story.md": f"stories/{RSTORY}.md",
    "module.md": "modules/lift-fixture.md",
    "flow.md": f"flows/{RFLOW}.md",
    "resolution_01.md": f"resolutions/R-{RSTORY}-01.md",
    "register.yaml": f"doubts/{RSTORY}.yaml",
    "sit_spec.yaml": f"tools/sit_specs/{RSTORY}.yaml",
    "uat_spec.yaml": f"tools/uat_specs/{RFLOW}.yaml",
}
_RTEMPLATE = []


def _run_py(d, *args):
    r = subprocess.run(["py", *args], cwd=d, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"py {args} failed: {r.stdout}{r.stderr}")
    return r.stdout


def render_project(dest=None):
    """Like scratch_project(), but holding a story (US-LIFT-FIX) and a flow
    (FLOW-LIFT-FIX) that the real renderers can render: coverage confirmed, the
    test cases rendered and sealed (one binding per scenario), a register of two
    questions, all committed. Built once per process, copied per call."""
    if not _RTEMPLATE:
        d = Path(tempfile.mkdtemp(prefix="doubts-render-template-"))
        atexit.register(shutil.rmtree, d, True)
        (d / "tools").mkdir()
        for p in (REPO / "tools").glob("*.py"):
            if not p.name.startswith("test_"):
                shutil.copy(p, d / "tools" / p.name)
        shutil.copy(REPO / "config.yaml", d / "config.yaml")
        for src, rel in RLAYOUT.items():
            out = d / rel
            out.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy(RFIX / src, out)
        (d / ".gitignore").write_text("build/\n__pycache__/\n", encoding="utf-8")
        _git(d, "init", "-q")
        _git(d, "config", "user.name", "tc-agent")
        _git(d, "config", "user.email", "tc-agent@internal")
        _git(d, "config", "commit.gpgsign", "false")
        _git(d, "add", "-A")
        _git(d, "commit", "-qm", "scratch: lift fixture content\n\n"
             "Assertion-Event: scratch-fixture " + RSTORY)
        _run_py(d, "tools/render_sit.py", "--story", RSTORY)
        _run_py(d, "tools/render_uat.py", "--flow", RFLOW)
        _run_py(d, "tools/wiki.py", "seal", "--no-commit")
        _git(d, "add", "-A")
        _git(d, "commit", "-qm", "scratch: render and seal\n\n"
             "Assertion-Event: scratch-fixture " + RSTORY)
        _RTEMPLATE.append(d)
    out = Path(dest) if dest is not None else Path(
        tempfile.mkdtemp(prefix="doubts-render-"))
    shutil.copytree(_RTEMPLATE[0], out, dirs_exist_ok=True)
    return out
