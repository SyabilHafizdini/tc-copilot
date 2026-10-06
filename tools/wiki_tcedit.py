#!/usr/bin/env python3
"""`wiki tc edit` - a human rewords ONE field of ONE test case.

The edit lands in the source spec (tools/sit_specs/<STORY>.yaml or
tools/uat_specs/<FLOW>.yaml), never in the rendered testcases/ file. The spec
is then rendered the way every spec-only edit is rendered (forced), sealed and
committed once. If anything refuses, every file this command wrote is put back
byte for byte and the refusal is printed.

Deterministic and LLM-free: one targeted text substitution plus the existing
render, index and seal commands.

    py tools/wiki.py tc edit <id> --field <field> --from <path> --by <human>

Never touches `confidence` or `remarks`: a level changes only through
`wiki doubts answer` (CLAUDE.md rule 2).
"""
import copy
import subprocess
import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
import render_sit
import render_uat
import wiki_doubts
from wiki import (ROOT, agent_commit, append_log, arg_after, index_paths,
                  load_all, read_concept, refuse_if_schema1, resolve_ref,
                  signature_problem, unsealed_tcs)

TOOLS = Path(__file__).resolve().parent
USAGE = ("usage: wiki tc edit <id> --field <field> --from <path> --by <human>")

SIT_FIELDS = ("title", "objective", "steps", "data", "expected", "post",
              "pre_extra", "priority")
UAT_FIELDS = ("title", "objective", "steps", "expected", "priority")
EDITABLE = {"sit": SIT_FIELDS, "uat": UAT_FIELDS}
# Optional spec keys: saving empty text removes the key, which restores the
# renderer's default ("-" for data, post_default for post, no extra line).
REMOVABLE = ("data", "post", "pre_extra")
# pre_extra: render_sit's validator requires one line; refusing here is the
# same rule met before the spec is written instead of after.
ONE_LINE = ("title", "priority", "pre_extra")
# Where a key the entry does not carry yet is inserted: after the nearest of
# these that is present, so a new key lands where the specs already keep it.
ANCHORS = ("expected", "data", "pre_extra", "post")
TEXT_MAX = 20000
EDITS_DIR = "build/edits"


class Refused(Exception):
    """A reason this edit must not happen. Printed verbatim, exit 1."""


def clean_text(text):
    """LF line ends, no trailing spaces, no blank lines at either end - the
    form a `|-` block scalar holds exactly."""
    lines = [ln.rstrip() for ln in
             str(text).replace("\r\n", "\n").replace("\r", "\n").split("\n")]
    return "\n".join(lines).strip("\n")


# ------------------------------------------------------------- resolution
def _load(path):
    try:
        return yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError):
        return None


def spec_index():
    """{scenario_id: (kind, spec_path, key, entry)} over every SIT and UAT spec.

    The scenario id is the renderer's own binding key: render_sit formats it
    from an entry's (ac, seq), render_uat from a journey id, and the manifest
    binds it to the test case id for good. Matching on it is therefore the
    exact inverse of the render, and it still holds after `migrate-ids`, when
    a test case id no longer equals what `tc_id_for` would compute.
    `key` is the index into `test_cases` (SIT) or the journey id (UAT)."""
    out = {}
    for path in sorted(render_sit.SPEC_DIR.glob("*.yaml")):
        spec = _load(path)
        if not isinstance(spec, dict) or not isinstance(spec.get("test_cases"), list):
            continue
        for i, tc in enumerate(spec["test_cases"]):
            if not isinstance(tc, dict):
                continue
            try:
                sc = str(spec["scenario_id"]).format(
                    ac=tc["ac"], ac_id=render_sit.ac_id_of(spec, tc["ac"]),
                    seq=tc["seq"])
            except (KeyError, ValueError, IndexError):
                continue
            out[sc] = ("sit", path, i, tc)
    for path in sorted(render_uat.SPEC_DIR.glob("*.yaml")):
        spec = _load(path)
        if not isinstance(spec, dict) or not isinstance(spec.get("entries"), dict):
            continue
        for jid, entry in spec["entries"].items():
            if not isinstance(entry, dict):
                continue
            try:
                sc = str(spec["scenario_id"]).format(jid=jid)
            except (KeyError, ValueError, IndexError):
                continue
            out[sc] = ("uat", path, jid, entry)
    return out


