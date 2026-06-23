import { useNavigate } from "@tanstack/react-router"
import {
  ArrowLeft,
  Clock3,
  ExternalLink,
  FileText,
  Home,
  Link2,
  Upload,
} from "lucide-react"
import { type ReactNode, useEffect, useMemo, useState } from "react"
import ReactMarkdown from "react-markdown"
import remarkGfm from "remark-gfm"
import { Button } from "@/components/ui/button"
import {
  getPdEcrModuleDraft,
  resolvePdEcrAssetUrl,
  savePdEcrModuleDraft,
} from "@/lib/pdEcrApi"
import { PdEcrProcessFlowButton } from "./PdEcrProcessFlow"
import {
  findModule,
  loadActiveResult,
  loadGeneratedResult,
  loadHistoryResult,
  saveActiveResult,
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

function ToolFooter() {
  return (
    <div className="mt-6 flex flex-wrap items-center gap-3 border-t border-stone-200 pt-4">
      <Button type="button" variant="outline" className="bg-white">
        <Upload className="size-4" />
        Upload files
      </Button>
      <Button type="button" variant="outline" className="bg-white">
        Export PD-ECR excel file
      </Button>
      <Button type="button" variant="outline" className="bg-white">
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

function firstDataValue(module: PdEcrDisplayModule, keys: string[]) {
  for (const key of keys) {
    const value = module.data[key]
    if (value !== undefined && value !== null && String(value).trim()) {
      return String(value)
    }
  }
  return ""
}

function SignatureDashboard({ module }: { module: PdEcrDisplayModule }) {
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

function FirstSignatureStatus({ module }: { module: PdEcrDisplayModule }) {
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
  const ragResults = Array.isArray(module.data.rag_retrieval_results)
    ? (module.data.rag_retrieval_results as Record<string, unknown>[])
    : []
  const aiPrompt = String(module.data.ai_prompt || "").trim()

  return (
    <div className="space-y-5">
      <section className="rounded-lg border border-stone-200 bg-white p-5">
        <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
          <div>
            <p className="text-xs font-semibold uppercase tracking-wide text-stone-500">
              Template rendered content
            </p>
            <h2 className="mt-1 text-xl font-semibold text-stone-900">
              {templateFile || "Generated module"}
            </h2>
          </div>
          {templateFile ? (
            <span className="rounded-full border border-amber-200 bg-amber-50 px-3 py-1 text-xs font-semibold text-amber-800">
              {templateFile}
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
                    {String(item.source_file || "")}
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

const departmentOptions = ["Sales", "ENG", "TEF", "Production", "QMM", "LOG"]

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

function getActiveRecordId() {
  const active = loadActiveResult()

  return (
    active.currentCase?.id ||
    active.reportUrl ||
    active.relatedCases[0] ||
    active.source ||
    "pd-ecr"
  )
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
  const [saveStatus, setSaveStatus] = useState("Auto-filled from history")
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
            <Button
              type="button"
              size="sm"
              className="bg-amber-600 hover:bg-amber-700"
              onClick={saveDraft}
            >
              Save changes
            </Button>
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
      <ToolFooter />
    </div>
  )
}

export function ImpactAnalysisView({ module }: { module: PdEcrDisplayModule }) {
  const impactRows = [
    "Function & Performance influenced",
    "Interface and Appearance influenced",
    "Reliability and robustness influenced",
    "Other component influenced",
    "Manufactory / assembly / testing influenced",
    "Influence on supplier part",
  ]
  const documentRows = [
    "Interface FMEA relevant / IFMEA",
    "Product FMEA relevant / DFMEA",
    "Special Characteristics relevant / PSC",
    "IMDS relevant",
    "Offer drawing relevant",
    "TCD relevant",
    "Norm, WB, HF relevant",
  ]

  return (
    <div className="grid gap-5 xl:grid-cols-[1fr_24rem]">
      <div className="space-y-5">
        <div className="overflow-hidden rounded-lg border border-stone-200">
          <table className="w-full border-collapse text-left text-sm">
            <thead className="bg-amber-600 text-white">
              <tr>
                <th className="px-3 py-2">Step 3.1 Impact analysis</th>
                <th className="px-3 py-2">No</th>
                <th className="px-3 py-2">Yes</th>
                <th className="px-3 py-2">Confirmed by</th>
              </tr>
            </thead>
            <tbody>
              {impactRows.map((row, index) => (
                <tr
                  key={row}
                  className="border-t border-stone-200 even:bg-stone-50"
                >
                  <td className="px-3 py-2">
                    {index + 1}. {row}
                  </td>
                  <td className="px-3 py-2">
                    <input type="checkbox" readOnly />
                  </td>
                  <td className="px-3 py-2">
                    <input
                      type="checkbox"
                      readOnly
                      defaultChecked={index === 0 || index === 4}
                    />
                  </td>
                  <td className="px-3 py-2 text-stone-500">Engineer</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <div className="overflow-hidden rounded-lg border border-stone-200">
          <table className="w-full border-collapse text-left text-sm">
            <thead className="bg-amber-600 text-white">
              <tr>
                <th className="px-3 py-2">Step 3.3 Affected documents Check</th>
                <th className="px-3 py-2">No</th>
                <th className="px-3 py-2">Yes</th>
                <th className="px-3 py-2">Resp. person</th>
                <th className="px-3 py-2">Due date</th>
              </tr>
            </thead>
            <tbody>
              {documentRows.map((row, index) => (
                <tr
                  key={row}
                  className="border-t border-stone-200 even:bg-stone-50"
                >
                  <td className="px-3 py-2">
                    {index + 1}. {row}
                  </td>
                  <td className="px-3 py-2">
                    <input
                      type="checkbox"
                      readOnly
                      defaultChecked={index > 2}
                    />
                  </td>
                  <td className="px-3 py-2">
                    <input
                      type="checkbox"
                      readOnly
                      defaultChecked={index <= 2}
                    />
                  </td>
                  <td className="px-3 py-2 text-stone-500">Resp.</td>
                  <td className="px-3 py-2 text-stone-500">Target date</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <GeneratedContent module={module} />
        <FirstSignatureStatus module={module} />
        <ToolFooter />
      </div>
      <SignatureDashboard module={module} />
      <AiTask>
        <ol className="list-decimal space-y-2 pl-5">
          <li>
            检索历史相似 CASE 的影响分析部分内容，自动生成影响分析问题条的答案。
          </li>
          <li>AI 再次检查工程师调整后的内容，推介后续相关措施。</li>
        </ol>
      </AiTask>
    </div>
  )
}

export function ValidationPlanView({ module }: { module: PdEcrDisplayModule }) {
  const rows = [
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
  ]
  return (
    <div className="grid gap-5 xl:grid-cols-[1fr_24rem]">
      <div className="space-y-5">
        <h2 className="text-3xl font-semibold">
          <span className="bg-yellow-200 px-1">
            QAC / Validation plan (with evaluation criteria)
          </span>{" "}
          in trial run:
        </h2>
        <div className="overflow-hidden rounded-lg border border-stone-200">
          <table className="w-full border-collapse text-left text-sm">
            <thead className="bg-amber-600 text-white">
              <tr>
                {[
                  "Validations",
                  "Evaluation criteria",
                  "Plan finish date",
                  "Resp. person",
                  "Comments",
                ].map((h) => (
                  <th key={h} className="px-3 py-2">
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => (
                <tr
                  key={row}
                  className="border-t border-stone-200 even:bg-stone-50"
                >
                  <td className="px-3 py-2">
                    <input type="checkbox" readOnly className="mr-2" />
                    {row}
                  </td>
                  <td className="px-3 py-2 text-stone-500">
                    AI suggested criteria
                  </td>
                  <td className="px-3 py-2 text-stone-500">Target date</td>
                  <td className="px-3 py-2 text-stone-500">Owner</td>
                  <td className="px-3 py-2 text-stone-500">Remark</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <GeneratedContent module={module} />
        <ToolFooter />
      </div>
      <SignatureDashboard module={module} />
      <AiTask>
        检索历史相似 CASE 的 validation plan 内容，自动生成各个 validation plan
        的内容，提供给业务工程师校准。
      </AiTask>
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
          <ToolFooter />
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
        <ToolFooter />
      </div>
      <SignatureDashboard module={module} />
    </div>
  )
}

export function ImplementationView({
  module,
  resultOnly = false,
}: {
  module: PdEcrDisplayModule
  resultOnly?: boolean
}) {
  const rows = [
    "Change BOMs & Drawings & Documents in POE system",
    "Inform documents update",
    "Update offer drawing, TCD, D-FMEA",
    "Norm, WB, HF",
    "MoC, IMDS",
    "Related equipment be ready on site",
    "Related program be ready",
    "Old tooling / cutting / fixture disposal",
    "Old materials disposal",
  ]
  return (
    <div className="grid gap-5 xl:grid-cols-[1fr_24rem]">
      <div className="space-y-5">
        <div className="overflow-hidden rounded-lg border border-stone-200">
          <table className="w-full border-collapse text-left text-sm">
            <thead className="bg-amber-600 text-white">
              <tr>
                {[
                  "Departments",
                  "Y/N",
                  "Description",
                  "Responsible",
                  "Due date",
                  "Implementation result",
                ].map((h) => (
                  <th key={h} className="px-3 py-2">
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {rows.map((row, index) => (
                <tr
                  key={row}
                  className="border-t border-stone-200 even:bg-stone-50"
                >
                  <td className="px-3 py-2 font-medium">
                    {index < 5 ? "Development" : "Manufacturing"}
                  </td>
                  <td className="px-3 py-2">{index % 3 === 0 ? "Y" : "N"}</td>
                  <td className="px-3 py-2">{row}</td>
                  <td className="px-3 py-2 text-stone-500">
                    {resultOnly ? "XXX" : "Resp."}
                  </td>
                  <td className="px-3 py-2 text-stone-500">
                    {resultOnly ? "Apr. 30" : "Target date"}
                  </td>
                  <td className="px-3 py-2 text-stone-500">
                    {resultOnly ? "Done" : "Closed / Ongoing / Open"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <GeneratedContent module={module} />
        <ToolFooter />
      </div>
      <div className="space-y-5">
        <SignatureDashboard module={module} />
        <div className="hidden rounded-lg border border-stone-200 bg-white p-4">
          <div className="flex items-start justify-between gap-3">
            <div>
              <p className="font-semibold">Dashboard</p>
              <h3 className="mt-3 text-xl font-semibold">
                Overdue of Measures
              </h3>
            </div>
            <StatusLights active={resultOnly ? "green" : "amber"} />
          </div>
          <div className="mt-4 flex gap-4 text-sm">
            <Clock3 className="size-10 text-amber-600" />
            <ul className="space-y-1">
              <li>Action 1: xxx Resp. xxx</li>
              <li>Action 2: xxx Resp. xxx</li>
              <li>Action 3: xxx Resp. xxx</li>
            </ul>
          </div>
        </div>
        <AiTask>
          {resultOnly
            ? "自动抓取措施状态，列出 overdue 措施，并自动 LINK OUTLOOK 提醒 RESP. 关于过期措施执行。"
            : "基于历史相似 CASE 和影响分析部分内容，AI 推荐执行措施供工程师校准。"}
        </AiTask>
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

function renderModuleBody(module: PdEcrDisplayModule) {
  switch (module.id) {
    case "change_description":
    case "change-description":
      return <ChangeDescriptionView module={module} />
    default:
      return (
        <div className="space-y-5">
          <GeneratedContent module={module} />
          <ToolFooter />
        </div>
      )
  }
}

function SourceTracePanel({ module }: { module: PdEcrDisplayModule }) {
  const sourceCases =
    module.sourceCases ||
    (Array.isArray(module.data.source_cases)
      ? (module.data.source_cases as string[])
      : [])
  const sourceFiles =
    module.sourceFiles ||
    (Array.isArray(module.data.source_files)
      ? (module.data.source_files as string[])
      : [])
  const warnings =
    module.warnings ||
    (Array.isArray(module.data.warnings)
      ? (module.data.warnings as string[])
      : [])
  const needsHumanInput = Boolean(
    module.needsHumanInput || module.data.needs_human_input,
  )

  return (
    <aside className="mb-5 rounded-lg border border-amber-200 bg-amber-50 p-4">
      <div className="flex flex-wrap items-center gap-2">
        <span className="rounded-full border border-amber-300 bg-white px-3 py-1 text-xs font-semibold text-amber-800">
          Source trace
        </span>
        {needsHumanInput ? (
          <span className="rounded-full border border-red-200 bg-red-50 px-3 py-1 text-xs font-semibold text-red-700">
            Needs human input
          </span>
        ) : null}
      </div>
      <div className="mt-3 grid gap-3 text-sm text-stone-700 md:grid-cols-2">
        <div>
          <p className="font-semibold text-stone-900">Source cases</p>
          <p className="mt-1 break-words">{sourceCases.join(", ") || "-"}</p>
        </div>
        <div>
          <p className="font-semibold text-stone-900">Source files</p>
          <p className="mt-1 break-words">{sourceFiles.join(", ") || "-"}</p>
        </div>
      </div>
      {warnings.length ? (
        <ul className="mt-3 list-disc space-y-1 pl-5 text-sm text-amber-900">
          {warnings.map((warning) => (
            <li key={warning}>{warning}</li>
          ))}
        </ul>
      ) : null}
    </aside>
  )
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
          <div className="border-b border-stone-200 bg-white p-6 md:p-8">
            <div className="flex flex-wrap items-start justify-between gap-4">
              <div>
                <p className="text-xs font-semibold uppercase tracking-[0.18em] text-amber-600">
                  {source}
                </p>
                <h1 className="mt-3 text-3xl font-semibold tracking-normal text-stone-900">
                  {module.title}
                </h1>
              </div>
              <div className="flex size-12 items-center justify-center rounded-lg bg-amber-50 text-amber-600">
                <FileText className="size-6" />
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
