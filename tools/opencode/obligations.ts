import { readFile, readdir } from "node:fs/promises"
import { createHash } from "node:crypto"
import { join } from "node:path"

export type Obligation = { id: string; scope: string; text: string }

const RENDER_RE = /render_(?:sit|[a-z_]*uat)[^\n]*/
const RENDERED_N_RE = /^rendered (\d+)/m
const STORY_ARG_RE = /--story\s+(\S+)/

function sha256(buf: Buffer): string {
  return "sha256:" + createHash("sha256").update(buf).digest("hex")
}

/**
 * Session-scoped obligation tracker.
 *
 * Memory records that an obligation was INCURRED. Whether it has been
 * DISCHARGED is always re-checked against disk -- a remembered `seal` that
 * silently failed must not clear anything. When disk cannot be read the
 * obligation stands, because the safe default is to keep telling the model.
 */
export function createTracker(root: string) {
  let sealOwedBy: string | null = null

  async function sealDischarged(): Promise<boolean> {
    try {
      const manifest = JSON.parse(
        await readFile(join(root, "manifest.json"), "utf8"),
      ) as { tc_hashes?: Record<string, string> }
      const hashes = manifest.tc_hashes ?? {}
      for (const [rel, want] of Object.entries(hashes)) {
        const buf = await readFile(join(root, rel + ".md"))
        if (sha256(buf) !== want) return false
      }
      return true
    } catch {
      return false
    }
  }

  // Hoisted out of the returned object so `blocks()` never needs `this` --
  // a caller that destructures (`const { blocks } = createTracker(root)`,
  // the natural way to wire this into opencode hook callbacks) must not
  // throw in strict ESM just because `this` is unbound.
  async function openObligations(): Promise<Obligation[]> {
    if (sealOwedBy === null) return []
    if (await sealDischarged()) {
      sealOwedBy = null
      return []
    }
    return [{
      id: "seal",
      scope: sealOwedBy,
      text: `${sealOwedBy}: rendered test cases are NOT sealed. ` +
            `Run \`py tools/wiki.py seal\` before compiling or exporting anything.`,
    }]
  }

  return {
    note(command: string, output: string): void {
      if (!RENDER_RE.test(command)) return
      const m = RENDERED_N_RE.exec(output)
      if (!m || Number(m[1]) === 0) return
      sealOwedBy = STORY_ARG_RE.exec(command)?.[1] ?? "the last render"
    },

    async open(): Promise<Obligation[]> {
      return openObligations()
    },

    async blocks(command: string): Promise<string | null> {
      const open = await openObligations()
      const seal = open.find((o) => o.id === "seal")
      if (!seal) return null
      if (/wiki\.py\s+seal/.test(command)) return null

      if (/suite\s+compile|wiki\.py\s+export|wiki\.py\s+dashboard/.test(command)) {
        return `Blocked: ${seal.scope} has unsealed test cases. ` +
               `Run \`py tools/wiki.py seal\` first.`
      }
      const other = STORY_ARG_RE.exec(command)?.[1]
      if (other && other !== seal.scope && RENDER_RE.test(command)) {
        return `Blocked: finish ${seal.scope} before switching to ${other} -- ` +
               `its rendered test cases are unsealed. Run \`py tools/wiki.py seal\`.`
      }
      return null
    },

    async checkAssertedResolution(path: string): Promise<string | null> {
      const p = path.replace(/\\/g, "/")
      if (!/(^|\/)resolutions\/[^/]+\.md$/.test(p)) return null
      try {
        const rel = p.slice(p.indexOf("resolutions/"))
        const text = await readFile(join(root, rel), "utf8")
        if (!/^status:\s*asserted\s*$/m.test(text)) return null
        return "Blocked: asserted Resolutions are append-only. Write a NEW " +
               "resolution with `supersedes:` pointing at this one, and set " +
               "`superseded_by:` on it in the same commit (lint L9)."
      } catch {
        return null
      }
    },
  }
}
