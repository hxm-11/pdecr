import { ChevronDown, ChevronLeft, ChevronRight, FileText, UserCheck } from "lucide-react"
import { useEffect, useRef, useState } from "react"
import type { PdEcrDisplayModule } from "./pdEcrState"
import {
  renderModuleBody,
  SignatureDashboard,
} from "./PdEcrModuleDetail"

// ── Simplified module list: only 3 modules ──
const ACCORDION_MODULE_IDS = [
  "change-description",
  "impact-analysis",
  "implementation-plan",
] as const

const MODULE_LABELS: Record<string, { title: string; subtitle: string }> = {
  "change-description": { title: "变更描述", subtitle: "Change Description" },
  "impact-analysis": { title: "影响分析", subtitle: "Impact Analysis" },
  "implementation-plan": { title: "实施与验证", subtitle: "Implementation & Validation" },
}

// ── Approval panel types & constants (shared with ImpactAnalysisView) ──
type ApprovalRow = { person: string; date: string }
const APPROVAL_DEPTS = ["Development", "Purchasing", "MFE", "Quality", "COS", "MOEx", "LOG"]

function defaultApproval(): ApprovalRow {
  return { person: "", date: "" }
}

// ── Right-side fixed approval panel ──
function ApprovalSignerPanel({ impactModule }: { impactModule?: PdEcrDisplayModule }) {
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
      prev.map((r, j) => (j !== i ? r : { ...r, [field]: value }))
    )
  }

  return (
    <div className="sticky top-4 space-y-4" style={{ maxHeight: "calc(100vh - 8rem)", overflowY: "auto" }}>
      {/* ── Approval signer inputs ── */}
      <div className="rounded-lg border border-amber-300 bg-white shadow-sm">
        <div className="rounded-t-lg bg-amber-600 px-4 py-2.5 text-sm font-semibold text-white">
          Step 4 / 7 Approval / 审批签字
        </div>
        <div className="divide-y divide-stone-100">
          {APPROVAL_DEPTS.map((dept, i) => (
            <div key={dept} className="px-4 py-2.5">
              <p className="text-xs font-semibold text-stone-700">{dept}</p>
              <input
                value={approvals[i].person}
                onChange={(e) => updateApproval(i, "person", e.target.value)}
                className="mt-1 h-8 w-full rounded border border-stone-200 bg-white px-2 text-xs outline-none focus:border-amber-400"
                placeholder="签批人..."
              />
              {approvals[i].date ? (
                <p className="mt-1 text-[10px] text-stone-400">{approvals[i].date}</p>
              ) : (
                <p className="mt-1 text-[10px] text-stone-300">待签字</p>
              )}
            </div>
          ))}
        </div>
      </div>

      {/* ── Signature status table ── */}
      {impactModule && <SignatureDashboard module={impactModule} />}

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

// ── Main component ──
export function PdEcrModuleAccordion({
  modules,
}: {
  modules: PdEcrDisplayModule[]
}) {
  const [expandedId, setExpandedId] = useState<string | null>(null)
  const [showApproval, setShowApproval] = useState(true)

  const handleToggle = (moduleId: string) => {
    setExpandedId((prev) => (prev === moduleId ? null : moduleId))
  }

  // Filter to only the 3 desired modules, in order
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
            <ApprovalSignerPanel impactModule={impactModule} />
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
