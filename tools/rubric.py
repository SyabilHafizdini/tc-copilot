#!/usr/bin/env python3
"""Loader and validator for the versioned test-case rubric.

The rubric is an ORIGINAL work derived from the structure of
ISO/IEC/IEEE 29119-4:2021. It cites clause numbers and restates obligations in
our own words; it reproduces none of the standard's prose. The operator
guide is docs/skills/tc-rubric.md.

Deliberately has no wiki dependency: a rubric is valid or not on its own terms,
and the standalone evaluator scores foreign workbooks with no wiki in sight.
"""
import hashlib
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
RUBRIC_DIR = ROOT / "standards/rubric"

# Provenance. There is no 'house' tier by design: a dimension that cannot cite
# a clause does not belong in this rubric (spec 2.2).
SOURCES = {"standard", "derived"}
SCORED_MODES = {"mech", "judge"}
TIERS = (1, 2)
BANDS = {0: "absent", 1: "poor", 2: "adequate", 3: "good", 4: "exemplary"}

DIM_REQUIRED = ("id", "tier", "name", "source", "clause", "scored", "weight",
                "obligation")


def rubric_path(version="v1"):
    return RUBRIC_DIR / f"tc-rubric-{version}.yaml"


def validate_rubric(data, label):
    """Pure structural validation. Returns error strings; never exits."""
    errs = []
    if not isinstance(data, dict):
        return [f"{label}: top level must be a mapping"]
    dims = data.get("dimensions")
    if not isinstance(dims, list) or not dims:
        return [f"{label}: 'dimensions' must be a non-empty list"]

    seen = set()
    by_tier = {t: 0 for t in TIERS}
    for i, d in enumerate(dims):
        where = f"{label}: dimensions[{i}]"
        if not isinstance(d, dict):
            errs.append(f"{where}: must be a mapping")
            continue
        where = f"{label}: {d.get('id', f'dimensions[{i}]')}"
        for k in DIM_REQUIRED:
            if k not in d:
                errs.append(f"{where}: missing required key '{k}'")
        did = d.get("id")
        # `did` is None when 'id' is missing, which DIM_REQUIRED already
        # reported. Keying duplicate detection on None would add a spurious
        # "duplicate dimension id 'None'" beside the real error.
        if did is not None:
            if did in seen:
                errs.append(f"{label}: duplicate dimension id '{did}'")
            seen.add(did)

        src = d.get("source")
        if src not in SOURCES:
            errs.append(f"{where}: source {src!r} must be one of "
                        f"{sorted(SOURCES)} - there is no 'house' tier")
        # A cited clause is what makes a 'standard' dimension defensible.
        if src == "standard" and not d.get("clause"):
            errs.append(f"{where}: clause is required when source is 'standard'")

        tier = d.get("tier")
        if tier not in TIERS:
            errs.append(f"{where}: tier {tier!r} must be 1 or 2")

        w = d.get("weight")
        if not isinstance(w, int) or isinstance(w, bool) or w <= 0:
            errs.append(f"{where}: weight must be a positive integer, got {w!r}")
        elif tier in by_tier:
            by_tier[tier] += w

        scored = d.get("scored")
        if not isinstance(scored, list) or not scored:
            errs.append(f"{where}: scored must be a non-empty list")
        else:
            for m in scored:
                if m not in SCORED_MODES:
                    errs.append(f"{where}: scored {m!r} must be one of "
                                f"{sorted(SCORED_MODES)}")

    for t in TIERS:
        if by_tier[t] != 100:
            errs.append(f"{label}: tier {t} weights sum to {by_tier[t]}, "
                        f"must be exactly 100")
    return errs


def load_rubric(version="v1"):
    """Validated rubric, or exit(1) reporting every problem at once."""
    path = rubric_path(version)
    if not path.exists():
        sys.exit(f"rubric: no rubric at {path.relative_to(ROOT).as_posix()}")
    label = path.relative_to(ROOT).as_posix()
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as e:
        sys.exit(f"rubric: {label} is not valid YAML: {e}")
    errs = validate_rubric(data, label)
    if errs:
        print(f"RUBRIC INVALID: {label}", file=sys.stderr)
        for e in errs:
            print("  ERROR", e, file=sys.stderr)
        sys.exit(1)
    return data


def rubric_hash(version="v1"):
    """sha256 of the rubric file's bytes. Two scores are only comparable under
    the same hash, so every output stamps it."""
    return "sha256:" + hashlib.sha256(
        rubric_path(version).read_bytes()).hexdigest()


def dimensions(rubric, tier=None):
    dims = rubric.get("dimensions") or []
    return [d for d in dims if tier is None or d.get("tier") == tier]
