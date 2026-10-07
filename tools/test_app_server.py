#!/usr/bin/env python3
"""Plain-assert tests for the operator app's HTTP surface
(run: py tools/test_app_server.py). Matches the tools/smoke.py idiom -- no
pytest in this repo.

Requires FastAPI's TestClient (which itself needs an HTTP client package --
httpx2 on starlette 1.3.x, httpx on older starlette; see the comment in
tools/app/requirements.txt). smoke.py [SKIP]s this file when that import is
unavailable, the same way it guards the npm and bun suites, so the harness
never becomes runtime-dependent.

Uses fastapi.testclient, so nothing binds a real port.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

sys.path.insert(0, str(ROOT / "tools/app"))

try:
    from fastapi.testclient import TestClient
except (ImportError, RuntimeError) as e:
    # ImportError: fastapi itself is absent (older/plain "not installed" case).
    # RuntimeError: fastapi IS present but starlette.testclient's own HTTP
    # client dependency (httpx2 on starlette >=1.0, httpx on older starlette)
    # is missing -- starlette raises RuntimeError, not ImportError, for that
    # case (verified against the installed starlette 1.3.1's source), so both
    # must be caught here or this exact "requirements.txt only" install state
    # crashes instead of skipping.
    print(f"[SKIP] test_app_server ({e}) -- install the app's test extras: "
          f"py -m pip install -r tools/app/requirements.txt")
    sys.exit(0)

import server

# TestClient's default base_url is http://testserver, which would make every
# request carry Host: testserver -- now rejected by _host_ok (the app only
# accepts 127.0.0.1/localhost, the DNS-rebinding fix). Pointing the client at
# http://localhost instead makes its Host header match what a real browser
# talking to this app would send, and Origin below is set to agree with it.
CLIENT = TestClient(server.create_app(), base_url="http://localhost")
GOOD = {"X-TC-Token": server.TOKEN, "Origin": "http://localhost"}


def test_state_endpoint_returns_the_read_model():
    r = CLIENT.get("/api/state")
    assert r.status_code == 200, r.text
    body = r.json()
    assert "stories" in body and "next" in body, sorted(body)


def test_flow_builder_endpoint_returns_its_read_model():
    """The Flow Builder page stitches from this: stories, flows, test cases."""
    r = CLIENT.get("/api/flow_builder")
    assert r.status_code == 200, r.text
    assert {"stories", "flows", "tcs"} <= set(r.json()), sorted(r.json())
    assert CLIENT.get("/api/flow_builder", headers={"Host": "evil.example"}).status_code == 403


def test_flow_overview_export_is_a_standalone_download():
    r = CLIENT.get("/api/flow_overview.html")
    assert r.status_code == 200, r.text
    assert r.headers["content-type"].startswith("text/html")
    assert "attachment" in r.headers["content-disposition"]
    assert "window.__TC_FLOW_OVERVIEW__ = {" in r.text
    assert CLIENT.get("/api/flow_overview.html", headers={"Host": "evil.example"}).status_code == 403


def test_action_runs_and_reports_rc():
    r = CLIENT.post("/api/action/status", json={"params": {}}, headers=GOOD)
    assert r.status_code == 200, r.text
    assert r.json()["rc"] == 0, r.json()


def test_refusal_text_reaches_the_client_verbatim():
    """A blocked gate is the system working; the UI must see the CLI's words."""
    r = CLIENT.post("/api/action/gate", json={"params": {"story": "US-81FRM"}},
                    headers=GOOD)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["rc"] != 0, body
    assert "GATE" in (body["stdout"] + body["stderr"]).upper(), body


def test_unknown_action_is_rejected_with_400():
    r = CLIENT.post("/api/action/rm-rf", json={"params": {}}, headers=GOOD)
    assert r.status_code == 400, r.text
    assert "allowlist" in r.json()["error"], r.json()


