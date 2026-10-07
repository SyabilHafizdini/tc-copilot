import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from 'react'
import {
  Background, Controls, Handle, MiniMap, Position, ReactFlow, ReactFlowProvider,
  useNodesState, useReactFlow,
  type Edge, type Node, type NodeProps,
} from '@xyflow/react'
import '@xyflow/react/dist/style.css'
import './flowbuilder.css'
import { getFlowBuilder, onChange } from '../api'
import type { BuilderModel, JourneyTc } from '../api'
import { Moon, Sun } from 'lucide-react'
import { useResizableWidth } from '../../lib/useResizableWidth'
import { Banner, PageSkeleton } from '../ui'
import { mergeFlows, shortLabel, type Overview, type OvNode } from './overview'

/* Flow overview: every flow's journey on one canvas. Steps the flows share are
 * one node; where a flow leaves the others it gets its own node, so the
 * permutations read as lanes parting from and rejoining a common path.
 * Clicking a step opens, in the side panel, the test case each flow runs
 * there, as its workbook row prints it.
 * Read-only: flows are drawn in the Flow Builder and asserted in alignment.
 *
 * Export downloads this page as one standalone file: the app bundle with the
 * flows baked in (see bakedOverview), which opens to the same canvas with no
 * server behind it. */

type Theme = 'light' | 'dark'
const EXPORT_HREF = '/api/flow_overview.html'
const DEFAULT_TITLE = 'Flow overview'

// The flows an exported file carries, or null in the running app.
export const bakedOverview = (): BuilderModel | null =>
  (window as { __TC_FLOW_OVERVIEW__?: BuilderModel }).__TC_FLOW_OVERVIEW__ ?? null

// The page heading: the project's own (config `flow_overview.title`) when set.
const titleOf = (model: BuilderModel) => (model.overview_title ?? '').trim() || DEFAULT_TITLE

type Criterion = { ac: string; title: string }
type OvFlowNode = Node<{ step: OvNode }, 'ovstep'>

const START_VIEW = { x: 24, y: 40, zoom: 0.7 }

const Ctx = createContext<{
  overview: Overview
  criteria: Record<string, Criterion>
  focus: string | null
  picked: string | null
}>({ overview: { nodes: [], edges: [], flows: [], shared: 0 }, criteria: {}, focus: null, picked: null })

function criteriaOf(model: BuilderModel): Record<string, Criterion> {
  const out: Record<string, Criterion> = {}
  model.stories.forEach((s) => s.acs.forEach((ac) => {
    out[`${s.id}#${ac.id}`] = { ac: ac.id, title: ac.title || ac.text }
  }))
  return out
}

function StepView({ data }: NodeProps<OvFlowNode>) {
  const { overview, criteria, focus, picked } = useContext(Ctx)
  const { step } = data
  const total = overview.flows.length
  const c = criteria[step.ref]
  const dim = focus !== null && !step.flows.includes(focus)
  const all = step.flows.length === total
  // one unnamed variant walked by every flow of the step says nothing: hide it
  const variants = step.variants.filter((v) => v.note || step.variants.length > 1)
  return (
    <div className={`fb-node fo-node${all ? ' main' : ' alt'}${dim ? ' fo-dim' : ''}${picked === step.id ? ' selected' : ''}`}>
      <Handle type="target" position={Position.Left} isConnectable={false} />
      <div className="fb-node-bar">
        <b>{c?.ac ?? step.ref.split('#')[1] ?? step.ref}</b>
        <span className="fb-dim">{all ? `all ${total} flows` : `${step.flows.length} of ${total} flows`}</span>
      </div>
      <div className="fb-node-body">
        <div className="fo-title" title={c?.title}>{c?.title ?? 'This criterion no longer exists.'}</div>
        {step.endState && <div className="fb-dim fo-end">{step.endState}</div>}
        {!all && variants.length === 0 && (
          <div className="fo-chips">{step.flows.map((f) => <Chip key={f} id={f} focus={focus} />)}</div>
        )}
        {variants.map((v) => (
          <div key={v.note} className="fo-variant">
            {v.note && <div>{v.note}</div>}
            <div className="fo-chips">{v.flows.map((f) => <Chip key={f} id={f} focus={focus} />)}</div>
          </div>
        ))}
      </div>
      <Handle type="source" position={Position.Right} isConnectable={false} />
    </div>
  )
}
const Chip = ({ id, focus }: { id: string; focus: string | null }) =>
  <span className={`fo-chip${focus === id ? ' on' : ''}`}>{shortLabel(id)}</span>

