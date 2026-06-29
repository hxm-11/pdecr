import { useQuery } from "@tanstack/react-query"
import { useNavigate } from "@tanstack/react-router"
import { ClipboardCheck, FileText, UserCheck } from "lucide-react"
import { useState } from "react"

import { Button } from "@/components/ui/button"
import {
  completePdEcrExecutionTask,
  confirmPdEcrExecutionAssignment,
  getPdEcrCase,
  listMyPdEcrWorkflowTasks,
  reviewPdEcrLeaderTask,
  type PdEcrDbModule,
  type PdEcrExecutionWorkflowTask,
  type PdEcrLeaderReviewWorkflowTask,
} from "@/lib/pdEcrApi"
import {
  fallbackGeneratedModules,
  normalizeModules,
  saveActiveResult,
} from "./pdEcrState"

function statusClass(status: string) {
  switch (status) {
    case "completed":
    case "approved":
    case "confirmed":
      return "border-emerald-200 bg-emerald-50 text-emerald-700"
    case "changes_requested":
    case "rejected":
      return "border-rose-200 bg-rose-50 text-rose-700"
    case "pending_confirmation":
    case "in_progress":
    case "pending":
      return "border-amber-200 bg-amber-50 text-amber-700"
    default:
      return "border-stone-200 bg-stone-50 text-stone-600"
  }
}

function isOpenExecutionTask(task: PdEcrExecutionWorkflowTask) {
  return !["completed", "cancelled"].includes(task.status)
}

function isOpenLeaderTask(task: PdEcrLeaderReviewWorkflowTask) {
  return !["approved", "rejected"].includes(task.status)
}

function taskCaseLabel(
  task: PdEcrExecutionWorkflowTask | PdEcrLeaderReviewWorkflowTask,
) {
  return (
    task.case?.case_no ||
    task.case?.dc_no ||
    task.case?.mcr_no ||
    task.case?.id ||
    task.case_id
  )
}

function taskCaseTitle(
  task: PdEcrExecutionWorkflowTask | PdEcrLeaderReviewWorkflowTask,
) {
  return task.case?.title || task.case?.customer_project || "PD-ECR change package"
}

function taskCaseId(
  task: PdEcrExecutionWorkflowTask | PdEcrLeaderReviewWorkflowTask,
) {
  return task.case?.id || task.case_id
}

function canOpenTaskCase(
  task: PdEcrExecutionWorkflowTask | PdEcrLeaderReviewWorkflowTask,
) {
  return task.case_exists !== false
}

function errorMessage(error: unknown) {
  if (!error || typeof error !== "object") return "Unknown error"
  const record = error as {
    message?: string
    response?: { status?: number; data?: unknown }
  }
  const detail =
    record.response?.data && typeof record.response.data === "object"
      ? (record.response.data as { detail?: unknown }).detail
      : undefined
  return [
    record.response?.status ? `HTTP ${record.response.status}` : "",
    typeof detail === "string" ? detail : record.message || "Request failed",
  ]
    .filter(Boolean)
    .join(": ")
}

function mapCaseModules(modules: PdEcrDbModule[]) {
  return modules.map((module) => {
    const contentJson = module.content_json || {}
    const content = contentJson.content || module.content_md || module.title || ""
    const warnings = Array.isArray(contentJson.warnings)
      ? contentJson.warnings
      : []

    return {
      id: module.module_id,
      module_id: module.module_id,
      title: module.title,
      summary:
        String(contentJson.summary || "") ||
        module.content_md ||
        module.title ||
        module.module_id,
      content,
      data: {
        ...contentJson,
        content,
        source_cases: module.source_cases || [],
        source_files: module.source_files || [],
        needs_human_input: module.needs_human_input || false,
        warnings,
      },
      source_cases: module.source_cases || [],
      source_files: module.source_files || [],
      needs_human_input: module.needs_human_input || false,
      warnings,
    }
  })
}

