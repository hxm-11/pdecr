import type {
  PdEcrGenerateResponse,
  PdEcrHistoryResponse,
  PdEcrModule,
  PdEcrModules,
} from "@/lib/pdEcrApi"

export const CHANGE_SOURCE_OPTIONS = [
  { value: "Customer request", label: "Customer request / 客户要求" },
  { value: "Supplier request", label: "Supplier request / 供应商请求" },
  { value: "Design optimization", label: "Design optimization / 设计优化" },
  { value: "Correction", label: "Correction / 更正(错误)" },
  { value: "Process", label: "Process / 工艺" },
  { value: "Other", label: "Other / 其它" },
] as const

export type PdEcrModuleId =
  | "basic_information"
  | "change_description"
  | "reason_for_change"
  | "impact_analysis"
  | "implementation_plan"
  | "approval_signoff_information"
  | "change-description"
  | "impact-analysis"
  | "validation-plan"
  | "execution-checklist"
  | "validation-result"
  | "implementation-plan"
  | "implementation-result"
  | "feasibility-confirmation"

export type PdEcrDisplayModule = {
  id: PdEcrModuleId
  title: string
  subtitle: string
  summary: string
  description?: string
  data: Record<string, unknown>
  sourceCases?: string[]
  sourceFiles?: string[]
  needsHumanInput?: boolean
  warnings?: string[]
}

export type PdEcrPdEcrCaseRow = {
  id: string
  backendCaseId?: string
  sourceDocumentId?: string
  isHistorical?: boolean
  createDate: string
  productClass: string
  from: string
  initiator: string
  customer: string
  project: string
  partNumber: string
  dept: string
  link: string
  sourceFile?: string
  pdfFile?: string
  pdfUrl?: string
  missingFields?: string[]
  dcNo?: string
  mcrNo?: string
  productNo?: string
  changeType?: string
  sampleStatus?: string
  sampleType?: string
  reasonForChange?: string
  similarity?: number
  matchedKeywords?: string[]
  status?: string
  rawStatus?: string
}

export type PdEcrApprovalSuggestion = {
  role: string
  field: string
  person: string
  source?: string
  evidence?: string
}

export type PdEcrStoredResult = {
  source: "history" | "generated"
  draftId?: string
  draftStatus?: string
  inputSnapshot?: Record<string, unknown>
  reportUrl?: string
  relatedCases: string[]
  modules: PdEcrDisplayModule[]
  caseRows?: PdEcrPdEcrCaseRow[]
  currentCase?: PdEcrPdEcrCaseRow
  approvalSuggestions?: PdEcrApprovalSuggestion[]
  approvalLeadDays?: number
}

const STORAGE_KEY = "pd-ecr-generated-result"
const HISTORY_STORAGE_KEY = "pd-ecr-history-result"
const ACTIVE_STORAGE_KEY = "pd-ecr-active-result"
const DEMO_FALLBACK_ENABLED = import.meta.env.VITE_PD_ECR_DEMO_FALLBACK === "1"

/** Shared utility to resolve a PDF URL from a case row, used by both PdEcrCaseList and PdEcrCreationWorkflow. */
export function resolveRowPdfUrl(row: PdEcrPdEcrCaseRow, apiBaseUrl?: string): string | null {
  const base = apiBaseUrl || ""

  if (row.pdfUrl) {
    return row.pdfUrl.startsWith("http") ? row.pdfUrl : `${base}${row.pdfUrl}`
  }

  const id = row.id || row.sourceFile || ""
  const match = id.match(/PDECR\d{2}[_-]\d{3}/i)
  if (match) {
    const pdfName = row.pdfFile || `${match[0]}.pdf`
    return `${base}/api/v1/pd-ecr/pdf/${encodeURIComponent(pdfName)}`
  }

  if (row.sourceFile?.toLowerCase().endsWith(".pdf")) {
    return `${base}/api/v1/pd-ecr/pdf/${encodeURIComponent(row.sourceFile)}`
  }

  return null
}

/** Check if a case row has an associated PDF file. */
export function hasPdfForRow(row: PdEcrPdEcrCaseRow): boolean {
  return Boolean(
    row.pdfUrl ||
    row.pdfFile ||
    row.id?.match(/PDECR\d{2}[_-]\d{3}/i) ||
    row.sourceFile?.toLowerCase().endsWith(".pdf"),
  )
}

// Case rows now come exclusively from the backend API (/api/v1/pd-ecr/cases)
// or from localStorage cache. When neither is available, an empty list is shown
// with an appropriate status message — no hardcoded fallback data.
export const realPdEcrCaseRows: PdEcrPdEcrCaseRow[] = []

