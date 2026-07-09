import { CheckCircle2, Circle, Play, RotateCcw, XCircle } from "lucide-react"

// Canonical PD-ECR lifecycle (source of truth: backend lifecycle_service).
const flowSteps = [
  { id: "draft", short: "Draft", zh: "草稿" },
  { id: "submitted", short: "Submit", zh: "提交" },
  { id: "applicant_confirming", short: "Confirm", zh: "发起确认" },
  { id: "leader_reviewing", short: "Review", zh: "领导审核" },
  { id: "task_executing", short: "Exec", zh: "执行" },
  { id: "result_confirming", short: "Result", zh: "结果确认" },
  { id: "closed", short: "Close", zh: "关闭" },
] as const

const nextGate: Record<string, string> = {
  draft: "Submit for approval",
  submitted: "Applicant confirmation",
  applicant_confirming: "Leader review",
  leader_reviewing: "Execute tasks",
  task_executing: "Confirm results",
  result_confirming: "Close case",
  closed: "Archived",
  historical: "Reference only",
  rejected: "Resolve & resubmit",
  cancelled: "Stopped",
  expired: "Overdue",
}

// Legacy/raw → canonical, mirroring backend LEGACY_STATUS_ALIASES so old case
// records still resolve to a real step instead of an unknown (-1) index.
const statusAlias: Record<string, string> = {
  v1_mvp_draft: "draft",
  pending: "submitted",
  generated: "task_executing",
  implementation: "task_executing",
  execution_assignment: "task_executing",
  assignee_confirmation: "task_executing",
  execution_in_progress: "task_executing",
  approved: "task_executing",
  review: "leader_reviewing",
  in_review: "leader_reviewing",
  leader_review: "leader_reviewing",
  department_confirmation: "applicant_confirming",
  department_alignment: "applicant_confirming",
  changes_requested: "rejected",
}

function normalizeStatus(status?: string, source?: string) {
  if (source === "history" || status === "historical") return "historical"
  const normalized = String(status || "").trim().toLowerCase()
  if (!normalized) return "draft"
  return statusAlias[normalized] || normalized
}

function currentIndex(status: string) {
  return flowSteps.findIndex((step) => step.id === status)
}

function statusText(status: string) {
  if (status === "historical") return "Historical / 历史"
  if (status === "rejected") return "Rejected / 退回"
  if (status === "cancelled") return "Cancelled / 取消"
  if (status === "expired") return "Expired / 超期"
  const step = flowSteps.find((item) => item.id === status)
  return step ? `${step.short} / ${step.zh}` : status.replace(/_/g, " ")
}

export function PdEcrCaseStatusFlow({
  status,
  source,
  compact = false,
}: {
  status?: string
  source?: string
  compact?: boolean
}) {
  const normalized = normalizeStatus(status, source)
  const activeIndex = currentIndex(normalized)
  const isHistorical = normalized === "historical"
  const isReturned = normalized === "rejected"
  const isCancelled = normalized === "cancelled" || normalized === "expired"
  const visibleSteps = compact
    ? flowSteps.filter((_, index) => index % 2 === 0 || index === activeIndex)
    : flowSteps

  return (
    <div className="min-w-[19rem] max-w-[34rem]">
      <div className="mb-1 flex items-center justify-between gap-2">
        <span
          className={`inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-[10px] font-semibold ${
            isHistorical
              ? "border-sky-200 bg-sky-50 text-sky-700"
              : isReturned
                ? "border-red-200 bg-red-50 text-red-700"
                : isCancelled
                  ? "border-stone-200 bg-stone-100 text-stone-500"
                  : "border-emerald-200 bg-emerald-50 text-emerald-700"
          }`}
        >
          {isReturned ? (
            <RotateCcw className="size-3" />
          ) : isCancelled ? (
            <XCircle className="size-3" />
          ) : isHistorical ? (
            <Circle className="size-3" />
          ) : (
            <Play className="size-3" />
          )}
          {statusText(normalized)}
        </span>
        <span className="truncate text-[10px] font-medium text-stone-400">
          Next: {nextGate[normalized] || "Check workflow"}
        </span>
      </div>
      <div className="flex items-center gap-1">
        {visibleSteps.map((step, index) => {
          const originalIndex = flowSteps.findIndex((item) => item.id === step.id)
          const isActive = step.id === normalized
          const isDone = activeIndex >= 0 && originalIndex < activeIndex
          return (
            <div key={step.id} className="flex min-w-0 flex-1 items-center gap-1">
              <div
                className={`group relative flex min-w-0 flex-1 items-center justify-center rounded-sm border px-1.5 py-1 ${
                  isActive
                    ? "border-stone-900 bg-stone-900 text-white"
                    : isDone
                      ? "border-emerald-200 bg-emerald-50 text-emerald-700"
                      : "border-stone-200 bg-white text-stone-400"
                }`}
                title={`${step.short} / ${step.zh}`}
              >
                {isDone ? (
                  <CheckCircle2 className="mr-1 size-3 shrink-0" />
                ) : (
                  <span
                    className={`mr-1 size-1.5 shrink-0 rounded-full ${
                      isActive ? "bg-white" : "bg-current"
                    }`}
                  />
                )}
                <span className="truncate text-[10px] font-semibold">
                  {step.short}
                </span>
              </div>
              {index < visibleSteps.length - 1 ? (
                <span className="h-px w-2 shrink-0 bg-stone-200" />
              ) : null}
            </div>
          )
        })}
      </div>
    </div>
  )
}
