#!/usr/bin/env python3
"""FastAPI surface for the operator app.

Reads are in-process; writes are subprocesses through actions.py + runner.py,
so every fence in tools/wiki.py applies unchanged and a refusal renders in the
UI exactly as it does in a terminal.

Binds 127.0.0.1 only. Any web page in the browser can POST to localhost, so
action endpoints require both a same-origin Origin header and a token minted
at startup. Reads are unauthenticated: they are side-effect free, and the page
needs them to bootstrap.
"""
import asyncio
import json
import re
import secrets
import sys
import traceback
import webbrowser
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import (FileResponse, JSONResponse, PlainTextResponse,
                               Response, StreamingResponse)

sys.path.insert(0, str(Path(__file__).resolve().parent))
import actions
import explorer_models
import opencode_sidecar
import read_models
import runner
import watcher

try:
    import httpx
except ImportError:
    httpx = None

ROOT = Path(__file__).resolve().parent.parent.parent
BUNDLE = ROOT / "tools/app/web/dist-app/index.html"
INVENTORY_DIR = ROOT / "build/inventory"
XLSX_MEDIA = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"

TOKEN = secrets.token_urlsafe(32)
POLL_SECONDS = 1.0

_write_lock = asyncio.Lock()


_HOST_RE = re.compile(r"^(127\.0\.0\.1|localhost)(:\d+)?$")


def _host_ok(request):
    """DNS rebinding guard: a page on evil.com can rebind its own hostname to
    127.0.0.1, so the browser sends Origin: http://evil.com:<port> AND
    Host: evil.com:<port> -- those match each other, so a same-origin check
    that only compares Origin against Host (see _origin_ok below) passes even
    though the request is not actually same-origin with this server. Pinning
    Host itself to the loopback names this server is reachable at closes that
    hole regardless of what Origin claims."""
    return bool(_HOST_RE.fullmatch(request.headers.get("host", "")))


def _origin_ok(request):
    origin = request.headers.get("origin")
    if origin is None:      # non-browser client (curl, tests without Origin)
        return True
    host = request.headers.get("host", "")
    return origin in (f"http://{host}", f"https://{host}")


def _crash_response(exc):
    """A localhost single-operator tool shows crashes rather than swallowing
    them: SystemExit (e.g. wiki_next.collect_next() sys.exit()ing on no
    matches) and any unexpected exception from load_all/collect become an
    HTTP 500 carrying the full traceback, instead of taking down the ASGI
    worker or vanishing into a generic error page."""
    return JSONResponse(
        {"error": f"{type(exc).__name__}: {exc}",
         "traceback": traceback.format_exc()},
        status_code=500)


@asynccontextmanager
async def _lifespan(app):
    yield
    opencode_sidecar.stop()


