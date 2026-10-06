import { Banner, Button, Spinner } from '../ui'
import type { Freshness, WbSource } from './types'

// A source the app can recompile: a suite by name, or an export that recorded
// its story (`wiki export` takes --story only).
export function canRecompile(source: WbSource | null): source is WbSource {
  return !!source && (source.type === 'suite' || !!source.story)
}

export function StaleBanner({ freshness, changedCount, source, busy, refusal, onRecompile }: {
  freshness: Freshness
  changedCount: number
  source: WbSource | null
  busy: boolean
  refusal: string | null
  onRecompile: () => void
}) {
  if (freshness === 'fresh' && !refusal) return null
  const message = freshness === 'changed'
    ? `${changedCount} test case${changedCount === 1 ? '' : 's'} changed since this workbook was compiled`
    : freshness === 'unknown'
      ? 'freshness unknown — recompile to track changes'
      : null
  return (
    <div className="wb-stale">
      {message && (
        <Banner tone="attn">
          {message}{' '}
          {busy
            ? <span className="loading-inline"><Spinner size={14} /> Recompiling…</span>
            : canRecompile(source) && <Button onClick={onRecompile}>Recompile</Button>}
        </Banner>
      )}
      {refusal && (
        <Banner tone="blocked">
          <pre className="wb-refusal">{refusal}</pre>
        </Banner>
      )}
    </div>
  )
}
