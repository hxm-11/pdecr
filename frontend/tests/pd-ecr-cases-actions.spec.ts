import { readFile } from "node:fs/promises"
import { expect, test } from "@playwright/test"

test.use({ storageState: { cookies: [], origins: [] } })

const storedResult = {
  source: "history",
  relatedCases: ["LL-0001", "LL-0002", "LL-0003"],
  caseRows: [
    {
      id: "LL-0001",
      createDate: "2026-06-01",
      productClass: "Dnox",
      from: "Knowledge Base",
      initiator: "Fan",
      customer: "Dnox",
      project: "JIM-493",
      partNumber: "F01ZH003G1-00",
      reasonForChange: "Supplier switch case.",
      changeType: "Supplier change",
      sampleType: "A sample",
      dept: "Development",
      link: "Open modules",
      similarity: 91,
    },
    {
      id: "LL-0002",
      createDate: "2026-06-02",
      productClass: "JIM",
      from: "Knowledge Base",
      initiator: "Fan",
      customer: "JIM",
      project: "JIM-493",
      partNumber: "F01ZH003G1-01",
      reasonForChange: "Design optimization.",
      changeType: "Design optimization",
      sampleType: "B sample",
      dept: "Quality",
      link: "Open modules",
      similarity: 82,
    },
    {
      id: "LL-0003",
      createDate: "2026-06-03",
      productClass: "HDP",
      from: "Knowledge Base",
      initiator: "Fan",
      customer: "HDP",
      project: "JIM-493",
      partNumber: "F01ZH003G1-02",
      reasonForChange: "Validation update.",
      changeType: "Validation update",
      sampleType: "C sample",
      dept: "MFE",
      link: "Open modules",
      similarity: 74,
    },
  ],
  modules: [
    {
      id: "change-description",
      title: "Change Description",
      subtitle: "Historical change description",
      summary: "Describe the historical change.",
      data: { Summary: "Supplier switch case." },
    },
    {
      id: "impact-analysis",
      title: "Impact Analysis",
      subtitle: "Historical impact analysis",
      summary: "Analyze product and process impact.",
      data: { Risk: "No material property change." },
    },
    {
      id: "validation-plan",
      title: "Validation Plan",
      subtitle: "Historical validation plan",
      summary: "Define validation tasks.",
      data: { Plan: "Run trial and validation." },
    },
    {
      id: "implementation-plan",
      title: "Implementation & Validation",
      subtitle: "Historical implementation and validation",
      summary: "Track implementation actions.",
      data: { Checklist: "Update BOM and supplier documents." },
    },
  ],
}

test.beforeEach(async ({ page }) => {
  await page.addInitScript((result) => {
    localStorage.setItem("access_token", "playwright-test-token")
    localStorage.setItem("pd-ecr-history-result", JSON.stringify(result))
    localStorage.setItem("pd-ecr-active-result", JSON.stringify(result))
    Object.defineProperty(navigator, "share", {
      configurable: true,
      value: async () => undefined,
    })
    Object.defineProperty(navigator, "clipboard", {
      configurable: true,
      value: {
        writeText: async (text: string) => {
          localStorage.setItem("pd-ecr-shared-text", text)
        },
      },
    })
  }, storedResult)

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

  await page.route("**/api/v1/pd-ecr/cases", async (route) => {
    await route.fulfill({ json: { cases: storedResult.caseRows } })
  })

  await page.route("**/api/v1/pd-ecr/cases/LL-0001", async (route) => {
    await route.fulfill({
      json: {
        case: { id: "LL-0001", case_no: "LL-0001" },
        modules: storedResult.modules.map((module) => ({
          module_id: module.id,
          title: module.title,
          content_md: module.summary,
          content_json: module.data,
          source_cases: ["LL-0001"],
          source_files: ["LL-0001.md"],
          status: "draft",
          version: 1,
        })),
      },
    })
  })
})

