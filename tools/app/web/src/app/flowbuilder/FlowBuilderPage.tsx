import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from 'react'
import {
  Background, Controls, Handle, MiniMap, Position, ReactFlow, ReactFlowProvider,
  addEdge, useEdgesState, useNodesState, useReactFlow,
  type Connection, type Edge, type Node, type NodeProps,
} from '@xyflow/react'
import '@xyflow/react/dist/style.css'
import './flowbuilder.css'
import { getFlowBuilder, onChange, runAction } from '../api'
import type { ActionResult, BuilderModel } from '../api'
import { Banner, PageSkeleton } from '../ui'
import {
  computeJourney, layoutFlow, tidy, toDraft,
  type JourneyResult, type Meta, type StepEdge, type StepNode,
} from './journey'

/* Flow builder: stitch SIT test cases into a flow by dragging them onto a
 * canvas and connecting them. Each step is a test case; the criterion it
 * covers comes along, because a flow's journey is keyed by criterion. Saving
 * writes a DRAFT flow through the allowlisted `flow_draft` action; the flow
 * still goes through alignment and the human's assertion before any UAT test
 * case is generated from it. */

type Tc = { id: string; title: string; end: string }
type Section = { ref: string; story: string; ac: string; text: string; tcs: Tc[] }
// tc is null only for a step loaded from a flow that predates test-case steps
type StepData = { tc: string | null; ref: string; endState: string; note: string }
type StepFlowNode = Node<StepData, 'step'>

const STORE = 'tc-flow-builder'
const DRAG_TYPE = 'application/x-tc-testcase'
// A long journey fitted to the screen is unreadable; open on its first steps.
const START_VIEW = { x: 20, y: 30, zoom: 0.8 }

function sectionsOf(model: BuilderModel): Record<string, Section> {
  const out: Record<string, Section> = {}
  model.stories.forEach((s) => s.acs.forEach((ac) => {
    if (ac.status === 'voided') return
    out[`${s.id}#${ac.id}`] = {
      ref: `${s.id}#${ac.id}`, story: s.id, ac: ac.id, text: ac.text,
      tcs: ac.tcs.filter((id) => model.tcs[id]).map((id) => ({
        id, title: model.tcs[id].title ?? '',
        // where the test case leaves the user: the step's starting end state
        end: model.tcs[id].sections['Postconditions'].replace(/\*\*/g, '').trim(),
      })),
    }
  }))
  return out
}

function nextFlowId(model: BuilderModel): string {
  const hits = model.flows.map((f) => f.id.match(/^(.*?)(\d+)$/)).filter((m): m is RegExpMatchArray => !!m)
  if (!hits.length) return `FLOW-${model.code || 'X'}-001`
  const top = hits.sort((a, b) => Number(b[2]) - Number(a[2]))[0]
  return top[1] + String(Number(top[2]) + 1).padStart(top[2].length, '0')
}

const toStep = (n: StepFlowNode): StepNode =>
  ({ id: n.id, tc: n.data.tc, ref: n.data.ref, x: n.position.x, y: n.position.y,
     endState: n.data.endState, note: n.data.note })
const toFlowNode = (n: StepNode): StepFlowNode => ({
  id: n.id, type: 'step', position: { x: n.x, y: n.y },
  data: { tc: n.tc ?? null, ref: n.ref, endState: n.endState, note: n.note },
})
const toFlowEdge = (e: StepEdge): Edge => ({ id: `${e.from}>${e.to}`, source: e.from, target: e.to })

const Ctx = createContext<{
  res: JourneyResult
  sections: Record<string, Section>
  patch: (id: string, data: Partial<StepData>) => void
}>({ res: { errors: [], journey: [], branches: [], paths: [], order: {}, kind: {} }, sections: {}, patch: () => {} })

