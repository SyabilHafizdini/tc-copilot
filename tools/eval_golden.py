#!/usr/bin/env python3
"""Golden-set evaluator (skill-revamp spec, 'Golden-set evaluation').

Compares the wiki's generated test set against the org-authored golden
workbooks in eval/golden/. Product-agnostic comparator: golden facts are
parsed from the workbooks; ours from the wiki. Project data appears only as fixture
content. LLM-free.

Usage: py tools/eval_golden.py [--strict]
  --strict : exit 1 if SIT missing > 0, OR a journey exists and UAT
             segmentation mismatches (journey entries != active UAT TCs)
"""
import re
import sys
from datetime import datetime
from pathlib import Path

import yaml
from openpyxl import load_workbook

from wiki import ROOT, all_concepts, resolve_ref

GOLD_DIR = ROOT / "eval/golden"


def _golden(kind):
    """The project's golden workbook for `kind`, or None when it has none.

    Globbed rather than hardcoded so a project can version its golden set
    (sit-v0.1.xlsx, sit-v2.xlsx, ...) without editing this file; the
    highest-sorting name wins. A project with no golden set at all is a normal
    state, not an error -- see main().
    """
    return next(reversed(sorted(GOLD_DIR.glob(f"{kind}-*.xlsx"))), None)


GOLD_SIT = _golden("sit")
GOLD_UAT = _golden("uat")
GOLD_ALIASES = GOLD_DIR / "aliases.yaml"
TC_RE = re.compile(r"^(?:TC-)?(\d[\d.]*)-AC0*(\d+)-0*(\d+)\s*$")
ALIAS_TARGET_RE = re.compile(r"^(\d[\d.]*)-AC(\d+)$")


def load_aliases(path=GOLD_ALIASES):
    """Human-recorded golden-ID renumbering (eval/golden/aliases.yaml), data-driven —
    no product literals live in this file. Missing file -> no aliasing (empty dict)."""
    if not path.exists():
        return {}
    label = path.relative_to(ROOT).as_posix() if path.is_relative_to(ROOT) else str(path)
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as e:
        sys.exit(f"eval: {label} is not valid YAML: {e}")
    if data is None:
        return {}
    if not isinstance(data, dict):
        sys.exit(f"eval: {label} must be a YAML mapping (got {type(data).__name__})")
    return data


def apply_alias(tup, aliases):
    """(story, ac, seq) -> aliased (story, ac, seq) per aliases.yaml, else unchanged."""
    s, a, q = tup
    target = aliases.get(f"{s}-AC{a}")
    if not target:
        return tup
    m = ALIAS_TARGET_RE.match(str(target).strip())
    if not m:
        return tup
    return (m.group(1), int(m.group(2)), q)


def parse_golden(path):
    wb = load_workbook(path, data_only=True)
    tcs = []
    for ws in wb.worksheets:
        if not ws.title.startswith("C-TC"):
            continue
        group = None
        for row in ws.iter_rows(min_row=9, max_col=1):
            v = row[0].value
            if v is None:
                continue
            s = str(v).strip()
            m = TC_RE.match(s)
            if m:
                tcs.append((group, m.group(1), int(m.group(2)), int(m.group(3))))
            elif not s.startswith(("<Pre-condition>",)) and \
                    not re.match(r"^\d+\.\s", s) and len(s) > 3:
                group = s          # section or screen group row
    return {"tcs": tcs}


def wiki_tcs(kind):
    """(matched [(id, story, ac, seq)], skipped_ids) for active `kind` TCs."""
    out, skipped_ids = [], []
    for _rel, fm, _body, _p in all_concepts():
        if not fm or fm.get("type") != "Test Case" or fm.get("kind") != kind:
            continue
        if fm.get("status") != "active":
            continue
        m = TC_RE.match(fm["id"].removeprefix("UAT-"))
        if m:
            out.append((fm["id"], m.group(1), int(m.group(2)), int(m.group(3))))
        else:
            skipped_ids.append(fm["id"])
    return out, skipped_ids


def flow_journeys():
    """[(flow_rel, flow_id, [(story_num, ac_num), ...]), ...] for every flow
    that has a journey (usually one, but the evaluator supports N)."""
    seqs = []
    for rel, fm, _b, _p in all_concepts():
        if fm and fm.get("type") == "Flow" and fm.get("journey"):
            seq = []
            for e in fm["journey"]:
                frag = resolve_ref(e.get("ref", ""))[1] or ""
                m = re.match(r"^(.*)-AC0*(\d+)$", frag)
                if m:
                    seq.append((m.group(1), int(m.group(2))))
            seqs.append((rel, fm["id"], seq))
    return seqs


