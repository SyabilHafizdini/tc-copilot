import type { ActionResult } from '../api'

// The one place CLI output is shown. rc/stdout/stderr are rendered verbatim --
// a non-zero rc is a refusal doing its job, not an error to swallow.
export function Console({ result }: { result: ActionResult }) {
  const ok = result.rc === 0
  return (
    <div className="console">
      <div className="bar">
        <span className="cmd">$ py tools/wiki.py <b>{result.argv.join(' ')}</b></span>
        <span className={`exit ${ok ? 'ok' : 'bad'}`}>exit {result.rc}</span>
      </div>
      <pre>{result.stdout}{result.stderr}</pre>
    </div>
  )
}
