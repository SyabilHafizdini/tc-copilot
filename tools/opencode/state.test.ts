import { describe, expect, test } from "bun:test"
import { join } from "node:path"
import { createTracker } from "./obligations"
import { createState } from "./state"

const ROOT = join(import.meta.dir, "..", "..")

describe("getBlock", () => {
  test("contains the marker, a scope, and the skill routing", async () => {
    const s = createState(ROOT, createTracker(ROOT))
    const block = await s.getBlock()
    expect(block).toContain("tc-copilot")
    expect(block).toContain("skill:")
    // Asserted on shape, not on one project's story id: a populated bundle
    // names its stories/flows here, and an empty one (the base branch) says
    // it is empty. Either is a correct block; naming US-VHLD made this test
    // pass only in the bundle it was written against.
    expect(block).toMatch(/US-[A-Z0-9-]+|FLOW-[a-z0-9-]+|empty bundle/)
  }, 20000)

  test("second call is served from cache and does not call the runner again", async () => {
    let calls = 0
    const runner = () => {
      calls++
      return Promise.resolve<[string, string]>(["fake next output", ""])
    }
    const s = createState(ROOT, createTracker(ROOT), runner)

    await s.getBlock()
    await s.getBlock()
    expect(calls).toBe(1) // cache hit -- runner not called again
  }, 20000)

  test("invalidate forces a recompute", async () => {
    let calls = 0
    const runner = () => {
      calls++
      return Promise.resolve<[string, string]>(["fake next output", ""])
    }
    const s = createState(ROOT, createTracker(ROOT), runner)

    await s.getBlock()
    s.invalidate()
    await s.getBlock()
    expect(calls).toBe(2) // invalidate forced a real recompute, not a no-op
  }, 20000)

  test("degrades to one line outside a wiki and never throws", async () => {
    const bad = join(ROOT, "does-not-exist")
    const s = createState(bad, createTracker(bad))
    const block = await s.getBlock()
    expect(block).toContain("state unavailable")
  }, 20000)

  test("degradation is sticky - the second call does not retry the runner", async () => {
    let calls = 0
    const runner = () => {
      calls++
      return Promise.reject(new Error("boom"))
    }
    const s = createState(ROOT, createTracker(ROOT), runner)

    const a = await s.getBlock()
    const b = await s.getBlock()

    expect(a).toContain("state unavailable")
    expect(b).toContain("state unavailable")
    expect(calls).toBe(1) // must not retry after the first failure
  }, 20000)
})
