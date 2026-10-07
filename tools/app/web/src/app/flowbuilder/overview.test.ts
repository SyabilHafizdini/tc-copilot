import { describe, expect, it } from 'vitest'
import { COL_W, ROW_H, mergeFlows, normNote, shortLabel } from './overview'

const step = (id: string, ac: string, end: string, note: string | null = null) =>
  ({ id, end_state: end, note, ac_ref: `US-T#${ac}` as string | null, source_tc: null, branch: null })
const flow = (id: string, journey: ReturnType<typeof step>[]) =>
  ({ id, title: `Title ${id}`, status: 'aligned', entry_condition: null, journey })

describe('mergeFlows', () => {
  const MODEL = {
    flows: [
      flow('FLOW-X-SC01', [
        step('J01', 'AC-1', 'Logged in', 'Scenario 1 logs in as a citizen'),
        step('J09', 'AC-2', 'Refused'),            // a check only this flow walks
        step('J02', 'AC-2', 'Partner added', 'Pink card'),
        step('J03', 'AC-3', 'Submitted'),
      ]),
      flow('FLOW-X-SC02', [
        step('J01', 'AC-1', 'Logged in', 'Scenario 2 logs in as a citizen'),
        step('J02', 'AC-2', 'Partner added', 'Blue card'),
        step('J03', 'AC-3', 'Submitted'),
      ]),
    ],
  }

  it('shares a node between flows that walk the same criterion to the same end state', () => {
    const o = mergeFlows(MODEL, false)
    expect(o.nodes.map((n) => [n.ref, n.endState, n.flows.length])).toEqual([
      ['US-T#AC-1', 'Logged in', 2], ['US-T#AC-2', 'Refused', 1],
      ['US-T#AC-2', 'Partner added', 2], ['US-T#AC-3', 'Submitted', 2],
    ])
    expect(o.shared).toBe(3)
    expect(o.flows.map((f) => [f.label, f.steps])).toEqual([['SC01', 4], ['SC02', 3]])
  })

  it('keeps the same criterion with another end state as its own step', () => {
    const o = mergeFlows(MODEL, false)
    const [refused, added] = o.nodes.filter((n) => n.ref === 'US-T#AC-2')
    expect(refused.flows).toEqual(['FLOW-X-SC01'])
    expect(added.flows).toEqual(['FLOW-X-SC01', 'FLOW-X-SC02'])
  })

  it('lists the data notes of a shared step, ignoring the flow naming itself', () => {
    const o = mergeFlows(MODEL, false)
    const login = o.nodes[0]
    expect(login.variants).toEqual([{ note: 'Scenario # logs in as a citizen', flows: ['FLOW-X-SC01', 'FLOW-X-SC02'] }])
    const added = o.nodes.find((n) => n.endState === 'Partner added')!
    expect(added.variants.map((v) => [v.note, v.flows])).toEqual([
      ['Pink card', ['FLOW-X-SC01']], ['Blue card', ['FLOW-X-SC02']],
    ])
  })

  it('splits a step by data note when asked', () => {
    const o = mergeFlows(MODEL, true)
    const added = o.nodes.filter((n) => n.endState === 'Partner added')
    expect(added.map((n) => [n.variants[0].note, n.flows])).toEqual([
      ['Pink card', ['FLOW-X-SC01']], ['Blue card', ['FLOW-X-SC02']],
    ])
    expect(o.nodes).toHaveLength(5)
    expect(o.shared).toBe(2)
  })

  it('carries on each line the flows that take it', () => {
    const o = mergeFlows(MODEL, false)
    const name = (id: string) => o.nodes.find((n) => n.id === id)!.endState
    expect(o.edges.map((e) => [name(e.from), name(e.to), e.flows.map(shortLabel)])).toEqual([
      ['Logged in', 'Refused', ['SC01']],
      ['Refused', 'Partner added', ['SC01']],
      ['Partner added', 'Submitted', ['SC01', 'SC02']],
      ['Logged in', 'Partner added', ['SC02']],
    ])
  })

  it('lays a step one column right of its latest predecessor, the most shared on top', () => {
    const o = mergeFlows(MODEL, false)
    const at = (end: string) => o.nodes.find((n) => n.endState === end)!
    expect([at('Logged in').col, at('Refused').col, at('Partner added').col, at('Submitted').col]).toEqual([0, 1, 2, 3])
    expect(at('Partner added').x).toBe(2 * COL_W)
    const split = mergeFlows(MODEL, true)
    const [pink, blue] = split.nodes.filter((n) => n.endState === 'Partner added')
    expect([pink.col, blue.col]).toEqual([2, 2])
    expect([pink.y, blue.y]).toEqual([0, ROW_H])
  })

  it('still lays out when two flows order the same steps differently', () => {
    const o = mergeFlows({ flows: [
      flow('F-1', [step('J01', 'AC-1', 'a'), step('J02', 'AC-2', 'b')]),
      flow('F-2', [step('J01', 'AC-2', 'b'), step('J02', 'AC-1', 'a')]),
    ] }, false)
    expect(o.nodes).toHaveLength(2)
    expect(o.nodes.every((n) => Number.isFinite(n.x) && n.col <= 2)).toBe(true)
  })

  it('skips entries with no criterion and copes with no flows', () => {
    expect(mergeFlows({ flows: [] }, false)).toEqual({ nodes: [], edges: [], flows: [], shared: 0 })
    const o = mergeFlows({ flows: [flow('F-1', [{ ...step('J01', 'AC-1', 'a'), ac_ref: null }])] }, false)
    expect(o.nodes).toHaveLength(0)
    expect(o.flows[0].steps).toBe(0)
  })
})

describe('normNote', () => {
  it('blanks only the flow\'s own number', () => {
    expect(normNote('Scenario 4 shows the 31 day page', 'FLOW-DEMO-SC04')).toBe('Scenario # shows the 31 day page')
    expect(normNote('Pass valid 6 months', 'FLOW-DEMO-SC04')).toBe('Pass valid 6 months')
    expect(normNote(null, 'FLOW-DEMO-SC04')).toBe('')
    expect(normNote('No number in the id', 'MAIN')).toBe('No number in the id')
  })
})
