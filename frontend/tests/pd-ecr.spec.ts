import { expect, type Page, test } from "@playwright/test"

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
    case_no: "PDECR26-001",
    case_id: "PDECR26-001",
    dc_no: "DC-2026-001",
    customer_project: "JIM-493",
    product_no: "F01ZH003G1-00",
    part_no: "F01ZH003G1-00",
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
    case_no: "PDECR25-084",
    case_id: "PDECR25-084",
    dc_no: "DC-2025-084",
    customer_project: "JIM-493",
    product_no: "F01ZH003G1-00",
    part_no: "F01ZH003G1-00",
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

const editableModules = [
  {
    module_id: "change-description",
    title: "Change Request description",
    content_md: "Use second supplier bolts while keeping material unchanged.",
    content_json: {
      summary: "Generated change request.",
      content: "Use second supplier bolts while keeping material unchanged.",
      change_proposal: "Second supplier bolt change.",
      change_reason: "RPP cost reduction",
      component_no: "F01ZH003G1-00",
      initiator: "Development",
      department: "Development",
      source_cases: ["PDECR26-001"],
      source_files: ["pilot_supplier_change.md"],
      warnings: [],
    },
    source_cases: ["PDECR26-001"],
    source_files: ["pilot_supplier_change.md"],
    needs_human_input: false,
    status: "draft",
    version: 1,
  },
  {
    module_id: "impact-analysis",
    title: "Impact analysis",
    content_md: "Function, supplier part, and manufacturing impact reviewed.",
    content_json: {
      summary: "Impact matrix prepared from similar cases.",
      content: "Function, supplier part, and manufacturing impact reviewed.",
      source_cases: ["PDECR26-001"],
      source_files: ["pilot_supplier_change.md"],
      warnings: [],
    },
    source_cases: ["PDECR26-001"],
    source_files: ["pilot_supplier_change.md"],
    needs_human_input: false,
    status: "draft",
    version: 1,
  },
  {
    module_id: "validation-plan",
    title: "Validation &trial run plan",
    content_md: "Trial run, BOM check, and supplier quality validation planned.",
    content_json: {
      summary: "Validation plan prepared.",
      content: "Trial run, BOM check, and supplier quality validation planned.",
      source_cases: ["PDECR26-001"],
      source_files: ["pilot_supplier_change.md"],
      warnings: [],
    },
    source_cases: ["PDECR26-001"],
    source_files: ["pilot_supplier_change.md"],
    needs_human_input: false,
    status: "draft",
    version: 1,
  },
  {
    module_id: "implementation-plan",
    title: "Implementation & Validation",
    content_md: "Update BOM, supplier documents, quality checks, and import plan.",
    content_json: {
      summary: "Implementation actions prepared.",
      content: "Update BOM, supplier documents, quality checks, and import plan.",
      template_file: "5implementation_plan.md",
      rag_retrieval_results: similarCases,
      ai_prompt: "Use retrieved similar cases to draft implementation actions.",
      source_cases: ["PDECR25-084"],
      source_files: ["pilot_design_optimization.md"],
      warnings: [],
    },
    source_cases: ["PDECR25-084"],
    source_files: ["pilot_design_optimization.md"],
    needs_human_input: false,
    status: "draft",
    version: 1,
  },
]

const stagedDocument = {
  id: "staged-doc-001",
  status: "draft",
  original_filename: "new-change.xlsx",
  file_type: "xlsx",
  preview_pdf_url: "/api/v1/pd-ecr/documents/staged-doc-001/preview",
  parsed_text:
    "# Parsed PD-ECR\n\n| Field | Content |\n| --- | --- |\n| Product No. | F01ZH003G1-00 |",
  metadata: {
    product_no: "F01ZH003G1-00",
    customer_project: "JIM-493",
    change_source: "Purchasing",
    reason: "RPP cost reduction",
    change_description: "Second supplier change",
    controls_json: [
      {
        type: "checkbox",
        sheet: "Impact analysis&QAC",
        cell: "E49",
        caption: "yes/是",
        checked: true,
        value: "yes",
        nearby_label: "Function Performance will be influenced?",
        source: "xlsx_xml",
      },
    ],
  },
  sections: [
    {
      index: 0,
      heading: "Change description",
      level: 1,
      content: "Second supplier change",
      page_no: 1,
    },
  ],
  tables: [
    {
      index: 0,
      caption: "Basic information",
      headers: ["Field", "Content"],
      rows: [["Product No.", "F01ZH003G1-00"]],
      page_no: 1,
    },
  ],
  created_at: "2026-06-24T00:00:00Z",
  updated_at: "2026-06-24T00:00:00Z",
}

