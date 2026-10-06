#!/usr/bin/env python3
"""`wiki migrate-prds` -- convert a schema-1 project (one unnamed PRD) to the
PRD registry (manifest schema 2), in one commit.

Deterministic and LLM-free. There is no dual-layout mode, so this runs once
per project: it moves the flat PRD layout one level down under the PRD's id,
rewrites every reference to the moved sections, gives each test case its
`generated_from.prd_versions`, rewrites the manifest, and re-seals.

Everything is planned in memory first and every refusal fires before the
first write: a migration that stops halfway leaves a project in neither
layout. Once the first write has happened, every mutation goes through a
journal, so any failure (a refusal from the self-check, lint refusing the
commit, a failing hook, an exception) puts every file back and leaves HEAD
where it was. It only moves files and rewrites references: it never adds,
changes or re-emits an assertion (`status: aligned`, `asserted_by`,
confirmed coverage or test model) and never raises a confidence level.

A test case is edited in place at its two spots (the `prd_version` line and
the Traceability tail) and wherever a moved section is referenced (a retired
test case's `retirement.caused_by`), not re-serialised and not re-rendered. A
forced re-render would also change `generated_from.wiki_commit` in every test
case and cannot reach stale or retired ones.

A concept file whose text is not what write_concept would produce (quotes,
comments, wrapping) is edited in place the same way: each planned reference
is substituted where it stands and every other byte is kept. Either kind of
in-place edit is accepted only when the edited text parses back to exactly
the planned frontmatter and body; otherwise the migration refuses.

The migration commit carries NO `Assertion-Event:` trailer: nobody asserted
anything, and the trailer would blind lint L10 to this commit.
"""
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import wiki
import yaml
from wiki import (FURNITURE, ROOT, agent_commit, all_concepts, append_log,
                  arg_after, concept_text, covmap_hash, fragment_hash_map,
                  index_paths, is_schema1, load_manifest, prd_id_problem,
                  prd_label, prd_versions_for, rebuild_manifest, resolve_ref,
                  save_manifest, set_prd_versions, sha256, unsealed_tcs,
                  write_indexes)

_SKIP = ("index.md", "log.md")
_FLAT_REF = re.compile(r"(/?)sources/prd/([^/#]+?)(\.md)?(#.*)?")
_FLAT_INPUT = re.compile(r"/inputs/prd/(v\d+/.+)")
_PROSE = re.compile(r"\]\(/sources/prd/([^/)#\s]+)\.md")
_TRACE = re.compile(r" · PRD v\S+ · wiki ")
_TRACE_HEAD = re.compile(r"^# Traceability[ \t]*$", re.MULTILINE)
_FM_SPLIT = re.compile(r"^---\n(.*?)\n---\n?(.*)$", re.DOTALL)
# A section id inside free text (`prd#1-1 removed in v2`). The boundaries keep
# a token that already carries its PRD id (`prd#legacy/1-1`) from matching
# again, stop it matching inside a longer word, and stop the match from
# backtracking to a prefix.
_TOKEN = re.compile(r"(?<![\w#/])prd#([a-z0-9-]+)(?![\w/-])")
_CR_SUMMARY = re.compile(r"^PRD v(\d+) -> v(\d+):", re.MULTILINE)
_CR_TITLE = re.compile(r"\bPRD v(\d+) -> v(\d+)")
# Frontmatter keys whose string value is free text that can name a section.
_CAUSE_KEYS = ("cause", "caused_by")
# Test-only (precedent: TC_MANIFEST_OVERRIDE). `raise:N` makes the Nth
# journalled operation raise, to prove the roll-back; it never edits a file.
# Unset in normal operation.
_FAULT_ENV = "TC_MIGRATE_PRDS_FAULT"


# Every command that would repair a pre-condition refuses on schema 1, so the
# repair happens before the upgrade. Printed under each such refusal.
_PRE_UPGRADE = (
    "  On schema 1 every command but migrate-prds, status and lint refuses, "
    "so this cannot be repaired on this platform revision.\n"
    "  Check out the platform revision the project last ran on (the last one "
    "before the PRD registry), resolve it there, commit, then upgrade and "
    "re-run migrate-prds.")


class Refused(Exception):
    pass


def _glob(base, pattern):
    return sorted((ROOT / base).glob(pattern)) if (ROOT / base).exists() else []


def legacy_layout(manifest):
    """What this project holds in the flat (schema-1) PRD layout."""
    vdirs = [p for p in _glob("inputs/prd", "v*")
             if p.is_dir() and p.name[1:].isdigit()]
    return {
        "sections": [p for p in _glob("sources/prd", "*.md")
                     if p.name not in _SKIP],
        "vdirs": vdirs,
        "docs": [f for d in vdirs for f in sorted(d.rglob("*"))
                 if f.is_file() and f.name not in FURNITURE],
        "staged": _glob("staging", "prd-v*.json"),
        "crs": _glob("changereports", "CR-*.md"),
        "adopted": manifest.get("adopted_prd_version"),
        "staged_version": manifest.get("staged_prd_version"),
    }


