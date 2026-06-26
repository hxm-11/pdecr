import { useEffect, useMemo, useState, type Dispatch, type SetStateAction } from "react"
import { Button } from "@/components/ui/button"
import {
  assignPdEcrExecution,
  completePdEcrExecutionTask,
  confirmPdEcrExecutionAssignment,
  getPdEcrWorkflow,
  publishPdEcrDepartments,
  reviewPdEcrLeaderTask,
  type PdEcrExecutionAssignmentInput,
  type PdEcrExecutionWorkflowTask,
  type PdEcrLeaderReviewWorkflowTask,
  type PdEcrWorkflowState,
} from "@/lib/pdEcrApi"

const WORKFLOW_DEPTS = [
  { id: "design", label: "Development" },
  { id: "system", label: "System" },
  { id: "purchasing", label: "Purchasing" },
  { id: "manufacturing", label: "Manufacturing" },
  { id: "quality", label: "Quality" },
  { id: "pm", label: "PM / PMO / COS" },
  { id: "catalyst", label: "Catalyst" },
]

const DEPARTMENT_ID_BY_LABEL: Record<string, string> = {
  CPJM: "pm",
  COS: "pm",
  DEVELOPMENT: "design",
  DESIGN: "design",
  LOP: "pm",
  MANUFACTURING: "manufacturing",
  MFE: "manufacturing",
  MOEX: "manufacturing",
  OTHERS: "pm",
  PM: "pm",
  PMO: "pm",
  PURCHASING: "purchasing",
  QUALITY: "quality",
  SYSTEM: "system",
}

type ChecklistRow = {
  id: string
  department: string
  yn: string
  description: string
  responsible?: string
  dueDate?: string
}

