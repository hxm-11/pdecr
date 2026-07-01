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

  await page.route("**/api/v1/pd-ecr/knowledge-base/status", async (route) => {
    await route.fulfill({
      json: {
        knowledge_files_on_disk: 24,
        knowledge_dir: "C:\\app\\rag\\knowledge",
        vector_store: {
          index_exists: true,
          meta_exists: true,
          chunk_files: 5,
          index_path: "C:\\app\\rag\\vector_store\\pd_ecr.faiss",
          meta_path: "C:\\app\\rag\\vector_store\\pd_ecr_meta.pkl",
          index_updated_at: "2026-06-24T09:00:00+08:00",
          meta_updated_at: "2026-06-24T09:00:00+08:00",
        },
        staged_documents: {
          pending: 2,
          confirmed: 7,
          total: 9,
        },
        parser_capabilities: {
          xlsx_controls: true,
          excel_to_markdown: true,
          pdf_to_markdown: true,
          mineru: false,
        },
        last_rebuild: {
          success: true,
          total_documents: 128,
          last_rebuild_at: "2026-06-24T09:05:00+08:00",
          error: "",
        },
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
  await expect(page.getByText("Knowledge Base Health")).toBeVisible()
  await page.getByRole("button", { name: /Details/ }).click()
  await expect(page.getByText("128")).toBeVisible()
  await expect(page.getByText("2 pending review")).toBeVisible()
  await expect(page.getByText("XLSX controls")).toBeVisible()
  await expect(page.getByText("PDECR25_084")).toBeVisible()

  await page.goto("/projects")

  await expect(page).toHaveURL(/\/pd-ecr\/dashboard$/)
  await expect(
    page.getByRole("heading", { name: "PD-ECR Dashboard" }),
  ).toBeVisible()
})

test("keeps new change entry as draft enrichment instead of approval submit", async ({
  page,
}) => {
  await page.goto("/pd-ecr")

  await expect(page.getByRole("heading", { name: "PD-ECR Platform" })).toBeVisible()
  await expect(page.getByLabel("变更名称")).toBeVisible()
  await expect(page.getByRole("heading", { name: "变更评审会 / 参与人" })).toBeVisible()
  await expect(page.getByText("发起人可在新建阶段先拉会")).toBeVisible()
  await expect(page.getByRole("button", { name: "需要上会" })).toBeVisible()
  await expect(page.getByRole("button", { name: /下一步：补充变更描述/ })).toBeVisible()
  await expect(page.getByRole("button", { name: /提交审批/ })).toHaveCount(0)

  await page.getByRole("button", { name: /下一步：补充变更描述/ }).click()
  await expect(page.getByText("请先填写变更名称")).toBeVisible()
  await page.getByLabel("变更名称").fill("JIM 493 supplier change")
  await expect(page.getByText("请先填写变更名称")).toHaveCount(0)
})
