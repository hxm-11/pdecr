import { AlertCircle, CheckCircle2, ChevronDown, ChevronLeft, ChevronRight, CircleDashed, FileText, UserCheck } from "lucide-react"
import { type ReactNode, useEffect, useRef, useState } from "react"
import { Button } from "@/components/ui/button"
import { loadActiveResult, type PdEcrDisplayModule } from "./pdEcrState"
import { PdEcrExecutionWorkflowPanel } from "./PdEcrExecutionWorkflowPanel"
import { renderModuleBody } from "./PdEcrModuleDetail"

// ── Simplified module list ──
const ACCORDION_MODULE_IDS = [
  "change-description",
  "impact-analysis",
  "validation-plan",
  "implementation-plan",
] as const

const MODULE_LABELS: Record<string, { title: string; subtitle: string }> = {
  "change-description": { title: "1.1 变更描述", subtitle: "Change Description" },
  "impact-analysis": { title: "1.2 影响分析", subtitle: "Impact Analysis" },
  "validation-plan": { title: "1.3 QAC & 验证计划", subtitle: "QAC & Validation Plan" },
  "implementation-plan": { title: "1.4 执行计划", subtitle: "Implementation & Plan" },
}

const RESULT_MODULE_LABELS: Record<string, { title: string; subtitle: string }> = {
  "validation-plan": { title: "3.1 QAC & Validation results", subtitle: "Validation Results" },
  "implementation-plan": { title: "3.2 Implementation results", subtitle: "Implementation Results" },
}

function HistoricalReferencePanel() {
  return (
    <div className="sticky top-4 rounded-lg border border-sky-200 bg-sky-50 p-4 text-sm text-sky-800">
      <div className="flex items-center gap-2 font-semibold text-sky-900">
        <FileText className="size-4" />
        Historical reference
      </div>
      <p className="mt-2 text-xs leading-5">
        This source case is opened from the historical knowledge base. Workflow
        publish, assignment, and approval actions are available only for saved
        active PD-ECR cases.
      </p>
    </div>
  )
}

type ModuleCompletionState = {
  label: "Complete" | "Needs input" | "Empty"
  detail: string
  className: string
  icon: ReactNode
}

function safeParseJson(value: string | null) {
  if (!value) return undefined
  try {
    return JSON.parse(value) as Record<string, unknown>
  } catch {
    return undefined
  }
}

function textValue(...values: unknown[]) {
  for (const value of values) {
    const text = String(value ?? "").trim()
    if (text) return text
  }
  return ""
}

function hasGeneratedContent(module: PdEcrDisplayModule) {
  return Boolean(
    module.data &&
      Object.keys(module.data).length > 0 &&
      (module.summary || String(module.data.content || "").trim()),
  )
}

function activeRecordIdForStatus() {
  const active = loadActiveResult()
  return (
    active.currentCase?.id ||
    active.reportUrl ||
    active.relatedCases[0] ||
    active.source ||
    localStorage.getItem("pd-ecr-draft-record-id") ||
    "generated"
  )
}

function completionState(label: ModuleCompletionState["label"], detail: string): ModuleCompletionState {
  if (label === "Complete") {
    return {
      label,
      detail,
      className: "border-emerald-200 bg-emerald-50 text-emerald-800",
      icon: <CheckCircle2 className="size-3.5" />,
    }
  }
  if (label === "Needs input") {
    return {
      label,
      detail,
      className: "border-amber-200 bg-amber-50 text-amber-800",
      icon: <AlertCircle className="size-3.5" />,
    }
  }
  return {
    label,
    detail,
    className: "border-stone-200 bg-stone-50 text-stone-500",
    icon: <CircleDashed className="size-3.5" />,
  }
}

