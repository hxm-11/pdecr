import { useMutation } from "@tanstack/react-query"
import { useNavigate } from "@tanstack/react-router"
import {
  ArrowLeft,
  ChevronDown,
  ExternalLink,
  FileText,
  Home,
  Link2,
  Sparkles,
  Upload,
} from "lucide-react"
import { type ReactNode, useEffect, useMemo, useRef, useState } from "react"
import ReactMarkdown from "react-markdown"
import remarkGfm from "remark-gfm"
import { Button } from "@/components/ui/button"
import {
  createPdEcrCase,
  generatePdEcrReport,
  getPdEcrModuleDraft,
  resolvePdEcrAssetUrl,
  savePdEcrModuleDraft,
} from "@/lib/pdEcrApi"
import { PdEcrProcessFlowButton } from "./PdEcrProcessFlow"
import { buildPdEcrOnePageHtml } from "./pdEcrExport"
import {
  buildGeneratedResult,
  findModule,
  loadActiveResult,
  loadGeneratedResult,
  loadHistoryResult,
  saveActiveResult,
  saveGeneratedResult,
  type PdEcrApprovalSuggestion,
  type PdEcrDisplayModule,
} from "./pdEcrState"

function textValue(module: PdEcrDisplayModule, keys: string[], fallback = "-") {
  for (const key of keys) {
    const value = module.data[key]
    if (value !== undefined && value !== null && String(value).trim()) {
      return String(value)
    }
  }
  return fallback
}

function isMarkdownFileName(value: unknown) {
  return /\.md\b/i.test(String(value || ""))
}

function visibleFileRefs(values: unknown): string[] {
  const list = Array.isArray(values) ? values : values ? [values] : []
  return list
    .map((value) => String(value || "").trim())
    .filter((value) => value && !isMarkdownFileName(value))
}

function redactMarkdownFileNames(value: string) {
  return value.replace(/[^\s,;|()<>[\]{}"']+\.md\b/gi, "")
}

function StatusLights({
  active = "amber",
}: {
  active?: "red" | "amber" | "green"
}) {
  return (
    <div className="flex flex-col gap-1 rounded-md border border-stone-300 bg-white p-1">
      {(["red", "amber", "green"] as const).map((item) => (
        <span
          key={item}
          className={`size-4 rounded-full ${
            item === "red"
              ? "bg-red-500"
              : item === "amber"
                ? "bg-amber-400"
                : "bg-emerald-500"
          } ${item === active ? "ring-2 ring-stone-500" : "opacity-75"}`}
        />
      ))}
    </div>
  )
}

function ToolFooter({ module }: { module?: PdEcrDisplayModule }) {
  const exportCsv = () => {
    if (!module) return
    const rows = [["Module", "Field", "Value"]]
    rows.push([module.title, "Title", module.title])
    rows.push([module.title, "Summary", module.summary || ""])
    Object.entries(module.data).forEach(([key, value]) => {
      rows.push([module.title, key, typeof value === "string" ? value : JSON.stringify(value)])
    })
    const csv = rows.map((r) => r.map((c) => `"${String(c ?? "").replace(/"/g, '""')}"`).join(",")).join("\n")
    const blob = new Blob([csv], { type: "text/csv;charset=utf-8" })
    const url = URL.createObjectURL(blob)
    const a = document.createElement("a")
    a.href = url; a.download = `pd-ecr-${module.id}.csv`; a.click()
    URL.revokeObjectURL(url)
  }

  const exportOnePage = () => {
    if (!module) return
    const html = buildPdEcrOnePageHtml({
      cases: [],
      result: {
        source: "generated",
        relatedCases: [],
        modules: [module],
      },
    })
    const blob = new Blob([html], { type: "text/html;charset=utf-8" })
    const url = URL.createObjectURL(blob)
    const a = document.createElement("a")
    a.href = url; a.download = `pd-ecr-${module.id}-one-page.html`; a.click()
    URL.revokeObjectURL(url)
  }

  const handleFileUpload = (files: FileList | null) => {
    if (!files?.length) return
    const names = Array.from(files).map((f) => f.name).join(", ")
    alert(`Files selected: ${names}\n(Backend upload integration pending)`)
  }

  return (
    <div className="mt-6 flex flex-wrap items-center gap-3 border-t border-stone-200 pt-4">
      <Button asChild type="button" variant="outline" className="bg-white cursor-pointer">
        <label>
          <Upload className="size-4" />
          Upload files
          <input type="file" multiple className="hidden" onChange={(e) => handleFileUpload(e.target.files)} />
        </label>
      </Button>
      <Button type="button" variant="outline" className="bg-white" onClick={exportCsv}>
        Export PD-ECR excel file
      </Button>
      <Button type="button" variant="outline" className="bg-white" onClick={exportOnePage}>
        Export PD-ECR One-page
      </Button>
      <Button type="button" variant="outline" className="ml-auto bg-amber-50">
        <Link2 className="size-4" />
        RA SuperOPL link
      </Button>
      <Button type="button" variant="outline" className="bg-amber-50">
        Concession link
      </Button>
    </div>
  )
}

function AiTask({ children }: { children: ReactNode }) {
  return (
    <aside className="rounded-lg border border-yellow-200 bg-yellow-50 p-4">
      <div className="inline-flex items-center rounded-full border border-lime-400 bg-yellow-300 px-4 py-2 text-sm font-semibold text-stone-800">
        AI 任务
      </div>
      <div className="mt-4 text-sm leading-6 text-stone-700">{children}</div>
    </aside>
  )
}

export function firstDataValue(module: PdEcrDisplayModule, keys: string[]) {
  for (const key of keys) {
    const value = module.data[key]
    if (value !== undefined && value !== null && String(value).trim()) {
      return String(value)
    }
  }
  return ""
}

export function SignatureDashboard({ module }: { module: PdEcrDisplayModule }) {
  const rows = [
    {
      role: "Engineering",
      person: firstDataValue(module, [
        "approval_engineering_person",
        "approval_development_person",
        "engineering_signer",
        "development_signer",
      ]),
      status: firstDataValue(module, [
        "approval_engineering_status",
        "approval_development_status",
        "engineering_signature_status",
      ]),
    },
    {
      role: "MFE",
      person: firstDataValue(module, [
        "approval_mfe_person",
        "mfe_signer",
        "manufacturing_signer",
      ]),
      status: firstDataValue(module, [
        "approval_mfe_status",
        "mfe_signature_status",
      ]),
    },
    {
      role: "Quality",
      person: firstDataValue(module, [
        "approval_quality_person",
        "quality_signer",
      ]),
      status: firstDataValue(module, [
        "approval_quality_status",
        "quality_signature_status",
      ]),
    },
    {
      role: "Purchasing",
      person: firstDataValue(module, [
        "approval_purchasing_person",
        "purchasing_signer",
      ]),
      status: firstDataValue(module, [
        "approval_purchasing_status",
        "purchasing_signature_status",
      ]),
    },
  ]

  return (
    <aside className="rounded-lg border border-stone-200 bg-white p-4">
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-xs font-semibold uppercase tracking-wide text-stone-500">
            Dashboard
          </p>
          <h3 className="mt-2 text-xl font-semibold text-stone-900">
            Signature status
          </h3>
        </div>
        <StatusLights active="amber" />
      </div>
      <div className="mt-4 overflow-hidden rounded-md border border-stone-200">
        <table className="w-full text-left text-sm">
          <thead className="bg-stone-100 text-stone-700">
            <tr>
              <th className="px-3 py-2 font-semibold">Function</th>
              <th className="px-3 py-2 font-semibold">Signer</th>
              <th className="px-3 py-2 font-semibold">Status</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row.role} className="border-t border-stone-200">
                <td className="px-3 py-2">{row.role}</td>
                <td className="px-3 py-2 text-stone-700">{row.person}</td>
                <td className="px-3 py-2 text-stone-700">{row.status}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </aside>
  )
}

const firstApprovalRoles: { role: string; field: string; aliases: string[] }[] = [
  {
    role: "Development",
    field: "approval_development_person",
    aliases: ["approval_engineering_person", "engineering_signer"],
  },
  {
    role: "Purchasing",
    field: "approval_purchasing_person",
    aliases: ["purchasing_signer"],
  },
  {
    role: "MFE",
    field: "approval_mfe_person",
    aliases: ["mfe_signer", "manufacturing_signer"],
  },
  {
    role: "COS",
    field: "approval_cos_person",
    aliases: ["cos_signer"],
  },
  {
    role: "Quality",
    field: "approval_quality_person",
    aliases: ["quality_signer"],
  },
  {
    role: "CPJM",
    field: "approval_cpjm_person",
    aliases: ["cpjm_signer"],
  },
  {
    role: "MOEX",
    field: "approval_moex_person",
    aliases: ["moex_signer"],
  },
  {
    role: "LOG",
    field: "approval_log_person",
    aliases: ["log_signer"],
  },
]

function parseDateValue(value?: string) {
  if (!value || value === "-") return undefined

  const isoMatch = value.match(/\d{4}-\d{1,2}-\d{1,2}/)
  const compactMatch = value.match(/\b(\d{4})(\d{2})(\d{2})\b/)
  const normalized = isoMatch?.[0] ||
    (compactMatch
      ? `${compactMatch[1]}-${compactMatch[2]}-${compactMatch[3]}`
      : value)
  const date = new Date(normalized)

  return Number.isNaN(date.getTime()) ? undefined : date
}

function addBusinessDays(date: Date, days: number) {
  const next = new Date(date)
  let remaining = days

  while (remaining > 0) {
    next.setDate(next.getDate() + 1)
    const day = next.getDay()
    if (day !== 0 && day !== 6) remaining -= 1
  }

  return next
}

function formatDate(date: Date) {
  return date.toISOString().slice(0, 10)
}

/**
 * 从模块数据中提取 Target Close date（最终截止日）。
 * 优先从 target_close_date 字段，其次从 remarks 文本中解析。
 */
function extractTargetCloseDate(module: PdEcrDisplayModule): Date | undefined {
  // 直接字段
  const direct = firstDataValue(module, [
    "target_close_date",
    "target_close",
    "close_date",
  ])
  if (direct) {
    const parsed = parseDateValue(direct)
    if (parsed) return parsed
  }

  // 从 remarks 文本解析 "Target Close date: Jun. 11" 或 "Target close date: 2026-06-11"
  const remarks = String(module.data.remarks || "")
  const match = remarks.match(
    /Target\s*[Cc]lose\s*date\s*[:：]\s*([A-Za-z]+\s*\d{1,2}|\d{4}-\d{2}-\d{2})/,
  )
  if (match) {
    const parsed = parseDateValue(match[1])
    if (parsed) return parsed
  }

  return undefined
}

/** 从 Target Close date 起算，预留工作日给后续审批和实施步骤 */
const DEFAULT_APPROVAL_LEAD_DAYS = 12

function getApprovalLeadDays(): number {
  const active = loadActiveResult()
  const generated = loadGeneratedResult()
  return (
    active.approvalLeadDays ||
    generated.approvalLeadDays ||
    DEFAULT_APPROVAL_LEAD_DAYS
  )
}

function suggestedFirstApprovalDate(module: PdEcrDisplayModule) {
  const targetCloseDate = extractTargetCloseDate(module)
  const leadDays = getApprovalLeadDays()

  // 如果有 Target Close date，反向推算：截止日 - 历史案例估算工作日 = 建议第一轮签字日
  if (targetCloseDate) {
    return formatDate(subtractBusinessDays(targetCloseDate, leadDays))
  }

  // 兜底：用创建日期 + 2 工作日
  const baseValue = firstDataValue(module, [
    "first_approval_suggested_date",
    "approval_suggested_date",
    "approval_target_date",
    "plan_finish_date",
    "target_date",
    "date",
    "create_date",
  ])
  const baseDate = parseDateValue(baseValue) || new Date()

  return formatDate(addBusinessDays(baseDate, 2))
}

function subtractBusinessDays(date: Date, days: number) {
  const next = new Date(date)
  let remaining = days

  while (remaining > 0) {
    next.setDate(next.getDate() - 1)
    const day = next.getDay()
    if (day !== 0 && day !== 6) remaining -= 1
  }

  return next
}

function getStoredApprovalSuggestions() {
  const active = loadActiveResult()
  const history = loadHistoryResult()
  const activeSuggestions = active.approvalSuggestions || []
  const historySuggestions = history.approvalSuggestions || []

  return activeSuggestions.some((item) => item.person)
    ? activeSuggestions
    : historySuggestions
}

function buildFirstApprovalRows(
  module: PdEcrDisplayModule,
  suggestions: PdEcrApprovalSuggestion[],
) {
  return firstApprovalRoles.map(({ role, field, aliases }) => {
    const suggestion = suggestions.find((item) => item.field === field)
    const person =
      suggestion?.person || firstDataValue(module, [field, ...aliases])

    return {
      role,
      field,
      person,
      source: suggestion?.source || "Historical RAG",
      status: person ? "AI suggested" : "Need confirmation",
    }
  })
}

export function FirstSignatureStatus({ module }: { module: PdEcrDisplayModule }) {
  const { rows, suggestedDate, source, targetCloseDate, leadDays } =
    useMemo(() => {
      const suggestions = getStoredApprovalSuggestions()
      const rows = buildFirstApprovalRows(module, suggestions)
      const source =
        suggestions.find((item) => item.person)?.source || "Historical RAG"
      const targetCloseDate = extractTargetCloseDate(module)

      return {
        rows,
        suggestedDate: suggestedFirstApprovalDate(module),
        source,
        targetCloseDate,
        leadDays: targetCloseDate ? getApprovalLeadDays() : 0,
      }
    }, [module])

  return (
    <section className="rounded-lg border border-amber-200 bg-amber-50/60 p-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="text-xs font-semibold uppercase tracking-wide text-amber-600">
            AI suggestion
          </p>
          <h3 className="mt-1 text-xl font-semibold text-stone-900">
            First signature status
          </h3>
          <p className="mt-1 text-sm leading-6 text-stone-600">
            {targetCloseDate
              ? `建议在第一轮签字日（${suggestedDate}）前完成，预留 ${leadDays} 个工作日用于后续审批和实施，确保在 Target Close date（${formatDate(targetCloseDate)}）前全部完成。`
              : "Historical approvers are extracted from structured approval fields; suggested date is planned two working days after the validation plan base date."}
          </p>
        </div>
        <div className="rounded-md border border-amber-200 bg-white px-3 py-2 text-sm text-stone-700">
          <span className="font-semibold text-stone-800">Source:</span>{" "}
          {source}
        </div>
      </div>

      <div className="mt-4 overflow-hidden rounded-md border border-amber-200 bg-white">
        <table className="w-full text-left text-sm">
          <thead className="bg-amber-600 text-white">
            <tr>
              <th className="px-3 py-2 font-semibold">Function</th>
              <th className="px-3 py-2 font-semibold">Historical approver</th>
              <th className="px-3 py-2 font-semibold">
                AI suggested approval date
              </th>
              <th className="px-3 py-2 font-semibold">Status</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row.field} className="border-t border-amber-100 even:bg-stone-50">
                <td className="px-3 py-2 font-medium text-stone-800">
                  {row.role}
                </td>
                <td className="px-3 py-2 text-stone-700">
                  {row.person || "-"}
                </td>
                <td className="px-3 py-2 text-stone-700">
                  {suggestedDate}
                </td>
                <td className="px-3 py-2">
                  <span
                    className={`inline-flex rounded-full border px-2.5 py-1 text-xs font-semibold ${
                      row.person
                        ? "border-emerald-200 bg-emerald-50 text-emerald-700"
                        : "border-amber-200 bg-amber-50 text-amber-700"
                    }`}
                  >
                    {row.status}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  )
}

