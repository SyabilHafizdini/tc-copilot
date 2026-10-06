#!/usr/bin/env python3
"""Playwright visual gate for the operator app
(run: py tools/test_app_visual.py). Matches the tools/smoke.py idiom -- no
pytest in this repo.

This is the check that makes "unstyled" a FAILURE rather than something a human
has to notice. It boots the committed bundle and asserts the shell actually
rendered and is styled -- in both themes -- then walks the real pages
(Projects, Dashboard, Inbox, Explore, Test Cases, Workbook), asserting real
content mounts on each. The docked chat is Off by default: the default shell
is checked without it, then it is switched On through Settings and the walk
continues with it.

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

# The Test Cases and Workbook pages need content too: a rendered test case,
# and a workbook compiled under build/ (git-ignored; smoke's full tier compiles
# every suite before it reaches this file).
HAS_TCS = (ROOT / "testcases").exists() and any(
    q.name != "index.md" for q in (ROOT / "testcases").rglob("*.md"))
HAS_WORKBOOK = any((ROOT / "build/inventory").glob("*/*-latest.xlsx"))

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


def _check_shell(page, theme, chat):
    """Framing that must hold on every route: real styling + the persistent
    nav column + the two anchors (TopBar, Sidebar) of the new shell. `chat`
    says whether the docked chat is switched On: Off (the default) renders no
    chat column at all."""
    body_bg = page.eval_on_selector("body", "el => getComputedStyle(el).backgroundColor")
    assert body_bg == GROUND[theme], f"{theme}: body background {body_bg!r} != token {GROUND[theme]!r} (styling did not apply)"
    if chat:
        assert page.locator(".chatcol").count() == 1, f"{theme}: chat panel missing"
    else:
        assert page.locator(".chatcol").count() == 0, f"{theme}: chat is Off by default but a chat column rendered"
        assert page.locator(".chat-reopen").count() == 0, f"{theme}: chat is Off but its reopen button rendered"
    assert page.locator(".navcol").count() == 1, f"{theme}: nav rail missing"
    brand = page.locator(".topbar .brand-mark span").inner_text()
    assert brand == "tc-copilot", f"{theme}: TopBar brand missing/wrong -- {brand!r}"
    proj = page.locator(".navcol .proj-head-nav .who b").inner_text()
    assert proj, f"{theme}: Sidebar project header empty"
    search_hint = page.locator(".topbar .search kbd").inner_text()
    assert search_hint == "Ctrl K", f"{theme}: TopBar search hint missing/wrong -- {search_hint!r}"


def _check_testcases(page, theme):
    """The Test Cases grid renders rows in the workbook's columns and a row
    opens the review panel; the ID column stays in view when the grid scrolls
    sideways. Needs a rendered test case."""
    if not HAS_TCS:
        print(f"[SKIP] {theme}: Test Cases grid (no rendered test case in this bundle)")
        return
    page.get_by_role("button", name="Test Cases", exact=True).click()
    page.wait_for_selector(".tc-grid tr.tc-row")
    assert page.locator(".tc-grid thead th").count() == 7, f"{theme}: the grid does not have the workbook's 7 columns"
    assert page.locator(".tc-grid tr.tc-row").count() >= 1, f"{theme}: no test case rows"
    page.locator(".tc-grid tr.tc-row").first.click()
    page.wait_for_selector(".tc-panel")
    assert page.locator(".tc-panel").count() == 1, f"{theme}: a row click did not open the review panel"
    # The card scrolls inside the page; the page itself does not grow sideways.
    over = page.evaluate("document.scrollingElement.scrollWidth - window.innerWidth")
    assert over <= 1, f"{theme}: the Test Cases page overflows the window by {over}px"
    stuck = page.evaluate("""() => {
        const card = document.querySelector('.tc-grid-card')
        card.scrollLeft = 400
        const id = document.querySelector('.tc-grid tr.tc-row td.tc-id').getBoundingClientRect()
        return [card.scrollLeft, Math.round(id.left - card.getBoundingClientRect().left)]
    }""")
    if stuck[0] > 0:        # the card is wide enough to scroll sideways
        assert stuck[1] <= 2, f"{theme}: the ID column scrolled out of view ({stuck[1]}px)"
    page.screenshot(path=str(SHOTS / f"operator-testcases-{theme}.png"))
    # A narrow window stacks the panel under the grid: the card keeps to the
    # page's width (scrolling inside itself) and the panel is reachable below.
    wide = page.viewport_size
    page.set_viewport_size({"width": 860, "height": 900})
    try:
        narrow = page.evaluate("""() => {
            const pg = document.querySelector('.page').getBoundingClientRect()
            const card = document.querySelector('.tc-grid-card').getBoundingClientRect()
            const panel = document.querySelector('.tc-panel').getBoundingClientRect()
            return {page: [pg.left, pg.right], card: [card.left, card.right],
                    panelTop: panel.top, cardBottom: card.bottom,
                    over: document.scrollingElement.scrollWidth - window.innerWidth}
        }""")
        assert narrow["card"][0] >= narrow["page"][0] and narrow["card"][1] <= narrow["page"][1] + 1, \
            f"{theme}: at 860px the grid card leaves the page ({narrow})"
        assert narrow["over"] <= 1, f"{theme}: at 860px the page overflows sideways ({narrow})"
        assert narrow["panelTop"] >= narrow["cardBottom"] - 1, \
            f"{theme}: at 860px the panel is not stacked under the grid ({narrow})"
    finally:
        page.set_viewport_size(wide)
    page.get_by_role("button", name="Close review panel").click()
    page.wait_for_selector(".tc-panel", state="detached")


def _check_workbook(page, theme, chat=False):
    """The Workbook view owns its scrolling: the document does not scroll, the
    sheet does, the frozen header band stays at the top of the sheet, the tab
    bar stays inside the window, and the docked review panel stays in view.
    Needs a compiled workbook."""
    if not HAS_WORKBOOK:
        print(f"[SKIP] {theme}: Workbook view (nothing compiled under build/inventory/ -- "
              f"py tools/wiki.py suite compile <name> --no-commit)")
        return
    who = f"{theme}{' (chat on)' if chat else ''}"
    page.get_by_role("button", name="Workbook", exact=True).click()
    page.wait_for_selector(".wb-sheet tbody tr")
    page.wait_for_selector(".wb-tabs .wb-tab")
    dims = page.evaluate("""() => {
        const box = document.querySelector('.wb-scroll')
        const tabs = document.querySelector('.wb-tabs').getBoundingClientRect()
        return {doc: document.scrollingElement.scrollHeight, win: window.innerHeight,
                inner: box.scrollHeight, view: box.clientHeight, tabsBottom: tabs.bottom,
                tabsTop: tabs.top}
    }""")
    assert dims["doc"] <= dims["win"] + 1, \
        f"{who}: the document scrolls ({dims['doc']}px in a {dims['win']}px window) instead of the sheet"
    assert dims["tabsBottom"] <= dims["win"] + 1 and dims["tabsTop"] > 0, \
        f"{who}: the sheet tab bar is outside the window ({dims['tabsTop']}..{dims['tabsBottom']} of {dims['win']})"
    assert dims["inner"] > dims["view"], \
        f"{who}: the sheet has nothing to scroll ({dims['inner']} <= {dims['view']}); pick a longer sheet"
    moved = page.evaluate("""() => {
        const box = document.querySelector('.wb-scroll')
        box.scrollTo(0, 900)
        const head = document.querySelector('.wb-sheet thead')
        return {top: box.scrollTop, doc: document.scrollingElement.scrollTop,
                head: head ? Math.round(head.getBoundingClientRect().top - box.getBoundingClientRect().top) : null}
    }""")
    assert moved["top"] > 0, f"{who}: the sheet did not scroll (scrollTop stayed 0)"
    assert moved["doc"] == 0, f"{who}: scrolling the sheet moved the document"
    if moved["head"] is not None:       # the sheet freezes its header rows
        assert abs(moved["head"]) <= 2, \
            f"{who}: the frozen header band left the top of the sheet ({moved['head']}px) after scrolling"
    # A test case row opens the panel docked beside the sheet, inside the window.
    row = page.locator(".wb-sheet tr.wb-tc").first
    if row.count():
        row.scroll_into_view_if_needed()
        row.locator("td").nth(1).click()
        page.wait_for_selector(".wb-body > .tc-panel, .wb-body > .wb-missing")
        assert page.locator(".wb-body > .tc-panel").count() == 1, \
            f"{who}: a test case row did not open the review panel"
        box = page.evaluate("""() => {
            const r = document.querySelector('.wb-body > .tc-panel').getBoundingClientRect()
            return {top: r.top, bottom: r.bottom, right: r.right,
                    w: window.innerWidth, h: window.innerHeight}
        }""")
        assert box["top"] >= 0 and box["bottom"] <= box["h"] + 1 and box["right"] <= box["w"] + 1, \
            f"{who}: the docked panel is not inside the window ({box})"
        assert page.evaluate("document.scrollingElement.scrollHeight") <= dims["win"] + 1, \
            f"{who}: opening the panel made the document scroll"
        page.screenshot(path=str(SHOTS / f"operator-workbook-{theme}{'-chat' if chat else ''}.png"))
        page.get_by_role("button", name="Close review panel").click()
        page.wait_for_selector(".wb-body > .tc-panel", state="detached")


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
                        _check_shell(page, theme, chat=False)
                        heading = page.locator(".page-head h1").inner_text()
                        assert heading == "Projects", f"{theme}: Projects heading missing/wrong -- {heading!r}"
                        assert page.locator(".proj-card").count() >= 1, f"{theme}: no project tiles rendered"

                        # The Test Cases grid and the Workbook view, in the
                        # default shell (chat Off), then again beside the chat.
                        _check_testcases(page, theme)
                        _check_workbook(page, theme)

                        # Chat is switched On where the operator switches it:
                        # Settings, Appearance, chat. The rest of the walk runs
                        # with the chat column docked.
                        page.get_by_role("button", name="Settings", exact=True).click()
                        page.wait_for_selector(".fm-field")
                        page.locator(".fm-field", has=page.locator("dt", has_text="chat")) \
                            .get_by_role("button", name="On", exact=True).click()
                        page.wait_for_selector(".chatcol")
                        _check_shell(page, theme, chat=True)
                        assert page.evaluate("localStorage.getItem('tc-chat-enabled')") == "1", \
                            f"{theme}: the chat switch was not remembered"
                        _check_workbook(page, theme, chat=True)

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

                        # A long ordinary page scrolls inside `.page`, never the
                        # document (the same height chain the Workbook view uses).
                        scroll = page.evaluate("""() => {
                            const pg = document.querySelector('.page')
                            return {doc: document.scrollingElement.scrollHeight,
                                    win: window.innerHeight,
                                    flow: getComputedStyle(pg).overflowY}
                        }""")
                        assert scroll["doc"] <= scroll["win"] + 1 and scroll["flow"] == "auto", \
                            f"{theme}: an ordinary page no longer scrolls inside itself ({scroll})"

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
