import { $ } from "bun"
import type { createTracker } from "./obligations"

const MAX_AGE_MS = 60_000
const TIMEOUT_MS = 10_000
const UNAVAILABLE = "<tc-copilot: state unavailable>"

function withTimeout<T>(p: Promise<T>, ms: number): Promise<T> {
  return Promise.race([
    p,
    new Promise<T>((_, rej) => setTimeout(() => rej(new Error("timeout")), ms)),
  ])
}

// Default shell runner: [nextOutput, gitStatusOutput]. On Windows, `py` is
// commonly installed as a WindowsApps App Execution Alias (a reparse
// point). Bun's own $ / spawn PATH resolver does a raw stat() to find
// candidates, and that stat gets EACCES on these aliases, so Bun reports
// "command not found" even though the alias runs fine through the real OS
// process launcher. Routing through `cmd /c` hands resolution to Windows
// itself, which handles the alias correctly. Verified empirically:
// `$\`py --version\`` fails with "command not found: py" on this class of
// install, while `$\`cmd /c py --version\`` succeeds. `git` is a normal
// PATH binary and is unaffected.
function realRunner(root: string): () => Promise<[string, string]> {
  return () => {
    const nextP = process.platform === "win32"
      ? $`cmd /c py tools/wiki.py next --brief`.cwd(root).text()
      : $`py tools/wiki.py next --brief`.cwd(root).text()
    return Promise.all([
      nextP,
      $`git status --porcelain`.cwd(root).text(),
    ])
  }
}

/**
 * Produces the block pushed into the model's system prompt.
 *
 * Cached because `wiki next` costs ~1-3s and this runs on every turn.
 * Degradation is STICKY: once the shell path fails, stop trying for the rest
 * of the session, or every turn pays the full timeout - worse than no plugin.
 *
 * `runner` is injectable for tests (it returns [nextOutput, gitStatusOutput]);
 * omitted, it defaults to the real `cmd /c py ...` / `git status` shell calls
 * above, so production behavior and every existing call site are unchanged.
 */
export function createState(
  root: string,
  tracker: ReturnType<typeof createTracker>,
  runner: () => Promise<[string, string]> = realRunner(root),
) {
  let cached: string | null = null
  let cachedAt = 0
  let disabled = false

  async function compute(): Promise<string> {
    const [next, dirty] = await withTimeout(runner(), TIMEOUT_MS)
    const lines = [
      "<tc-copilot-state>",
      "Live wiki state. Trust this over your memory of earlier turns.",
      "",
      next.trim(),
    ]
    const changed = dirty.trim()
    if (changed) {
      const n = changed.split("\n").length
      lines.push("", `Working tree: ${n} uncommitted change(s).`)
    }
    lines.push("</tc-copilot-state>")
    return lines.join("\n")
  }

  return {
    invalidate(): void {
      cached = null
    },

    async getBlock(): Promise<string> {
      // Obligations are local-file-only (manifest.json + TC hashes) and
      // unrelated to the shell path this hook otherwise depends on, so they
      // are computed unconditionally, even once `disabled` has latched --
      // a sticky shell failure must not also silence outstanding seal
      // reminders.
      const obligations = await tracker.open().catch(() => [])
      const prefix = obligations.length
        ? "<tc-copilot-obligations>\nYou have unfinished work:\n" +
          obligations.map((o) => `- ${o.text}`).join("\n") +
          "\n</tc-copilot-obligations>\n"
        : ""

      if (disabled) return prefix + UNAVAILABLE

      const fresh = cached !== null && Date.now() - cachedAt < MAX_AGE_MS
      if (fresh) return prefix + cached

      try {
        cached = await compute()
        cachedAt = Date.now()
        return prefix + cached
      } catch {
        disabled = true
        return prefix + UNAVAILABLE
      }
    },
  }
}