def resolve(fm, index=None):
    """(kind, spec_path, key, entry) for a test case's frontmatter, or None
    when no spec entry renders it."""
    hit = (spec_index() if index is None else index).get(fm.get("scenario_id"))
    return hit if hit and hit[0] == fm.get("kind") else None


def editable_fields(fm, index=None):
    """The fields `tc edit` accepts for this test case; [] when it has no spec
    entry or is not active."""
    if fm.get("status") != "active" or not resolve(fm, index):
        return []
    return list(EDITABLE[fm["kind"]])


# ---------------------------------------------------------------- rewrite
class _BlockDumper(yaml.SafeDumper):
    """The dumper the spec files are written with: block style for any
    multi-line string, PyYAML's own choice of plain / quoted otherwise."""


_BlockDumper.add_representer(
    str, lambda d, v: d.represent_scalar(
        "tag:yaml.org,2002:str", v, style="|" if "\n" in v else None))


def _emit(key, text, col, eol):
    """`key: value` lines as a spec file writes them. The first line carries
    no indent (the caller's text already stands at column `col`); every
    following line is indented to `col`."""
    out = yaml.dump({key: text}, Dumper=_BlockDumper, sort_keys=False,
                    allow_unicode=True, width=1000)
    lines = out.split("\n")[:-1]
    pad = " " * col
    return eol.join([lines[0]] + [pad + ln if ln else ln for ln in lines[1:]]) + eol


def _value_end(raw, start, col):
    """Index just past the lines owned by the key that starts at `start` in
    column `col`: its own line plus every following line indented deeper.
    Blank lines are owned only when a deeper line follows them."""
    nl = raw.find("\n", start)
    if nl < 0:
        return len(raw)
    pos = end = nl + 1
    while pos < len(raw):
        nl = raw.find("\n", pos)
        nxt = len(raw) if nl < 0 else nl + 1
        line = raw[pos:nxt].rstrip("\r\n")
        if line.strip():
            if len(line) - len(line.lstrip(" ")) <= col:
                break
            end = nxt
        pos = nxt
    return end


def _guard_comments(raw, field, start, end, vnode):
    """Refuse when replacing raw[start:end] would delete a YAML comment.

    The proof in apply_edit compares parsed data, which cannot see comments.
    The scalar's own text is told apart from comments by the node marks:
    a quoted / plain scalar ends at its end mark, so any `#` after it is a
    comment; a block scalar's text is every line indented at least as deep as
    its first content line, so a `#` line there is text, while a `#` in the
    header or on a shallower line after the content is a comment."""
    region = raw[start:end]
    if vnode.style in ("|", ">"):
        head, _nl, body = region.partition("\n")
        after = head[head.index(":") + 1:].strip()
        if "#" in after:
            raise Refused(f"{field} carries a comment ({after[after.index('#'):]!r}) "
                          f"that this edit would delete; move it out of the way first")
        lines = body.split("\n")
        ind = next((len(ln) - len(ln.lstrip(" ")) for ln in lines if ln.strip()), 0)
        for ln in lines:
            if ln.strip() and len(ln) - len(ln.lstrip(" ")) < ind:
                raise Refused(f"{field} is followed by a comment ({ln.strip()!r}) "
                              f"that this edit would delete; move it out of the way first")
        return
    rest = raw[vnode.end_mark.index:end]
    if "#" in rest:
        note = next(ln.strip() for ln in rest.split("\n") if "#" in ln)
        raise Refused(f"{field} carries a comment ({note[note.index('#'):]!r}) "
                      f"that this edit would delete; move it out of the way first")


def _entry_node(raw, kind, key):
    root = yaml.compose(raw)
    top = {k.value: v for k, v in root.value}
    if kind == "sit":
        return top["test_cases"].value[key]
    return next(v for k, v in top["entries"].value if k.value == key)