test("filters case rows only after Run and Show all resets the list", async ({
  page,
}) => {
  await page.goto("/pd-ecr/cases")

  await expect(page.getByRole("columnheader", { name: "Status flow" })).toBeVisible()
  await expect(page.getByText("Next: Generate AI draft").first()).toBeVisible()
  await page.getByLabel("Filter similar cases").fill("Dnox")
  await expect(page.getByText("LL-0001")).toBeVisible()

  await page.getByRole("button", { name: "Run" }).click()
  await expect(page.getByText("LL-0001")).toBeVisible()
  await expect(page.getByText("LL-0002")).not.toBeVisible()

  await page.getByRole("button", { name: "Show all" }).click()
  await expect(page.getByLabel("Filter similar cases")).toHaveValue("")
  await expect(page.getByText("LL-0001")).toBeVisible()
  await expect(page.getByText("LL-0002")).toBeVisible()
})

test("uses side filters, row selection, and action buttons", async ({
  page,
}) => {
  await page.goto("/pd-ecr/cases")

  await page.getByRole("button", { name: "Customer", exact: true }).click()
  await expect(page.getByLabel("Search field")).toHaveValue("customer")
  await expect(page.getByLabel("Filter similar cases")).toHaveAttribute(
    "placeholder",
    /customer/i,
  )

  await page.getByLabel("Select LL-0001").check()
  await expect(page.getByText("1 selected: LL-0001")).toBeVisible()

  await page.getByRole("button", { name: "Share PD-ECR" }).click()
  await expect(page.getByRole("status")).toContainText(/Shared|Copied/)

  await page.getByRole("button", { name: "Print one page" }).click()
  await expect(page.getByRole("status")).toContainText("Print preview opened")

  await page.getByRole("button", { name: "Edit PD-ECR" }).click()
  await expect(page).toHaveURL(/\/pd-ecr\/content$/)
})

test("exports the visible list and one-page report", async ({ page }) => {
  await page.goto("/pd-ecr/cases")

  const csvDownload = page.waitForEvent("download")
  await page.getByRole("button", { name: "Export list" }).click()
  const csv = await csvDownload
  expect(csv.suggestedFilename()).toBe("pd-ecr-cases.csv")

  await page.getByLabel("Select LL-0001").check()
  const htmlDownload = page.waitForEvent("download")
  await page.getByRole("button", { name: "Export PD-ECR one page" }).click()
  const html = await htmlDownload
  expect(html.suggestedFilename()).toBe("pd-ecr-one-page.html")
  const htmlPath = await html.path()
  expect(htmlPath).toBeTruthy()
  const content = await readFile(htmlPath!, "utf-8")
  expect(content).toContain("PD-ECR One Page Package")
  expect(content).toContain("Change Request description")
  expect(content).toContain("Impact analysis")
  expect(content).toContain("Validation &amp;trial run plan")
  expect(content).toContain("Implementation &amp; Validation")
  expect(content).toContain("Supplier switch case.")
  expect(content).toContain("Update BOM and supplier documents.")
})

test("disables row actions until selection and exposes a bulk toolbar", async ({
  page,
}) => {
  await page.goto("/pd-ecr/cases")

  await expect(page.getByRole("button", { name: "Edit PD-ECR" })).toBeDisabled()
  await expect(
    page.getByRole("button", { name: "Share PD-ECR" }),
  ).toBeDisabled()
  await expect(
    page.getByRole("button", { name: "Print one page" }),
  ).toBeDisabled()

  await page.getByLabel("Select LL-0001").check()

  await expect(page.getByText("Bulk actions")).toBeVisible()
  await expect(
    page.getByRole("button", { name: "Clear selection" }),
  ).toBeVisible()
  await expect(page.getByRole("button", { name: "Edit PD-ECR" })).toBeEnabled()
})

test("sorts rows and displays applied filter chips", async ({ page }) => {
  await page.goto("/pd-ecr/cases")

  await page.getByRole("button", { name: "Sort by customer" }).click()
  await expect(page.getByTestId("case-row").first()).toContainText("Dnox")

  await page.getByRole("button", { name: "Customer", exact: true }).click()
  await page.getByLabel("Filter similar cases").fill("HDP")
  await page.getByRole("button", { name: "Run" }).click()

  await expect(page.getByText("Customer: HDP")).toBeVisible()
  await expect(page.getByText("LL-0003")).toBeVisible()
  await expect(page.getByText("LL-0001")).not.toBeVisible()

  await page.getByRole("button", { name: "Clear filter" }).click()
  await expect(page.getByText("LL-0001")).toBeVisible()
})