def _ref(s, pid, slugs):
    """One string: a flat section ref, a flat section id, or a flat upload
    path gains the PRD id. Anything else comes back unchanged."""
    m = _FLAT_REF.fullmatch(s)
    if m and m.group(2) in slugs:
        return (f"{m.group(1)}sources/prd/{pid}/{m.group(2)}"
                f"{m.group(3) or ''}{m.group(4) or ''}")
    if s.startswith("prd#") and s[4:] in slugs:
        return f"prd#{pid}/{s[4:]}"
    m = _FLAT_INPUT.fullmatch(s)
    if m:
        return f"/inputs/prd/{pid}/{m.group(1)}"
    return s


def _token(s, pid, slugs):
    """Free text: every flat `prd#<slug>` token of an existing section."""
    return _TOKEN.sub(lambda m: f"prd#{pid}/{m.group(1)}"
                      if m.group(1) in slugs else m.group(0), s)


def _rewrite(obj, pid, slugs, key=None):
    """Frontmatter walk: every string value AND every string key (story
    source_pins are keyed by section id). The values of `cause` and
    `caused_by` are free text, so section ids inside them are rewritten too."""
    if isinstance(obj, str):
        out = _ref(obj, pid, slugs)
        return _token(out, pid, slugs) if key in _CAUSE_KEYS else out
    if isinstance(obj, list):
        return [_rewrite(x, pid, slugs, key) for x in obj]
    if isinstance(obj, dict):
        return {(_ref(k, pid, slugs) if isinstance(k, str) else k):
                _rewrite(v, pid, slugs, k if isinstance(k, str) else None)
                for k, v in obj.items()}
    return obj


def _rewrite_body(body, pid, slugs):
    def sub(m):
        if m.group(1) not in slugs:
            return m.group(0)
        return f"](/sources/prd/{pid}/{m.group(1)}.md"
    return _PROSE.sub(sub, body or "")


def _with_prd(fm, pid):
    """`prd: <id>` directly after `description`, where ingest and
    stage_prd_version write it."""
    out = {}
    for k, v in fm.items():
        out[k] = v
        if k == "description":
            out["prd"] = pid
    out.setdefault("prd", pid)
    return out


def _report(fm, body, pid):
    """A change report as stage_prd_version writes it today: `prd` after
    `description`, `PRD <id> vA -> vB` in the title and the summary line.

    Only a PENDING report is reworded. A report a human already acted on
    (approved, rejected, superseded) is a record: it gains `prd: <id>` and
    nothing else, so git keeps pairing it as a rename and lint L10 never reads
    its `asserted_by:` line as newly added."""
    fm = _with_prd(fm, pid)
    if fm.get("status") != "pending":
        return fm, body
    if isinstance(fm.get("title"), str):
        fm["title"] = _CR_TITLE.sub(
            lambda m: f"PRD {pid} v{m.group(1)} -> v{m.group(2)}", fm["title"])
    body = _CR_SUMMARY.sub(
        lambda m: f"PRD {pid} v{m.group(1)} -> v{m.group(2)}:", body, count=1)
    return fm, body


def _staged_stories(fm, new_fms):
    """The story frontmatters a test case's PRD versions derive from: the
    stories it covers and, like the UAT renderer, every story of its flow's
    journey. `new_fms` holds the REWRITTEN concepts, so their refs carry ids."""
    flows, stories = set(), {}
    for ref in fm.get("covers") or []:
        rel = resolve_ref(ref)[0]
        cfm = new_fms.get(rel) or {}
        if cfm.get("type") == "User Story":
            stories[rel] = cfm
        elif cfm.get("type") == "Flow":
            flows.add(rel)
    if fm.get("flow"):
        flows.add(resolve_ref(fm["flow"])[0])
    for frel in flows:
        for entry in (new_fms.get(frel) or {}).get("journey") or []:
            rel = resolve_ref(entry.get("ref") or "")[0] \
                if isinstance(entry, dict) else ""
            cfm = new_fms.get(rel) or {}
            if cfm.get("type") == "User Story":
                stories[rel] = cfm
    return list(stories.values())


def _tc_versions(fm, pid, new_fms):
    """{prd id: version} for a test case in the old form. The version kept is
    the one the test case was generated from, not today's adopted one. Which
    PRDs it names comes from the helper the renderers use, fed the REWRITTEN
    stories and a synthetic registry holding the test case's own version."""
    old = fm["generated_from"]["prd_version"]
    if not pid or old is None:
        return {}
    return prd_versions_for(_staged_stories(fm, new_fms),
                            {"prds": {pid: {"adopted_version": old}}})


def _trace_rewrite(body, versions):
    """The body with the Traceability line's `PRD vN` replaced by the shared
    label. Anchored to the LAST `# Traceability` section, so the same text
    in an earlier section is never touched. None when it is not there."""
    heads = list(_TRACE_HEAD.finditer(body))
    if not heads:
        return None
    cut = heads[-1].end()
    tail, n = _TRACE.subn(f" · {prd_label(versions)} · wiki ", body[cut:],
                          count=1)
    return body[:cut] + tail if n else None