def rewrite_key(raw, kind, key, field, text):
    """`raw` with `field` of one entry set to `text` (None removes the key).

    Positions come from PyYAML's own node marks, so the key is found where
    the parser found it, not where a regular expression guessed. Only that
    key's lines are replaced; every other character of `raw` is returned
    as it was."""
    eol = "\r\n" if "\r\n" in raw else "\n"
    pairs = [(k.value, k, v) for k, v in _entry_node(raw, kind, key).value]
    hit = next((p for p in pairs if p[0] == field), None)
    if hit:
        _name, knode, vnode = hit
        if not isinstance(vnode, yaml.ScalarNode):
            raise Refused(f"{field} is not a text value in the spec")
        start, col = knode.start_mark.index, knode.start_mark.column
        if raw[start:start + len(field) + 1] != f"{field}:":
            raise Refused(f"{field} is written in a form tc edit cannot "
                          f"rewrite (quoted or complex key)")
        end = _value_end(raw, start, col)
        _guard_comments(raw, field, start, end, vnode)
        if text is None:
            line_start = raw.rfind("\n", 0, start) + 1
            if raw[line_start:start].strip():
                raise Refused(f"{field} is the first key of its entry and "
                              f"cannot be removed")
            return raw[:line_start] + raw[end:]
        return raw[:start] + _emit(field, text, col, eol) + raw[end:]
    if text is None:
        return raw
    present = {p[0]: p for p in pairs}
    before = [a for a in ANCHORS[:ANCHORS.index(field)] if a in present] \
        if field in ANCHORS else []
    _name, knode, _v = present[before[-1]] if before else pairs[-1]
    col = knode.start_mark.column
    at = _value_end(raw, knode.start_mark.index, col)
    lead = "" if raw[:at].endswith("\n") else eol
    return raw[:at] + lead + " " * col + _emit(field, text, col, eol) + raw[at:]


def apply_edit(raw, kind, key, field, text):
    """rewrite_key, then PROVE it: the rewritten file must parse to the old
    data with exactly this one key changed. Anything else is refused and the
    caller writes nothing."""
    new = rewrite_key(raw, kind, key, field, text)
    want = copy.deepcopy(yaml.safe_load(raw))
    entry = want["test_cases"][key] if kind == "sit" else want["entries"][key]
    if text is None:
        entry.pop(field, None)
    else:
        entry[field] = text
    try:
        got = yaml.safe_load(new)
    except yaml.YAMLError as e:
        raise Refused(f"the rewritten spec would not parse ({e})")
    if got != want:
        raise Refused("the rewrite would change more than the one key")
    return new


# ---------------------------------------------------------------- command
def _git(*args):
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True,
                          text=True, encoding="utf-8", errors="replace")


def _tool(script, *args):
    """Run a sibling tool the way a human would; a non-zero exit is a refusal
    whose own words are passed on."""
    r = subprocess.run([sys.executable, str(TOOLS / script), *args], cwd=ROOT,
                       capture_output=True, text=True, encoding="utf-8",
                       errors="replace")
    if r.returncode != 0:
        raise Refused(f"`{script} {' '.join(args)}` refused:\n"
                      f"{(r.stdout + r.stderr).strip()}")
    return r.stdout


def _read_text(src):
    p = Path(src)
    p = p if p.is_absolute() else ROOT / p
    if not p.is_file():
        raise Refused(f"--from {src}: no such file")
    try:
        data = p.read_bytes()
    except OSError as e:
        raise Refused(f"--from {src}: cannot be read ({e})")
    try:
        # A one-shot transport file written by the app: gone as soon as it is
        # read, so it is deleted on success and on every later refusal. A path
        # anywhere else is never deleted.
        if p.resolve().parent == (ROOT / EDITS_DIR).resolve():
            p.unlink()
    except OSError:
        pass
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        raise Refused(f"--from {src}: not UTF-8 text")


def _find(tc_id, concepts):
    for rel, (fm, _body, _p) in concepts.items():
        if fm and fm.get("type") == "Test Case" and fm.get("id") == tc_id:
            return rel, fm
    raise Refused(f"test case {tc_id} not found")


def _checked_text(kind, field, text):
    """The text to store, or None to remove an optional key."""
    if "\x00" in text:
        raise Refused(f"{field} contains a NUL character")
    text = clean_text(text)
    if len(text) > TEXT_MAX:
        raise Refused(f"{field} is {len(text)} characters; the limit is {TEXT_MAX}")
    if not text:
        if kind == "sit" and field in REMOVABLE:
            return None
        raise Refused(f"{field} cannot be empty")
    if field in ONE_LINE and "\n" in text:
        raise Refused(f"{field} must be one line")
    if field == "priority" and text not in render_sit.PRIORITIES:
        raise Refused(f"priority '{text}' is not one of "
                      f"{sorted(render_sit.PRIORITIES)}")
    return text