const DEFAULT_IMPLEMENTATION_CHECKLIST: Omit<ChecklistRow, "id">[] = [
  { department: "Development", yn: "N", description: "Documents release (drawing, offer drawing, BOM, Spec., ...)", responsible: "", dueDate: "" },
  { department: "Development", yn: "N", description: "Change BOMs & Drawings & Documents in POE system", responsible: "", dueDate: "" },
  { department: "Development", yn: "N", description: "Inform documents update (check work-on can met requirements)", responsible: "", dueDate: "" },
  { department: "Development", yn: "Y", description: "Update Offer drawing, TCD, D-FMEA", responsible: "", dueDate: "" },
  { department: "Development", yn: "N", description: "Norm, WB, HF...", responsible: "", dueDate: "" },
  { department: "Development", yn: "N", description: "MoC, IMDS", responsible: "", dueDate: "" },
  { department: "Manufacturing", yn: "Y", description: "Related (Production/Testing) equipment be ready on site", responsible: "", dueDate: "" },
  { department: "Manufacturing", yn: "Y", description: "Related (Production/Testing) program be ready", responsible: "", dueDate: "" },
  { department: "Manufacturing", yn: "Y", description: "Related (Production/Testing) tooling / cutting / fixture etc. be ready", responsible: "", dueDate: "" },
  { department: "Manufacturing", yn: "Y", description: "Old tooling / cutting / fixture disposal", responsible: "", dueDate: "" },
  { department: "Manufacturing", yn: "Y", description: "Old materials disposal", responsible: "", dueDate: "" },
  { department: "Manufacturing", yn: "Y", description: "Planner update the planning sheet", responsible: "", dueDate: "" },
  { department: "Manufacturing", yn: "Y", description: "Update FMEA", responsible: "", dueDate: "" },
  { department: "Manufacturing", yn: "Y", description: "Update CP/FC (Control Plan/Flow Chart)", responsible: "", dueDate: "" },
  { department: "Manufacturing", yn: "Y", description: "Update WI/PDS (Include attachments.)", responsible: "", dueDate: "" },
  { department: "Manufacturing", yn: "Y", description: "First batch Mark, Special Mark (Inside Package)", responsible: "", dueDate: "" },
  { department: "Manufacturing", yn: "Y", description: "First batch Mark, Special Mark (Outside Package)", responsible: "", dueDate: "" },
  { department: "Manufacturing", yn: "Y", description: "Training", responsible: "", dueDate: "" },
  { department: "COS", yn: "Y", description: "Confirm the storage of old parts and coordinate the introduction date for new parts", responsible: "", dueDate: "" },
  { department: "COS", yn: "Y", description: "Confirm the delivery date of old parts and first delivery of new parts (FG)", responsible: "", dueDate: "" },
  { department: "COS", yn: "Y", description: "Check sample orders which affected: material order of CKD", responsible: "", dueDate: "" },
  { department: "COS", yn: "Y", description: "Confirm production scheduling according to the alignment, any changes share the information", responsible: "", dueDate: "" },
  { department: "COS", yn: "Y", description: "Confirm the old stock / do prioritize delivery and inventory handling", responsible: "", dueDate: "" },
  { department: "COS", yn: "Y", description: "Inform the first delivery to PMO", responsible: "", dueDate: "" },
  { department: "Purchasing", yn: "Y", description: "Check sample orders which affected: material order of purchasing parts", responsible: "", dueDate: "" },
  { department: "Purchasing", yn: "Y", description: "Inform internal related departments (COS, MFE, MOEx) with following requirements", responsible: "", dueDate: "" },
  { department: "Purchasing", yn: "Y", description: "Update incoming inspection plan", responsible: "", dueDate: "" },
  { department: "Quality", yn: "Y", description: "Update testing program on testing equipment", responsible: "", dueDate: "" },
  { department: "Quality", yn: "Y", description: "Update inspection plan for CKD parts", responsible: "", dueDate: "" },
  { department: "CPjM", yn: "Y", description: "Distribute the Offer drawing, TCD to customer", responsible: "", dueDate: "" },
  { department: "LOP", yn: "Y", description: "Check 10 digit material order", responsible: "", dueDate: "" },
  { department: "PMO", yn: "Y", description: "Check sample orders which affected: Customer order", responsible: "", dueDate: "" },
  { department: "PMO", yn: "Y", description: "Inform Customer the first delivery information", responsible: "", dueDate: "" },
  { department: "Others", yn: "", description: "", responsible: "", dueDate: "" },
]

function createDefaultImplementationChecklist(): ChecklistRow[] {
  return DEFAULT_IMPLEMENTATION_CHECKLIST.map((row, index) => ({
    ...row,
    id: `impl-default-${index + 1}`,
  }))
}

function workflowBadgeClass(status: string) {
  switch (status) {
    case "completed":
    case "approved":
    case "confirmed":
      return "border-emerald-200 bg-emerald-50 text-emerald-700"
    case "changes_requested":
    case "rejected":
      return "border-rose-200 bg-rose-50 text-rose-700"
    case "pending_confirmation":
    case "leader_review":
    case "in_progress":
      return "border-amber-200 bg-amber-50 text-amber-700"
    default:
      return "border-stone-200 bg-stone-50 text-stone-600"
  }
}

function normalizeDepartmentId(label: string) {
  const normalized = label.trim().toUpperCase()
  return DEPARTMENT_ID_BY_LABEL[normalized] || normalized.toLowerCase()
}

function loadImplementationChecklist(): ChecklistRow[] {
  try {
    const raw = localStorage.getItem("pd-ecr-implementation-implementation-plan")
    const parsed = raw ? JSON.parse(raw) : null
    return Array.isArray(parsed?.checklistRows) ? parsed.checklistRows : createDefaultImplementationChecklist()
  } catch {
    return createDefaultImplementationChecklist()
  }
}