export const pdEcrModuleMeta: Partial<
  Record<
    PdEcrModuleId,
    { title: string; backendKeys: string[]; subtitle: string }
  >
> = {
  basic_information: {
    title: "Change Request description",
    backendKeys: ["basic_information", "basic_info"],
    subtitle: "Content 1 / 6",
  },
  change_description: {
    title: "Impact analysis",
    backendKeys: ["change_description", "change-description"],
    subtitle: "Content 2 / 6",
  },
  reason_for_change: {
    title: "Validation &trial run plan",
    backendKeys: ["reason_for_change", "change_reason", "reason"],
    subtitle: "Content 3 / 6",
  },
  impact_analysis: {
    title: "Validation &Trial run plan result",
    backendKeys: ["impact_analysis", "impact-analysis"],
    subtitle: "Content 4 / 6",
  },
  implementation_plan: {
    title: "Implementation task plan",
    backendKeys: ["implementation_plan", "implementation-plan"],
    subtitle: "Content 5 / 6",
  },
  approval_signoff_information: {
    title: "Implementation result",
    backendKeys: ["approval_signoff_information", "approval_signature"],
    subtitle: "Content 6 / 6",
  },
  "change-description": {
    title: "Change Request description",
    backendKeys: ["basic_information", "basic_info", "change-description"],
    subtitle: "Content 1 / 4",
  },
  "impact-analysis": {
    title: "Impact analysis",
    backendKeys: ["change_description", "impact-analysis", "affection_analysis"],
    subtitle: "Content 2 / 4",
  },
  "validation-plan": {
    title: "Validation &trial run plan",
    backendKeys: ["reason_for_change", "validation-plan", "validation_plan"],
    subtitle: "Content 3 / 4",
  },
  "execution-checklist": {
    title: "执行清单",
    backendKeys: [
      "execution_checklist",
      "implementation_checklist",
      "approval_signature",
      "engineering_analysis",
    ],
    subtitle: "Execution checklist",
  },
  "validation-result": {
    title: "Validation &Trial run plan result",
    backendKeys: ["impact_analysis", "validation-result", "validation_result"],
    subtitle: "Content 4 / 6",
  },
  "implementation-plan": {
    title: "Implementation & Validation",
    backendKeys: [
      "implementation_plan",
      "implementation-plan",
      "approval_signoff_information",
      "implementation-result",
      "implementation_result",
    ],
    subtitle: "Content 4 / 4",
  },
  "implementation-result": {
    title: "Implementation result",
    backendKeys: [
      "approval_signoff_information",
      "implementation-result",
      "implementation_result",
    ],
    subtitle: "Content 6 / 6",
  },
  "feasibility-confirmation": {
    title: "可行性确认",
    backendKeys: ["feasibility_confirmation", "feasibility-confirmation"],
    subtitle: "Feasibility Confirmation",
  },
}

export const moduleOrder: PdEcrModuleId[] = [
  "change-description",
  "impact-analysis",
  "validation-plan",
  "implementation-plan",
  "feasibility-confirmation",
]

const demoFallbackHistoryModules: PdEcrDisplayModule[] = [
  {
    id: "change-description",
    title: "变更描述",
    subtitle: "Historical change description",
    summary:
      "历史案例显示：第二供应商切换时需说明供应商、材料状态和强度等级变化。",
    data: {
      历史摘要: "第二供应商切换，材料特性保持不变，强度等级提升。",
      关键字段: "供应商、强度等级、材料特性、产品影响范围",
    },
  },
  {
    id: "impact-analysis",
    title: "影响分析",
    subtitle: "Historical impact analysis",
    summary: "历史案例通常关注功能、可靠性、供应商件和制造装配测试影响。",
    data: {
      历史摘要: "需确认功能性能、可靠性、制造装配和供应商质量稳定性。",
      建议关注: "Function / Reliability / Supplier Part / Manufacturing",
    },
  },
  {
    id: "validation-plan",
    title: "验证计划",
    subtitle: "Historical validation plan",
    summary: "历史案例中常见验证包含样件确认、强度验证、装配验证和测试报告。",
    data: {
      历史摘要: "执行样件验证、强度等级确认、装配适配和测试报告归档。",
      输出物: "Validation result / Test report",
    },
  },
  {
    id: "implementation-plan",
    title: "实施与验证",
    subtitle: "Historical implementation and validation",
    summary: "历史案例执行项通常包括 BOM、供应商资料、导入日期和审批确认。",
    data: {
      历史摘要: "更新 BOM、供应商文件、质量检查项和导入计划。",
      责任部门: "Development / Purchasing / Quality / MFE",
    },
  },
  {
    id: "feasibility-confirmation",
    title: "可行性确认",
    subtitle: "Feasibility Confirmation",
    summary: "发起人确认变更可行性信息，并上传相关附件。",
    data: {
      状态: "需要人工输入",
    },
  },
]

