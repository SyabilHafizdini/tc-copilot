/* Pure drawing -> journey logic for the flow builder.
 *
 * A flow's journey is a LIST (flows/<id>.md `journey:`), so the drawing is
 * read as one main path plus branches that leave it and optionally rejoin it.
 * Where two lines leave a step, the upper target is the main path. */

export type StepNode = {
  id: string
  tc: string | null    // the SIT test case this step stitches in, if chosen
  ref: string          // "<story id>#<criterion id>" that test case covers
  x: number
  y: number
  endState: string
  note: string
}
export type StepEdge = { from: string; to: string }
export type Meta = { id: string; title: string; entry: string }

export type JourneyEntry = {
  id: string
  ref: string
  source_tc: string | null
  end_state: string
  note: string | null
  branch: string | null
}
export type Branch = { id: string; key: string; title: string; text: string; steps: string[] }
export type JourneyResult = {
  errors: string[]
  journey: JourneyEntry[]
  branches: Branch[]
  paths: string[][]
  order: Record<string, string>          // node id -> J-id
  kind: Record<string, 'main' | 'alt'>
}

const MAX_PATHS = 40
const acOf = (ref: string) => ref.split('#')[1] ?? ref
// how a step is named to the user: its test case, else its criterion
const nameOf = (n: { tc: string | null; ref: string }) => n.tc ?? acOf(n.ref)
const pad = (n: number) => String(n).padStart(2, '0')

export function computeJourney(
  nodes: StepNode[], edges: StepEdge[], meta: Meta,
  branchTitles: Record<string, string> = {},
): JourneyResult {
  const errors: string[] = []
  const res: JourneyResult = { errors, journey: [], branches: [], paths: [], order: {}, kind: {} }
  if (!nodes.length) return res
  const byId = new Map(nodes.map((n) => [n.id, n]))
  const live = edges.filter((e) => byId.has(e.from) && byId.has(e.to))
  const outs = (id: string) => live.filter((e) => e.from === id).map((e) => byId.get(e.to)!)
    .sort((a, b) => a.y - b.y || a.x - b.x)
  const hasIn = (id: string) => live.some((e) => e.to === id)

  const starts = nodes.filter((n) => !hasIn(n.id))
  if (starts.length !== 1) {
    errors.push(starts.length
      ? `${starts.length} steps have nothing leading into them (${starts.map(nameOf).join(', ')}). A flow has one first step: connect the others.`
      : 'The steps form a loop with no first step.')
    return res
  }
  const main: StepNode[] = []
  const seen = new Set<string>()
  for (let n: StepNode | undefined = starts[0]; n && !seen.has(n.id); n = outs(n.id)[0]) {
    main.push(n); seen.add(n.id)
  }
  if (outs(main[main.length - 1].id)[0]) {
    errors.push('The main path loops back on itself.')
    return res
  }
  const mainIdx = new Map(main.map((n, i) => [n.id, i]))

  type Raw = { fork: StepNode; steps: StepNode[]; rejoin: StepNode | null; id: string; note: string }
  const raws: Raw[] = []
  const taken = new Set<string>()
  main.forEach((fork) => outs(fork.id).slice(1).forEach((first) => {
    if (mainIdx.has(first.id)) {           // a line that only skips main steps
      raws.push({ fork, steps: [], rejoin: first, id: '', note: '' })
      return
    }
    const steps: StepNode[] = []
    let rejoin: StepNode | null = null
    const walk = (n: StepNode) => {
      if (taken.has(n.id)) return
      taken.add(n.id); steps.push(n)
      outs(n.id).forEach((m) => {
        if (mainIdx.has(m.id)) {
          if (!rejoin || mainIdx.get(m.id)! < mainIdx.get(rejoin.id)!) rejoin = m
        } else walk(m)
      })
    }
    walk(first)
    raws.push({ fork, steps, rejoin, id: '', note: '' })
  }))
  nodes.forEach((n) => {
    if (!mainIdx.has(n.id) && !taken.has(n.id)) errors.push(`${nameOf(n)} is not connected to the flow.`)
  })
  raws.forEach((b) => {
    if (b.rejoin && mainIdx.get(b.rejoin.id)! <= mainIdx.get(b.fork.id)!) {
      errors.push(`A branch from ${nameOf(b.fork)} loops back to an earlier step.`)
    }
  })
  if (errors.length) return res

  // Journey order: the main path, each branch's steps just before it rejoins.
  const before = new Map<string, Raw[]>()
  const tail: Raw[] = []
  raws.forEach((b, i) => {
    b.id = `B${pad(i + 1)}`
    if (b.rejoin) before.set(b.rejoin.id, [...(before.get(b.rejoin.id) ?? []), b])
    else tail.push(b)
  })
  const ordered: [StepNode, Raw | null][] = []
  main.forEach((n) => {
    (before.get(n.id) ?? []).forEach((b) => b.steps.forEach((s) => ordered.push([s, b])))
    ordered.push([n, null])
  })
  tail.forEach((b) => b.steps.forEach((s) => ordered.push([s, b])))
  ordered.forEach(([n], i) => { res.order[n.id] = `J${pad(i + 1)}` })
  const J = (n: StepNode) => res.order[n.id]

  res.branches = raws.map((b) => {
    const a = mainIdx.get(b.fork.id)!
    const z = b.rejoin ? mainIdx.get(b.rejoin.id)! : main.length
    const skipped = main.slice(a + 1, z).map(J)
    b.note = `leaves the main path after ${J(b.fork)}`
      + (skipped.length ? `; replaces ${skipped.join(', ')}` : '; extra step')
      + (b.rejoin ? `; rejoins at ${J(b.rejoin)}` : '; ends the journey')
    const key = `${b.fork.id}>${b.steps[0] ? b.steps[0].id : b.rejoin!.id}`
    return {
      id: b.id, key,
      title: branchTitles[key] || (b.steps.length
        ? `Alternative via ${b.steps.map(nameOf).join(', ')}`
        : `Skip ${skipped.join(', ')}`),
      text: `${b.note.charAt(0).toUpperCase()}${b.note.slice(1)}.`,
      steps: b.steps.map(J),
    }
  })
  ordered.forEach(([n, b]) => {
    res.kind[n.id] = b ? 'alt' : 'main'
    if (!n.endState.trim()) errors.push(`${J(n)} (${nameOf(n)}) needs an end state.`)
    res.journey.push({
      id: J(n), ref: n.ref, source_tc: n.tc, end_state: n.endState.trim(),
      note: [n.note.trim(), b ? b.note : ''].filter(Boolean).join('; ') || null,
      branch: b ? b.id : null,
    })
  })

  // Every way through the drawing is a possible flow.
  const walkAll = (n: StepNode, path: string[]) => {
    if (res.paths.length >= MAX_PATHS) return
    const next = outs(n.id).filter((m) => !path.includes(J(m)))
    if (!next.length) res.paths.push(path)
    else next.forEach((m) => walkAll(m, [...path, J(m)]))
  }
  walkAll(starts[0], [J(starts[0])])

  if (!meta.title.trim()) errors.push('Give the flow a title.')
  if (!/^[A-Za-z0-9][A-Za-z0-9-]{1,63}$/.test(meta.id.trim())) {
    errors.push('The flow id may use letters, digits and hyphens.')
  }
  return res
}