function changeDescriptionStatus(module: PdEcrDisplayModule) {
  const recordId = activeRecordIdForStatus()
  const stored = safeParseJson(
    localStorage.getItem(`pd-ecr-change-description-draft:${recordId}:${module.id}`),
  )
  const data = module.data || {}
  const values = {
    summary: textValue(stored?.changeSummary, data.change_proposal, data.summary, module.summary),
    reason: textValue(stored?.reason, data.change_reason, data.reason_for_change),
    part: textValue(stored?.partNumber, data.component_no, data.part_no, data.product_no),
    initiator: textValue(stored?.initiator, data.initiator),
    department: textValue(
      Array.isArray(stored?.departments) ? stored?.departments.join(", ") : stored?.departments,
      stored?.department,
      data.affected_departments,
      data.department,
    ),
  }
  const filled = Object.values(values).filter(Boolean).length
  if (!filled && !hasGeneratedContent(module)) return completionState("Empty", "No change description yet")

  const missing = Object.entries(values)
    .filter(([, value]) => !value)
    .map(([key]) => key)
  if (missing.length) {
    return completionState("Needs input", `Missing ${missing.slice(0, 2).join(", ")}`)
  }
  return completionState("Complete", "Core change fields ready")
}

function impactAnalysisStatus(module: PdEcrDisplayModule) {
  const draft = safeParseJson(localStorage.getItem(`pd-ecr-impact-analysis-${module.id}`))
  const impacts = Array.isArray(draft?.impacts) ? draft.impacts as Array<Record<string, unknown>> : []
  if (!impacts.length) {
    return hasGeneratedContent(module)
      ? completionState("Needs input", "Impact matrix not reviewed")
      : completionState("Empty", "No impact analysis yet")
  }

  const unselected = impacts.filter((row) => !row.no && !row.yes).length
  const yesWithoutMeasure = impacts.filter((row) => row.yes && !textValue(row.desc)).length
  if (unselected || yesWithoutMeasure) {
    const parts = []
    if (unselected) parts.push(`${unselected} unselected`)
    if (yesWithoutMeasure) parts.push(`${yesWithoutMeasure} Yes missing measures`)
    return completionState("Needs input", parts.join(", "))
  }
  return completionState("Complete", `${impacts.length} impact item${impacts.length > 1 ? "s" : ""} reviewed`)
}

function validationPlanStatus(module: PdEcrDisplayModule) {
  const draft = safeParseJson(localStorage.getItem(`pd-ecr-validation-plan-${module.id}`))
  const rows = Array.isArray(draft?.rows) ? draft.rows as Array<Record<string, unknown>> : []
  const selected = rows.filter((row) => Boolean(row.checked))

  const impactDraft = safeParseJson(localStorage.getItem("pd-ecr-impact-analysis-impact-analysis"))
  const impactRows = Array.isArray(impactDraft?.impacts) ? impactDraft.impacts as Array<Record<string, unknown>> : []
  const customMeasureIndexes = impactRows
    .map((row, index) => (row.yes && textValue(row.desc) ? index : -1))
    .filter((index) => index >= 0)
  const customRows = draft?.customRows && typeof draft.customRows === "object"
    ? draft.customRows as Record<string, Record<string, unknown>>
    : {}

  const selectedMissing = selected.filter((row) => !textValue(row.respPerson) || !textValue(row.finishDate)).length
  const customMissing = customMeasureIndexes.filter((index) => {
    const row = customRows[`impact-${index}`]
    if (row?.checked === false) return false
    return !textValue(row?.respPerson) || !textValue(row?.finishDate)
  }).length

  if (!rows.length && !customMeasureIndexes.length) {
    return hasGeneratedContent(module)
      ? completionState("Needs input", "No validation item selected")
      : completionState("Empty", "No validation plan yet")
  }
  if (!selected.length && !customMeasureIndexes.length) {
    return completionState("Needs input", "Select at least one validation item")
  }
  if (selectedMissing || customMissing) {
    const total = selectedMissing + customMissing
    return completionState("Needs input", `${total} validation item${total > 1 ? "s" : ""} missing owner/date`)
  }
  return completionState("Complete", `${selected.length + customMeasureIndexes.length} validation item${selected.length + customMeasureIndexes.length > 1 ? "s" : ""} planned`)
}