export const fallbackHistoryModules: PdEcrDisplayModule[] =
  DEMO_FALLBACK_ENABLED ? demoFallbackHistoryModules : []

export const fallbackGeneratedModules: PdEcrDisplayModule[] = [
  {
    id: "change-description",
    title: "Change Request description",
    subtitle: "Content 1 / 4",
    summary: "等待生成变更请求描述。",
    data: {
      状态: "尚未生成",
    },
  },
  {
    id: "impact-analysis",
    title: "Impact analysis",
    subtitle: "Content 2 / 4",
    summary: "等待生成影响分析。",
    data: {
      状态: "尚未生成",
    },
  },
  {
    id: "validation-plan",
    title: "Validation & Trial Run Results",
    subtitle: "Content 3 / 4",
    summary: "等待生成验证和试运行结果。",
    data: {
      状态: "尚未生成",
    },
  },
  {
    id: "implementation-plan",
    title: "Implementation & Validation Results",
    subtitle: "Content 4 / 4",
    summary: "等待生成实施与验证结果。",
    data: {
      状态: "尚未生成",
    },
  },
  {
    id: "feasibility-confirmation",
    title: "可行性确认",
    subtitle: "Feasibility Confirmation",
    summary: "发起人确认变更可行性信息并上传附件，部门领导签字确认。",
    data: {
      状态: "需要人工输入",
    },
  },
]

const v01ModuleOrder: PdEcrModuleId[] = [
  "change-description",
  "impact-analysis",
  "validation-plan",
  "implementation-plan",
  "feasibility-confirmation",
]

const v01ModuleMeta: Partial<
  Record<PdEcrModuleId, { title: string; subtitle: string; summary: string }>
> = {
  basic_information: {
    title: "Basic Information",
    subtitle: "V1 module 1 / 6",
    summary: "PD-ECR 基础信息、编号、产品/零件、项目和草稿状态。",
  },
  change_description: {
    title: "Change Description",
    subtitle: "V1 module 2 / 6",
    summary: "当前设计、变更提案和变更描述。",
  },
  reason_for_change: {
    title: "Reason for Change",
    subtitle: "V1 module 3 / 6",
    summary: "变更原因及历史证据摘要。",
  },
  impact_analysis: {
    title: "Impact Analysis",
    subtitle: "V1 module 4 / 6",
    summary: "功能、可靠性、制造、供应商、BOM/图纸/文档影响分析。",
  },
  implementation_plan: {
    title: "Implementation Plan",
    subtitle: "V1 module 5 / 6",
    summary: "实施动作、验证计划、责任人与导入事项。",
  },
  approval_signoff_information: {
    title: "Approval / Sign-off Information",
    subtitle: "V1 module 6 / 6",
    summary: "签核参考信息；V1 不代表正式审批流。",
  },
  "change-description": {
    title: "Change Request description",
    subtitle: "Change Request description",
    summary:
      "变更来源、原因、发起人、当前方案、变更方案、影响部门和 before/after 信息。",
  },
  "impact-analysis": {
    title: "Impact analysis",
    subtitle: "Impact analysis",
    summary: "基于历史相似 CASE 生成影响分析答案，供业务工程师校准。",
  },
  "validation-plan": {
    title: "Validation &trial run plan",
    subtitle: "Validation &trial run plan",
    summary:
      "生成 QAC / validation plan，包括验证项、评价标准、完成日期、负责人和备注。",
  },
  "validation-result": {
    title: "Validation &Trial run plan result",
    subtitle: "Validation &Trial run plan result",
    summary: "记录 validation result、trial run result、OK/NOK、签字和日期。",
  },
  "implementation-plan": {
    title: "Implementation & Validation",
    subtitle: "Implementation & Validation",
    summary: "基于影响分析和历史 CASE 推荐实施、验证、责任人与结果跟踪。",
  },
  "feasibility-confirmation": {
    title: "可行性确认",
    subtitle: "Feasibility Confirmation",
    summary: "发起人确认变更可行性信息并上传附件，部门领导签字确认。",
  },
}

function cloneModuleForV01(
  id: PdEcrModuleId,
  source?: PdEcrDisplayModule,
): PdEcrDisplayModule {
  const meta = v01ModuleMeta[id] || {
    title: id,
    subtitle: id,
    summary: "暂无内容",
  }

  return {
    id,
    title: meta.title,
    subtitle: meta.subtitle,
    summary: cleanPdEcrDisplayText(
      source?.summary || source?.description,
      meta.summary,
    ),
    description: source?.description,
    data:
      source?.data && Object.keys(source.data).length
        ? {
            ...source.data,
            v01_module: meta.title,
          }
        : {
            module: meta.title,
            content: meta.summary,
          },
    sourceCases: source?.sourceCases,
    sourceFiles: source?.sourceFiles,
    needsHumanInput: source?.needsHumanInput,
    warnings: source?.warnings,
  }
}

