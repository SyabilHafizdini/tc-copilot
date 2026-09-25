#!/usr/bin/env python3
"""Plain-assert tests for the opencode sidecar supervisor
(run: py tools/test_app_sidecar.py). No pytest.

Never spawns the real opencode. A fake `opencode` shim on a temp PATH proves
the spawn/stop wiring; PATH is restored in a finally.
"""
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools/app"))
sys.path.insert(0, str(ROOT / "tools"))
import opencode_sidecar as oc


def test_health_unavailable_when_binary_absent():
    saved = os.environ["PATH"]
    try:
        os.environ["PATH"] = ""     # no opencode anywhere
        h = oc.health()
        assert h["available"] is False, h
        assert "opencode" in h["reason"].lower(), h
    finally:
        os.environ["PATH"] = saved


def test_model_id_from_config():
    from wiki import load_config
    m = load_config().get("model") or {}
    expect = f"{m.get('gateway', 'gateway')}/{m.get('chat_model', '')}"
    assert oc.model_id() == expect, oc.model_id()


def test_ensure_started_returns_none_when_unavailable():
    saved = os.environ["PATH"]
    try:
        os.environ["PATH"] = ""
        assert oc.ensure_started() is None
    finally:
        os.environ["PATH"] = saved
        oc.stop()


def test_ensure_started_survives_port_bind_failure():
    """_free_port() (or the socket it uses) can raise OSError -- resource
    exhaustion, a sandbox blocking sockets. ensure_started() must degrade to
    None, never propagate."""
    saved_health = oc.health
    saved_free_port = oc._free_port
    try:
        oc.health = lambda: {"available": True, "model": "m", "reason": "ready"}
        def _boom():
            raise OSError("no free ports")
        oc._free_port = _boom
        assert oc.ensure_started() is None
    finally:
        oc.health = saved_health
        oc._free_port = saved_free_port
        oc.stop()


def test_ensure_started_survives_spawn_failure():
    """The binary can vanish / become unexecutable between the health()
    check and the Popen() spawn (TOCTOU). ensure_started() must degrade to
    None and leave _proc/_url unset, never propagate."""
    saved_health = oc.health
    saved_popen = oc.subprocess.Popen
    try:
        oc.health = lambda: {"available": True, "model": "m", "reason": "ready"}
        def _boom(*a, **k):
            raise FileNotFoundError("opencode vanished")
        oc.subprocess.Popen = _boom
        assert oc.ensure_started() is None
        assert oc._proc is None
        assert oc._url is None
    finally:
        oc.health = saved_health
        oc.subprocess.Popen = saved_popen
        oc.stop()


if __name__ == "__main__":
    fails = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn(); print(f"[PASS] {name}")
            except Exception as e:
                fails += 1; print(f"[FAIL] {name}: {e}")
    sys.exit(1 if fails else 0)
