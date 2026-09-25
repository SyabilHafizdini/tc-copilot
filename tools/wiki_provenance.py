#!/usr/bin/env python3
"""`wiki migrate-provenance` -- backfill the provenance field on stories
written before it was mandatory (lint L13).

Deterministic and LLM-free. It stamps only the case it can know: a story that
cites PRD sections took its AC text from them, so it is 'prd-verbatim'. A
story citing nothing could be human-stated or could be an agent's invention,
and only a person knows which -- those are REPORTED, never guessed. Guessing
there would launder exactly what L13 exists to catch.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from wiki import (ROOT, agent_commit, all_concepts, read_concept,
                  write_concept)


def plan_backfill(concepts):
    """(to_stamp {rel: value}, unresolved [rel]) -- pure, never writes."""
    to_stamp, unresolved = {}, []
    for rel, (fm, _body) in sorted(concepts.items()):
        if not fm or fm.get("type") != "User Story" or fm.get("provenance"):
            continue
        if fm.get("derived_from"):
            to_stamp[rel] = "prd-verbatim"
        else:
            unresolved.append(rel)
    return to_stamp, unresolved


def cmd_migrate_provenance(args):
    concepts = {rel: (fm, body) for rel, fm, body, _p in all_concepts()}
    to_stamp, unresolved = plan_backfill(concepts)

    if not to_stamp and not unresolved:
        print("every story already declares a provenance -- nothing to do.")
        return

    for rel, value in to_stamp.items():
        no_acs = not (concepts[rel][0].get("acceptance_criteria") or [])
        flag = "  (no acceptance_criteria yet -- re-check at alignment)" if no_acs else ""
        print(f"  {rel}  ->  provenance: {value}{flag}")
    for rel in unresolved:
        print(f"  {rel}  ->  CANNOT DECIDE: no derived_from. Declare "
              f"'human-stated' if a human stated these ACs; otherwise the "
              f"story needs re-aligning against its source.")

    if "--apply" not in args:
        print(f"\n{len(to_stamp)} story(ies) would be stamped; nothing written.")
        print("Re-run with --apply.")
        return

    for rel, value in to_stamp.items():
        path = ROOT / (rel + ".md")
        fm, body = read_concept(path)
        fm["provenance"] = value
        write_concept(path, fm, body)
    print(f"\nstamped {len(to_stamp)} story(ies).")
    if unresolved:
        print(f"{len(unresolved)} story(ies) still undeclared -- lint will "
              f"error and the commit will refuse until you declare them. "
              f"That refusal is correct.")
    print("Run `py tools/wiki.py lint` next -- W6 flags any stamped story "
          "whose AC text is not covered by the PRD sections it cites.")
    agent_commit(f"migrate-provenance: {len(to_stamp)} story(ies) -> prd-verbatim")
