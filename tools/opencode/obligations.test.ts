import { describe, expect, test } from "bun:test"
import { mkdir, mkdtemp, readdir, readFile, rm, writeFile } from "node:fs/promises"
import { tmpdir } from "node:os"
import { createHash } from "node:crypto"
import { join } from "node:path"
import { createTracker } from "./obligations"

const ROOT = join(import.meta.dir, "..", "..")

// Fixture content for the mismatch-vs-match tests below. The manifest key
// deliberately has NO ".md" suffix -- sealDischarged() appends ".md" itself.
const FIXTURE_TC_REL = "testcases/sit/x/TC-01"
const FIXTURE_CONTENT = "TC-01 fixture content\n"

function fixtureHash(): string {
  return "sha256:" + createHash("sha256").update(Buffer.from(FIXTURE_CONTENT, "utf8")).digest("hex")
}

async function makeFixtureRoot(recordedHash: string): Promise<string> {
  const dir = await mkdtemp(join(tmpdir(), "obligations-test-"))
  await mkdir(join(dir, "testcases", "sit", "x"), { recursive: true })
  await writeFile(join(dir, FIXTURE_TC_REL + ".md"), FIXTURE_CONTENT)
  await writeFile(
    join(dir, "manifest.json"),
    JSON.stringify({ tc_hashes: { [FIXTURE_TC_REL]: recordedHash } }),
  )
  return dir
}

describe("note", () => {
  test("a render with N>0 opens a seal obligation", async () => {
    // The committed repo's US-VHLD test cases are already sealed (manifest
    // hashes match disk), so a tracker on the real ROOT would legitimately
    // find the obligation discharged on first check -- disk always wins, per
    // the same rule proven below in "discharge is checked against disk".
    // Point this one at an unreadable root so discharge cannot be verified,
    // which is exactly what lets a freshly-noted obligation surface here.
    const t = createTracker(ROOT + "/does-not-exist")
    t.note("py tools/render_sit.py --story US-VHLD --force",
           "rendered 31, untouched 0 (fragments unchanged), suppressed 0 -> testcases/sit/x")
    const open = await t.open()
    expect(open.some((o) => o.id === "seal")).toBe(true)
    expect(open.find((o) => o.id === "seal")!.scope).toBe("US-VHLD")
  })

  test("a render with 0 opens nothing", async () => {
    const t = createTracker(ROOT)
    t.note("py tools/render_sit.py --story US-VHLD",
           "rendered 0, untouched 31 (fragments unchanged), suppressed 0 -> testcases/sit/x")
    expect(await t.open()).toEqual([])
  })

  test("an unrelated command opens nothing", async () => {
    const t = createTracker(ROOT)
    t.note("py tools/wiki.py status", "US-VHLD aligned")
    expect(await t.open()).toEqual([])
  })
})

describe("discharge is checked against disk, not memory", () => {
  test("seal obligation clears when hashes match the manifest", async () => {
    const t = createTracker(ROOT)
    t.note("py tools/render_sit.py --story US-VHLD --force", "rendered 31, ...")
    // The committed repo IS sealed, so disk disagrees with the remembered render.
    // Disk must win.
    expect(await t.open()).toEqual([])
  })
})

describe("discharge distinguishes a real hash mismatch from an unreadable disk", () => {
  test("a readable manifest with the WRONG hash leaves the obligation open", async () => {
    const dir = await makeFixtureRoot("sha256:deadbeef")
    try {
      const t = createTracker(dir)
      t.note("py tools/render_sit.py --story US-VHLD --force", "rendered 31, ...")
      const open = await t.open()
      expect(open.some((o) => o.id === "seal")).toBe(true)
    } finally {
      await rm(dir, { recursive: true, force: true })
    }
  })

  test("a readable manifest with the CORRECT hash discharges the obligation", async () => {
    const dir = await makeFixtureRoot(fixtureHash())
    try {
      const t = createTracker(dir)
      t.note("py tools/render_sit.py --story US-VHLD --force", "rendered 31, ...")
      expect(await t.open()).toEqual([])
    } finally {
      await rm(dir, { recursive: true, force: true })
    }
  })
})

describe("blocks", () => {
  test("suite compile is blocked while a seal is owed", async () => {
    const t = createTracker(ROOT + "/does-not-exist")  // manifest unreadable => cannot verify => obligation stands
    t.note("py tools/render_sit.py --story US-VHLD --force", "rendered 31, ...")
    expect(await t.blocks("py tools/wiki.py suite compile sit-all")).toContain("seal")
  })

  test("seal itself is never blocked", async () => {
    const t = createTracker(ROOT + "/does-not-exist")
    t.note("py tools/render_sit.py --story US-VHLD --force", "rendered 31, ...")
    expect(await t.blocks("py tools/wiki.py seal")).toBeNull()
  })

  test("a different story's render is blocked while a seal is owed", async () => {
    const t = createTracker(ROOT + "/does-not-exist")
    t.note("py tools/render_sit.py --story US-VHLD --force", "rendered 31, ...")
    expect(await t.blocks("py tools/render_sit.py --story US-VDTL")).toContain("US-VHLD")
  })

  test("the SAME story's re-render is allowed", async () => {
    const t = createTracker(ROOT + "/does-not-exist")
    t.note("py tools/render_sit.py --story US-VHLD --force", "rendered 31, ...")
    expect(await t.blocks("py tools/render_sit.py --story US-VHLD --force")).toBeNull()
  })

  test("nothing is blocked with no obligations", async () => {
    const t = createTracker(ROOT)
    expect(await t.blocks("py tools/wiki.py suite compile sit-all")).toBeNull()
  })

  test("blocks() works after destructuring (no this-binding dependency)", async () => {
    const { note, blocks } = createTracker(ROOT + "/does-not-exist")
    note("py tools/render_sit.py --story US-VHLD --force", "rendered 31, ...")
    expect(await blocks("py tools/wiki.py suite compile sit-all")).toContain("seal")
  })
})

describe("checkAssertedResolution", () => {
  /** The first `status: asserted` resolution this bundle has, or null.
   *  Discovered rather than named so the check holds for any project; a
   *  bundle with none (the base branch, or a project before its first
   *  assertion) simply has nothing to assert on. */
  const anAssertedResolution = async (): Promise<string | null> => {
    const dir = join(ROOT, "resolutions")
    let names: string[]
    try {
      names = (await readdir(dir)).filter((f) => f.endsWith(".md") && f !== "index.md")
    } catch {
      return null
    }
    for (const f of names.sort()) {
      const text = await readFile(join(dir, f), "utf8")
      if (/^status:\s*asserted\s*$/m.test(text)) return `resolutions/${f}`
    }
    return null
  }

  test("blocks editing an asserted resolution", async () => {
    const rel = await anAssertedResolution()
    if (rel === null) return // no asserted resolution in this bundle
    const t = createTracker(ROOT)
    const m = await t.checkAssertedResolution(rel)
    expect(m).toContain("supersedes")
  })

  test("allows a path that is not a resolution", async () => {
    const t = createTracker(ROOT)
    expect(await t.checkAssertedResolution("stories/US-VHLD.md")).toBeNull()
  })

  test("allows a resolution that does not exist yet", async () => {
    const t = createTracker(ROOT)
    expect(await t.checkAssertedResolution("resolutions/R-NEW-99.md")).toBeNull()
  })
})
