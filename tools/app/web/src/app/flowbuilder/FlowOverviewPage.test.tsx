import { beforeEach, describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import type { BuilderModel } from '../api'

vi.mock('../api', async () => {
  const actual = await vi.importActual<typeof import('../api')>('../api')
  return { ...actual, getFlowBuilder: vi.fn(), onChange: () => () => {} }
})
import * as api from '../api'
import { FlowOverviewPage } from './FlowOverviewPage'

const step = (id: string, ac: string, end: string, note: string | null = null) =>
  ({ id, end_state: end, note, ac_ref: `US-T#${ac}`, source_tc: null, branch: null })

const MODEL: BuilderModel = {
  project: 'Demo', code: 'DMO',
  stories: [{
    id: 'US-T', title: 'Apply', status: 'aligned',
    acs: [
      { id: 'AC-1', title: 'Login', text: 'Login opens the Home page.', status: null, tcs: [] },
      { id: 'AC-2', text: 'The spouse is added.', status: null, tcs: [] },
    ],
  }],
  flows: [
    { id: 'FLOW-DMO-SC01', title: 'Citizen couple', status: 'aligned', entry_condition: null,
      journey: [step('J01', 'AC-1', 'Home shown'), step('J02', 'AC-2', 'Spouse added', 'Pink card')] },
    { id: 'FLOW-DMO-SC02', title: 'Resident couple', status: 'aligned', entry_condition: null,
      journey: [step('J01', 'AC-1', 'Home shown'), step('J02', 'AC-2', 'Spouse added', 'Blue card')] },
  ],
  tcs: {},
}

const panel = () => document.querySelector('.fb-panel') as HTMLElement
const steps = () => document.querySelectorAll('.fo-node')

beforeEach(() => { vi.mocked(api.getFlowBuilder).mockResolvedValue(MODEL) })

describe('FlowOverviewPage', () => {
  it('draws one step per shared criterion and lists the flows', async () => {
    render(<FlowOverviewPage theme="light" />)
    expect(await screen.findByRole('heading', { name: 'Flow overview' })).toBeInTheDocument()
    await waitFor(() => expect(steps()).toHaveLength(2))
    expect(panel()).toHaveTextContent('2 distinct steps, 2 walked by every flow.')
    // a criterion title is shown where the story gives one, else its text
    expect(screen.getByText('Login')).toBeInTheDocument()
    expect(screen.getByText('The spouse is added.')).toBeInTheDocument()
    // the shared step lists both data notes with the flow that carries each
    expect(screen.getByText('Pink card')).toBeInTheDocument()
    expect(screen.getByText('Blue card')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Citizen couple/ })).toHaveAttribute('aria-pressed', 'false')
  })

  it('splits a step into one node per data note', async () => {
    render(<FlowOverviewPage theme="light" />)
    await screen.findByRole('heading', { name: 'Flow overview' })
    fireEvent.click(screen.getByRole('checkbox', { name: 'Split steps by data' }))
    await waitFor(() => expect(steps()).toHaveLength(3))
    expect(panel()).toHaveTextContent('3 distinct steps, 1 walked by every flow.')
  })

  it('traces one flow and dims the steps it does not walk', async () => {
    render(<FlowOverviewPage theme="light" />)
    await screen.findByRole('heading', { name: 'Flow overview' })
    fireEvent.click(screen.getByRole('checkbox', { name: 'Split steps by data' }))
    const pick = screen.getByRole('button', { name: /Resident couple/ })
    fireEvent.click(pick)
    expect(pick).toHaveAttribute('aria-pressed', 'true')
    await waitFor(() => expect(document.querySelectorAll('.fo-node.fo-dim')).toHaveLength(1))
    fireEvent.click(screen.getByRole('button', { name: 'Show all flows' }))
    expect(document.querySelectorAll('.fo-node.fo-dim')).toHaveLength(0)
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
})