def _pairs(old, new, out):
    """Walk the frontmatter and its planned rewrite side by side and collect
    (old text, new text) for every string value and key the plan changes.
    The plan only substitutes strings, so both have one shape; the `prd` key
    the plan adds to a moved file is not a substitution and is skipped."""
    if isinstance(old, str) and isinstance(new, str):
        if old != new:
            out.add((old, new))
    elif isinstance(old, list) and isinstance(new, list):
        for a, b in zip(old, new):
            _pairs(a, b, out)
    elif isinstance(old, dict) and isinstance(new, dict):
        keys = [k for k in new if not (k == "prd" and "prd" not in old)]
        for a, b in zip(old, keys):
            if isinstance(a, str) and isinstance(b, str) and a != b:
                out.add((a, b))
            _pairs(old[a], new[b], out)
    return out


def _sub(fm_text, pairs, whole):
    """Frontmatter text with each planned string substituted where it stands.
    `whole` substitutes only a string that is a line's entire value or key
    (block style, plain or quoted); otherwise it is substituted wherever it
    stands as a token of its own (flow style, a value after other text)."""
    if not pairs:
        return fm_text
    new_of = dict(pairs)
    alt = "|".join(re.escape(o) for o in sorted(new_of, key=len, reverse=True))
    if not whole:
        return re.sub(rf"(?<![\w#/.-])(?:{alt})(?![\w/.#-])",
                      lambda m: new_of[m.group(0)], fm_text)
    value = re.compile(rf"^([ \t]*(?:- +)*(?:[^\s:#'\"\[\]{{}}-][^:]*?: +)?)"
                       rf"(['\"]?)({alt})\2([ \t]*)$")
    key = re.compile(rf"^([ \t]*(?:- +)*)(['\"]?)({alt})\2(:(?: .*)?)$")
    out = []
    for ln in fm_text.split("\n"):
        m = value.match(ln) or key.match(ln)
        out.append(m.group(1) + m.group(2) + new_of[m.group(3)] + m.group(2)
                   + m.group(4) if m else ln)
    return "\n".join(out)


def _add_prd(fm_text, pid):
    """`prd: <id>` as a top-level line directly after `description` (and its
    continuation lines), where _with_prd puts it."""
    line = yaml.safe_dump({"prd": pid}, default_flow_style=False).rstrip("\n")
    lines = fm_text.split("\n")
    at = len(lines)
    for i, ln in enumerate(lines):
        if ln.startswith("description:"):
            at = i + 1
            while at < len(lines) and (not lines[at].strip()
                                       or lines[at][:1] in " \t"):
                at += 1
            break
    return "\n".join(lines[:at] + [line] + lines[at:])


def _edit_in_place(raw, fm, new_fm, new_body):
    """`raw` with the planned references substituted where they stand in its
    frontmatter, its body replaced by the planned body, and every other byte
    kept. None unless the result parses back to exactly (new_fm, new_body):
    the edit is proven equal to the plan or it is not made."""
    m = _FM_SPLIT.match(raw)
    if not m:
        return None
    pairs = _pairs(fm, new_fm, set())
    for whole in (True, False):
        fm_text = _sub(m.group(1), pairs, whole)
        if "prd" in new_fm and "prd" not in fm:
            fm_text = _add_prd(fm_text, new_fm["prd"])
        try:
            if yaml.safe_load(fm_text) == new_fm:
                return (raw[:m.start(1)] + fm_text + raw[m.end(1):m.start(2)]
                        + new_body)
        except yaml.YAMLError:
            pass
    return None


def _edit_tc(raw, versions):
    """The test case text with its two spots changed and every other byte
    kept: the `  prd_version:` line under `generated_from:` becomes
    `prd_versions`, and the Traceability tail `PRD vN` becomes the shared
    label. None when a spot cannot be found."""
    m = _FM_SPLIT.match(raw)
    if not m:
        return None
    lines, out, in_gf, done = m.group(1).split("\n"), [], False, False
    for ln in lines:
        if ln.startswith("generated_from:"):
            in_gf = True
        elif in_gf and ln and not ln.startswith(" "):
            in_gf = False
        if in_gf and not done and re.match(r"^  prd_version:(\s|$)", ln):
            frag = yaml.safe_dump({"prd_versions": versions}, sort_keys=False,
                                  default_flow_style=False).rstrip("\n")
            out += ["  " + f for f in frag.split("\n")]
            done = True
            continue
        out.append(ln)
    body = _trace_rewrite(m.group(2), versions)
    if not done or body is None:
        return None
    return (raw[:m.start(1)] + "\n".join(out) + raw[m.end(1):m.start(2)] + body)


def _git(*argv):
    return subprocess.run(["git", *argv], cwd=ROOT, capture_output=True,
                          text=True, encoding="utf-8", errors="replace")


def _head():
    """The commit HEAD names, or None when git cannot say (never a made-up
    value: callers must not read 'unreadable' as 'unchanged')."""
    r = _git("rev-parse", "HEAD")
    return r.stdout.strip() if r.returncode == 0 and r.stdout.strip() else None


class _Unknown(Exception):
    pass


def _status():
    """`git status --porcelain` lines, or None when git cannot say."""
    r = _git("status", "--porcelain")
    return r.stdout.splitlines() if r.returncode == 0 else None