export function PdEcrMyTasks() {
  const navigate = useNavigate()
  const [message, setMessage] = useState("")
  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ["pd-ecr-my-workflow-tasks"],
    queryFn: listMyPdEcrWorkflowTasks,
  })

  if (isLoading) return <p className="text-sm text-stone-500">Loading tasks...</p>
  if (error) {
    return (
      <div className="mx-auto max-w-6xl p-4 sm:p-6">
        <div className="rounded border border-rose-200 bg-rose-50 p-4 text-sm text-rose-700">
          <p className="font-semibold">My Tasks 加载失败</p>
          <p className="mt-1">{errorMessage(error)}</p>
        </div>
      </div>
    )
  }

  const executionTasks = data?.execution_tasks || []
  const leaderTasks = data?.leader_review_tasks || []
  const openCount =
    executionTasks.filter(isOpenExecutionTask).length +
    leaderTasks.filter(isOpenLeaderTask).length

  const refreshAfterAction = async (nextMessage: string) => {
    setMessage(nextMessage)
    await refetch()
  }

  const openCase = async (caseId: string) => {
    setMessage("Loading change package...")
    try {
      const detail = await getPdEcrCase(caseId)
      const modules = normalizeModules(
        mapCaseModules(detail.modules),
        fallbackGeneratedModules,
      )
      const label = detail.case.case_no || detail.case.dc_no || detail.case.id
      saveActiveResult({
        source: "generated",
        draftStatus: detail.case.status,
        relatedCases: [label],
        modules,
        currentCase: {
          id: label,
          backendCaseId: detail.case.id,
          createDate: detail.case.created_at?.slice(0, 10) || "-",
          productClass: detail.case.product_no || "-",
          from: "Workflow task",
          initiator: detail.case.initiator || "-",
          customer: detail.case.customer_project || "-",
          project: detail.case.customer_project || "-",
          partNumber: detail.case.part_no || detail.case.component_no || "-",
          dept: "-",
          link: "Open modules",
          dcNo: detail.case.dc_no || undefined,
          mcrNo: detail.case.mcr_no || undefined,
          changeType: detail.case.change_type || undefined,
        },
      })
      navigate({ to: "/pd-ecr/content" })
    } catch (err) {
      setMessage("")
      throw err
    }
  }

  return (
    <div className="mx-auto max-w-6xl space-y-6 p-4 sm:p-6">
      <header>
        <h1 className="text-2xl font-semibold text-stone-900">PD-ECR My Tasks</h1>
        <p className="mt-1 text-sm text-stone-500">
          {openCount} open workflow items
        </p>
        {message ? (
          <p className="mt-2 rounded border border-emerald-200 bg-emerald-50 px-3 py-2 text-sm text-emerald-700">
            {message}
          </p>
        ) : null}
      </header>

      <section>
        <div className="flex items-center gap-2">
          <ClipboardCheck className="size-4 text-amber-600" />
          <h2 className="text-base font-semibold text-stone-900">Execution Tasks</h2>
        </div>
        <div className="mt-3 divide-y divide-stone-100 rounded border border-stone-200 bg-white">
          {executionTasks.map((task) => (
            <ExecutionTaskRow
              key={task.id}
              task={task}
              onOpenCase={openCase}
              onChanged={refreshAfterAction}
            />
          ))}
          {!executionTasks.length && (
            <p className="p-3 text-sm text-stone-500">No execution tasks.</p>
          )}
        </div>
      </section>

      <section>
        <div className="flex items-center gap-2">
          <UserCheck className="size-4 text-amber-600" />
          <h2 className="text-base font-semibold text-stone-900">Leader Reviews</h2>
        </div>
        <div className="mt-3 divide-y divide-stone-100 rounded border border-stone-200 bg-white">
          {leaderTasks.map((task) => (
            <LeaderReviewRow
              key={task.id}
              task={task}
              onOpenCase={openCase}
              onChanged={refreshAfterAction}
            />
          ))}
          {!leaderTasks.length && (
            <p className="p-3 text-sm text-stone-500">No leader reviews.</p>
          )}
        </div>
      </section>
    </div>
  )
}

