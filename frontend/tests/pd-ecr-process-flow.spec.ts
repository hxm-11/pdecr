import { expect, test } from "@playwright/test"

test.use({ storageState: { cookies: [], origins: [] } })

const storedResult = {
  source: "generated",
  relatedCases: [],
  modules: [
    {
      id: "change-description",
      title: "Change Description",
      subtitle: "Generated change description",
      summary: "Describe the change request.",
      data: { Summary: "Supplier change request." },
    },
    {
      id: "impact-analysis",
      title: "Impact Analysis",
      subtitle: "Generated impact analysis",
      summary: "Analyze product and process impact.",
      data: { Summary: "No material property change." },
    },
    {
      id: "validation-plan",
      title: "Validation Plan",
      subtitle: "Generated validation plan",
      summary: "Define validation and trial run plan.",
      data: { Summary: "Run validation before approval." },
    },
    {
      id: "execution-checklist",
      title: "Execution Checklist",
      subtitle: "Generated execution checklist",
      summary: "Track implementation actions.",
      data: { Summary: "Update BOM and supplier documents." },
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
    localStorage.setItem("pd-ecr-generated-result", JSON.stringify(result))
    localStorage.setItem("pd-ecr-active-result", JSON.stringify(result))
  }, storedResult)
})

test("shows the PD-ECR process flow from every PD-ECR page", async ({
  page,
}) => {
  await page.goto("/pd-ecr")

  await page.getByRole("button", { name: /Process flow/ }).click()
  await expect(
    page.getByRole("heading", { name: "Process flow chart" }),
  ).toBeVisible()
  await expect(page.getByText("Main UI")).toBeVisible()
  await expect(page.getByText("2nd approval")).toBeVisible()
  await page.getByRole("button", { name: "Close" }).first().click()

  await page.goto("/pd-ecr/content")
  await page.getByRole("button", { name: /Process flow/ }).click()
  await expect(
    page.getByRole("heading", { name: "Process flow chart" }),
  ).toBeVisible()
  await page.getByRole("button", { name: "Close" }).first().click()

  await page.goto("/pd-ecr/content/validation-plan")
  await page.getByRole("button", { name: /Process flow/ }).click()
  await expect(
    page.getByRole("heading", { name: "Process flow chart" }),
  ).toBeVisible()
})