def create_app():
    app = FastAPI(title="tc-copilot operator app", docs_url=None, redoc_url=None,
                   lifespan=_lifespan)

    def _chat_guard(request):
        # Chat writes carry the same fence as every other write: loopback Host,
        # same-origin, and the startup token. Reads use _host_ok directly.
        return (_host_ok(request)
                and _origin_ok(request)
                and request.headers.get("x-tc-token") == TOKEN)

    @app.get("/api/token")
    def token(request: Request):
        if not _host_ok(request):
            return JSONResponse({"error": "forbidden"}, status_code=403)
        return {"token": TOKEN}

    @app.get("/api/state")
    def state(request: Request):
        if not _host_ok(request):
            return JSONResponse({"error": "forbidden"}, status_code=403)
        try:
            return read_models.state()
        except (SystemExit, Exception) as e:
            return _crash_response(e)

    @app.get("/api/explorer")
    def explorer(request: Request):
        if not _host_ok(request):
            return JSONResponse({"error": "forbidden"}, status_code=403)
        try:
            return explorer_models.explorer()
        except (SystemExit, Exception) as e:
            return _crash_response(e)

    @app.get("/api/inbox")
    def inbox(request: Request):
        if not _host_ok(request):
            return JSONResponse({"error": "forbidden"}, status_code=403)
        try:
            return read_models.inbox()
        except (SystemExit, Exception) as e:
            return _crash_response(e)

    @app.get("/api/download/{artifact:path}")
    def download(artifact: str, request: Request):
        if not _host_ok(request):
            return JSONResponse({"error": "forbidden"}, status_code=403)
        base = INVENTORY_DIR.resolve()
        target = (base / artifact).resolve()
        # resolve() collapses any '..' first, so a single containment check
        # after resolving is traversal-safe regardless of how the path was
        # spelled. Only existing .xlsx files under build/inventory/ are served.
        if (not target.is_relative_to(base)
                or not target.is_file()
                or target.suffix != ".xlsx"):
            return JSONResponse({"error": "not found"}, status_code=404)
        return FileResponse(target, media_type=XLSX_MEDIA, filename=target.name)

    @app.get("/api/projects")
    def projects(request: Request):
        if not _host_ok(request):
            return JSONResponse({"error": "forbidden"}, status_code=403)
        try:
            return read_models.projects()
        except (SystemExit, Exception) as e:
            return _crash_response(e)

    @app.post("/api/suite_preview")
    async def suite_preview(request: Request):
        if not _host_ok(request) or not _origin_ok(request):
            return JSONResponse({"error": "forbidden"}, status_code=403)
        try:
            body = await request.json()
        except Exception:
            body = {}
        try:
            return read_models.suite_preview((body or {}).get("filters") or {})
        except ValueError as e:
            return JSONResponse({"error": str(e)}, status_code=400)
        except (SystemExit, Exception) as e:
            return _crash_response(e)

    @app.post("/api/action/{name}")
    async def action(name: str, request: Request):
        if (not _host_ok(request) or not _origin_ok(request)
                or request.headers.get("x-tc-token") != TOKEN):
            return JSONResponse({"error": "forbidden"}, status_code=403)
        try:
            body = await request.json()
        except Exception:
            body = {}
        try:
            argv = actions.build(name, (body or {}).get("params") or {})
            # runner.run() is a blocking subprocess.run(); running it on a
            # worker thread keeps the event loop free so SSE ticks and other
            # requests are not stalled for the duration of the subprocess.
            if name in actions.MUTATING:
                async with _write_lock:
                    return await asyncio.to_thread(runner.run, argv)
            return await asyncio.to_thread(runner.run, argv)
        except actions.ActionError as e:
            return JSONResponse({"error": str(e)}, status_code=400)
        except (SystemExit, Exception) as e:
            return _crash_response(e)

    @app.get("/api/events")
    async def events():
        async def stream():
            seen = watcher.snapshot()
            yield f"data: {json.dumps({'changed': False})}\n\n"
            while True:
                await asyncio.sleep(POLL_SECONDS)
                fired, seen = await asyncio.to_thread(watcher.changed, seen)
                if fired:
                    yield f"data: {json.dumps({'changed': True})}\n\n"
        return StreamingResponse(stream(), media_type="text/event-stream")

    @app.get("/api/chat/health")
    def chat_health(request: Request):
        if not _host_ok(request):
            return JSONResponse({"error": "forbidden"}, status_code=403)
        return opencode_sidecar.health()

    @app.post("/api/chat/session")
    async def chat_session(request: Request):
        if not _chat_guard(request):
            return JSONResponse({"error": "forbidden"}, status_code=403)
        base = opencode_sidecar.ensure_started()
        if base is None:
            return JSONResponse(opencode_sidecar.health(), status_code=503)
        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.post(f"{base}/session", json={})
            return JSONResponse(r.json() if r.content else {}, status_code=r.status_code)

    @app.get("/api/chat/session/{sid}/message")
    async def chat_messages(sid: str, request: Request):
        if not _host_ok(request):
            return JSONResponse({"error": "forbidden"}, status_code=403)
        base = opencode_sidecar.base_url()
        if base is None:
            return JSONResponse([], status_code=200)
        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.get(f"{base}/session/{sid}/message")
            return JSONResponse(r.json(), status_code=r.status_code)

    @app.post("/api/chat/prompt")
    async def chat_prompt(request: Request):
        if not _chat_guard(request):
            return JSONResponse({"error": "forbidden"}, status_code=403)
        base = opencode_sidecar.ensure_started()
        if base is None:
            return JSONResponse(opencode_sidecar.health(), status_code=503)
        body = await request.json()
        sid, text = body.get("session"), body.get("text") or ""
        # Do NOT force a model. config.yaml's model.* names the *production
        # target* (tc-copilot-spec §14: "local development runs under whatever
        # harness invokes the skills") -- the config's chat_model may not be
        # the id the gateway exposes, so it is not necessarily the model the
        # operator's local opencode is configured with. Sending a modelID
        # opencode cannot resolve makes the prompt fail silently after a 204.
        # Omitting the model lets opencode use its own configured default
        # agent/model, which is what the operator actually has provisioned.
        payload = {"parts": [{"type": "text", "text": text}]}
        async with httpx.AsyncClient(timeout=None) as client:
            r = await client.post(f"{base}/session/{sid}/prompt_async", json=payload)
            # opencode returns 204 No Content on accept. A 204 (or any empty
            # body) must NOT carry a response body -- h11 raises
            # "Too much data for declared Content-Length" under real uvicorn.
            # Relay a JSON body only when the sidecar actually sent one.
            if r.content:
                return JSONResponse(r.json(), status_code=r.status_code)
            return Response(status_code=r.status_code)

    @app.post("/api/chat/abort")
    async def chat_abort(request: Request):
        if not _chat_guard(request):
            return JSONResponse({"error": "forbidden"}, status_code=403)
        base = opencode_sidecar.base_url()
        if base is None:
            return JSONResponse({"ok": False}, status_code=503)
        sid = (await request.json()).get("session")
        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.post(f"{base}/session/{sid}/abort")
            # Our own summary body -- return it as 200, never propagate the
            # sidecar's 204 (a 204 must carry no body).
            return JSONResponse({"ok": r.status_code < 400})

    @app.post("/api/chat/permission")
    async def chat_permission(request: Request):
        if not _chat_guard(request):
            return JSONResponse({"error": "forbidden"}, status_code=403)
        base = opencode_sidecar.base_url()
        if base is None:
            return JSONResponse({"ok": False}, status_code=503)
        body = await request.json()
        sid, pid, resp = body.get("session"), body.get("permission"), body.get("response")
        if resp not in ("once", "always", "reject"):
            return JSONResponse({"error": "bad response"}, status_code=400)
        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.post(
                f"{base}/session/{sid}/permissions/{pid}", json={"response": resp})
            # Our own summary body -- return as 200; the sidecar replies 204.
            return JSONResponse({"ok": r.status_code < 400})

    @app.get("/api/chat/event")
    async def chat_event(request: Request):
        if not _host_ok(request):
            return JSONResponse({"error": "forbidden"}, status_code=403)
        base = opencode_sidecar.base_url()
        if base is None:
            async def empty():
                yield "data: {\"type\":\"unavailable\"}\n\n"
            return StreamingResponse(empty(), media_type="text/event-stream")

        async def relay():
            async with httpx.AsyncClient(timeout=None) as client:
                async with client.stream("GET", f"{base}/event") as r:
                    async for line in r.aiter_lines():
                        # opencode already emits SSE framing; pass it through.
                        yield line + "\n"
        return StreamingResponse(relay(), media_type="text/event-stream")

    @app.get("/")
    def index():
        if not BUNDLE.exists():
            return PlainTextResponse(
                "App bundle missing: tools/app/web/dist-app/index.html\n"
                "Rebuild with: cd tools/app/web && npm run build:app",
                status_code=503)
        return FileResponse(BUNDLE)

    return app


def serve(port=8765, open_browser=True):
    import uvicorn
    url = f"http://127.0.0.1:{port}/"
    print(f"tc-copilot operator app: {url}")
    print(f"  operator: {actions.human()}")
    if not BUNDLE.exists():
        print("  WARNING: app bundle missing — rebuild with "
              "`cd tools/app/web && npm run build:app`")
    if open_browser:
        webbrowser.open(url)
    uvicorn.run(create_app(), host="127.0.0.1", port=port, log_level="warning")
