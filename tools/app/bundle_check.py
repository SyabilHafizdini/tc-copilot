#!/usr/bin/env python3
"""Freshness check for the committed viewer bundle.

tools/app/web/dist/viewer.html is a build artifact that is committed, so the
repo runs on Python alone. A committed artifact can go stale silently, so this
records a digest of every build input and compares on demand -- pure Python, so
it works on a machine with no JS runtime.

Run `py tools/app/bundle_check.py --write` after every `npm run build:viewer`.
"""
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
WEB = ROOT / "tools/app/web"
BUNDLE = WEB / "dist/viewer.html"
# Outside dist/ deliberately: `vite build` empties outDir on every build.
MANIFEST = WEB / "build-manifest.json"

APP_BUNDLE = WEB / "dist-app/index.html"
# src/**/* (not just src/app/**/*): the app is expected to start importing
# vendored graph components from src/components/ or src/lib/ in a later
# sub-project, and at that point editing one of those files changes the app
# bundle without this glob noticing. Over-invalidating is the safe failure
# direction here -- a viewer-only edit under src/ will now also report the
# app bundle stale, which is spurious but harmless (an extra rebuild), versus
# under-invalidating, which is a silent, permanent false pass.
APP_SOURCE_GLOBS = ("src/**/*", "app.html",
                    "vite.app.config.ts", "tsconfig.json", "package.json",
                    "package-lock.json")

# Every file whose change should invalidate the bundle. node_modules is only
# approximated by package-lock.json -- a hand-patched node_modules, a partial
# install, or a different Node/npm major can yield a different bundle with an
# unchanged digest. scripts/ is excluded: it drives baking, not the bundle.
SOURCE_GLOBS = ("src/**/*", "index.html", "vite.viewer.config.ts",
                "tsconfig.json", "package.json", "package-lock.json")


def source_files():
    """Sorted workspace-relative paths of every VIEWER build input.

    src/app/** belongs to the operator app (sub-project B), not the viewer, so
    editing it must not report the viewer bundle stale.
    """
    out = set()
    for pattern in SOURCE_GLOBS:
        for p in WEB.glob(pattern):
            if not p.is_file():
                continue
            rel = p.relative_to(WEB).as_posix()
            # Exclude test-only files and the operator app's own sources.
            if ".test." in p.name or p.name == "test-setup.ts":
                continue
            if rel.startswith("src/app/"):
                continue
            out.add(rel)
    return sorted(out)


def source_digest():
    """One sha256 over (path, content-hash) pairs.

    Hashing the path as well as the content makes the digest sensitive to
    renames and deletions, not just edits.
    """
    h = hashlib.sha256()
    for rel in source_files():
        h.update(rel.encode())
        h.update(hashlib.sha256((WEB / rel).read_bytes()).hexdigest().encode())
    return h.hexdigest()


def bundle_digest():
    return hashlib.sha256(BUNDLE.read_bytes()).hexdigest()


def app_source_files():
    """Sorted workspace-relative paths of every APP build input."""
    out = set()
    for pattern in APP_SOURCE_GLOBS:
        for p in WEB.glob(pattern):
            if p.is_file() and ".test." not in p.name:
                out.add(p.relative_to(WEB).as_posix())
    return sorted(out)


def app_source_digest():
    h = hashlib.sha256()
    for rel in app_source_files():
        h.update(rel.encode())
        h.update(hashlib.sha256((WEB / rel).read_bytes()).hexdigest().encode())
    return h.hexdigest()


def app_bundle_digest():
    return hashlib.sha256(APP_BUNDLE.read_bytes()).hexdigest()


def write_manifest():
    MANIFEST.write_text(
        json.dumps({"sources": source_digest(),
                    "viewer_html": bundle_digest(),
                    "app_sources": app_source_digest(),
                    "app_html": app_bundle_digest()}, indent=1) + "\n",
        encoding="utf-8", newline="\n")


def check(record=None):
    """[] when both committed bundles are fresh, else human-readable reasons."""
    for path, what, build in ((BUNDLE, "viewer", "build:viewer"),
                              (APP_BUNDLE, "app", "build:app")):
        if not path.exists():
            return [f"missing {what} bundle: {path.relative_to(ROOT).as_posix()} "
                    f"-- run: cd tools/app/web && npm run {build}"]
    if record is None:
        if not MANIFEST.exists():
            return [f"missing manifest: {MANIFEST.relative_to(ROOT).as_posix()} "
                    f"-- run: py tools/app/bundle_check.py --write"]
        record = json.loads(MANIFEST.read_text(encoding="utf-8"))
    errs = []
    if record.get("sources") != source_digest():
        errs.append("viewer sources changed since the bundle was built "
                    "-- run: cd tools/app/web && npm run build:viewer")
    if record.get("viewer_html") != bundle_digest():
        errs.append("dist/viewer.html was modified after it was built "
                    "-- rebuild rather than hand-editing it")
    if record.get("app_sources") != app_source_digest():
        errs.append("app sources changed since the bundle was built "
                    "-- run: cd tools/app/web && npm run build:app")
    if record.get("app_html") != app_bundle_digest():
        errs.append("dist-app/index.html was modified after it was built "
                    "-- rebuild rather than hand-editing it")
    return errs


if __name__ == "__main__":
    if "--write" in sys.argv:
        write_manifest()
        print(f"wrote {MANIFEST.relative_to(ROOT).as_posix()}")
        sys.exit(0)
    problems = check()
    for p in problems:
        print(f"ERROR: {p}", file=sys.stderr)
    sys.exit(1 if problems else 0)
