import { expect, test } from "@playwright/test"

test.use({ storageState: { cookies: [], origins: [] } })

const mockUser = {
  email: "fan.xiaofeng@example.com",
  full_name: "Fan Xiaofeng",
  id: "user-pd-ecr",
  is_active: true,
  is_superuser: false,
}

const similarCases = [
  {
    rank: 1,
    case_id: "PDECR26-001",
    dc_no: "DC-2026-001",
    change_type: "Supplier change",
    matched_fields: ["customer_project", "part_no", "change_type"],
    similarity_score: 0.92,
    similarity_reason: "Same project, part family, and supplier change reason.",
    source_file: "pilot_supplier_change.md",
    module_summary: "Supplier switch with unchanged material properties.",
    source_cases: ["PDECR26-001"],
    source_files: ["pilot_supplier_change.md"],
    retrieval_mode: "hybrid",
  },
  {
    rank: 2,
    case_id: "PDECR25-084",
    dc_no: "DC-2025-084",
    change_type: "Design optimization",
    matched_fields: ["customer_project"],
    similarity_score: 0.81,
    similarity_reason: "Same customer project and validation pattern.",
    source_file: "pilot_design_optimization.md",
    module_summary: "Validation plan and implementation checklist available.",
    source_cases: ["PDECR25-084"],
    source_files: ["pilot_design_optimization.md"],
    retrieval_mode: "hybrid_keyword",
  },
]

const v1Modules = [
  {
    module_id: "basic_information",
    title: "Change Request description",
    summary: "PD-ECR request identifiers and V1 draft status.",
    content: "DC and MCR data for the new request.",
    source_cases: ["PDECR26-001"],
    source_files: ["pilot_supplier_change.md"],
    needs_human_input: false,
    warnings: [],
  },
  {
    module_id: "change_description",
    title: "Affection analysis",
    summary: "Second supplier bolt change with unchanged material properties.",
    content: "Use second supplier bolts while keeping material unchanged.",
    source_cases: ["PDECR26-001"],
    source_files: ["pilot_supplier_change.md"],
    needs_human_input: false,
    warnings: [],
  },
  {
    module_id: "reason_for_change",
    title: "Validation &trial run plan",
    summary: "RPP cost reduction and supply resilience.",
    content: "The change is driven by RPP cost reduction.",
    source_cases: ["PDECR26-001"],
    source_files: ["pilot_supplier_change.md"],
    needs_human_input: false,
    warnings: [],
  },
  {
    module_id: "impact_analysis",
    title: "Validation &Trial run plan result",
    summary: "Function, reliability, supplier quality, and assembly checked.",
    content: "Validate assembly consistency and supplier quality stability.",
    source_cases: ["PDECR26-001", "PDECR25-084"],
    source_files: ["pilot_supplier_change.md", "pilot_design_optimization.md"],
    needs_human_input: false,
    warnings: [],
  },
  {
    module_id: "implementation_plan",
    title: "Implementation task plan",
    summary: "Update BOM, supplier files, validation evidence, and import date.",
    content: "Update BOM, supplier documents, quality checks, and import plan.",
    data: {
      content:
        "# Step 6 Implementation Plan / 导入计划\n\n## 2. Implementation Summary / 导入概要\n\nUpdate BOM, supplier documents, quality checks, and import plan.",
      template_file: "5implementation_plan.md",
      rag_retrieval_results: similarCases,
      ai_prompt:
        "Use templates_pre/5implementation_plan.md and retrieved similar cases to draft implementation actions.",
    },
    source_cases: ["PDECR25-084"],
    source_files: ["pilot_design_optimization.md"],
    needs_human_input: false,
    warnings: [],
  },
  {
    module_id: "approval_signoff_information",
    title: "Implementation result",
    summary: "V1 draft sign-off references only, not formal approval.",
    content: "Review by Engineering, Purchasing, MFE, and Quality is required.",
    source_cases: [],
    source_files: [],
    needs_human_input: true,
    warnings: ["V1 does not create a formal approval route."],
  },
]

