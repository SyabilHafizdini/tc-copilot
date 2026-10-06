#!/usr/bin/env python3
"""The `prds` field of test case grid rows
(run: py tools/test_app_testcase_prds.py). No pytest."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "tools/app"))
import testcase_models
from testkit import skip_if_empty


def test_row_prds_is_the_sorted_key_list_of_prd_versions():
    fm = {"generated_from": {"prd_versions": {"rental-payment": 1, "rental-application": 2}}}
    assert testcase_models.row_prds(fm) == ["rental-application", "rental-payment"]


def test_row_prds_is_empty_without_a_prd():
    assert testcase_models.row_prds({"generated_from": {"prd_versions": {}}}) == []
    assert testcase_models.row_prds({"generated_from": {"prd_version": 1}}) == []
    assert testcase_models.row_prds({}) == []


def test_every_served_row_carries_prds():
    rows = testcase_models.testcases()["rows"]
    assert rows, "the grid payload has no rows"
    for row in rows:
        assert isinstance(row.get("prds"), list), row
        assert all(isinstance(p, str) for p in row["prds"]), row


if __name__ == "__main__":
    skip_if_empty("unit: test case grid PRD field")
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"[PASS] {name}")
    print("test_app_testcase_prds OK")
