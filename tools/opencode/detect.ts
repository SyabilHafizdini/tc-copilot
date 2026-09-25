import { access } from "node:fs/promises"
import { join } from "node:path"

/**
 * A tc-copilot wiki is identified by config.yaml + tools/wiki.py at its root.
 * Returns false rather than throwing for any unreadable path: a detection
 * failure must make the plugin inert, never break the session.
 */
export async function isWiki(dir: string): Promise<boolean> {
  try {
    await Promise.all([
      access(join(dir, "config.yaml")),
      access(join(dir, "tools", "wiki.py")),
    ])
    return true
  } catch {
    return false
  }
}
