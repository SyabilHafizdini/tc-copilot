#!/usr/bin/env python3
"""The allowlist -- the app's ONLY write path.

Every UI intent maps to a fixed argv shape built here. Parameters are
validated against strict patterns and never interpolated into a string, so
the app cannot be talked into running a command that is not on this list.

Sub-project B ships read-only actions only. Mutating actions (assert,
card revise|discard, approve-cr, retire, void-ac, ...) arrive with the
decision surfaces in sub-project D, and each one must be added here with its
own validated builder -- never by relaxing these patterns.
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "tools"))
from wiki import load_config

# Deliberately strict: uppercase story ids and lowercase-hyphen flow slugs are
# the only shapes the wiki uses. Anything else -- shell metacharacters, path
# traversal, a stray flag -- fails to match and is refused.
STORY_RE = re.compile(r"^[A-Z0-9][A-Z0-9-]{1,31}$")
FLOW_RE = re.compile(r"^[a-z0-9][a-z0-9-]{1,63}$")

# Session ids are the shape cards carry: US-XXXX-001, coverage ids, etc.
SESSION_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9-]{1,63}$")

# Suite names are lowercase-hyphen slugs (sit-all, uat-<flow>).
SUITE_RE = re.compile(r"^[a-z0-9][a-z0-9-]{1,63}$")

# Workbook names are the operator's own label for an export. Must start with an
# alphanumeric (so ".." and leading-dot traversal are impossible) and contain
# only safe filename characters -- no slash, no backslash, no space, no shell
# metacharacter -- because the name flows into a filesystem path and an argv.
NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")


class ActionError(ValueError):
    """An action name or parameter that is not on the allowlist."""


def human():
    """The operator's signature, from config.yaml provenance.human."""
    who = ((load_config().get("provenance") or {}).get("human") or "").strip()
    if not who:
        raise ActionError(
            "config.yaml provenance.human is not set -- it is the signature "
            "every human-gated command is run under")
    return who


def _no_params(params):
    if params:
        raise ActionError(f"unexpected params: {sorted(params)}")


def _status(params):
    _no_params(params)
    return ["status"]


def _lint(params):
    _no_params(params)
    return ["lint"]


def _next(params):
    extra = set(params) - {"story"}
    if extra:
        raise ActionError(f"unexpected params: {sorted(extra)}")
    story = params.get("story")
    if story is None:
        return ["next", "--json"]
    if not isinstance(story, str):
        raise ActionError(f"invalid story id: {story!r}")
    if not STORY_RE.fullmatch(story):
        raise ActionError(f"invalid story id: {story!r}")
    return ["next", "--json", "--story", story]


def _gate(params):
    extra = set(params) - {"story", "flow"}
    if extra:
        raise ActionError(f"unexpected params: {sorted(extra)}")
    story, flow = params.get("story"), params.get("flow")
    if bool(story) == bool(flow):
        raise ActionError("gate needs exactly one of story or flow")
    if story:
        if not isinstance(story, str) or not STORY_RE.fullmatch(story):
            raise ActionError(f"invalid story id: {story!r}")
        return ["gate", "--story", story]
    if not isinstance(flow, str) or not FLOW_RE.fullmatch(flow):
        raise ActionError(f"invalid flow slug: {flow!r}")
    return ["gate", "--flow", flow]


def _export(params):
    extra = set(params) - {"story", "flow", "name", "draft"}
    if extra:
        raise ActionError(f"unexpected params: {sorted(extra)}")
    story, flow, name = params.get("story"), params.get("flow"), params.get("name")
    draft = params.get("draft", False)
    if not isinstance(name, str) or not NAME_RE.fullmatch(name):
        raise ActionError(f"invalid workbook name: {name!r}")
    if not isinstance(draft, bool):
        raise ActionError(f"draft must be true or false, got {draft!r}")
    if bool(story) == bool(flow):
        raise ActionError("export needs exactly one of story or flow")
    tail = ["--draft"] if draft else []
    if story:
        if not isinstance(story, str) or not STORY_RE.fullmatch(story):
            raise ActionError(f"invalid story id: {story!r}")
        return ["export", "--story", story, "--name", name] + tail
    if not isinstance(flow, str) or not FLOW_RE.fullmatch(flow):
        raise ActionError(f"invalid flow slug: {flow!r}")
    return ["export", "--flow", flow, "--name", name] + tail