function GeneratedContent({ module }: { module: PdEcrDisplayModule }) {
  const content = String(
    module.data.content || module.data.content_md || module.summary || "",
  ).trim()
  const templateFile = String(module.data.template_file || module.subtitle || "")
  const visibleTemplateFile = isMarkdownFileName(templateFile)
    ? ""
    : templateFile
  const ragResults = Array.isArray(module.data.rag_retrieval_results)
    ? (module.data.rag_retrieval_results as Record<string, unknown>[])
    : []
  const aiPrompt = redactMarkdownFileNames(
    String(module.data.ai_prompt || "").trim(),
  ).trim()

  return (
    <div className="space-y-5">
      <section className="rounded-lg border border-stone-200 bg-white p-5">
        <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
          <div>
            <p className="text-xs font-semibold uppercase tracking-wide text-stone-500">
              Template rendered content
            </p>
            <h2 className="mt-1 text-xl font-semibold text-stone-900">
              {visibleTemplateFile || "Generated module"}
            </h2>
          </div>
          {visibleTemplateFile ? (
            <span className="rounded-full border border-amber-200 bg-amber-50 px-3 py-1 text-xs font-semibold text-amber-800">
              {visibleTemplateFile}
            </span>
          ) : null}
        </div>

        {content ? (
          <div className="prose prose-stone prose-sm max-w-none">
            <ReactMarkdown
              remarkPlugins={[remarkGfm]}
              components={{
                table: ({ children }) => (
                  <div className="my-5 overflow-x-auto rounded-lg border border-stone-200 shadow-sm">
                    <table className="w-full border-collapse text-left text-sm">
                      {children}
                    </table>
                  </div>
                ),
                thead: ({ children }) => (
                  <thead className="bg-stone-800 text-white">{children}</thead>
                ),
                tbody: ({ children }) => <tbody>{children}</tbody>,
                tr: ({ children }) => (
                  <tr className="border-b border-stone-200 odd:bg-white even:bg-stone-50/50 hover:bg-amber-50/50 transition-colors">{children}</tr>
                ),
                th: ({ children }) => (
                  <th className="px-4 py-2.5 text-xs font-semibold uppercase tracking-wide text-white">
                    {children}
                  </th>
                ),
                td: ({ children }) => (
                  <td className="px-4 py-2.5 align-top text-xs leading-5 text-stone-700 [&:first-child]:font-medium [&:first-child]:text-stone-500 [&:first-child]:whitespace-nowrap">
                    {children}
                  </td>
                ),
                h1: ({ children }) => (
                  <h1 className="mb-5 mt-1 text-2xl font-bold tracking-tight text-stone-900 border-b border-stone-200 pb-2">
                    {children}
                  </h1>
                ),
                h2: ({ children }) => (
                  <h2 className="mb-3 mt-8 text-lg font-semibold text-stone-800 flex items-center gap-2 before:block before:h-5 before:w-1 before:rounded-full before:bg-amber-500">
                    {children}
                  </h2>
                ),
                h3: ({ children }) => (
                  <h3 className="mb-2 mt-5 text-base font-semibold text-stone-700">
                    {children}
                  </h3>
                ),
                h4: ({ children }) => (
                  <h4 className="mb-2 mt-4 text-sm font-semibold text-stone-600">
                    {children}
                  </h4>
                ),
                p: ({ children }) => (
                  <p className="my-3 leading-7 text-stone-700">{children}</p>
                ),
                ul: ({ children }) => (
                  <ul className="my-3 space-y-1 list-disc pl-6 text-stone-700">{children}</ul>
                ),
                ol: ({ children }) => (
                  <ol className="my-3 space-y-1 list-decimal pl-6 text-stone-700">{children}</ol>
                ),
                li: ({ children }) => <li className="leading-7">{children}</li>,
                hr: () => <hr className="my-6 border-stone-200" />,
                strong: ({ children }) => (
                  <strong className="font-semibold text-stone-900">{children}</strong>
                ),
                em: ({ children }) => (
                  <em className="italic text-stone-600">{children}</em>
                ),
                code: ({ children, className }) => {
                  const isInline = !className
                  return isInline ? (
                    <code className="rounded bg-stone-100 px-1.5 py-0.5 text-xs font-medium text-amber-800">
                      {children}
                    </code>
                  ) : (
                    <code className="my-3 block overflow-x-auto rounded-lg bg-stone-900 p-4 text-xs leading-relaxed text-stone-100">
                      {children}
                    </code>
                  )
                },
                pre: ({ children }) => <>{children}</>,
                blockquote: ({ children }) => (
                  <blockquote className="my-4 border-l-4 border-amber-400 bg-amber-50/50 py-2 pl-4 pr-4 text-stone-600 italic">
                    {children}
                  </blockquote>
                ),
                a: ({ href, children }) => (
                  <a href={href} target="_blank" rel="noopener noreferrer" className="font-medium text-amber-700 underline underline-offset-2 hover:text-amber-900">
                    {children}
                  </a>
                ),
              }}
            >
              {content}
            </ReactMarkdown>
          </div>
        ) : (
          <div className="rounded-md border border-amber-200 bg-amber-50 p-4 text-sm leading-6 text-amber-900">
            Template content is empty. Please complete the template or fill this
            module manually.
          </div>
        )}
      </section>

      <section className="rounded-lg border border-stone-200 bg-white p-5">
        <h2 className="text-xl font-semibold text-stone-900">
          RAG retrieval results
        </h2>
        {ragResults.length ? (
          <div className="mt-4 grid gap-3">
            {ragResults.map((item, index) => (
              <div
                key={`${String(item.case_id || item.source_file || index)}`}
                className="rounded-md border border-stone-200 bg-stone-50 p-3 text-sm"
              >
                <div className="flex flex-wrap items-center gap-2">
                  <span className="font-semibold text-stone-900">
                    {String(item.case_id || `Case ${index + 1}`)}
                  </span>
                  <span className="text-stone-500">
                    {visibleFileRefs(item.source_file).join(", ")}
                  </span>
                </div>
                <p className="mt-2 leading-6 text-stone-700">
                  {String(item.module_summary || "-")}
                </p>
                <p className="mt-2 text-xs text-stone-500">
                  Matched:{" "}
                  {Array.isArray(item.matched_fields)
                    ? item.matched_fields.join(", ")
                    : "-"}{" "}
                  · Score: {String(item.similarity_score ?? "-")}
                </p>
              </div>
            ))}
          </div>
        ) : (
          <p className="mt-3 text-sm text-stone-500">
            No module-level RAG results were attached.
          </p>
        )}
      </section>

      <section className="rounded-lg border border-amber-200 bg-amber-50 p-5">
        <h2 className="text-xl font-semibold text-stone-900">AI prompt</h2>
        <p className="mt-3 whitespace-pre-wrap text-sm leading-6 text-stone-700">
          {aiPrompt || "No AI prompt metadata was attached for this module."}
        </p>
      </section>
    </div>
  )
}

type ChangeDescriptionDraft = {
  source: string
  reason: string
  department: string
  initiator: string
  date: string
  product: string
  customer: string
  partNumber: string
  title: string
  changeSummary: string
  notChange: string
  departments: string[]
}

type BeforeAfterAttachment = {
  name: string
  type: string
  size: number
  previewUrl?: string
}

const changeFieldSpecs: {
  key: keyof Omit<ChangeDescriptionDraft, "departments">
  label: string
  dataKeys: string[]
  tableLabels: string[]
}[] = [
  {
    key: "source",
    label: "变更来源",
    dataKeys: ["source", "change_source"],
    tableLabels: ["change source", "变更来源"],
  },
  {
    key: "reason",
    label: "变更原因",
    dataKeys: ["reason", "change_reason"],
    tableLabels: ["reason of changes", "更改理由"],
  },
  {
    key: "department",
    label: "变更发起部门",
    dataKeys: ["department", "initiator_department"],
    tableLabels: ["department", "发起部门"],
  },
  {
    key: "initiator",
    label: "变更发起人",
    dataKeys: ["initiator", "owner"],
    tableLabels: ["initiator", "发起人"],
  },
  {
    key: "date",
    label: "变更发起日期",
    dataKeys: ["date", "create_date"],
    tableLabels: ["date", "日期"],
  },
  {
    key: "product",
    label: "产品",
    dataKeys: ["product_no", "product"],
    tableLabels: ["product no", "产品号"],
  },
  {
    key: "customer",
    label: "客户",
    dataKeys: ["customer", "customer_project"],
    tableLabels: ["customer project", "客户项目"],
  },
  {
    key: "partNumber",
    label: "零部件号.",
    dataKeys: ["component_no", "part_number"],
    tableLabels: ["component no", "部件号", "零部件号"],
  },
  {
    key: "title",
    label: "变更名称",
    dataKeys: ["title", "change_name"],
    tableLabels: ["change name", "变更名称"],
  },
]

export const departmentOptions = ["Sales", "ENG", "TEF", "Production", "QMM", "LOG"]

function cleanModuleText(value: unknown) {
  return String(value ?? "")
    .replace(/<[^>]+>/g, " ")
    .replace(/\s+/g, " ")
    .trim()
}