def test_invalid_params_are_rejected_with_400():
    r = CLIENT.post("/api/action/gate", json={"params": {"story": "x; rm -rf /"}},
                    headers=GOOD)
    assert r.status_code == 400, r.text


def test_action_without_token_is_rejected():
    r = CLIENT.post("/api/action/status", json={"params": {}},
                    headers={"Origin": "http://testserver"})
    assert r.status_code == 403, r.text


def test_action_from_foreign_origin_is_rejected():
    """Any web page can POST to localhost; the Origin check is what stops it."""
    r = CLIENT.post("/api/action/status", json={"params": {}},
                    headers={"X-TC-Token": server.TOKEN,
                             "Origin": "https://evil.example"})
    assert r.status_code == 403, r.text


def test_reads_need_no_token():
    """GET /api/state is harmless and the page fetches it before bootstrapping."""
    assert CLIENT.get("/api/state").status_code == 200


def test_state_endpoint_rejects_spoofed_host():
    """DNS rebinding: a page on evil.example can rebind to 127.0.0.1 and send
    Host: evil.example, which this must reject regardless of Origin."""
    r = CLIENT.get("/api/state", headers={"Host": "evil.example"})
    assert r.status_code == 403, r.text


def test_token_endpoint_rejects_spoofed_host():
    r = CLIENT.get("/api/token", headers={"Host": "evil.example"})
    assert r.status_code == 403, r.text


def test_action_rejects_spoofed_host_even_with_matching_origin():
    """After a DNS rebind, Origin and Host can both say evil.example -- the
    same-origin comparison in _origin_ok would pass, so Host must be checked
    against the loopback allowlist independently."""
    r = CLIENT.post("/api/action/status", json={"params": {}},
                    headers={"X-TC-Token": server.TOKEN,
                             "Origin": "http://evil.example",
                             "Host": "evil.example"})
    assert r.status_code == 403, r.text


def test_state_endpoint_500s_on_system_exit():
    """read_models.state() calls wiki_next.collect_next(), which sys.exit()s
    when nothing matches -- inside a request handler that must not propagate
    SystemExit, since ASGI does not turn it into an HTTP error and it can take
    down the worker."""
    original = server.read_models.state

    def boom():
        raise SystemExit(1)

    server.read_models.state = boom
    try:
        r = CLIENT.get("/api/state")
        assert r.status_code == 500, r.text
        assert "error" in r.json(), r.json()
    finally:
        server.read_models.state = original


def test_state_endpoint_500s_on_unexpected_exception():
    """Malformed-wiki exceptions from load_all/collect must not crash the
    worker either -- they render as a 500 with the traceback, per this
    project's crash-visibility design for a localhost single-operator tool."""
    original = server.read_models.state

    def boom():
        raise RuntimeError("boom")

    server.read_models.state = boom
    try:
        r = CLIENT.get("/api/state")
        assert r.status_code == 500, r.text
        assert "boom" in r.text, r.text
    finally:
        server.read_models.state = original


def test_explorer_endpoint_returns_the_snapshot():
    r = CLIENT.get("/api/explorer")
    assert r.status_code == 200, r.text
    body = r.json()
    assert "tree" in body and "docs" in body and "graph" in body, sorted(body)


def test_explorer_endpoint_rejects_spoofed_host():
    r = CLIENT.get("/api/explorer", headers={"Host": "evil.example"})
    assert r.status_code == 403, r.text


def test_inbox_endpoint_returns_cards():
    r = CLIENT.get("/api/inbox")
    assert r.status_code == 200, r.text
    assert "cards" in r.json(), r.json()


def test_inbox_endpoint_rejects_spoofed_host():
    r = CLIENT.get("/api/inbox", headers={"Host": "evil.example"})
    assert r.status_code == 403, r.text


