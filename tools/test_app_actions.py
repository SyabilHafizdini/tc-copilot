#!/usr/bin/env python3
"""Plain-assert tests for the app's write path
(run: py tools/test_app_actions.py). Matches the tools/smoke.py idiom -- no
pytest in this repo.

Argv construction is asserted WITHOUT spawning anything, so these tests can
never mutate the wiki. Exactly one test runs a real (read-only) command to
prove the runner wiring.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools/app"))
import actions
import runner

# actions.build() validates that the named card EXISTS under build/cards/.
# That directory is git-ignored, so naming a card left over from a previous
# session made this file pass only on a working copy that had run one -- a
# fresh clone had no build/cards/ at all and these tests died. The fixture is
# synthesised in __main__ instead, and removed afterwards.
CARD = "test-app-actions-fixture.json"
CARD_FILE = ROOT / "build/cards" / CARD


def test_allowlist_is_read_only_in_b():
    """B shipped read-only; D added card mutations; Plan 2 adds export (a writer)."""
    assert set(actions.ALLOWLIST) == {
        "status", "lint", "gate", "next", "assert", "card_revise",
        "card_discard", "session_revert", "export", "suite_compile"}, sorted(actions.ALLOWLIST)


def test_build_produces_argv_list_not_a_string():
    argv = actions.build("status", {})
    assert isinstance(argv, list) and all(isinstance(a, str) for a in argv), argv
    assert argv == ["status"], argv


def test_gate_requires_a_scope():
    try:
        actions.build("gate", {})
    except actions.ActionError as e:
        assert "story" in str(e) or "flow" in str(e), str(e)
    else:
        raise AssertionError("gate with no scope must raise ActionError")


def test_gate_story_argv():
    assert actions.build("gate", {"story": "US-VHLD"}) == ["gate", "--story", "US-VHLD"]


def test_unknown_action_is_refused():
    try:
        actions.build("rm-rf", {})
    except actions.ActionError as e:
        assert "rm-rf" in str(e), str(e)
    else:
        raise AssertionError("unknown action must raise ActionError")


def test_injection_attempts_are_refused():
    """Params are validated, never interpolated. Each of these must be refused."""
    for bad in ["US-VHLD; rm -rf /", "US-VHLD && echo x", "../../etc/passwd",
                "US-VHLD --allow-lint-errors", "US VHLD", "", "-rf"]:
        try:
            actions.build("gate", {"story": bad})
        except actions.ActionError:
            pass
        else:
            raise AssertionError(f"must refuse story id {bad!r}")


def test_no_extra_params_pass_through():
    """An unexpected key is a refusal, not something silently ignored."""
    try:
        actions.build("status", {"flags": "--force"})
    except actions.ActionError as e:
        assert "flags" in str(e), str(e)
    else:
        raise AssertionError("unexpected params must raise ActionError")


def test_human_signature_is_configured():
    who = actions.human()
    assert isinstance(who, str) and who.strip(), \
        "config.yaml provenance.human must be set"


def test_runner_returns_rc_stdout_stderr():
    """One real spawn, of a read-only command."""
    out = runner.run(["status"])
    assert set(out) == {"argv", "rc", "stdout", "stderr"}, out.keys()
    assert out["rc"] == 0, out
    assert out["stdout"].strip(), "status printed nothing"


def test_runner_surfaces_refusals_verbatim():
    """A blocked gate exits non-zero; its text must reach the caller unaltered."""
    out = runner.run(["gate", "--story", "US-81FRM"])
    assert out["rc"] != 0, out
    combined = out["stdout"] + out["stderr"]
    assert "GATE" in combined.upper(), combined


def test_gate_story_with_trailing_newline_is_refused():
    """Python's $ matches before a trailing \\n -- the regex must not."""
    try:
        actions.build("gate", {"story": "US-VHLD\n"})
    except actions.ActionError:
        pass
    else:
        raise AssertionError("story id with a trailing newline must be refused")


def test_gate_story_non_str_int_is_refused():
    """A non-str param must raise ActionError, never a bare TypeError."""
    try:
        actions.build("gate", {"story": 123})
    except actions.ActionError:
        pass
    else:
        raise AssertionError("non-str story id must be refused")


def test_gate_story_non_str_list_is_refused():
    """A non-str param must raise ActionError, never a bare TypeError."""
    try:
        actions.build("gate", {"story": ["US-VHLD"]})
    except actions.ActionError:
        pass
    else:
        raise AssertionError("non-str story id must be refused")