export function PdEcrExecutionWorkflowPanel({
  caseId,
  onComplete,
}: {
  caseId: string
  onComplete?: () => void
}) {
  const [workflow, setWorkflow] = useState<PdEcrWorkflowState | null>(null)
  const [selected, setSelected] = useState<Record<string, boolean>>({ quality: true })
  const [selectionTouched, setSelectionTouched] = useState(false)
  const [checklistRows, setChecklistRows] = useState<ChecklistRow[]>(() => loadImplementationChecklist())
  const [assignmentEmails, setAssignmentEmails] = useState<Record<string, string>>({})
  const [statusText, setStatusText] = useState("Loading workflow...")
  const [isSaving, setIsSaving] = useState(false)

  useEffect(() => {
    let mounted = true
    getPdEcrWorkflow(caseId)
      .then((state) => {
        if (!mounted) return
        setWorkflow(state)
        setStatusText("Workflow ready")
      })
      .catch(() => {
        if (!mounted) return
        setStatusText("Workflow not started")
      })
    return () => {
      mounted = false
    }
  }, [caseId])

  useEffect(() => {
    const refresh = () => setChecklistRows(loadImplementationChecklist())
    const timer = window.setInterval(refresh, 1500)
    window.addEventListener("focus", refresh)
    return () => {
      window.clearInterval(timer)
      window.removeEventListener("focus", refresh)
    }
  }, [])

  const yRows = useMemo(
    () => checklistRows.filter((row) => row.yn === "Y"),
    [checklistRows],
  )

  const publishedDepartments = useMemo(
    () => new Set((workflow?.department_visibility || []).map((item) => item.department)),
    [workflow?.department_visibility],
  )
  const hasExecutionTasks = !!workflow?.execution_tasks.length

  useEffect(() => {
    if (selectionTouched || publishedDepartments.size || !yRows.length) return
    setSelected((prev) => {
      const next = { ...prev }
      yRows.forEach((row) => {
        const department = normalizeDepartmentId(row.department)
        if (WORKFLOW_DEPTS.some((dept) => dept.id === department)) {
          next[department] = true
        }
      })
      return next
    })
  }, [publishedDepartments.size, selectionTouched, yRows])

  const publishDepartments = async () => {
    const departments = WORKFLOW_DEPTS.filter((dept) => selected[dept.id]).map((dept) => dept.id)
    setIsSaving(true)
    setStatusText("Publishing departments...")
    try {
      const next = await publishPdEcrDepartments(caseId, departments)
      setWorkflow(next)
      setStatusText("Published to involved departments")
    } catch (err) {
      setStatusText(err instanceof Error ? err.message : "Publish failed")
    } finally {
      setIsSaving(false)
    }
  }

  const assignExecution = async () => {
    const currentRows = loadImplementationChecklist()
    const currentYRows = currentRows.filter((row) => row.yn === "Y")
    setChecklistRows(currentRows)
    const assignments: PdEcrExecutionAssignmentInput[] = currentYRows.map((row) => ({
      checklist_row_id: row.id,
      department: normalizeDepartmentId(row.department),
      description: row.description,
      assignee_email: assignmentEmails[row.id] || row.responsible || "",
      assignee_name: assignmentEmails[row.id] || row.responsible || "",
      due_date: row.dueDate || null,
    }))
    setIsSaving(true)
    setStatusText("Assigning execution tasks...")
    try {
      const next = await assignPdEcrExecution(caseId, assignments)
      setWorkflow(next)
      setStatusText("Execution assignments sent")
    } catch (err) {
      setStatusText(err instanceof Error ? err.message : "Assignment failed")
    } finally {
      setIsSaving(false)
    }
  }

  const allApproved = workflow?.leader_review_tasks.length
    ? workflow.leader_review_tasks.every((task) => task.status === "approved")
    : false

  return (
    <div className="sticky top-4 space-y-4" style={{ maxHeight: "calc(100vh - 8rem)", overflowY: "auto" }}>
      <div className="rounded-lg border border-amber-300 bg-white shadow-sm">
        <div className="rounded-t-lg bg-amber-600 px-4 py-2.5 text-sm font-semibold text-white">
          PD-ECR Workflow
        </div>
        <div className="space-y-3 p-3">
          <p className="text-xs text-stone-500" role="status">{statusText}</p>
          {workflow && (
            <span className={`inline-flex rounded-full border px-2 py-0.5 text-[10px] font-semibold ${workflowBadgeClass(workflow.case.status)}`}>
              {workflow.case.status}
            </span>
          )}
          <DepartmentPublishStep
            publishedDepartments={publishedDepartments}
            selected={selected}
            setSelected={setSelected}
            onTouchSelection={() => setSelectionTouched(true)}
            onSubmit={publishDepartments}
            disabled={isSaving || hasExecutionTasks}
          />
          <ExecutionAssignmentStep
            rows={yRows}
            assignmentEmails={assignmentEmails}
            setAssignmentEmails={setAssignmentEmails}
            onSubmit={assignExecution}
            disabled={isSaving || hasExecutionTasks || !yRows.length || yRows.some((row) => !(assignmentEmails[row.id] || row.responsible || "").trim())}
          />
        </div>
      </div>

      {workflow?.execution_tasks.length ? (
        <div className="space-y-2">
          <p className="text-xs font-semibold uppercase text-stone-500">Execution tasks</p>
          {workflow.execution_tasks.map((task) => (
            <ExecutionTaskCard key={task.id} task={task} onRefresh={setWorkflow} />
          ))}
        </div>
      ) : null}

      {workflow?.leader_review_tasks.length ? (
        <div className="space-y-2">
          <p className="text-xs font-semibold uppercase text-stone-500">Leader review</p>
          {workflow.leader_review_tasks.map((task) => (
            <LeaderReviewCard key={task.id} task={task} onRefresh={setWorkflow} />
          ))}
        </div>
      ) : null}

      {allApproved && onComplete && (
        <Button type="button" className="w-full bg-emerald-600 hover:bg-emerald-700" onClick={onComplete}>
          全部签核完成，查看结果
        </Button>
      )}
    </div>
  )
}

