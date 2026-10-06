import { describe, expect, it } from 'vitest'
import { computeJourney, layoutFlow, tidy, toDraft, type StepNode } from './journey'

const META = { id: 'FLOW-T-001', title: 'Login journey', entry: 'Logged out' }
const step = (id: string, ac: string, x: number, y: number, endState = `${ac} done`): StepNode =>
  ({ id, tc: null, ref: `US-T#${ac}`, x, y, endState, note: '' })

// a -> b -> c on top; d hangs below, leaving after a and rejoining at c
const NODES = [step('a', 'AC-1', 0, 0), step('b', 'AC-2', 300, 0), step('c', 'AC-3', 600, 0),
               step('d', 'AC-9', 300, 300)]
const EDGES = [{ from: 'a', to: 'b' }, { from: 'b', to: 'c' }, { from: 'a', to: 'd' }, { from: 'd', to: 'c' }]

describe('computeJourney', () => {
  it('reads a straight line as the main path', () => {
    const r = computeJourney(NODES.slice(0, 3), EDGES.slice(0, 2), META)
    expect(r.errors).toEqual([])
    expect(r.journey.map((j) => [j.id, j.ref, j.branch])).toEqual([
      ['J01', 'US-T#AC-1', null], ['J02', 'US-T#AC-2', null], ['J03', 'US-T#AC-3', null]])
    expect(r.paths).toEqual([['J01', 'J02', 'J03']])
    expect(r.branches).toEqual([])
  })

  it('treats the lower line out of a step as a branch placed before it rejoins', () => {
    const r = computeJourney(NODES, EDGES, META)
    expect(r.errors).toEqual([])
    expect(r.journey.map((j) => `${j.id}:${j.ref.split('#')[1]}${j.branch ? `(${j.branch})` : ''}`))
      .toEqual(['J01:AC-1', 'J02:AC-2', 'J03:AC-9(B01)', 'J04:AC-3'])
    expect(r.journey[2].note).toBe('leaves the main path after J01; replaces J02; rejoins at J04')
    expect(r.branches[0]).toMatchObject({ id: 'B01', title: 'Alternative via AC-9', steps: ['J03'] })
    expect(r.kind).toEqual({ a: 'main', b: 'main', c: 'main', d: 'alt' })
    expect(r.paths).toEqual([['J01', 'J02', 'J04'], ['J01', 'J03', 'J04']])
  })

  it('lets the drawing decide which line is main: the upper target wins', () => {
    const flipped = NODES.map((n) => (n.id === 'd' ? { ...n, y: -100 } : n))
    const r = computeJourney(flipped, EDGES, META)
    expect(r.kind).toMatchObject({ d: 'main', b: 'alt' })
  })

  it('names steps by their test case and carries it into the journey', () => {
    const withTc = NODES.map((n) => (n.id === 'd' ? { ...n, tc: '1.1-AC09-02', endState: ' ' } : n))
    const r = computeJourney(withTc, EDGES, META)
    expect(r.errors).toEqual(['J03 (1.1-AC09-02) needs an end state.'])
    expect(r.journey.map((j) => j.source_tc)).toEqual([null, null, '1.1-AC09-02', null])
    expect(r.branches[0].title).toBe('Alternative via 1.1-AC09-02')
  })

  it('keeps a renamed branch title', () => {
    const r = computeJourney(NODES, EDGES, META, { 'a>d': 'No account' })
    expect(r.branches[0].title).toBe('No account')
  })

  it('a branch that never rejoins ends the journey and goes last', () => {
    const r = computeJourney(NODES, EDGES.slice(0, 3), META)
    expect(r.journey.map((j) => j.ref.split('#')[1])).toEqual(['AC-1', 'AC-2', 'AC-3', 'AC-9'])
    expect(r.journey[3].note).toContain('ends the journey')
  })

  it('says what is missing instead of producing a journey', () => {
    expect(computeJourney(NODES, EDGES.slice(0, 2), META).errors[0]).toContain('nothing leading into them')
    expect(computeJourney(NODES.slice(0, 2), [{ from: 'a', to: 'b' }, { from: 'b', to: 'a' }], META).errors[0])
      .toContain('loop')
    const blank = NODES.slice(0, 2).map((n) => ({ ...n, endState: ' ' }))
    expect(computeJourney(blank, EDGES.slice(0, 1), META).errors).toContain('J01 (AC-1) needs an end state.')
    expect(computeJourney(NODES.slice(0, 1), [], { ...META, title: '' }).errors).toContain('Give the flow a title.')
    expect(computeJourney(NODES.slice(0, 1), [], { ...META, id: '../x' }).errors[0]).toContain('flow id')
  })

  it('ignores a line whose step was removed', () => {
    const r = computeJourney(NODES.slice(0, 2), [...EDGES.slice(0, 1), { from: 'b', to: 'gone' }], META)
    expect(r.errors).toEqual([])
  })
})

describe('toDraft', () => {
  it('produces what `wiki flow-draft` reads', () => {
    const d = toDraft(META, computeJourney(NODES, EDGES, META))
    expect(d).toMatchObject({ kind: 'flow-draft', id: 'FLOW-T-001', title: 'Login journey',
                              entry_condition: 'Logged out' })
    expect(d.branches).toEqual([{ id: 'B01', title: 'Alternative via AC-9',
                                  text: 'Leaves the main path after J01; replaces J02; rejoins at J04.' }])
  })
})

describe('layoutFlow', () => {
  const flow = {
    id: 'FLOW-X', title: 'x', entry_condition: null,
    journey: [
      { id: 'J01', end_state: 'one', note: null, ac_ref: 'US-T#AC-1', branch: null },
      { id: 'J02', end_state: 'two', note: null, ac_ref: 'US-T#AC-2', source_tc: '1.1-AC02-01',
        branch: { id: 'B01', title: 'Guest' } },
      { id: 'J03', end_state: 'three', note: null, ac_ref: 'US-T#AC-3', branch: null },
    ],
  }
  it('round-trips an existing journey: same order, same branch, same title', () => {
    const g = layoutFlow(flow)
    const r = computeJourney(g.nodes, g.edges, { id: 'FLOW-X', title: 'x', entry: '' }, g.branchTitles)
    expect(r.errors).toEqual([])
    expect(r.journey.map((j) => [j.end_state, j.branch])).toEqual([['one', null], ['two', 'B01'], ['three', null]])
    expect(r.branches[0].title).toBe('Guest')
    expect(r.journey.map((j) => j.source_tc)).toEqual([null, '1.1-AC02-01', null])
  })
  it('tidy lines steps up in journey order with branches below', () => {
    const g = layoutFlow(flow)
    const r = computeJourney(g.nodes, g.edges, { id: 'FLOW-X', title: 'x', entry: '' })
    const t = tidy([...g.nodes].reverse(), r)
    expect(t.map((n) => n.endState)).toEqual(['one', 'two', 'three'])
    expect(t[1].y).toBeGreaterThan(t[0].y)
  })
})