const NODE_TYPES = { ovstep: StepView }

const toFlowNode = (n: OvNode): OvFlowNode =>
  ({ id: n.id, type: 'ovstep', position: { x: n.x, y: n.y }, data: { step: n } })

// Workbook cell text keeps its **bold** markers; show them as bold.
function cellText(text: string): ReactNode {
  if (!text) return <span className="fb-dim">-</span>
  return text.split(/(\*\*[^*]+\*\*)/g).map((part, i) =>
    part.startsWith('**') && part.endsWith('**') && part.length > 4
      ? <b key={i}>{part.slice(2, -2)}</b> : part)
}

const Conf = ({ level }: { level: string }) =>
  level ? <span className={`fo-conf ${level.toLowerCase()}`}>{level}</span> : <span className="fb-dim">-</span>

// One test case, cell by cell in the order of its workbook row.
function TestCase({ tc }: { tc: JourneyTc }) {
  return (
    <dl className="fo-tc">
      <dt>Test Case ID</dt><dd><b className="fo-tcid">{tc.id}</b></dd>
      <dt>Scenario</dt><dd>{cellText(tc.scenario)}</dd>
      <dt>Test Steps</dt><dd>{cellText(tc.steps)}</dd>
      <dt>Field / Values</dt><dd>{cellText(tc.data)}</dd>
      <dt>Expected Results</dt><dd>{cellText(tc.expected)}</dd>
      <dt>Confidence</dt><dd><Conf level={tc.confidence} /></dd>
      <dt>Test Case Remarks</dt><dd>{cellText(tc.remarks)}</dd>
    </dl>
  )
}

/* The side panel for one picked step: what the step is, then one block per
 * flow that walks it, holding that flow's test case. The traced flow leads
 * and is the one opened. */
function StepDetail({ step, model, focus, onClose }: {
  step: OvNode; model: BuilderModel; focus: string | null; onClose: () => void
}) {
  const { criteria } = useContext(Ctx)
  const c = criteria[step.ref]
  const flowOf = (id: string) => model.flows.find((f) => f.id === id)
  const entries = [...step.entries].sort((a, b) => Number(b.flow === focus) - Number(a.flow === focus))
  const lead = entries[0]?.flow
  return (
    <>
      <button className="btn fo-back" onClick={onClose}>Back to flows</button>
      <div className="fb-lbl">{c?.ac ?? step.ref.split('#')[1] ?? step.ref}</div>
      <div className="fo-detail-title">{c?.title ?? 'This criterion no longer exists.'}</div>
      {step.endState && <p className="fb-dim">Ends with: {step.endState}</p>}
      <div className="fb-lbl">Test cases ({entries.length})</div>
      {entries.map((e) => {
        const tc = model.journey_tcs?.[`${e.flow}#${e.jid}`]
        return (
          <details key={`${e.flow}#${e.jid}`} className="fo-tcbox" open={e.flow === lead}>
            <summary>
              <span className={`fo-chip${focus === e.flow ? ' on' : ''}`}>{shortLabel(e.flow)}</span>
              <span className="fo-flow-title">{flowOf(e.flow)?.title || e.flow}</span>
              {tc && <Conf level={tc.confidence} />}
            </summary>
            {e.note && <p className="fo-note">{e.note}</p>}
            {tc ? <TestCase tc={tc} />
              : <p className="fb-dim">No test case has been generated for this step of the flow yet.</p>}
          </details>
        )
      })}
    </>
  )
}