function DepartmentPublishStep({
  publishedDepartments,
  selected,
  setSelected,
  onTouchSelection,
  onSubmit,
  disabled,
}: {
  publishedDepartments: Set<string>
  selected: Record<string, boolean>
  setSelected: Dispatch<SetStateAction<Record<string, boolean>>>
  onTouchSelection: () => void
  onSubmit: () => void
  disabled: boolean
}) {
  return (
    <div className="space-y-2">
      <p className="text-xs font-semibold text-stone-600">Involved departments</p>
      {WORKFLOW_DEPTS.map((dept) => (
        <label key={dept.id} className="flex items-center gap-2 rounded border border-stone-100 p-2 text-xs">
          <input
            type="checkbox"
            checked={!!selected[dept.id]}
            onChange={(event) => {
              onTouchSelection()
              setSelected((prev) => ({ ...prev, [dept.id]: event.target.checked }))
            }}
            className="accent-amber-600"
          />
          <span className="font-semibold text-stone-700">{dept.label}</span>
          {publishedDepartments.has(dept.id) && (
            <span className="ml-auto rounded-full border border-emerald-200 bg-emerald-50 px-1.5 py-0.5 text-[10px] font-semibold text-emerald-700">
              visible
            </span>
          )}
        </label>
      ))}
      <Button type="button" className="w-full bg-stone-800 hover:bg-stone-700" onClick={onSubmit} disabled={disabled}>
        Publish to departments
      </Button>
    </div>
  )
}

