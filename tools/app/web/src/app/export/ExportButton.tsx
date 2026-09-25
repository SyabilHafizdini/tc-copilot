import { Button } from '../ui/Button'
import { runDownload } from '../api'

// Export writes to build/inventory/sit/<name>_<ts>.xlsx AND a stable
// <name>-latest.xlsx; we download the stable copy, whose name is deterministic.

type ExportButtonProps =
  | { story: string; flow?: never; name: string }
  | { flow: string; story?: never; name: string }

export function ExportButton(props: ExportButtonProps) {
  const artifact = `sit/${props.name}-latest.xlsx`
  const params = 'story' in props
    ? { story: props.story, name: props.name }
    : { flow: props.flow, name: props.name }
  return (
    <Button variant="primary" onClick={() => { void runDownload(artifact, params) }}>
      Export ↓
    </Button>
  )
}