def test_status_params_non_dict_list_is_refused():
    """A non-dict params container must raise ActionError, never a bare ValueError."""
    try:
        actions.build("status", ["a", "b"])
    except actions.ActionError:
        pass
    else:
        raise AssertionError("non-dict params must be refused")


def test_status_params_non_dict_int_is_refused():
    """A non-dict params container must raise ActionError, never a bare TypeError."""
    try:
        actions.build("status", 5)
    except actions.ActionError:
        pass
    else:
        raise AssertionError("non-dict params must be refused")


def test_assert_builds_argv():
    argv = actions.build("assert", {"id": "US-VHLD", "card": CARD})
    assert argv[:3] == ["assert", "story", "US-VHLD"], argv
    assert "--by" in argv and "--card" in argv, argv
    assert argv[argv.index("--card") + 1] == f"build/cards/{CARD}", argv


def test_card_revise_expands_answers_to_repeated_flags():
    argv = actions.build("card_revise", {"card": CARD,
                                         "answers": {"Q1": "accept", "Q2": "fix it"},
                                         "note": "n"})
    assert argv[:2] == ["card", "revise"], argv
    pairs = [argv[i + 1] for i, a in enumerate(argv) if a == "--answer"]
    assert "Q1=accept" in pairs and "Q2=fix it" in pairs, pairs
    assert argv[argv.index("--note") + 1] == "n", argv


def test_card_discard_builds_argv():
    argv = actions.build("card_discard", {"card": CARD, "note": "x"})
    assert argv[:2] == ["card", "discard"], argv


def test_card_path_rejects_traversal_and_non_json():
    for bad in ("../wiki.py", "x.txt", "a/b.json", "sess ion.json"):
        try:
            actions.build("card_discard", {"card": bad})
            assert False, f"expected ActionError for {bad!r}"
        except actions.ActionError:
            pass


def test_assert_rejects_bad_story_id():
    try:
        actions.build("assert", {"id": "x; rm -rf /", "card": CARD})
        assert False, "expected ActionError"
    except actions.ActionError:
        pass


def test_card_revise_rejects_bad_qid():
    try:
        actions.build("card_revise", {"card": CARD,
                                      "answers": {"nope": "x"}})
        assert False, "expected ActionError for bad qid"
    except actions.ActionError:
        pass


def test_session_revert_argv():
    assert actions.build("session_revert", {"session": "US-VHLD-001"}) == \
        ["session", "revert", "US-VHLD-001", "--by", actions.human()]


def test_session_revert_is_mutating():
    assert "session_revert" in actions.MUTATING


def test_session_revert_rejects_bad_session_id():
    for bad in ["US-VHLD; rm -rf /", "../../etc", "US VHLD", "--flag", "", "x" * 80]:
        try:
            actions.build("session_revert", {"session": bad})
        except actions.ActionError:
            pass
        else:
            raise AssertionError(f"bad session id must be refused: {bad!r}")


def test_session_revert_requires_session():
    try:
        actions.build("session_revert", {})
    except actions.ActionError as e:
        assert "session" in str(e), str(e)
    else:
        raise AssertionError("session_revert with no session must raise")


def test_export_story_argv():
    assert actions.build("export", {"story": "US-VHLD", "name": "US-VHLD-sit"}) == \
        ["export", "--story", "US-VHLD", "--name", "US-VHLD-sit"]


def test_export_flow_argv():
    assert actions.build("export", {"flow": "vault-hold", "name": "vault-hold-uat"}) == \
        ["export", "--flow", "vault-hold", "--name", "vault-hold-uat"]


def test_export_is_on_the_allowlist_and_is_mutating():
    assert "export" in actions.ALLOWLIST
    assert "export" in actions.MUTATING, "export writes an xlsx + commits -> needs the write mutex"


def test_export_requires_a_name():
    try:
        actions.build("export", {"story": "US-VHLD"})
    except actions.ActionError as e:
        assert "name" in str(e), str(e)
    else:
        raise AssertionError("export with no name must raise ActionError")