function ExecutionTaskRow({
  task,
  onOpenCase,
  onChanged,
}: {
  task: PdEcrExecutionWorkflowTask
  onOpenCase: (caseId: string) => Promise<void>
  onChanged: (message: string) => Promise<void>
}) {
  const [result, setResult] = useState(task.execution_result || "completed")
  const [note, setNote] = useState(task.execution_note || "")
  const [evidence, setEvidence] = useState(task.evidence_note || "")
  const [error, setError] = useState("")
  const [isSaving, setIsSaving] = useState(false)
  const caseLabel = taskCaseLabel(task)
  const canOpenCase = canOpenTaskCase(task)

  const openCase = async () => {
    if (!canOpenCase) {
      setError("该任务指向的后端案例不存在，无法打开变更包。")
      return
    }
    setIsSaving(true)
    setError("")
    try {
      await onOpenCase(taskCaseId(task))
    } catch (err) {
      setError(errorMessage(err))
      setIsSaving(false)
    }
  }

  const confirmAssignment = async () => {
    setIsSaving(true)
    setError("")
    try {
      await confirmPdEcrExecutionAssignment(task.id)
      await onChanged("Assignment confirmed. Execution can start.")
    } catch (err) {
      setError(err instanceof Error ? err.message : "Confirm failed")
    } finally {
      setIsSaving(false)
    }
  }

  const completeTask = async () => {
    setIsSaving(true)
    setError("")
    try {
      await completePdEcrExecutionTask(task.id, {
        execution_result: result,
        execution_note: note,
        evidence_note: evidence,
      })
      await onChanged("Execution result submitted.")
    } catch (err) {
      setError(err instanceof Error ? err.message : "Submit failed")
    } finally {
      setIsSaving(false)
    }
  }

  return (
    <div className="grid gap-3 p-3 lg:grid-cols-[1fr_17rem] lg:items-start">
      <div className="min-w-0">
        <div className="flex flex-wrap items-center gap-2">
          <p className="text-sm font-semibold text-stone-800">{task.description}</p>
          <span className={`w-fit rounded-full border px-2 py-0.5 text-[10px] font-semibold ${statusClass(task.status)}`}>
            {task.status}
          </span>
        </div>
        <p className="mt-1 text-xs text-stone-500">
          {caseLabel} · {taskCaseTitle(task)} · {task.department} · {task.assignee_name || task.assignee_email || "unassigned"}
        </p>
        {!canOpenCase ? (
          <p className="mt-2 rounded bg-rose-50 p-2 text-xs text-rose-700">
            该任务仍在列表中，但它关联的后端案例已经不存在或不可访问，因此不能打开变更包。
          </p>
        ) : null}
        {task.due_date && (
          <p className="mt-1 text-xs text-stone-500">
            Due {new Date(task.due_date).toLocaleDateString()}
          </p>
        )}
        {task.review_comment && (
          <p className="mt-2 rounded bg-rose-50 p-2 text-xs text-rose-700">
            {task.review_comment}
          </p>
        )}
        {task.status === "pending_confirmation" ? (
          <p className="mt-2 rounded bg-amber-50 p-2 text-xs text-amber-800">
            请先打开变更包确认变更描述、影响分析、验证计划和实施计划，再确认 assignment。
          </p>
        ) : null}
      </div>

      <div className="space-y-2">
        <Button
          type="button"
          size="sm"
          variant="outline"
          className="w-full bg-white"
          onClick={openCase}
          disabled={isSaving || !canOpenCase}
        >
          <FileText className="size-4" />
          Open change package
        </Button>

        {(task.status === "pending_confirmation" || task.status === "changes_requested") && (
          <Button
            type="button"
            size="sm"
            className="w-full bg-emerald-600 hover:bg-emerald-700"
            onClick={confirmAssignment}
            disabled={isSaving || !canOpenCase}
          >
            {task.status === "changes_requested" ? "Confirm rework" : "Confirm assignment"}
          </Button>
        )}

        {task.status === "in_progress" && (
          <>
            <input
              value={result}
              onChange={(event) => setResult(event.target.value)}
              className="h-8 w-full rounded border border-stone-200 px-2 text-xs outline-none focus:border-amber-400"
              placeholder="Execution result"
            />
            <textarea
              value={note}
              onChange={(event) => setNote(event.target.value)}
              className="min-h-16 w-full rounded border border-stone-200 px-2 py-1.5 text-xs outline-none focus:border-amber-400"
              placeholder="Execution note"
            />
            <textarea
              value={evidence}
              onChange={(event) => setEvidence(event.target.value)}
              className="min-h-16 w-full rounded border border-stone-200 px-2 py-1.5 text-xs outline-none focus:border-amber-400"
              placeholder="Evidence note"
            />
            <Button
              type="button"
              size="sm"
              className="w-full bg-emerald-600 hover:bg-emerald-700"
              onClick={completeTask}
              disabled={isSaving || !canOpenCase || !result.trim()}
            >
              Complete execution
            </Button>
          </>
        )}

        {task.status === "completed" && (
          <div className="rounded bg-emerald-50 p-2 text-xs text-emerald-800">
            <p>{task.execution_result || "completed"}</p>
            {task.execution_note && <p className="mt-1">{task.execution_note}</p>}
            {task.evidence_note && <p className="mt-1">{task.evidence_note}</p>}
          </div>
        )}

        {error && <p className="text-xs text-rose-600">{error}</p>}
      </div>
    </div>
  )
}