def _git_dirty():
    r = _git("status", "--porcelain")
    return r.stdout.strip() if r.returncode == 0 else ""


def _lint_problems():
    """[] only when lint exits 0. ANY other exit is a problem, with or
    without ERROR lines (a lint crash must not read as 'no errors')."""
    r = subprocess.run([sys.executable, wiki.__file__, "lint", "--no-commit"],
                       cwd=ROOT, capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    if r.returncode == 0:
        return []
    errs = [ln for ln in r.stdout.splitlines() if ln.startswith("ERROR")]
    if errs:
        return errs
    tail = (r.stdout + r.stderr).strip().splitlines()[-3:]
    return [f"lint exited {r.returncode}: " + " | ".join(tail)]


def _l10_tripped():
    """Stage everything, then ask lint L10's own function the question L10
    will ask of this commit later: read the staged diff with -M (as the L10
    `git log` does) and test it with wiki._l10_touches_assertion, per file so
    the refusal can name them."""
    _git("add", "-A")
    # Pinned so no user or repo git config changes the output format L10's
    # parser reads: L10 runs `git log --unified=0 -p -M`, which prints a/ and
    # b/ prefixes, runs no external diff and uses no colour.
    pin = ["-c", "diff.mnemonicPrefix=false", "-c", "diff.noprefix=false",
           "-c", "color.diff=false", "-c", "core.quotePath=false"]
    r = _git(*pin, "diff", "--cached", "-M", "--unified=0", "-p",
             "--no-ext-diff", "--no-textconv", "--no-color",
             "--src-prefix=a/", "--dst-prefix=b/")
    if r.returncode != 0:
        raise Refused("could not verify the staged change against lint L10: "
                      "git diff failed: " + (r.stderr.strip() or "no output"))
    names = _git(*pin, "diff", "--cached", "-M", "--name-only", "--no-color")
    in_wiki = [n for n in names.stdout.splitlines()
               if n.endswith(".md") and n.startswith(wiki._L10_WIKI_PREFIXES)]
    seen = [ln[6:].strip() for ln in r.stdout.splitlines()
            if ln.startswith("+++ b/")]
    seen = [n for n in seen if n.endswith(".md")
            and n.startswith(wiki._L10_WIKI_PREFIXES)]
    if in_wiki and "\n@@" in r.stdout and not seen:
        raise Refused("could not verify the staged change against lint L10: "
                      "the diff has wiki files but none could be attributed "
                      "to a wiki path (unexpected git output format).")
    tripped = []
    for chunk in ("\n" + r.stdout).split("\ndiff --git ")[1:]:
        if wiki._l10_touches_assertion(chunk):
            head = chunk.split("\n", 1)[0]
            unpaired = "\nnew file mode " in chunk.split("\n@@", 1)[0]
            tripped.append((head.rsplit(" b/", 1)[-1], unpaired))
    return tripped


class Journal:
    """Every mutation after the first goes through here, so any failure can
    put the tree back: old bytes of rewritten files, removal of created
    files and directories, reverse moves. Never `git reset --hard`, never
    `git clean`."""

    def __init__(self):
        self.undo = []
        self.ops = 0
        self.fault = os.environ.get(_FAULT_ENV, "")

    def _tick(self):
        self.ops += 1
        if self.fault.startswith("raise:") and \
                self.ops == int(self.fault.split(":", 1)[1]):
            raise RuntimeError("injected fault (TC_MIGRATE_PRDS_FAULT)")

    def _put_back(self, path, data):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)

    def mkdirs(self, d):
        missing = []
        while not d.exists() and d != d.parent:
            missing.append(d)
            d = d.parent
        for m in reversed(missing):
            self.undo.append(lambda m=m: m.rmdir() if m.exists() else None)
            m.mkdir()

    def snapshot(self, path):
        """Record `path`'s bytes (or its absence) before something else
        writes it."""
        if path.exists():
            old = path.read_bytes()
            self.undo.append(lambda: self._put_back(path, old))
        else:
            self.undo.append(lambda: path.unlink(missing_ok=True))

    def write_text(self, path, text):
        self._tick()
        self.mkdirs(path.parent)
        self.snapshot(path)
        path.write_bytes(text.encode("utf-8"))

    def unlink(self, path):
        self._tick()
        self.snapshot(path)
        path.unlink()

    def remove_tracked(self, d, tracked):
        """Remove only the files git tracks under `d` (`tracked`: posix paths
        relative to ROOT), then the directories that are left empty. Anything
        untracked or ignored stays, with its directory. Returns what stays."""
        for f in sorted(d.rglob("*")):
            if f.is_file() and f.relative_to(ROOT).as_posix() in tracked:
                self.unlink(f)
        subs = sorted((x for x in d.rglob("*") if x.is_dir()),
                      key=lambda x: len(x.parts), reverse=True) + [d]
        for sub in subs:
            if not any(sub.iterdir()):
                self.undo.append(lambda sub=sub: sub.mkdir(parents=True,
                                                           exist_ok=True))
                sub.rmdir()
        return [f.relative_to(ROOT).as_posix() for f in sorted(d.rglob("*"))
                if f.is_file()] if d.exists() else []

    def move(self, src, dst):
        self._tick()
        self.mkdirs(dst.parent)
        self.undo.append(lambda: shutil.move(str(dst), str(src))
                         if dst.exists() else None)
        shutil.move(str(src), str(dst))

    def restore(self):
        """Run every undo, newest first, then unstage the index. Returns the
        things that could not be put back."""
        failed, self.interrupted = [], False
        for fn in reversed(self.undo):
            try:
                fn()
            except BaseException as e:      # Ctrl-C must not abort the undo
                self.interrupted |= isinstance(e, KeyboardInterrupt)
                failed.append(str(e) or type(e).__name__)
        try:
            if _git("reset", "-q").returncode != 0:
                failed.append("the git index (run `git reset`)")
        except BaseException as e:
            self.interrupted |= isinstance(e, KeyboardInterrupt)
            failed.append("the git index (run `git reset`)")
        return failed


