import { beforeEach, describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import type { BuilderModel } from '../api'

vi.mock('../api', async () => {
  const actual = await vi.importActual<typeof import('../api')>('../api')
  return { ...actual, getFlowBuilder: vi.fn(), onChange: () => () => {} }
})
import * as api from '../api'
import { FlowOverviewExport, FlowOverviewPage, bakedOverview } from './FlowOverviewPage'

const step = (id: string, ac: string, end: string, note: string | null = null) =>
  ({ id, end_state: end, note, ac_ref: `US-T#${ac}`, source_tc: null, branch: null })

const MODEL: BuilderModel = {
  project: 'Demo', code: 'DMO',
  stories: [{
    id: 'US-T', title: 'Apply', status: 'aligned',
    acs: [
      { id: 'AC-1', title: 'Login', text: 'Login opens the Home page.', status: null, tcs: [] },
      { id: 'AC-2', text: 'The partner is added.', status: null, tcs: [] },
    ],
  }],
  flows: [
    { id: 'FLOW-DMO-SC01', title: 'Citizen couple', status: 'aligned', entry_condition: null,
      journey: [step('J01', 'AC-1', 'Home shown'), step('J02', 'AC-2', 'Partner added', 'Pink card')] },
    { id: 'FLOW-DMO-SC02', title: 'Resident couple', status: 'aligned', entry_condition: null,
      journey: [step('J01', 'AC-1', 'Home shown'), step('J02', 'AC-2', 'Partner added', 'Blue card')] },
  ],
  tcs: {},
  journey_tcs: {
    'FLOW-DMO-SC02#J02': {
      id: 'TC-DMO-SC02-AC02-01', section: 'Partner', confidence: 'Medium',
      scenario: 'Resident adds a partner', steps: '1. Click **Add partner**', data: '',
      expected: '1. The partner is listed', remarks: '**Test Steps**: Medium - inferred.',
    },
  },
}

const panel = () => document.querySelector('.fb-panel') as HTMLElement
const steps = () => document.querySelectorAll('.fo-node')

beforeEach(() => { vi.mocked(api.getFlowBuilder).mockResolvedValue(MODEL) })

describe('FlowOverviewPage', () => {
  it('draws one step per shared criterion and lists the flows', async () => {
    render(<FlowOverviewPage theme="light" />)
    expect(await screen.findByRole('heading', { name: 'Flow overview' })).toBeInTheDocument()
    fireEvent.click(screen.getByRole('switch', { name: 'Split steps by data' }))   // merged
    await waitFor(() => expect(steps()).toHaveLength(2))
    expect(panel()).toHaveTextContent('2 distinct steps, 2 walked by every flow.')
    // a criterion title is shown where the story gives one, else its text
    expect(screen.getByText('Login')).toBeInTheDocument()
    expect(screen.getByText('The partner is added.')).toBeInTheDocument()
    // the shared step lists both data notes with the flow that carries each
    expect(screen.getByText('Pink card')).toBeInTheDocument()
    expect(screen.getByText('Blue card')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Citizen couple/ })).toHaveAttribute('aria-pressed', 'false')
  })

  it('opens split into one node per data note, and merges on request', async () => {
    render(<FlowOverviewPage theme="light" />)
    await screen.findByRole('heading', { name: 'Flow overview' })
    expect(screen.getByRole('switch', { name: 'Split steps by data' })).toBeChecked()
    await waitFor(() => expect(steps()).toHaveLength(3))
    expect(panel()).toHaveTextContent('3 distinct steps, 1 walked by every flow.')
    fireEvent.click(screen.getByRole('switch', { name: 'Split steps by data' }))
    await waitFor(() => expect(steps()).toHaveLength(2))
  })

  it('traces one flow and dims the steps it does not walk', async () => {
    render(<FlowOverviewPage theme="light" />)
    await screen.findByRole('heading', { name: 'Flow overview' })
    const pick = screen.getByRole('button', { name: /Resident couple/ })
    fireEvent.click(pick)
    expect(pick).toHaveAttribute('aria-pressed', 'true')
    await waitFor(() => expect(document.querySelectorAll('.fo-node.fo-dim')).toHaveLength(1))
    fireEvent.click(screen.getByRole('button', { name: 'Show all flows' }))
    expect(document.querySelectorAll('.fo-node.fo-dim')).toHaveLength(0)
  })

  it('resets the chart: no flow traced, the split left as chosen', async () => {
    render(<FlowOverviewPage theme="light" />)
    await screen.findByRole('heading', { name: 'Flow overview' })
    fireEvent.click(screen.getByRole('button', { name: /Resident couple/ }))
    await waitFor(() => expect(document.querySelectorAll('.fo-node.fo-dim')).toHaveLength(1))
    fireEvent.click(screen.getByRole('button', { name: 'Reset chart' }))
    await waitFor(() => expect(document.querySelectorAll('.fo-node.fo-dim')).toHaveLength(0))
    expect(screen.getByRole('button', { name: /Resident couple/ })).toHaveAttribute('aria-pressed', 'false')
    expect(steps()).toHaveLength(3)
  })

  it('opens a picked step on the test case each flow runs there', async () => {
    render(<FlowOverviewPage theme="light" />)
    await screen.findByRole('heading', { name: 'Flow overview' })
    await waitFor(() => expect(steps()).toHaveLength(3))
    fireEvent.click(screen.getByText('Blue card'))
    expect(await screen.findByText('TC-DMO-SC02-AC02-01')).toBeInTheDocument()
    // the row's cells, with the workbook's bold markers shown as bold
    expect(panel()).toHaveTextContent('Test Steps1. Click Add partner')
    expect(screen.getByText('Add partner').tagName).toBe('B')
    expect(panel()).toHaveTextContent('Field / Values-')
    expect(panel()).toHaveTextContent('Test Case RemarksTest Steps: Medium - inferred.')
    expect(document.querySelector('.fo-node.selected')).not.toBeNull()
    fireEvent.click(screen.getByRole('button', { name: 'Back to flows' }))
    expect(panel()).toHaveTextContent('Flows (2)')
  })

  it('says so where a flow has no test case for the step yet', async () => {
    render(<FlowOverviewPage theme="light" />)
    await screen.findByRole('heading', { name: 'Flow overview' })
    await waitFor(() => expect(steps()).toHaveLength(3))
    fireEvent.click(screen.getByText('Pink card'))
    expect(await screen.findByText(/No test case has been generated/)).toBeInTheDocument()
  })

  it('is headed by the title the project sets', async () => {
    vi.mocked(api.getFlowBuilder).mockResolvedValue({ ...MODEL, overview_title: 'Two demo journeys' })
    render(<FlowOverviewPage theme="light" />)
    expect(await screen.findByRole('heading', { name: 'Two demo journeys' })).toBeInTheDocument()
  })

  it('has a side panel that can be dragged wider', async () => {
    render(<FlowOverviewPage theme="light" />)
    await screen.findByRole('heading', { name: 'Flow overview' })
    const work = document.querySelector('.fo-work') as HTMLElement
    expect(work.style.gridTemplateColumns).toContain('340px')
    fireEvent.mouseDown(screen.getByRole('separator', { name: 'Resize the side panel' }), { clientX: 900 })
    fireEvent.mouseMove(window, { clientX: 700 })
    fireEvent.mouseUp(window)
    await waitFor(() => expect(work.style.gridTemplateColumns).toContain('540px'))
  })

  it('says so when there are no flows', async () => {
    vi.mocked(api.getFlowBuilder).mockResolvedValue({ ...MODEL, flows: [] })
    render(<FlowOverviewPage theme="light" />)
    expect(await screen.findByText('No flows yet.')).toBeInTheDocument()
    expect(panel()).toHaveTextContent('Flows (0)')
  })

  it('shows the error when the flows cannot be read', async () => {
    vi.mocked(api.getFlowBuilder).mockRejectedValue(new Error('GET /api/flow_builder -> 500'))
    render(<FlowOverviewPage theme="light" />)
    expect(await screen.findByText(/GET \/api\/flow_builder -> 500/)).toBeInTheDocument()
  })

  it('offers the overview as a standalone download', async () => {
    render(<FlowOverviewPage theme="light" />)
    await screen.findByRole('heading', { name: 'Flow overview' })
    const link = screen.getByRole('link', { name: 'Export' })
    expect(link).toHaveAttribute('href', '/api/flow_overview.html')
    expect(link).toHaveAttribute('download')
  })
})

