#!/usr/bin/env python3
"""Read-only dashboard renderer (tc-copilot-spec §16).

Emits build/status/dashboard.json (the data feed) and a fully self-contained
build/status/dashboard.html (no external requests: styles, data and the small
force-layout are inline). The dashboard never writes wiki content; every
"action" on it is documentation of which CLI command the human runs.

Status colors follow the validated reserved status palette (dataviz skill
reference instance) and are never the only carrier: every state is also text.
"""
import json
import re
from pathlib import Path

from wiki import ROOT, body_section, load_all, load_config, resolve_ref, sha256
from wiki_coverage import components_covering, load_coverage
from wiki_graph import build_model, collect


def gather():
    concepts, manifest = load_all()
    stories_d, tcs, flows, terms, prd, figma, modules, _resolutions, coverage = \
        collect(concepts, manifest)

    story_rows = []
    for rel, fm in sorted(stories_d.items()):
        _fm, body, _p = concepts[rel]
        oq = body_section(body, "Open Questions") or ""
        openq = len([ln for ln in oq.splitlines() if ln.strip().startswith("-")])
        counts = {"active": 0, "stale": 0, "retired": 0}
        stale_causes = []
        for trel, tfm in tcs.items():
            if any(resolve_ref(c)[0] == rel for c in tfm.get("covers") or []):
                st = tfm.get("status")
                if st in counts:
                    counts[st] += 1
                if st == "stale":
                    stale_causes += [c.get("cause") for c in
                                     tfm.get("stale_because") or []]
        drift = []
        for trel, h in manifest.get("tc_hashes", {}).items():
            p = ROOT / (trel + ".md")
            if p.exists() and sha256(p.read_bytes()) != h:
                drift.append(trel.rsplit("/", 1)[-1])
        cmap, disp, _cs = load_coverage(fm)
        comp_stats = {"total": 0, "covered": 0, "acs_without_tcs": 0,
                      "out_of_scope": 0, "gaps": 0}
        for c in fm.get("components") or []:
            comp_stats["total"] += 1
            covering = components_covering(cmap, c["id"])
            has_active = any(
                t[1].get("status") == "active"
                for a in covering for t in coverage.get(f"{rel}#{a}", []))
            if covering and has_active:
                comp_stats["covered"] += 1
            elif covering:
                comp_stats["acs_without_tcs"] += 1
            elif c["id"] in disp:
                comp_stats["out_of_scope"] += 1
            else:
                comp_stats["gaps"] += 1
        story_rows.append({
            "id": fm["id"], "title": fm.get("title"), "status": fm.get("status"),
            "module": Path(resolve_ref(fm["module"])[0]).name
            if fm.get("module") else None,
            "acs": len(fm.get("acceptance_criteria") or []),
            "open_questions": openq, "tc": counts,
            "stale_causes": sorted(set(stale_causes)),
            "asserted_by": fm.get("asserted_by"),
            "components": comp_stats,
        })

    term_rows = []
    for rel, fm in sorted(terms.items()):
        inbound = sum(1 for s, k, t in manifest.get("edges", [])
                      if k == "uses_terms" and t == rel)
        term_rows.append({"id": fm["id"], "title": fm.get("title"),
                          "status": fm.get("status"),
                          "aliases": fm.get("aliases") or [],
                          "inbound": inbound})

    gaps = []
    for rel, fm in stories_d.items():
        for ac in fm.get("acceptance_criteria") or []:
            if ac.get("status") == "voided":
                continue
            cov = coverage.get(f"{rel}#{ac['id']}", [])
            if not any(t[1].get("status") == "active" for t in cov):
                gaps.append(f"{rel}#{ac['id']}")

    cards = []
    cards_dir = ROOT / "build/cards"
    if cards_dir.exists():
        for p in sorted(cards_dir.glob("*.json")):
            try:
                c = json.loads(p.read_text(encoding="utf-8"))
                cards.append({"file": p.name, "type": c.get("card_type"),
                              "session": c.get("session"),
                              "story": c.get("story")})
            except json.JSONDecodeError:
                pass

    crs = []
    for p in sorted((ROOT / "changereports").glob("CR-*.md")) if \
            (ROOT / "changereports").exists() else []:
        cfm, _b = __import__("wiki").read_concept(p)
        if cfm:
            crs.append({"id": cfm["id"], "status": cfm.get("status"),
                        "from": cfm.get("from_version"),
                        "to": cfm.get("to_version")})

    figma_rows = [{"id": fm["id"], "status": fm.get("status"),
                   "version": fm.get("version")} for _r, fm in sorted(figma.items())]
    suites = [p.stem for p in sorted((ROOT / "suites").glob("*.yaml"))] if \
        (ROOT / "suites").exists() else []

    dashboard = {
        "project": load_config()["project"]["name"],
        "prd": {"adopted": manifest.get("adopted_prd_version"),
                "staged": manifest.get("staged_prd_version")},
        "stories": story_rows, "terms": term_rows, "figma": figma_rows,
        "gaps": gaps, "cards": cards, "change_reports": crs, "suites": suites,
        "flows": [{"id": fm["id"], "status": fm.get("status")}
                  for _r, fm in sorted(flows.items())],
        "totals": {"tcs": len(tcs), "stories": len(stories_d),
                   "terms": len(terms), "prd_sections": len(prd)},
    }
    graph = build_model(concepts, manifest)
    return dashboard, graph