function extractMarkdownTableValue(content: string, labels: string[]) {
  const normalizedLabels = labels.map((label) => label.toLowerCase())
  const lines = content.split(/\r?\n/)

  for (const line of lines) {
    const trimmed = line.trim()
    if (!trimmed.startsWith("|")) continue
    if (/^\|\s*-+/.test(trimmed)) continue

    const cells = trimmed
      .split("|")
      .slice(1, -1)
      .map((cell) => cell.trim())

    if (cells.length < 2) continue

    const field = cells[0].toLowerCase()
    if (normalizedLabels.some((label) => field.includes(label))) {
      return cleanModuleText(cells.slice(1).join(" "))
    }
  }

  return ""
}

function firstModuleValue(
  module: PdEcrDisplayModule,
  dataKeys: string[],
  tableLabels: string[],
) {
  const direct = textValue(module, dataKeys, "")
  if (direct) return direct

  return extractMarkdownTableValue(
    String(module.data.content || ""),
    tableLabels,
  )
}

function buildChangeDraft(module: PdEcrDisplayModule): ChangeDescriptionDraft {
  const draft = Object.fromEntries(
    changeFieldSpecs.map((field) => [
      field.key,
      firstModuleValue(module, field.dataKeys, field.tableLabels),
    ]),
  ) as Omit<ChangeDescriptionDraft, "changeSummary" | "notChange" | "departments">

  const changeSummary =
    firstModuleValue(
      module,
      ["change_proposal", "summary"],
      ["step 2", "change proposal", "变更描述"],
    ) || module.summary

  const departmentsText = cleanModuleText(
    module.data.affected_departments || module.data.departments,
  )
  const departments = departmentOptions.filter((item) =>
    departmentsText
      ? departmentsText.toLowerCase().includes(item.toLowerCase())
      : item === "ENG",
  )

  return {
    ...draft,
    changeSummary,
    notChange: textValue(
      module,
      ["not_change"],
      "No product boundary change identified.",
    ),
    departments,
  }
}

function getActiveRecordId(): string {
  const active = loadActiveResult()

  const resolved =
    active.currentCase?.id ||
    active.reportUrl ||
    active.relatedCases[0] ||
    active.source

  if (resolved) return resolved

  // No case associated — use a persistent draft-id so multiple
  // standalone drafts don't collide under a single fallback key.
  const draftKey = "pd-ecr-draft-record-id"
  const existing = localStorage.getItem(draftKey)
  if (existing) return existing

  const newId = `draft-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`
  localStorage.setItem(draftKey, newId)
  return newId
}

function changeDraftStorageKey(module: PdEcrDisplayModule) {
  const recordId = getActiveRecordId()

  return `pd-ecr-change-description-draft:${recordId}:${module.id}`
}

function attachmentStorageKey(module: PdEcrDisplayModule, side: "before" | "after") {
  const recordId = getActiveRecordId()

  return `pd-ecr-before-after-attachments:${recordId}:${module.id}:${side}`
}

function loadStoredAttachments(
  module: PdEcrDisplayModule,
  side: "before" | "after",
): BeforeAfterAttachment[] {
  const raw = localStorage.getItem(attachmentStorageKey(module, side))
  if (!raw) return []

  try {
    return JSON.parse(raw) as BeforeAfterAttachment[]
  } catch {
    return []
  }
}

function persistAttachments(
  module: PdEcrDisplayModule,
  side: "before" | "after",
  attachments: BeforeAfterAttachment[],
) {
  localStorage.setItem(
    attachmentStorageKey(module, side),
    JSON.stringify(
      attachments.map(({ name, type, size }) => ({ name, type, size })),
    ),
  )
}

function fileSizeLabel(size: number) {
  if (!size) return ""
  if (size < 1024) return `${size} B`
  if (size < 1024 * 1024) return `${Math.round(size / 1024)} KB`
  return `${(size / 1024 / 1024).toFixed(1)} MB`
}

function ChangeDescriptionView({ module }: { module: PdEcrDisplayModule }) {
  const recordId = useMemo(() => getActiveRecordId(), [])
  const storageKey = useMemo(() => changeDraftStorageKey(module), [module])
  const [draft, setDraft] = useState<ChangeDescriptionDraft>(() => {
    const initialDraft = buildChangeDraft(module)
    const raw = localStorage.getItem(storageKey)
    if (!raw) return initialDraft

    try {
      return {
        ...initialDraft,
        ...(JSON.parse(raw) as Partial<ChangeDescriptionDraft>),
      }
    } catch {
      return initialDraft
    }
  })
  const navigate = useNavigate()
  const [saveStatus, setSaveStatus] = useState("Auto-filled from history")

  const generateMutation = useMutation({
    mutationFn: async () => {
      // Save draft first
      localStorage.setItem(storageKey, JSON.stringify(draft))
      const active = loadActiveResult()
      saveActiveResult({
        ...active,
        modules: active.modules.map((item) =>
          item.id === module.id
            ? {
                ...item,
                data: {
                  ...item.data,
                  source: draft.source,
                  change_reason: draft.reason,
                  department: draft.department,
                  initiator: draft.initiator,
                  date: draft.date,
                  product_no: draft.product,
                  customer_project: draft.customer,
                  component_no: draft.partNumber,
                  title: draft.title,
                  change_proposal: draft.changeSummary,
                  not_change: draft.notChange,
                  affected_departments: draft.departments.join(", "),
                },
              }
            : item,
        ),
      })

      // Build PdEcrInput from draft (same pattern as Platform page)
      const input = {
        dc_no: `PD-ECR-${Date.now()}`,
        date: draft.date || new Date().toISOString().slice(0, 10),
        customer_project: draft.customer || "PD-ECR Platform",
        initiator: draft.initiator || draft.source,
        reason: draft.reason,
        change_proposal: draft.changeSummary,
        remarks: [
          `Source: ${draft.source}`,
          `Product: ${draft.product}`,
          `Part: ${draft.partNumber}`,
          `Not change: ${draft.notChange}`,
          `Affected departments: ${draft.departments.join(", ")}`,
        ].join("\n"),
      }

      return generatePdEcrReport(input)
    },
    onSuccess: (response) => {
      const result = buildGeneratedResult(response)
      saveGeneratedResult(result)

      // Create DB case in background (non-blocking)
      const caseNo = response.draft_id || `PD-ECR-${Date.now()}`
      createPdEcrCase({
        case_no: caseNo,
        title: draft.title || draft.changeSummary || "New PD-ECR Change Request",
        status: "draft",
        source_type: "ai_generated",
        dc_no: `PD-ECR-${Date.now()}`,
        initiator: draft.initiator || draft.source || "AI Generated",
        customer_project: draft.customer || "PD-ECR Platform",
        product_no: draft.product || undefined,
        part_no: draft.partNumber || undefined,
        change_type: "Engineering Change",
      }).catch(() => {
        // Case creation is non-blocking
      })

      setSaveStatus("All 6 modules regenerated from RAG history.")
      navigate({ to: "/pd-ecr/content" })
    },
    onError: (error) => {
      setSaveStatus(
        error instanceof Error
          ? error.message
          : "Generation failed. Please try again.",
      )
    },
  })

  const [beforeAttachments, setBeforeAttachments] = useState<
    BeforeAfterAttachment[]
  >(() => loadStoredAttachments(module, "before"))
  const [afterAttachments, setAfterAttachments] = useState<
    BeforeAfterAttachment[]
  >(() => loadStoredAttachments(module, "after"))

  useEffect(() => {
    let ignore = false

    async function loadDatabaseDraft() {
      try {
        const response = await getPdEcrModuleDraft(recordId, module.id)
        if (ignore || !response.data) return

        setDraft((current) => ({
          ...current,
          ...(response.data as Partial<ChangeDescriptionDraft>),
        }))
        setSaveStatus("Loaded from database")
      } catch {
        if (!ignore) {
          setSaveStatus("Auto-filled from history")
        }
      }
    }

    loadDatabaseDraft()

    return () => {
      ignore = true
    }
  }, [module.id, recordId])

  const updateDraft = (
    key: keyof Omit<ChangeDescriptionDraft, "departments">,
    value: string,
  ) => {
    setDraft((current) => ({ ...current, [key]: value }))
  }

  const toggleDepartment = (department: string, checked: boolean) => {
    setDraft((current) => ({
      ...current,
      departments: checked
        ? Array.from(new Set([...current.departments, department]))
        : current.departments.filter((item) => item !== department),
    }))
  }

  const saveDraft = async () => {
    localStorage.setItem(storageKey, JSON.stringify(draft))

    const active = loadActiveResult()
    saveActiveResult({
      ...active,
      modules: active.modules.map((item) =>
        item.id === module.id
          ? {
              ...item,
              data: {
                ...item.data,
                source: draft.source,
                change_reason: draft.reason,
                department: draft.department,
                initiator: draft.initiator,
                date: draft.date,
                product_no: draft.product,
                customer_project: draft.customer,
                component_no: draft.partNumber,
                title: draft.title,
                change_proposal: draft.changeSummary,
                not_change: draft.notChange,
                affected_departments: draft.departments.join(", "),
              },
            }
          : item,
      ),
    })

    try {
      await savePdEcrModuleDraft({
        record_id: recordId,
        module_id: module.id,
        data: draft,
      })
      setSaveStatus("Saved to database")
    } catch {
      setSaveStatus("Saved locally, database unavailable")
    }
  }

  const addAttachments = (
    side: "before" | "after",
    files: FileList | null,
  ) => {
    const incoming = Array.from(files ?? []).map((file) => ({
      name: file.name,
      type: file.type || "application/octet-stream",
      size: file.size,
      previewUrl: file.type.startsWith("image/")
        ? URL.createObjectURL(file)
        : undefined,
    }))
    if (!incoming.length) return

    if (side === "before") {
      setBeforeAttachments((current) => {
        const next = [...current, ...incoming]
        persistAttachments(module, side, next)
        return next
      })
    } else {
      setAfterAttachments((current) => {
        const next = [...current, ...incoming]
        persistAttachments(module, side, next)
        return next
      })
    }
  }

  const attachmentList = (
    side: "before" | "after",
    attachments: BeforeAfterAttachment[],
  ) => (
    <div className="min-w-0 rounded-md border border-amber-200 bg-white p-3">
      <label className="inline-flex cursor-pointer items-center gap-2 rounded-md border border-stone-300 bg-white px-3 py-2 text-sm font-semibold text-stone-700 hover:bg-stone-50">
        <Upload className="size-4" />
        Upload {side} files
        <input
          aria-label={`Upload ${side} files`}
          type="file"
          multiple
          accept="image/*,application/pdf,.pdf"
          className="sr-only"
          onChange={(event) => addAttachments(side, event.target.files)}
        />
      </label>
      <div className="mt-3 space-y-2">
        {attachments.length ? (
          attachments.map((file, index) => (
            <div
              key={`${file.name}-${index}`}
              className="rounded border border-stone-200 bg-stone-50 p-2 text-xs text-stone-700"
            >
              {file.previewUrl ? (
                <img
                  src={file.previewUrl}
                  alt={file.name}
                  className="mb-2 h-32 w-full rounded border border-stone-200 bg-white object-contain"
                />
              ) : null}
              <p className="break-all font-semibold text-stone-900">
                {file.name}
              </p>
              <p className="mt-1 text-stone-500">
                {file.type || "file"} {file.size ? `· ${fileSizeLabel(file.size)}` : ""}
              </p>
            </div>
          ))
        ) : (
          <p className="text-xs leading-5 text-stone-500">
            Upload image or PDF evidence for the {side} side.
          </p>
        )}
      </div>
    </div>
  )

  return (
    <div className="space-y-5">
      <div className="grid gap-5 xl:grid-cols-[1fr_22rem]">
        <div className="rounded-lg border border-stone-200 bg-stone-50 p-5">
          <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
            <span className="rounded-full border border-amber-200 bg-amber-50 px-3 py-1 text-xs font-semibold text-amber-700">
              {saveStatus}
            </span>
            <div className="flex items-center gap-2">
              <Button
                type="button"
                size="sm"
                variant="outline"
                className="bg-white"
                onClick={saveDraft}
              >
                Save changes
              </Button>
              <Button
                type="button"
                size="sm"
                className="bg-amber-600 hover:bg-amber-700"
                onClick={() => generateMutation.mutate()}
                disabled={generateMutation.isPending}
              >
                <Sparkles className="size-4" />
                {generateMutation.isPending ? "AI 生成中..." : "生成"}
              </Button>
            </div>
          </div>
          <div className="grid gap-4 md:grid-cols-2">
            {changeFieldSpecs.map((field) => (
              <label key={field.key} className="space-y-1">
                <span className="text-sm font-semibold text-stone-700">
                  {field.label}
                </span>
                <input
                  value={draft[field.key]}
                  onChange={(event) =>
                    updateDraft(field.key, event.target.value)
                  }
                  className="h-10 w-full rounded-md border border-stone-300 bg-white px-3 text-sm"
                />
              </label>
            ))}
            <label className="space-y-1 md:col-span-2">
              <span className="text-sm font-semibold text-stone-700">
                是什么变更
              </span>
              <textarea
                value={draft.changeSummary}
                onChange={(event) =>
                  updateDraft("changeSummary", event.target.value)
                }
                className="min-h-28 w-full rounded-md border border-stone-300 bg-white px-3 py-2 text-sm leading-6"
              />
            </label>
            <label className="space-y-1 md:col-span-2">
              <span className="text-sm font-semibold text-stone-700">
                不是什么变更
              </span>
              <input
                value={draft.notChange}
                onChange={(event) =>
                  updateDraft("notChange", event.target.value)
                }
                className="h-10 w-full rounded-md border border-stone-300 bg-white px-3 text-sm"
              />
            </label>
          </div>
          <div className="mt-5">
            <p className="text-sm font-semibold text-stone-700">影响的部门有</p>
            <div className="mt-3 flex flex-wrap gap-6 text-sm">
              {departmentOptions.map((item) => (
                <label key={item} className="flex items-center gap-2">
                  <input
                    type="checkbox"
                    checked={draft.departments.includes(item)}
                    onChange={(event) =>
                      toggleDepartment(item, event.target.checked)
                    }
                  />
                  {item}
                </label>
              ))}
            </div>
          </div>
        </div>
        <div
          className="min-w-0 rounded-lg border border-stone-200 bg-amber-50 p-5"
          data-testid="before-after-panel"
        >
          <h2 className="inline bg-yellow-200 px-1 text-lg font-semibold">
            Before vs After
          </h2>
          <p className="mt-2 text-sm leading-6 text-stone-600">
            Upload 3D / 2D images, screenshots, PDFs, or other references for
            before and after comparison.
          </p>
          <div className="mt-6 grid min-w-0 gap-3 lg:grid-cols-2">
            {attachmentList("before", beforeAttachments)}
            {attachmentList("after", afterAttachments)}
          </div>
          <p className="mt-8 text-2xl font-semibold">Flow:</p>
        </div>
      </div>
      <ToolFooter module={module} />
    </div>
  )
}