def test_mutating_action_serialised_by_lock():
    """A mutating action must acquire the write lock; a read action must not.
    We assert the lock exists and the mutating set names the writers."""
    import actions
    assert actions.MUTATING == {"assert", "card_revise", "card_discard", "session_revert",
                                "export", "suite_compile", "tc_edit", "flow_draft"}
    assert hasattr(server, "_write_lock")


def test_card_discard_refusal_is_verbatim():
    """A discard on a nonexistent card is refused by actions.build (400) --
    the allowlist is the boundary."""
    r = CLIENT.post("/api/action/card_discard",
                    json={"params": {"card": "does-not-exist.json"}}, headers=GOOD)
    assert r.status_code == 400, r.text
    assert "card not found" in r.json()["error"], r.json()


def test_chat_health_returns_availability():
    r = CLIENT.get("/api/chat/health")
    assert r.status_code == 200, r.text
    body = r.json()
    assert "available" in body and "reason" in body, body


def test_chat_prompt_requires_token():
    """POST body is flat (not {"params": ...}), matching the Task 6 frontend
    wrappers; a foreign Origin and no token must be rejected before the
    request ever reaches the sidecar."""
    r = CLIENT.post("/api/chat/prompt", json={"session": "x", "text": "hi"},
                    headers={"Origin": "https://evil.example"})
    assert r.status_code == 403, r.text


def test_chat_prompt_degrades_when_unavailable():
    """Force unavailability hermetically (no pytest monkeypatch in this repo)
    so this never spawns a real opencode process, regardless of whether the
    binary/httpx are present on the machine running the suite."""
    import opencode_sidecar
    saved = opencode_sidecar.ensure_started
    opencode_sidecar.ensure_started = lambda: None
    try:
        r = CLIENT.post("/api/chat/prompt", json={"session": "x", "text": "hi"},
                        headers=GOOD)
        assert r.status_code == 503, r.text
    finally:
        opencode_sidecar.ensure_started = saved


def test_projects_endpoint_returns_cards():
    r = CLIENT.get("/api/projects")
    assert r.status_code == 200, r.text
    body = r.json()
    assert "projects" in body and isinstance(body["projects"], list), body
    assert body["projects"], "expected at least the current repo"
    c = body["projects"][0]
    for k in ("id", "product", "branch", "phase", "counts", "next"):
        assert k in c, c


def test_projects_endpoint_rejects_spoofed_host():
    r = CLIENT.get("/api/projects", headers={"Host": "evil.example"})
    assert r.status_code == 403, r.text


def test_download_serves_xlsx_from_inventory():
    """A real xlsx under build/inventory/ downloads with the spreadsheet
    content-type and an attachment disposition."""
    inv = ROOT / "build/inventory/sit"
    inv.mkdir(parents=True, exist_ok=True)
    f = inv / "US-PLANTEST-sit-latest.xlsx"
    f.write_bytes(b"PK\x03\x04 not-a-real-xlsx-but-enough-for-the-route")
    try:
        r = CLIENT.get("/api/download/sit/US-PLANTEST-sit-latest.xlsx")
        assert r.status_code == 200, r.text
        assert r.headers["content-type"] == \
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", r.headers
        assert "attachment" in r.headers.get("content-disposition", ""), r.headers
        assert "US-PLANTEST-sit-latest.xlsx" in r.headers.get("content-disposition", ""), r.headers
    finally:
        f.unlink(missing_ok=True)


def test_download_missing_artifact_is_404():
    r = CLIENT.get("/api/download/sit/does-not-exist-plantest.xlsx")
    assert r.status_code == 404, r.text


def test_download_non_xlsx_is_404():
    """Only .xlsx artifacts are downloadable; an .md sibling is not served."""
    inv = ROOT / "build/inventory/sit"
    inv.mkdir(parents=True, exist_ok=True)
    f = inv / "US-PLANTEST-sit-latest.md"
    f.write_text("inventory md", encoding="utf-8")
    try:
        r = CLIENT.get("/api/download/sit/US-PLANTEST-sit-latest.md")
        assert r.status_code == 404, r.text
    finally:
        f.unlink(missing_ok=True)