function ExecutionAssignmentStep({
  rows,
  assignmentEmails,
  setAssignmentEmails,
  onSubmit,
  disabled,
}: {
  rows: ChecklistRow[]
  assignmentEmails: Record<string, string>
  setAssignmentEmails: Dispatch<SetStateAction<Record<string, string>>>
  onSubmit: () => void
  disabled: boolean
}) {
  return (
    <div className="space-y-2">
      <p className="text-xs font-semibold text-stone-600">Assign Y checklist rows</p>
      {rows.length ? (
        rows.map((row) => (
          <label key={row.id} className="block rounded border border-stone-100 p-2 text-xs">
            <span className="font-semibold text-stone-700">{row.department}</span>
            <span className="mt-1 block text-stone-500">{row.description}</span>
            <input
              value={assignmentEmails[row.id] || ""}
              onChange={(event) => setAssignmentEmails((prev) => ({ ...prev, [row.id]: event.target.value }))}
              className="mt-2 h-8 w-full rounded border border-stone-200 px-2 outline-none focus:border-amber-400"
              placeholder={row.responsible || "assignee@email.com"}
            />
          </label>
        ))
      ) : (
        <p className="rounded border border-stone-100 bg-stone-50 p-2 text-xs text-stone-500">No Y checklist rows</p>
      )}
      <Button type="button" className="w-full bg-amber-600 hover:bg-amber-700" onClick={onSubmit} disabled={disabled}>
        Assign execution tasks
      </Button>
    </div>
  )
}

function ExecutionTaskCard({
  task,
  onRefresh,
}: {
  task: PdEcrExecutionWorkflowTask
  onRefresh: (state: PdEcrWorkflowState) => void
}) {
  const [result, setResult] = useState(task.execution_result || "completed")
  const [note, setNote] = useState(task.execution_note || "")
  const [evidence, setEvidence] = useState(task.evidence_note || "")
  const [isSaving, setIsSaving] = useState(false)
  const [error, setError] = useState("")

  const confirmAssignment = async () => {
    setIsSaving(true)
    setError("")
    try {
      const next = await confirmPdEcrExecutionAssignment(task.id)
      onRefresh(next)
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
      const next = await completePdEcrExecutionTask(task.id, {
        execution_result: result,
        execution_note: note,
        evidence_note: evidence,
      })
      onRefresh(next)
    } catch (err) {
      setError(err instanceof Error ? err.message : "Complete failed")
    } finally {
      setIsSaving(false)
    }
  }

  return (
    <div className="rounded border border-stone-200 bg-white p-3">
      <div className="flex items-center justify-between gap-2">
        <p className="text-sm font-semibold text-stone-800">{task.department}</p>
        <span className={`rounded-full border px-2 py-0.5 text-[10px] font-semibold ${workflowBadgeClass(task.status)}`}>
          {task.status}
        </span>
      </div>
      <p className="mt-1 text-xs text-stone-500">{task.description}</p>
      <p className="mt-1 text-xs text-stone-500">{task.assignee_name || task.assignee_email || "未分配"}</p>

      {task.status === "pending_confirmation" || task.status === "changes_requested" ? (
        <div className="mt-3 space-y-2">
          {task.status === "changes_requested" && task.review_comment ? (
            <p className="rounded bg-rose-50 p-2 text-xs text-rose-700">{task.review_comment}</p>
          ) : null}
          {error && <p className="text-xs text-rose-600">{error}</p>}
          <Button type="button" size="sm" className="w-full bg-emerald-600 hover:bg-emerald-700" onClick={confirmAssignment} disabled={isSaving}>
            {isSaving ? "确认中..." : task.status === "changes_requested" ? "Confirm changes" : "Confirm assignment"}
          </Button>
        </div>
      ) : null}

      {task.status === "in_progress" ? (
        <div className="mt-3 space-y-2">
          <input
            value={result}
            onChange={(event) => setResult(event.target.value)}
            className="h-8 w-full rounded border border-stone-200 px-2 text-xs outline-none focus:border-amber-400"
            placeholder="Execution result"
          />
          <textarea
            value={note}
            onChange={(event) => setNote(event.target.value)}
            className="min-h-14 w-full rounded border border-stone-200 px-2 py-1.5 text-xs outline-none focus:border-amber-400"
            placeholder="Execution note / 执行结果"
          />
          <textarea
            value={evidence}
            onChange={(event) => setEvidence(event.target.value)}
            className="min-h-14 w-full rounded border border-stone-200 px-2 py-1.5 text-xs outline-none focus:border-amber-400"
            placeholder="Evidence note / 验证记录"
          />
          {error && <p className="text-xs text-rose-600">{error}</p>}
          <Button type="button" size="sm" className="w-full bg-emerald-600 hover:bg-emerald-700" onClick={completeTask} disabled={isSaving || !result.trim()}>
            {isSaving ? "提交中..." : "Complete execution"}
          </Button>
        </div>
      ) : null}

      {task.status === "completed" ? (
        <div className="mt-3 rounded bg-emerald-50 p-2 text-xs text-emerald-800">
          <p>{task.execution_result || "completed"}</p>
          {task.execution_note && <p className="mt-1">{task.execution_note}</p>}
          {task.evidence_note && <p className="mt-1">{task.evidence_note}</p>}
          {task.completed_by_name && <p className="mt-1">执行人：{task.completed_by_name}</p>}
        </div>
      ) : null}
    </div>
  )
}

