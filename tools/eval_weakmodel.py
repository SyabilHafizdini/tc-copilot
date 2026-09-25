#!/usr/bin/env python3
"""Weak-model behavioural eval for the tc-copilot skills and CLI.

Answers the question this branch was built to answer: do the changes actually
make a weaker driving model more accurate? Drives the configured model directly
over the OpenAI-compatible API -- no opencode in the loop, so the measurement
isolates the skills/CLI rather than the harness.

Three A/B measurements:
  routing      does it pick the right skill?   A = pre-change descriptions
                                               B = current descriptions
  next_action  does it pick the right command? A = raw `wiki status` row
                                               B = `wiki next` block (what the
                                                   opencode plugin injects)
  refusal      when the CLI refuses, does it take the remedy or bypass it?
               (single condition -- measures whether refusal text is actionable)

Scoring is deterministic string matching. Every prompt constrains the model to
a one-line answer; there is no LLM judge anywhere in this file.

!! THIS CALLS A REAL MODEL AND COSTS TOKENS. It is deliberately NOT wired into
   smoke.py. The platform itself stays LLM-free (spec P1/P5); this evaluator
   evaluates the model, not the platform.

Requires TC_EVAL_BASE_URL (the gateway's OpenAI-compatible chat-completions
endpoint) and TC_EVAL_MODEL (the model id that gateway exposes) in the
environment -- there is no default gateway or model; a silent default would
measure whichever one happened to be configured rather than the one the
caller intends.

Usage:
    TC_EVAL_BASE_URL=https://your-gateway/v1/chat/completions \
    TC_EVAL_MODEL=your-model-id \
    py tools/eval_weakmodel.py [--trials N] [--only routing|next_action|refusal]
                               [--workers N] [--json OUT.json]
"""
import argparse
import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
SCENARIOS = ROOT / "eval/weakmodel/scenarios.yaml"
KEY_FILE = Path(os.path.expanduser("~/.config/opencode/tc-eval-key"))

# The commit before the skill-description rewrite. Condition A reads the
# descriptions as they were; condition B reads them as they are now.
PRE_CHANGE_REF = "d31267e^"

SKILLS = ["tc-align", "tc-generate-sit", "tc-generate-uat", "tc-suite-author",
          "tc-style", "tc-lifecycle", "tc-change-report", "tc-correct",
          "run-tc-copilot"]


# ------------------------------------------------------------------ model I/O

def api_key():
    if not KEY_FILE.exists():
        sys.exit(f"eval: no API key at {KEY_FILE}")
    k = KEY_FILE.read_text(encoding="utf-8").strip()
    if not k.startswith("sk-"):
        sys.exit("eval: key must be the bare sk-... token. Some gateways "
                 "prefix the stored key with an account id that must be "
                 "stripped before it is used as the Authorization header.")
    return k


def gateway_config():
    """(base_url, model) from the environment. Both are required -- see the
    module docstring for why there is no default."""
    base_url, model = os.environ.get("TC_EVAL_BASE_URL"), os.environ.get("TC_EVAL_MODEL")
    if not base_url or not model:
        sys.exit("eval: set TC_EVAL_BASE_URL and TC_EVAL_MODEL (both "
                 "required; see the module docstring for an example).")
    return base_url, model


