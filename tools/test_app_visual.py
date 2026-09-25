#!/usr/bin/env python3
"""Playwright visual gate for the operator app
(run: py tools/test_app_visual.py). Matches the tools/smoke.py idiom -- no
pytest in this repo.

This is the check that makes "unstyled" a FAILURE rather than something a human
has to notice. It boots the committed bundle and asserts the shell actually
rendered and is styled -- in both themes -- then walks the real pages
(Projects, Dashboard, Inbox, Explore), asserting real content mounts on each.

Triple-guarded: it needs FastAPI (to boot the app), Playwright, and a Chromium
build. When any is absent it prints a [SKIP] line and exits 0, exactly like
tools/test_app_server.py guards on FastAPI, so smoke never becomes
runtime-dependent.
"""
import importlib.util
import subprocess
import sys
import tempfile
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# The shell/styling assertions below hold for ANY bundle -- that an unstyled
# app is a FAILURE is this file's whole reason to exist, and it must keep
# holding on an empty base branch. The assertions that need a document to open
# or a story to route to are gated on STORY, discovered from the wiki, so the
# gate degrades to "chrome is real and styled" instead of failing for lack of
# content. Never gate a styling assertion this way.
STORY = next((p.stem for p in sorted((ROOT / "stories").glob("*.md"))
              if p.name != "index.md"), None) if (ROOT / "stories").exists() else None
HAS_DOCS = STORY is not None or any(
    (ROOT / d).exists() and any(
        q.name != "index.md" for q in (ROOT / d).glob("*.md"))
    for d in ("glossary", "modules", "flows", "resolutions", "sources/prd"))

PORT = 8791
BASE = f"http://127.0.0.1:{PORT}"
SHOTS = ROOT / "build/visual"

for mod in ("fastapi", "uvicorn", "playwright"):
    if importlib.util.find_spec(mod) is None:
        print(f"[SKIP] test_app_visual ({mod} not installed -- "
              f"py -m pip install playwright && py -m playwright install chromium)")
        sys.exit(0)

from playwright.sync_api import Error as PlaywrightError  # noqa: E402
from playwright.sync_api import sync_playwright  # noqa: E402

# Expected theme grounds (index.css tokens), as the rgb() strings getComputedStyle returns.
GROUND = {"dark": "rgb(22, 26, 29)", "light": "rgb(247, 248, 249)"}


def _tail(log_f, n=4000):
    """Best-effort tail of the server's captured stdout/stderr for error messages."""
    try:
        log_f.seek(0)
        data = log_f.read()
    except Exception as e:
        return f"(could not read server log: {e})"
    text = data.decode("utf-8", "replace") if isinstance(data, bytes) else data
    return text[-n:] if text else "(server produced no output)"


def _wait_ready(proc, log_f, timeout=60.0):
    """Poll /api/state until the server answers, failing fast if it dies."""
    import time
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if proc.poll() is not None:
            raise RuntimeError(
                f"app server exited early (rc={proc.returncode})\n"
                f"--- server output (tail) ---\n{_tail(log_f)}")
        try:
            with urllib.request.urlopen(f"{BASE}/api/state", timeout=5) as r:
                if r.status == 200:
                    return
        except Exception:
            time.sleep(0.3)
    raise RuntimeError(
        f"app server did not become ready in time\n"
        f"--- server output (tail) ---\n{_tail(log_f)}")


def _check_shell(page, theme):
    """Framing that must hold on every route: real styling + the persistent
    chat/nav columns + the two anchors (TopBar, Sidebar) of the new shell."""
    body_bg = page.eval_on_selector("body", "el => getComputedStyle(el).backgroundColor")
    assert body_bg == GROUND[theme], f"{theme}: body background {body_bg!r} != token {GROUND[theme]!r} (styling did not apply)"
    assert page.locator(".chatcol").count() == 1, f"{theme}: chat panel missing"
    assert page.locator(".navcol").count() == 1, f"{theme}: nav rail missing"
    brand = page.locator(".topbar .brand-mark span").inner_text()
    assert brand == "tc-copilot", f"{theme}: TopBar brand missing/wrong -- {brand!r}"
    proj = page.locator(".navcol .proj-head-nav .who b").inner_text()
    assert proj, f"{theme}: Sidebar project header empty"
    search_hint = page.locator(".topbar .search kbd").inner_text()
    assert search_hint == "Ctrl K", f"{theme}: TopBar search hint missing/wrong -- {search_hint!r}"


