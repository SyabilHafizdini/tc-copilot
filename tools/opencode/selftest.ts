/**
 * Drives every hook with a faked PluginInput. Proves the wiring without
 * running opencode headlessly, and fails loudly if a hook signature moves in a
 * future @opencode-ai/plugin release.
 *
 * Run: bun tools/opencode/selftest.ts
 */
import { readdir, readFile } from "node:fs/promises"
import { join } from "node:path"
import { TcCopilotPlugin } from "../../.opencode/plugins/tc-copilot"

const ROOT = join(import.meta.dir, "..", "..")
let failures = 0

function ok(label: string, cond: boolean) {
  console.log(`[${cond ? "PASS" : "FAIL"}] ${label}`)
  if (!cond) failures++
}

function skip(label: string, why: string) {
  console.log(`[SKIP] ${label} (${why})`)
}

/** The first `status: asserted` resolution this bundle has, or null.
 *  Discovered rather than named: the append-only guard is a platform
 *  property, but exercising it needs a project to have asserted something. */
async function anAssertedResolution(): Promise<string | null> {
  const dir = join(ROOT, "resolutions")
  let names: string[]
  try {
    names = (await readdir(dir)).filter((f) => f.endsWith(".md") && f !== "index.md")
  } catch {
    return null
  }
  for (const f of names.sort()) {
    if (/^status:\s*asserted\s*$/m.test(await readFile(join(dir, f), "utf8"))) {
      return `resolutions/${f}`
    }
  }
  return null
}

const ASSERTED_RESOLUTION = await anAssertedResolution()

const hooks = (await TcCopilotPlugin({ directory: ROOT } as never)) as Record<
  string,
  // deno-lint-ignore no-explicit-any
  any
>

ok("hooks registered inside a wiki", Object.keys(hooks).length === 4)

const inert = (await TcCopilotPlugin({
  directory: join(ROOT, "nope"),
} as never)) as Record<string, unknown>
ok("inert outside a wiki", Object.keys(inert).length === 0)

const system: string[] = []
await hooks["experimental.chat.system.transform"]({}, { system })
ok("system block injected", system.length === 1 && system[0]!.includes("tc-copilot"))

let threw = false
try {
  await hooks["tool.execute.before"](
    { tool: "edit", sessionID: "s", callID: "c1" },
    { args: { filePath: "manifest.json" } },
  )
} catch {
  threw = true
}
ok("blocks a manifest.json edit", threw)

threw = false
try {
  await hooks["tool.execute.before"](
    { tool: "edit", sessionID: "s", callID: "c2" },
    { args: { filePath: "tools/sit_specs/US-VHLD.yaml" } },
  )
} catch {
  threw = true
}
ok("allows a spec edit", !threw)

if (ASSERTED_RESOLUTION === null) {
  skip("reading an asserted resolution is allowed (C1 regression guard)",
       "bundle has no asserted resolution")
  skip("editing an asserted resolution is blocked",
       "bundle has no asserted resolution")
} else {
  threw = false
  try {
    await hooks["tool.execute.before"](
      { tool: "read", sessionID: "s", callID: "c4" },
      { args: { filePath: ASSERTED_RESOLUTION } },
    )
  } catch {
    threw = true
  }
  ok("reading an asserted resolution is allowed (C1 regression guard)", !threw)

  threw = false
  try {
    await hooks["tool.execute.before"](
      { tool: "edit", sessionID: "s", callID: "c5" },
      { args: { filePath: ASSERTED_RESOLUTION } },
    )
  } catch {
    threw = true
  }
  ok("editing an asserted resolution is blocked", threw)
}

await hooks["tool.execute.after"](
  { tool: "bash", sessionID: "s", callID: "c3" },
  { title: "t", output: "rendered 0, untouched 31", metadata: {} },
)
ok("after-hook tolerates an unknown callID", true)

await hooks["event"]({ event: { type: "file.edited" } })
ok("event hook tolerates file.edited", true)

console.log(failures === 0 ? "SELFTEST OK" : `SELFTEST FAILED (${failures})`)
process.exit(failures === 0 ? 0 : 1)
