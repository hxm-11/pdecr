import type {
  PdEcrDepartmentWorkflowTask,
  PdEcrExecutionWorkflowTask,
  PdEcrLeaderReviewWorkflowTask,
} from "@/lib/pdEcrApi"
import type { PdEcrPdEcrCaseRow } from "./pdEcrState"

export type PdEcrGateState = {
  label: string
  detail: string
  tone: "ready" | "blocked" | "warning" | "done" | "readonly"
  blockers: string[]
}

export type PdEcrCaseWorkbenchState = {
  owner: string
  currentTask: string
  dueLabel: string
  overdueDays: number
  risk: "High" | "Medium" | "Low" | "Closed" | "Reference"
  gate: PdEcrGateState
}

const activeStatuses = new Set([
  "draft",
  "generated",
  "submitted",
  "department_confirmation",
  "department_alignment",
  "execution_assignment",
  "assignee_confirmation",
  "execution_in_progress",
  "in_review",
  "leader_review",
  "changes_requested",
])

function normalizeStatus(status?: string, source?: string) {
  if (source === "history" || status === "historical") return "historical"
  const normalized = String(status || "").trim().toLowerCase()
  if (!normalized || normalized === "v1_mvp_draft") return "generated"
  return normalized
}

function daysUntil(dateValue?: string) {
  if (!dateValue || dateValue === "-") return null
  const target = new Date(dateValue)
  if (Number.isNaN(target.getTime())) return null
  const today = new Date()
  today.setHours(0, 0, 0, 0)
  target.setHours(0, 0, 0, 0)
  return Math.ceil((target.getTime() - today.getTime()) / 86_400_000)
}

function ownerFromRow(row: PdEcrPdEcrCaseRow, status: string) {
  if (status === "historical") return "Knowledge base"
  if (status === "leader_review") return "Leader approver"
  if (status === "execution_in_progress") return row.dept || "Task owner"
  return row.initiator || row.dept || "Unassigned"
}

export function evaluatePdEcrGate({
  status,
  source,
  row,
}: {
  status?: string
  source?: string
  row?: PdEcrPdEcrCaseRow
}): PdEcrGateState {
  const normalized = normalizeStatus(status, source)

  if (normalized === "historical") {
    return {
      label: "Read only",
      detail: "Historical reference case",
      tone: "readonly",
      blockers: [],
    }
  }
  if (normalized === "closed") {
    return {
      label: "Closed",
      detail: "No next transition",
      tone: "done",
      blockers: [],
    }
  }
  if (normalized === "cancelled") {
    return {
      label: "Stopped",
      detail: "Case cancelled",
      tone: "blocked",
      blockers: ["Cancelled case cannot continue."],
    }
  }
  if (normalized === "changes_requested") {
    return {
      label: "Rework",
      detail: "Resolve comments before resubmission",
      tone: "blocked",
      blockers: ["Open change comments must be resolved."],
    }
  }

  const blockers: string[] = []
  if (!row?.backendCaseId && normalized !== "generated") {
    blockers.push("Save backend case before formal workflow transition.")
  }
  if (["draft", "generated"].includes(normalized)) {
    blockers.push("Complete Page 1 modules and feasibility confirmation before submit.")
  }
  if (normalized === "department_confirmation") {
    blockers.push("All impacted departments must confirm action required.")
  }
  if (normalized === "execution_assignment") {
    blockers.push("Every Y implementation item needs owner and due date.")
  }
  if (normalized === "execution_in_progress") {
    blockers.push("Execution evidence and validation result are required.")
  }
  if (normalized === "leader_review") {
    blockers.push("All leader signatures are required before approval.")
  }

  if (!blockers.length) {
    return {
      label: "Ready",
      detail: "Next transition available",
      tone: "ready",
      blockers: [],
    }
  }

  return {
    label: "Needs input",
    detail: blockers[0],
    tone: normalized === "draft" || normalized === "generated" ? "warning" : "blocked",
    blockers,
  }
}

export function getPdEcrCurrentTask(status?: string, source?: string) {
  const normalized = normalizeStatus(status, source)
  switch (normalized) {
    case "historical":
      return "Reference only"
    case "draft":
    case "generated":
      return "Complete draft"
    case "submitted":
      return "Initial review"
    case "department_confirmation":
      return "Department impact confirmation"
    case "department_alignment":
      return "Resolve department alignment"
    case "execution_assignment":
      return "Assign implementation owners"
    case "assignee_confirmation":
      return "Assignees accept tasks"
    case "execution_in_progress":
      return "Execute and collect evidence"
    case "in_review":
      return "Review validation results"
    case "leader_review":
      return "Leader sign-off"
    case "changes_requested":
      return "Rework requested"
    case "approved":
      return "Prepare implementation"
    case "implementation":
      return "Close implementation result"
    case "closed":
      return "Archived"
    case "cancelled":
      return "Stopped"
    default:
      return "Check workflow"
  }
}

export function getPdEcrCaseWorkbenchState({
  row,
  status,
  source,
  targetCloseDate,
}: {
  row: PdEcrPdEcrCaseRow
  status?: string
  source?: string
  targetCloseDate?: string
}): PdEcrCaseWorkbenchState {
  const normalized = normalizeStatus(status || row.status, source)
  const gate = evaluatePdEcrGate({ status: normalized, source, row })
  const dueDays = daysUntil(targetCloseDate || row.createDate)
  const overdueDays =
    dueDays !== null && dueDays < 0 && activeStatuses.has(normalized)
      ? Math.abs(dueDays)
      : 0
  const dueLabel =
    dueDays === null
      ? "-"
      : dueDays < 0
        ? `${Math.abs(dueDays)}d overdue`
        : dueDays === 0
          ? "Due today"
          : `${dueDays}d left`
  const risk =
    normalized === "historical"
      ? "Reference"
      : normalized === "closed"
        ? "Closed"
        : normalized === "changes_requested" || overdueDays > 0
          ? "High"
          : gate.tone === "blocked" || gate.tone === "warning"
            ? "Medium"
            : "Low"

  return {
    owner: ownerFromRow(row, normalized),
    currentTask: getPdEcrCurrentTask(normalized, source),
    dueLabel,
    overdueDays,
    risk,
    gate,
  }
}

export function isTaskOverdue(task: { due_date?: string | null; status?: string }) {
  const dueDays = daysUntil(task.due_date || undefined)
  return (
    dueDays !== null &&
    dueDays < 0 &&
    !["completed", "approved", "rejected", "cancelled"].includes(task.status || "")
  )
}

export function workflowTaskDueLabel(task: { due_date?: string | null }) {
  const dueDays = daysUntil(task.due_date || undefined)
  if (dueDays === null) return "No due date"
  if (dueDays < 0) return `${Math.abs(dueDays)}d overdue`
  if (dueDays === 0) return "Due today"
  return `${dueDays}d left`
}

export function flattenMyWorkflowTasks({
  executionTasks,
  leaderTasks,
  departmentTasks,
}: {
  executionTasks: PdEcrExecutionWorkflowTask[]
  leaderTasks: PdEcrLeaderReviewWorkflowTask[]
  departmentTasks: PdEcrDepartmentWorkflowTask[]
}) {
  return [
    ...departmentTasks.map((task) => ({
      id: task.id,
      type: "department" as const,
      status: task.status,
      due_date: task.due_date,
    })),
    ...executionTasks.map((task) => ({
      id: task.id,
      type: "execution" as const,
      status: task.status,
      due_date: task.due_date,
    })),
    ...leaderTasks.map((task) => ({
      id: task.id,
      type: "leader" as const,
      status: task.status,
      due_date: null,
    })),
  ]
}