def run():
    SHOTS.mkdir(parents=True, exist_ok=True)
    log_f = tempfile.TemporaryFile(mode="w+b")
    proc = subprocess.Popen(
        [sys.executable, str(ROOT / "tools/wiki.py"), "app", "--no-open", "--port", str(PORT)],
        cwd=ROOT, stdout=log_f, stderr=subprocess.STDOUT)
    try:
        _wait_ready(proc, log_f)
        with sync_playwright() as p:
            try:
                browser = p.chromium.launch()
            except PlaywrightError as e:
                msg = str(e)
                if "Executable doesn't exist" in msg or "playwright install" in msg.lower():
                    print("[SKIP] test_app_visual (chromium not installed -- "
                          "run: py -m playwright install chromium)")
                    sys.exit(0)
                raise
            try:
                for theme in ("dark", "light"):
                    ctx = browser.new_context(color_scheme=theme)
                    try:
                        page = ctx.new_page()
                        # networkidle never fires: the app opens a persistent
                        # EventSource('/api/events') SSE connection on mount.
                        # Empty hash resolves to the Level-0 Projects portfolio
                        # (routes.ts viewFromHash -- unrecognized/empty head -> 'projects').
                        page.goto(BASE, wait_until="domcontentloaded")
                        page.wait_for_selector(".proj-card")
                        _check_shell(page, theme)
                        heading = page.locator(".page-head h1").inner_text()
                        assert heading == "Projects", f"{theme}: Projects heading missing/wrong -- {heading!r}"
                        assert page.locator(".proj-card").count() >= 1, f"{theme}: no project tiles rendered"

                        # Sidebar nav switches the center page but chat/nav persist --
                        # Dashboard is the project home (metric-card row + computed
                        # phase Kanban), reachable from the Sidebar under the new IA.
                        page.get_by_role("button", name="Dashboard", exact=True).click()
                        page.wait_for_selector(".dashboard .metric")
                        assert page.locator(".chatcol").count() == 1, f"{theme}: chat panel disappeared on navigation"
                        assert page.locator(".navcol").count() == 1, f"{theme}: nav rail disappeared on navigation"

                        # metric-card row (MetricCards): a real KPI label, not a placeholder
                        assert page.get_by_text("Open questions").count() == 1, f"{theme}: Open questions metric card missing"

                        # computed phase Kanban (PhaseKanban): four real columns, not a stub
                        assert page.get_by_role("region", name="① Ingested").count() == 1, f"{theme}: Ingested kanban column missing"
                        assert page.locator(".dashboard .kanban .kban-col").count() == 4, f"{theme}: expected 4 kanban columns"

                        # Inbox may legitimately be empty (all cards answered) --
                        # assert the page mounts, not a specific card.
                        page.get_by_role("button", name="Inbox", exact=True).click()
                        page.wait_for_selector(".inbox")
                        assert page.locator(".inbox").count() == 1, f"{theme}: inbox missing"

                        # Documents (Phase 1) renders and is styled
                        page.get_by_role("button", name="Documents").click()
                        page.wait_for_selector(".documents-page")
                        assert page.locator(".documents-page").count() == 1, \
                            f"{theme}: documents page missing"

                        # Suites & Export (Phase 3) renders and is styled
                        page.get_by_role("button", name="Suites & Export").click()
                        page.wait_for_selector(".suites-page")
                        assert page.locator(".suites-page").count() == 1, \
                            f"{theme}: suites page missing"
                        assert page.get_by_text("test cases resolved").count() >= 1 \
                            or page.get_by_text("resolving").count() >= 1, \
                            f"{theme}: suites preview did not render"

                        # New Explore view (Plan 4): tree-primary + type badge, both themes.
                        # Reached via the real Sidebar "Explore" entry (Browse group, the
                        # PRIMARY nav item -- tools/app/web/src/app/shell/Sidebar.tsx),
                        # same as an operator would.
                        page.get_by_role("button", name="Explore", exact=True).click()
                        page.wait_for_selector(".explore")
                        assert page.locator(".explore").count() == 1, f"{theme}: explore view missing"
                        assert page.locator(".chatcol").count() == 1, f"{theme}: chat panel disappeared on navigation"
                        if HAS_DOCS:
                            assert page.locator(".tree-item").count() >= 1, f"{theme}: no tree items in the vault tree"

                            # Selecting a real file drives the content pane + type badge (Task 3).
                            # Folder rows (.tree-folder) only toggle expand/collapse -- a file
                            # leaf is required to actually select a document.
                            page.locator(".explore .tree-item:not(.tree-folder)").first.click()
                            page.wait_for_selector(".doc-type-badge")
                            assert page.locator(".doc-type-badge").count() >= 1, f"{theme}: explore type badge missing"

                        page.screenshot(path=str(SHOTS / f"operator-{theme}.png"), full_page=True)

                        # Story issue-view (Plan 6): the shell routes #/story/<id> to
                        # StoryPage the same way App.tsx's own navigate() does
                        # (window.location.hash = hrefFor(view)), driving a real
                        # hashchange against a real story doc. The story is
                        # discovered, not named: there is no story to route to on an
                        # empty bundle, and nothing to screenshot.
                        if STORY:
                            page.evaluate(f"window.location.hash = '#/story/{STORY}'")
                            page.wait_for_selector(".story-view")
                            assert page.locator(".chatcol").count() == 1, f"{theme}: chat panel disappeared on navigation"
                            assert page.locator(".navcol").count() == 1, f"{theme}: nav rail disappeared on navigation"

                            # PhaseStepper (Task 3/5): four clickable phase steps.
                            assert page.locator(".phase-stepper .step").count() == 4, f"{theme}: phase stepper missing its 4 steps"

                            # ReadinessBox (Task 1/6): single merge-box rollup verdict, ready or blocked.
                            assert page.locator(".readiness").count() == 1, f"{theme}: readiness box missing"

                            # StoryPage tabs (Task 9): Overview/AC/Components/Test Cases/Coverage/Traceability/Activity.
                            assert page.locator(".story-main .tabs .tab").count() == 7, f"{theme}: story tabs missing/incomplete"

                            page.screenshot(path=str(SHOTS / f"operator-story-{theme}.png"), full_page=True)
                    finally:
                        ctx.close()
            finally:
                browser.close()
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except Exception:
            proc.kill()
        log_f.close()


def test_visual_gate():
    run()


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"[PASS] {name}")
    print("test_app_visual OK")
