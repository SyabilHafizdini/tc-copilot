#!/usr/bin/env python3
"""Plain-assert tests for the unsealed-TC check (run: py tools/test_wiki_seal.py).
Matches the tools/smoke.py idiom - no pytest in this repo.

These tests never touch the working tree: they pass synthetic manifests, so a
failure can never leave the wiki half-mutated.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from wiki import load_manifest, unsealed_tcs
from testkit import skip_if_empty


def test_clean_repo_reports_nothing_unsealed():
    assert unsealed_tcs(load_manifest()) == [], \
        "the committed repo is sealed; unsealed_tcs must be empty"


def test_missing_hash_entry_counts_as_unsealed():
    """A fresh render adds no tc_hashes entry — the case lint W4 cannot see."""
    m = load_manifest()
    victim = sorted(m["tc_hashes"])[0]
    m2 = {**m, "tc_hashes": {k: v for k, v in m["tc_hashes"].items()
                             if k != victim}}
    assert victim in unsealed_tcs(m2), \
        "a TC file with no manifest entry must count as unsealed"


def test_changed_hash_counts_as_unsealed():
    m = load_manifest()
    victim = sorted(m["tc_hashes"])[0]
    m2 = {**m, "tc_hashes": {**m["tc_hashes"], victim: "sha256:deadbeef"}}
    assert victim in unsealed_tcs(m2), \
        "a TC file whose hash differs must count as unsealed"


def test_result_is_sorted_and_relative():
    m = load_manifest()
    m2 = {**m, "tc_hashes": {}}
    out = unsealed_tcs(m2)
    assert out == sorted(out), "result must be sorted for stable messages"
    assert all(not r.endswith(".md") for r in out), "paths carry no .md suffix"
    assert all(r.startswith("testcases/") for r in out), "paths are repo-relative"


if __name__ == "__main__":
    skip_if_empty("unit: unsealed-TC check")
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"[PASS] {name}")
    print("test_wiki_seal OK")
