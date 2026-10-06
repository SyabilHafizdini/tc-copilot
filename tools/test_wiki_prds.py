#!/usr/bin/env python3
"""Plain-assert tests for the PRD registry accessors and the readers built on
them (run: py tools/test_wiki_prds.py). No pytest - matches tools/smoke.py.

Everything here is a pure function of an in-memory manifest; nothing on disk
is read or written."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import wiki

NONE = {"schema_version": 2, "prds": {}}
ONE = {"schema_version": 2, "prds": {
    "rental-application": {"title": "Rental application", "adopted_version": 2,
                        "staged_version": None}}}
TWO = {"schema_version": 2, "prds": {
    "rental-application": {"title": "Rental application", "adopted_version": 2,
                        "staged_version": None},
    "rental-payment": {"title": "Rental payment", "adopted_version": 1,
                    "staged_version": 2}}}


def _exit_text(fn, *a, **kw):
    try:
        fn(*a, **kw)
    except SystemExit as e:
        return str(e)
    return None


def test_registry_and_versions():
    assert wiki.prd_registry(NONE) == {}
    assert wiki.prd_registry({"schema_version": 1}) == {}
    assert sorted(wiki.prd_registry(TWO)) == ["rental-application", "rental-payment"]
    assert wiki.adopted_version(TWO, "rental-payment") == 1
    assert wiki.staged_version(TWO, "rental-payment") == 2
    assert wiki.staged_version(TWO, "rental-application") is None
    assert wiki.adopted_version(TWO, "nope") is None


def test_prd_id_pattern():
    for good in ("rental-application", "a1", "p-2"):
        assert wiki.PRD_ID_RE.fullmatch(good), good
    for bad in ("A", "a", "-rental", "rental_app", "RENTAL", "rental app", "x" * 65, ""):
        assert not wiki.PRD_ID_RE.fullmatch(bad), bad


def test_one_prd_needs_no_flag():
    assert wiki.resolve_prd_arg(ONE, []) == "rental-application"
    assert wiki.resolve_prd_arg(ONE, ["CR-001", "--by", "x"]) == "rental-application"


def test_two_prds_without_the_flag_is_refused_and_lists_both():
    msg = _exit_text(wiki.resolve_prd_arg, TWO, ["CR-001", "--by", "x"])
    assert msg and "rental-application" in msg and "rental-payment" in msg, msg
    assert "--prd" in msg, msg


def test_named_prd_is_returned():
    assert wiki.resolve_prd_arg(TWO, ["--prd", "rental-payment"]) == "rental-payment"


def test_bare_prd_flag_with_one_prd_still_resolves():
    """`diff --prd` used to take no value. It must keep working."""
    assert wiki.resolve_prd_arg(ONE, ["--prd"]) == "rental-application"
    assert wiki.resolve_prd_arg(ONE, ["--prd", "--by", "x"]) == "rental-application"


def test_bare_prd_flag_with_two_prds_is_refused_not_a_traceback():
    msg = _exit_text(wiki.resolve_prd_arg, TWO, ["--prd"])
    assert msg and "rental-application" in msg and "rental-payment" in msg, msg


def test_unregistered_id_is_refused_unless_new_is_allowed():
    msg = _exit_text(wiki.resolve_prd_arg, TWO, ["--prd", "rental-fees"])
    assert msg and "not a registered PRD" in msg, msg
    assert "rental-application" in msg and "rental-payment" in msg, msg
    assert wiki.resolve_prd_arg(TWO, ["--prd", "rental-fees"], allow_new=True) == "rental-fees"


def test_malformed_id_is_refused_even_when_new_is_allowed():
    msg = _exit_text(wiki.resolve_prd_arg, TWO, ["--prd", "Rental Fees"], allow_new=True)
    assert msg and "lowercase-hyphen" in msg, msg


def test_no_prd_registered_names_the_registering_command():
    msg = _exit_text(wiki.resolve_prd_arg, NONE, [])
    assert msg and "ingest-prd --prd" in msg and "--title" in msg, msg


def test_prd_id_of_ref():
    assert wiki.prd_id_of_ref("/sources/prd/rental-payment/1-1.md") == "rental-payment"
    assert wiki.prd_id_of_ref("sources/prd/rental-payment/1-1") == "rental-payment"
    assert wiki.prd_id_of_ref("/sources/prd/rental-payment/1-1.md#x") == "rental-payment"
    assert wiki.prd_id_of_ref("/sources/prd/1-1.md") is None          # schema-1 layout
    assert wiki.prd_id_of_ref("/sources/reference/rules.md") is None


def test_prd_versions_for_stories():
    app = {"derived_from": ["/sources/prd/rental-application/1-1.md"]}
    both = {"derived_from": ["/sources/prd/rental-payment/1-1.md",
                             "/sources/prd/rental-application/1-2.md",
                             "/sources/reference/rules.md"]}
    none = {"provenance": "human-stated"}
    assert wiki.prd_versions_for([app], TWO) == {"rental-application": 2}
    got = wiki.prd_versions_for([both], TWO)
    assert got == {"rental-application": 2, "rental-payment": 1}, got
    assert list(got) == ["rental-application", "rental-payment"], "sorted by id"
    assert wiki.prd_versions_for([none], TWO) == {}
    assert wiki.prd_versions_for([app, none, both], TWO) == got
    assert wiki.prd_versions_for([{"derived_from": "/sources/prd/rental-payment/1-1.md"}],
                                 TWO) == {"rental-payment": 1}, "a bare string ref"


def test_prd_label():
    assert wiki.prd_label({}) == "no PRD"
    assert wiki.prd_label({"rental-payment": 1}) == "PRD rental-payment v1"
    assert wiki.prd_label({"rental-payment": 1, "rental-application": 2}) == \
        "PRD rental-application v2, rental-payment v1"


def test_a_label_never_says_vNone():
    """One policy for the Traceability line, the workbook's PRD cells and the
    report headers: a PRD with nothing adopted says so, and one that is not
    in the registry says that."""
    assert wiki.prd_version_text("rental-payment", 3) == "rental-payment v3"
    assert wiki.prd_version_text("rental-payment", None) == \
        "rental-payment (no adopted version)"
    assert wiki.prd_version_text("gone", None, TWO) == "gone (unregistered)"
    assert wiki.prd_version_text("gone", 4, TWO) == "gone (unregistered)"
    assert wiki.prd_version_text("rental-payment", 1, TWO) == "rental-payment v1"
    assert wiki.prd_label({"rental-payment": None}) == \
        "PRD rental-payment (no adopted version)"
    assert wiki.prd_label({"gone": None, "rental-payment": 1}, TWO) == \
        "PRD gone (unregistered), rental-payment v1"
    staged_only = {"schema_version": 2, "prds": {"later": {
        "title": "Later", "adopted_version": None, "staged_version": 1}}}
    assert wiki.prd_summary(staged_only) == \
        "later (no adopted version) (v1 staged)"
    for text in (wiki.prd_label({"a-b": None}), wiki.prd_summary(staged_only)):
        assert "vNone" not in text, text


def test_one_rule_for_prd_ids():
    assert wiki.prd_id_problem("rental-application") is None
    for bad in ("RENTAL", "x", "a/b", "../x", ""):
        assert "lowercase-hyphen" in wiki.prd_id_problem(bad), bad
    for bad in ("v1", "v20"):
        assert "version directory names" in wiki.prd_id_problem(bad), bad
    for bad in ("index", "log"):
        assert "reserved name" in wiki.prd_id_problem(bad), bad
    assert wiki.prd_id_problem("v1-fees") is None, "only an exact vN collides"
    # an id that is already registered is not re-judged, a new one is
    odd = {"schema_version": 2, "prds": {"v2": {
        "title": "Old", "adopted_version": 1, "staged_version": None}}}
    assert wiki.resolve_prd_arg(odd, ["--prd", "v2"]) == "v2"
    msg = _exit_text(wiki.resolve_prd_arg, ONE, ["--prd", "v2"], allow_new=True)
    assert msg and "collides" in msg, msg
    msg = _exit_text(wiki.resolve_prd_arg, ONE, ["--prd", "index"], allow_new=True)
    assert msg and "reserved name" in msg, msg


def test_the_registry_has_one_writer():
    m = {"schema_version": 2}
    entry = wiki.set_prd_versions(m, "rental-fees", adopted=1, title="Rental fees")
    assert m["prds"] == {"rental-fees": {"title": "Rental fees", "adopted_version": 1,
                                      "staged_version": None}}, m
    assert entry is m["prds"]["rental-fees"]
    wiki.set_prd_versions(m, "rental-fees", staged=2)
    assert (wiki.adopted_version(m, "rental-fees"),
            wiki.staged_version(m, "rental-fees")) == (1, 2)
    wiki.set_prd_versions(m, "rental-fees", adopted=2, staged=None, title="ignored")
    assert m["prds"]["rental-fees"] == {"title": "Rental fees", "adopted_version": 2,
                                     "staged_version": None}, m


def test_a_schema_version_that_is_not_a_whole_number_is_an_error_not_a_guess():
    for bad in ("two", "2", 2.0, True, [2]):
        try:
            wiki.is_schema1({"schema_version": bad})
        except wiki.ManifestError as e:
            assert "not a whole number" in str(e), e
        else:
            raise AssertionError(f"schema_version {bad!r} was accepted")
        msg = _exit_text(wiki.refuse_if_schema1, {"schema_version": bad}, "gate")
        assert msg and msg.startswith("gate refused: manifest.json has "
                                      "schema_version"), msg
    assert not wiki.is_schema1({"schema_version": 2})
    assert wiki.is_schema1({"schema_version": 0})


def test_prd_rows_and_summary():
    assert wiki.prd_rows(NONE) == []
    assert wiki.prd_rows(TWO) == [
        {"id": "rental-application", "title": "Rental application", "adopted": 2, "staged": None},
        {"id": "rental-payment", "title": "Rental payment", "adopted": 1, "staged": 2}]
    assert wiki.prd_summary(NONE) == "no PRD"
    assert wiki.prd_summary(TWO) == "rental-application v2, rental-payment v1 (v2 staged)"


def test_schema1_refusal_names_the_migrate_command():
    assert wiki.is_schema1({"schema_version": 1})
    assert wiki.is_schema1({"bindings": {}}), "a manifest with no schema_version is schema 1"
    assert not wiki.is_schema1(NONE)
    assert _exit_text(wiki.refuse_if_schema1, NONE, "gate") is None
    msg = _exit_text(wiki.refuse_if_schema1, {"schema_version": 1}, "gate")
    assert msg and msg.startswith("gate refused"), msg
    assert "migrate-prds" in msg and "--id" in msg and "--title" in msg, msg


def test_next_raises_one_banner_per_staged_prd_and_names_it():
    import wiki_next
    assert wiki_next.prd_banners(NONE) == []
    assert wiki_next.prd_banners(ONE) == []
    banners = wiki_next.prd_banners(TWO)
    assert len(banners) == 1, banners
    assert "rental-payment" in banners[0]["state"], banners[0]
    assert "v2 is STAGED" in banners[0]["state"], banners[0]
    assert banners[0]["command"] == "py tools/wiki.py diff --prd rental-payment"
    assert "tc-change-report" in banners[0]["skill"]


def test_rtm_headers_name_each_prd():
    import wiki_rtm
    line = "PRDs: rental-application v2, rental-payment v1 (v2 staged)"
    assert line in wiki_rtm.build_matrix({}, {}, {}, {}, TWO)
    assert line in wiki_rtm.build_trace({}, {}, {}, TWO)
    assert "PRDs: no PRD" in wiki_rtm.build_matrix({}, {}, {}, {}, NONE)


def test_rtm_pin_check_is_per_prd():
    import wiki_rtm
    tcs = {"testcases/sit/m/T1": {
        "id": "T1", "covers": ["/stories/US-A.md#AC1"],
        "generated_from": {"prd_versions": {"rental-application": 1, "rental-payment": 1}}},
        "testcases/sit/m/T2": {
        "id": "T2", "covers": ["/stories/US-A.md#AC1"],
        "generated_from": {"prd_versions": {}}}}
    text, _gaps, _orph, npin, _comp = wiki_rtm.build_gaps({}, tcs, {}, {}, TWO)
    assert npin == 1, text
    assert "- T1 (pinned rental-application v1, adopted v2)" in text, text
    assert "rental-payment v1, adopted" not in text, text
    assert "- T2" not in text.split("non-adopted PRD version")[1].split("##")[0], text


def test_rtm_trace_shows_the_prd_with_the_section():
    import wiki_rtm
    stories = {"stories/US-A": {"id": "US-A", "derived_from": [
        "/sources/prd/rental-payment/1-1.md"]}}
    tcs = {"testcases/sit/m/T1": {"id": "T1", "status": "active",
                                  "covers": ["/stories/US-A.md#AC1"]}}
    assert "rental-payment/1-1" in wiki_rtm.build_trace(stories, tcs, {}, TWO)


def test_graph_meta_lists_prds_and_section_nodes_carry_their_prd():
    import wiki_graph
    concepts = {"sources/prd/rental-payment/1-1": (
        {"type": "PRD Section", "id": "prd#rental-payment/1-1", "title": "1.1 Fees",
         "description": "d", "prd": "rental-payment"}, "", None)}
    model = wiki_graph.build_model(concepts, TWO)
    assert model["meta"]["prds"] == wiki.prd_rows(TWO), model["meta"]
    assert "prd_version" not in model["meta"], model["meta"]
    node = [n for n in model["nodes"] if n["type"] == "PRD Section"][0]
    assert node["prd"] == "rental-payment", node
    desc = wiki_graph.convert(model)["meta"]["description"]
    assert desc.startswith("rental-application v2, rental-payment v1: "), desc
    assert wiki_graph.convert(wiki_graph.build_model({}, NONE))["meta"][
        "description"].startswith("no PRD: "), "an empty registry reads 'no PRD'"


def test_impact_accepts_a_section_id_as_well_as_its_path():
    import wiki_impact
    ctx = {"node_type": {"sources/prd/rental-payment/1-1": "PRD Section"},
           "src_id_to_rel": {"prd#rental-payment/1-1": "sources/prd/rental-payment/1-1"},
           "concepts": {}}
    assert wiki_impact._resolve_query("prd#rental-payment/1-1", ctx) == \
        "sources/prd/rental-payment/1-1"
    assert wiki_impact._resolve_query("sources/prd/rental-payment/1-1", ctx) == \
        "sources/prd/rental-payment/1-1"


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"[PASS] {name}")
    print("test_wiki_prds OK")