function SourceTracePanel({ module }: { module: PdEcrDisplayModule }) {
  const [open, setOpen] = useState(false)
  const cases = (module.sourceCases || []).filter(Boolean)
  const files = (module.sourceFiles || []).filter(Boolean)

  return (
    <div className="fixed bottom-4 right-4 z-50">
      {open ? (
        <div className="w-80 rounded-lg border border-stone-200 bg-white shadow-xl">
          <div className="flex items-center justify-between rounded-t-lg bg-stone-800 px-4 py-2.5 text-sm font-semibold text-white">
            <span>Source Cases / 来源追溯</span>
            <button onClick={() => setOpen(false)} className="text-stone-300 hover:text-white text-lg leading-none">&times;</button>
          </div>
          <div className="max-h-64 overflow-y-auto p-3 space-y-2">
            {cases.length > 0 && (
              <div>
                <p className="text-xs font-semibold text-stone-500 mb-1">Related Cases</p>
                {cases.map((c, i) => (
                  <div key={i} className="rounded border border-amber-100 bg-amber-50 px-2 py-1 text-xs text-stone-700">
                    {String(c)}
                  </div>
                ))}
              </div>
            )}
            {files.length > 0 && (
              <div>
                <p className="text-xs font-semibold text-stone-500 mb-1 mt-2">Source Files</p>
                {files.map((f, i) => (
                  <div key={i} className="truncate rounded border border-stone-200 bg-stone-50 px-2 py-1 text-xs text-stone-600">
                    {String(f)}
                  </div>
                ))}
              </div>
            )}
            {!cases.length && !files.length && (
              <p className="text-xs text-stone-400">No source cases available</p>
            )}
          </div>
        </div>
      ) : (
        <button
          onClick={() => setOpen(true)}
          className="flex items-center gap-2 rounded-full border border-amber-300 bg-amber-50 px-4 py-2 text-xs font-semibold text-amber-700 shadow-lg hover:bg-amber-100 transition"
        >
          <span>📋</span> Source Trace
        </button>
      )}
    </div>
  )
}