def _preflight(tc_id, rel, fm, hit, index, concepts, manifest):
    """Every refusal that needs no write. Order: the test case's own state,
    then the state of the set the render will rewrite."""
    kind, spec_path, _key, _entry = hit
    status = fm.get("status")
    if status == "retired":
        raise Refused(f"{tc_id} is retired - a retired test case is never "
                      f"re-rendered (unretire is tc-lifecycle)")
    for ref in fm.get("covers") or []:
        srel, frag = resolve_ref(ref)
        sfm = concepts[srel][0] if srel in concepts else None
        for ac in (sfm or {}).get("acceptance_criteria") or []:
            if isinstance(ac, dict) and ac.get("id") == frag \
                    and ac.get("status") == "voided":
                raise Refused(f"{tc_id} covers {ref}, which is voided")
    mine = {sc for sc, h in index.items() if h[1] == spec_path}
    never = sorted(sc for sc in mine if sc not in manifest.get("bindings", {}))
    if never:
        raise Refused(f"{spec_path.name} has {len(never)} test case(s) that "
                      f"were never rendered ({', '.join(never[:3])}"
                      f"{' ...' if len(never) > 3 else ''}) - generate first "
                      f"(tc-generate-{kind})")
    stale = sorted(f["id"] for _r, (f, _b, _p) in concepts.items()
                   if f and f.get("type") == "Test Case"
                   and f.get("scenario_id") in mine and f.get("status") == "stale")
    if stale:
        raise Refused(f"{len(stale)} test case(s) of {spec_path.stem} are stale "
                      f"({', '.join(stale[:3])}{' ...' if len(stale) > 3 else ''})"
                      f" - the forced render an edit needs would clear that "
                      f"flag; regenerate first (tc-generate-{kind})")
    # Repo-wide on purpose: `seal` re-hashes EVERY test case, so a hand edit
    # anywhere would be sealed into this commit, clearing W4 without the
    # human-gated release / revert.
    drift = sorted(unsealed_tcs(manifest))
    if drift:
        raise Refused(f"{len(drift)} test case file(s) differ from their "
                      f"sealed hash (hand-edit drift), and the seal an edit "
                      f"runs is repo-wide:\n"
                      + "\n".join(f"    {r}" for r in drift[:5])
                      + "\n  If you have just rendered (for example after "
                        "`wiki doubts answer`), the render is not sealed yet: "
                        "run `py tools/wiki.py seal`, then edit.\n"
                        "  If a file was edited by hand, resolve it with "
                        "`wiki release` or `wiki revert` (tc-lifecycle), then "
                        "edit.")
    if _git("status", "--porcelain").stdout.strip():
        raise Refused("working tree is dirty - commit or clean it first (an "
                      "edit is one commit of a known state)")


class RestoreFailed(Exception):
    """The roll-back itself could not put some files back."""


def _snapshot(spec_path, out_dir):
    """Every file the edit can write. The index files come from
    wiki.index_paths(), the list write_indexes itself walks, so a per-PRD
    sources/prd/<id>/index.md is covered like any other."""
    paths = [spec_path, ROOT / "manifest.json", ROOT / "log.md"]
    paths += sorted(out_dir.glob("*.md")) if out_dir.exists() else []
    paths += index_paths()
    return {p: (p.read_bytes() if p.exists() else None) for p in dict.fromkeys(paths)}


def _head():
    return _git("rev-parse", "HEAD").stdout.strip()


