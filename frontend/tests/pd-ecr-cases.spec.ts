import { expect, test } from "@playwright/test"

test.use({ storageState: { cookies: [], origins: [] } })

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

  await page.route("**/api/v1/pd-ecr/history/search", async (route) => {
    await route.fulfill({
      json: {
        message: "RAG search success",
        results: [
          {
            rank: 1,
            case_id: "LL-0001",
            dc_no: "DC-0001",
            change_type: "Supplier change",
            matched_fields: ["part_no"],
            similarity_score: 0.91,
            similarity_reason: "Same supplier change pattern.",
            source_file: "LL-0001.md",
            module_summary: "Supplier switch from first to second source.",
            source_cases: ["LL-0001"],
            source_files: ["LL-0001.md"],
            retrieval_mode: "hybrid",
          },
          {
            rank: 2,
            case_id: "LL-0002",
            dc_no: "DC-0002",
            change_type: "Design optimization",
            matched_fields: ["customer_project"],
            similarity_score: 0.82,
            similarity_reason: "Same customer project.",
            source_file: "LL-0002.md",
            module_summary: "Product class and material status checked.",
            source_cases: ["LL-0002"],
            source_files: ["LL-0002.md"],
            retrieval_mode: "hybrid_keyword",
          },
          {
            rank: 3,
            case_id: "LL-0003",
            dc_no: "DC-0003",
            change_type: "Validation update",
            matched_fields: ["change_type"],
            similarity_score: 0.74,
            similarity_reason: "Similar validation and trial run scope.",
            source_file: "LL-0003.md",
            module_summary: "Validation and trial run required.",
            source_cases: ["LL-0003"],
            source_files: ["LL-0003.md"],
            retrieval_mode: "keyword_fallback",
          },
        ],
        related_cases: ["LL-0001", "LL-0002", "LL-0003"],
        rag_context_preview: "Similar supplier change cases were found.",
        modules: {
          change_description: {
            title: "Change Description",
            description: "Historical change description",
            data: { Summary: "Supplier switch from first to second source." },
          },
          impact_analysis: {
            title: "Impact Analysis",
            description: "Historical impact analysis",
            data: { Summary: "Product class and material status checked." },
          },
          validation_plan: {
            title: "Validation Plan",
            description: "Historical validation plan",
            data: { Summary: "Validation and trial run required." },
          },
          execution_checklist: {
            title: "Execution Checklist",
            description: "Historical execution checklist",
            data: { Summary: "BOM and supplier files updated." },
          },
        },
      },
    })
  })
})

test("opens similar PD-ECR case list after running search", async ({
  page,
}) => {
  await page.goto("/pd-ecr")

  await page.getByLabel("AI Search").fill("second supplier material unchanged")
  await page.getByRole("button", { name: "Run" }).click()

  await expect(page).toHaveURL(/\/pd-ecr\/cases\?view=similar$/)
  await expect(
    page.getByRole("heading", { name: "ALL PD-ECR List" }),
  ).toBeVisible()
  await expect(
    page.getByRole("columnheader", { name: "PD-ECR Nr." }),
  ).toBeVisible()
  await expect(page.getByText("LL-0001")).toBeVisible()
  await expect(page.getByText("LL-0002")).toBeVisible()
  await expect(page.getByRole("button", { name: "Customer" })).toBeVisible()
})

test("opens PDF history rows as modules and shows rendered template markdown", async ({
  page,
}) => {
  await page.route("**/api/v1/pd-ecr/history/search", async (route) => {
    await route.fulfill({
      json: {
        message: "PDECR_JIE_JIM PDF metadata 检索成功",
        results: [
          {
            id: "PDECR25_084",
            case_id: "PDECR25_084",
            source_file: "PDECR25_084_JIM_493.pdf",
            pdf_file: "PDECR25_084_JIM_493.pdf",
            pdf_url: "/api/v1/pd-ecr/pdf/PDECR25_084_JIM_493.pdf",
            link: "Open modules",
            score: 42,
            module_summary: "压差支架取消卡夹。",
          },
        ],
      },
    })
  })
  await page.route("**/api/v1/pd-ecr/cases/PDECR25_084", async (route) => {
    await route.fulfill({ status: 404, json: { detail: "not found" } })
  })
  await page.route("**/api/v1/pd-ecr/cases/modules?**", async (route) => {
    await route.fulfill({
      json: {
        message: "历史案例模块生成成功",
        source: "history",
        modules: [
          {
            id: "implementation-plan",
            title: "Implementation task plan",
            subtitle: "5implementation_plan.md",
            summary: "Step 6 Implementation Plan",
            source_cases: ["PDECR25_084"],
            source_files: ["PDECR25_084_JIM_493.pdf"],
            data: {
              template_file: "5implementation_plan.md",
              content: "# Step 6 Implementation Plan\n\n历史 PDF 模板内容",
              rag_retrieval_results: [
                {
                  case_id: "PDECR25_084",
                  source_file: "PDECR25_084_JIM_493.pdf",
                  module_summary: "压差支架取消卡夹。",
                },
              ],
              ai_prompt: "AI prompt: complete templates_pre/5implementation_plan.md.",
            },
          },
        ],
      },
    })
  })

  await page.goto("/pd-ecr")
  await page.getByLabel("AI Search").fill("压差支架取消卡夹")
  await page.getByRole("button", { name: "Run" }).click()
  await page.getByRole("button", { name: "Open modules" }).click()

  await expect(page).toHaveURL(/\/pd-ecr\/content$/)
  await page.getByRole("button", { name: /Implementation task plan/ }).click()
  await expect(
    page.getByRole("heading", { name: /Step 6 Implementation Plan/ }),
  ).toBeVisible()
  await expect(page.getByText("RAG retrieval results")).toBeVisible()
})

test("keeps the PD-ECR platform on one desktop viewport", async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 950 })
  await page.goto("/pd-ecr")

  const sizes = await page.evaluate(() => ({
    body: document.body.scrollHeight,
    viewport: window.innerHeight,
  }))

  expect(sizes.body).toBeLessThanOrEqual(sizes.viewport + 8)
})