def _repin(bindings, concepts, new_fms):
    """Rewriting a ref inside a fragment (a voided AC's `voided.caused_by`)
    changes that fragment's hash. A pin that matched the fragment before the
    migration is moved to the new hash; a pin that was already out of date
    is left alone, so what was stale stays stale and nothing else becomes
    so. Mutates `bindings`; returns how many pins moved."""
    moved = 0
    for binding in bindings.values():
        pins = binding.get("fragment_pins") or {}
        for fragref, pin in list(pins.items()):
            tgt, _, frag = fragref.partition("#")
            old_fm, new_fm = (concepts.get(tgt) or (None,))[0], new_fms.get(tgt)
            if not old_fm or not new_fm or old_fm == new_fm:
                continue
            if frag.startswith("COVMAP:"):
                ac = frag[len("COVMAP:"):]
                old, new = covmap_hash(old_fm, ac), covmap_hash(new_fm, ac)
            else:
                old = fragment_hash_map(old_fm).get(frag)
                new = fragment_hash_map(new_fm).get(frag)
            if new and old == pin and new != pin:
                pins[fragref] = new
                moved += 1
    return moved


def _short(items, n=5):
    shown = "\n".join(f"    {r}" for r in items[:n])
    return shown + (f"\n    ... and {len(items) - n} more"
                    if len(items) > n else "")


