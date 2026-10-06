import { useEffect, useRef } from 'react'
import { hrefFor } from '../shell/routes'
import { confirmDiscard } from '../shell/unsaved'
import { PartEditor } from './PartEditor'
import { RichText } from './richText'
import type { EditableField, PartKey, TcRow } from './types'

const PART_LABEL: Record<PartKey, string> = {
  scenario: 'Scenario', steps: 'Test Steps', data: 'Field / Values', expected: 'Expected Results',
}
const PRIORITIES = ['P1', 'P2', 'P3']

export function ConfidenceTag({ level }: { level: string | null }) {
  if (!level) return null
  return <span className={`conf-tag ${level.toLowerCase()}`}>{level}</span>
}

/* A part that is derived, not authored on the test case: shown muted, with
 * where it is defined, and never with an editor. */
function ReadOnly({ label, text, where }: { label: string; text: string; where: string }) {
  if (!text) return null
  return (
    <div className="tc-field readonly" data-readonly={label}>
      <div className="tc-field-head"><span className="tc-field-label">{label}</span></div>
      <div className="tc-field-text"><RichText text={text} /></div>
      <p className="tc-where">{where}</p>
    </div>
  )
}

/* PHASE 2 SEAM - Confirm. Not built: phase 1 renders nothing here.
 * Phase 2 must be re-specified against `tc-resolve` before anything is put
 * in this slot. A confirmation is not per part and not one click: it is per
 * QUESTION, on an emitted doubts card (`wiki doubts card`), answered with
 * `card_revise` and applied with `wiki doubts answer`, which checks `--by`
 * against the card's `human_response`. `accept` is valid only when the
 * question has a `proposed` answer, and it covers every member part of the
 * question, across test cases. The row carries row.parts[part].level /
 * .state / .question, which is enough to show a part's doubt but not to
 * confirm it. Do not add an editor for a level or a remark: only
 * `wiki doubts answer` may change them. */
function PartActions(_props: { row: TcRow; part: PartKey }) {
  return null
}

/* What the operator must know before saving `field`: a confirmation is tied
 * to the exact text of a part, so editing a confirmed part re-opens it. */
function confirmedNote(row: TcRow, field: EditableField): string | null {
  const hit = (Object.keys(row.parts) as PartKey[]).filter(
    (p) => row.part_fields[p]?.includes(field) && row.parts[p].state === 'closed')
  if (!hit.length) return null
  // `authored` is on a part a confirmation lifted: the level it goes back to.
  const names = hit.map((p) => (row.parts[p].authored
    ? `${PART_LABEL[p]} (authored ${row.parts[p].authored})` : PART_LABEL[p])).join(', ')
  return `Confirmed part: ${names}. A confirmation is tied to the exact text, so saving a change `
    + 'returns the part to its authored level until it is confirmed again.'
}

function PartHead({ row, part }: { row: TcRow; part: PartKey }) {
  const p = row.parts[part]
  return (
    <div className="tc-part-head">
      <h3>{PART_LABEL[part]}</h3>
      <ConfidenceTag level={p.level} />
      {p.remark && <p className="tc-remark"><RichText text={p.remark} /></p>}
      <PartActions row={row} part={part} />
    </div>
  )
}