function Canvas({ model, theme, onToggleTheme }: {
  model: BuilderModel; theme: Theme
  onToggleTheme?: () => void   // given only in an exported file, which has no top bar
}) {
  const [split, setSplit] = useState(true)
  const [focus, setFocus] = useState<string | null>(null)
  const [picked, setPicked] = useState<string | null>(null)
  const overview = useMemo(() => mergeFlows(model, split), [model, split])
  const criteria = useMemo(() => criteriaOf(model), [model])
  const [nodes, setNodes, onNodesChange] = useNodesState<OvFlowNode>(overview.nodes.map(toFlowNode))
  const rf = useReactFlow()
  const { width, startResize } = useResizableWidth(340, 260, 900)

  // a new model or another grouping redraws the canvas; dragging a step does
  // not. Step ids belong to one grouping, so a picked step does not carry over.
  useEffect(() => { setNodes(overview.nodes.map(toFlowNode)); setPicked(null) }, [overview, setNodes])
  useEffect(() => {
    if (focus && !overview.flows.some((f) => f.id === focus)) setFocus(null)
  }, [overview, focus])

  const total = overview.flows.length
  const edges = useMemo<Edge[]>(() => overview.edges.map((e) => {
    const on = focus === null || e.flows.includes(focus)
    const all = e.flows.length === total
    return {
      id: e.id, source: e.from, target: e.to, type: 'smoothstep', selectable: false,
      // the line every flow takes is unlabelled; a parting line names its
      // flows, or counts them when the names would not fit between two steps
      label: all ? undefined
        : e.flows.length <= 2 ? e.flows.map(shortLabel).join(' ') : `${e.flows.length} flows`,
      className: `${all ? 'fb-edge-main' : 'fb-edge-alt'}${on ? '' : ' fo-dim'}`,
      animated: focus !== null && on,
      style: { strokeWidth: 1.5 + 3 * (e.flows.length / Math.max(total, 1)) },
    }
  }), [overview, focus, total])

  // back to the chart as first opened: dragged steps return, no flow is
  // traced, no step is picked, and the view is the readable zoom at the start
  const reset = () => {
    setNodes(overview.nodes.map(toFlowNode))
    setFocus(null)
    setPicked(null)
    rf.setViewport(START_VIEW, { duration: 200 })
  }
  const pickedStep = overview.nodes.find((n) => n.id === picked) ?? null

  return (
    <Ctx.Provider value={{ overview, criteria, focus, picked }}>
      <div className="page fb-page">
        <div className="page-head">
          <h1>{titleOf(model)}</h1>
          <div className="fb-actions">
            <label className="fo-toggle">
              <input type="checkbox" role="switch" checked={split} onChange={(e) => setSplit(e.target.checked)} />
              <span className="fo-switch" aria-hidden="true" />
              Split steps by data
            </label>
            <button className="btn" onClick={reset} disabled={!nodes.length}
              title="Back to the chart as first opened: steps where they were drawn, all flows, the starting zoom">Reset chart</button>
            {onToggleTheme
              ? <button className="icon-btn" onClick={onToggleTheme}
                  aria-label={theme === 'dark' ? 'Switch to light theme' : 'Switch to dark theme'}>
                  {theme === 'dark' ? <Moon size={16} /> : <Sun size={16} />}
                </button>
              : <a className="btn" href={EXPORT_HREF} download="flow-overview.html"
                  title="Download this overview as one standalone file to share">Export</a>}
          </div>
        </div>
        <div className="fb-work fo-work" style={{ gridTemplateColumns: `minmax(0, 1fr) ${width}px` }}>
          <div className="fb-canvas">
            <ReactFlow
              nodes={nodes} edges={edges} nodeTypes={NODE_TYPES} onNodesChange={onNodesChange}
              onNodeClick={(_e, n) => setPicked(n.id)} onPaneClick={() => setPicked(null)}
              colorMode={theme} nodesConnectable={false} deleteKeyCode={null}
              minZoom={0.1} defaultViewport={START_VIEW} proOptions={{ hideAttribution: false }}
            >
              <Background gap={22} />
              <Controls showInteractive={false} />
              <MiniMap pannable zoomable />
            </ReactFlow>
            {!nodes.length && (
              <div className="fb-empty">
                <b>No flows yet.</b> Draw one in the Flow Builder or ask the agent to align one; every
                flow with a journey appears here.
              </div>
            )}
          </div>
          <aside className="fo-panel">
            {/* outside the scrolling body, so the handle spans the panel however long its content */}
            <div className="fo-resize" role="separator" aria-orientation="vertical"
              aria-label="Resize the side panel" title="Drag to resize" onMouseDown={startResize} />
            <div className="fb-panel">
            {pickedStep
              ? <StepDetail step={pickedStep} model={model} focus={focus} onClose={() => setPicked(null)} />
              : <>
                <div className="fb-lbl">Flows ({total})</div>
                <p className="fb-dim">
                  {overview.nodes.length} distinct steps, {overview.shared} walked by every flow.
                  Pick a flow to trace its path, or a step to read its test cases.
                </p>
                {overview.flows.map((f) => (
                  <button
                    key={f.id} className={`fo-flow${focus === f.id ? ' on' : ''}`} aria-pressed={focus === f.id}
                    onClick={() => setFocus(focus === f.id ? null : f.id)}>
                    <span className="fo-chip">{f.label}</span>
                    <span className="fo-flow-title">{f.title || f.id}</span>
                    <span className="fb-dim">{f.steps} steps · {f.status}</span>
                  </button>
                ))}
                {focus && <button className="btn fo-clear" onClick={() => setFocus(null)}>Show all flows</button>}
                <div className="fb-lbl">Reading the canvas</div>
                <ul className="fo-legend">
                  <li><span className="fo-sw main" />A step every flow walks</li>
                  <li><span className="fo-sw alt" />A step only some flows walk</li>
                  <li>A dashed line is labelled with the flows that take it.</li>
                  <li>A thicker line carries more flows.</li>
                </ul>
              </>}
            </div>
          </aside>
        </div>
      </div>
    </Ctx.Provider>
  )
}

