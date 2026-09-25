import type { Plugin } from "@opencode-ai/plugin"
import { isWiki } from "../../tools/opencode/detect"
import { check, FILE_TOOLS } from "../../tools/opencode/guards"
import { createTracker } from "../../tools/opencode/obligations"
import { createState } from "../../tools/opencode/state"

/**
 * tc-copilot session support for opencode.
 *
 * NOT an enforcement layer: tool.execute.before does not intercept subagent
 * tool calls (opencode#5894), so every rule here also holds in tools/wiki.py.
 * This exists for TIMING -- telling the model what is true now, and what it
 * still owes, on the turn it matters.
 */
export const TcCopilotPlugin: Plugin = async ({ directory }) => {
  if (!(await isWiki(directory))) return {}

  const tracker = createTracker(directory)
  const state = createState(directory, tracker)
  const pending = new Map<string, string>()

  const MUTATING =
    /tools\/wiki\.py|render_[a-z_]*\.py|git\s+commit/

  return {
    "experimental.chat.system.transform": async (_input, output) => {
      try {
        // Append to the LAST existing system entry rather than push()ing a new
        // one. opencode renders each output.system[] element as a separate
        // system message, and some OpenAI-compatible gateways reject more
        // than one system message with a 400 "System message must be at the
        // beginning" -- which that gateway then mislabels as "context length
        // exceeded". Folding the state block into the existing system
        // message keeps a single leading system message, so the request is
        // accepted.
        const block = await state.getBlock()
        if (output.system.length > 0) {
          output.system[output.system.length - 1] += "\n\n" + block
        } else {
          output.system.push(block)
        }
      } catch {
        /* never break the session */
      }
    },

    "tool.execute.before": async (input, output) => {
      // A throw HERE is the blocking mechanism and must propagate.
      const args = output.args as Record<string, unknown> | undefined

      const guard = check(input.tool, args, directory)
      if (guard) throw new Error(guard)

      // Only file-MUTATING tools may be blocked here. Reading an asserted
      // resolution must stay allowed -- the model is routinely told to write
      // a new resolution with `supersedes:` pointing at the one it just read.
      const filePath = args?.["filePath"] ?? args?.["path"]
      if (FILE_TOOLS.has(input.tool) && typeof filePath === "string") {
        const res = await tracker
          .checkAssertedResolution(filePath)
          .catch(() => null)
        if (res) throw new Error(res)
      }

      const command = args?.["command"]
      if (typeof command === "string") {
        const blocked = await tracker.blocks(command).catch(() => null)
        if (blocked) throw new Error(blocked)
        if (MUTATING.test(command)) pending.set(input.callID, command)
      } else if (typeof filePath === "string") {
        pending.set(input.callID, `edit:${filePath}`)
      }
    },

    "tool.execute.after": async (input, output) => {
      try {
        const command = pending.get(input.callID)
        if (!command) return
        pending.delete(input.callID)
        state.invalidate()
        tracker.note(command, output.output ?? "")
      } catch {
        /* never break the session */
      }
    },

    event: async ({ event }) => {
      try {
        if (event.type === "file.edited") state.invalidate()
      } catch {
        /* never break the session */
      }
    },
  }
}