def test_download_traversal_is_refused():
    """A path that resolves outside build/inventory/ must never be served."""
    for bad in ("sit/../../../tools/wiki.py",
                "..%2f..%2ftools%2fwiki.py",
                "sit/..%2f..%2f..%2ftools%2fwiki.py"):
        r = CLIENT.get(f"/api/download/{bad}")
        assert r.status_code == 404, (bad, r.status_code, r.text[:80])


def test_download_rejects_spoofed_host():
    r = CLIENT.get("/api/download/sit/anything.xlsx", headers={"Host": "evil.example"})
    assert r.status_code == 403, r.text


def test_suite_preview_endpoint_returns_a_count():
    r = CLIENT.post("/api/suite_preview", json={"filters": {"kind": "sit"}},
                    headers=GOOD)
    assert r.status_code == 200, r.text
    body = r.json()
    assert "count" in body and isinstance(body["count"], int), body
    assert body["count"] == len(body["ids"]), body


def test_suite_preview_endpoint_rejects_bad_filters_with_400():
    r = CLIENT.post("/api/suite_preview", json={"filters": {"kind": "nope"}},
                    headers=GOOD)
    assert r.status_code == 400, r.text


def test_suite_compile_action_wiring_refuses_bad_name_with_400():
    """The builder refuses a bad name before any subprocess spawns."""
    r = CLIENT.post("/api/action/suite_compile",
                    json={"params": {"name": "BAD NAME"}}, headers=GOOD)
    assert r.status_code == 400, r.text
    assert "suite name" in r.json().get("error", ""), r.json()


def test_testcases_endpoint_returns_rows_and_groups():
    r = CLIENT.get("/api/testcases")
    assert r.status_code == 200, r.text
    body = r.json()
    assert set(body) == {"rows", "groups"}, sorted(body)
    assert isinstance(body["rows"], list) and isinstance(body["groups"], list)


def test_testcases_endpoint_rejects_spoofed_host():
    r = CLIENT.get("/api/testcases", headers={"Host": "evil.example"})
    assert r.status_code == 403, r.text


def test_testcases_endpoint_500s_instead_of_crashing_the_worker():
    original = server.testcase_models.testcases

    def boom():
        raise SystemExit("spec unreadable")

    server.testcase_models.testcases = boom
    try:
        r = CLIENT.get("/api/testcases")
        assert r.status_code == 500 and "error" in r.json(), r.text
    finally:
        server.testcase_models.testcases = original


def test_tc_edit_action_refuses_a_non_editable_field_with_400():
    """The allowlist is the boundary: nothing spawns and no file is written."""
    r = CLIENT.post("/api/action/tc_edit",
                    json={"params": {"id": "1.1-AC02-01", "field": "confidence",
                                     "text": "High"}}, headers=GOOD)
    assert r.status_code == 400, r.text
    assert "field not editable" in r.json()["error"], r.json()


def test_tc_edit_action_needs_the_token():
    r = CLIENT.post("/api/action/tc_edit",
                    json={"params": {"id": "1.1-AC02-01", "field": "steps", "text": "x"}},
                    headers={"Origin": "http://localhost"})
    assert r.status_code == 403, r.text


