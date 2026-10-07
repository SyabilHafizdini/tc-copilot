import { createContext, useContext, useEffect, useMemo, useState } from 'react'
import {
  Background, Controls, Handle, MiniMap, Position, ReactFlow, ReactFlowProvider,
  useNodesState, useReactFlow,
  type Edge, type Node, type NodeProps,
} from '@xyflow/react'
import '@xyflow/react/dist/style.css'
import './flowbuilder.css'
import { getFlowBuilder, onChange } from '../api'
import type { BuilderModel } from '../api'
import { Banner, PageSkeleton } from '../ui'
import { mergeFlows, shortLabel, type Overview, type OvNode } from './overview'

/* Flow overview: every flow's journey on one canvas. Steps the flows share are
 * one node; where a flow leaves the others it gets its own node, so the
 * permutations read as lanes parting from and rejoining a common path.
 * Read-only: flows are drawn in the Flow Builder and asserted in alignment. */

type Criterion = { ac: string; title: string }
type OvFlowNode = Node<{ step: OvNode }, 'ovstep'>

const START_VIEW = { x: 24, y: 40, zoom: 0.7 }

const Ctx = createContext<{
  overview: Overview
  criteria: Record<string, Criterion>
  focus: string | null
}>({ overview: { nodes: [], edges: [], flows: [], shared: 0 }, criteria: {}, focus: null })

function criteriaOf(model: BuilderModel): Record<string, Criterion> {
  const out: Record<string, Criterion> = {}
  model.stories.forEach((s) => s.acs.forEach((ac) => {
    out[`${s.id}#${ac.id}`] = { ac: ac.id, title: ac.title || ac.text }
  }))
  return out
}

function StepView({ data }: NodeProps<OvFlowNode>) {
  const { overview, criteria, focus } = useContext(Ctx)
  const { step } = data
  const total = overview.flows.length
  const c = criteria[step.ref]
  const dim = focus !== null && !step.flows.includes(focus)
  const all = step.flows.length === total
  // one unnamed variant walked by every flow of the step says nothing: hide it
  const variants = step.variants.filter((v) => v.note || step.variants.length > 1)
  return (
    <div className={`fb-node fo-node${all ? ' main' : ' alt'}${dim ? ' fo-dim' : ''}`}>
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

function Canvas({ model, theme }: { model: BuilderModel; theme: 'light' | 'dark' }) {
  const [split, setSplit] = useState(false)
  const [focus, setFocus] = useState<string | null>(null)
  const overview = useMemo(() => mergeFlows(model, split), [model, split])
  const criteria = useMemo(() => criteriaOf(model), [model])
  const [nodes, setNodes, onNodesChange] = useNodesState<OvFlowNode>(overview.nodes.map(toFlowNode))
  const rf = useReactFlow()

  // a new model or another grouping redraws the canvas; dragging a step does not
  useEffect(() => { setNodes(overview.nodes.map(toFlowNode)) }, [overview, setNodes])
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

  const fit = () => rf.fitView({ padding: 0.1, duration: 200 })

  return (
    <Ctx.Provider value={{ overview, criteria, focus }}>
      <div className="page fb-page">
        <div className="page-head">
          <h1>Flow overview</h1>
          <div className="fb-actions">
            <label className="fo-toggle">
              <input type="checkbox" checked={split} onChange={(e) => setSplit(e.target.checked)} />
              Split steps by data
            </label>
            <button className="btn" onClick={fit} disabled={!nodes.length}>Fit</button>
          </div>
        </div>
        <div className="fb-work fo-work">
          <div className="fb-canvas">
            <ReactFlow
              nodes={nodes} edges={edges} nodeTypes={NODE_TYPES} onNodesChange={onNodesChange}
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
          <aside className="fb-panel">
            <div className="fb-lbl">Flows ({total})</div>
            <p className="fb-dim">
              {overview.nodes.length} distinct steps, {overview.shared} walked by every flow.
              Pick a flow to trace its path.
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
          </aside>
        </div>
      </div>
    </Ctx.Provider>
  )
}

export function FlowOverviewPage({ theme }: { theme: 'light' | 'dark' }) {
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