function implementationPlanStatus(module: PdEcrDisplayModule) {
  const draft = safeParseJson(localStorage.getItem(`pd-ecr-implementation-${module.id}`))
  const rows = Array.isArray(draft?.checklistRows) ? draft.checklistRows as Array<Record<string, unknown>> : []
  if (!rows.length) {
    return hasGeneratedContent(module)
      ? completionState("Needs input", "Implementation checklist not reviewed")
      : completionState("Empty", "No implementation plan yet")
  }

  const activeRows = rows.filter((row) => String(row.yn || "").toUpperCase() === "Y")
  const missing = activeRows.filter((row) =>
    !textValue(row.description) || !textValue(row.responsible) || !textValue(row.dueDate),
  ).length

  if (!activeRows.length) {
    return completionState("Needs input", "No active implementation item")
  }
  if (missing) {
    return completionState("Needs input", `${missing} Y item${missing > 1 ? "s" : ""} missing owner/date`)
  }
  return completionState("Complete", `${activeRows.length} implementation item${activeRows.length > 1 ? "s" : ""} ready`)
}

function getModuleCompletionState(module: PdEcrDisplayModule): ModuleCompletionState {
  if (module.needsHumanInput) {
    return completionState("Needs input", "AI marked this module for review")
  }

  switch (module.id) {
    case "change-description":
    case "change_description":
      return changeDescriptionStatus(module)
    case "impact-analysis":
      return impactAnalysisStatus(module)
    case "validation-plan":
      return validationPlanStatus(module)
    case "implementation-plan":
      return implementationPlanStatus(module)
    default:
      return hasGeneratedContent(module)
        ? completionState("Complete", "Content available")
        : completionState("Empty", "No content yet")
  }
}