test.beforeEach(async ({ page }) => {
  await page.route("**/api/v1/users/me", async (route) => {
    await route.fulfill({ json: mockUser })
  })

  await page.route("**/api/v1/pd-ecr/history/search", async (route) => {
    await route.fulfill({
      json: {
        message: "RAG search success",
        results: similarCases,
        related_cases: similarCases.map((item) => item.case_id),
        rag_context_preview: "Similar supplier change cases were found.",
        modules: Object.fromEntries(
          v1Modules.map((module) => [module.module_id, module]),
        ),
      },
    })
  })

  await page.route("**/api/v1/pd-ecr/generate-report", async (route) => {
    await route.fulfill({
      json: {
        message: "generated",
        url: "/static/reports/report_pd-ecr-demo.html",
        draft_id: "draft-main-v1",
        draft_status: "V1_MVP_DRAFT",
        input_snapshot: { dc_no: "PD-ECR-MAIN" },
        similar_cases: similarCases,
        modules: v1Modules,
      },
    })
  })

  await page.route("**/api/v1/pd-ecr/requests", async (route) => {
    const input = route.request().postDataJSON()
    await route.fulfill({
      json: { request_id: "request-v1-demo", input, missing_fields: [] },
    })
  })

  await page.route("**/api/v1/pd-ecr/retrieve", async (route) => {
    const payload = route.request().postDataJSON()
    await route.fulfill({
      json: {
        query_input: payload.input,
        top_k: payload.top_k ?? 5,
        results: similarCases,
      },
    })
  })

  await page.route("**/api/v1/pd-ecr/cases/generate-from-ai", async (route) => {
    await route.fulfill({
      json: {
        case: {
          id: "case-generated-v1",
          case_no: "PD-ECR-DEMO-001",
          status: "draft",
          dc_no: "PD-ECR-DEMO-001",
          mcr_no: "MCR-DEMO-001",
          customer_project: "JIM-493",
          product_no: "F01ZH003G1-00",
          part_no: "F01ZH003G1-00",
          change_type: "Supplier change",
        },
        modules: v1Modules.map((module) => ({
          id: `case-generated-v1:${module.module_id}`,
          case_id: "case-generated-v1",
          module_id: module.module_id,
          title: module.title,
          content_json: {
            content:
              module.data?.content ||
              module.content,
            template_file: module.data?.template_file,
            rag_retrieval_results: module.data?.rag_retrieval_results,
            ai_prompt: module.data?.ai_prompt,
            source_cases: module.source_cases,
            source_files: module.source_files,
            needs_human_input: module.needs_human_input,
            warnings: module.warnings,
          },
          content_md: module.content,
          source_cases: module.source_cases,
          source_files: module.source_files,
          needs_human_input: module.needs_human_input,
          status: "draft",
          version: 1,
        })),
        draft_id: "draft-editable-v1",
        draft_status: "V1_MVP_DRAFT",
      },
    })
  })
})

test("searches historical PD-ECR data and opens a historical module detail", async ({
  page,
}) => {
  await page.goto("/pd-ecr")

  await expect(
    page.getByRole("heading", { name: "PD-ECR Platform" }),
  ).toBeVisible()
  await expect(
    page.getByRole("heading", { name: "历史数据检索" }),
  ).toBeVisible()
  await expect(page.getByRole("heading", { name: "新建变更" })).toBeVisible()
  await page.getByLabel("AI Search").fill("second supplier material unchanged")
  await page.getByRole("button", { name: "Run" }).click()

  await expect(page).toHaveURL(/\/pd-ecr\/cases\?view=similar$/)
  await expect(
    page.getByRole("heading", { name: "ALL PD-ECR List" }),
  ).toBeVisible()
  await expect(page.getByText("PDECR26-001")).toBeVisible()

  await page.getByRole("button", { name: "Open modules" }).first().click()

  await expect(page).toHaveURL(/\/pd-ecr\/content$/)
  await expect(
    page.getByRole("button", { name: /Change Request description/ }),
  ).toBeVisible()
})

test("shows active generated related cases and six content modules on platform", async ({
  page,
}) => {
  await page.addInitScript(() => {
    const result = {
      source: "generated",
      relatedCases: ["PDECR26-001", "PDECR25-084"],
      modules: [
        {
          id: "change-description",
          title: "Change Request description",
          subtitle: "Content 1 / 6",
          summary: "Generated change request.",
          data: { content: "Generated change request." },
        },
        {
          id: "impact-analysis",
          title: "Affection analysis",
          subtitle: "Content 2 / 6",
          summary: "Generated affection analysis.",
          data: { content: "Generated affection analysis." },
        },
        {
          id: "validation-plan",
          title: "Validation &trial run plan",
          subtitle: "Content 3 / 6",
          summary: "Generated validation plan.",
          data: { content: "Generated validation plan." },
        },
        {
          id: "validation-result",
          title: "Validation &Trial run plan result",
          subtitle: "Content 4 / 6",
          summary: "Generated validation result.",
          data: { content: "Generated validation result." },
        },
        {
          id: "implementation-plan",
          title: "Implementation task plan",
          subtitle: "Content 5 / 6",
          summary: "Generated implementation plan.",
          data: { content: "Generated implementation plan." },
        },
        {
          id: "implementation-result",
          title: "Implementation result",
          subtitle: "Content 6 / 6",
          summary: "Generated implementation result.",
          data: { content: "Generated implementation result." },
        },
      ],
    }
    localStorage.setItem("pd-ecr-generated-result", JSON.stringify(result))
    localStorage.setItem("pd-ecr-active-result", JSON.stringify(result))
    localStorage.setItem(
      "pd-ecr-history-result",
      JSON.stringify({
        source: "history",
        relatedCases: [],
        caseRows: [],
        modules: result.modules,
      }),
    )
  })

  await page.goto("/pd-ecr")

  await expect(page.getByText("Related cases").locator("..")).toContainText("2")
  await expect(page.getByText("Modules").locator("..")).toContainText("6")
})

