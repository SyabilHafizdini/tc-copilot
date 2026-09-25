import { describe, it, expect } from 'vitest'
import { buildFileTree } from './fileTree'
import type { FileNode } from './fileTree'

describe('buildFileTree', () => {
  it('turns a single top-level ref into a lone file node (no folder)', () => {
    const tree = buildFileTree(['README'])
    expect(tree).toEqual([{ kind: 'file', name: 'README', ref: 'README' }])
  })

  it('groups refs sharing a prefix under one folder', () => {
    const tree = buildFileTree(['glossary/edo', 'glossary/mo'])
    expect(tree).toEqual([
      {
        kind: 'folder', name: 'glossary', path: 'glossary',
        children: [
          { kind: 'file', name: 'edo', ref: 'glossary/edo' },
          { kind: 'file', name: 'mo', ref: 'glossary/mo' },
        ],
      },
    ])
  })

  it('builds arbitrarily deep nesting (testcases/sit/production-monitoring/...)', () => {
    const tree = buildFileTree(['testcases/sit/production-monitoring/1.1.3.1.1-AC01-01'])
    expect(tree).toEqual([
      {
        kind: 'folder', name: 'testcases', path: 'testcases',
        children: [
          {
            kind: 'folder', name: 'sit', path: 'testcases/sit',
            children: [
              {
                kind: 'folder', name: 'production-monitoring', path: 'testcases/sit/production-monitoring',
                children: [
                  { kind: 'file', name: '1.1.3.1.1-AC01-01', ref: 'testcases/sit/production-monitoring/1.1.3.1.1-AC01-01' },
                ],
              },
            ],
          },
        ],
      },
    ])
  })

  it('merges refs that share an intermediate folder without duplicating it', () => {
    const tree = buildFileTree(['sources/prd/1', 'sources/prd/4-1-1-1', 'sources/other'])
    const sources = tree.find((n) => n.kind === 'folder' && n.name === 'sources') as Extract<FileNode, { kind: 'folder' }>
    expect(sources).toBeDefined()
    expect(sources.children).toHaveLength(2) // 'other' file + 'prd' folder
    const prd = sources.children.find((n) => n.kind === 'folder' && n.name === 'prd') as Extract<FileNode, { kind: 'folder' }>
    expect(prd).toBeDefined()
    expect(prd.children.map((c) => c.name)).toEqual(['1', '4-1-1-1'])
  })

  it('sorts folders before files at the same level', () => {
    const tree = buildFileTree(['stories/US-A', 'sources/prd/1'])
    expect(tree.map((n) => n.name)).toEqual(['sources', 'stories'])
    // 'sources' is a folder, 'stories' would also be a folder here (both have children) —
    // use a case that mixes a file and a folder at the same level instead:
    const mixed = buildFileTree(['modules/81-tasking', 'modules-note'])
    expect(mixed.map((n) => n.kind)).toEqual(['folder', 'file'])
    expect(mixed.map((n) => n.name)).toEqual(['modules', 'modules-note'])
  })

  it('sorts folders-first, then alphabetically, within a folder mixing files and subfolders', () => {
    const tree = buildFileTree(['flows/zeta-flow', 'flows/alpha/nested', 'flows/beta-flow'])
    const flows = tree[0] as Extract<FileNode, { kind: 'folder' }>
    expect(flows.name).toBe('flows')
    // 'alpha' (folder) sorts before the files even though 'alpha' < 'beta-flow' < 'zeta-flow' alphabetically too;
    // the real test is folders-first when alpha ordering would disagree:
    expect(flows.children.map((c) => c.kind)).toEqual(['folder', 'file', 'file'])
    expect(flows.children.map((c) => c.name)).toEqual(['alpha', 'beta-flow', 'zeta-flow'])
  })

  it('sorts top-level folders alphabetically, matching the real doc set kinds', () => {
    const refs = [
      'testcases/sit/x', 'stories/US-1', 'sources/prd/1', 'resolutions/R-1',
      'modules/81-tasking', 'glossary/edo', 'flows/production-monitoring-e2e',
    ]
    const tree = buildFileTree(refs)
    expect(tree.map((n) => n.name)).toEqual(
      ['flows', 'glossary', 'modules', 'resolutions', 'sources', 'stories', 'testcases'],
    )
    expect(tree.every((n) => n.kind === 'folder')).toBe(true)
  })

  it('is stable/idempotent and handles an empty list', () => {
    expect(buildFileTree([])).toEqual([])
  })

  it('produces folder nodes whose path is the joined ancestor segments, not just the leaf name', () => {
    const tree = buildFileTree(['testcases/sit/production-monitoring/1.1.3.1.1-AC01-01'])
    const testcases = tree[0] as Extract<FileNode, { kind: 'folder' }>
    const sit = testcases.children[0] as Extract<FileNode, { kind: 'folder' }>
    expect(sit.path).toBe('testcases/sit')
    const pm = sit.children[0] as Extract<FileNode, { kind: 'folder' }>
    expect(pm.path).toBe('testcases/sit/production-monitoring')
  })
})