describe('FlowOverviewExport', () => {
  it('draws the baked flows without calling the server', async () => {
    vi.mocked(api.getFlowBuilder).mockClear()
    render(<FlowOverviewExport model={MODEL} />)
    await waitFor(() => expect(steps()).toHaveLength(3))
    expect(api.getFlowBuilder).not.toHaveBeenCalled()
    expect(document.title).toBe('Flow overview - Demo')
    expect(screen.getByRole('button', { name: 'Whole chart' })).toBeEnabled()
    // the same controls as in the app, bar the export itself
    fireEvent.click(screen.getByRole('switch', { name: 'Split steps by data' }))
    await waitFor(() => expect(steps()).toHaveLength(2))
    expect(screen.getByRole('button', { name: 'Reset chart' })).toBeEnabled()
    expect(screen.queryByRole('link', { name: 'Export' })).toBeNull()
    fireEvent.click(screen.getByRole('button', { name: /Switch to dark theme/ }))
    expect(document.documentElement.dataset.theme).toBe('dark')
  })

  it('reads the flows a file carries, and nothing in the running app', () => {
    expect(bakedOverview()).toBeNull()
    ;(window as { __TC_FLOW_OVERVIEW__?: BuilderModel }).__TC_FLOW_OVERVIEW__ = MODEL
    expect(bakedOverview()).toBe(MODEL)
    delete (window as { __TC_FLOW_OVERVIEW__?: BuilderModel }).__TC_FLOW_OVERVIEW__
  })
})