def _with_workbook_inventory(fn):
    """Run fn() with the workbook model pointed at a temp inventory holding one
    real workbook, one corrupt .xlsx, one .md, and a real workbook OUTSIDE the
    inventory. Nothing is written under build/."""
    import shutil
    import tempfile
    from openpyxl import Workbook
    wm = server.workbook_model
    tmp = Path(tempfile.mkdtemp(prefix="wbv-srv-"))
    saved = wm.INVENTORY_DIR
    wm.INVENTORY_DIR = tmp / "inventory"
    wm._CACHE.clear()
    try:
        sit = wm.INVENTORY_DIR / "sit"
        sit.mkdir(parents=True)
        wb = Workbook()
        wb.active.title = "S"
        wb.active["A1"] = "hello"
        wb.save(sit / "US-PLANTEST-wbv-latest.xlsx")
        (sit / "broken-latest.xlsx").write_bytes(b"PK\x03\x04 nope")
        (sit / "notes.md").write_text("x", encoding="utf-8")
        shutil.copyfile(sit / "US-PLANTEST-wbv-latest.xlsx", tmp / "outside.xlsx")
        return fn()
    finally:
        wm.INVENTORY_DIR = saved
        wm._CACHE.clear()
        shutil.rmtree(tmp, ignore_errors=True)


def test_workbook_endpoint_returns_the_read_model():
    def check():
        r = CLIENT.get("/api/workbook/sit/US-PLANTEST-wbv-latest.xlsx")
        assert r.status_code == 200, r.text
        body = r.json()
        for key in ("name", "file", "kind", "compiled_at", "source", "freshness",
                    "changed_count", "versions", "sheets", "links"):
            assert key in body, sorted(body)
        assert body["name"] == "US-PLANTEST-wbv" and body["kind"] == "sit", body["name"]
        assert body["freshness"] == "unknown" and body["sheets"][0]["name"] == "S"
        assert body["sheets"][0]["rows"][0]["cells"][0]["runs"] == \
            [{"text": "hello", "bold": False}], body["sheets"][0]["rows"][0]
    _with_workbook_inventory(check)


def test_workbook_endpoint_404s_missing_non_xlsx_and_traversal():
    """Same rule as /api/download: only an existing .xlsx under the inventory."""
    def check():
        for bad in ("sit/missing-latest.xlsx", "sit/notes.md",
                    "sit/..%2f..%2foutside.xlsx", "../outside.xlsx",
                    "%2e%2e/outside.xlsx", "sit/../../outside.xlsx"):
            r = CLIENT.get(f"/api/workbook/{bad}")
            assert r.status_code == 404, (bad, r.status_code, r.text[:80])
    _with_workbook_inventory(check)


def test_workbook_endpoint_422s_an_unreadable_file():
    def check():
        r = CLIENT.get("/api/workbook/sit/broken-latest.xlsx")
        assert r.status_code == 422, r.text
        assert "cannot read broken-latest.xlsx" in r.json()["error"], r.json()
    _with_workbook_inventory(check)


def test_workbook_endpoint_rejects_spoofed_host():
    r = CLIENT.get("/api/workbook/sit/anything-latest.xlsx",
                   headers={"Host": "evil.example"})
    assert r.status_code == 403, r.text


def test_workbook_endpoint_500s_on_unexpected_exception():
    original = server.workbook_model.workbook

    def boom(kind, file):
        raise RuntimeError("boom")

    server.workbook_model.workbook = boom
    try:
        r = CLIENT.get("/api/workbook/sit/x-latest.xlsx")
        assert r.status_code == 500, r.text
        assert "boom" in r.text, r.text
    finally:
        server.workbook_model.workbook = original


def test_workbooks_endpoint_lists_the_inventory():
    def check():
        r = CLIENT.get("/api/workbooks")
        assert r.status_code == 200, r.text
        names = [w["name"] for w in r.json()["workbooks"]]
        assert names == ["US-PLANTEST-wbv"], names      # the corrupt file is skipped
        w = r.json()["workbooks"][0]
        for key in ("name", "file", "kind", "compiled_at", "source", "freshness",
                    "changed_count", "versions", "tcs"):
            assert key in w, sorted(w)
    _with_workbook_inventory(check)


def test_workbooks_endpoint_rejects_spoofed_host():
    r = CLIENT.get("/api/workbooks", headers={"Host": "evil.example"})
    assert r.status_code == 403, r.text


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"[PASS] {name}")
    print("test_app_server OK")