function StepNodeView({ id, data, selected }: NodeProps<StepFlowNode>) {
  const { res, sections, patch } = useContext(Ctx)
  const s = sections[data.ref]
  const tc = s?.tcs.find((t) => t.id === data.tc)
  const name = data.tc ?? s?.ac ?? data.ref
  const kind = res.kind[id] ?? 'loose'
  // choosing a test case re-seeds the end state unless the human already wrote one
  const choose = (tcId: string) => {
    const next = s?.tcs.find((t) => t.id === tcId)
    const untouched = !data.endState.trim() || data.endState === tc?.end
    patch(id, { tc: tcId || null, ...(next && untouched ? { endState: next.end } : {}) })
  }
  return (
    <div className={`fb-node ${kind}${selected ? ' selected' : ''}`}>
      <Handle type="target" position={Position.Left} />
      <div className="fb-node-bar">
        {res.order[id] && <span className="fb-jid">{res.order[id]}</span>}
        <b>{name}</b>
        <span className="fb-dim">{s ? `${s.ac} · ${s.story}` : ''}</span>
      </div>
      <div className="fb-node-body">
        <div className="fb-node-title" title={tc?.title}>
          {tc ? tc.title
            : data.tc ? 'This test case no longer exists.'
              : <span className="fb-dim">No test case chosen for this step yet.</span>}
        </div>
        <textarea
          className="nodrag" aria-label={`End state of ${name}`}
          placeholder="End state: where is the user left?"
          value={data.endState} onChange={(e) => patch(id, { endState: e.target.value })} />
        <details className="nodrag">
          <summary>Criterion {s?.ac ?? ''} and options</summary>
          <div className="fb-dim">{s?.text ?? 'This criterion no longer exists.'}</div>
          {s && s.tcs.length > 0 && (
            <select aria-label={`Test case for ${name}`} value={data.tc ?? ''} onChange={(e) => choose(e.target.value)}>
              {!tc && <option value="">Choose a test case…</option>}
              {s.tcs.map((t) => <option key={t.id} value={t.id}>{t.id} - {t.title}</option>)}
            </select>
          )}
          <input
            aria-label="Note" placeholder="Note (optional)" value={data.note}
            onChange={(e) => patch(id, { note: e.target.value })} />
        </details>
      </div>
      <Handle type="source" position={Position.Right} />
    </div>
  )
}
const NODE_TYPES = { step: StepNodeView }

type Saved = { meta: Meta; nodes: StepNode[]; edges: StepEdge[]; branchTitles: Record<string, string>; seq: number }

function loadSaved(): Saved | null {
  try {
    const s = JSON.parse(localStorage.getItem(STORE) || 'null')
    return s && Array.isArray(s.nodes) ? s : null
  } catch { return null }
}