export function ImpactAnalysisView({ module, hideApproval }: { module: PdEcrDisplayModule; hideApproval?: boolean }) {
  const impactItems = [
    { en: "Function & Performance will be influenced?", zh: "产品功能性能影响?" },
    { en: "Interface and Appearance will be influenced?", zh: "接口和外观影响?" },
    { en: "Reliability and robustness will be influenced?", zh: "产品可靠性、鲁棒性影响?" },
    { en: "Other components will be influenced?", zh: "其他零部件影响?" },
    { en: "Manufactory / assembly / testing will be influenced?", zh: "加工、装配、测试影响?" },
    { en: "Influence on supplier part?", zh: "供应商零件影响?" },
    { en: "Influence on System / HW / SW / Calibration / Mechanical?", zh: "系统/硬件/软件/标定/机械影响?" },
    { en: "Influence on cost?", zh: "对成本的影响?" },
  ]
  const docItems = [
    "Interface FMEA relevant / IFMEA",
    "Product FMEA relevant / DFMEA",
    "Special Characteristics relevant / PSC",
    "IMDS relevant",
    "Offer drawing relevant",
    "TCD relevant",
    "Norm, WB, HF... relevant",
    "WI check",
  ]
  const stockDeliveryOptions = [
    "Not affect",
    "Use in other products",
    "Scrap",
    "Rework",
    "Use up",
    "Recall",
  ]
  const defaultStockDeliveryRows = [
    {
      label: "Raw materials",
      zh: "原材料",
      options: ["Not affect", "Use in other products", "Scrap", "Rework", "Use up"],
      checked: ["Not affect"],
      remark: "包含在途",
    },
    {
      label: "Parts/Subassemble",
      zh: "零件/分总成",
      options: ["Not affect", "Use in other products", "Scrap", "Rework", "Use up"],
      checked: ["Not affect"],
      remark: "",
    },
    {
      label: "Finished goods(inhouse)",
      zh: "厂内成品",
      options: ["Not affect", "Scrap", "Rework", "Use up"],
      checked: ["Not affect"],
      remark: "",
    },
    {
      label: "Finished goods(RDCK外库)",
      zh: "RDCK外库成品",
      options: ["Not affect", "Scrap", "Rework", "Use up"],
      checked: ["Not affect"],
      remark: "",
    },
    {
      label: "Finished goods(customer)",
      zh: "客户处成品",
      options: ["Not affect", "Recall", "Rework"],
      checked: ["Not affect"],
      remark: "包含在途",
    },
  ]
  const approvalDepts = ["Development", "Purchasing", "MFE", "Quality", "COS", "MOEx", "LOG"]

  const storageKey = `pd-ecr-impact-analysis-${module.id}`
  type ImpactRow = { no: boolean; yes: boolean; confirmedBy: string; confirmedAt: string; desc: string }
  type DocRow = { no: boolean; yes: boolean; respPerson: string; dueDate: string }
  type ApprovalRow = { person: string; date: string }
  type StockDeliveryRow = {
    label: string
    zh: string
    options: string[]
    checked: string[]
    remark: string
  }

  const defaultImpact = (): ImpactRow => ({ no: true, yes: false, confirmedBy: "", confirmedAt: "", desc: "" })
  const defaultDoc = (): DocRow => ({ no: true, yes: false, respPerson: "", dueDate: "" })
  const defaultApproval = (): ApprovalRow => ({ person: "", date: "" })

  const [impacts, setImpacts] = useState<ImpactRow[]>(() => {
    try { const p = JSON.parse(localStorage.getItem(storageKey) || ""); if (p?.impacts?.length === 8) return p.impacts } catch {}
    return impactItems.map(() => defaultImpact())
  })
  const [documents, setDocuments] = useState<DocRow[]>(() => {
    try { const p = JSON.parse(localStorage.getItem(storageKey) || ""); if (p?.documents?.length) return p.documents } catch {}
    return docItems.map(() => defaultDoc())
  })
  const [mixedDeliveries, setMixedDeliveries] = useState<string>(() => {
    try { const p = JSON.parse(localStorage.getItem(storageKey) || ""); if (p?.mixedDeliveries) return p.mixedDeliveries } catch {}
    return "YES"
  })
  const [mixedDeliveryRemark, setMixedDeliveryRemark] = useState<string>(() => {
    try { const p = JSON.parse(localStorage.getItem(storageKey) || ""); if (p?.mixedDeliveryRemark) return p.mixedDeliveryRemark } catch {}
    return "单机不混，整托可混"
  })
  const [firstDeliveryAnswer, setFirstDeliveryAnswer] = useState<string>(() => {
    try { const p = JSON.parse(localStorage.getItem(storageKey) || ""); if (p?.firstDeliveryAnswer) return p.firstDeliveryAnswer } catch {}
    return "维持跟先前一样"
  })
  const [stockDeliveryRows, setStockDeliveryRows] = useState<StockDeliveryRow[]>(() => {
    try {
      const p = JSON.parse(localStorage.getItem(storageKey) || "")
      if (p?.stockDeliveryRows?.length) return p.stockDeliveryRows
    } catch {}
    return defaultStockDeliveryRows
  })
  const [approvals, setApprovals] = useState<ApprovalRow[]>(() => {
    try { const p = JSON.parse(localStorage.getItem(storageKey) || ""); if (p?.approvals?.length === 7) return p.approvals } catch {}
    return approvalDepts.map(() => defaultApproval())
  })
  const [costNote, setCostNote] = useState(() => {
    try { const p = JSON.parse(localStorage.getItem(storageKey) || ""); if (p?.costNote) return p.costNote } catch {}
    return ""
  })
  const [saveStatus, setSaveStatus] = useState("Draft")
  const autoSaveTimer = useRef<ReturnType<typeof setTimeout>>(undefined)

  // Inner step expand/collapse state (multi-select)
  const [expandedSteps, setExpandedSteps] = useState<Set<string>>(() => new Set(["step-3.1"]))

  const toggleStep = (stepId: string) => {
    setExpandedSteps((prev) => {
      const next = new Set(prev)
      if (next.has(stepId)) next.delete(stepId)
      else next.add(stepId)
      return next
    })
  }

  // Auto-save on data change (debounced 1s, skips initial render)
  useEffect(() => {
    const skip = !autoSaveTimer.current
    if (skip) { autoSaveTimer.current = setTimeout(() => {}, 0); return }
    setSaveStatus("Saving...")
    clearTimeout(autoSaveTimer.current)
    autoSaveTimer.current = setTimeout(() => {
      localStorage.setItem(storageKey, JSON.stringify({
        impacts, documents, mixedDeliveries, mixedDeliveryRemark,
        firstDeliveryAnswer, stockDeliveryRows, approvals, costNote,
      }))
      setSaveStatus("Auto-saved")
      setTimeout(() => setSaveStatus("Draft"), 2000)
    }, 1000)
    return () => clearTimeout(autoSaveTimer.current)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [impacts, documents, mixedDeliveries, mixedDeliveryRemark, firstDeliveryAnswer, stockDeliveryRows, approvals, costNote])

  const navigate = useNavigate()

  // Sync: when engineer fills "Confirmed by", auto-stamp on right approval panel
  const updateImpact = (i: number, f: keyof ImpactRow, v: string) => {
    setImpacts((p) => p.map((r, j) => {
      if (j !== i) return r
      const next = { ...r, [f]: v }
      if (f === "confirmedBy" && v.trim() && !r.confirmedAt) {
        next.confirmedAt = new Date().toISOString()
      }
      return next
    }))
  }
  const toggleImpact = (i: number, field: "no" | "yes") =>
    setImpacts((p) => p.map((r, j) => j === i ? { ...r, [field]: !r[field], [field === "no" ? "yes" : "no"]: false } : r))
  const toggleDoc = (i: number, field: "no" | "yes") =>
    setDocuments((p) => p.map((r, j) => j === i ? { ...r, [field]: !r[field], [field === "no" ? "yes" : "no"]: false } : r))
  const updateDoc = (i: number, f: keyof DocRow, v: string) =>
    setDocuments((p) => p.map((r, j) => j === i ? { ...r, [f]: v } : r))
  const updateApproval = (i: number, f: keyof ApprovalRow, v: string) =>
    setApprovals((p) => p.map((r, j) => {
      if (j !== i) return r
      const next = { ...r, [f]: v }
      if (f === "person") {
        if (v.trim()) {
          const now = new Date(); next.date = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}-${String(now.getDate()).padStart(2, "0")} ${String(now.getHours()).padStart(2, "0")}:${String(now.getMinutes()).padStart(2, "0")}:${String(now.getSeconds()).padStart(2, "0")}`
        } else {
          next.date = ""
        }
      }
      return next
    }))
  const updateStockDeliveryRemark = (i: number, v: string) =>
    setStockDeliveryRows((p) => p.map((r, j) => j === i ? { ...r, remark: v } : r))
  const toggleStockDelivery = (i: number, option: string) =>
    setStockDeliveryRows((p) => p.map((r, j) => {
      if (j !== i) return r
      const checked = r.checked.includes(option)
        ? r.checked.filter((item) => item !== option)
        : [...r.checked, option]
      return { ...r, checked }
    }))

  return (
    <div className={hideApproval ? "" : "grid gap-5 xl:grid-cols-[4fr_1fr]"}>
      {/* ═══ LEFT: scrollable Impact Analysis Content ═══ */}
      <div className={`min-w-0 space-y-5 ${hideApproval ? "" : "pr-1"}`} style={hideApproval ? {} : { maxHeight: "calc(100vh - 8rem)", overflowY: "auto" }}>
        <div className="flex flex-wrap items-center justify-between gap-3">
          <span className="inline-flex items-center gap-2 rounded-full border border-amber-200 bg-amber-50 px-3 py-1 text-xs font-semibold text-amber-700">
            <span className={`size-1.5 rounded-full ${saveStatus === "Saving..." ? "bg-amber-400 animate-pulse" : saveStatus === "Auto-saved" ? "bg-green-500" : "bg-amber-500"}`} />{saveStatus}
          </span>
          <Button type="button" variant="outline" size="sm" className="bg-white"
            onClick={() => navigate({ to: "/pd-ecr/content" })}>
            返回模块
          </Button>
        </div>

        {/* Step 3.1 Impact analysis */}
        <div className="overflow-hidden rounded-lg border border-stone-200 bg-white shadow-sm">
          <button
            type="button"
            onClick={() => toggleStep("step-3.1")}
            className="flex w-full items-center justify-between bg-stone-800 px-4 py-2.5 text-sm font-semibold text-white hover:bg-stone-700 transition"
          >
            <span><span className="mr-2 text-amber-400">Step 3.1</span>Impact Analysis / 影响分析</span>
            <ChevronDown className={`size-4 shrink-0 transition-transform duration-200 ${expandedSteps.has("step-3.1") ? "rotate-180" : ""}`} />
          </button>
          {expandedSteps.has("step-3.1") && (
          <>
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead>
                <tr className="border-b-2 border-stone-200 bg-stone-50 text-xs font-semibold uppercase text-stone-500">
                  <th className="w-8 px-3 py-2.5">#</th>
                  <th className="px-3 py-2.5">Influence area / 影响范围</th>
                  <th className="w-12 px-2 py-2.5 text-center">No</th>
                  <th className="w-12 px-2 py-2.5 text-center">Yes</th>
                  <th className="w-64 px-3 py-2.5">Measures / 措施</th>
                  <th className="w-40 px-3 py-2.5">Confirmed by / 确认人</th>
                </tr>
              </thead>
              <tbody>
                {impacts.map((row, i) => (
                  <tr key={impactItems[i].en} className="border-b border-stone-100 even:bg-stone-50/50 hover:bg-amber-50/30 transition-colors">
                    <td className="px-3 py-2.5 text-xs text-stone-400">{i + 1}</td>
                    <td className="px-3 py-2.5">
                      <p className="text-sm font-medium text-stone-800">{impactItems[i].en}</p>
                      <p className="text-xs text-stone-400">{impactItems[i].zh}</p>
                    </td>
                    <td className="px-2 py-2.5 text-center">
                      <input type="checkbox" checked={row.no} onChange={() => toggleImpact(i, "no")} className="accent-stone-500 size-4" />
                    </td>
                    <td className="px-2 py-2.5 text-center">
                      <input type="checkbox" checked={row.yes} onChange={() => toggleImpact(i, "yes")} className="accent-amber-600 size-4" />
                    </td>
                    <td className="px-3 py-2.5">
                      <input value={row.desc} onChange={(e) => updateImpact(i, "desc", e.target.value)}
                        className="h-8 w-full rounded border border-stone-200 bg-white px-2 text-xs outline-none focus:border-amber-400"
                        placeholder="Remark / 备注" />
                    </td>
                    <td className="px-3 py-2.5">
                      <div>
                        <input value={row.confirmedBy} onChange={(e) => updateImpact(i, "confirmedBy", e.target.value)}
                          className="h-8 w-full rounded border border-stone-200 bg-white px-2 text-xs outline-none focus:border-amber-400" placeholder="Name" />
                        {row.confirmedAt && <p className="mt-0.5 text-[10px] text-stone-400">{new Date(row.confirmedAt).toLocaleString()}</p>}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <button type="button" onClick={() => setImpacts((p) => [...p, defaultImpact()])}
            className="flex w-full items-center justify-center gap-1 border-t border-stone-200 py-1.5 text-xs text-stone-400 hover:bg-stone-50 hover:text-stone-600 transition">
            + 添加影响项
          </button>
          {/* Cost note (item 8) */}
          <div className="border-t border-stone-200 bg-amber-50/30 px-4 py-3">
            <p className="text-sm font-semibold text-stone-700">8. Influence on cost / 对成本的影响</p>
            <div className="mt-2 flex flex-wrap items-center gap-4">
              {["Increase", "Decrease", "No change"].map((opt) => (
                <label key={opt} className="flex items-center gap-1.5 text-sm">
                  <input type="radio" name={`cost-${module.id}`} value={opt} checked={costNote === opt}
                    onChange={(e) => setCostNote(e.target.value)} className="accent-amber-600" />{opt}
                </label>
              ))}
              <input value={costNote && !["Increase","Decrease","No change"].includes(costNote) ? costNote : ""}
                onChange={(e) => setCostNote(e.target.value)}
                className="h-8 flex-1 rounded border border-stone-200 bg-white px-2 text-xs outline-none focus:border-amber-400" placeholder="备注说明..." />
            </div>
          </div>
          </>
          )}
        </div>

        {/* Mixed Deliveries */}
        <div className="overflow-hidden rounded-lg border border-stone-200 bg-white shadow-sm">
          <button
            type="button"
            onClick={() => toggleStep("step-3.1.9")}
            className="flex w-full items-center justify-between bg-stone-800 px-4 py-2.5 text-sm font-semibold text-white hover:bg-stone-700 transition"
          >
            <span><span className="mr-2 text-amber-400">Step 3.1.9</span>Stock / Delivery Treatment / 库存发货处理</span>
            <ChevronDown className={`size-4 shrink-0 transition-transform duration-200 ${expandedSteps.has("step-3.1.9") ? "rotate-180" : ""}`} />
          </button>
          {expandedSteps.has("step-3.1.9") && (
          <div className="p-4">
            <div className="overflow-x-auto rounded-md border border-stone-200">
              <table className="min-w-250 w-full text-left text-sm">
                <thead className="bg-stone-50 text-xs font-semibold uppercase text-stone-500">
                  <tr>
                    <th className="w-72 px-3 py-2.5">Item / 项目</th>
                    {stockDeliveryOptions.map((option) => (
                      <th key={option} className="w-28 px-2 py-2.5 text-center normal-case">
                        {option}
                      </th>
                    ))}
                    <th className="min-w-64 px-3 py-2.5">Remark / 备注</th>
                  </tr>
                </thead>
                <tbody>
                  <tr className="border-t border-stone-200">
                    <td className="px-3 py-2.5 font-medium text-stone-800">
                      <p>Mixed Deliveries Permissible?</p>
                      <p className="text-xs font-normal text-stone-400">改前改后是否可以混合供货？</p>
                    </td>
                    <td className="px-2 py-2.5 text-center">
                      <label className="inline-flex items-center gap-1.5">
                        <input type="radio" name={`mixed-${module.id}`} value="YES" checked={mixedDeliveries === "YES"}
                          onChange={(e) => setMixedDeliveries(e.target.value)} className="accent-amber-600" />
                        YES
                      </label>
                    </td>
                    <td className="px-2 py-2.5 text-center">
                      <label className="inline-flex items-center gap-1.5">
                        <input type="radio" name={`mixed-${module.id}`} value="NO" checked={mixedDeliveries === "NO"}
                          onChange={(e) => setMixedDeliveries(e.target.value)} className="accent-amber-600" />
                        NO
                      </label>
                    </td>
                    <td colSpan={stockDeliveryOptions.length - 2} className="px-2 py-2.5" />
                    <td className="px-3 py-2.5">
                      <input value={mixedDeliveryRemark} onChange={(e) => setMixedDeliveryRemark(e.target.value)}
                        className="h-8 w-full rounded border border-stone-200 bg-white px-2 text-xs outline-none focus:border-amber-400" />
                    </td>
                  </tr>
                  <tr className="border-t border-stone-200 bg-stone-50/50">
                    <td className="px-3 py-2.5 font-medium text-stone-800">
                      <p>How to deal with 1st delivery after change?</p>
                      <p className="text-xs font-normal text-stone-400">改后第一批货物的交货要求?</p>
                    </td>
                    <td colSpan={stockDeliveryOptions.length + 1} className="px-3 py-2.5">
                      <input value={firstDeliveryAnswer} onChange={(e) => setFirstDeliveryAnswer(e.target.value)}
                        className="h-8 w-full rounded border border-stone-200 bg-white px-2 text-xs outline-none focus:border-amber-400"
                        placeholder="Answer / 回答" />
                    </td>
                  </tr>
                  {stockDeliveryRows.map((row, i) => (
                    <tr key={row.label} className="border-t border-stone-200 even:bg-stone-50/50">
                      <td className="px-3 py-2.5 font-medium text-stone-800">
                        <p>{row.label}</p>
                        <p className="text-xs font-normal text-stone-400">{row.zh}</p>
                      </td>
                      {stockDeliveryOptions.map((option) => (
                        <td key={option} className="px-2 py-2.5 text-center">
                          {row.options.includes(option) ? (
                            <input type="checkbox" checked={row.checked.includes(option)}
                              onChange={() => toggleStockDelivery(i, option)}
                              className="accent-amber-600 size-4" aria-label={`${row.label} ${option}`} />
                          ) : null}
                        </td>
                      ))}
                      <td className="px-3 py-2.5">
                        <input value={row.remark} onChange={(e) => updateStockDeliveryRemark(i, e.target.value)}
                          className="h-8 w-full rounded border border-stone-200 bg-white px-2 text-xs outline-none focus:border-amber-400"
                          placeholder="Remark / 备注" />
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
          )}
        </div>

        {/* Step 3.3 Affected documents */}
        <div className="overflow-hidden rounded-lg border border-stone-200 bg-white shadow-sm">
          <button
            type="button"
            onClick={() => toggleStep("step-3.3")}
            className="flex w-full items-center justify-between bg-stone-800 px-4 py-2.5 text-sm font-semibold text-white hover:bg-stone-700 transition"
          >
            <span><span className="mr-2 text-amber-400">Step 3.3</span>Affected Documents Check / 受影响文件检查</span>
            <ChevronDown className={`size-4 shrink-0 transition-transform duration-200 ${expandedSteps.has("step-3.3") ? "rotate-180" : ""}`} />
          </button>
          {expandedSteps.has("step-3.3") && (
          <>
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead>
                <tr className="border-b-2 border-stone-200 bg-stone-50 text-xs font-semibold uppercase text-stone-500">
                  <th className="w-8 px-3 py-2.5">#</th>
                  <th className="px-3 py-2.5">Document / 文件</th>
                  <th className="w-12 px-2 py-2.5 text-center">No</th>
                  <th className="w-12 px-2 py-2.5 text-center">Yes</th>
                  <th className="w-28 px-3 py-2.5">Resp. person</th>
                  <th className="w-36 px-3 py-2.5">Due date</th>
                </tr>
              </thead>
              <tbody>
                {documents.map((row, i) => (
                  <tr key={i} className="border-b border-stone-100 even:bg-stone-50/50 hover:bg-amber-50/30 transition-colors">
                    <td className="px-3 py-2.5 text-xs text-stone-400">{i + 1}</td>
                    <td className="px-3 py-2.5 text-sm font-medium text-stone-800">{docItems[i]}</td>
                    <td className="px-2 py-2.5 text-center">
                      <input type="checkbox" checked={row.no} onChange={() => toggleDoc(i, "no")} className="accent-stone-500 size-4" />
                    </td>
                    <td className="px-2 py-2.5 text-center">
                      <input type="checkbox" checked={row.yes} onChange={() => toggleDoc(i, "yes")} className="accent-amber-600 size-4" />
                    </td>
                    <td className="px-3 py-2.5">
                      <input value={row.respPerson} onChange={(e) => updateDoc(i, "respPerson", e.target.value)}
                        className="h-8 w-full rounded border border-stone-200 bg-white px-2 text-xs outline-none focus:border-amber-400" placeholder="Resp." />
                    </td>
                    <td className="px-3 py-2.5">
                      <input type="date" value={row.dueDate} onChange={(e) => updateDoc(i, "dueDate", e.target.value)}
                        className="h-8 w-full rounded border border-stone-200 bg-white px-2 text-xs outline-none focus:border-amber-400" />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <button type="button" onClick={() => setDocuments((p) => [...p, defaultDoc()])}
            className="flex w-full items-center justify-center gap-1 border-t border-stone-200 py-1.5 text-xs text-stone-400 hover:bg-stone-50 hover:text-stone-600 transition">
            + 添加文件项
          </button>
          </>
          )}
        </div>

      </div>

      {/* ═══ RIGHT: Leader Approval Panel (1/5, sticky) — hidden when outer panel is active ═══ */}
      {!hideApproval && (
      <div className="hidden xl:block">
        <div className="sticky top-4 space-y-4" style={{ maxHeight: "calc(100vh - 8rem)", overflowY: "auto" }}>
          {/* Auto-synced approval panel */}
          <div className="rounded-lg border border-amber-300 bg-white shadow-sm">
            <div className="rounded-t-lg bg-amber-600 px-4 py-2.5 text-sm font-semibold text-white">
              Change-Feasibility Review / 可行性评审
            </div>
            <div className="divide-y divide-stone-100">
              {approvalDepts.map((dept, i) => (
                <div key={dept} className="px-4 py-2.5">
                  <p className="text-xs font-semibold text-stone-700">{dept}</p>
                  <input value={approvals[i].person} onChange={(e) => updateApproval(i, "person", e.target.value)}
                    className="mt-1 h-8 w-full rounded border border-stone-200 bg-white px-2 text-xs outline-none focus:border-amber-400"
                    placeholder="签批人..." />
                  {approvals[i].date ? (
                    <p className="mt-1 text-[10px] font-medium text-emerald-600">
                      ✓ {approvals[i].date}
                    </p>
                  ) : (
                    <p className="mt-1 text-[10px] text-stone-300">待确认</p>
                  )}
                </div>
              ))}
            </div>
          </div>

          {/* Impact confirmations feed into approval */}
          <div className="rounded-lg border border-stone-200 bg-stone-50 p-4">
            <p className="text-xs font-semibold text-stone-500">已确认的影响项</p>
            <div className="mt-2 max-h-48 space-y-1.5 overflow-y-auto">
              {impacts.filter((r) => r.confirmedBy).length === 0 && (
                <p className="text-xs text-stone-400">左侧填写确认人后自动显示</p>
              )}
              {impacts.filter((r) => r.confirmedBy).map((r, i) => (
                <div key={i} className="rounded border border-amber-100 bg-white px-2 py-1 text-xs">
                  <span className="font-medium text-stone-700">{impactItems[i].en.slice(0, 40)}...</span>
                  <div className="mt-0.5 flex items-center justify-between text-stone-500">
                    <span>{r.confirmedBy}</span>
                    <span className="text-[10px]">{r.confirmedAt ? new Date(r.confirmedAt).toLocaleString() : ""}</span>
                  </div>
                </div>
              ))}
            </div>
          </div>

          <SignatureDashboard module={module} />
        </div>
      </div>
      )}

      {/* ═══ Floating Source Trace (bottom-right, collapsible) ═══ */}
      {module.sourceCases?.length || module.sourceFiles?.length ? (
        <SourceTracePanel module={module} />
      ) : null}
    </div>
  )
}

export function ValidationPlanView({ module }: { module: PdEcrDisplayModule }) {
  const rowLabels = [
    "Try run", "Capability Studies CMK", "Capability Studies MSA", "MAE release",
    "Cleanness test", "QZ test", "200h PDL", "BOM check", "Test report", "PAV release", "Other",
  ]
  const storageKey = `pd-ecr-validation-plan-${module.id}`
  type ValRow = { id: string; label: string; checked: boolean; criteria: string; finishDate: string; respPerson: string; comments: string }

  const [rows, setRows] = useState<ValRow[]>(() => {
    const raw = localStorage.getItem(storageKey)
    if (raw) {
      try { const parsed = JSON.parse(raw); if (parsed.rows) return parsed.rows } catch {}
    }
    return rowLabels.map((label) => ({ id: `init-${label}`, label, checked: false, criteria: "AI suggested criteria", finishDate: "", respPerson: "", comments: "" }))
  })
  const [saveStatus, setSaveStatus] = useState("Draft")

  const toggleCheck = (index: number) => setRows((prev) => prev.map((r, i) => i === index ? { ...r, checked: !r.checked } : r))
  const updateField = (index: number, field: keyof Omit<ValRow, "label" | "checked">, value: string) => {
    setRows((prev) => prev.map((r, i) => i === index ? { ...r, [field]: value } : r))
  }
  const savePlan = () => {
    localStorage.setItem(storageKey, JSON.stringify({ rows }))
    setSaveStatus("Saved")
  }

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <span className="inline-flex items-center gap-2 rounded-full border border-amber-200 bg-amber-50 px-3 py-1 text-xs font-semibold text-amber-700">
          <span className={`size-1.5 rounded-full ${saveStatus === "Saving..." ? "bg-amber-400 animate-pulse" : saveStatus === "Saved" ? "bg-green-500" : "bg-amber-500"}`} />{saveStatus || "Draft"}
        </span>
        <Button type="button" variant="outline" size="sm" className="bg-white" onClick={savePlan}>Save changes</Button>
      </div>

      <div className="overflow-hidden rounded-lg border border-stone-200 bg-white shadow-sm">
        <div className="flex items-center justify-between bg-stone-800 px-4 py-2.5 text-sm font-semibold text-white">
          <span><span className="mr-2 text-amber-400">Step 3.2</span>QAC &amp; Validation plan</span>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead>
              <tr className="border-b-2 border-stone-200 bg-stone-50 text-xs font-semibold uppercase text-stone-500">
                <th className="w-8 px-3 py-2.5">☑</th>
                <th className="px-3 py-2.5">Validation / 验证项目</th>
                <th className="w-32 px-3 py-2.5">Plan finish date</th>
                <th className="w-28 px-3 py-2.5">Resp. person</th>
                <th className="px-3 py-2.5">Comments / 备注</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row, i) => (
                <tr key={row.id} className="border-b border-stone-100 even:bg-stone-50/50 hover:bg-amber-50/30 transition-colors">
                  <td className="px-3 py-2.5 text-center">
                    <input type="checkbox" checked={row.checked} onChange={() => toggleCheck(i)} className="accent-amber-600 size-4" />
                  </td>
                  <td className="px-3 py-2.5 text-sm font-medium text-stone-800">{row.label}</td>
                  <td className="px-3 py-2.5">
                    <input type="date" value={row.finishDate} onChange={(e) => updateField(i, "finishDate", e.target.value)}
                      className="h-8 w-full rounded border border-stone-200 bg-white px-2 text-xs outline-none focus:border-amber-400" />
                  </td>
                  <td className="px-3 py-2.5">
                    <input value={row.respPerson} onChange={(e) => updateField(i, "respPerson", e.target.value)}
                      className="h-8 w-full rounded border border-stone-200 bg-white px-2 text-xs outline-none focus:border-amber-400" placeholder="Resp." />
                  </td>
                  <td className="px-3 py-2.5">
                    <input value={row.comments} onChange={(e) => updateField(i, "comments", e.target.value)}
                      className="h-8 w-full rounded border border-stone-200 bg-white px-2 text-xs outline-none focus:border-amber-400" placeholder="备注" />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <button type="button" onClick={() => setRows((p) => [...p, { id: `new-${Date.now()}-${p.length}`, label: "", checked: false, criteria: "", finishDate: "", respPerson: "", comments: "" }])}
          className="flex w-full items-center justify-center gap-1 border-t border-stone-200 py-1.5 text-xs text-stone-400 hover:bg-stone-50 hover:text-stone-600 transition">
          + 添加验证项
        </button>
      </div>
    </div>
  )
}

export function _ValidationResultView({
  module,
}: {
  module: PdEcrDisplayModule
}) {
  return (
    <div className="grid gap-5 xl:grid-cols-[1fr_24rem]">
      <div className="grid gap-5 md:grid-cols-2">
        <div className="rounded-lg border border-stone-200 bg-white p-5">
          <h2 className="text-3xl font-semibold">Validation result</h2>
          <div className="mt-5 min-h-72 border border-stone-300 bg-yellow-100 p-4 text-2xl leading-relaxed">
            User check 打勾 Y/N，表示结果状态
            <br />
            <br />
            签字，日期
          </div>
        </div>
        <div className="rounded-lg border border-stone-200 bg-white p-5">
          <h2 className="text-3xl font-semibold">Trial run result</h2>
          <div className="mt-5 flex min-h-72 items-end border border-stone-300 bg-stone-50 p-4">
            <div className="bg-yellow-100 p-2 text-2xl">
              User 自己填写 + click 递交/R
            </div>
          </div>
        </div>
        <div className="md:col-span-2">
          <GeneratedContent module={module} />
          <ToolFooter module={module} />
        </div>
      </div>
      <SignatureDashboard module={module} />
      <AiTask>
        <p>与 USER 确认调研：是否需要 AI 辅助判断验证结果 OK / NOK。</p>
        <p className="mt-3 bg-amber-200 px-1 font-semibold">
          AI 的技术应用考量点：
        </p>
        <p>
          基于历史相似 PD-ECR CASE 的相同部分内容，并关联 validation plan and
          evaluation criteria。
        </p>
      </AiTask>
    </div>
  )
}

export function ValidationResultFunctionalView({
  module,
}: {
  module: PdEcrDisplayModule
}) {
  const storageKey = `pd-ecr-validation-result-${module.id}`
  const defaultRows = [
    "Try run",
    "Capability Studies CMK",
    "Capability Studies MSA",
    "MAE release",
    "Cleanness test",
    "QZ test",
    "200h PDL",
    "BOM check",
    "Test report",
    "PAV release",
    "Other",
  ].map((item) => ({
    date: "",
    item,
    result: "",
    signer: "",
    status: "",
  }))
  const [rows, setRows] = useState(() => {
    const raw = localStorage.getItem(storageKey)
    if (!raw) return defaultRows
    try {
      const parsed = JSON.parse(raw) as typeof defaultRows
      return parsed.length ? parsed : defaultRows
    } catch {
      return defaultRows
    }
  })
  const [trialRunResult, setTrialRunResult] = useState(
    () => localStorage.getItem(`${storageKey}-trial-run`) || "",
  )
  const [saveStatus, setSaveStatus] = useState("Draft")

  const updateRow = (
    index: number,
    key: keyof (typeof rows)[number],
    value: string,
  ) => {
    setRows((current) =>
      current.map((row, rowIndex) =>
        rowIndex === index ? { ...row, [key]: value } : row,
      ),
    )
  }

  const saveResult = (nextStatus: string) => {
    localStorage.setItem(storageKey, JSON.stringify(rows))
    localStorage.setItem(`${storageKey}-trial-run`, trialRunResult)
    setSaveStatus(nextStatus)
  }

  const exportCsv = () => {
    const csv = [
      ["Validation item", "Status", "Result / evidence", "Signer", "Date"],
      ...rows.map((row) => [
        row.item,
        row.status,
        row.result,
        row.signer,
        row.date,
      ]),
      ["Trial run result", "", trialRunResult, "", ""],
    ]
      .map((row) =>
        row
          .map((cell) => `"${String(cell ?? "").replace(/"/g, '""')}"`)
          .join(","),
      )
      .join("\n")

    const blob = new Blob([csv], { type: "text/csv;charset=utf-8" })
    const url = URL.createObjectURL(blob)
    const link = document.createElement("a")
    link.href = url
    link.download = "pd-ecr-validation-result.csv"
    link.click()
    URL.revokeObjectURL(url)
    setSaveStatus("Exported")
  }

  return (
    <div className="grid gap-5 xl:grid-cols-[1fr_24rem]">
      <div className="space-y-5">
        <section className="rounded-lg border border-stone-200 bg-white p-5">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <h2 className="text-2xl font-semibold">Validation result</h2>
            <span className="rounded-full border border-amber-200 bg-amber-50 px-3 py-1 text-xs font-semibold text-amber-700">
              {saveStatus}
            </span>
          </div>
          <div className="mt-5 overflow-x-auto rounded-lg border border-stone-200">
            <table className="min-w-225 w-full border-collapse text-left text-sm">
              <thead className="bg-amber-600 text-white">
                <tr>
                  <th className="px-3 py-2">Validation item</th>
                  <th className="w-32 px-3 py-2">OK / NOK</th>
                  <th className="px-3 py-2">Result / evidence</th>
                  <th className="w-40 px-3 py-2">Signer</th>
                  <th className="w-36 px-3 py-2">Date</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((row, index) => (
                  <tr
                    key={row.item}
                    className="border-t border-stone-200 even:bg-stone-50"
                  >
                    <td className="px-3 py-2 font-medium">{row.item}</td>
                    <td className="px-3 py-2">
                      <select
                        value={row.status}
                        onChange={(event) =>
                          updateRow(index, "status", event.target.value)
                        }
                        className="h-9 w-full rounded-md border border-stone-300 bg-white px-2"
                      >
                        <option value="" />
                        <option value="OK">OK</option>
                        <option value="NOK">NOK</option>
                        <option value="N/A">N/A</option>
                      </select>
                    </td>
                    <td className="px-3 py-2">
                      <input
                        value={row.result}
                        onChange={(event) =>
                          updateRow(index, "result", event.target.value)
                        }
                        className="h-9 w-full rounded-md border border-stone-300 bg-white px-2"
                      />
                    </td>
                    <td className="px-3 py-2">
                      <input
                        value={row.signer}
                        onChange={(event) =>
                          updateRow(index, "signer", event.target.value)
                        }
                        className="h-9 w-full rounded-md border border-stone-300 bg-white px-2"
                      />
                    </td>
                    <td className="px-3 py-2">
                      <input
                        type="date"
                        value={row.date}
                        onChange={(event) =>
                          updateRow(index, "date", event.target.value)
                        }
                        className="h-9 w-full rounded-md border border-stone-300 bg-white px-2"
                      />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>

        <section className="rounded-lg border border-stone-200 bg-white p-5">
          <h2 className="text-2xl font-semibold">Trial run result</h2>
          <textarea
            value={trialRunResult}
            onChange={(event) => setTrialRunResult(event.target.value)}
            className="mt-4 min-h-44 w-full resize-y rounded-lg border border-stone-300 bg-white px-4 py-3 text-sm leading-6"
            placeholder="Record trial run result, evidence, abnormal points, and conclusion."
          />
        </section>

        <div className="flex flex-wrap items-center gap-3">
          <Button type="button" onClick={() => saveResult("Saved")}>
            Save draft
          </Button>
          <Button
            type="button"
            className="bg-amber-600 hover:bg-amber-700"
            onClick={() => saveResult("Submitted")}
          >
            Submit result
          </Button>
          <Button type="button" variant="outline" onClick={exportCsv}>
            Export CSV
          </Button>
        </div>

        <GeneratedContent module={module} />
        <ToolFooter module={module} />
      </div>
      <SignatureDashboard module={module} />
    </div>
  )
}

export function ImplementationView({
  module,
  resultOnly: _resultOnly = false,
}: {
  module: PdEcrDisplayModule
  resultOnly?: boolean
}) {
  // ── Data definitions matching Excel template ──
  type ImplRow = { id: string; department: string; yn: string; description: string; responsible: string; dueDate: string; result?: string; resultNote?: string }
  let _implRowId = 0
  const nextImplRowId = () => `impl-${Date.now()}-${_implRowId++}-${Math.random().toString(36).slice(2, 6)}`

  const defaultChecklist: ImplRow[] = [
    // Development
    { id: nextImplRowId(), department: "Development", yn: "N", description: "Documents release (drawing, offer drawing, BOM, Spec., ...)", responsible: "", dueDate: "" },
    { id: nextImplRowId(), department: "Development", yn: "N", description: "Change BOMs & Drawings & Documents in POE system", responsible: "", dueDate: "" },
    { id: nextImplRowId(), department: "Development", yn: "N", description: "Inform documents update (check work-on can met requirements)", responsible: "", dueDate: "" },
    { id: nextImplRowId(), department: "Development", yn: "Y", description: "Update Offer drawing, TCD, D-FMEA", responsible: "", dueDate: "" },
    { id: nextImplRowId(), department: "Development", yn: "N", description: "Norm, WB, HF...", responsible: "", dueDate: "" },
    { id: nextImplRowId(), department: "Development", yn: "N", description: "MoC, IMDS", responsible: "", dueDate: "" },
    // Manufacturing
    { id: nextImplRowId(), department: "Manufacturing", yn: "Y", description: "Related (Production/Testing) equipment be ready on site", responsible: "", dueDate: "" },
    { id: nextImplRowId(), department: "Manufacturing", yn: "Y", description: "Related (Production/Testing) program be ready", responsible: "", dueDate: "" },
    { id: nextImplRowId(), department: "Manufacturing", yn: "Y", description: "Related (Production/Testing) tooling / cutting / fixture etc. be ready", responsible: "", dueDate: "" },
    { id: nextImplRowId(), department: "Manufacturing", yn: "Y", description: "Old tooling / cutting / fixture disposal", responsible: "", dueDate: "" },
    { id: nextImplRowId(), department: "Manufacturing", yn: "Y", description: "Old materials disposal", responsible: "", dueDate: "" },
    { id: nextImplRowId(), department: "Manufacturing", yn: "Y", description: "Planner update the planning sheet", responsible: "", dueDate: "" },
    { id: nextImplRowId(), department: "Manufacturing", yn: "Y", description: "Update FMEA", responsible: "", dueDate: "" },
    { id: nextImplRowId(), department: "Manufacturing", yn: "Y", description: "Update CP/FC (Control Plan/Flow Chart)", responsible: "", dueDate: "" },
    { id: nextImplRowId(), department: "Manufacturing", yn: "Y", description: "Update WI/PDS (Include attachments.)", responsible: "", dueDate: "" },
    { id: nextImplRowId(), department: "Manufacturing", yn: "Y", description: "First batch Mark, Special Mark (Inside Package)", responsible: "", dueDate: "" },
    { id: nextImplRowId(), department: "Manufacturing", yn: "Y", description: "First batch Mark, Special Mark (Outside Package)", responsible: "", dueDate: "" },
    { id: nextImplRowId(), department: "Manufacturing", yn: "Y", description: "Training", responsible: "", dueDate: "" },
    // COS
    { id: nextImplRowId(), department: "COS", yn: "Y", description: "Confirm the storage of old parts and coordinate the introduction date for new parts", responsible: "", dueDate: "" },
    { id: nextImplRowId(), department: "COS", yn: "Y", description: "Confirm the delivery date of old parts and first delivery of new parts (FG)", responsible: "", dueDate: "" },
    { id: nextImplRowId(), department: "COS", yn: "Y", description: "Check sample orders which affected: material order of CKD", responsible: "", dueDate: "" },
    { id: nextImplRowId(), department: "COS", yn: "Y", description: "Confirm production scheduling according to the alignment, any changes share the information", responsible: "", dueDate: "" },
    { id: nextImplRowId(), department: "COS", yn: "Y", description: "Confirm the old stock / do prioritize delivery and inventory handling", responsible: "", dueDate: "" },
    { id: nextImplRowId(), department: "COS", yn: "Y", description: "Inform the first delivery to PMO", responsible: "", dueDate: "" },
    // Purchasing
    { id: nextImplRowId(), department: "Purchasing", yn: "Y", description: "Check sample orders which affected: material order of purchasing parts", responsible: "", dueDate: "" },
    { id: nextImplRowId(), department: "Purchasing", yn: "Y", description: "Inform internal related departments (COS, MFE, MOEx) with following requirements", responsible: "", dueDate: "" },
    { id: nextImplRowId(), department: "Purchasing", yn: "Y", description: "Update incoming inspection plan", responsible: "", dueDate: "" },
    // Quality
    { id: nextImplRowId(), department: "Quality", yn: "Y", description: "Update testing program on testing equipment", responsible: "", dueDate: "" },
    { id: nextImplRowId(), department: "Quality", yn: "Y", description: "Update inspection plan for CKD parts", responsible: "", dueDate: "" },
    // CPjM
    { id: nextImplRowId(), department: "CPjM", yn: "Y", description: "Distribute the Offer drawing, TCD to customer", responsible: "", dueDate: "" },
    // LOP
    { id: nextImplRowId(), department: "LOP", yn: "Y", description: "Check 10 digit material order", responsible: "", dueDate: "" },
    // PMO
    { id: nextImplRowId(), department: "PMO", yn: "Y", description: "Check sample orders which affected: Customer order", responsible: "", dueDate: "" },
    { id: nextImplRowId(), department: "PMO", yn: "Y", description: "Inform Customer the first delivery information", responsible: "", dueDate: "" },
    // Others
    { id: nextImplRowId(), department: "Others", yn: "", description: "", responsible: "", dueDate: "" },
  ]

  const storageKey = `pd-ecr-implementation-${module.id}`

  // ── State ──
  const [developmentConfirmation] = useState(() => {
    try { const p = JSON.parse(localStorage.getItem(storageKey) || ""); if (p?.developmentConfirmation) return p.developmentConfirmation } catch {}
    return ""
  })
  const [checklistRows, setChecklistRows] = useState<ImplRow[]>(() => {
    try {
      const p = JSON.parse(localStorage.getItem(storageKey) || "")
      if (p?.checklistRows?.length) {
        // Migrate old data: ensure every row has an id
        return p.checklistRows.map((r: ImplRow) => r.id ? r : { ...r, id: nextImplRowId() })
      }
    } catch {}
    return defaultChecklist
  })
  const [implementationDate] = useState(() => {
    try { const p = JSON.parse(localStorage.getItem(storageKey) || ""); if (p?.implementationDate) return p.implementationDate } catch {}
    return ""
  })
  const [saveStatus, setSaveStatus] = useState("Draft")
  const autoSaveTimer = useRef<ReturnType<typeof setTimeout>>(undefined)

  // Inner step expand/collapse
  const [expandedSteps, setExpandedSteps] = useState<Set<string>>(() => new Set(["step-6.1"]))
  const [expandedDepts, setExpandedDepts] = useState<Set<string>>(() => new Set(["dept-Development"]))
  const toggleStep = (stepId: string) => {
    setExpandedSteps((prev) => {
      const next = new Set(prev)
      if (next.has(stepId)) next.delete(stepId)
      else next.add(stepId)
      return next
    })
  }

  // ── Department list for Step 6.1 ──
  const departments = [...new Set(checklistRows.map((r) => r.department))]

  // ── Mutations ──
  const updateChecklist = (index: number, field: keyof ImplRow, value: string) => {
    setChecklistRows((prev) => prev.map((r, i) => i === index ? { ...r, [field]: value } : r))
  }
  const addChecklistItem = (dept: string) => {
    setChecklistRows((prev) => {
      const newRow: ImplRow = { id: nextImplRowId(), department: dept, yn: "", description: "", responsible: "", dueDate: "", result: "", resultNote: "" }
      // Insert after the last item of this department
      const lastIndex = prev.map((r) => r.department).lastIndexOf(dept)
      if (lastIndex >= 0) {
        const next = [...prev]
        next.splice(lastIndex + 1, 0, newRow)
        return next
      }
      return [...prev, newRow]
    })
  }
  // ── Auto-save ──
  useEffect(() => {
    const skip = !autoSaveTimer.current
    if (skip) { autoSaveTimer.current = setTimeout(() => {}, 0); return }
    setSaveStatus("Saving...")
    clearTimeout(autoSaveTimer.current)
    autoSaveTimer.current = setTimeout(() => {
      localStorage.setItem(storageKey, JSON.stringify({
        developmentConfirmation, checklistRows, implementationDate,
      }))
      setSaveStatus("Auto-saved")
      setTimeout(() => setSaveStatus("Draft"), 2000)
    }, 1000)
    return () => clearTimeout(autoSaveTimer.current)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [developmentConfirmation, checklistRows, implementationDate])

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-3">
        <span className="rounded-full border border-amber-200 bg-amber-50 px-3 py-1 text-xs font-semibold text-amber-700">{saveStatus}</span>
      </div>

      {/* ── Step 6.1: Implementation check list ── */}
      <div className="overflow-hidden rounded-lg border border-stone-200 bg-white shadow-sm">
        <button
          type="button"
          onClick={() => toggleStep("step-6.1")}
          className="flex w-full items-center justify-between bg-stone-800 px-4 py-2.5 text-sm font-semibold text-white hover:bg-stone-700 transition"
        >
          <span><span className="mr-2 text-amber-400">Step 6.1</span>Implementation check list / 导入清单</span>
          <ChevronDown className={`size-4 shrink-0 transition-transform duration-200 ${expandedSteps.has("step-6.1") ? "rotate-180" : ""}`} />
        </button>
        {expandedSteps.has("step-6.1") && (
          <div className="divide-y divide-stone-200">
            {departments.map((dept) => {
              const deptRows = checklistRows.filter((r) => r.department === dept)
              const deptKey = `dept-${dept}`
              const isDeptExpanded = expandedDepts.has(deptKey)
              const toggleDept = () => {
                setExpandedDepts((prev) => {
                  const next = new Set(prev)
                  if (next.has(deptKey)) next.delete(deptKey)
                  else next.add(deptKey)
                  return next
                })
              }
              return (
                <div key={dept}>
                  {/* ── Department header bar ── */}
                  <button
                    type="button"
                    onClick={toggleDept}
                    className="flex w-full items-center gap-2 bg-stone-100 px-4 py-2 text-left hover:bg-stone-200 transition cursor-pointer"
                  >
                    <ChevronDown className={`size-3.5 text-stone-500 shrink-0 transition-transform duration-200 ${isDeptExpanded ? "rotate-180" : ""}`} />
                    <span className="text-sm font-semibold text-stone-800">{dept}</span>
                    <span className="text-xs text-stone-400">({deptRows.length} items)</span>
                  </button>
                  {/* ── Department mini-table (with its own headers) ── */}
                  {isDeptExpanded && (
                    <div className="overflow-x-auto">
                      <table className="w-full text-left text-sm">
                        <thead>
                          <tr className="border-b border-stone-200 bg-amber-50/50 text-xs font-semibold uppercase text-stone-500">
                            <th className="w-8 px-2 py-2 text-center">#</th>
                            <th className="px-3 py-2">Description</th>
                            <th className="w-14 px-2 py-2 text-center">Y/N</th>
                            <th className="w-36 px-3 py-2">Responsible</th>
                            <th className="w-32 px-3 py-2">Due date</th>
                            <th className="w-28 px-3 py-2">STATUS</th>
                            <th className="w-40 px-3 py-2">Result</th>
                          </tr>
                        </thead>
                        <tbody>
                          {deptRows.map((row, idx) => {
                            const globalIndex = checklistRows.findIndex((r) => r.id === row.id)
                            return (
                              <tr key={row.id} className="border-b border-stone-100 even:bg-stone-50/50 hover:bg-amber-50/30 transition-colors">
                                <td className="px-2 py-2 text-center text-xs text-stone-400">
                                  {idx + 1}
                                </td>
                                <td className="px-3 py-2 text-xs leading-5 text-stone-700">
                                  {row.description || "-"}
                                </td>
                                <td className="px-2 py-2 text-center">
                                  <select
                                    value={row.yn}
                                    onChange={(e) => updateChecklist(globalIndex, "yn", e.target.value)}
                                    className="h-8 w-14 rounded border border-stone-200 bg-white px-1 text-xs outline-none focus:border-amber-400"
                                  >
                                    <option value="">-</option>
                                    <option value="Y">Y</option>
                                    <option value="N">N</option>
                                  </select>
                                </td>
                                <td className="px-3 py-2">
                                  <input
                                    value={row.responsible}
                                    onChange={(e) => updateChecklist(globalIndex, "responsible", e.target.value)}
                                    className="h-8 w-full rounded border border-stone-200 bg-white px-2 text-xs outline-none focus:border-amber-400"
                                    placeholder="Resp."
                                  />
                                </td>
                                <td className="px-3 py-2">
                                  <input
                                    type="date"
                                    value={row.dueDate}
                                    onChange={(e) => updateChecklist(globalIndex, "dueDate", e.target.value)}
                                    className="h-8 w-full rounded border border-stone-200 bg-white px-2 text-xs outline-none focus:border-amber-400"
                                  />
                                </td>
                                <td className="px-3 py-2">
                                  <select
                                    value={row.result || ""}
                                    onChange={(e) => updateChecklist(globalIndex, "result", e.target.value)}
                                    disabled={row.yn === "N"}
                                    className={`h-8 w-full rounded border px-1 text-xs font-semibold outline-none transition ${
                                      row.yn === "N"
                                        ? "border-stone-100 bg-stone-100 text-stone-300 cursor-not-allowed"
                                        : row.result === "Closed"
                                          ? "border-emerald-300 bg-emerald-50 text-emerald-700"
                                          : row.result === "Ongoing"
                                            ? "border-amber-300 bg-amber-50 text-amber-700"
                                            : row.result === "Open"
                                              ? "border-blue-300 bg-blue-50 text-blue-700"
                                              : "border-stone-200 bg-white"
                                    }`}
                                  >
                                    <option value="">-</option>
                                    <option value="Closed">Closed</option>
                                    <option value="Ongoing">Ongoing</option>
                                    <option value="Open">Open</option>
                                  </select>
                                </td>
                                <td className="px-3 py-2">
                                  <input
                                    value={row.resultNote || ""}
                                    onChange={(e) => updateChecklist(globalIndex, "resultNote", e.target.value)}
                                    className="h-8 w-full rounded border border-stone-200 bg-white px-2 text-xs outline-none focus:border-amber-400"
                                    placeholder="Result..."
                                  />
                                </td>
                              </tr>
                            )
                          })}
                        </tbody>
                      </table>
                      <button
                        type="button"
                        onClick={() => addChecklistItem(dept)}
                        className="flex w-full items-center justify-center gap-1 border-t border-stone-200 py-1.5 text-xs text-stone-400 hover:bg-stone-50 hover:text-stone-600 transition"
                      >
                        + 添加项
                      </button>
                    </div>
                  )}
                </div>
              )
            })}
          </div>
        )}
      </div>

    </div>
  )
}

export function FallbackView({ module }: { module: PdEcrDisplayModule }) {
  return (
    <div className="space-y-5">
      <GeneratedContent module={module} />
      <div className="overflow-hidden rounded-lg border border-stone-200">
        <table className="w-full border-collapse text-left text-sm">
          <thead>
            <tr className="bg-stone-100 text-stone-700">
              <th className="w-64 border-b border-stone-200 px-4 py-3 font-semibold">
                Field
              </th>
              <th className="border-b border-stone-200 px-4 py-3 font-semibold">
                Content
              </th>
            </tr>
          </thead>
          <tbody>
            {Object.entries(module.data).map(([key, value]) => (
              <tr key={key} className="bg-white even:bg-stone-50">
                <th className="border-t border-stone-200 px-4 py-3 align-top font-semibold text-amber-700">
                  {key}
                </th>
                <td className="whitespace-pre-wrap border-t border-stone-200 px-4 py-3 leading-7 text-stone-700">
                  {String(value)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}

export function renderModuleBody(module: PdEcrDisplayModule, hideApproval?: boolean) {
  switch (module.id) {
    case "change_description":
    case "change-description":
      return <ChangeDescriptionView module={module} />
    case "impact-analysis":
      return <ImpactAnalysisView module={module} hideApproval={hideApproval} />
    case "validation-plan":
      return <ValidationPlanView module={module} />
    case "validation-result":
      return <ValidationResultFunctionalView module={module} />
    case "implementation-plan":
      return <ImplementationView module={module} resultOnly={false} />
    case "implementation-result":
      return <ImplementationView module={module} resultOnly={true} />
    default:
      return (
        <div className="space-y-5">
          <GeneratedContent module={module} />
          <ToolFooter module={module} />
        </div>
      )
  }
}

function loadModule(moduleId: string): {
  module?: PdEcrDisplayModule
  reportUrl?: string
  source: "历史数据" | "AI 生成内容"
} {
  const active = loadActiveResult()
  const generated = loadGeneratedResult()
  const history = loadHistoryResult()
  const module =
    findModule(active, moduleId) ||
    findModule(generated, moduleId) ||
    findModule(history, moduleId)

  return {
    module,
    reportUrl: active.reportUrl || generated.reportUrl,
    source: active.source === "history" ? "历史数据" : "AI 生成内容",
  }
}

export function PdEcrModuleDetail({ moduleId }: { moduleId: string }) {
  const navigate = useNavigate()
  const { module, reportUrl, source } = useMemo(
    () => loadModule(moduleId),
    [moduleId],
  )
  const resolvedReportUrl = resolvePdEcrAssetUrl(reportUrl)

  if (!module) {
    return (
      <section className="min-h-[calc(100vh-7rem)] bg-stone-50 p-4">
        <div className="flex items-center gap-2">
          <Button variant="outline" onClick={() => navigate({ to: "/pd-ecr" })}>
            <ArrowLeft className="size-4" />
            回到主页
          </Button>
        </div>
        <div className="mt-6 rounded-lg border border-stone-200 bg-white p-8 shadow-sm">
          <h1 className="text-2xl font-semibold text-stone-800">模块不存在</h1>
          <p className="mt-3 text-stone-500">
            当前没有找到这个 PD-ECR 模块内容。
          </p>
        </div>
      </section>
    )
  }

  return (
    <section className="min-h-[calc(100vh-7rem)] bg-stone-50 text-stone-800">
      <div className="w-full min-w-0 space-y-5">
        <div className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-stone-200 bg-white px-4 py-3 shadow-sm">
          <div className="flex items-center gap-2">
            <Button
              variant="outline"
              onClick={() =>
                navigate({
                  to: "/pd-ecr/content",
                })
              }
            >
              <ArrowLeft className="size-4" />
              返回
            </Button>
            <Button
              variant="ghost"
              size="icon"
              onClick={() => navigate({ to: "/pd-ecr" })}
              aria-label="回到主页"
            >
              <Home className="size-5" />
            </Button>
          </div>
          <PdEcrProcessFlowButton />
          {resolvedReportUrl ? (
            <Button asChild className="bg-stone-800 hover:bg-stone-700">
              <a href={resolvedReportUrl} target="_blank" rel="noreferrer">
                <ExternalLink className="size-4" />
                打开完整报告
              </a>
            </Button>
          ) : null}
        </div>

        <article className="overflow-hidden rounded-lg border border-stone-200 bg-white shadow-sm">
          <div className="border-b border-stone-200 bg-white px-4 py-3">
            <div className="flex items-center gap-3">
              <div className="flex size-8 items-center justify-center rounded bg-amber-50 text-amber-600">
                <FileText className="size-4" />
              </div>
              <div>
                <p className="text-[11px] font-semibold uppercase tracking-wide text-amber-600">
                  {source}
                </p>
                <h1 className="text-lg font-semibold text-stone-900">
                  {module.title}
                </h1>
              </div>
            </div>
            <p className="mt-4 max-w-5xl text-base leading-7 text-stone-600">
              {module.summary}
            </p>
          </div>

          <div className="p-4 md:p-8">
            <SourceTracePanel module={module} />
            {renderModuleBody(module)}
          </div>
        </article>
      </div>
    </section>
  )
}