def ask(key, prompt, base_url, model, max_tokens=16000, timeout=600, retries=2):
    """One completion. Returns the assistant's text, or a __...__ error marker.

    This is a REASONING model: it spends most of its budget in a `reasoning`
    field and only then emits `content`. If the budget runs out first it returns
    content=None with finish_reason='length'.

    Truncation is reported as __TRUNCATED__ and excluded from scoring rather
    than counted as a wrong answer -- scoring an unfinished response as a
    failure would measure the token budget, not the model.
    """
    body = json.dumps({
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": max_tokens,
        "temperature": 0,
    }).encode()

    # Retry 5xx/timeouts. The gateway 504s on long reasoning, and that loss is
    # NOT random: the conditions that give the model least context make it think
    # longest, so they time out most. An un-retried run silently deletes exactly
    # the arm you are trying to measure -- a first pass here lost 100% of one
    # condition and would have reported the survivor's score as a result.
    last = "__ERR__ no attempt"
    for attempt in range(retries + 1):
        req = urllib.request.Request(
            base_url, data=body,
            headers={"Authorization": "Bearer " + key,
                     "Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                d = json.loads(r.read())
            ch = d["choices"][0]
            text = (ch["message"].get("content") or "").strip()
            used = (d.get("usage") or {}).get("completion_tokens")
            if not text:
                if ch.get("finish_reason") == "length":
                    return "__TRUNCATED__ reasoning consumed the whole budget", used
                return "__EMPTY__ model returned no content", used
            return text, used
        except urllib.error.HTTPError as e:
            last = f"__HTTP_{e.code}__ " + e.read(200).decode("utf-8", "replace")
            if e.code < 500:
                return last, None
        except Exception as e:
            last = f"__ERR__ {type(e).__name__}: {e}"
        if attempt < retries:
            time.sleep(4 * (attempt + 1))
    return last, None


ERROR_MARKERS = ("__HTTP_", "__ERR__", "__TRUNCATED__", "__EMPTY__")


def failed(reply):
    return reply is None or reply.startswith(ERROR_MARKERS)


# ------------------------------------------------------------------ fixtures

def descriptions(ref=None):
    """{skill: description} either from the working tree (ref=None) or a git ref."""
    out = {}
    for s in SKILLS:
        rel = f".claude/skills/{s}/SKILL.md"
        if ref:
            r = subprocess.run(["git", "show", f"{ref}:{rel}"], cwd=ROOT,
                               capture_output=True, text=True, encoding="utf-8")
            text = r.stdout
        else:
            text = (ROOT / rel).read_text(encoding="utf-8")
        m = re.search(r"^description:\s*(.+?)$", text, re.M)
        if m:
            out[s] = m.group(1).strip()
    return out


# ------------------------------------------------------------------ prompts

def routing_prompt(descs, request):
    listing = "\n".join(f"- {k}: {v}" for k, v in descs.items())
    return (
        "You are an agent working in a test-case authoring repo. These skills "
        "are available:\n\n" + listing + "\n\n"
        "The user says:\n\"" + request.strip() + "\"\n\n"
        "Which ONE skill do you invoke? Reply with only the skill name, exactly "
        "as written above. No explanation, no punctuation."
    )


def next_action_prompt(block, is_next):
    kind = ("the output of `py tools/wiki.py next`"
            if is_next else "a row from `py tools/wiki.py status`")
    return (
        "You are an agent driving the tc-copilot platform. Here is " + kind +
        ":\n\n" + block.strip() + "\n\n"
        "What is the single next thing you should do? Reply with only the one "
        "shell command you would run, or only the skill name if the next step "
        "is a skill rather than a command. One line, nothing else."
    )


def refusal_prompt(refusal):
    return (
        "You are an agent driving the tc-copilot platform. You ran a command "
        "and it refused:\n\n" + refusal.strip() + "\n\n"
        "What do you do next? Reply with only the one shell command you would "
        "run next, or a one-line description of the single action you take. "
        "One line, nothing else."
    )


# ------------------------------------------------------------------ scoring

def score_routing(reply, expect):
    got = reply.strip().strip("`\"'.").split("\n")[0].strip()
    return got == expect, got


def score_contains(reply, needle):
    return needle.lower() in reply.lower(), reply.strip().split("\n")[0][:70]


def score_refusal(reply, correct, bypass):
    low = reply.lower()
    if any(b.lower() in low for b in bypass):
        return "BYPASS", reply.strip().split("\n")[0][:70]
    if any(c.lower() in low for c in correct):
        return "CORRECT", reply.strip().split("\n")[0][:70]
    return "OTHER", reply.strip().split("\n")[0][:70]


# ------------------------------------------------------------------ runner

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--trials", type=int, default=3)
    ap.add_argument("--only", choices=["routing", "next_action", "refusal"])
    ap.add_argument("--workers", type=int, default=3)
    ap.add_argument("--json", dest="json_out")
    args = ap.parse_args()

    key = api_key()
    base_url, model = gateway_config()
    sc = yaml.safe_load(SCENARIOS.read_text(encoding="utf-8"))
    jobs = []

    if args.only in (None, "routing"):
        before, after = descriptions(PRE_CHANGE_REF), descriptions()
        if len(before) < len(SKILLS):
            print(f"[warn] only {len(before)}/{len(SKILLS)} pre-change "
                  f"descriptions found at {PRE_CHANGE_REF}", file=sys.stderr)
        for item in sc["routing"]:
            for cond, descs in (("A_before", before), ("B_after", after)):
                for t in range(args.trials):
                    jobs.append(("routing", item["id"], cond, t,
                                 routing_prompt(descs, item["request"]), item))

    if args.only in (None, "next_action"):
        for item in sc["next_action"]:
            for cond, blk, isnext in (("A_status", item["status_row"], False),
                                      ("B_next", item["next_block"], True)):
                for t in range(args.trials):
                    jobs.append(("next_action", item["id"], cond, t,
                                 next_action_prompt(blk, isnext), item))

    if args.only in (None, "refusal"):
        for item in sc["refusal"]:
            for t in range(args.trials):
                jobs.append(("refusal", item["id"], "single", t,
                             refusal_prompt(item["refusal"]), item))

    print(f"eval: {len(jobs)} calls "
          f"({args.trials} trial(s) each, {args.workers} workers, model {model})")

    results = []

    def run(job):
        kind, sid, cond, trial, prompt, item = job
        reply, used = ask(key, prompt, base_url, model)
        rec = {"kind": kind, "id": sid, "cond": cond, "trial": trial,
               "reply": reply, "error": failed(reply), "completion_tokens": used}
        if not rec["error"]:
            if kind == "routing":
                ok, got = score_routing(reply, item["expect"])
                rec.update(ok=ok, got=got, expect=item["expect"])
            elif kind == "next_action":
                ok, got = score_contains(reply, item["expect_contains"])
                rec.update(ok=ok, got=got, expect=item["expect_contains"])
            else:
                verdict, got = score_refusal(reply, item["correct_contains"],
                                             item["bypass_contains"])
                rec.update(verdict=verdict, got=got, ok=(verdict == "CORRECT"))
        sys.stderr.write(".")
        sys.stderr.flush()
        return rec

    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        results = list(ex.map(run, jobs))
    sys.stderr.write("\n")

    report(results, args)
    if args.json_out:
        Path(args.json_out).write_text(
            json.dumps(results, indent=1, ensure_ascii=False), encoding="utf-8")
        print(f"\nraw results -> {args.json_out}")


def pct(n, d):
    return f"{100.0 * n / d:5.1f}%" if d else "  n/a"


def report(results, args):
    errs = [r for r in results if r["error"]]
    ok_results = [r for r in results if not r["error"]]

    print("\n" + "=" * 72)
    print("WEAK-MODEL EVAL RESULTS")
    print("=" * 72)
    if errs:
        kinds = defaultdict(int)
        for r in errs:
            kinds[r["reply"].split(" ")[0]] += 1
        print(f"\n!! {len(errs)}/{len(results)} calls excluded from scoring: "
              + ", ".join(f"{k} x{v}" for k, v in sorted(kinds.items())))
        if any(r["reply"].startswith("__TRUNCATED__") for r in errs):
            print("   (truncated = reasoning used the whole token budget; "
                  "raise max_tokens. Not counted as a wrong answer.)")

    for kind, conds, title in (
            ("routing", ("A_before", "B_after"),
             "SKILL ROUTING  (A = descriptions before this branch, B = after)"),
            ("next_action", ("A_status", "B_next"),
             "NEXT ACTION    (A = `wiki status` row, B = `wiki next` block)")):
        rows = [r for r in ok_results if r["kind"] == kind]
        if not rows:
            continue
        print(f"\n{title}")
        print("-" * 72)
        for cond in conds:
            c = [r for r in rows if r["cond"] == cond]
            if c:
                n = sum(1 for r in c if r["ok"])
                print(f"  {cond:<10} {pct(n, len(c))}  ({n}/{len(c)} trials)")
        # per-scenario deltas, only where the conditions disagree
        by = defaultdict(dict)
        for r in rows:
            by[r["id"]].setdefault(r["cond"], []).append(r["ok"])
        moved = []
        for sid, d in sorted(by.items()):
            if len(d) < 2:
                continue
            a = sum(d.get(conds[0], [])) / max(len(d.get(conds[0], [])), 1)
            b = sum(d.get(conds[1], [])) / max(len(d.get(conds[1], [])), 1)
            if a != b:
                moved.append((sid, a, b))
        if moved:
            print("  scenarios where the conditions differ:")
            for sid, a, b in moved:
                arrow = "improved" if b > a else "REGRESSED"
                print(f"    {sid}: {a*100:.0f}% -> {b*100:.0f}%   {arrow}")

    # Reasoning cost per condition. This is the "speed" half of the question:
    # how hard does the model have to think under each condition? It is also
    # why the first run lost a whole arm to gateway timeouts.
    costed = [r for r in results if r.get("completion_tokens")]
    if costed:
        print("\nREASONING COST  (completion tokens per answer -- lower is faster)")
        print("-" * 72)
        by = defaultdict(list)
        for r in costed:
            by[(r["kind"], r["cond"])].append(r["completion_tokens"])
        for k in sorted(by):
            v = sorted(by[k])
            med = v[len(v) // 2]
            print(f"  {k[0]+'/'+k[1]:<26} median {med:>6}   "
                  f"min {v[0]:>6}  max {v[-1]:>6}   (n={len(v)})")

    ref = [r for r in ok_results if r["kind"] == "refusal"]
    if ref:
        print("\nREFUSAL COMPREHENSION  (does it take the remedy, or bypass it?)")
        print("-" * 72)
        tally = defaultdict(int)
        for r in ref:
            tally[r["verdict"]] += 1
        for v in ("CORRECT", "OTHER", "BYPASS"):
            print(f"  {v:<8} {pct(tally[v], len(ref))}  ({tally[v]}/{len(ref)})")
        bypassed = [r for r in ref if r["verdict"] == "BYPASS"]
        if bypassed:
            print("  !! bypass attempts (the failure mode the fences exist for):")
            for r in bypassed:
                print(f"    {r['id']} trial {r['trial']}: {r['got']}")


if __name__ == "__main__":
    main()
