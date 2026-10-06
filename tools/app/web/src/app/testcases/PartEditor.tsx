import { useEffect, useId, useRef, useState } from 'react'
import { editTestCase } from '../api'
import { setUnsavedDraft } from '../shell/unsaved'
import { RichText } from './richText'
import type { EditableField, TcRow } from './types'

/* One editable field of a test case: its text, and its own Edit / Save /
 * Cancel. Save runs the `tc_edit` action; a refusal (non-zero exit) is shown
 * verbatim beside the field with the operator's text still in the editor.
 * A field the row does not list in `editable` shows no editor at all. */
export function PartEditor({ row, field, label, text, options, note }: {
  row: TcRow
  field: EditableField
  label: string
  text: string
  options?: string[]          // a closed set (priority): a select, not a textarea
  note?: string | null        // shown while editing, before the save
}) {
  const [editing, setEditing] = useState(false)
  const [draft, setDraft] = useState(text)
  const [saving, setSaving] = useState(false)
  const [refusal, setRefusal] = useState<string | null>(null)
  // The grid reloads a moment after a save; until then keep showing what was
  // saved rather than flashing the old text back.
  // `base` is the prop text at the moment of the save: the saved draft is
  // shown only while the prop still holds that text, so it never flashes the
  // pre-save text and gives way as soon as the prop changes to anything else.
  const [saved, setSaved] = useState<{ value: string; base: string } | null>(null)
  // What the open editor was started from: `prop` is the text the row held,
  // `shown` the text on screen (the just-saved draft, until the reload lands).
  // A prop that is neither of them means the text changed underneath.
  const [opened, setOpened] = useState({ prop: text, shown: text })
  // Bumped when the row or field changes and on unmount, so a save still in
  // flight for the old row is ignored when it resolves.
  const gen = useRef(0)
  const control = useRef<HTMLTextAreaElement & HTMLSelectElement>(null)
  const editButton = useRef<HTMLButtonElement>(null)
  // Set when Save or Cancel closes the editor: focus goes back to Edit, so the
  // keyboard is not dropped on the page body.
  const refocus = useRef(false)
  // A freshly opened editor takes focus, so the keyboard is in the field at once.
  useEffect(() => {
    if (editing) control.current?.focus()
    else if (refocus.current) { refocus.current = false; editButton.current?.focus() }
  }, [editing])
  useEffect(() => {
    // Another test case in the same panel: drop any half-made edit. Whoever
    // changed the row asked first (shell/unsaved).
    setEditing(false); setRefusal(null); setSaving(false); setSaved(null)
    return () => { gen.current += 1 }
  }, [row.id, field])

  const canEdit = row.editable.includes(field)
  const shown = saved && saved.base === text ? saved.value : text
  const changedUnderneath = editing && text !== opened.prop && text !== opened.shown

  // Unsaved text is reported for as long as it exists, and never after the
  // editor is gone.
  const key = useId()
  const unsaved = editing && draft !== opened.shown
  useEffect(() => {
    setUnsavedDraft(key, unsaved)
    return () => setUnsavedDraft(key, false)
  }, [key, unsaved])

  const start = () => {
    setDraft(shown); setOpened({ prop: text, shown }); setRefusal(null); setEditing(true)
  }
  const cancel = () => { refocus.current = true; setEditing(false); setRefusal(null) }
  const save = async () => {
    const mine = gen.current
    setSaving(true)
    setRefusal(null)
    try {
      const res = await editTestCase(row.id, field, draft)
      if (gen.current !== mine) return
      if (res.rc === 0) {
        setSaved({ value: draft, base: text })
        refocus.current = true
        setEditing(false)
      } else {
        setRefusal((res.stdout + res.stderr).trim() || `exit ${res.rc}`)
      }
    } catch (e) {
      if (gen.current !== mine) return
      setRefusal(String(e instanceof Error ? e.message : e))
    } finally {
      if (gen.current === mine) setSaving(false)
    }
  }

  return (
    <div className="tc-field" data-field={field}>
      <div className="tc-field-head">
        <span className="tc-field-label">{label}</span>
        {canEdit && !editing && (
          <button ref={editButton} className="btn ghost" onClick={start} aria-label={`Edit ${label}`}>Edit</button>
        )}
      </div>
      {!editing ? (
        <div className="tc-field-text">
          {shown ? <RichText text={shown} /> : <span className="tc-none">None</span>}
        </div>
      ) : (
        <div className="tc-field-edit">
          {note && <p className="tc-edit-note" role="note">{note}</p>}
          {changedUnderneath && (
            <p className="tc-edit-note" role="status">
              This text changed while you were editing. Saving will replace the newer text.
            </p>
          )}
          {options ? (
            <select ref={control} aria-label={label} value={draft} onChange={(e) => setDraft(e.target.value)}>
              {options.map((o) => <option key={o} value={o}>{o}</option>)}
            </select>
          ) : (
            <textarea
              ref={control} aria-label={label} value={draft} rows={Math.min(18, Math.max(3, draft.split('\n').length + 1))}
              onChange={(e) => setDraft(e.target.value)} />
          )}
          <div className="tc-field-actions">
            <button className="btn primary" onClick={save} disabled={saving}>{saving ? 'Saving...' : 'Save'}</button>
            <button className="btn" onClick={cancel} disabled={saving}>Cancel</button>
          </div>
          {refusal && <pre className="tc-refusal" role="alert">{refusal}</pre>}
        </div>
      )}
    </div>
  )
}