def _restore(snap, out_dir):
    failed = []
    for p in sorted(out_dir.glob("*.md")) if out_dir.exists() else []:
        if p not in snap:
            try:
                p.unlink()
            except OSError:
                failed.append(str(p))
    for p, data in snap.items():
        try:
            if data is None:
                p.unlink(missing_ok=True)
            elif not p.exists() or p.read_bytes() != data:
                p.write_bytes(data)
        except OSError:
            failed.append(str(p))
    # a commit that failed after `git add` leaves the index staged
    if _git("reset", "-q").returncode != 0:
        failed.append("the git index (run `git reset`)")
    if failed:
        raise RestoreFailed(f"could not put back: {', '.join(failed)} - "
                            f"restore them from the last commit before editing again")
    # The edit started from a clean tree (preflight), so anything git still
    # reports is something the roll-back missed. Say so: "Nothing was
    # changed" must be true when it is printed.
    left = _git("status", "--porcelain")
    if left.returncode != 0:
        raise RestoreFailed("`git status` could not be read to verify the "
                            "roll-back - check the working tree before "
                            "editing again")
    if left.stdout.strip():
        raise RestoreFailed(
            "these paths still differ from the last commit:\n"
            + "\n".join(f"    {ln}" for ln in left.stdout.splitlines()[:10])
            + "\n  Restore them from the last commit (`git restore .`; "
              "remove untracked paths) before editing again")


class CommittedThenFailed(Exception):
    """The edit's commit landed and something after it failed."""

    def __init__(self, sha, cause):
        super().__init__(f"{type(cause).__name__}: {cause}")
        self.sha = sha


def _lifts(out_dir):
    """{(test case id, part): resolution ref} over the rendered files of one
    story or flow: the confirmed parts as the files show them."""
    out = {}
    for p in sorted(out_dir.glob("*.md")) if out_dir.exists() else []:
        if p.name in ("index.md", "log.md"):
            continue
        fm, _body = read_concept(p)
        if not isinstance(fm, dict) or fm.get("type") != "Test Case":
            continue
        for part, ref in wiki_doubts.lifted_parts(fm.get("confidence_parts")).items():
            out[(fm.get("id"), part)] = ref
    return out


def _lift_notes(before, after, edited):
    """What the render did to human confirmations, in words. A reworded part
    no longer matches the text its Resolution confirmed, so it returns to its
    authored level; a confirmation that was waiting for a render is rendered
    by this one. Neither may happen without a record."""
    rid = lambda ref: Path(str(ref)).stem
    lost = [f"confirmation {rid(ref)} of {tc} {part} no longer applies "
            + ("(text changed)" if tc == edited else
               "(it had stopped matching before this edit)")
            for (tc, part), ref in sorted(before.items())
            if after.get((tc, part)) != ref]
    gained = sorted({rid(ref) for key, ref in after.items()
                     if before.get(key) != ref})
    notes = list(lost)
    if gained:
        notes.append(f"also rendered {len(gained)} confirmed lift(s): "
                     f"{', '.join(gained)}")
    return notes


def _unparsable_specs():
    """Name any spec file that does not parse: spec_index skips those, which
    would otherwise read as 'no spec entry' with no hint why."""
    bad = []
    for d in (render_sit.SPEC_DIR, render_uat.SPEC_DIR):
        for path in sorted(d.glob("*.yaml")):
            try:
                yaml.safe_load(path.read_text(encoding="utf-8"))
            except (yaml.YAMLError, OSError, UnicodeDecodeError) as e:
                bad.append(f"{path.name} ({str(e).splitlines()[0] if str(e) else 'unreadable'})")
    return ("\n  Spec file(s) that do not parse: " + "; ".join(bad)) if bad else ""


