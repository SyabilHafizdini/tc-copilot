import { beforeEach, describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import type { BuilderModel } from '../api'

vi.mock('../api', async () => {
  const actual = await vi.importActual<typeof import('../api')>('../api')
  return { ...actual, getFlowBuilder: vi.fn(), runAction: vi.fn(), onChange: () => () => {} }
})
import * as api from '../api'
import { FlowBuilderPage } from './FlowBuilderPage'

const tc = (id: string, title: string, acs: string[], end: string) =>
  ({ id, title, acs, sections: { Postconditions: end } })

const MODEL: BuilderModel = {
  project: 'Demo', code: 'DMO',
  stories: [{
    id: 'US-T', title: 'Log in', status: 'aligned',
    acs: [
      { id: 'AC-1', text: 'Login opens the Home page.', status: null, tcs: ['1.1-AC01-01', '1.1-AC01-02'] },
      { id: 'AC-2', text: 'A wrong password shows an error.', status: null, tcs: ['1.1-AC02-01'] },
      { id: 'AC-3', text: 'Removed criterion.', status: 'voided', tcs: [] },
      { id: 'AC-4', text: 'Nothing generated here yet.', status: null, tcs: [] },
    ],
  }],
  flows: [{
    id: 'FLOW-DMO-004', title: 'Existing', status: 'aligned', entry_condition: 'Logged out',
    journey: [
      { id: 'J01', end_state: 'Home shown', note: null, ac_ref: 'US-T#AC-1', source_tc: null, branch: null },
      { id: 'J02', end_state: 'Error shown', note: null, ac_ref: 'US-T#AC-2', source_tc: '1.1-AC02-01', branch: null },
    ],
  }],
  tcs: {
    '1.1-AC01-01': tc('1.1-AC01-01', 'Log in with valid credentials', ['US-T#AC-1'], '**Home** page shown.'),
    '1.1-AC01-02': tc('1.1-AC01-02', 'Log in with remember me ticked', ['US-T#AC-1'], 'Home page shown; session remembered.'),
    '1.1-AC02-01': tc('1.1-AC02-01', 'Reject a wrong password', ['US-T#AC-2'], ''),
  },
}

const panel = () => document.querySelector('.fb-panel') as HTMLElement
const palette = () => document.querySelector('.fb-palette') as HTMLElement
const saveButton = () => screen.getByRole('button', { name: /save as draft flow/i })
const add = (id: string) => screen.getByRole('button', { name: `Add ${id}` })

beforeEach(() => {
  localStorage.clear()
  vi.mocked(api.getFlowBuilder).mockResolvedValue(MODEL)
  vi.mocked(api.runAction).mockReset()
})

describe('FlowBuilderPage', () => {
  it('lists test cases by id and title under their criterion', async () => {
    render(<FlowBuilderPage theme="light" />)
    expect(await screen.findByRole('button', { name: 'Add 1.1-AC01-01' })).toBeInTheDocument()
    expect(within(palette()).getByText('Log in with valid credentials')).toBeInTheDocument()
    expect(within(palette()).getByText('Reject a wrong password')).toBeInTheDocument()
    // a criterion with nothing generated says so; a voided one is not offered
    expect(within(palette()).getByText('No SIT test cases yet.')).toBeInTheDocument()
    expect(within(palette()).queryByText('AC-3')).toBeNull()
    expect(within(panel()).getByDisplayValue('FLOW-DMO-005')).toBeInTheDocument()
    expect(saveButton()).toBeDisabled()
  })

  it('filters the list by test case title', async () => {
    render(<FlowBuilderPage theme="light" />)
    await screen.findByRole('button', { name: 'Add 1.1-AC01-01' })
    fireEvent.change(screen.getByLabelText('Filter test cases'), { target: { value: 'wrong pass' } })
    expect(screen.queryByRole('button', { name: 'Add 1.1-AC01-01' })).toBeNull()
    expect(add('1.1-AC02-01')).toBeInTheDocument()
  })

  it('pressing + chains test cases into a journey; each seeds its own end state', async () => {
    render(<FlowBuilderPage theme="light" />)
    fireEvent.click(await screen.findByRole('button', { name: 'Add 1.1-AC01-01' }))
    fireEvent.click(add('1.1-AC02-01'))
    await waitFor(() => expect(within(panel()).getByText(/Journey \(2 steps\)/)).toBeInTheDocument())
    expect(within(panel()).getByText('Home page shown.')).toBeInTheDocument()
    expect(within(panel()).getByText('Log in with valid credentials')).toBeInTheDocument()
    // 1.1-AC02-01 has no postcondition to seed from, so the builder says what is missing
    expect(within(panel()).getByText('J02 (1.1-AC02-01) needs an end state.')).toBeInTheDocument()
    expect(within(panel()).getByText('Give the flow a title.')).toBeInTheDocument()
    expect(saveButton()).toBeDisabled()
  })

  it('saves the stitched test case with the criterion it covers', async () => {
    vi.mocked(api.runAction).mockResolvedValue({ argv: [], rc: 0, stdout: 'ok', stderr: '' })
    render(<FlowBuilderPage theme="light" />)
    fireEvent.click(await screen.findByRole('button', { name: 'Add 1.1-AC01-02' }))
    fireEvent.change(within(panel()).getByPlaceholderText('What journey is this?'), { target: { value: 'Login' } })
    await waitFor(() => expect(saveButton()).toBeEnabled())
    fireEvent.click(saveButton())
    await waitFor(() => expect(api.runAction).toHaveBeenCalledTimes(1))
    const [name, params] = vi.mocked(api.runAction).mock.calls[0]
    expect(name).toBe('flow_draft')
    expect(params).toEqual({ draft: {
      kind: 'flow-draft', id: 'FLOW-DMO-005', title: 'Login', entry_condition: '',
      journey: [{ id: 'J01', ref: 'US-T#AC-1', source_tc: '1.1-AC01-02',
                  end_state: 'Home page shown; session remembered.', note: null, branch: null }],
      branches: [], paths: [['J01']],
    } })
    expect(await screen.findByText(/Saved FLOW-DMO-005 as a draft flow/)).toBeInTheDocument()
  })

  it('shows a refusal from the command verbatim', async () => {
    vi.mocked(api.runAction).mockResolvedValue(
      { argv: [], rc: 1, stdout: '', stderr: 'flow-draft: REFUSED - FLOW-DMO-005 already exists' })
    render(<FlowBuilderPage theme="light" />)
    fireEvent.click(await screen.findByRole('button', { name: 'Add 1.1-AC01-01' }))
    fireEvent.change(within(panel()).getByPlaceholderText('What journey is this?'), { target: { value: 'Login' } })
    await waitFor(() => expect(saveButton()).toBeEnabled())
    fireEvent.click(saveButton())
    expect(await screen.findByText(/REFUSED - FLOW-DMO-005 already exists/)).toBeInTheDocument()
  })

  it('loads an existing flow: stitched steps keep their test case, older steps show the criterion', async () => {
    render(<FlowBuilderPage theme="light" />)
    await screen.findByRole('button', { name: 'Add 1.1-AC01-01' })
    fireEvent.change(screen.getByLabelText('Start from an existing flow'), { target: { value: 'FLOW-DMO-004' } })
    await waitFor(() => expect(within(panel()).getByText(/Journey \(2 steps\)/)).toBeInTheDocument())
    expect(within(panel()).getByDisplayValue('FLOW-DMO-004')).toBeInTheDocument()
    const steps = within(panel()).getAllByRole('listitem').map((li) => li.textContent)
    expect(steps[0]).toContain('J01 AC-1')
    expect(steps[1]).toContain('J02 1.1-AC02-01')
    expect(steps[1]).toContain('Reject a wrong password')
  })
})