def cmd_migrate_prds(args):
    for flag in ("--no-commit", "--allow-lint-errors"):
        if flag in sys.argv:
            sys.exit(f"migrate-prds refused: {flag} is not accepted here. The "
                     f"migration's guarantee is one clean commit or nothing; "
                     f"to inspect first, copy the project and run it there.")
    manifest = load_manifest()
    if not is_schema1(manifest):
        dirty = _git_dirty()
        if dirty:
            sys.exit(
                "migrate-prds: manifest.json is schema 2 but the working tree "
                "has uncommitted changes, so this may be a migration that "
                "stopped halfway, not a finished one.\n"
                "  Check `git status` and `git diff`; restore the tree with "
                "git (for example `git restore .` and removing the untracked "
                "paths listed) and re-run, or commit them if they are yours:\n"
                + _short(dirty.splitlines(), 8))
        print("migrate-prds: already migrated (manifest schema 2) - "
              "nothing changed.")
        return
    pid = arg_after(args, "--id") if "--id" in args else None
    title = (arg_after(args, "--title") if "--title" in args else "").strip()
    old = legacy_layout(manifest)
    has_prd = bool(old["adopted"] or old["staged_version"] or old["sections"]
                   or old["docs"] or old["staged"] or old["crs"])

    # ---- refusals: all of them, before anything is written ----------------
    if has_prd and not pid:
        sys.exit(
            f"migrate-prds refused: this project has an ingested PRD "
            f"(adopted v{old['adopted']}, {len(old['sections'])} section(s), "
            f"{len(old['docs'])} document(s) under inputs/prd/vN/, "
            f"{len(old['crs'])} change report(s)) and it needs a name.\n"
            f'  Re-run: py tools/wiki.py migrate-prds --id <id> --title "<title>"\n'
            f"  <id> is a lowercase-hyphen slug, for example rental-application.")
    if pid and not has_prd:
        sys.exit("migrate-prds refused: this project has no PRD to name "
                 "(nothing adopted, no sections, no uploads).\n"
                 "  Re-run without arguments; register PRDs afterwards with "
                 'ingest-prd --prd <id> --title "<title>".')
    if pid and prd_id_problem(pid):
        sys.exit(f"migrate-prds refused: --id {prd_id_problem(pid)}")
    if pid and not title:
        sys.exit(f'migrate-prds refused: --id {pid} needs --title "<title>"')
    if pid:
        taken = [r for r in (f"inputs/prd/{pid}", f"sources/prd/{pid}",
                             f"staging/{pid}", f"changereports/{pid}")
                 if (ROOT / r).exists()]
        if taken:
            sys.exit(f"migrate-prds refused: --id {pid} collides with an "
                     f"existing path: {', '.join(taken)}.\n  Pick another id.")
    un = unsealed_tcs(manifest)
    if un:
        sys.exit(
            f"migrate-prds refused: {len(un)} test case(s) not sealed.\n"
            f"{_short(un)}\n"
            f"  The migration re-seals every test case, which would hide "
            f"this drift.\n  Resolve it first (release or revert a hand "
            f"edit; seal after a render).\n{_PRE_UPGRADE}")
    dirty = _git_dirty()
    if dirty:
        sys.exit("migrate-prds refused: the working tree has uncommitted "
                 "changes, and the migration commits everything it finds.\n"
                 "  Commit or discard them first:\n" +
                 _short(dirty.splitlines()))
    problems = _lint_problems()
    if problems:
        sys.exit("migrate-prds refused: lint does not pass, so the migration "
                 "commit would be refused after the files had moved.\n"
                 "  Fix this first:\n" + _short(problems) + "\n" + _PRE_UPGRADE)
    head0 = _head()
    if not head0:
        sys.exit("migrate-prds refused: this is not a git repository with at "
                 "least one commit.")

    # ---- plan: every rewrite, in memory ------------------------------------
    slugs = {p.stem for p in old["sections"]}
    moving = set(old["sections"]) | set(old["crs"])
    crs = set(old["crs"])
    concepts = {rel: (fm, body, p) for rel, fm, body, p in all_concepts()}

    def rel_of(p):
        return p.relative_to(ROOT).as_posix()

    unreadable = [rel_of(p) for p in moving
                  if not concepts.get(rel_of(p)[:-3], (None,))[0]]
    staged = []
    for f in old["staged"]:
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            assert isinstance(data, dict)
        except (ValueError, AssertionError):
            unreadable.append(rel_of(f))
            continue
        staged.append((f, data))
    if unreadable:
        sys.exit("migrate-prds refused: these PRD files have no readable "
                 "frontmatter or JSON, so they cannot be moved safely:\n" +
                 "\n".join(f"    {u}" for u in unreadable) +
                 "\n  Repair them first. Nothing was changed.")
    badid = [f"{rel_of(p)}  (id is {concepts[rel_of(p)[:-3]][0].get('id')!r}, "
             f"expected 'prd#{p.stem}')" for p in old["sections"]
             if concepts[rel_of(p)[:-3]][0].get("id") != f"prd#{p.stem}"]
    if badid:
        sys.exit("migrate-prds refused: these section files do not carry the "
                 "id their file name implies, so their references cannot be "
                 "rewritten reliably:\n" + "\n".join(f"    {b}" for b in badid)
                 + "\n  Nothing was changed.")

    new_fms, plan = {}, {}
    for rel, (fm, body, p) in sorted(concepts.items()):
        if not fm:
            continue
        new_fm, new_body = fm, body
        if pid:
            new_fm = _rewrite(fm, pid, slugs)
            new_body = _rewrite_body(body, pid, slugs)
            if p in crs:
                new_fm, new_body = _report(new_fm, new_body, pid)
            elif p in moving:
                new_fm = _with_prd(new_fm, pid)
        new_fms[rel] = new_fm
        plan[rel] = (new_fm, new_body)

    writes, noncanon, tc_bad = [], [], []
    texts = {}                       # rel -> text the file will hold
    dropped, left_empty, n_tc_rewritten = [], [], 0
    reg = {"prds": {pid: {"adopted_version": 1}}} if pid else {}
    for rel, (fm, body, p) in sorted(concepts.items()):
        if not fm:
            continue
        new_fm, new_body = plan[rel]
        dest = p.parent / pid / p.name if pid and p in moving else p
        raw = p.read_bytes().decode("utf-8")
        if fm.get("type") == "Test Case":
            gf = fm.get("generated_from")
            if isinstance(gf, dict) and "prd_version" in gf:
                versions = _tc_versions(new_fm, pid, new_fms)
                if pid and gf["prd_version"] is not None and not versions:
                    dropped.append(f"{fm.get('id', rel)} (v{gf['prd_version']})")
                expect_fm = dict(new_fm, generated_from={
                    ("prd_versions" if k == "prd_version" else k):
                    (versions if k == "prd_version" else v)
                    for k, v in gf.items()})
                # The two spots first, then every other planned ref (a
                # retirement.caused_by naming a moved section). The second
                # step returns nothing unless the whole text parses back to
                # the plan.
                text = _edit_tc(raw, versions)
                body = _trace_rewrite(new_body, versions)
                if text is not None and body is not None:
                    m = _FM_SPLIT.match(text)
                    text = _edit_in_place(text, yaml.safe_load(m.group(1)),
                                          expect_fm, body)
                if text is None or body is None:
                    tc_bad.append(rel)
                    continue
                texts[rel] = text
                writes.append((p, p, text, True))
                n_tc_rewritten += 1
                continue
            if isinstance(gf, dict) and gf.get("prd_versions") == {} and pid \
                    and prd_versions_for(_staged_stories(new_fm, new_fms), reg):
                left_empty.append(fm.get("id", rel))
        if new_fm == fm and new_body == body and dest == p:
            texts[rel] = raw
            continue
        if concept_text(fm, body) == raw:
            text = concept_text(new_fm, new_body)
        else:
            # Not the text write_concept produces: re-serialising it would
            # change quotes, comments or wrapping and could re-emit an
            # assertion line. Edit the references where they stand instead.
            text = _edit_in_place(raw, fm, new_fm, new_body)
            if text is None:
                noncanon.append(rel)
                continue
        texts[rel] = text
        writes.append((p, dest, text, False))
    if tc_bad or noncanon:
        parts = []
        if tc_bad:
            parts.append(
                "these test cases have generated_from.prd_version but their "
                "`prd_version` line or the ' · PRD vN · wiki ' tail of their "
                "# Traceability section is not where the migration can "
                "rewrite it, or a reference to a moved section in their "
                "frontmatter could not be rewritten in place:\n"
                + "\n".join(f"    {r}" for r in tc_bad))
        if noncanon:
            parts.append(
                "these files reference a moved section, their text is not in "
                "the canonical form write_concept produces (quotes, comments, "
                "wrapping), and the reference could not be rewritten in place "
                "(it is folded over several lines or written with escapes):\n"
                + "\n".join(f"    {r}" for r in noncanon) +
                "\n  Re-serialising such a file could re-emit an assertion "
                "line, which lint L10 reads as an assertion tc-agent made, so "
                "the migration will not. Write each such reference on one "
                "line as a plain string.")
        sys.exit("migrate-prds refused: " + "\n\n  and ".join(parts) +
                 "\n" + _PRE_UPGRADE + "\n  Nothing was changed.")
    notes = _notes(pid, slugs, concepts, texts, dropped, left_empty)

    # ---- write: the first mutation is below this line ----------------------
    journal = Journal()
    tracked = set(_git("ls-files", "-z", "--", "inputs/prd")
                  .stdout.split("\0"))
    stays = []
    try:
        for p, dest, text, _tc in writes:
            if dest != p:
                journal.unlink(p)
            journal.write_text(dest, text)
        if pid:
            for d in old["vdirs"]:
                journal.move(d, ROOT / "inputs/prd" / pid / d.name)
            for f, data in staged:
                data = {"prd": pid, **data}
                data["source_file"] = _ref(data.get("source_file") or "",
                                           pid, slugs)
                journal.write_text(ROOT / "staging" / pid / f.name,
                                   json.dumps(data, indent=1,
                                              ensure_ascii=False))
                journal.unlink(f)
        else:
            # No PRD: a version directory holding only furniture means
            # nothing under inputs/prd/<id>/vN/. Keep inputs/prd/ tracked.
            # Only what git tracks is removed; an untracked or ignored file
            # (a Thumbs.db) is not recoverable from git, so it stays.
            for d in old["vdirs"]:
                stays += journal.remove_tracked(d, tracked)
            if old["vdirs"]:
                journal.write_text(ROOT / "inputs/prd/.gitkeep", "")

        new = {"schema_version": 2, "prds": {}}
        if pid:
            set_prd_versions(new, pid, adopted=old["adopted"],
                             staged=old["staged_version"], title=title)
        for k, v in manifest.items():
            if k not in ("schema_version", "prds", "adopted_prd_version",
                         "staged_prd_version"):
                new[k] = v
        # The flat prd# keys go; rebuild_manifest re-adds each section under
        # its new id from the frontmatter just written.
        new["sources"] = {k: v for k, v in (new.get("sources") or {}).items()
                          if not k.startswith("prd#")}
        rebuild_manifest(new)
        repinned = _repin(new.get("bindings") or {}, concepts, new_fms)
        hashes = new.setdefault("tc_hashes", {})
        for rel, fm, _body, p in all_concepts():
            if fm and fm.get("type") == "Test Case":
                hashes[rel] = sha256(p.read_bytes())
        # index_paths() is read here, after the moves, so it names the
        # per-PRD index this run creates as well as the ones it rewrites.
        for path in [ROOT / "manifest.json", ROOT / "log.md"] + index_paths():
            journal.snapshot(path)
        save_manifest(new)
        write_indexes()
        what = (f"PRD registered as {pid} ('{title}'), {len(old['sections'])} "
                f"section(s) moved" if pid else "no PRD registered")
        append_log(f"**Migration (agent)**: manifest schema 2; {what}; "
                   f"{n_tc_rewritten} test case(s) rewritten and re-sealed "
                   f"with prd_versions")

        tripped = _l10_tripped()
        if tripped:
            unpaired = [t for t, new_file in tripped if new_file]
            in_place = [t for t, new_file in tripped if not new_file]
            why = []
            if unpaired:
                why.append(
                    "git cannot pair these moved files with their old paths "
                    "as renames (too many of their lines change), so their "
                    "asserted_by:/status: lines look newly added:\n" +
                    "\n".join(f"    {t}" for t in unpaired) +
                    "\n  This is most often a change report that cites many "
                    "moved sections. To let it pass, a human shortens the "
                    "list of references in that record (so fewer of its "
                    "lines change), commits, and re-runs.")
            if in_place:
                why.append(
                    "rewriting a reference in these files changes a line "
                    "that carries asserted_by: or an asserted status: (the "
                    "file did not move):\n" +
                    "\n".join(f"    {t}" for t in in_place) +
                    "\n  A human moves the reference off that line (one key "
                    "per line), commits, and re-runs.")
            raise Refused(
                "lint L10 would read this commit as an assertion tc-agent "
                "made: " + "\n  and ".join(why) +
                "\n  The migration will not reword a record a human "
                "asserted, and nothing may bypass L10.")
        try:
            agent_commit("migrate-prds: manifest schema 2, "
                         + (f"PRD {pid}" if pid else "no PRD"))
        except SystemExit:
            raise Refused("lint refused the migrated project (errors above)")
        landed = _head()
        if landed is None:
            raise _Unknown()
        if landed == head0:
            raise Refused("the commit did not go through (see [git] above)")
    except BaseException as e:
        now = _head()
        if now is None or isinstance(e, _Unknown):
            sys.exit("migrate-prds failed and git cannot report HEAD, so "
                     "whether the migration commit landed is UNKNOWN. "
                     "Nothing was rolled back.\n  Check `git log -1` and "
                     "`git status`: if there is no migrate-prds commit, "
                     "restore with `git restore .` and remove the untracked "
                     "paths `git status` lists; if there is one, the "
                     "migration is done.")
        if now != head0:
            sys.exit(f"migrate-prds: the migration IS committed ({now[:8]}) "
                     f"but a later step failed ({type(e).__name__}: {e}). "
                     f"Nothing was undone.\n  Check `git status`.")
        failed = journal.restore()
        left = _status()
        problems = []
        if failed:
            problems.append("could not put back " + "; ".join(failed))
        if left is None:
            problems.append("`git status` could not be read to verify")
        elif left:
            problems.append("still different from the last commit:\n" +
                            "\n".join(f"    {ln}" for ln in left[:10]))
        if problems:
            sys.exit(f"migrate-prds failed ({type(e).__name__}: {e}) AND the "
                     f"roll-back is not verified clean: " +
                     "\n  ".join(problems) + "\n  Restore from the last "
                     "commit (`git restore .`; remove untracked paths) "
                     "before anything else.")
        if isinstance(e, KeyboardInterrupt):
            sys.exit("migrate-prds interrupted; every file it wrote was "
                     "restored (git status is clean); nothing was committed.")
        if isinstance(e, Refused):
            sys.exit(f"migrate-prds refused: {e}\n  Every file it wrote was "
                     f"restored (git status is clean); nothing was committed.")
        sys.exit(f"migrate-prds failed: {type(e).__name__}: {e}\n  Every "
                 f"file it wrote was restored (git status is clean); "
                 f"nothing was committed.")

    print(f"migrate-prds: manifest schema 2; {what}; {len(writes)} file(s) "
          f"rewritten, {n_tc_rewritten} test case(s) rewritten and re-sealed")
    if repinned:
        print(f"note: {repinned} fragment pin(s) moved with a fragment whose "
              f"reference to a moved section was rewritten (a pin that was "
              f"already out of date was left as it was).")
    after = _status()
    if after:
        print(f"note: the migration IS committed ({landed[:8]}), but the "
              f"working tree is not clean afterwards (a post-commit hook?). "
              f"Nothing was undone; check:\n" +
              "\n".join(f"    {ln}" for ln in after[:10]))
    if stays:
        print("note: left in place (git does not track them, so removing "
              "them would be unrecoverable): " + ", ".join(stays))
    for n in notes:
        print(n)
    print("note: every rewritten test case hash changed, so compiled "
          "workbooks under build/ read as changed until you recompile the "
          "suites (py tools/wiki.py suite compile <name>).")