function LeaderReviewRow({
  task,
  onOpenCase,
  onChanged,
}: {
  task: PdEcrLeaderReviewWorkflowTask
  onOpenCase: (caseId: string) => Promise<void>
  onChanged: (message: string) => Promise<void>
}) {
  const [comment, setComment] = useState(task.review_comment || "")
  const [signature, setSignature] = useState(task.signature_name || task.reviewer_name || "")
  const [error, setError] = useState("")
  const [isSaving, setIsSaving] = useState(false)
  const caseLabel = taskCaseLabel(task)
  const canOpenCase = canOpenTaskCase(task)

  const openCase = async () => {
    if (!canOpenCase) {
      setError("该任务指向的后端案例不存在，无法打开变更包。")
      return
    }
    setIsSaving(true)
    setError("")
    try {
      await onOpenCase(taskCaseId(task))
    } catch (err) {
      setError(errorMessage(err))
      setIsSaving(false)
    }
  }

  const review = async (decision: "approved" | "changes_requested") => {
    setIsSaving(true)
    setError("")
    try {
      await reviewPdEcrLeaderTask(task.id, {
        decision,
        review_comment: comment,
        signature_name: signature,
      })
      await onChanged(
        decision === "approved"
          ? "Leader review approved."
          : "Changes requested and sent back.",
      )
    } catch (err) {
      setError(err instanceof Error ? err.message : "Review failed")
    } finally {
      setIsSaving(false)
    }
  }

  return (
    <div className="grid gap-3 p-3 lg:grid-cols-[1fr_17rem] lg:items-start">
      <div className="min-w-0">
        <div className="flex flex-wrap items-center gap-2">
          <p className="text-sm font-semibold capitalize text-stone-800">{task.department}</p>
          <span className={`w-fit rounded-full border px-2 py-0.5 text-[10px] font-semibold ${statusClass(task.status)}`}>
            {task.status}
          </span>
        </div>
        <p className="mt-1 text-xs text-stone-500">
          {caseLabel} · {taskCaseTitle(task)} · {task.reviewer_name || task.reviewer_email || "unassigned reviewer"}
        </p>
        {!canOpenCase ? (
          <p className="mt-2 rounded bg-rose-50 p-2 text-xs text-rose-700">
            该签核任务关联的后端案例已经不存在或不可访问，因此不能打开变更包。
          </p>
        ) : null}
        {task.review_comment && (
          <p className="mt-2 rounded bg-stone-50 p-2 text-xs text-stone-600">
            {task.review_comment}
          </p>
        )}
      </div>

      {task.status === "approved" ? (
        <div className="rounded bg-emerald-50 p-2 text-xs text-emerald-800">
          <p>Signed by {task.signature_name || task.reviewer_name || "leader"}</p>
          {task.reviewed_at && <p className="mt-1">{new Date(task.reviewed_at).toLocaleString()}</p>}
        </div>
      ) : (
        <div className="space-y-2">
          <Button
            type="button"
            size="sm"
            variant="outline"
            className="w-full bg-white"
            onClick={openCase}
            disabled={isSaving || !canOpenCase}
          >
            <FileText className="size-4" />
            Open change package
          </Button>
          <input
            value={signature}
            onChange={(event) => setSignature(event.target.value)}
            className="h-8 w-full rounded border border-stone-200 px-2 text-xs outline-none focus:border-amber-400"
            placeholder="Signature name"
          />
          <textarea
            value={comment}
            onChange={(event) => setComment(event.target.value)}
            className="min-h-16 w-full rounded border border-stone-200 px-2 py-1.5 text-xs outline-none focus:border-amber-400"
            placeholder="Review comment"
          />
          <div className="grid grid-cols-2 gap-2">
            <Button
              type="button"
              size="sm"
              className="bg-emerald-600 hover:bg-emerald-700"
              onClick={() => review("approved")}
              disabled={isSaving || !canOpenCase || !signature.trim()}
            >
              Approve
            </Button>
            <Button
              type="button"
              size="sm"
              variant="outline"
              className="bg-white"
              onClick={() => review("changes_requested")}
              disabled={isSaving || !canOpenCase}
            >
              Request changes
            </Button>
          </div>
          {error && <p className="text-xs text-rose-600">{error}</p>}
        </div>
      )}
    </div>
  )
}