def uat_tcs_by_flow():
    """flow_rel -> count of active kind:uat TCs whose `covers` includes a ref
    resolving to a path under flows/ (a cheap prefix check — no need to load
    the target concept to know it's a flow; segmentation is scored per flow,
    not globally)."""
    counts = {}
    for _rel, fm, _b, _p in all_concepts():
        if fm and fm.get("type") == "Test Case" and fm.get("kind") == "uat" \
                and fm.get("status") == "active":
            flow_rels = {resolve_ref(c)[0] for c in fm.get("covers") or []
                        if resolve_ref(c)[0].startswith("flows/")}
            for frel in flow_rels:
                counts[frel] = counts.get(frel, 0) + 1
    return counts


def lcs_len(a, b):
    dp = [[0] * (len(b) + 1) for _ in range(len(a) + 1)]
    for i, x in enumerate(a):
        for j, y in enumerate(b):
            dp[i + 1][j + 1] = dp[i][j] + 1 if x == y else \
                max(dp[i][j + 1], dp[i + 1][j])
    return dp[-1][-1]


def main():
    if GOLD_SIT is None:
        # No golden set is the normal state for a project that has not been
        # given one (and for the empty base branch). This is a calibration
        # harness, not a gate, so it reports and succeeds -- including under
        # --strict, which must not fail a project for lacking golden data.
        print("eval: no golden workbook in eval/golden/ — nothing to compare "
              "against.\n"
              "      Add <sit|uat>-<version>.xlsx there to calibrate against "
              "your org's\n"
              "      hand-written test cases (see eval/golden/README.md).")
        return
    aliases = load_aliases()
    lines = ["# Golden-set evaluation", ""]
    # ---------------- SIT ----------------
    gold = parse_golden(GOLD_SIT)
    gset = {apply_alias((s, a, q), aliases) for _g, s, a, q in gold["tcs"]}
    ours, sit_skipped = wiki_tcs("sit")
    oset = {(s, a, q) for _id, s, a, q in ours}
    missing = sorted(gset - oset)
    extra = sorted(oset - gset)
    # ordering: within each story prefix, our export order = sorted key —
    # verify our set is strictly top-down when sorted the way the suite sorts
    lines += [f"## SIT vs {GOLD_SIT.name}", "",
              f"- golden TCs: {len(gset)} · ours (active): {len(oset)}",
              f"- matched: {len(gset & oset)}",
              f"- **missing from ours: {len(missing)}** "
              f"{['%s-AC%02d-%02d' % m for m in missing] if missing else ''}",
              f"- extra in ours (allowed, reported): {len(extra)}"]
    if sit_skipped:
        lines.append(f"- skipped {len(sit_skipped)} non-conventional SIT id(s) "
                     f"(branch-style, excluded from match): {', '.join(sorted(sit_skipped))}")
    lines.append("")
    # ---------------- UAT ----------------
    seg_mismatch = False
    uat_skipped = []
    if GOLD_UAT is None:
        # A project may calibrate SIT only; absence is reported, not fatal.
        # Falls through to the report + --strict check below, so a SIT
        # regression still fails even when there is no golden UAT set.
        lines += ["## UAT", "",
                  "- no golden UAT workbook in eval/golden/ — UAT comparison "
                  "skipped", ""]
    else:
        gold_u = parse_golden(GOLD_UAT)
        gseq = [apply_alias((s, a, q), aliases)[:2] for _g, s, a, q in gold_u["tcs"]]
        lines += [f"## UAT vs {GOLD_UAT.name}", "",
                  f"- golden journey rows: {len(gseq)}"]
        journeys = flow_journeys()
        _uat_ours, uat_skipped = wiki_tcs("uat")
        if not journeys:
            lines += ["- **no flow has a journey — UAT revamp not applied**", ""]
        else:
            flow_counts = uat_tcs_by_flow()
            for frel, fid, seq in journeys:
                l = lcs_len(gseq, seq)
                pos = sum(1 for i, x in enumerate(seq[:len(gseq)]) if gseq[i] == x)
                uat_tc_n = flow_counts.get(frel, 0)
                mismatch = uat_tc_n != len(seq)
                seg_mismatch = seg_mismatch or mismatch
                lines += [f"- flow {fid}: journey length {len(seq)}",
                          f"- LCS with golden: {l}/{len(gseq)}",
                          f"- positional matches: {pos}/{len(gseq)}",
                          f"- segmentation: journey entries {len(seq)} vs active UAT "
                          f"TCs {uat_tc_n} ({'1:1 OK' if not mismatch else 'MISMATCH'})",
                          ""]
    if uat_skipped:
        lines.append(f"- skipped {len(uat_skipped)} non-conventional UAT id(s) "
                     f"(excluded from segmentation count): {', '.join(sorted(uat_skipped))}")
        lines.append("")
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    outdir = ROOT / "build/reports"
    outdir.mkdir(parents=True, exist_ok=True)
    out = outdir / f"golden-eval-{ts}.md"
    out.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    print("\n".join(lines))
    print(f"-> {out.relative_to(ROOT)}")
    if "--strict" in sys.argv and (missing or seg_mismatch):
        sys.exit(1)


if __name__ == "__main__":
    main()
