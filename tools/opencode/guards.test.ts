import { describe, expect, test } from "bun:test"
import { check } from "./guards"

describe("blocked", () => {
  test("editing a generated test case", () => {
    const m = check("edit", { filePath: "testcases/sit/production-monitoring/1.1.3.1.1-AC01-01.md" })
    expect(m).toContain("tools/sit_specs")
  })

  test("writing manifest.json", () => {
    expect(check("write", { filePath: "manifest.json" })).toContain("wiki.py manifest")
  })

  test("editing a verbatim PRD source", () => {
    expect(check("edit", { filePath: "sources/prd/4-1-1-1.md" })).toContain("tc-change-report")
  })

  test("editing a generated index file names wiki.py index, not sit_specs", () => {
    const m = check("edit", { filePath: "testcases/sit/index.md" })
    expect(m).not.toBeNull()
    expect(m).toContain("wiki.py index")
  })

  test("the coverage override flag", () => {
    const m = check("bash", { command: "py tools/render_sit.py --story US-VHLD --allow-unconfirmed-coverage" })
    expect(m).toContain("not a substitute")
  })

  test("the UAT coverage override flag (worse than SIT: the map IS the test content)", () => {
    const m = check("bash", { command: "py tools/render_production_monitoring_uat.py --allow-unconfirmed-coverage" })
    expect(m).toContain("not a substitute")
  })

  test("editing a generated UAT test case names the UAT renderer, not sit_specs", () => {
    const m = check("edit", { filePath: "testcases/uat/production-monitoring/UAT-01.md" })
    expect(m).not.toBeNull()
    expect(m).toContain("render_production_monitoring_uat")
  })

  test("editing a generated SIT test case still names tools/sit_specs", () => {
    const m = check("edit", { filePath: "testcases/sit/production-monitoring/1.1.3.1.1-AC01-01.md" })
    expect(m).toContain("tools/sit_specs")
  })

  test("a differently-named root still normalises and blocks (worktree/clone safety)", () => {
    const m = check(
      "edit",
      { filePath: "C:/work/some-other-name/manifest.json" },
      "C:/work/some-other-name",
    )
    expect(m).toContain("wiki.py manifest")
  })

  test("windows-style backslash paths are caught too", () => {
    expect(check("write", { filePath: "testcases\\sit\\x\\TC-01.md" })).not.toBeNull()
  })

  test("absolute paths are caught too", () => {
    expect(check("edit", { filePath: "C:/path/to/tc-copilot/manifest.json" })).not.toBeNull()
  })
})

describe("allowed - false positives are the dangerous failure", () => {
  const ok: Array<[string, unknown]> = [
    ["edit", { filePath: "tools/sit_specs/US-VHLD.yaml" }],
    ["edit", { filePath: "stories/US-VHLD.md" }],
    ["edit", { filePath: "glossary/serviceability.md" }],
    ["write", { filePath: "resolutions/R-VHLD-06.md" }],
    ["edit", { filePath: "docs/superpowers/plans/x.md" }],
    ["edit", { filePath: "tools/wiki.py" }],
    ["bash", { command: "py tools/render_sit.py --story US-VHLD" }],
    ["bash", { command: "py tools/render_sit.py --story US-VHLD --force" }],
    ["bash", { command: "py tools/wiki.py seal" }],
    ["bash", { command: "py tools/wiki.py next --brief" }],
    ["bash", { command: "grep -rn allow-unconfirmed-coverage docs/" }],
    ["read", { filePath: "testcases/sit/production-monitoring/TC-01.md" }],
    ["grep", { pattern: "manifest.json" }],
    ["bash", { command: "py tools/render_sit.py --story US-VHLD --force  # do not add --allow-unconfirmed-coverage" }],
    ["bash", { command: "py tools/render_sit.py --story US-VHLD # --allow-unconfirmed-coverage is forbidden" }],
  ]
  for (const [tool, args] of ok) {
    test(`${tool} ${JSON.stringify(args)}`, () => {
      expect(check(tool, args)).toBeNull()
    })
  }
})

describe("robustness", () => {
  test("null args never throw", () => { expect(check("edit", null)).toBeNull() })
  test("missing filePath never throws", () => { expect(check("edit", {})).toBeNull() })
  test("unknown tool is allowed", () => {
    expect(check("mystery", { filePath: "manifest.json" })).toBeNull()
  })
})