export function FlowOverviewPage({ theme }: { theme: Theme }) {
  const [model, setModel] = useState<BuilderModel | null>(null)
  const [error, setError] = useState<string | null>(null)
  useEffect(() => {
    const load = () => getFlowBuilder().then(setModel).catch((e) => setError(String(e)))
    load()
    return onChange(load)
  }, [])
  if (error) return <div className="page"><Banner tone="blocked">{error}</Banner></div>
  if (!model) return <PageSkeleton />
  return <ReactFlowProvider><Canvas model={model} theme={theme} /></ReactFlowProvider>
}

/* What an exported file renders in place of the app: the canvas alone, over
 * the flows baked into the file. */
export function FlowOverviewExport({ model }: { model: BuilderModel }) {
  const [theme, setTheme] = useState<Theme>(
    () => (window.matchMedia?.('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'))
  useEffect(() => { document.documentElement.dataset.theme = theme }, [theme])
  useEffect(() => {
    document.title = model.overview_title?.trim() || `${DEFAULT_TITLE} - ${model.project}`
  }, [model])
  return (
    <div className="fo-export">
      <ReactFlowProvider>
        <Canvas model={model} theme={theme} onToggleTheme={() => setTheme(theme === 'dark' ? 'light' : 'dark')} />
      </ReactFlowProvider>
    </div>
  )
}
