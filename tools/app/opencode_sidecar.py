#!/usr/bin/env python3
"""Supervises a single `opencode serve` sidecar for the operator app.

Reads are in-process; writes are wiki.py subprocesses; the AGENT is this
sidecar -- a child process the app spawns lazily, proxies to (server.py), and
kills on shutdown. It is never exposed to the browser.

A missing `opencode` binary or a missing `httpx` is an "unavailable" state,
never a crash: chat degrades to a clipboard handoff and the app stays fully
usable on its read/decision surfaces. Likewise a port bind failure or a
failed spawn is reported as "unavailable" (None), never an exception.
"""
import shutil
import socket
import subprocess
import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from wiki import load_config

try:
    import httpx
except ImportError:
    httpx = None

_proc = None
_url = None
_lock = threading.Lock()  # serializes the check-and-spawn section of
                           # ensure_started() so concurrent callers (Task 5
                           # will call this from request handlers) can't
                           # both pass the "not running" check and spawn
                           # two sidecars.


def model_id():
    m = load_config().get("model") or {}
    return f"{m.get('gateway', 'gateway')}/{m.get('chat_model', '')}"


def _binary():
    return shutil.which("opencode")


def health():
    if _binary() is None:
        return {"available": False, "model": model_id(),
                "reason": "the `opencode` binary is not on PATH -- install it "
                          "to chat here, or use your own terminal"}
    if httpx is None:
        return {"available": False, "model": model_id(),
                "reason": "python httpx is not installed (pip install -r "
                          "tools/app/requirements.txt) -- chat proxy needs it"}
    return {"available": True, "model": model_id(),
            "reason": "running" if _proc else "ready"}


def _free_port():
    """Bind a free loopback port and return it, or None on failure (e.g.
    resource exhaustion, a sandbox blocking sockets). Never raises."""
    s = None
    try:
        s = socket.socket()
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]
    except OSError:
        return None
    finally:
        if s is not None:
            try:
                s.close()
            except OSError:
                pass


def base_url():
    return _url


def ensure_started():
    """Idempotent. Spawn opencode serve if not running; return its base URL,
    or None when unavailable. Never raises."""
    global _proc, _url
    if not health()["available"]:
        return None
    with _lock:
        if _proc and _proc.poll() is None:
            return _url
        try:
            port = _free_port()
        except OSError:
            port = None
        if port is None:
            return None
        root = Path(__file__).resolve().parent.parent.parent
        try:
            _proc = subprocess.Popen(
                [_binary(), "serve", "--hostname", "127.0.0.1", "--port", str(port)],
                cwd=root, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        except OSError:
            # Binary vanished / became unexecutable between the health()
            # check above and this spawn (TOCTOU) -- degrade, don't crash.
            _proc, _url = None, None
            return None
        _url = f"http://127.0.0.1:{port}"
        # Wait for readiness: poll the sidecar until it answers or we time out.
        deadline = time.monotonic() + 20
        while time.monotonic() < deadline:
            if _proc.poll() is not None:            # died on startup
                _proc, _url = None, None
                return None
            try:
                httpx.get(f"{_url}/config", timeout=0.5)
                return _url
            except Exception:
                time.sleep(0.2)
        stop()
        return None


def stop():
    global _proc, _url
    if _proc and _proc.poll() is None:
        _proc.terminate()
        try:
            _proc.wait(timeout=5)
        except Exception:
            _proc.kill()
    _proc, _url = None, None