function Builder({ model, theme }: { model: BuilderModel; theme: 'light' | 'dark' }) {
  const sections = useMemo(() => sectionsOf(model), [model])
  const saved = useRef(loadSaved()).current
  const [meta, setMeta] = useState<Meta>(saved?.meta ?? { id: nextFlowId(model), title: '', entry: '' })
  const [nodes, setNodes, onNodesChange] = useNodesState<StepFlowNode>((saved?.nodes ?? []).map(toFlowNode))
  const [edges, setEdges, onEdgesChange] = useEdgesState<Edge>((saved?.edges ?? []).map(toFlowEdge))
  const [branchTitles, setBranchTitles] = useState<Record<string, string>>(saved?.branchTitles ?? {})
  const seq = useRef(saved?.seq ?? 1)
  const [filter, setFilter] = useState('')
  const [result, setResult] = useState<ActionResult | { error: string } | null>(null)
  const [saving, setSaving] = useState(false)
  const rf = useReactFlow()

  const steps = useMemo(() => nodes.map(toStep), [nodes])
  const links = useMemo(() => edges.map((e) => ({ from: e.source, to: e.target })), [edges])
  const res = useMemo(() => computeJourney(steps, links, meta, branchTitles), [steps, links, meta, branchTitles])

  useEffect(() => {
    try {
      localStorage.setItem(STORE, JSON.stringify({ meta, nodes: steps, edges: links, branchTitles, seq: seq.current }))
    } catch { /* storage unavailable: the canvas still works for this visit */ }
  }, [meta, steps, links, branchTitles])

  const patch = useCallback((id: string, data: Partial<StepData>) => {
    setNodes((ns) => ns.map((n) => (n.id === id ? { ...n, data: { ...n.data, ...data } } : n)))
  }, [setNodes])

  // every stitchable test case, with the criterion it is listed under
  const tcIndex = useMemo(() => {
    const out: Record<string, { ref: string; end: string }> = {}
    Object.values(sections).forEach((s) => s.tcs.forEach((t) => { out[t.id] ??= { ref: s.ref, end: t.end } }))
    return out
  }, [sections])

  const addStep = useCallback((tcId: string, pos?: { x: number; y: number }) => {
    const t = tcIndex[tcId]
    if (!t) return
    const id = `n${seq.current++}`
    setNodes((ns) => {
      const last = ns[ns.length - 1]
      const position = pos ?? (last ? { x: last.position.x + 300, y: last.position.y } : { x: 40, y: 60 })
      // "+" continues the line: hook the new step onto the newest loose end
      if (!pos && last) {
        setEdges((es) => (es.some((e) => e.source === last.id) ? es
          : [...es, toFlowEdge({ from: last.id, to: id })]))
      }
      return [...ns, { id, type: 'step', position, data: { tc: tcId, ref: t.ref, endState: t.end, note: '' } }]
    })
  }, [tcIndex, setNodes, setEdges])

  const onConnect = useCallback((c: Connection) => {
    if (c.source === c.target) return
    setEdges((es) => addEdge(c, es))
  }, [setEdges])

  const onDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    const tcId = e.dataTransfer.getData(DRAG_TYPE)
    if (tcId) addStep(tcId, rf.screenToFlowPosition({ x: e.clientX - 120, y: e.clientY - 20 }))
  }, [addStep, rf])

  const replaceCanvas = (g: { nodes: StepNode[]; edges: StepEdge[]; branchTitles: Record<string, string> }, m: Meta) => {
    seq.current = g.nodes.length + 1
    setMeta(m); setBranchTitles(g.branchTitles)
    setNodes(g.nodes.map(toFlowNode)); setEdges(g.edges.map(toFlowEdge)); setResult(null)
    window.requestAnimationFrame(() => rf.setViewport(START_VIEW))
  }
  const loadExisting = (id: string) => {
    const f = model.flows.find((x) => x.id === id)
    if (!f || (nodes.length && !window.confirm(`Replace what is on the canvas with ${f.id}?`))) return
    replaceCanvas(layoutFlow(f), { id: f.id, title: f.title ?? '', entry: f.entry_condition ?? '' })
  }
  const clear = () => {
    if (nodes.length && !window.confirm('Clear the canvas?')) return
    replaceCanvas({ nodes: [], edges: [], branchTitles: {} }, { id: nextFlowId(model), title: '', entry: '' })
  }
  const doTidy = () => {
    setNodes(tidy(steps, res).map(toFlowNode))
    window.requestAnimationFrame(() => rf.setViewport(START_VIEW))
  }
  const save = () => {
    setSaving(true); setResult(null)
    runAction('flow_draft', { draft: toDraft(meta, res) })
      .then(setResult).catch((e) => setResult({ error: String(e) }))
      .finally(() => setSaving(false))
  }

  // the main path reads solid, branches dashed: never colour alone
  const shownEdges = useMemo(() => edges.map((e) => {
    const main = res.kind[e.source] === 'main' && res.kind[e.target] === 'main'
    return { ...e, className: main ? 'fb-edge-main' : res.kind[e.target] ? 'fb-edge-alt' : '' }
  }), [edges, res])

  const q = filter.toLowerCase()
  const ready = !res.errors.length && res.journey.length > 0
  const saveOk = result && !('error' in result) && result.rc === 0

  return (
    <Ctx.Provider value={{ res, sections, patch }}>
      <div className="page fb-page">
        <div className="page-head">
          <h1>Flow builder</h1>
          <div className="fb-actions">
            <select aria-label="Start from an existing flow" value="" onChange={(e) => loadExisting(e.target.value)}>
              <option value="">Start from an existing flow…</option>
              {model.flows.map((f) => <option key={f.id} value={f.id}>{f.id} ({f.status})</option>)}
            </select>
            <button className="btn" onClick={doTidy} disabled={!res.journey.length}>Tidy</button>
            <button className="btn" onClick={clear}>Clear</button>
            <button className="btn primary" onClick={save} disabled={!ready || saving}>
              {saving ? 'Saving…' : 'Save as draft flow'}
            </button>
          </div>
        </div>
        <div className="fb-work">
          <aside className="fb-palette">
            <input aria-label="Filter test cases" placeholder="Filter test cases" value={filter}
                   onChange={(e) => setFilter(e.target.value)} />
            {model.stories.map((s) => {
              // a test case is listed once, under the first criterion it covers
              const groups = s.acs.map((ac) => sections[`${s.id}#${ac.id}`])
                .filter((x): x is Section => !!x)
                .map((x) => ({ x, rows: x.tcs.filter((t) => tcIndex[t.id]?.ref === x.ref
                  && `${t.id} ${t.title} ${x.ac}`.toLowerCase().includes(q)) }))
                .filter((g) => g.rows.length || (!q && !g.x.tcs.length))
              if (!groups.length) return null
              return (
                <div key={s.id}>
                  <div className="fb-lbl">{s.id} · {s.status}</div>
                  {groups.map(({ x, rows }) => (
                    <div key={x.ref} className="fb-group">
                      <div className="fb-group-head" title={x.text}><b>{x.ac}</b> <span className="fb-dim">{x.text}</span></div>
                      {rows.map((t) => (
                        <div key={t.id} className="fb-item" draggable
                             onDragStart={(e) => { e.dataTransfer.setData(DRAG_TYPE, t.id); e.dataTransfer.effectAllowed = 'move' }}>
                          <button className="btn fb-add" aria-label={`Add ${t.id}`} title="Add to canvas"
                                  onClick={() => addStep(t.id)}>+</button>
                          <b>{t.id}</b>
                          <div className="fb-item-title" title={t.title}>{t.title}</div>
                        </div>
                      ))}
                      {!x.tcs.length && <div className="fb-dim fb-none">No SIT test cases yet.</div>}
                    </div>
                  ))}
                </div>
              )
            })}
            {!Object.keys(tcIndex).length && <p className="fb-dim">No test cases to stitch: generate SIT test cases first.</p>}
          </aside>
          <div className="fb-canvas" onDrop={onDrop} onDragOver={(e) => { e.preventDefault(); e.dataTransfer.dropEffect = 'move' }}>
            <ReactFlow
              nodes={nodes} edges={shownEdges} nodeTypes={NODE_TYPES}
              onNodesChange={onNodesChange} onEdgesChange={onEdgesChange} onConnect={onConnect}
              colorMode={theme} deleteKeyCode={['Delete', 'Backspace']}
              defaultEdgeOptions={{ type: 'smoothstep' }} minZoom={0.2} defaultViewport={START_VIEW}
              proOptions={{ hideAttribution: false }}
            >
              <Background gap={22} />
              <Controls />
              <MiniMap pannable zoomable />
            </ReactFlow>
            {!nodes.length && (
              <div className="fb-empty">
                <b>Stitch a flow.</b> Drag a test case from the left onto the canvas (or press +), then drag
                from the dot on a step's right edge to the next step. Where two lines leave one step, the
                upper one is the main path and the lower one becomes a branch. Select a line or step and
                press Delete to remove it.
              </div>
            )}
          </div>
          <aside className="fb-panel">
            <div className="fb-lbl">Flow</div>
            <label>Id<input value={meta.id} onChange={(e) => setMeta({ ...meta, id: e.target.value })} /></label>
            <label>Title<input value={meta.title} placeholder="What journey is this?"
                               onChange={(e) => setMeta({ ...meta, title: e.target.value })} /></label>
            <label>Starts from<textarea value={meta.entry} placeholder="State and data needed before step 1"
                                        onChange={(e) => setMeta({ ...meta, entry: e.target.value })} /></label>
            {result && ('error' in result
              ? <Banner tone="blocked" onDismiss={() => setResult(null)}>{result.error}</Banner>
              : saveOk
                ? <div className="fb-ok" role="status">
                    Saved {meta.id} as a draft flow. It is not aligned yet: ask the agent to align it
                    (tc-align) and assert it before generating UAT test cases.
                  </div>
                : <Banner tone="blocked" onDismiss={() => setResult(null)}>
                    <span style={{ whiteSpace: 'pre-wrap' }}>{(result.stdout + result.stderr).trim()}</span>
                  </Banner>)}
            {res.errors.map((e) => <div key={e} className="fb-err">{e}</div>)}
            {res.journey.length > 0 && (
              <>
                <div className="fb-lbl">Journey ({res.journey.length} steps)</div>
                <ol className="fb-journey">
                  {res.journey.map((j) => (
                    <li key={j.id}>
                      <b>{j.id}</b> {j.source_tc ?? j.ref.split('#')[1]} {j.branch && <span className="fb-chip">{j.branch}</span>}
                      {j.source_tc && <div className="fb-dim">{model.tcs[j.source_tc]?.title}</div>}
                      <div>{j.end_state || <span className="fb-dim">no end state yet</span>}</div>
                      {j.note && <div className="fb-dim">{j.note}</div>}
                    </li>
                  ))}
                </ol>
              </>
            )}
            {res.branches.length > 0 && <div className="fb-lbl">Branches</div>}
            {res.branches.map((b) => (
              <label key={b.key}><span className="fb-chip">{b.id}</span> {b.text}
                <input value={b.title} onChange={(e) => setBranchTitles({ ...branchTitles, [b.key]: e.target.value })} />
              </label>
            ))}
            {res.paths.length > 0 && <div className="fb-lbl">Possible flows ({res.paths.length})</div>}
            {res.paths.map((p, i) => (
              <div key={p.join('>')} className="fb-path">{i ? `alt ${i}` : 'main'}: {p.join(' › ')}</div>
            ))}
          </aside>
        </div>
      </div>
    </Ctx.Provider>
  )
}

export function FlowBuilderPage({ theme }: { theme: 'light' | 'dark' }) {
  const [model, setModel] = useState<BuilderModel | null>(null)
  const [error, setError] = useState<string | null>(null)
  useEffect(() => {
    const load = () => getFlowBuilder().then(setModel).catch((e) => setError(String(e)))
    load()
    return onChange(load)
  }, [])
  if (error) return <div className="page"><Banner tone="blocked">{error}</Banner></div>
  if (!model) return <PageSkeleton />
  return <ReactFlowProvider><Builder model={model} theme={theme} /></ReactFlowProvider>
}
