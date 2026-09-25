#!/usr/bin/env python3
"""ID migration (tc-copilot-spec §10). The ONLY sanctioned way to change
`ids.tc_format` after the freeze: rewrites every TC ID, filename, manifest
binding/hash/counter, and inbound reference, and emits a migration map —
all in one commit. Silent renumbering breaks downstream references (defect
reports, TMS imports); the CSV map is the survival kit.
"""
import csv
import re
import sys
from datetime import datetime
from pathlib import Path

from wiki import (ROOT, agent_commit, append_log, load_all, load_config,
                  resolve_ref, save_manifest, sha256, write_concept)


def components_of(fm, rel):
    """Derive template variables for one TC."""
    covers = fm.get("covers") or []
    first_ac = resolve_ref(covers[0])[1] or "" if covers else ""
    m = re.match(r"^(.*)-AC(\d+)$", first_ac)
    story_num, ac, ac_num = ((m.group(1), f"AC{int(m.group(2)):02d}",
                              int(m.group(2))) if m else ("", "", None))
    seq = int(re.search(r"(\d+)$", fm["id"]).group(1))
    module = Path(resolve_ref(fm["module"])[0]).name if fm.get("module") else ""
    flow = Path(resolve_ref(fm["flow"])[0]).name if fm.get("flow") else ""
    return {"story_num": story_num, "ac": ac, "ac_num": ac_num, "seq": seq,
            "module": module, "flow": flow,
            "kind": (fm.get("kind") or "").upper()}


def transform(obj, path_map, id_map):
    """Recursively rewrite old TC paths/IDs inside frontmatter values."""
    if isinstance(obj, str):
        for old, new in path_map.items():
            obj = obj.replace(old, new)
        return id_map.get(obj, obj)
    if isinstance(obj, list):
        return [transform(x, path_map, id_map) for x in obj]
    if isinstance(obj, dict):
        return {k: transform(v, path_map, id_map) for k, v in obj.items()}
    return obj


def cmd_migrate_ids(args):
    cfg = load_config()
    new_fmt = cfg["ids"]["tc_format"]
    concepts, manifest = load_all()
    old_fmt = manifest.get("id_format")
    if not manifest.get("id_config_frozen"):
        sys.exit("migrate-ids: IDs are not frozen yet — just edit config.yaml")
    if old_fmt == new_fmt:
        sys.exit(f"migrate-ids: config format equals frozen format ({old_fmt}); "
                 "edit ids.tc_format in config.yaml first")

    tcs = {rel: (fm, body, p) for rel, (fm, body, p) in concepts.items()
           if fm and fm.get("type") == "Test Case"}
    fmt_uat = cfg["ids"].get("tc_format_uat") or new_fmt
    unchanged = []
    id_map, path_map, rows = {}, {}, []
    for rel, (fm, _b, _p) in sorted(tcs.items()):
        comps = components_of(fm, rel)
        fmt = fmt_uat if fm.get("kind") == "uat" else new_fmt
        if "{ac" in fmt and comps.get("ac_num") is None:
            unchanged.append(fm["id"])
            rows.append((fm["id"], fm["id"], rel + ".md", rel + ".md (unchanged: no AC binding)"))
            continue
        try:
            new_id = fmt.format(**comps)
        except (KeyError, IndexError) as e:
            sys.exit(f"migrate-ids: template {fmt!r} failed for {fm['id']}: {e}")
        if new_id == fm["id"]:
            continue
        id_map[fm["id"]] = new_id
        new_rel = str(Path(rel).parent / new_id).replace("\\", "/")
        path_map["/" + rel + ".md"] = "/" + new_rel + ".md"
        rows.append((fm["id"], new_id, rel + ".md", new_rel + ".md"))
    print(f"unchanged (no AC binding): {unchanged}")
    dupes = [i for i in set(id_map.values()) if list(id_map.values()).count(i) > 1]
    if dupes:
        sys.exit(f"migrate-ids REFUSED: template produces duplicate IDs {dupes[:5]} "
                 "— the format must keep every TC unique (e.g. include {ac})")

    # rewrite every concept's frontmatter references, rename TC files
    for rel, (fm, body, p) in concepts.items():
        if not fm:
            continue
        new_fm = transform(fm, path_map, id_map)
        is_tc = rel in tcs
        renamed = is_tc and fm["id"] in id_map
        # new_fm["id"] is already id_map[fm["id"]] here: transform() recurses
        # into every frontmatter string, including "id", through the same
        # id_map.get(obj, obj) substitution — no separate override needed.
        if new_fm != fm or renamed:
            write_concept(p, new_fm, body)
        if renamed:
            new_p = p.parent / (id_map[fm["id"]] + ".md")
            p.rename(new_p)

    # manifest: bindings, tc_hashes, counters
    rel_map = {old.strip("/")[:-3]: new.strip("/")[:-3]
               for old, new in path_map.items()}
    manifest["tc_hashes"] = {
        rel_map.get(k, k): sha256((ROOT / (rel_map.get(k, k) + ".md")).read_bytes())
        for k in manifest.get("tc_hashes", {})}
    for b in manifest.get("bindings", {}).values():
        b["tc"] = rel_map.get(b["tc"], b["tc"])
    manifest["id_format"] = new_fmt
    save_manifest(manifest)

    # suites extra_include / extra_exclude
    import yaml as _yaml
    for spath in sorted((ROOT / "suites").glob("*.yaml")):
        s = _yaml.safe_load(spath.read_text(encoding="utf-8"))
        changed = False
        for key in ("extra_include", "extra_exclude"):
            if s.get(key):
                s[key] = [id_map.get(x, x) for x in s[key]]
                changed = True
        if changed:
            spath.write_text(_yaml.safe_dump(s, sort_keys=False),
                             encoding="utf-8", newline="\n")

    outdir = ROOT / "build/reports"
    outdir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    with open(outdir / f"id-migration-{ts}.csv", "w", newline="",
              encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["old_id", "new_id", "old_path", "new_path"])
        w.writerows(rows)
    append_log(f"**Migration (agent)**: {len(rows)} TC IDs migrated "
               f"'{old_fmt}' -> '{new_fmt}' (map: build/reports/id-migration-{ts}.csv)")
    print(f"migrated {len(rows)} TC IDs; map at build/reports/id-migration-{ts}.csv")
    agent_commit(f"migrate-ids: '{old_fmt}' -> '{new_fmt}' ({len(rows)} TCs)")