function expandToV01Modules(
  modules: PdEcrDisplayModule[],
): PdEcrDisplayModule[] {
  const byId = new Map(modules.map((module) => [module.id, module]))
  const executionModule = byId.get("execution-checklist")

  const sourceByV01Id: Partial<Record<PdEcrModuleId, PdEcrDisplayModule>> = {
    "change-description":
      byId.get("change-description") ||
      byId.get("basic_information") ||
      byId.get("change_description"),
    "impact-analysis":
      byId.get("impact-analysis") ||
      byId.get("change_description") ||
      byId.get("impact_analysis"),
    "validation-plan":
      byId.get("validation-plan") ||
      byId.get("reason_for_change") ||
      byId.get("validation-plan"),
    "implementation-plan":
      byId.get("implementation-plan") ||
      byId.get("implementation_plan") ||
      byId.get("implementation-result") ||
      byId.get("approval_signoff_information") ||
      byId.get("validation-plan") ||
      executionModule,
  }

  return v01ModuleOrder.map((id) =>
    cloneModuleForV01(id, sourceByV01Id[id]),
  )
}

function stringifyValue(value: unknown): string {
  if (value === null || value === undefined || value === "") {
    return "-"
  }

  if (Array.isArray(value)) {
    return value.map(stringifyValue).join("；")
  }

  if (typeof value === "object") {
    return JSON.stringify(value)
  }

  return String(value)
}

function looksLikeMarkdownTemplate(value: string) {
  return (
    /^#{1,6}\s/m.test(value) ||
    /\|[^|\n]+\|[^|\n]*\|/.test(value) ||
    /^\s*\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)+\|?\s*$/m.test(value)
  )
}

