import { readFile } from "node:fs/promises"
import { expect, test } from "@playwright/test"

test.use({ storageState: { cookies: [], origins: [] } })

const generatedResult = {
  source: "generated",
  draftId: "draft-export-v1",
  draftStatus: "V1_MVP_DRAFT",
  inputSnapshot: {
    dc_no: "PD-ECR-DEMO-001",
    mcr_no: "MCR-DEMO-001",
    customer_project: "JIM-493",
  },
  relatedCases: ["PDECR26-001"],
  modules: [
    {
      id: "change-description",
      title: "Change Request description",
      subtitle: "Content 1 / 6",
      summary: "Generated basic information.",
      data: { content: "DC and MCR request data." },
      sourceCases: ["PDECR26-001"],
      sourceFiles: ["pilot_supplier_change.md"],
      needsHumanInput: false,
      warnings: [],
    },
    {
      id: "impact-analysis",
      title: "Affection analysis",
      subtitle: "Content 2 / 6",
      summary:
        "# Step 3.1 Impact Analysis / 影响分析\n## 1. Basic Information / 基本信息\n| Field / 字段 | Content / 内容 |\n|---|---|\n| Corresponding DC No. / 对应开发更改编号 | PD-ECR-1782202914453 |",
      data: { content: "Generated supplier change description." },
      sourceCases: ["PDECR26-001"],
      sourceFiles: ["pilot_supplier_change.md"],
      needsHumanInput: false,
      warnings: [],
    },
    {
      id: "validation-plan",
      title: "Validation &trial run plan",
      subtitle: "Content 3 / 6",
      summary: "Generated reason summary.",
      data: { content: "RPP cost reduction." },
      sourceCases: ["PDECR26-001"],
      sourceFiles: ["pilot_supplier_change.md"],
      needsHumanInput: false,
      warnings: [],
    },
    {
      id: "validation-result",
      title: "Validation &Trial run plan result",
      subtitle: "Content 4 / 6",
      summary: "Generated impact summary.",
      data: { content: "Assembly and supplier quality impact." },
      sourceCases: ["PDECR26-001"],
      sourceFiles: ["pilot_supplier_change.md"],
      needsHumanInput: false,
      warnings: [],
    },
    {
      id: "implementation-plan",
      title: "Implementation task plan",
      subtitle: "Content 5 / 6",
      summary: "Generated checklist summary.",
      data: { content: "BOM update and supplier document update." },
      sourceCases: ["PDECR26-001"],
      sourceFiles: ["pilot_supplier_change.md"],
      needsHumanInput: false,
      warnings: [],
    },
    {
      id: "implementation-result",
      title: "Implementation result",
      subtitle: "Content 6 / 6",
      summary: "Generated sign-off summary.",
      data: { content: "V1 review only." },
      sourceCases: [],
      sourceFiles: [],
      needsHumanInput: true,
      warnings: ["V1 does not create formal approval."],
    },
  ],
}

test.beforeEach(async ({ page }) => {
  await page.route("**/api/v1/users/me", async (route) => {
    await route.fulfill({
      json: {
        email: "fan.xiaofeng@example.com",
        full_name: "Fan Xiaofeng",
        id: "user-pd-ecr",
        is_active: true,
        is_superuser: false,
      },
    })
  })

  await page.addInitScript((result) => {
    localStorage.setItem("access_token", "playwright-test-token")
    localStorage.setItem("pd-ecr-generated-result", JSON.stringify(result))
    localStorage.setItem("pd-ecr-active-result", JSON.stringify(result))
  }, generatedResult)
})

test("exports generated one-page package with the four MVP modules and sources", async ({
  page,
}) => {
  await page.goto("/pd-ecr/content")

  const downloadPromise = page.waitForEvent("download")
  await page.getByRole("button", { name: "Export official HTML/PDF" }).click()
  const download = await downloadPromise
  const htmlPath = await download.path()
  expect(htmlPath).toBeTruthy()
  const content = await readFile(htmlPath!, "utf-8")

  expect(content).toContain("PD-ECR One Page Package")
  expect(content).toContain("V1_MVP_DRAFT")
  expect(content).toContain("PD-ECR-DEMO-001")
  expect(content).toContain("Change Request description")
  expect(content).toContain("Impact analysis")
  expect(content).not.toContain("Affection analysis")
  expect(content).not.toContain("# Step 3.1")
  expect(content).not.toContain("| Field / 字段 |")
  expect(content).toContain("Validation &amp;trial run plan")
  expect(content).toContain("Implementation &amp; Validation")
  expect(content).toContain("可行性确认")
  expect(content).not.toContain("Validation &amp;Trial run plan result")
  expect(content).not.toContain("Implementation result")
  expect(content).not.toContain("pilot_supplier_change.md")
  expect(content).toContain("PDECR26-001")
  expect(content).toContain("Generated supplier change description.")
  expect(content).toContain("BOM update and supplier document update.")
})

test("impact module hides markdown file names and shows stock delivery checklist", async ({
  page,
}) => {
  await page.goto("/pd-ecr/content/impact-analysis")

  await expect(
    page.getByRole("heading", { name: "Impact analysis" }),
  ).toBeVisible()
  await expect(page.getByText("Affection analysis")).toHaveCount(0)
  await expect(page.getByText("pilot_supplier_change.md")).toHaveCount(0)
  await expect(page.getByText("# Step 3.1")).toHaveCount(0)
  await expect(page.getByText("| Field / 字段 |")).toHaveCount(0)
  await expect(page.getByText("Function & Performance will be influenced?")).toBeVisible()

  await page.getByRole("button", { name: /1\.2\.2Stock/ }).click()
  await expect(page.getByRole("columnheader", { name: /Remark/ }).first()).toBeVisible()
  await expect(
    page.getByText("How to deal with 1st delivery after change?"),
  ).toBeVisible()
  await expect(page.getByText("Finished goods(customer)")).toBeVisible()
})