// ── Accordion item ──
function AccordionItem({
  module,
  isExpanded,
  onToggle,
  label,
  mode = "plan",
}: {
  module: PdEcrDisplayModule
  isExpanded: boolean
  onToggle: () => void
  label: { title: string; subtitle: string }
  mode?: "plan" | "result"
}) {
  const [statusRevision, setStatusRevision] = useState(0)
  const hasContent = hasGeneratedContent(module)
  const state = getModuleCompletionState(module)

  useEffect(() => {
    const refresh = () => setStatusRevision((value) => value + 1)
    const timer = window.setInterval(refresh, 2000)
    window.addEventListener("storage", refresh)
    window.addEventListener("pd-ecr-impacts-updated", refresh)
    return () => {
      window.clearInterval(timer)
      window.removeEventListener("storage", refresh)
      window.removeEventListener("pd-ecr-impacts-updated", refresh)
    }
  }, [])

  void statusRevision

  return (
    <div className="overflow-hidden rounded-lg border border-stone-200 bg-white shadow-sm">
      {/* ── Header ── */}
      <button
        type="button"
        onClick={onToggle}
        className={`flex w-full items-center gap-4 px-5 py-4 text-left transition hover:bg-stone-50 ${
          isExpanded ? "border-b border-stone-200 bg-stone-50/50" : ""
        }`}
      >
        <div
          className={`flex size-10 shrink-0 items-center justify-center rounded-lg ${
            hasContent
              ? "bg-amber-50 text-amber-700"
              : "bg-stone-100 text-stone-400"
          }`}
        >
          <FileText className="size-5" />
        </div>

        <div className="min-w-0 flex-1">
          <p className="text-xs font-semibold uppercase tracking-wide text-stone-500">
            {label.subtitle}
          </p>
          <h3 className="text-lg font-semibold tracking-normal text-stone-900">
            {label.title}
          </h3>
          {!isExpanded && (
            <p className="mt-1 line-clamp-2 text-sm leading-6 text-stone-500">
              {module.summary || "暂无内容 — 点击展开"}
            </p>
          )}
        </div>

        <div className="hidden shrink-0 flex-col items-end gap-1 md:flex">
          <span className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs font-semibold ${state.className}`}>
            {state.icon}
            {state.label}
          </span>
          {state.detail ? (
            <span className="max-w-52 truncate text-[11px] font-medium text-stone-500" title={state.detail}>
              {state.detail}
            </span>
          ) : null}
          {module.warnings?.length ? (
            <span className="text-[11px] font-medium text-amber-700">
              {module.warnings.length} warning{module.warnings.length > 1 ? "s" : ""}
            </span>
          ) : null}
        </div>

        <ChevronDown
          className={`size-5 shrink-0 text-stone-400 transition-transform duration-200 ${
            isExpanded ? "rotate-180" : ""
          }`}
        />
      </button>

      {/* ── Body ── */}
      {isExpanded && (
        <div className="p-4 md:p-6">
          <p className="mb-5 max-w-5xl text-base leading-7 text-stone-600">
            {module.summary}
          </p>

          {renderModuleBody(module, true, mode)}

          {/* Implementation view now handles all steps internally */}
        </div>
      )}
    </div>
  )
}

export function PdEcrResultModuleAccordion({ modules }: { modules: PdEcrDisplayModule[] }) {
  const [expandedId, setExpandedId] = useState<string | null>("validation-plan")
  const resultModules = ["validation-plan", "implementation-plan"]
    .map((id) => modules.find((module) => module.id === id))
    .filter(Boolean) as PdEcrDisplayModule[]

  if (!resultModules.length) {
    return (
      <div className="rounded-lg border border-stone-200 bg-white p-8 text-center text-stone-500">
        No result modules available.
      </div>
    )
  }

  return (
    <div className="space-y-3">
      {resultModules.map((module) => (
        <AccordionItem
          key={module.id}
          module={module}
          label={RESULT_MODULE_LABELS[module.id] || { title: module.title, subtitle: module.subtitle }}
          isExpanded={expandedId === module.id}
          onToggle={() => setExpandedId((current) => current === module.id ? null : module.id)}
          mode="result"
        />
      ))}
    </div>
  )
}

// ── Result row types ──
type ValResultRow = { id?: string; label: string; checked: boolean; finishDate: string; respPerson: string; comments: string }
type ValResultDetail = { date: string; item: string; result: string; signer: string; status: string }
type ImplResultRow = { id?: string; department: string; yn: string; description: string; responsible: string; dueDate: string; result?: string; resultNote?: string }

function loadValidationResults(moduleId: string): ValResultRow[] {
  try {
    const raw = localStorage.getItem(`pd-ecr-validation-plan-${moduleId}`)
    if (raw) {
      const parsed = JSON.parse(raw)
      if (parsed?.rows?.length) return parsed.rows
    }
  } catch { /* ignore */ }
  return []
}

function loadValidationResultDetails(moduleId: string): ValResultDetail[] {
  try {
    const raw = localStorage.getItem(`pd-ecr-validation-result-${moduleId}`)
    if (raw) {
      const parsed = JSON.parse(raw)
      if (Array.isArray(parsed) && parsed.length) return parsed as ValResultDetail[]
    }
  } catch { /* ignore */ }
  return []
}

function loadImplementationResults(moduleId: string) {
  try {
    const raw = localStorage.getItem(`pd-ecr-implementation-${moduleId}`)
    if (raw) {
      const parsed = JSON.parse(raw)
      if (parsed?.checklistRows?.length) {
        return {
          checklistRows: parsed.checklistRows as ImplResultRow[],
          developmentConfirmation: parsed.developmentConfirmation || "",
          implementationDate: parsed.implementationDate || "",
        }
      }
    }
  } catch { /* ignore */ }
  return { checklistRows: [] as ImplResultRow[], developmentConfirmation: "", implementationDate: "" }
}

// ── Result signers ──
const RESULT_SIGNER_ROLES = [
  "PD-ECR Initiator's manager",
  "Initiator's HoD",
  "Business owner/Product owner (HoD)",
] as const

type ResultSignerRow = { person: string; date: string }

function loadResultSigners(): ResultSignerRow[] {
  try {
    const raw = localStorage.getItem("pd-ecr-result-signers")
    if (raw) {
      const parsed = JSON.parse(raw)
      if (parsed?.signers?.length === 3) return parsed.signers
    }
  } catch { /* ignore */ }
  return RESULT_SIGNER_ROLES.map(() => ({ person: "", date: "" }))
}

function saveResultSigners(signers: ResultSignerRow[]) {
  localStorage.setItem("pd-ecr-result-signers", JSON.stringify({ signers }))
}

// ── Result signer panel (right side, sticky) ──
function ResultSignerPanel() {
  const [signers, setSigners] = useState<ResultSignerRow[]>(() => loadResultSigners())
  const autoSaveTimer = useRef<ReturnType<typeof setTimeout>>(undefined)

  useEffect(() => {
    const skip = !autoSaveTimer.current
    if (skip) { autoSaveTimer.current = setTimeout(() => {}, 0); return }
    clearTimeout(autoSaveTimer.current)
    autoSaveTimer.current = setTimeout(() => {
      saveResultSigners(signers)
    }, 1000)
    return () => clearTimeout(autoSaveTimer.current)
  }, [signers])

  const updateSigner = (i: number, value: string) => {
    setSigners((prev) =>
      prev.map((r, j) => {
        if (j !== i) return r
        const next = { ...r, person: value }
        if (value.trim()) {
          const now = new Date()
          next.date = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}-${String(now.getDate()).padStart(2, "0")} ${String(now.getHours()).padStart(2, "0")}:${String(now.getMinutes()).padStart(2, "0")}:${String(now.getSeconds()).padStart(2, "0")}`
        } else {
          next.date = ""
        }
        return next
      })
    )
  }

  return (
    <div className="sticky top-4 space-y-4" style={{ maxHeight: "calc(100vh - 8rem)", overflowY: "auto" }}>
      <div className="rounded-lg border border-amber-300 bg-white shadow-sm">
        <div className="rounded-t-lg bg-amber-600 px-4 py-2.5 text-sm font-semibold text-white">
          Result Sign-off / 结果签核
        </div>
        <div className="divide-y divide-stone-100">
          {RESULT_SIGNER_ROLES.map((role, i) => (
            <div key={role} className="px-4 py-2.5">
              <p className="text-xs font-semibold text-stone-700">{role}</p>
              <input
                value={signers[i].person}
                onChange={(e) => updateSigner(i, e.target.value)}
                className="mt-1 h-8 w-full rounded border border-stone-200 bg-white px-2 text-xs outline-none focus:border-amber-400"
                placeholder="签字人..."
              />
              {signers[i].date ? (
                <p className="mt-1 text-[10px] font-medium text-emerald-600">✓ {signers[i].date}</p>
              ) : (
                <p className="mt-1 text-[10px] text-stone-300">待签字</p>
              )}
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}

// ── Collapsible result section ──
function CollapsibleResultSection({
  title,
  defaultExpanded = true,
  children,
}: {
  title: ReactNode
  defaultExpanded?: boolean
  children: ReactNode
}) {
  const [expanded, setExpanded] = useState(defaultExpanded)

  return (
    <div className="overflow-hidden rounded-lg border border-stone-200 bg-white shadow-sm">
      <button
        type="button"
        onClick={() => setExpanded((v) => !v)}
        className="flex w-full items-center justify-between bg-stone-800 px-4 py-2.5 text-sm font-semibold text-white hover:bg-stone-700 transition"
      >
        <span>{title}</span>
        <ChevronDown className={`size-4 shrink-0 transition-transform duration-200 ${expanded ? "rotate-180" : ""}`} />
      </button>
      {expanded && children}
    </div>
  )
}

// ── Result view (shown after all approvers confirmed) ──
export function ResultView({ modules }: { modules: PdEcrDisplayModule[] }) {
  const valModule = modules.find((m) => m.id === "validation-plan")
  const implModule = modules.find((m) => m.id === "implementation-plan")

  const valRows = valModule ? loadValidationResults(valModule.id) : []
  const valResultDetails = valModule ? loadValidationResultDetails(valModule.id) : []
  const implData = implModule ? loadImplementationResults(implModule.id) : { checklistRows: [] as ImplResultRow[], developmentConfirmation: "", implementationDate: "" }
  return (
    <div className="space-y-4">
      {/* ── QAC & Validation result ── */}
      <CollapsibleResultSection title={<span><span className="mr-2 text-amber-400">Result</span>QAC &amp; Validation result</span>}>
        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead>
              <tr className="border-b-2 border-stone-200 bg-stone-50 text-xs font-semibold uppercase text-stone-500">
                <th className="w-8 px-3 py-2.5">☑</th>
                <th className="px-3 py-2.5">Validation / 验证项目</th>
                <th className="w-32 px-3 py-2.5">Plan finish date</th>
                <th className="w-28 px-3 py-2.5">Resp. person</th>
                <th className="px-3 py-2.5">Comments / 备注</th>
                <th className="w-20 px-3 py-2.5 text-center">OK/NOK</th>
                <th className="px-3 py-2.5">Result / 结果</th>
                <th className="w-28 px-3 py-2.5">Signer / 签字人</th>
                <th className="w-28 px-3 py-2.5">Date</th>
              </tr>
            </thead>
            <tbody>
              {valRows.length ? valRows.map((row, i) => {
                const detail = valResultDetails.find((d) => d.item === row.label)
                return (
                <tr key={row.id || i} className="border-b border-stone-100 even:bg-stone-50/50">
                  <td className="px-3 py-2.5 text-center">
                    <span className={`inline-flex size-4 items-center justify-center rounded text-xs font-bold ${row.checked ? "bg-emerald-100 text-emerald-700" : "bg-stone-100 text-stone-400"}`}>
                      {row.checked ? "✓" : "—"}
                    </span>
                  </td>
                  <td className="px-3 py-2.5 text-sm font-medium text-stone-800">{row.label}</td>
                  <td className="px-3 py-2.5 text-xs text-stone-600">{row.finishDate || "-"}</td>
                  <td className="px-3 py-2.5 text-xs text-stone-600">{row.respPerson || "-"}</td>
                  <td className="px-3 py-2.5 text-xs text-stone-600">{row.comments || "-"}</td>
                  <td className="px-3 py-2.5 text-center">
                    {detail ? (
                      <span className={`inline-flex items-center rounded px-1.5 py-0.5 text-[10px] font-bold ${
                        detail.status === "OK" ? "bg-emerald-100 text-emerald-700" :
                        detail.status === "NOK" ? "bg-red-100 text-red-700" :
                        detail.status === "N/A" ? "bg-amber-100 text-amber-700" :
                        "bg-stone-100 text-stone-400"
                      }`}>
                        {detail.status || "—"}
                      </span>
                    ) : (
                      <span className="text-xs text-stone-300">—</span>
                    )}
                  </td>
                  <td className="px-3 py-2.5 text-xs text-stone-600 whitespace-pre-wrap">{detail?.result || "-"}</td>
                  <td className="px-3 py-2.5 text-xs text-stone-600">{detail?.signer || "-"}</td>
                  <td className="px-3 py-2.5 text-xs text-stone-600">{detail?.date || "-"}</td>
                </tr>
              )}) : (
                <tr>
                  <td colSpan={9} className="px-3 py-8 text-center text-sm text-stone-400">暂无验证计划数据</td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </CollapsibleResultSection>

      {/* ── Implementation & Plan result ── */}
      <CollapsibleResultSection title={<span><span className="mr-2 text-amber-400">Result</span>Implementation &amp; Plan result</span>}>
        {implData.developmentConfirmation && (
          <div className="border-b border-stone-200 bg-amber-50/50 px-4 py-3">
            <p className="text-xs font-semibold text-stone-500">Development confirmation</p>
            <p className="mt-1 text-sm text-stone-800 whitespace-pre-wrap">{implData.developmentConfirmation}</p>
          </div>
        )}
        {implData.implementationDate && (
          <div className="border-b border-stone-200 bg-amber-50/50 px-4 py-3">
            <p className="text-xs font-semibold text-stone-500">Implementation date</p>
            <p className="mt-1 text-sm text-stone-800">{implData.implementationDate}</p>
          </div>
        )}
        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead>
              <tr className="border-b-2 border-stone-200 bg-stone-50 text-xs font-semibold uppercase text-stone-500">
                <th className="w-24 px-3 py-2.5">Department</th>
                <th className="w-10 px-3 py-2.5 text-center">Y/N</th>
                <th className="px-3 py-2.5">Description</th>
                <th className="w-28 px-3 py-2.5">Responsible</th>
                <th className="w-28 px-3 py-2.5">Due date</th>
                <th className="w-20 px-3 py-2.5 text-center">STATUS</th>
                <th className="px-3 py-2.5">Result / 结果</th>
              </tr>
            </thead>
            <tbody>
              {implData.checklistRows.length ? implData.checklistRows.map((row, i) => (
                <tr key={row.id || i} className="border-b border-stone-100 even:bg-stone-50/50">
                  <td className="px-3 py-2.5 text-xs font-medium text-stone-700">{row.department}</td>
                  <td className="px-3 py-2.5 text-center">
                    <span className={`inline-flex size-5 items-center justify-center rounded text-xs font-bold ${
                      row.yn === "Y" ? "bg-emerald-100 text-emerald-700" : "bg-stone-100 text-stone-400"
                    }`}>
                      {row.yn || "—"}
                    </span>
                  </td>
                  <td className="px-3 py-2.5 text-xs text-stone-600">{row.description || "-"}</td>
                  <td className="px-3 py-2.5 text-xs text-stone-600">{row.responsible || "-"}</td>
                  <td className="px-3 py-2.5 text-xs text-stone-600">{row.dueDate || "-"}</td>
                  <td className="px-3 py-2.5 text-center">
                    {row.result ? (
                      <span className={`inline-flex items-center rounded px-1.5 py-0.5 text-[10px] font-bold ${
                        row.result === "Closed" ? "bg-emerald-100 text-emerald-700" :
                        row.result === "Ongoing" ? "bg-sky-100 text-sky-700" :
                        row.result === "Open" ? "bg-amber-100 text-amber-700" :
                        "bg-stone-100 text-stone-500"
                      }`}>
                        {row.result}
                      </span>
                    ) : (
                      <span className="text-xs text-stone-300">—</span>
                    )}
                  </td>
                  <td className="px-3 py-2.5 text-xs text-stone-600 whitespace-pre-wrap">{row.resultNote || "-"}</td>
                </tr>
              )) : (
                <tr>
                  <td colSpan={7} className="px-3 py-8 text-center text-sm text-stone-400">暂无实施计划数据</td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </CollapsibleResultSection>
    </div>
  )
}

// ── Main component ──
export function PdEcrModuleAccordion({
  modules,
  caseId,
  workflowEnabled = Boolean(caseId),
}: {
  modules: PdEcrDisplayModule[]
  caseId?: string
  workflowEnabled?: boolean
}) {
  const [expandedId, setExpandedId] = useState<string | null>(null)
  const [showApproval, setShowApproval] = useState(true)
  const [viewMode, setViewMode] = useState<"accordion" | "result">("accordion")

  const handleToggle = (moduleId: string) => {
    setExpandedId((prev) => (prev === moduleId ? null : moduleId))
  }

  // Filter to only the desired modules, in order
  const filteredModules = ACCORDION_MODULE_IDS
    .map((id) => modules.find((m) => m.id === id))
    .filter(Boolean) as PdEcrDisplayModule[]

  if (!filteredModules.length) {
    return (
      <div className="rounded-lg border border-stone-200 bg-white p-8 text-center text-stone-500">
        No modules available. Please generate PD-ECR content first.
      </div>
    )
  }

  // ── Result view ──
  if (viewMode === "result") {
    return (
      <div className="relative">
        <div className="mb-4 flex items-center justify-between">
          <h2 className="text-xl font-semibold text-stone-900">Sign-off / 签核确认</h2>
          <Button
            type="button"
            variant="outline"
            size="sm"
            className="bg-white"
            onClick={() => setViewMode("accordion")}
          >
            ← 返回编辑
          </Button>
        </div>
        <div className="grid gap-5 xl:grid-cols-[1fr_17rem]">
          <div className="min-w-0">
            <ResultView modules={modules} />
          </div>
          <div className="hidden xl:block">
            <ResultSignerPanel />
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="relative">
      <div className={`grid gap-5 ${showApproval && Boolean(caseId) ? "xl:grid-cols-[1fr_17rem]" : ""}`}>
        {/* ── LEFT: Accordion modules ── */}
        <div className="space-y-3 min-w-0 min-h-0">
          {filteredModules.map((module) => (
            <AccordionItem
              key={module.id}
              module={module}
              label={MODULE_LABELS[module.id] || { title: module.title, subtitle: module.subtitle }}
              isExpanded={expandedId === module.id}
              onToggle={() => handleToggle(module.id)}
            />
          ))}
        </div>

        {/* ── RIGHT: Collapsible approval / workflow panel (only when caseId exists) ── */}
        {showApproval && Boolean(caseId) && (
          <div className="hidden xl:block">
            <div className="flex items-center justify-between mb-3">
              <div className="flex items-center gap-2">
                <UserCheck className="size-4 text-amber-600" />
                <p className="text-sm font-semibold text-stone-700">
                  {workflowEnabled
                    ? "状态流 / Workflow"
                    : "Historical reference"}
                </p>
              </div>
              <button
                type="button"
                onClick={() => setShowApproval(false)}
                className="rounded p-1 text-stone-400 hover:bg-stone-100 hover:text-stone-600 transition"
                title="收起审批面板"
              >
                <ChevronRight className="size-4" />
              </button>
            </div>
            {workflowEnabled && caseId ? (
              <PdEcrExecutionWorkflowPanel caseId={caseId} onComplete={() => setViewMode("result")} />
            ) : (
              <HistoricalReferencePanel />
            )}
          </div>
        )}
      </div>

      {showApproval && Boolean(caseId) && (
        <div className="mt-5 xl:hidden">
          <div className="mb-3 flex items-center gap-2">
            <UserCheck className="size-4 text-amber-600" />
            <p className="text-sm font-semibold text-stone-700">
              {workflowEnabled
                ? "状态流 / Workflow"
                : "Historical reference"}
            </p>
          </div>
          {workflowEnabled && caseId ? (
            <PdEcrExecutionWorkflowPanel caseId={caseId} onComplete={() => setViewMode("result")} />
          ) : (
            <HistoricalReferencePanel />
          )}
        </div>
      )}

      {/* ── Floating toggle to show approval panel when hidden ── */}
      {!showApproval && caseId && (
        <button
          type="button"
          onClick={() => setShowApproval(true)}
          className="hidden xl:flex fixed right-4 top-24 z-40 items-center gap-1.5 rounded-l-lg border border-amber-300 bg-amber-50 px-3 py-2 text-xs font-semibold text-amber-700 shadow-md hover:bg-amber-100 transition"
          title="展开审批面板"
        >
          <ChevronLeft className="size-3.5" />
          <UserCheck className="size-3.5" />
          确认
        </button>
      )}
    </div>
  )
}