export function cleanPdEcrDisplayText(value: unknown, fallback = "") {
  const text = stringifyValue(value).trim()
  if (!text || text === "-") return fallback

  if (looksLikeMarkdownTemplate(text)) {
    return fallback
  }

  return (
    text
      .replace(/[^\s,;|()<>[\]{}"']+\.md\b/gi, "")
      .replace(/^#{1,6}\s*/gm, "")
      .replace(/^\s*[-*+]\s+/gm, "")
      .replace(/\*\*(.+?)\*\*/g, "$1")
      .replace(/\*(.+?)\*/g, "$1")
      .replace(/`([^`]+)`/g, "$1")
      .replace(/\[(.+?)\]\(.*?\)/g, "$1")
      .replace(/\s+/g, " ")
      .trim() || fallback
  )
}

function normalizeData(module?: PdEcrModule): Record<string, string> {
  const source = module?.data ?? {}
  const entries = Object.entries(source)
    .map(([key, value]) => [key, stringifyValue(value)] as const)
    .filter(([, value]) => value !== "-")

  return Object.fromEntries(entries)
}

function pickBackendModule(
  modules: PdEcrModules | undefined,
  id: PdEcrModuleId,
): PdEcrModule | undefined {
  const directModule = modules?.[id]
  if (directModule) return directModule

  const meta = pdEcrModuleMeta[id]
  if (!meta) return undefined
  return meta.backendKeys.map((key) => modules?.[key]).find(Boolean)
}

function getModuleMeta(id: PdEcrModuleId): {
  title: string
  subtitle: string
  backendKeys: string[]
} {
  const directMeta = pdEcrModuleMeta[id]
  if (directMeta) return directMeta

  const displayMeta = v01ModuleMeta[id]
  if (displayMeta) {
    return {
      title: displayMeta.title,
      subtitle: displayMeta.subtitle,
      backendKeys: [],
    }
  }

  return {
    title: id,
    subtitle: id,
    backendKeys: [],
  }
}

function firstMeaningfulValue(data: Record<string, unknown>): string {
  return (
    Object.values(data)
      .map((value) => stringifyValue(value))
      .find((value) => value && value !== "-") ?? ""
  )
}

export function normalizeModules(
  modules: PdEcrModules | (PdEcrDisplayModule | PdEcrModule)[] | undefined,
  fallback: PdEcrDisplayModule[],
): PdEcrDisplayModule[] {
  if (Array.isArray(modules)) {
    const apiModules = modules as PdEcrModule[]
    const responseIds = apiModules
      .map((module) => module.id || module.module_id)
      .filter((id): id is PdEcrModuleId =>
        Boolean(id && v01ModuleOrder.includes(id as PdEcrModuleId)),
      )
    const ids = responseIds.length ? v01ModuleOrder : moduleOrder

    return ids.map((id): PdEcrDisplayModule => {
      const meta = getModuleMeta(id)
      const fallbackModule = fallback.find((module) => module.id === id)
      const backendModule = apiModules.find(
        (module) =>
          (module.id || module.module_id) === id ||
          meta.backendKeys?.includes(String(module.id || module.module_id)),
      )

      if (!backendModule) {
        return (
          fallbackModule || {
            id,
            title: meta.title,
            subtitle: meta.subtitle,
            summary: "暂无内容",
            data: {},
          }
        )
      }

      const rawData = backendModule.data || {}
      const data = {
        ...rawData,
        content:
          rawData.content ??
          backendModule.content ??
          backendModule.description ??
          backendModule.summary ??
          "",
        source_cases: backendModule.source_cases || rawData.source_cases || [],
        source_files: backendModule.source_files || rawData.source_files || [],
        needs_human_input:
          backendModule.needs_human_input ??
          rawData.needs_human_input ??
          false,
        warnings: backendModule.warnings || rawData.warnings || [],
      }

      return {
        id,
        title: meta.title,
        subtitle: backendModule.subtitle || meta.subtitle,
        summary: cleanPdEcrDisplayText(
          backendModule.summary ||
            backendModule.description ||
            firstMeaningfulValue(data),
          fallbackModule?.summary || "暂无内容",
        ),
        data,
        sourceCases: backendModule.source_cases || (data.source_cases as string[]),
        sourceFiles: backendModule.source_files || (data.source_files as string[]),
        needsHumanInput: Boolean(data.needs_human_input),
        warnings: backendModule.warnings || (data.warnings as string[]),
      }
    })
  }

  const objectIds = modules
    ? v01ModuleOrder.filter((id) => {
        const meta = pdEcrModuleMeta[id]
        return Boolean(
          modules[id] ||
            meta?.backendKeys.some((key) => Boolean(modules[key])),
        )
      })
    : []
  const ids = objectIds.length ? v01ModuleOrder : moduleOrder

  return ids.map((id) => {
    const meta = getModuleMeta(id)
    const fallbackModule = fallback.find((module) => module.id === id)
    const backendModule = pickBackendModule(modules, id)
    const data = normalizeData(backendModule)
    const summary = cleanPdEcrDisplayText(
      backendModule?.description || firstMeaningfulValue(data),
      fallbackModule?.summary || "暂无内容",
    )

    return {
      id,
      title: meta.title,
      subtitle:
        backendModule?.title || fallbackModule?.subtitle || meta.subtitle,
      summary,
      data: Object.keys(data).length > 0 ? data : fallbackModule?.data || {},
      sourceCases: fallbackModule?.sourceCases,
      sourceFiles: fallbackModule?.sourceFiles,
      needsHumanInput: fallbackModule?.needsHumanInput,
      warnings: fallbackModule?.warnings,
    }
  })
}

function safePick(record: Record<string, unknown>, keys: string[]): string {
  for (const key of keys) {
    const value = record[key]
    if (value !== undefined && value !== null && value !== "") {
      return stringifyValue(value)
    }
  }
  return ""
}

function truthyPick(record: Record<string, unknown>, keys: string[]): boolean {
  for (const key of keys) {
    const value = record[key]
    if (value === true) return true
    if (typeof value === "string" && ["true", "1", "yes"].includes(value.trim().toLowerCase())) {
      return true
    }
  }
  return false
}

const approvalFields: { role: string; field: string }[] = [
  { role: "Development", field: "approval_development_person" },
  { role: "Purchasing", field: "approval_purchasing_person" },
  { role: "MFE", field: "approval_mfe_person" },
  { role: "COS", field: "approval_cos_person" },
  { role: "Quality", field: "approval_quality_person" },
  { role: "CPJM", field: "approval_cpjm_person" },
  { role: "MOEX", field: "approval_moex_person" },
  { role: "LOG", field: "approval_log_person" },
]

function cleanApprovalPerson(value: unknown): string {
  const text = stringifyValue(value).trim()
  if (!text || text === "-") return ""

  return text.split("|")[0].replace(/_{2,}/g, "").trim()
}

function approvalSourceFromResult(item: unknown): string {
  if (!item || typeof item !== "object") return "Historical RAG"

  const record = item as Record<string, unknown>
  const metadata = (record.metadata || {}) as Record<string, unknown>

  return (
    safePick(record, ["source", "source_file", "document_name"]) ||
    safePick(metadata, ["source", "source_file", "document_name"]) ||
    "Historical RAG"
  )
}

function extractApprovalRecordFromText(text: string): Record<string, string> {
  const record: Record<string, string> = {}
  if (!text) return record

  for (const { field } of approvalFields) {
    const match = text.match(new RegExp(`${field}\\s*[:：]\\s*([^\\n\\r]+)`, "i"))
    const value = cleanApprovalPerson(match?.[1])
    if (value) record[field] = value
  }

  return record
}

function mergeApprovalRecord(
  target: Record<string, string>,
  source: Record<string, unknown>,
) {
  for (const { field } of approvalFields) {
    if (!target[field]) {
      const value = cleanApprovalPerson(source[field])
      if (value) target[field] = value
    }
  }
}

function buildApprovalSuggestions(
  response: PdEcrHistoryResponse,
): PdEcrApprovalSuggestion[] {
  const approvalRecord: Record<string, string> = {}
  const approvalTestResult = response.approval_test_result

  if (approvalTestResult && typeof approvalTestResult === "object") {
    mergeApprovalRecord(approvalRecord, approvalTestResult)
  }

  mergeApprovalRecord(
    approvalRecord,
    extractApprovalRecordFromText(response.rag_context || ""),
  )
  mergeApprovalRecord(
    approvalRecord,
    extractApprovalRecordFromText(response.rag_context_preview || ""),
  )

  const approvalResults = response.approval_results || []
  for (const item of approvalResults) {
    if (!item || typeof item !== "object") continue

    const record = item as Record<string, unknown>
    mergeApprovalRecord(approvalRecord, record)
    mergeApprovalRecord(
      approvalRecord,
      extractApprovalRecordFromText(stringifyValue(record.text)),
    )
  }

  const firstSource = approvalResults[0] || response.results?.[0]
  const source = approvalSourceFromResult(firstSource)

  return approvalFields.map(({ role, field }) => ({
    role,
    field,
    person: approvalRecord[field] || "",
    source,
    evidence: approvalRecord[field]
      ? "Historical structured approval fields"
      : "Waiting for historical approval match",
  }))
}

function uniqueStrings(values: unknown[]): string[] {
  return Array.from(
    new Set(
      values
        .flatMap((value) => (Array.isArray(value) ? value : [value]))
        .map((value) => stringifyValue(value).trim())
        .filter((value) => value && value !== "-"),
    ),
  )
}

export function normalizePdEcrCaseRow(
  item: unknown,
  index: number,
): PdEcrPdEcrCaseRow {
  if (!item || typeof item !== "object") {
    const id = stringifyValue(item) || `PD-ECR-${index + 1}`
    return {
      id,
      createDate: "-",
      productClass: "-",
      from: "Knowledge Base",
      initiator: "-",
      customer: "-",
      project: "-",
      partNumber: "-",
      dept: "-",
      link: "Open modules",
    }
  }

  const record = item as Record<string, unknown>
  const metadata = (record.metadata || {}) as Record<string, unknown>
  const isHistorical =
    truthyPick(record, ["is_historical", "isHistorical"]) ||
    truthyPick(metadata, ["is_historical", "isHistorical"])
  const rawStatus =
    safePick(record, ["raw_status", "rawStatus"]) ||
    safePick(metadata, ["raw_status", "rawStatus"]) ||
    safePick(record, ["status", "draft_status", "case_status"]) ||
    safePick(metadata, ["status", "draft_status", "case_status"])

  const id =
    safePick(record, [
      "case_no",
      "caseNo",
      "pd_ecr_no",
      "pdEcrNo",
      "dc_no",
      "document_name",
      "source",
      "source_file",
      "case_id",
      "id",
    ]) ||
    safePick(metadata, ["case_no", "caseNo", "document_name", "source", "file_name", "case_id"]) ||
    `PD-ECR-${index + 1}`
  const rawLink = safePick(record, ["link"])
  const link = rawLink.toLowerCase().includes("pdf")
    ? "Open modules"
    : rawLink || "Open modules"

  return {
    id,
    backendCaseId: safePick(record, ["id", "backend_case_id", "backendCaseId", "db_id", "uuid"]),
    isHistorical,
    sourceDocumentId:
      safePick(record, ["source_document_id", "sourceDocumentId", "source_doc_id"]) ||
      safePick(metadata, ["source_document_id", "sourceDocumentId", "source_doc_id"]),
    createDate:
      safePick(record, ["createDate", "create_date", "date"]) ||
      safePick(metadata, ["createDate", "create_date", "date"]) ||
      "-",
    productClass:
      safePick(record, [
        "productClass",
        "product_class",
        "product_no",
        "product",
      ]) ||
      safePick(metadata, [
        "productClass",
        "product_class",
        "product_no",
        "product",
      ]) ||
      "-",
    from:
      safePick(record, ["from", "source_type"]) ||
      safePick(metadata, ["from", "source_type"]) ||
      "Knowledge Base",
    initiator:
      safePick(record, ["initiator", "owner", "responsible_person"]) ||
      safePick(metadata, ["initiator", "owner", "responsible_person"]) ||
      "-",
    customer:
      safePick(record, ["customer", "customer_project"]) ||
      safePick(metadata, ["customer", "customer_project"]) ||
      "-",
    project:
      safePick(record, ["project", "customer_project"]) ||
      safePick(metadata, ["project", "customer_project"]) ||
      "-",
    partNumber:
      safePick(record, [
        "partNumber",
        "part_number",
        "part_no",
        "component_no",
      ]) ||
      safePick(metadata, [
        "partNumber",
        "part_number",
        "part_no",
        "component_no",
      ]) ||
      "-",
    productNo:
      safePick(record, ["productNo", "product_no"]) ||
      safePick(metadata, ["productNo", "product_no"]),
    dept:
      safePick(record, ["dept", "department"]) ||
      safePick(metadata, ["dept", "department"]) ||
      "-",
    sourceFile:
      safePick(record, ["sourceFile", "source_file", "document_name"]) ||
      safePick(metadata, ["sourceFile", "source_file", "document_name"]),
    pdfFile:
      safePick(record, ["pdfFile", "pdf_file"]) ||
      safePick(metadata, ["pdfFile", "pdf_file"]),
    pdfUrl:
      safePick(record, ["pdfUrl", "pdf_url"]) ||
      safePick(metadata, ["pdfUrl", "pdf_url"]),
    missingFields: uniqueStrings([
      record.missing_fields,
      record.missingFields,
      metadata.missing_fields,
      metadata.missingFields,
    ]),
    dcNo:
      safePick(record, ["dcNo", "dc_no"]) ||
      safePick(metadata, ["dcNo", "dc_no"]),
    mcrNo:
      safePick(record, ["mcrNo", "mcr_no"]) ||
      safePick(metadata, ["mcrNo", "mcr_no"]),
    changeType:
      safePick(record, ["changeType", "change_type"]) ||
      safePick(metadata, ["changeType", "change_type"]),
    sampleStatus:
      safePick(record, ["sampleStatus", "sample_status"]) ||
      safePick(metadata, ["sampleStatus", "sample_status"]),
    sampleType:
      safePick(record, ["sampleType", "sample_type"]) ||
      safePick(metadata, ["sampleType", "sample_type"]),
    reasonForChange:
      safePick(record, ["reasonForChange", "reason_for_change"]) ||
      safePick(metadata, ["reasonForChange", "reason_for_change"]),
    similarity:
      typeof record.similarity_score === "number"
        ? record.similarity_score
        : typeof record.score === "number"
          ? record.score
          : typeof metadata.score === "number"
            ? metadata.score
            : undefined,
    matchedKeywords:
      Array.isArray(record.matched_keywords)
        ? (record.matched_keywords as string[])
        : Array.isArray(record.matched_fields)
          ? (record.matched_fields as string[])
          : undefined,
    status: isHistorical ? "historical" : rawStatus,
    rawStatus,
    link,
  }
}

export function normalizePdEcrCaseRows(items: unknown[]): PdEcrPdEcrCaseRow[] {
  return items.map(normalizePdEcrCaseRow)
}

function extractPdEcrCaseRows(
  response: PdEcrHistoryResponse,
): PdEcrPdEcrCaseRow[] {
  const rawCases =
    (response as unknown as Record<string, unknown>).case_rows ||
    (response as unknown as Record<string, unknown>).cases ||
    response.results ||
    response.matched_files ||
    response.related_cases ||
    []

  if (!Array.isArray(rawCases) || rawCases.length === 0) {
    return []
  }

  return rawCases
    .slice(0, 20)
    .map(normalizePdEcrCaseRow)
}

export function buildHistoryResult(
  response: PdEcrHistoryResponse,
): PdEcrStoredResult {
  const caseRows = extractPdEcrCaseRows(response)

  return {
    source: "history",
    relatedCases: caseRows.map((row) => row.id),
    caseRows,
    approvalSuggestions: buildApprovalSuggestions(response),
    modules: expandToV01Modules(
      normalizeModules(response.modules, fallbackHistoryModules),
    ),
  }
}

export function buildGeneratedResult(
  response: PdEcrGenerateResponse,
): PdEcrStoredResult {
  const modulesFromResponse =
    response.modules ||
    (response.llm_result
      ? {
          change_description: {
            title: "变更描述",
            description: "AI 生成的变更描述",
            data: response.llm_result,
          },
          engineering_analysis: {
            title: "影响分析 / 验证计划",
            description: "AI 生成的工程分析、影响分析和验证计划",
            data: response.llm_result,
          },
          execution_checklist: {
            title: "执行清单",
            description: "AI 生成的执行清单",
            data: {
              implementation: response.implementation,
              example_of_affected_actions: response.example_of_affected_actions,
              revision_history: response.revision_history,
            },
          },
        }
      : undefined)

  const modules = expandToV01Modules(
    normalizeModules(modulesFromResponse, fallbackGeneratedModules),
  )
  const relatedCasesFromSimilar =
    response.similar_cases
      ?.map((item) => item.case_id || item.source_file || "")
      .filter(Boolean) || []
  const relatedCasesFromModules = uniqueStrings(
    modules.flatMap((module) => [
      module.sourceCases,
      module.data.source_cases,
      module.data.sourceCases,
    ]),
  )

  return {
    source: "generated",
    draftId: response.draft_id,
    draftStatus: response.draft_status,
    inputSnapshot: response.input_snapshot,
    reportUrl: response.url,
    relatedCases:
      relatedCasesFromSimilar.length > 0
        ? relatedCasesFromSimilar
        : relatedCasesFromModules.length > 0
          ? relatedCasesFromModules
          : response.url
            ? [response.url]
            : [],
    approvalLeadDays: response.approval_lead_days,
    modules,
  }
}

export function saveGeneratedResult(result: PdEcrStoredResult) {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(result))
  saveActiveResult(result)
}

export function saveHistoryResult(result: PdEcrStoredResult) {
  localStorage.setItem(HISTORY_STORAGE_KEY, JSON.stringify(result))
  saveActiveResult(result)
}

export function saveActiveResult(result: PdEcrStoredResult) {
  localStorage.setItem(ACTIVE_STORAGE_KEY, JSON.stringify(result))
}

export function loadGeneratedResult(): PdEcrStoredResult {
  return loadStoredResult(STORAGE_KEY, {
    source: "generated",
    relatedCases: [],
    modules: fallbackGeneratedModules,
  })
}

export function loadHistoryResult(): PdEcrStoredResult {
  return loadStoredResult(HISTORY_STORAGE_KEY, {
    source: "history",
    relatedCases: [],
    caseRows: [],
    approvalSuggestions: [],
    modules: fallbackHistoryModules,
  })
}

export function loadActiveResult(): PdEcrStoredResult {
  return loadStoredResult(ACTIVE_STORAGE_KEY, loadGeneratedResult())
}

export function getPdEcrActiveRecordId(result: PdEcrStoredResult = loadActiveResult()): string {
  const resolved =
    result.currentCase?.backendCaseId ||
    result.draftId ||
    result.currentCase?.id ||
    result.reportUrl ||
    result.relatedCases[0] ||
    result.source

  if (resolved) return resolved

  const draftKey = "pd-ecr-draft-record-id"
  const existing = localStorage.getItem(draftKey)
  if (existing) return existing

  const newId = `draft-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`
  localStorage.setItem(draftKey, newId)
  return newId
}

function loadStoredResult(
  key: string,
  fallback: PdEcrStoredResult,
): PdEcrStoredResult {
  const raw = localStorage.getItem(key)
  if (!raw) {
    return {
      ...fallback,
      modules: expandToV01Modules(fallback.modules),
    }
  }

  try {
    const parsed = JSON.parse(raw) as PdEcrStoredResult
    if (!parsed.modules?.length) {
      return {
        ...fallback,
        modules: expandToV01Modules(fallback.modules),
      }
    }
    const legacyRows = (
      parsed as unknown as { PdEcrCaseRows?: PdEcrPdEcrCaseRow[] }
    ).PdEcrCaseRows
    if (!parsed.caseRows?.length && legacyRows?.length) {
      parsed.caseRows = legacyRows
    }
    if (parsed.source === "history" && parsed.caseRows?.length) {
      parsed.relatedCases = parsed.caseRows.map((row) => row.id)
    }
    // No more hardcoded case rows — if the stored history has no cases,
    // keep what we have (empty) and let the UI show an appropriate message.
    if (parsed.source === "history" && !parsed.approvalSuggestions) {
      parsed.approvalSuggestions = []
    }
    parsed.modules = expandToV01Modules(parsed.modules)
    if (!parsed.relatedCases?.length) {
      parsed.relatedCases = uniqueStrings(
        parsed.modules.flatMap((module) => [
          module.sourceCases,
          module.data.source_cases,
          module.data.sourceCases,
        ]),
      )
    }
    return parsed
  } catch {
    return fallback
  }
}

export function findModule(
  result: PdEcrStoredResult,
  moduleId: string,
): PdEcrDisplayModule | undefined {
  return result.modules.find((module) => module.id === moduleId)
}
