import { ChevronDown, ChevronLeft, ChevronRight, FileText, UserCheck } from "lucide-react"
import { type ReactNode, useEffect, useMemo, useRef, useState } from "react"
import { Button } from "@/components/ui/button"
import type { PdEcrDisplayModule } from "./pdEcrState"
import { renderModuleBody } from "./PdEcrModuleDetail"

// ── Simplified module list ──
const ACCORDION_MODULE_IDS = [
  "change-description",
  "impact-analysis",
  "validation-plan",
  "implementation-plan",
] as const

const MODULE_LABELS: Record<string, { title: string; subtitle: string }> = {
  "change-description": { title: "变更描述", subtitle: "Change Description" },
  "impact-analysis": { title: "影响分析", subtitle: "Impact Analysis" },
  "validation-plan": { title: "QAC & Validation plan", subtitle: "QAC & Validation Plan" },
  "implementation-plan": { title: "实施与验证", subtitle: "Implementation & Plan" },
}

// ── Approval panel types & constants (shared with ImpactAnalysisView) ──
type ApprovalRow = { person: string; date: string }
const APPROVAL_DEPTS = ["Development", "Purchasing", "MFE", "Quality", "COS", "MOEx", "LOG"]

function defaultApproval(): ApprovalRow {
  return { person: "", date: "" }
}