def test_export_needs_exactly_one_scope():
    # both story and flow -> refused
    try:
        actions.build("export", {"story": "US-VHLD", "flow": "vault-hold", "name": "x"})
    except actions.ActionError as e:
        assert "one of" in str(e) or "story" in str(e), str(e)
    else:
        raise AssertionError("export with both story and flow must raise")
    # neither -> refused
    try:
        actions.build("export", {"name": "x"})
    except actions.ActionError:
        pass
    else:
        raise AssertionError("export with no scope must raise")


def test_export_rejects_bad_workbook_names():
    """A name is never interpolated; traversal, slashes, and metachars are refused."""
    for bad in ["../etc/passwd", "a/b", "a\\b", "..", ".hidden", "a;rm -rf /",
                "a b", "", "a&b", "-flag", "x" * 80]:
        try:
            actions.build("export", {"story": "US-VHLD", "name": bad})
        except actions.ActionError:
            pass
        else:
            raise AssertionError(f"bad workbook name must be refused: {bad!r}")


def test_export_rejects_bad_story_and_flow_ids():
    try:
        actions.build("export", {"story": "US-VHLD; rm -rf /", "name": "ok"})
    except actions.ActionError:
        pass
    else:
        raise AssertionError("bad story id must be refused")
    try:
        actions.build("export", {"flow": "Vault Hold", "name": "ok"})
    except actions.ActionError:
        pass
    else:
        raise AssertionError("bad flow slug must be refused")


def test_export_rejects_extra_params():
    try:
        actions.build("export", {"story": "US-VHLD", "name": "ok", "kind": "uat"})
    except actions.ActionError as e:
        assert "kind" in str(e), str(e)
    else:
        raise AssertionError("unexpected params must be refused")


def test_export_draft_flag_is_a_strict_boolean():
    assert actions.build("export", {"story": "US-1", "name": "n", "draft": True}) == \
        ["export", "--story", "US-1", "--name", "n", "--draft"]
    assert actions.build("export", {"story": "US-1", "name": "n", "draft": False}) == \
        ["export", "--story", "US-1", "--name", "n"]
    assert actions.build("export", {"flow": "f-e2e", "name": "n", "draft": True}) == \
        ["export", "--flow", "f-e2e", "--name", "n", "--draft"]
    for bad in ("true", 1, None):
        try:
            actions.build("export", {"story": "US-1", "name": "n", "draft": bad})
        except actions.ActionError:
            continue
        raise AssertionError(f"draft={bad!r} must be refused")


def test_suite_compile_argv():
    assert actions.build("suite_compile", {"name": "sit-vhld-p1"}) == \
        ["suite", "compile", "sit-vhld-p1"]


def test_suite_compile_is_on_the_allowlist_and_mutating():
    assert "suite_compile" in actions.ALLOWLIST
    assert "suite_compile" in actions.MUTATING  # compile writes build/inventory


def test_suite_compile_requires_a_name():
    try:
        actions.build("suite_compile", {})
    except actions.ActionError as e:
        assert "name" in str(e), str(e)
    else:
        raise AssertionError("suite_compile with no name must raise")


def test_suite_compile_rejects_bad_names():
    for bad in ["sit; rm -rf /", "../suites/x", "SIT-ALL", "sit all",
                "--graph", "", "a", "x" * 80, "sit\n"]:
        try:
            actions.build("suite_compile", {"name": bad})
        except actions.ActionError:
            pass
        else:
            raise AssertionError(f"bad suite name must be refused: {bad!r}")


def test_suite_compile_rejects_non_str_name():
    for bad in (123, ["sit-all"], None):
        try:
            actions.build("suite_compile", {"name": bad})
        except actions.ActionError:
            pass
        else:
            raise AssertionError(f"non-str suite name must be refused: {bad!r}")


def test_suite_compile_rejects_extra_params():
    try:
        actions.build("suite_compile", {"name": "sit-all", "graph": True})
    except actions.ActionError as e:
        assert "graph" in str(e), str(e)
    else:
        raise AssertionError("extra params must be refused")


if __name__ == "__main__":
    CARD_FILE.parent.mkdir(parents=True, exist_ok=True)
    CARD_FILE.write_text('{"id": "test-app-actions-fixture"}\n',
                         encoding="utf-8", newline="\n")
    try:
        for name, fn in sorted(globals().items()):
            if name.startswith("test_") and callable(fn):
                fn()
                print(f"[PASS] {name}")
    finally:
        CARD_FILE.unlink(missing_ok=True)
    print("test_app_actions OK")