# state -> reserved status palette (validated; text label always accompanies)
STATE_COLORS = {
    "aligned": "#0ca30c", "asserted": "#0ca30c", "active": "#0ca30c",
    "needs-review": "#fab219", "stale": "#ec835a",
    "voided": "#d03b3b", "removed": "#d03b3b",
    "retired": "#8a8984", "proposed": "#8a8984", "draft": "#8a8984",
    "in-alignment": "#fab219", "pending": "#fab219",
}

HTML_TEMPLATE = """<!doctype html>
<html><head><meta charset="utf-8">
<title>tc-copilot dashboard — __PROJECT__</title>
<style>
:root { --surface:#fcfcfb; --ink:#1f1f1e; --muted:#6c6b68; --line:#e4e2de; }
@media (prefers-color-scheme: dark) {
  :root { --surface:#1a1a19; --ink:#ecebe8; --muted:#a3a19c; --line:#3a3936; }
}
body { background:var(--surface); color:var(--ink);
  font:14px/1.5 system-ui, "Segoe UI", sans-serif; margin:2rem auto;
  max-width:1100px; padding:0 1rem; }
h1 { font-size:1.4rem; } h2 { font-size:1.05rem; margin-top:2rem; }
table { border-collapse:collapse; width:100%; font-size:13px; }
th, td { text-align:left; padding:4px 10px; border-bottom:1px solid var(--line);
  vertical-align:top; }
th { color:var(--muted); font-weight:600; }
.badge { display:inline-flex; align-items:center; gap:6px; }
.dot { width:9px; height:9px; border-radius:50%; display:inline-block; }
.muted { color:var(--muted); }
#graph { width:100%; height:520px; border:1px solid var(--line);
  border-radius:8px; }
.legend { display:flex; gap:1.2rem; flex-wrap:wrap; margin:.5rem 0;
  font-size:12px; color:var(--muted); }
code { font-size:12px; }
.note { color:var(--muted); font-size:12px; }
</style></head><body>
<h1>tc-copilot — __PROJECT__</h1>
<p class="note">Read-only render of wiki + manifest (spec §16). Actions happen
via the CLI: assert / retire / approve-cr — this page never writes.</p>
<div id="summary"></div>
<h2>Project status</h2><div id="stories"></div>
<h2>RTM graph <span class="note">(drag to pan focus; hover a node for its
id/state — states are also listed in the tables, never color alone)</span></h2>
<div class="legend" id="legend"></div>
<svg id="graph"></svg>
<h2>Coverage gaps</h2><div id="gaps"></div>
<h2>Glossary</h2><div id="terms"></div>
<h2>Change reports & cards</h2><div id="admin"></div>
<script>
const DASH = __DASH__;
const GRAPH = __GRAPH__;
const COLORS = __COLORS__;
const dot = s => `<span class="badge"><span class="dot" style="background:${
  COLORS[s] || '#8a8984'}"></span>${s}</span>`;
document.getElementById('summary').innerHTML =
  `<p>PRD adopted <b>v${DASH.prd.adopted}</b>` +
  (DASH.prd.staged ? ` — <b>v${DASH.prd.staged} staged, not adopted</b>` : '') +
  ` · ${DASH.totals.prd_sections} sections · ${DASH.totals.stories} stories · ` +
  `${DASH.totals.tcs} test cases · suites: ${DASH.suites.join(', ') || '—'}</p>`;
const compCell = c => {
  if (!c || !c.total) return '<span class="muted">—</span>';
  let s = `${c.covered}/${c.total} covered`;
  if (c.acs_without_tcs) s += ` · ${c.acs_without_tcs} no-TC`;
  if (c.out_of_scope) s += ` · ${c.out_of_scope} oos`;
  if (c.gaps) s += ` · <span class="badge"><span class="dot" style="background:${
    COLORS.voided}"></span>${c.gaps} GAP</span>`;
  return s;
};
document.getElementById('stories').innerHTML = '<table><tr><th>story</th>' +
  '<th>status</th><th>module</th><th>ACs</th><th>openQ</th>' +
  '<th>TC active/stale/retired</th><th>components</th><th>stale causes</th></tr>' +
  DASH.stories.map(s => `<tr><td>${s.id} <span class="muted">${s.title}</span></td>` +
    `<td>${dot(s.status)}</td><td>${s.module || ''}</td><td>${s.acs}</td>` +
    `<td>${s.open_questions}</td><td>${s.tc.active}/${s.tc.stale}/${s.tc.retired}</td>` +
    `<td>${compCell(s.components)}</td>` +
    `<td class="muted">${s.stale_causes.join('; ')}</td></tr>`).join('') + '</table>';
document.getElementById('gaps').innerHTML = DASH.gaps.length
  ? '<ul>' + DASH.gaps.map(g => `<li><code>${g}</code> — no active covering TC</li>`).join('') + '</ul>'
  : '<p class="muted">None — every active AC has an active covering TC.</p>';
document.getElementById('terms').innerHTML = '<table><tr><th>term</th>' +
  '<th>status</th><th>aliases</th><th>inbound uses</th></tr>' +
  DASH.terms.map(t => `<tr><td>${t.title}</td><td>${dot(t.status)}</td>` +
    `<td class="muted">${t.aliases.join(', ')}</td><td>${t.inbound}</td></tr>`)
    .join('') + '</table>';
document.getElementById('admin').innerHTML =
  '<p>Change reports: ' + (DASH.change_reports.map(c =>
    `${c.id} (v${c.from}→v${c.to}, ${c.status})`).join(', ') || 'none') + '</p>' +
  '<p>Cards: ' + (DASH.cards.map(c => `${c.session} (${c.type})`).join(', ')
    || 'none') + '</p>' +
  '<p>Flows: ' + (DASH.flows.map(f => `${f.id} (${f.status})`).join(', ')
    || 'none') + '</p>';

// legend: node types (shape/size) + states (status palette)
const states = [...new Set(GRAPH.nodes.map(n => n.state))];
document.getElementById('legend').innerHTML =
  states.map(dot).join(' ') +
  ' <span>size: PRD/Module &gt; Story/Flow &gt; TC/AC/Term</span>';

// minimal force layout — no external libraries (offline artifact)
const svg = document.getElementById('graph');
const W = svg.clientWidth || 1060, H = 520;
svg.setAttribute('viewBox', `0 0 ${W} ${H}`);
const nodes = GRAPH.nodes.map((n, i) => ({...n,
  x: W/2 + (W/3) * Math.cos(2*Math.PI*i/GRAPH.nodes.length),
  y: H/2 + (H/3) * Math.sin(2*Math.PI*i/GRAPH.nodes.length), vx:0, vy:0}));
const byId = Object.fromEntries(nodes.map(n => [n.id, n]));
const links = GRAPH.links.filter(l => byId[l.source] && byId[l.target]);
const R = {'PRD Section':5,'Module':7,'Story':7,'Flow':7,'TC':3.5,'AC':3,
  'Term':3.5,'Figma Page':5};
for (let it = 0; it < 260; it++) {           // simple spring/repulsion pass
  for (const l of links) {
    const a = byId[l.source], b = byId[l.target];
    const dx = b.x-a.x, dy = b.y-a.y, d = Math.hypot(dx,dy)||1;
    const f = (d-46)*0.01;
    a.vx += f*dx/d; a.vy += f*dy/d; b.vx -= f*dx/d; b.vy -= f*dy/d;
  }
  for (let i = 0; i < nodes.length; i++) for (let j = i+1; j < nodes.length; j++) {
    const a = nodes[i], b = nodes[j];
    const dx = b.x-a.x, dy = b.y-a.y, d2 = dx*dx+dy*dy || 1;
    if (d2 < 8000) { const f = 260/d2;
      a.vx -= f*dx; a.vy -= f*dy; b.vx += f*dx; b.vy += f*dy; }
  }
  for (const n of nodes) {
    n.vx += (W/2-n.x)*0.002; n.vy += (H/2-n.y)*0.002;
    n.x = Math.max(8, Math.min(W-8, n.x + n.vx*0.85));
    n.y = Math.max(8, Math.min(H-8, n.y + n.vy*0.85));
    n.vx *= 0.6; n.vy *= 0.6;
  }
}
svg.innerHTML =
  links.map(l => { const a = byId[l.source], b = byId[l.target];
    return `<line x1="${a.x.toFixed(1)}" y1="${a.y.toFixed(1)}" ` +
      `x2="${b.x.toFixed(1)}" y2="${b.y.toFixed(1)}" ` +
      `stroke="var(--line)" stroke-width="1"/>`; }).join('') +
  nodes.map(n =>
    `<circle cx="${n.x.toFixed(1)}" cy="${n.y.toFixed(1)}" r="${R[n.type]||4}" ` +
    `fill="${COLORS[n.state] || '#8a8984'}" stroke="var(--surface)" ` +
    `stroke-width="1.5"><title>${n.type}: ${n.label} — ${n.state}</title>` +
    `</circle>`).join('');
</script></body></html>
"""


def cmd_dashboard():
    from wiki import refuse_if_unsealed
    refuse_if_unsealed("dashboard")
    dashboard, graph = gather()
    outdir = ROOT / "build/status"
    outdir.mkdir(parents=True, exist_ok=True)
    (outdir / "dashboard.json").write_text(
        json.dumps(dashboard, indent=1, ensure_ascii=False),
        encoding="utf-8", newline="\n")
    html = (HTML_TEMPLATE
            .replace("__PROJECT__", dashboard["project"])
            .replace("__DASH__", json.dumps(dashboard, ensure_ascii=False))
            .replace("__GRAPH__", json.dumps(graph, ensure_ascii=False))
            .replace("__COLORS__", json.dumps(STATE_COLORS)))
    (outdir / "dashboard.html").write_text(html, encoding="utf-8", newline="\n")
    print(f"dashboard: {len(dashboard['stories'])} stories, "
          f"{graph['meta']['counts']['nodes']} graph nodes -> "
          "build/status/dashboard.json + dashboard.html")