// ── Right-side fixed approval panel ──
function ApprovalSignerPanel({ impactModule, onSubmit }: { impactModule?: PdEcrDisplayModule; onSubmit?: () => void }) {
  const storageKey = impactModule
    ? `pd-ecr-impact-analysis-${impactModule.id}`
    : "pd-ecr-impact-analysis-fallback"

  const [approvals, setApprovals] = useState<ApprovalRow[]>(() => {
    try {
      const raw = localStorage.getItem(storageKey)
      if (raw) {
        const parsed = JSON.parse(raw)
        if (parsed?.approvals?.length === 7) return parsed.approvals
      }
    } catch { /* ignore */ }
    return APPROVAL_DEPTS.map(() => defaultApproval())
  })

  const [saveStatus, setSaveStatus] = useState("")
  const autoSaveTimer = useRef<ReturnType<typeof setTimeout>>(undefined)

  // Auto-save on approval change (debounced 1s)
  useEffect(() => {
    const skip = !autoSaveTimer.current
    if (skip) { autoSaveTimer.current = setTimeout(() => {}, 0); return }
    setSaveStatus("Saving...")
    clearTimeout(autoSaveTimer.current)
    autoSaveTimer.current = setTimeout(() => {
      let existing: Record<string, unknown> = {}
      try {
        const raw = localStorage.getItem(storageKey)
        if (raw) existing = JSON.parse(raw)
      } catch { /* ignore */ }
      localStorage.setItem(storageKey, JSON.stringify({ ...existing, approvals }))
      setSaveStatus("Auto-saved")
      setTimeout(() => setSaveStatus(""), 2000)
    }, 1000)
    return () => clearTimeout(autoSaveTimer.current)
  }, [approvals, storageKey])

  const updateApproval = (i: number, field: keyof ApprovalRow, value: string) => {
    setApprovals((prev) =>
      prev.map((r, j) => {
        if (j !== i) return r
        const next = { ...r, [field]: value }
        if (field === "person") {
          if (value.trim()) {
            const now = new Date()
            next.date = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}-${String(now.getDate()).padStart(2, "0")} ${String(now.getHours()).padStart(2, "0")}:${String(now.getMinutes()).padStart(2, "0")}:${String(now.getSeconds()).padStart(2, "0")}`
          } else {
            next.date = ""
          }
        }
        return next
      })
    )
  }

  const allConfirmed = useMemo(
    () => approvals.every((a) => a.person.trim()),
    [approvals],
  )

  return (
    <div className="sticky top-4 space-y-4" style={{ maxHeight: "calc(100vh - 8rem)", overflowY: "auto" }}>
      {/* ── Approval signer inputs ── */}
      <div className="rounded-lg border border-amber-300 bg-white shadow-sm">
        <div className="rounded-t-lg bg-amber-600 px-4 py-2.5 text-sm font-semibold text-white">
          Change-Feasibility Review
        </div>
        <div className="divide-y divide-stone-100">
          {APPROVAL_DEPTS.map((dept, i) => (
            <div key={dept} className="px-4 py-2.5">
              <p className="text-xs font-semibold text-stone-700">{dept}</p>
              <input
                value={approvals[i].person}
                onChange={(e) => updateApproval(i, "person", e.target.value)}
                className="mt-1 h-8 w-full rounded border border-stone-200 bg-white px-2 text-xs outline-none focus:border-amber-400"
                placeholder="确认人..."
              />
              {approvals[i].date ? (
                <p className="mt-1 text-[10px] font-medium text-emerald-600">✓ {approvals[i].date}</p>
              ) : (
                <p className="mt-1 text-[10px] text-stone-300">待确认</p>
              )}
            </div>
          ))}
        </div>
      </div>

      {/* ── Submit button when all confirmed ── */}
      {allConfirmed && onSubmit && (
        <Button
          type="button"
          className="w-full bg-emerald-600 hover:bg-emerald-700"
          onClick={onSubmit}
        >
          全部确认完成，查看结果 →
        </Button>
      )}

      {/* ── Save indicator ── */}
      {saveStatus && (
        <p className="text-center text-[10px] text-stone-400">{saveStatus}</p>
      )}
    </div>
  )
}

// ── Accordion item ──
function AccordionItem({
  module,
  isExpanded,
  onToggle,
  label,
}: {
  module: PdEcrDisplayModule
  isExpanded: boolean
  onToggle: () => void
  label: { title: string; subtitle: string }
}) {
  const hasContent =
    module.data &&
    Object.keys(module.data).length > 0 &&
    (module.summary || String(module.data.content || "").trim())

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

          {/* Main content (plan view for implementation) — hide internal approval panel, we have the external one */}
          {renderModuleBody(module, true)}

          {/* Implementation view now handles all steps internally */}
        </div>
      )}
    </div>
  )
}

// ── Result row types ──
type ValResultRow = { id?: string; label: string; checked: boolean; finishDate: string; respPerson: string; comments: string }
type ImplResultRow = { id?: string; department: string; yn: string; description: string; responsible: string; dueDate: string }

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
function ResultView({ modules }: { modules: PdEcrDisplayModule[] }) {
  const valModule = modules.find((m) => m.id === "validation-plan")
  const implModule = modules.find((m) => m.id === "implementation-plan")

  const valRows = valModule ? loadValidationResults(valModule.id) : []
  const implData = implModule ? loadImplementationResults(implModule.id) : { checklistRows: [] as ImplResultRow[], developmentConfirmation: "", implementationDate: "" }
  const ynRows = implData.checklistRows.filter((r) => r.yn === "Y")

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
              </tr>
            </thead>
            <tbody>
              {valRows.length ? valRows.map((row, i) => (
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
                </tr>
              )) : (
                <tr>
                  <td colSpan={5} className="px-3 py-8 text-center text-sm text-stone-400">暂无验证计划数据</td>
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
              </tr>
            </thead>
            <tbody>
              {ynRows.length ? ynRows.map((row, i) => (
                <tr key={row.id || i} className="border-b border-stone-100 even:bg-stone-50/50">
                  <td className="px-3 py-2.5 text-xs font-medium text-stone-700">{row.department}</td>
                  <td className="px-3 py-2.5 text-center">
                    <span className="inline-flex size-5 items-center justify-center rounded bg-emerald-100 text-xs font-bold text-emerald-700">
                      Y
                    </span>
                  </td>
                  <td className="px-3 py-2.5 text-xs text-stone-600">{row.description || "-"}</td>
                  <td className="px-3 py-2.5 text-xs text-stone-600">{row.responsible || "-"}</td>
                  <td className="px-3 py-2.5 text-xs text-stone-600">{row.dueDate || "-"}</td>
                </tr>
              )) : (
                <tr>
                  <td colSpan={5} className="px-3 py-8 text-center text-sm text-stone-400">暂无实施计划数据</td>
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
}: {
  modules: PdEcrDisplayModule[]
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

  // Find the impact-analysis module for the right approval panel
  const impactModule = modules.find((m) => m.id === "impact-analysis")

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
      <div className={`grid gap-5 ${showApproval ? "xl:grid-cols-[1fr_17rem]" : ""}`}>
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

        {/* ── RIGHT: Collapsible approval signer panel ── */}
        {showApproval && (
          <div className="hidden xl:block">
            <div className="flex items-center justify-between mb-3">
              <div className="flex items-center gap-2">
                <UserCheck className="size-4 text-amber-600" />
                <p className="text-sm font-semibold text-stone-700">审批签字</p>
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
            <ApprovalSignerPanel impactModule={impactModule} onSubmit={() => setViewMode("result")} />
          </div>
        )}
      </div>

      {/* ── Floating toggle to show approval panel when hidden ── */}
      {!showApproval && (
        <button
          type="button"
          onClick={() => setShowApproval(true)}
          className="hidden xl:flex fixed right-4 top-24 z-40 items-center gap-1.5 rounded-l-lg border border-amber-300 bg-amber-50 px-3 py-2 text-xs font-semibold text-amber-700 shadow-md hover:bg-amber-100 transition"
          title="展开审批面板"
        >
          <ChevronLeft className="size-3.5" />
          <UserCheck className="size-3.5" />
          审批
        </button>
      )}
    </div>
  )
}
