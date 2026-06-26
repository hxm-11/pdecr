import { useQuery } from "@tanstack/react-query"
import { ClipboardCheck, UserCheck } from "lucide-react"

import { listMyPdEcrWorkflowTasks } from "@/lib/pdEcrApi"

function statusClass(status: string) {
  switch (status) {
    case "completed":
    case "approved":
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

export function PdEcrMyTasks() {
  const { data, isLoading, error } = useQuery({
    queryKey: ["pd-ecr-my-workflow-tasks"],
    queryFn: listMyPdEcrWorkflowTasks,
  })

  if (isLoading) return <p className="text-sm text-stone-500">Loading tasks...</p>
  if (error) return <p className="text-sm text-rose-600">Failed to load tasks.</p>

  const executionTasks = data?.execution_tasks || []
  const leaderTasks = data?.leader_review_tasks || []

  return (
    <div className="mx-auto max-w-6xl space-y-6 p-4 sm:p-6">
      <header>
        <h1 className="text-2xl font-semibold text-stone-900">PD-ECR My Tasks</h1>
        <p className="mt-1 text-sm text-stone-500">
          {executionTasks.length + leaderTasks.length} open workflow items
        </p>
      </header>

      <section>
        <div className="flex items-center gap-2">
          <ClipboardCheck className="size-4 text-amber-600" />
          <h2 className="text-base font-semibold text-stone-900">Execution Tasks</h2>
        </div>
        <div className="mt-3 divide-y divide-stone-100 rounded border border-stone-200 bg-white">
          {executionTasks.map((task) => (
            <div key={task.id} className="grid gap-2 p-3 sm:grid-cols-[1fr_auto] sm:items-start">
              <div className="min-w-0">
                <p className="text-sm font-semibold text-stone-800">{task.description}</p>
                <p className="mt-1 text-xs text-stone-500">
                  {task.department} · {task.assignee_name || task.assignee_email || "unassigned"}
                </p>
                {task.due_date && (
                  <p className="mt-1 text-xs text-stone-500">
                    Due {new Date(task.due_date).toLocaleDateString()}
                  </p>
                )}
              </div>
              <span className={`w-fit rounded-full border px-2 py-0.5 text-[10px] font-semibold ${statusClass(task.status)}`}>
                {task.status}
              </span>
            </div>
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
            <div key={task.id} className="grid gap-2 p-3 sm:grid-cols-[1fr_auto] sm:items-start">
              <div className="min-w-0">
                <p className="text-sm font-semibold capitalize text-stone-800">{task.department}</p>
                <p className="mt-1 text-xs text-stone-500">
                  {task.reviewer_name || task.reviewer_email || "unassigned reviewer"}
                </p>
                {task.review_comment && (
                  <p className="mt-1 text-xs text-stone-500">{task.review_comment}</p>
                )}
              </div>
              <span className={`w-fit rounded-full border px-2 py-0.5 text-[10px] font-semibold ${statusClass(task.status)}`}>
                {task.status}
              </span>
            </div>
          ))}
          {!leaderTasks.length && (
            <p className="p-3 text-sm text-stone-500">No leader reviews.</p>
          )}
        </div>
      </section>
    </div>
  )
}
