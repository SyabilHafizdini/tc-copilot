/**
 * The blocklist. Pure: no I/O, no opencode imports, so the whole thing is
 * testable without a harness or a wiki.
 *
 * Only cases with EXACTLY ONE correct alternative earn a rule -- every message
 * names it. A false positive strands the model, which is worse than not
 * blocking, so ambiguous cases are deliberately absent.
 *
 * This is a second net under the tools/wiki.py fences, never a replacement:
 * subagent tool calls bypass this hook entirely (opencode#5894).
 */
export const FILE_TOOLS = new Set(["edit", "write", "patch", "multiedit"])

/**
 * Normalise to forward slashes and drop the repo-root prefix.
 *
 * When `root` is given, strip it off directly (case-insensitive, so this
 * works the same on Windows drive-letter paths) -- this is correct in any
 * worktree or clone regardless of directory name. When `root` is absent,
 * fall back to hunting for a directory literally named "tc-copilot", which
 * is what the pure `check(tool, args)` contract (no root, e.g. every
 * existing test) already relies on.
 */
function normalise(p: string, root?: string): string {
  const slashed = p.replace(/\\/g, "/")
  if (root) {
    const slashedRoot = root.replace(/\\/g, "/").replace(/\/+$/, "")
    const prefix = slashedRoot.toLowerCase() + "/"
    if (slashed.toLowerCase().startsWith(prefix)) {
      return slashed.slice(prefix.length)
    }
    return slashed
  }
  const cut = slashed.toLowerCase().indexOf("/tc-copilot/")
  return cut >= 0 ? slashed.slice(cut + "/tc-copilot/".length) : slashed
}

export type GuardRule = {
  readonly id: string
  readonly test: (path: string) => boolean
  readonly message: string
}

export const FILE_RULES: readonly GuardRule[] = [
  {
    id: "generated-tc-index",
    test: (p) => /^testcases\/(?:.*\/)?index\.md$/.test(p),
    message:
      "Blocked: testcases/**/index.md is generated, not edited. Regenerate it " +
      "with `py tools/wiki.py index`.",
  },
  {
    id: "generated-tc-uat",
    test: (p) => /^testcases\/uat\/.*\.md$/.test(p),
    message:
      "Blocked: UAT test cases are generated, not edited. The journey lives " +
      "on the flow, not a spec file -- re-render with " +
      "`py tools/render_production_monitoring_uat.py --force`, then " +
      "`py tools/wiki.py seal`.",
  },
  {
    id: "generated-tc",
    test: (p) => /^testcases\/.*\.md$/.test(p),
    message:
      "Blocked: test cases are generated, not edited. Change the content spec " +
      "at tools/sit_specs/<STORY>.yaml and re-render with " +
      "`py tools/render_sit.py --story <id> --force`, then `py tools/wiki.py seal`.",
  },
  {
    id: "manifest",
    test: (p) => p === "manifest.json",
    message:
      "Blocked: manifest.json is never hand-edited. Run `py tools/wiki.py manifest`.",
  },
  {
    id: "prd-source",
    test: (p) => /^sources\/prd\//.test(p),
    message:
      "Blocked: sources/prd/ holds verbatim PRD transcriptions. A PRD change " +
      "enters through `py tools/wiki.py ingest-prd` and the tc-change-report skill.",
  },
]

const COMMAND_RULES: readonly { id: string; test: RegExp; message: string }[] = [
  {
    id: "coverage-override",
    test: /render_[a-z_]*\.py[^\n|;&#]*--allow-unconfirmed-coverage/,
    message:
      "Blocked: --allow-unconfirmed-coverage is not a substitute for the human " +
      "confirming the coverage card (tc-generate-sit step 2d). Run " +
      "`py tools/wiki.py coverage --story <id> --propose` and present the card.",
  },
]

export function check(tool: string, args: unknown, root?: string): string | null {
  if (!args || typeof args !== "object") return null
  const a = args as Record<string, unknown>

  if (FILE_TOOLS.has(tool)) {
    const raw = a["filePath"] ?? a["path"] ?? a["file"]
    if (typeof raw !== "string" || raw.length === 0) return null
    const p = normalise(raw, root)
    for (const rule of FILE_RULES) if (rule.test(p)) return rule.message
    return null
  }

  if (tool === "bash") {
    const cmd = a["command"]
    if (typeof cmd !== "string") return null
    for (const rule of COMMAND_RULES) if (rule.test.test(cmd)) return rule.message
    return null
  }

  return null
}
