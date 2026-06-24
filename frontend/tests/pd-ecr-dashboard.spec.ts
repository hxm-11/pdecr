import { expect, test } from "@playwright/test"

test.use({ storageState: { cookies: [], origins: [] } })

test.beforeEach(async ({ page }) => {
  await page.addInitScript(() => {
    localStorage.setItem("access_token", "playwright-test-token")
  })

  await page.route("**/api/v1/users/me", async (route) => {
    await route.fulfill({
      json: {
        email: "fan.xiaofeng@example.com",
        full_name: "Fan Xiaofeng",
        id: "user-pd-ecr-dashboard",
        is_active: true,
        is_superuser: false,
      },
    })
  })

  await page.route("**/api/v1/pd-ecr/cases", async (route) => {
    await route.fulfill({
      json: {
        total: 3,
        cases: [
          {
            id: "PDECR25_084",
            case_id: "PDECR25_084",
            case_no: "PDECR25_084",
            title: "压差支架取消卡夹",
            dc_no: "25_084",
            customer_project: "JIM-493",
            change_type: "Customer request",
            source_type: "historical",
            is_historical: true,
            create_date: "2025-07-02",
            source_file: "PDECR25_084_JIM_493.pdf",
          },
          {
            id: "draft-001",
            case_no: "PD-ECR-DRAFT-001",
            title: "SCR bracket update",
            status: "draft",
            source_type: "ai_generated",
            customer_project: "JIM-PT611",
            created_at: "2026-06-20T08:00:00Z",
          },
          {
            id: "review-001",
            case_no: "PD-ECR-REVIEW-001",
            title: "Catalyst spec release",
            status: "in_review",
            source_type: "database",
            customer_project: "JIE-4JJ",
            created_at: "2026-06-21T08:00:00Z",
          },
        ],
      },
    })
  })
})

test("uses PD-ECR dashboard as the real dashboard and removes project management", async ({
  page,
}) => {
  await page.goto("/")

  await expect(page).toHaveURL(/\/pd-ecr\/dashboard$/)
  await expect(
    page.getByRole("heading", { name: "PD-ECR Dashboard" }),
  ).toBeVisible()
  await expect(
    page.getByRole("heading", { name: "PD-ECR Platform" }),
  ).not.toBeVisible()
  await expect(page.getByText("项目管理")).not.toBeVisible()
  await expect(page.getByText("3 total cases")).toBeVisible()
  await expect(page.getByText("PDECR25_084")).toBeVisible()

  await page.goto("/projects")

  await expect(page).toHaveURL(/\/pd-ecr\/dashboard$/)
  await expect(
    page.getByRole("heading", { name: "PD-ECR Dashboard" }),
  ).toBeVisible()
})