export type FlowDraft = {
  kind: 'flow-draft'
  id: string
  title: string
  entry_condition: string
  journey: JourneyEntry[]
  branches: { id: string; title: string; text: string }[]
  paths: string[][]
}

export function toDraft(meta: Meta, res: JourneyResult): FlowDraft {
  return {
    kind: 'flow-draft', id: meta.id.trim(), title: meta.title.trim(),
    entry_condition: meta.entry.trim(), journey: res.journey,
    branches: res.branches.map(({ id, title, text }) => ({ id, title, text })),
    paths: res.paths,
  }
}

export type ExistingFlow = {
  id: string
  title: string | null
  entry_condition: string | null
  journey: {
    id: string; end_state: string | null; note: string | null; ac_ref: string | null
    source_tc?: string | null
    branch: { id: string; title: string | null } | null
  }[]
}

const COL = 300, MAIN_Y = 60, ALT_Y = 330

/* Lay an existing journey out on the canvas. The journey list does not record
 * where a branch leaves and rejoins, so that wiring is a best guess:
 * consecutive entries on one branch hang between the main steps around them. */
export function layoutFlow(flow: ExistingFlow): {
  nodes: StepNode[]; edges: StepEdge[]; branchTitles: Record<string, string>
} {
  const nodes: StepNode[] = []
  const edges: StepEdge[] = []
  const branchTitles: Record<string, string> = {}
  let prevMain: string | null = null
  let groups: { branch: string; last: string }[] = []
  let open: { branch: string; last: string } | null = null
  flow.journey.forEach((j, i) => {
    if (!j.ac_ref) return
    const id = `n${i + 1}`
    const b = j.branch?.id ?? null
    nodes.push({ id, tc: j.source_tc ?? null, ref: j.ac_ref, x: 40 + nodes.length * COL, y: b ? ALT_Y : MAIN_Y,
                 endState: j.end_state ?? '', note: j.note ?? '' })
    if (b) {
      if (open && open.branch === b) { edges.push({ from: open.last, to: id }); open.last = id }
      else {
        open = { branch: b, last: id }; groups.push(open)
        if (prevMain) edges.push({ from: prevMain, to: id })
        branchTitles[`${prevMain ?? ''}>${id}`] = j.branch?.title ?? ''
      }
    } else {
      if (prevMain) edges.push({ from: prevMain, to: id })
      groups.forEach((g) => edges.push({ from: g.last, to: id }))
      groups = []; open = null; prevMain = id
    }
  })
  return { nodes, edges, branchTitles }
}

/* Line the steps up left to right in journey order: main path on top. */
export function tidy(nodes: StepNode[], res: JourneyResult): StepNode[] {
  const rank = (n: StepNode) => res.order[n.id] ?? 'Z'
  return [...nodes].sort((a, b) => rank(a).localeCompare(rank(b)))
    .map((n, i) => ({ ...n, x: 40 + i * COL, y: res.kind[n.id] === 'alt' ? ALT_Y : MAIN_Y }))
}
