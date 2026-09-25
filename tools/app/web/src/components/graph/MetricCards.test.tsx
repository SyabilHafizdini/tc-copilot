import { describe, it, expect } from 'vitest'
import { render, screen, fireEvent, within } from '@testing-library/react'
import MetricCards from './MetricCards'
import { computeMetrics } from '../../lib/metrics'
import type { GraphNode, GraphEdge, GraphStats } from '../../lib/types'

const nodes: GraphNode[] = [
  {
    nodeId: 'page_home',
    nodeType: 'Page',
    displayLabel: 'Home',
    properties: { route: '/' },
    content: '# Home',
  },
  { nodeId: 'f_email', nodeType: 'Field', displayLabel: 'Email', properties: {} },
  { nodeId: 'f_pass', nodeType: 'Field', displayLabel: 'Password', properties: {} },
  { nodeId: 'lonely', nodeType: 'State', displayLabel: 'Lonely', properties: {} },
]

// page_home has degree 2, both fields have degree 1, lonely has none.
const edges: GraphEdge[] = [
  {
    edgeId: 'e1',
    edgeType: 'HAS_FIELD',
    fromNodeId: 'page_home',
    toNodeId: 'f_email',
    properties: {},
  },
  {
    edgeId: 'e2',
    edgeType: 'HAS_FIELD',
    fromNodeId: 'page_home',
    toNodeId: 'f_pass',
    properties: {},
  },
]

const totals: GraphStats = {
  totalNodes: 14,
  totalEdges: 13,
  nodesByType: {},
  edgesByType: {},
}

/** The bar ships collapsed, so every card assertion opens it first. */
const renderCards = (n: GraphNode[] = nodes, e: GraphEdge[] = edges): void => {
  render(<MetricCards metrics={computeMetrics(n, e, totals)} />)
  fireEvent.click(screen.getByRole('button', { name: /Summary/ }))
}

const card = (name: string): HTMLElement => screen.getByTestId(`metric-${name}`)

describe('MetricCards', () => {
  it('shows filtered counts against the whole-graph totals', () => {
    renderCards()

    expect(within(card('nodes')).getByText('4 of 14')).toBeInTheDocument()
    expect(within(card('edges')).getByText('2 of 13')).toBeInTheDocument()
  })

  it('reports orphans, the hub and average degree', () => {
    renderCards()

    expect(within(card('orphans')).getByText('1')).toBeInTheDocument()
    expect(within(card('hub')).getByText('Home')).toBeInTheDocument()
    expect(within(card('hub')).getByText('2 edges')).toBeInTheDocument()
    // 2 edges * 2 endpoints / 4 nodes = 1.0
    expect(within(card('avg-degree')).getByText('1.0')).toBeInTheDocument()
  })

  it('reports the type spread with the dominant type named', () => {
    renderCards()

    expect(within(card('node-types')).getByText('3')).toBeInTheDocument()
    expect(within(card('node-types')).getByText('top: Field')).toBeInTheDocument()
    expect(within(card('edge-types')).getByText('1')).toBeInTheDocument()
    expect(within(card('edge-types')).getByText('top: HAS_FIELD')).toBeInTheDocument()
  })

  it('reports content coverage and nodes lacking properties', () => {
    renderCards()

    expect(within(card('content')).getByText('1')).toBeInTheDocument()
    expect(within(card('content')).getByText('25% of in view')).toBeInTheDocument()
    expect(within(card('no-props')).getByText('3')).toBeInTheDocument()
  })

  it('renders a dash for the hub when nothing in view has an edge', () => {
    renderCards(nodes, [])

    expect(within(card('hub')).getByText('—')).toBeInTheDocument()
  })

  it('renders zeroes rather than NaN when every node is filtered out', () => {
    renderCards([], [])

    expect(within(card('nodes')).getByText('0 of 14')).toBeInTheDocument()
    expect(within(card('avg-degree')).getByText('0.0')).toBeInTheDocument()
    expect(within(card('node-types')).getByText('0')).toBeInTheDocument()
    expect(screen.queryByText(/NaN/)).not.toBeInTheDocument()
  })

  it('starts collapsed, showing only the one-line summary', () => {
    render(<MetricCards metrics={computeMetrics(nodes, edges, totals)} />)

    expect(screen.queryByTestId('metric-nodes')).not.toBeInTheDocument()
    expect(screen.getByText('4 of 14 nodes · 2 of 13 edges')).toBeInTheDocument()
  })

  it('expands to the cards and collapses back', () => {
    renderCards() // renders, then opens
    const toggle = screen.getByRole('button', { name: /Summary/ })

    expect(screen.getByTestId('metric-nodes')).toBeInTheDocument()

    fireEvent.click(toggle)
    expect(screen.queryByTestId('metric-nodes')).not.toBeInTheDocument()
    expect(screen.getByText('4 of 14 nodes · 2 of 13 edges')).toBeInTheDocument()
  })
})
