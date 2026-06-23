import type { PdEcrDisplayModule, PdEcrStoredResult } from "./pdEcrState"

export type PdEcrCaseSummary = {
  id: string
  createDate: string
  productClass: string
  from: string
  initiator: string
  customer: string
  project: string
  partNumber: string
  dept: string
}

function escapeHtml(value: string | number | undefined) {
  return String(value ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;")
}

function formatExportValue(value: unknown): string {
  if (value === null || value === undefined) return ""
  if (typeof value === "string" || typeof value === "number")
    return String(value)
  return JSON.stringify(value, null, 2)
}

function isMarkdownFileName(value: unknown) {
  return /\.md\b/i.test(String(value || ""))
}

function withoutMarkdownFiles(values: unknown): string[] {
  const list = Array.isArray(values) ? values : values ? [values] : []
  return list
    .map((value) => String(value || "").trim())
    .filter((value) => value && !isMarkdownFileName(value))
}

function shouldExportModuleField(key: string, value: unknown) {
  if (key === "source_files") return false

  if (["source_files", "source_file", "template_file"].includes(key)) {
    return withoutMarkdownFiles(value).length > 0
  }

  return !isMarkdownFileName(value)
}

export function downloadText(filename: string, content: string, type: string) {
  const blob = new Blob([content], { type })
  const url = URL.createObjectURL(blob)
  const link = document.createElement("a")
  link.href = url
  link.download = filename
  document.body.appendChild(link)
  link.click()
  link.remove()
  URL.revokeObjectURL(url)
}

function buildPdEcrCaseRows(cases: PdEcrCaseSummary[]) {
  if (!cases.length) {
    return `<tr><td colspan="9">No selected or visible reference cases.</td></tr>`
  }

  return cases
    .map(
      (row) => `
        <tr>
          <td>${escapeHtml(row.id)}</td>
          <td>${escapeHtml(row.createDate)}</td>
          <td>${escapeHtml(row.productClass)}</td>
          <td>${escapeHtml(row.from)}</td>
          <td>${escapeHtml(row.initiator)}</td>
          <td>${escapeHtml(row.customer)}</td>
          <td>${escapeHtml(row.project)}</td>
          <td>${escapeHtml(row.partNumber)}</td>
          <td>${escapeHtml(row.dept)}</td>
        </tr>`,
    )
    .join("")
}

function buildModuleFields(module: PdEcrDisplayModule) {
  const visibleSourceFiles = withoutMarkdownFiles(
    module.sourceFiles || module.data.source_files || [],
  )
  const entries: [string, unknown][] = [
    ...Object.entries(module.data).filter(([key, value]) =>
      shouldExportModuleField(key, value),
    ),
    ["source_cases", module.sourceCases || module.data.source_cases || []],
    ...(visibleSourceFiles.length
      ? ([["source_files", visibleSourceFiles]] as [string, unknown][])
      : []),
    ["needs_human_input", module.needsHumanInput ?? module.data.needs_human_input ?? false],
    ["warnings", module.warnings || module.data.warnings || []],
  ]

  if (!entries.length) {
    return `<p class="muted">No structured fields available.</p>`
  }

  return `
    <table class="field-table">
      <tbody>
        ${entries
          .map(
            ([key, value]) => `
              <tr>
                <th>${escapeHtml(key)}</th>
                <td>${escapeHtml(formatExportValue(value))}</td>
              </tr>`,
          )
          .join("")}
      </tbody>
    </table>`
}

function buildModuleCard(module: PdEcrDisplayModule, index: number) {
  const sources = module.sourceCases || module.data?.source_cases || []
  const files = withoutMarkdownFiles(module.sourceFiles || module.data?.source_files || [])
  const needsHuman = module.needsHumanInput ?? module.data?.needs_human_input
  const warnings = module.warnings || module.data?.warnings || []
  const sourceLabel = Array.isArray(sources) && sources.length ? sources.join(", ") : Array.isArray(files) && files.length ? files.join(", ") : null

  return `
    <section class="module-card">
      <div class="module-index">0${index + 1}</div>
      <div>
        <p class="eyebrow">${escapeHtml(module.subtitle)}</p>
        <h2>${escapeHtml(module.title)}</h2>
        <p class="summary">${escapeHtml(module.summary)}</p>
        ${needsHuman ? '<p class="warning-banner">⚠️ 需要人工确认 — Needs human input</p>' : ""}
        ${Array.isArray(warnings) && warnings.length ? warnings.map((w) => `<p class="warning">⚠ ${escapeHtml(String(w))}</p>`).join("") : ""}
        ${sourceLabel ? `<p class="source-ref">📎 Sources: ${escapeHtml(sourceLabel)}</p>` : ""}
        ${buildModuleFields(module)}
      </div>
    </section>`
}

export function buildPdEcrOnePageHtml({
  cases,
  result,
}: {
  cases: PdEcrCaseSummary[]
  result: PdEcrStoredResult
}) {
  const generatedAt = new Date().toLocaleString()

  return `<!doctype html>
<html>
  <head>
    <meta charset="utf-8" />
    <title>PD-ECR One Page Package</title>
    <style>
      :root {
        color: #0f172a;
        font-family: Arial, "Microsoft YaHei", sans-serif;
      }
      body {
        margin: 32px;
        background: #f8fafc;
      }
      .page {
        max-width: 1180px;
        margin: 0 auto;
        border: 1px solid #cbd5e1;
        border-radius: 14px;
        background: white;
        padding: 28px;
      }
      header {
        display: flex;
        justify-content: space-between;
        gap: 24px;
        border-bottom: 1px solid #e2e8f0;
        padding-bottom: 20px;
      }
      h1 {
        margin: 0;
        font-size: 32px;
      }
      h2 {
        margin: 4px 0 10px;
        font-size: 22px;
      }
      .muted, .summary {
        color: #475569;
        line-height: 1.65;
      }
      .badge {
        display: inline-block;
        border: 1px solid #a5f3fc;
        border-radius: 999px;
        background: #ecfeff;
        color: #0e7490;
        font-size: 12px;
        font-weight: 700;
        padding: 5px 10px;
      }
      .meta {
        text-align: right;
        color: #64748b;
        font-size: 13px;
      }
      .case-table, .field-table {
        width: 100%;
        border-collapse: collapse;
      }
      .case-table {
        margin: 22px 0 26px;
        font-size: 13px;
      }
      .case-table th {
        background: #0f172a;
        color: white;
        padding: 10px;
        text-align: left;
      }
      .case-table td {
        border-bottom: 1px solid #e2e8f0;
        padding: 10px;
      }
      .module-grid {
        display: grid;
        grid-template-columns: 1fr 1fr;
        gap: 16px;
      }
      .module-card {
        display: grid;
        grid-template-columns: 56px 1fr;
        gap: 16px;
        border: 1px solid #dbe3ea;
        border-radius: 12px;
        padding: 18px;
        break-inside: avoid;
      }
      .module-index {
        width: 42px;
        height: 42px;
        border-radius: 10px;
        background: #ecfeff;
        color: #0e7490;
        display: flex;
        align-items: center;
        justify-content: center;
        font-weight: 800;
      }
      .eyebrow {
        margin: 0;
        color: #64748b;
        font-size: 12px;
        font-weight: 700;
        letter-spacing: .08em;
        text-transform: uppercase;
      }
      .field-table {
        margin-top: 12px;
        font-size: 13px;
      }
      .field-table th {
        width: 170px;
        border-top: 1px solid #e2e8f0;
        color: #0e7490;
        padding: 9px 10px 9px 0;
        text-align: left;
        vertical-align: top;
      }
      .field-table td {
        border-top: 1px solid #e2e8f0;
        color: #1e293b;
        line-height: 1.55;
        padding: 9px 0;
        white-space: pre-wrap;
      }
      .warning-banner {
        margin: 10px 0 6px;
        padding: 8px 12px;
        border-left: 3px solid #f59e0b;
        background: #fffbeb;
        color: #92400e;
        font-size: 13px;
        font-weight: 600;
        border-radius: 4px;
      }
      .warning { color: #b45309; font-size: 12px; margin: 2px 0; }
      .source-ref { color: #0e7490; font-size: 12px; margin: 4px 0 0; }
      @media print {
        body { margin: 0; background: white; }
        .page { border: none; border-radius: 0; }
      }
    </style>
  </head>
  <body>
    <main class="page">
      <header>
        <div>
          <span class="badge">PD-ECR AI</span>
          <h1>PD-ECR One Page Package</h1>
          <p class="muted">V1 MVP draft package including input, reference cases, six modules, and source references.</p>
        </div>
        <div class="meta">
          <div>Source: ${escapeHtml(result.source)}</div>
          <div>Status: ${escapeHtml(result.draftStatus || "V1_MVP_DRAFT")}</div>
          <div>Draft: ${escapeHtml(result.draftId || "")}</div>
          <div>Generated: ${escapeHtml(generatedAt)}</div>
        </div>
      </header>

      <div style="margin:16px 0;padding:12px 16px;border-left:4px solid #f59e0b;background:#fffbeb;border-radius:6px;">
        <strong style="color:#92400e;">⚠ V1 MVP Draft — Not for production approval</strong>
        <p style="margin:4px 0 0;color:#a16207;font-size:13px;">This report is AI-generated from historical PD-ECR cases. Content must be reviewed and confirmed by responsible engineers before any production use.</p>
      </div>

      <h2>Input Snapshot</h2>
      <pre>${escapeHtml(formatExportValue(result.inputSnapshot || {}))}</pre>

      <h2>Reference Cases</h2>
      <table class="case-table">
        <thead>
          <tr>
            <th>PD-ECR Nr.</th>
            <th>Create Date</th>
            <th>Product class</th>
            <th>From</th>
            <th>Initiator</th>
            <th>Customer</th>
            <th>Project</th>
            <th>Part number</th>
            <th>Dept.</th>
          </tr>
        </thead>
        <tbody>${buildPdEcrCaseRows(cases)}</tbody>
      </table>

      <h2>Six V1 Report Modules</h2>
      <div class="module-grid">
        ${result.modules.map(buildModuleCard).join("")}
      </div>
    </main>
  </body>
</html>`
}

export function exportPdEcrOnePage({
  cases,
  result,
  returnHtml = false,
}: {
  cases: PdEcrCaseSummary[]
  result: PdEcrStoredResult
  returnHtml?: boolean
}) {
  const html = buildPdEcrOnePageHtml({ cases, result })

  if (returnHtml) {
    return html
  }

  downloadText("pd-ecr-one-page.html", html, "text/html;charset=utf-8")

  return html
}