function LeaderReviewCard({
  task,
  onRefresh,
}: {
  task: PdEcrLeaderReviewWorkflowTask
  onRefresh: (state: PdEcrWorkflowState) => void
}) {
  const [comment, setComment] = useState(task.review_comment || "")
  const [signature, setSignature] = useState(task.signature_name || task.reviewer_name || "")
  const [isSaving, setIsSaving] = useState(false)
  const [error, setError] = useState("")

  const review = async (decision: "approved" | "rejected" | "changes_requested") => {
    setIsSaving(true)
    setError("")
    try {
      const next = await reviewPdEcrLeaderTask(task.id, {
        decision,
        review_comment: comment,
        signature_name: signature,
      })
      onRefresh(next)
    } catch (err) {
      setError(err instanceof Error ? err.message : "Review failed")
    } finally {
      setIsSaving(false)
    }
  }

  return (
    <div className="rounded border border-stone-200 bg-white p-3">
      <div className="flex items-center justify-between gap-2">
        <p className="text-sm font-semibold capitalize text-stone-800">{task.department}</p>
        <span className={`rounded-full border px-2 py-0.5 text-[10px] font-semibold ${workflowBadgeClass(task.status)}`}>
          {task.status}
        </span>
      </div>
      <p className="mt-1 text-xs text-stone-500">
        {task.reviewer_name || task.reviewer_email || "等待 leader 分配"}
      </p>
      {task.status === "approved" ? (
        <div className="mt-3 rounded bg-emerald-50 p-2 text-xs text-emerald-800">
          <p>签核：{task.signature_name || task.reviewer_name}</p>
          {task.reviewed_at && <p className="mt-1">{new Date(task.reviewed_at).toLocaleString()}</p>}
        </div>
      ) : (
        <div className="mt-3 space-y-2">
          <input
            value={signature}
            onChange={(event) => setSignature(event.target.value)}
            className="h-8 w-full rounded border border-stone-200 px-2 text-xs outline-none focus:border-amber-400"
            placeholder="Signature name / 签核人"
          />
          <textarea
            value={comment}
            onChange={(event) => setComment(event.target.value)}
            className="min-h-14 w-full rounded border border-stone-200 px-2 py-1.5 text-xs outline-none focus:border-amber-400"
            placeholder="Review comment / 审核意见"
          />
          {error && <p className="text-xs text-rose-600">{error}</p>}
          <div className="grid grid-cols-2 gap-2">
            <Button type="button" size="sm" className="bg-emerald-600 hover:bg-emerald-700" onClick={() => review("approved")} disabled={isSaving || !signature.trim()}>
              Approve
            </Button>
            <Button type="button" size="sm" variant="outline" className="bg-white" onClick={() => review("changes_requested")} disabled={isSaving}>
              退回
            </Button>
          </div>
        </div>
      )}
    </div>
  )
}