def _notes(pid, slugs, concepts, texts, dropped, left_empty):
    """Things worth a human's eye after migrating. Never a refusal."""
    out = []
    if pid and slugs:
        alt = "|".join(re.escape(s) for s in sorted(slugs, key=len,
                                                    reverse=True))
        flat = re.compile(rf"(?:sources/prd/(?:{alt})(?![\w/-])"
                          rf"|(?<![\w#/])prd#(?:{alt})(?![\w/-]))")
        hits = []
        for rel, (fm, _b, p) in sorted(concepts.items()):
            m = flat.search(texts.get(rel) or p.read_text(encoding="utf-8"))
            if m:
                hits.append(f"note: {rel}.md still names the flat '{m.group(0)}'"
                            f" (not a reference the migration rewrites; check "
                            f"it by hand)")
        out += hits[:20] + ([f"note: ... and {len(hits) - 20} more files"]
                            if len(hits) > 20 else [])
    if dropped:
        out.append(f"note: {len(dropped)} test case(s) carried a PRD version "
                   f"but their story cites no PRD, so prd_versions is {{}}: "
                   + ", ".join(dropped[:10])
                   + (" ..." if len(dropped) > 10 else ""))
    if left_empty:
        out.append(f"note: {len(left_empty)} test case(s) already have "
                   f"prd_versions {{}} although their story cites the PRD; "
                   f"re-render them to record it: " + ", ".join(left_empty[:10])
                   + (" ..." if len(left_empty) > 10 else ""))
    return out