test("completes V1 flow from form retrieval to generated module export", async ({
  page,
}) => {
  await page.goto("/pd-ecr/new")

  await page.getByLabel("Change source").fill("Purchasing")
  await page.getByLabel("Reason").fill("RPP cost reduction")
  await page.getByLabel("Target close date").fill("2026-07-03")
  await page.getByLabel("Change description").fill(
    "Second supplier bolt change with unchanged material properties.",
  )
  await expect(page.getByText("First signature target")).toBeVisible()
  await expect(page.getByText("2026-06-19")).toBeVisible()
  await expect(page.getByText("Second signature target")).toBeVisible()
  await expect(page.getByText("2026-06-26")).toBeVisible()
  await page.getByRole("button", { name: "Search similar cases" }).click()

  await expect(page.getByText("PDECR26-001")).toBeVisible()
  await expect(page.getByText("pilot_supplier_change.md")).toBeVisible()

  await page.getByRole("button", { name: /Generate editable draft/ }).click()

  await expect(page).toHaveURL(/\/pd-ecr\/content$/)
  await expect(
    page.getByRole("heading", { name: "PD-ECR-DEMO-001" }),
  ).toBeVisible()
  await expect(
    page.getByRole("button", { name: /Change Request description/ }),
  ).toBeVisible()
  await expect(
    page.getByRole("button", { name: /Validation &trial run plan/ }),
  ).toBeVisible()
  await expect(
    page.getByRole("button", { name: /Implementation task plan/ }),
  ).toBeVisible()

  await page.getByRole("button", { name: /Implementation task plan/ }).click()

  await expect(page).toHaveURL(/\/pd-ecr\/content\/implementation-plan/)
  await expect(page.getByText("Source trace")).toBeVisible()
  await expect(
    page.getByRole("complementary").getByText("PDECR25-084"),
  ).toBeVisible()
  await expect(
    page.getByRole("complementary").getByText("pilot_design_optimization.md"),
  ).toBeVisible()
  await expect(
    page.getByRole("heading", { name: /Step 6 Implementation Plan/ }),
  ).toBeVisible()
  await expect(page.getByText("RAG retrieval results")).toBeVisible()
  await expect(page.getByText("AI prompt")).toBeVisible()
  await expect(
    page.getByRole("heading", { name: "5implementation_plan.md" }),
  ).toBeVisible()
})

test("keeps change description editable and accepts before after attachments", async ({
  page,
}) => {
  await page.goto("/pd-ecr/content")
  await page.addInitScript(() => {
    const result = {
      source: "generated",
      relatedCases: ["PDECR26-001"],
      modules: [
        {
          id: "change-description",
          title: "Change Request description",
          subtitle: "Content 1 / 6",
          summary: "Generated change request.",
          data: {
            change_source: "Purchasing",
            change_reason: "RPP cost reduction",
            content: "# Should not be the primary display",
          },
          sourceCases: ["PDECR26-001"],
          sourceFiles: ["pilot_supplier_change.md"],
          needsHumanInput: false,
          warnings: [],
        },
      ],
    }
    localStorage.setItem("pd-ecr-generated-result", JSON.stringify(result))
    localStorage.setItem("pd-ecr-active-result", JSON.stringify(result))
  })

  await page.goto("/pd-ecr/content/change-description")

  await expect(page.getByLabel("变更来源")).toBeVisible()
  await expect(
    page.getByRole("heading", { name: "Before vs After" }),
  ).toBeVisible()
  await expect(page.getByText("Should not be the primary display")).toHaveCount(0)

  await page.getByLabel("Upload before files").setInputFiles({
    name: "before-image.png",
    mimeType: "image/png",
    buffer: Buffer.from("before"),
  })
  await page.getByLabel("Upload after files").setInputFiles({
    name: "after-change.pdf",
    mimeType: "application/pdf",
    buffer: Buffer.from("%PDF-1.4"),
  })

  await expect(page.getByText("before-image.png")).toBeVisible()
  await expect(page.getByText("after-change.pdf")).toBeVisible()

  const beforeAfterMetrics = await page
    .getByTestId("before-after-panel")
    .evaluate((element) => ({
      scrollWidth: element.scrollWidth,
      clientWidth: element.clientWidth,
    }))
  expect(beforeAfterMetrics.scrollWidth).toBeLessThanOrEqual(
    beforeAfterMetrics.clientWidth + 2,
  )
})
