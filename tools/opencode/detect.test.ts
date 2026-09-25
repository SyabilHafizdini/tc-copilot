import { describe, expect, test } from "bun:test"
import { mkdtemp, mkdir, writeFile } from "node:fs/promises"
import { tmpdir } from "node:os"
import { join } from "node:path"
import { isWiki } from "./detect"

async function scratch(): Promise<string> {
  return await mkdtemp(join(tmpdir(), "tc-detect-"))
}

describe("isWiki", () => {
  test("true for the real repo", async () => {
    expect(await isWiki(join(import.meta.dir, "..", ".."))).toBe(true)
  })

  test("false for an empty directory", async () => {
    expect(await isWiki(await scratch())).toBe(false)
  })

  test("false when config.yaml exists but tools/wiki.py does not", async () => {
    const d = await scratch()
    await writeFile(join(d, "config.yaml"), "project: fake\n")
    expect(await isWiki(d)).toBe(false)
  })

  test("false when tools/wiki.py exists but config.yaml does not", async () => {
    const d = await scratch()
    await mkdir(join(d, "tools"), { recursive: true })
    await writeFile(join(d, "tools", "wiki.py"), "# fake\n")
    expect(await isWiki(d)).toBe(false)
  })

  test("never throws on an unreadable path", async () => {
    expect(await isWiki("\u0000/definitely/not/a/path")).toBe(false)
  })
})
