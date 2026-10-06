import type { TcPart, TcRow, TestCasesPayload } from './types'

// Test fixtures only (imported by *.test.tsx; never by the app).

const part = (level: TcPart['level'], remark = '', state: string | null = null): TcPart =>
  ({ level, remark, state, question: null, resolution: state === 'closed' ? 'R-DEMO-07' : null })

export function row(over: Partial<TcRow> = {}): TcRow {
  const id = over.id ?? '1.1-AC01-01'
  const steps = over.steps ?? '1. Open the portal.\n2. Click **Login**.'
  const chain = over.chain ?? 'Start of run: no test case to continue from.'
  const expected = over.expected ?? '1. The page opens.'
  const block = over.element_block ?? '2. The following elements are displayed and labelled correctly:\n    a. Button : **Login**'
  const data = over.data ?? '**Login provider** = TEST-IDP'
  const base: TcRow = {
    ref: `testcases/sit/rental-desk/${id}`,
    id, display_id: `TC-${id}`, level: 'sit', story: 'US-DEMO-001', flow: null,
    module: 'rental-desk', run: 'Main flow', section: 'Login', order: 1,
    group: 'run:sit:Main flow', status: 'active', priority: 'P1', technique: 'UC',
    covers: ['/stories/US-DEMO-001.md#HS-01'], prds: [],
    title: 'Log in as the tenant', objective: 'Verify the tenant can log in.',
    scenario: '**Scenario:** Log in.\n\n**Given:** A tenant.\n\n**When:** The tenant logs in.\n\n**Then:** The page opens.',
    chain, steps, data, expected, element_block: block,
    pre_extra: '', post: 'Tenant logged in.',
    confidence: 'Low',
    parts: {
      scenario: part('High', 'Source: HS-01.'),
      steps: part('Medium', 'Inferred: a log in action. Verify: the button.', 'open'),
      data: part('Low', 'Inferred: the profile id. Verify: fill it in.', 'open'),
      expected: part('High', 'Source: HS-01.'),
    },
    part_fields: { scenario: ['title', 'objective'], steps: ['steps'], data: ['data', 'pre_extra'], expected: ['expected'] },
    cells: {
      scenario: '**Scenario:** Log in.\n\n**Given:** A tenant.\n\n**When:** The tenant logs in.\n\n**Then:** The page opens.',
      steps: `${chain}\n\n${steps}`, data, expected: `${expected}\n${block}`,
      remarks: '**Scenario**: High - Source: HS-01.\n**Test Steps**: Medium - Inferred: a log in action. Verify: the button.',
    },
    editable: ['title', 'objective', 'steps', 'data', 'expected', 'post', 'pre_extra', 'priority'],
    spec: 'tools/sit_specs/US-DEMO-001.yaml',
  }
  return { ...base, ...over }
}

export const PAYLOAD: TestCasesPayload = {
  groups: [
    { key: 'run:sit:Main flow', label: 'Main flow', kind: 'run', level: 'sit', sections: ['Login', 'Self-check'], common: ['Shared setup.', 'Shared **data**.'] },
    { key: 'run:sit:Variant flow', label: 'Variant flow', kind: 'run', level: 'sit', sections: ['Login'], common: [] },
    { key: 'flow:uat:flows/FLOW-DEMO-001', label: 'Rental journey', kind: 'flow', level: 'uat', sections: ['Login'], common: [] },
  ],
  rows: [
    row(),
    row({ id: '1.1-AC02-01', display_id: 'TC-1.1-AC02-01', title: 'Pass the self-check', section: 'Self-check', order: 2, confidence: 'Medium',
      chain: 'Continue from TC-1.1-AC01-01: Tenant logged in.' }),
    row({ id: '1.1-AC02-02', display_id: 'TC-1.1-AC02-02', title: 'Fail the self-check', section: 'Self-check', order: 3, confidence: 'High', status: 'stale', editable: [] }),
    row({ id: '1.1-AC01-02', display_id: 'TC-1.1-AC01-02', title: 'Log in as a returning tenant', run: 'Variant flow', group: 'run:sit:Variant flow', order: 4, confidence: 'High', story: 'US-DEMO-002' }),
    row({ id: 'UAT-1.1-AC01-01', display_id: 'TC-1.1-AC01-01', ref: 'testcases/uat/UAT-1.1-AC01-01', level: 'uat', title: 'Journey login',
      run: null, flow: 'FLOW-DEMO-001', group: 'flow:uat:flows/FLOW-DEMO-001', order: 1, confidence: 'High', data: '',
      editable: ['title', 'objective', 'steps', 'expected', 'priority'], spec: 'tools/uat_specs/FLOW-DEMO-001.yaml',
      part_fields: { scenario: ['title', 'objective'], steps: ['steps'], data: ['steps'], expected: ['expected'] } }),
  ],
}