def edit(tc_id, field, src, by):
    text = _read_text(src)
    concepts, manifest = load_all()
    # Here, not in wiki.main(): the one-shot text file is already consumed and
    # nothing has been written. The forced render below would refuse too, but
    # only after the spec was written and had to be rolled back.
    refuse_if_schema1(manifest, "tc edit")
    rel, fm = _find(tc_id, concepts)
    kind = fm.get("kind")
    if kind not in EDITABLE:
        raise Refused(f"{tc_id} is neither a SIT nor a UAT test case")
    index = spec_index()
    hit = resolve(fm, index)
    if not hit:
        raise Refused(f"no spec entry renders {tc_id} (scenario "
                      f"{fm.get('scenario_id')}) - it cannot be edited here"
                      f"{_unparsable_specs()}")
    _k, spec_path, key, entry = hit
    if field not in EDITABLE[kind]:
        raise Refused(f"field '{field}' is not editable on a {kind.upper()} "
                      f"test case (editable: {', '.join(EDITABLE[kind])})")
    text = _checked_text(kind, field, text)
    _preflight(tc_id, rel, fm, hit, index, concepts, manifest)
    current = entry.get(field)
    if (text is None and field not in entry) or \
            (text is not None and isinstance(current, str) and current == text):
        print(f"tc edit: {tc_id} {field} unchanged - nothing to do")
        return
    try:
        raw = spec_path.read_bytes().decode("utf-8")
        new = apply_edit(raw, kind, key, field, text)
        spec = yaml.safe_load(raw)
    except (yaml.YAMLError, UnicodeDecodeError) as e:
        raise Refused(f"{spec_path.name} cannot be read as YAML ({e})")
    out_dir = ROOT / spec["out"]
    snap = _snapshot(spec_path, out_dir)
    lifts0 = _lifts(out_dir)
    head0 = _head()
    notes = []
    try:
        spec_path.write_bytes(new.encode("utf-8"))
        # A spec-only edit moves no pinned fragment, so an unforced render
        # would skip every test case: --force is the documented invocation.
        if kind == "sit":
            _tool("render_sit.py", "--story", spec_path.stem, "--force")
        else:
            _tool("render_uat.py", "--flow", spec_path.stem, "--force")
        _tool("wiki.py", "index", "--no-commit")
        _tool("wiki.py", "seal", "--no-commit")
        try:
            where = spec_path.relative_to(ROOT).as_posix()
        except ValueError:
            where = spec_path.name
        notes = _lift_notes(lifts0, _lifts(out_dir), tc_id)
        tail = "".join(f"; {n}" for n in notes)
        append_log(f"**TC edit ({by})**: {tc_id} {field} reworded in {where}{tail}")
        try:
            agent_commit(f"tc edit({tc_id}): {field} by {by}"
                         + ("\n\n" + "\n".join(notes) if notes else ""))
        except SystemExit:
            raise Refused("lint refused the edited wiki (errors above)")
        # Success is a moved HEAD, not a clean tree: a commit that went
        # through must never be rolled back because something else is dirty.
        if "--no-commit" not in sys.argv and _head() == head0:
            raise Refused("the commit did not go through (see [git] above)")
    except BaseException as e:
        # Anything after the spec write - a refusal, KeyboardInterrupt, a
        # locked file - puts every written file back, unless the commit landed.
        now = _head()
        if now == head0:
            _restore(snap, out_dir)
            raise
        raise CommittedThenFailed(now, e) from e
    print(f"tc edit: {tc_id} {field} saved by {by}")
    for n in notes:
        print(f"  note: {n}")


def cmd_tc(args):
    if len(args) < 2 or args[0] != "edit" or args[1].startswith("--"):
        sys.exit(USAGE)
    tc_id = args[1]
    # One commit of a state lint has passed, or nothing. `--no-commit` stays
    # (it leaves the rendered edit in the tree for inspection); skipping lint
    # would let an edit signed by a human commit a lint-invalid wiki.
    if "--allow-lint-errors" in sys.argv:
        sys.exit("tc edit refused: --allow-lint-errors is not accepted here. "
                 "An edit is one commit of a wiki that passes lint, or "
                 "nothing; fix the lint errors first.\n  Nothing was changed.")
    field, src, by = (arg_after(args, f) for f in ("--field", "--from", "--by"))
    problem = signature_problem(by)
    if problem:
        sys.exit(f"tc edit refused: --by <human> is the name the edit is "
                 f"signed with, and {problem}.\n  Nothing was changed.")
    try:
        edit(tc_id, field, src, by)
    except yaml.YAMLError as e:
        sys.exit(f"tc edit refused: a YAML file could not be read ({e})\n"
                 f"  Nothing was changed.")
    except Refused as e:
        sys.exit(f"tc edit refused: {e}\n  Nothing was changed.")
    except RestoreFailed as e:
        sys.exit(f"tc edit failed AND the roll-back was incomplete: {e}")
    except CommittedThenFailed as e:
        sys.exit(f"tc edit: the edit IS committed ({e.sha[:8]}) but a later "
                 f"step failed ({e}).\n  Nothing was undone. Check "
                 f"`git status`.")
    except (KeyboardInterrupt, Exception) as e:
        sys.exit(f"tc edit failed: {type(e).__name__}: {e}\n"
                 f"  Every file it wrote was restored.")
