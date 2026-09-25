import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent, within } from '@testing-library/react'
import AboutPanel from './AboutPanel'
import type { GraphMeta, GraphPreset, GraphStats } from '../../lib/types'
import { TypeColorProvider } from '../../lib/TypeColorContext'
import { resolveTypeColors } from '../../lib/nodeStyle'

const meta: GraphMeta = {
  title: 'TaskFlow — Auth & Tasks',
  description: 'A richer sample with markdown content.',
}

const stats: GraphStats = {
  totalNodes: 14,
  totalEdges: 13,
  nodesByType: { Field: 5, Page: 2, Component: 1 },
  edgesByType: { HAS_FIELD: 8, CALLS: 5 },
}

const presets: GraphPreset[] = [
  {
    name: 'Frontend',
    description: 'Pages, components and fields',
    default: true,
    nodeTypes: ['Page', 'Component', 'Field'],
    edgeTypes: ['HAS_COMPONENT', 'HAS_FIELD'],
  },
  {
    name: 'Backend',
    description: 'Actions, endpoints, DB and state',
    nodeTypes: ['Action', 'APIEndpoint'],
  },
]

const renderPanel = (
  over: Partial<Parameters<typeof AboutPanel>[0]> = {},
): { onClose: () => void } => {
  const onClose = vi.fn()
  render(
    <AboutPanel
      meta={meta}
      presets={presets}
      stats={stats}
      onClose={onClose}
      {...over}
    />,
  )
  return { onClose }
}

const preset = (name: string): HTMLElement => screen.getByTestId(`about-preset-${name}`)

describe('AboutPanel', () => {
  it('shows the graph title and description', () => {
    renderPanel()

    expect(screen.getByText('TaskFlow — Auth & Tasks')).toBeInTheDocument()
    expect(screen.getByText('A richer sample with markdown content.')).toBeInTheDocument()
  })

  it('falls back to the default title and omits an absent description', () => {
    renderPanel({ meta: undefined })

    expect(screen.getByText('Knowledge Graph Explorer')).toBeInTheDocument()
    expect(screen.queryByTestId('about-description')).not.toBeInTheDocument()
  })

  it('reports the shape of the graph', () => {
    renderPanel()
    const shape = screen.getByTestId('about-shape')

    expect(shape).toHaveTextContent('14 nodes')
    expect(shape).toHaveTextContent('13 edges')
    expect(shape).toHaveTextContent('3 node types')
    expect(shape).toHaveTextContent('2 edge types')
  })

  it('lists node types with counts, most common first', () => {
    renderPanel()
    const rows = screen.getAllByTestId(/^about-nodetype-/)

    expect(rows.map((r) => r.dataset.testid)).toEqual([
      'about-nodetype-Field',
      'about-nodetype-Page',
      'about-nodetype-Component',
    ])
    expect(rows[0]).toHaveTextContent('5')
  })

  it('lists each preset with its description and the slice it selects', () => {
    renderPanel()
    const frontend = within(preset('Frontend'))

    expect(frontend.getByText('Pages, components and fields')).toBeInTheDocument()
    expect(frontend.getByText('Page')).toBeInTheDocument()
    expect(frontend.getByText('HAS_COMPONENT')).toBeInTheDocument()
  })

  it('marks the default preset', () => {
    renderPanel()

    expect(within(preset('Frontend')).getByText(/default/i)).toBeInTheDocument()
    expect(within(preset('Backend')).queryByText(/default/i)).not.toBeInTheDocument()
  })

  it('labels an omitted type key as all rather than an empty list', () => {
    renderPanel()

    // Backend omits edgeTypes entirely, which means every edge type.
    expect(within(preset('Backend')).getByTestId('about-preset-edgetypes')).toHaveTextContent(
      'all',
    )
  })

  it('shows an empty state when the graph defines no presets', () => {
    renderPanel({ presets: [] })

    expect(screen.getByText('This graph defines no presets.')).toBeInTheDocument()
  })

  it('closes on the close button, Escape and a backdrop click', () => {
    const a = renderPanel()
    fireEvent.click(screen.getByRole('button', { name: /close/i }))
    expect(a.onClose).toHaveBeenCalledTimes(1)

    const b = renderPanel()
    fireEvent.keyDown(document, { key: 'Escape' })
    expect(b.onClose).toHaveBeenCalled()

    const c = renderPanel()
    fireEvent.click(screen.getAllByTestId('about-backdrop')[2])
    expect(c.onClose).toHaveBeenCalled()
  })

  it('is an accessible dialog named by its heading', () => {
    renderPanel()

    expect(screen.getByRole('dialog', { name: /TaskFlow/ })).toBeInTheDocument()
  })

  it("paints a node type swatch with the graph's custom palette", () => {
    const onClose = vi.fn()
    render(
      <TypeColorProvider colors={resolveTypeColors({ VALIDATION_RULE: '#EF4444' })}>
        <AboutPanel
          meta={meta}
          presets={presets}
          stats={{
            ...stats,
            nodesByType: { VALIDATION_RULE: 1 },
          }}
          onClose={onClose}
        />
      </TypeColorProvider>,
    )
    const row = screen.getByTestId('about-nodetype-VALIDATION_RULE')
    expect(row.querySelector('.rounded-full')).toHaveStyle({ backgroundColor: '#EF4444' })
  })
})
