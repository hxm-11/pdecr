import { readFile } from "node:fs/promises"
import { expect, test } from "@playwright/test"

test.use({ storageState: { cookies: [], origins: [] } })

const storedResult = {
  source: "history",
  relatedCases: ["LL-0001", "LL-0002", "LL-0003"],
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
      id: "execution-checklist",
      title: "Execution Checklist",
      subtitle: "Historical execution checklist",
      summary: "Track implementation actions.",
      data: { Checklist: "Update BOM and supplier documents." },
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
    localStorage.setItem("pd-ecr-history-result", JSON.stringify(result))
    localStorage.setItem("pd-ecr-active-result", JSON.stringify(result))
  }, storedResult)
})

test("filters case rows only after Run and Show all resets the list", async ({
  page,
}) => {
  await page.goto("/pd-ecr/cases")

  await page.getByLabel("Filter similar cases").fill("Dnox")
  await expect(page.getByText("LL-0001")).toBeVisible()

  await page.getByRole("button", { name: "Run" }).click()
  await expect(page.getByText("LL-0001")).not.toBeVisible()
  await expect(page.getByText("LL-0002")).toBeVisible()

  await page.getByRole("button", { name: "Show all" }).click()
  await expect(page.getByLabel("Filter similar cases")).toHaveValue("")
  await expect(page.getByText("LL-0001")).toBeVisible()
  await expect(page.getByText("LL-0002")).toBeVisible()
})

test("uses side filters, row selection, and action buttons", async ({
  page,
}) => {
  await page.goto("/pd-ecr/cases")

  await page.getByRole("button", { name: "Customer" }).click()
  await expect(page.getByLabel("Search field")).toHaveValue("customer")
  await expect(page.getByLabel("Filter similar cases")).toHaveAttribute(
    "placeholder",
    /customer/i,
  )

  await page.getByLabel("Select LL-0001").check()
  await expect(page.getByText("1 selected: LL-0001")).toBeVisible()

  await page.getByRole("button", { name: "Edit PD-ECR" }).click()
  await expect(page.getByRole("status")).toContainText("Editing LL-0001")

  await page.getByRole("button", { name: "Share PD-ECR" }).click()
  await expect(page.getByRole("status")).toContainText("Share link prepared")

  await page.getByRole("button", { name: "Print one page" }).click()
  await expect(page.getByRole("status")).toContainText("Print preview prepared")
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
  expect(content).toContain("Change Description")
  expect(content).toContain("Impact Analysis")
  expect(content).toContain("Validation Plan")
  expect(content).toContain("Execution Checklist")
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

  await page.getByRole("button", { name: "Sort by Product class" }).click()
  await expect(page.getByTestId("case-row").first()).toContainText("Dnox")

  await page.getByRole("button", { name: "Product class", exact: true }).click()
  await page.getByLabel("Filter similar cases").fill("HDP")
  await page.getByRole("button", { name: "Run" }).click()

  await expect(page.getByText("Product class: HDP")).toBeVisible()
  await expect(page.getByText("LL-0003")).toBeVisible()
  await expect(page.getByText("LL-0001")).not.toBeVisible()

  await page.getByRole("button", { name: "Clear filter" }).click()
  await expect(page.getByText("LL-0001")).toBeVisible()
})
