import { useState } from 'react'
import { useInbox } from './useInbox'
import { AlignmentCard } from './AlignmentCard'
import { CoverageCard } from './CoverageCard'
import { runAction } from '../api'
import type { ActionResult } from '../api'
import { Console, Banner, PageSkeleton } from '../ui'

const storyId = (story: string | null) => (story ?? '').split('/').pop() ?? ''

export function cardTitle(card: { card_type: string; story: string | null }): string {
  const label = card.card_type.replace(/[_-]/g, ' ')
  const capLabel = label.charAt(0).toUpperCase() + label.slice(1)
  const story = card.story ? storyId(card.story) : ''
  return story ? `${capLabel} · ${story}` : capLabel
}

export function InboxPage() {
  const { snapshot, error, selected, select } = useInbox()
  const [result, setResult] = useState<ActionResult | { error: string } | null>(null)

  const run = (name: string, params: Record<string, unknown>) =>
    runAction(name, params).then(setResult).catch((e) => setResult({ error: String(e) }))

  if (error && !snapshot) return <div className="page"><Banner tone="blocked">{error}</Banner></div>
  if (!snapshot) return <PageSkeleton />

  const card = snapshot.cards.find((c) => c.file === selected) ?? null

  const lastWasDiscard = !!result && !('error' in result) &&
    result.rc === 0 && result.argv[0] === 'card' && result.argv[1] === 'discard'

  return (
    <div className="inbox">
      <div className="inbox-list">
        {snapshot.cards.length === 0 && <div className="empty">No pending cards.</div>}
        {snapshot.cards.map((c) => (
          <div key={c.file} className={`inbox-item${c.file === selected ? ' selected' : ''}`}
            onClick={() => select(c.file)} style={{ cursor: 'pointer' }}>
            <b>{cardTitle(c)}</b><span>{c.file}</span>
          </div>
        ))}
      </div>
      <div className="inbox-detail">
        {card?.card_type === 'alignment' && (
          <AlignmentCard key={card.file} card={card}
            onAssert={() => run('assert', { id: storyId(card.story), card: card.file })}
            onRevise={({ answers, note }) => run('card_revise', { card: card.file, answers, note })}
            onDiscard={({ note }) => run('card_discard', { card: card.file, note })} />
        )}
        {card?.card_type === 'coverage' && (
          <CoverageCard key={card.file} card={card}
            onAssert={() => run('assert', { id: storyId(card.story), card: card.file })}
            onDiscard={({ note }) => run('card_discard', { card: card.file, note })} />
        )}
        {result && ('error' in result
          ? <Banner tone="blocked">{result.error}</Banner>
          : <Console result={result} />)}
        {lastWasDiscard && card?.session && (
          <button className="btn danger"
            onClick={() => run('session_revert', { session: card.session })}>
            Revert this session&apos;s commits
          </button>
        )}
      </div>
    </div>
  )
}