QID_RE = re.compile(r"^Q\d+$")
CARD_NAME_RE = re.compile(r"^[A-Za-z0-9._-]+\.json$")
CARD_DIR = ROOT / "build/cards"


def _card_path(name):
    if not isinstance(name, str) or not CARD_NAME_RE.fullmatch(name):
        raise ActionError(f"invalid card filename: {name!r}")
    p = (CARD_DIR / name).resolve()
    if p.parent != CARD_DIR.resolve():
        raise ActionError(f"card escapes build/cards/: {name!r}")
    if not p.exists():
        raise ActionError(f"card not found: {name!r}")
    return f"build/cards/{name}"


def _assert(params):
    extra = set(params) - {"id", "card"}
    if extra:
        raise ActionError(f"unexpected params: {sorted(extra)}")
    ident, card = params.get("id"), params.get("card")
    if not isinstance(ident, str) or not STORY_RE.fullmatch(ident):
        raise ActionError(f"invalid story id: {ident!r}")
    return ["assert", "story", ident, "--by", human(), "--card", _card_path(card)]


def _card_revise(params):
    extra = set(params) - {"card", "answers", "note"}
    if extra:
        raise ActionError(f"unexpected params: {sorted(extra)}")
    rel = _card_path(params.get("card"))
    argv = ["card", "revise", rel, "--by", human()]
    answers = params.get("answers") or {}
    if not isinstance(answers, dict):
        raise ActionError(f"answers must be an object, got {type(answers).__name__}")
    for qid, value in answers.items():
        if not isinstance(qid, str) or not QID_RE.fullmatch(qid):
            raise ActionError(f"invalid question id: {qid!r}")
        if not isinstance(value, str):
            raise ActionError(f"answer value must be a string: {value!r}")
        argv += ["--answer", f"{qid}={value}"]
    note = params.get("note")
    if note is not None:
        if not isinstance(note, str):
            raise ActionError("note must be a string")
        argv += ["--note", note]
    return argv


def _card_discard(params):
    extra = set(params) - {"card", "note"}
    if extra:
        raise ActionError(f"unexpected params: {sorted(extra)}")
    argv = ["card", "discard", _card_path(params.get("card")), "--by", human()]
    note = params.get("note")
    if note is not None:
        if not isinstance(note, str):
            raise ActionError("note must be a string")
        argv += ["--note", note]
    return argv


def _session_revert(params):
    extra = set(params) - {"session"}
    if extra:
        raise ActionError(f"unexpected params: {sorted(extra)}")
    session = params.get("session")
    if not isinstance(session, str) or not SESSION_RE.fullmatch(session):
        raise ActionError(f"invalid session id: {session!r}")
    return ["session", "revert", session, "--by", human()]


def _suite_compile(params):
    extra = set(params) - {"name"}
    if extra:
        raise ActionError(f"unexpected params: {sorted(extra)}")
    name = params.get("name")
    if not isinstance(name, str) or not SUITE_RE.fullmatch(name):
        raise ActionError(f"invalid suite name: {name!r}")
    return ["suite", "compile", name]


MUTATING = {"assert", "card_revise", "card_discard", "session_revert", "export", "suite_compile"}

ALLOWLIST = {"status": _status, "lint": _lint, "gate": _gate, "next": _next,
             "assert": _assert, "card_revise": _card_revise,
             "card_discard": _card_discard, "session_revert": _session_revert,
             "export": _export, "suite_compile": _suite_compile}


def build(name, params=None):
    """Action name + params -> validated argv list. Raises ActionError."""
    if name not in ALLOWLIST:
        raise ActionError(
            f"action not on the allowlist: {name!r} "
            f"(allowed: {', '.join(sorted(ALLOWLIST))})")
    if params is not None and not isinstance(params, dict):
        raise ActionError(
            f"params must be a dict, got {type(params).__name__}: {params!r}")
    return ALLOWLIST[name](dict(params or {}))