async function fillRequiredCreationFields(page: Page) {
  await page.getByLabel("Product No.").fill("F01ZH003G1-00")
  await page.getByLabel("Customer / Project").fill("JIM-493")
  await page.getByLabel("Component No.").fill("F01ZH003G1-00")
  await page.getByLabel("Initiator").fill("Development")
  await page.getByRole("button", { name: "Change source" }).click()
  await page.getByText("Customer request / 客户要求").click()
  await page.getByLabel("Reason", { exact: true }).fill("RPP cost reduction")
  await page.getByLabel("Target close date").fill("2026-07-03")
  await page
    .getByLabel("Change description")
    .fill("Second supplier bolt change with unchanged material properties.")
}

test.beforeEach(async ({ page }) => {
  await page.addInitScript(() => {
    localStorage.setItem("access_token", "playwright-test-token")
  })

  await page.route("**/api/v1/users/me", async (route) => {
    await route.fulfill({ json: mockUser })
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

  await page.route("**/api/v1/pd-ecr/history/search", async (route) => {
    await route.fulfill({
      json: {
        message: "RAG search success",
        results: similarCases,
        related_cases: similarCases.map((item) => item.case_no),
        rag_context_preview: "Similar supplier change cases were found.",
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
          initiator: "Development",
        },
        modules: editableModules.map((module) => ({
          id: `case-generated-v1:${module.module_id}`,
          case_id: "case-generated-v1",
          ...module,
        })),
        draft_id: "draft-editable-v1",
        draft_status: "V1_MVP_DRAFT",
      },
    })
  })

  await page.route("**/api/v1/pd-ecr/cases/case-generated-v1/transition", async (route) => {
    const payload = route.request().postDataJSON()
    await route.fulfill({
      json: {
        case: {
          id: "case-generated-v1",
          case_no: "PD-ECR-DEMO-001",
          status: payload.status,
        },
      },
    })
  })

  await page.route("**/api/v1/pd-ecr/documents/upload", async (route) => {
    await route.fulfill({ json: stagedDocument })
  })

  await page.route("**/api/v1/pd-ecr/documents/staged-doc-001/confirm", async (route) => {
    await route.fulfill({
      json: {
        case_id: "case-from-upload",
        source_document_id: "source-doc-001",
        chunks_created: 6,
        case: { id: "case-from-upload", case_no: "PDECR-UPLOAD-001" },
      },
    })
  })

  await page.route("**/api/v1/pd-ecr/documents/staged-doc-001", async (route) => {
    if (route.request().method() === "PATCH") {
      await route.fulfill({ json: stagedDocument })
      return
    }
    await route.fulfill({ json: stagedDocument })
  })

  await page.route("**/api/v1/pd-ecr/cases", async (route) => {
    await route.fulfill({
      json: {
        cases: [
          {
            id: "case-from-upload",
            case_no: "PDECR-UPLOAD-001",
            source_document_id: "source-doc-001",
            source_file: "new-change.xlsx",
            pdf_file: "new-change.pdf",
            pdf_url: "/api/v1/pd-ecr/source-documents/source-doc-001/preview",
            customer_project: "JIM-493",
            product_no: "F01ZH003G1-00",
            part_no: "F01ZH003G1-00",
            change_type: "Supplier change",
          },
        ],
      },
    })
  })
})

test("uploads Excel as staged document, previews parsed content, then confirms ingestion", async ({
  page,
}) => {
  await page.goto("/pd-ecr/new")

  await page.locator('input[type="file"]').setInputFiles({
    name: "new-change.xlsx",
    mimeType:
      "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    buffer: Buffer.from("fake excel bytes"),
  })

  await expect(page).toHaveURL(/\/pd-ecr\/documents\/staged-doc-001$/)
  await expect(page.getByRole("heading", { name: "new-change.xlsx" })).toBeVisible()
  await expect(page.getByText(/历史 PD-ECR 文件解析完成/)).toBeVisible()
  await expect(page.getByText("1 sections")).toBeVisible()
  await expect(page.getByText("1 tables")).toBeVisible()
  await expect(page.getByText("1 controls")).toBeVisible()
  await expect(page.getByTitle("PDF Preview")).toBeVisible()
  await expect(page.getByText("Function Performance will be influenced?")).toBeVisible()

  await page.getByRole("button", { name: /确认入库/ }).click()
  await expect(page).toHaveURL(/\/pd-ecr\/cases\?view=all$/)
  await expect(page.getByText("PDECR-UPLOAD-001")).toBeVisible()
})

test("creates a PD-ECR draft through retrieve, AI generation, and four module review", async ({
  page,
}) => {
  await page.goto("/pd-ecr/new")

  await fillRequiredCreationFields(page)
  await page.getByRole("button", { name: "Next" }).click()
  await page.getByRole("button", { name: /搜索相似案例/ }).click()

  await expect(page.getByText("PDECR26-001")).toBeVisible()
  await expect(
    page.getByText("Supplier switch with unchanged material properties."),
  ).toBeVisible()

  await page.getByRole("button", { name: /AI 一键生成/ }).click()
  await expect(
    page.getByText("Generated editable PD-ECR draft PD-ECR-DEMO-001."),
  ).toBeVisible()

  await page.getByRole("button", { name: "查看全部模块" }).click()
  await expect(page).toHaveURL(/\/pd-ecr\/content$/)
  await expect(page.getByRole("heading", { name: "PD-ECR-DEMO-001" })).toBeVisible()
  await expect(page.getByRole("button", { name: /1\.1 变更描述/ })).toBeVisible()
  await expect(page.getByRole("button", { name: /1\.2 影响分析/ })).toBeVisible()
  await expect(page.getByRole("button", { name: /1\.3 QAC & 验证计划/ })).toBeVisible()
  await expect(page.getByRole("button", { name: /1\.4 执行计划/ })).toBeVisible()
})

test("opens Page 2 only after Page 1 modules and feasibility confirmation are complete", async ({
  page,
}) => {
  await page.addInitScript(() => {
    const draftId = "draft-page2-gate"
    const result = {
      source: "generated",
      draftId,
      draftStatus: "V1_MVP_DRAFT",
      relatedCases: ["PDECR26-001"],
      modules: [
        {
          id: "change-description",
          title: "Change Request description",
          subtitle: "Content 1 / 4",
          summary: "Second supplier bolt change.",
          data: {
            change_proposal: "Second supplier bolt change.",
            change_reason: "RPP cost reduction",
            component_no: "F01ZH003G1-00",
            initiator: "Development",
            department: "Development",
          },
        },
        {
          id: "impact-analysis",
          title: "Impact analysis",
          subtitle: "Content 2 / 4",
          summary: "Impact reviewed.",
          data: { content: "Impact reviewed." },
        },
        {
          id: "validation-plan",
          title: "Validation &trial run plan",
          subtitle: "Content 3 / 4",
          summary: "Validation planned.",
          data: { content: "Validation planned." },
        },
        {
          id: "implementation-plan",
          title: "Implementation & Validation",
          subtitle: "Content 4 / 4",
          summary: "Implementation planned.",
          data: { content: "Implementation planned." },
        },
      ],
    }
    localStorage.setItem("pd-ecr-generated-result", JSON.stringify(result))
    localStorage.setItem("pd-ecr-active-result", JSON.stringify(result))
    localStorage.setItem(
      `pd-ecr-change-description-draft:${draftId}:change-description`,
      JSON.stringify({
        changeSummary: "Second supplier bolt change.",
        reason: "RPP cost reduction",
        partNumber: "F01ZH003G1-00",
        initiator: "Development",
        department: "Development",
        departments: ["Development"],
      }),
    )
    localStorage.setItem(
      "pd-ecr-impact-analysis-impact-analysis",
      JSON.stringify({ impacts: [{ no: true, yes: false, desc: "" }] }),
    )
    localStorage.setItem(
      "pd-ecr-validation-plan-validation-plan",
      JSON.stringify({
        rows: [
          {
            id: "trial-run",
            label: "Try run",
            checked: true,
            finishDate: "2026-07-03",
            respPerson: "Quality",
            comments: "OK",
          },
        ],
        customRows: {},
      }),
    )
    localStorage.setItem(
      "pd-ecr-implementation-implementation-plan",
      JSON.stringify({
        checklistRows: [
          {
            id: "bom",
            department: "Development",
            yn: "Y",
            description: "Update BOM",
            responsible: "Development",
            dueDate: "2026-07-03",
          },
        ],
      }),
    )
    localStorage.setItem(
      "pd-ecr-feasibility-confirmation",
      JSON.stringify({
        infoText: "Feasible with current resource and validation plan.",
        initiatorConfirmed: true,
        initiatorConfirmDate: "2026-06-30 10:00:00",
        attachments: [{ name: "feasibility.pdf", type: "application/pdf", size: 1000 }],
      }),
    )
  })

  await page.goto("/pd-ecr/content")
  await page.getByRole("button", { name: /验证结果与领导签核/ }).click()

  await expect(page.getByRole("heading", { name: "QAC & Implementation Results" })).toBeVisible()
  await expect(page.getByRole("button", { name: /3\.1 QAC & Validation results/ })).toBeVisible()
  await expect(page.getByRole("button", { name: /3\.2 Implementation results/ })).toBeVisible()
  await expect(page.getByRole("heading", { name: "领导签核" })).toBeVisible()
})