export function ReviewPanel({ row, onClose, onNavigate, workbookHref }: {
  row: TcRow
  onClose: () => void
  onNavigate?: (dir: -1 | 1) => void
  workbookHref?: string | null
}) {
  const panel = useRef<HTMLElement>(null)
  // Prev, Next and Close replace or unmount every editor in the panel: with
  // unsaved text the operator is asked first, and a "no" leaves all as it is.
  const close = () => { if (confirmDiscard()) onClose() }
  const move = (dir: -1 | 1) => { if (confirmDiscard()) onNavigate?.(dir) }
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      // Typing in an editor must never close the panel or move the row.
      if (e.ctrlKey || e.altKey || e.metaKey || e.shiftKey || e.defaultPrevented) return
      const t = e.target as HTMLElement | null
      if (t && (t.isContentEditable || t.closest?.('input,textarea,select,[contenteditable]'))) return
      // An open editor owns the keyboard wherever focus happens to be.
      if (panel.current?.querySelector('.tc-field-edit')) return
      if (e.key === 'Escape') onClose()
      else if (e.key === 'ArrowUp' && onNavigate) { e.preventDefault(); onNavigate(-1) }
      else if (e.key === 'ArrowDown' && onNavigate) { e.preventDefault(); onNavigate(1) }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onClose, onNavigate])

  const sit = row.level === 'sit'
  const editor = (field: EditableField, label: string, text: string, options?: string[]) => (
    <PartEditor row={row} field={field} label={label} text={text} options={options}
      note={confirmedNote(row, field)} />
  )
  const ac = row.covers[0]?.split('#')[1] ?? null

  return (
    <aside ref={panel} className="tc-panel" aria-label={`Review ${row.display_id}`}>
      <header className="tc-panel-head">
        <span className="id">{row.display_id}</span>
        <ConfidenceTag level={row.confidence || null} />
        {row.status && row.status !== 'active' && <span className="pill attn">{row.status}</span>}
        <span className="tc-panel-nav">
          {onNavigate && <button className="btn ghost" onClick={() => move(-1)} aria-label="Previous test case">Prev</button>}
          {onNavigate && <button className="btn ghost" onClick={() => move(1)} aria-label="Next test case">Next</button>}
          <button className="btn ghost" onClick={close} aria-label="Close review panel">Close</button>
        </span>
      </header>

      {!row.editable.length && (
        <p className="tc-where">
          {row.status && row.status !== 'active'
            ? `This test case is ${row.status}; it is read-only here.`
            : 'No spec entry renders this test case; it is read-only here.'}
        </p>
      )}

      <section className="tc-part">
        {editor('title', 'Title', row.title)}
        {editor('objective', 'Objective', row.objective)}
        {editor('priority', 'Priority', row.priority ?? '', row.priority ? PRIORITIES : ['', ...PRIORITIES])}
        <dl className="tc-meta">
          <dt>Technique</dt><dd>{row.technique ?? '-'}</dd>
          <dt>Covers</dt>
          <dd>{row.story
            ? <a className="row-link" href={hrefFor({ kind: 'story', id: row.story })}>{row.story}{ac ? ` # ${ac}` : ''}</a>
            : '-'}</dd>
        </dl>
      </section>

      <section className="tc-part" data-part="scenario">
        <PartHead row={row} part="scenario" />
        <ReadOnly label="Given / When / Then" text={row.scenario}
          where="Derived from the acceptance criterion's text - change it in the story." />
      </section>

      <section className="tc-part" data-part="steps">
        <PartHead row={row} part="steps" />
        <ReadOnly label="Starts from" text={row.chain}
          where="Set by the flow chain (continue_from) - owned by generation." />
        {editor('steps', 'Test Steps', row.steps)}
      </section>

      <section className="tc-part" data-part="data">
        <PartHead row={row} part="data" />
        {sit
          ? editor('data', 'Field / Values', row.data)
          : <p className="tc-where">A UAT test case carries its values inside the steps - edit Test Steps.</p>}
        {sit
          ? editor('pre_extra', 'Extra precondition', row.pre_extra)
          : <ReadOnly label="Extra precondition" text={row.pre_extra} where="From the flow's journey entry." />}
      </section>

      <section className="tc-part" data-part="expected">
        <PartHead row={row} part="expected" />
        {editor('expected', 'Expected Results', row.expected)}
        <ReadOnly label="Element block" text={row.element_block}
          where="Derived from the story's coverage map - change it on the coverage card." />
      </section>

      <section className="tc-part">
        {sit
          ? editor('post', 'Postcondition', row.post)
          : <ReadOnly label="Postcondition" text={row.post} where="The journey entry's end state - change it in the flow." />}
      </section>

      <footer className="tc-panel-links">
        <a className="row-link" href={hrefFor({ kind: 'explore', path: row.ref })}>Markdown file</a>
        {row.story && <a className="row-link" href={hrefFor({ kind: 'story', id: row.story })}>Story {row.story}</a>}
        {/* undefined: not known (the Workbook page itself, or the inventory is
            not read yet) - nothing is shown. null: read, and in no workbook. */}
        {workbookHref && <a className="row-link" href={workbookHref}>Open in workbook</a>}
        {workbookHref === null && <span className="tc-link-inert">Not in a compiled workbook</span>}
      </footer>
    </aside>
  )
}
