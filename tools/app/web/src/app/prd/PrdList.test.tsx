import { describe, expect, it } from 'vitest'
import { render, screen, within } from '@testing-library/react'
import { PrdList } from './PrdList'
import type { Prd } from '../api'

const PRDS: Prd[] = [
  { id: 'rental-application', title: 'Rental application', adopted: 2, staged: null },
  { id: 'rental-payment', title: 'Rental payment', adopted: 1, staged: 2 },
]

describe('PrdList', () => {
  it('lists every PRD with its title, adopted and staged version', () => {
    render(<PrdList prds={PRDS} />)
    const app = screen.getByRole('row', { name: /rental-application/ })
    expect(within(app).getByText('Rental application')).toBeInTheDocument()
    expect(within(app).getByText('v2')).toBeInTheDocument()
    expect(within(app).getByText('none staged')).toBeInTheDocument()
    const pay = screen.getByRole('row', { name: /rental-payment/ })
    expect(within(pay).getByText('v1')).toBeInTheDocument()
    expect(within(pay).getByText('v2 staged')).toBeInTheDocument()
  })

  it('says so when no PRD is registered', () => {
    render(<PrdList prds={[]} />)
    expect(screen.getByText('No PRD registered.')).toBeInTheDocument()
  })

  it('does not claim "No PRD registered." on a project that is not migrated yet', () => {
    render(<PrdList prds={[]} schema1 />)
    expect(screen.getByText('PRD state is not shown until the project is migrated.')).toBeInTheDocument()
    expect(screen.queryByText('No PRD registered.')).toBeNull()
  })

  it('shows a PRD that is registered but has nothing adopted yet', () => {
    render(<PrdList prds={[{ id: 'rental-fees', title: 'Rental fees', adopted: null, staged: null }]} />)
    expect(within(screen.getByRole('row', { name: /rental-fees/ })).getByText('not adopted')).toBeInTheDocument()
  })
})