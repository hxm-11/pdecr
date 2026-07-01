import { useMutation, useQuery } from "@tanstack/react-query";
import { useNavigate } from "@tanstack/react-router";
import { ClipboardCheck, FileText, UserCheck } from "lucide-react";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import {
  approvePdEcrCase,
  completePdEcrExecutionTask,
  confirmPdEcrExecutionAssignment,
  getPdEcrCase,
  listMyPdEcrWorkflowTasks,
  rejectPdEcrCase,
  reviewPdEcrLeaderTask,
  type PdEcrApprovalTask,
  type PdEcrDbModule,
  type PdEcrDepartmentWorkflowTask,
  type PdEcrExecutionWorkflowTask,
  type PdEcrLeaderReviewWorkflowTask,
  type PdEcrTaskTarget,
} from "@/lib/pdEcrApi";
import {
  fallbackGeneratedModules,
  normalizeModules,
  saveActiveResult,
} from "./pdEcrState";
import {
  flattenMyWorkflowTasks,
  isTaskOverdue,
  workflowTaskDueLabel,
} from "./PdEcrWorkflowRules";

type TaskFilter =
  | "all"
  | "confirmation"
  | "signoff"
  | "submitted"
  | "execution"
  | "supplement"
  | "overdue"
  | "returned";

type WorkflowTask =
  | PdEcrApprovalTask
  | PdEcrDepartmentWorkflowTask
  | PdEcrExecutionWorkflowTask
  | PdEcrLeaderReviewWorkflowTask;

type OpenTaskTarget = WorkflowTask & PdEcrTaskTarget;

function statusClass(status: string) {
  switch (status) {
    case "completed":
    case "approved":
    case "confirmed":
      return "border-emerald-200 bg-emerald-50 text-emerald-700";
    case "changes_requested":
    case "rejected":
      return "border-rose-200 bg-rose-50 text-rose-700";
    case "pending_confirmation":
    case "in_progress":
    case "pending":
      return "border-amber-200 bg-amber-50 text-amber-700";
    default:
      return "border-stone-200 bg-stone-50 text-stone-600";
  }
}

function isOpenExecutionTask(task: PdEcrExecutionWorkflowTask) {
  return !["completed", "cancelled"].includes(task.status);
}

function isOpenLeaderTask(task: PdEcrLeaderReviewWorkflowTask) {
  return !["approved", "rejected"].includes(task.status);
}

function taskCaseLabel(task: WorkflowTask) {
  return (
    task.case?.case_no ||
    task.case?.dc_no ||
    task.case?.mcr_no ||
    task.case?.id ||
    task.case_id
  );
}

function taskCaseTitle(task: WorkflowTask) {
  return (
    task.case?.title || task.case?.customer_project || "PD-ECR change package"
  );
}

function taskCaseId(task: WorkflowTask) {
  return task.case?.id || task.case_id;
}

function canOpenTaskCase(task: WorkflowTask) {
  return task.case_exists !== false;
}

function taskBucket(task: WorkflowTask) {
  if (task.task_bucket) return task.task_bucket;
  if (["changes_requested", "rejected"].includes(task.status))
    return "supplement";
  if ("checklist_row_id" in task) {
    return task.status === "pending_confirmation"
      ? "confirmation"
      : "execution";
  }
  if ("impact_result" in task) return "confirmation";
  return "signoff";
}

function isReturnedTask(task: WorkflowTask) {
  return task.status === "rejected";
}

function isClosedTask(task: WorkflowTask) {
  return ["approved", "completed", "confirmed", "cancelled"].includes(
    task.status,
  );
}

function taskMatchesFilter(task: WorkflowTask, filter: TaskFilter) {
  if (filter === "all" && "approver_email" in task) return true;
  if (filter === "all") return !isClosedTask(task) || isReturnedTask(task);
  if (filter === "overdue") return isTaskOverdue(task);
  if (filter === "returned") return isReturnedTask(task);
  if (filter === "supplement") {
    return (
      taskBucket(task) === "supplement" || task.status === "changes_requested"
    );
  }
  return !isClosedTask(task) && taskBucket(task) === filter;
}

function openButtonLabel(task: WorkflowTask) {
  if (task.module_id && task.field_path) return "Open target field";
  if (task.module_id) return "Open target module";
  return "Open change package";
}

function errorMessage(error: unknown) {
  if (!error || typeof error !== "object") return "Unknown error";
  const record = error as {
    message?: string;
    response?: { status?: number; data?: unknown };
  };
  const detail =
    record.response?.data && typeof record.response.data === "object"
      ? (record.response.data as { detail?: unknown }).detail
      : undefined;
  return [
    record.response?.status ? `HTTP ${record.response.status}` : "",
    typeof detail === "string" ? detail : record.message || "Request failed",
  ]
    .filter(Boolean)
    .join(": ");
}

function mapCaseModules(modules: PdEcrDbModule[]) {
  return modules.map((module) => {
    const contentJson = module.content_json || {};
    const content =
      contentJson.content || module.content_md || module.title || "";
    const warnings = Array.isArray(contentJson.warnings)
      ? contentJson.warnings
      : [];

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
    };
  });
}

function MetricCard({
  label,
  value,
  tone,
}: {
  label: string;
  value: number;
  tone?: "default" | "accent";
}) {
  return (
    <div className="enterprise-panel px-4 py-3 text-center">
      <p
        className={
          tone === "accent"
            ? "text-lg font-semibold text-blue-700"
            : "text-lg font-semibold text-slate-900"
        }
      >
        {value}
      </p>
      <p className="text-xs text-slate-500">{label}</p>
    </div>
  );
}

export function PdEcrMyTasks() {
  const navigate = useNavigate();
  const [message, setMessage] = useState("");
  const [taskFilter, setTaskFilter] = useState<TaskFilter>("all");
  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ["pd-ecr-my-workflow-tasks"],
    queryFn: listMyPdEcrWorkflowTasks,
  });

  if (isLoading)
    return (
      <p className="page-shell text-sm text-slate-500">Loading tasks...</p>
    );
  if (error) {
    return (
      <div className="page-shell w-full min-w-0">
        <div className="rounded border border-rose-200 bg-rose-50 p-4 text-sm text-rose-700">
          <p className="font-semibold">My Tasks 加载失败</p>
          <p className="mt-1">{errorMessage(error)}</p>
        </div>
      </div>
    );
  }

  const executionTasks = data?.execution_tasks || [];
  const leaderTasks = data?.leader_review_tasks || [];
  const approvalTasks = data?.approval_tasks || [];
  const submittedApprovalTasks = data?.submitted_approval_tasks || [];
  const departmentTasks = data?.department_tasks || [];
  const allTasks: WorkflowTask[] = [
    ...approvalTasks,
    ...departmentTasks,
    ...executionTasks,
    ...leaderTasks,
  ];
  const flattenedTasks = flattenMyWorkflowTasks({
    executionTasks,
    leaderTasks,
    departmentTasks,
  });
  const openExecutionCount = executionTasks.filter(isOpenExecutionTask).length;
  const openLeaderReviewCount = leaderTasks.filter(isOpenLeaderTask).length;
  const overdueCount =
    allTasks.filter(isTaskOverdue).length ||
    flattenedTasks.filter(isTaskOverdue).length;
  const pendingApprovalCount = approvalTasks.filter(
    (t) => t.status === "pending",
  ).length;
  const submittedApprovalCount = submittedApprovalTasks.filter(
    (t) => t.status === "pending",
  ).length;
  const confirmationCount = allTasks.filter((task) =>
    taskMatchesFilter(task, "confirmation"),
  ).length;
  const signoffCount = allTasks.filter((task) =>
    taskMatchesFilter(task, "signoff"),
  ).length;
  const supplementCount = allTasks.filter((task) =>
    taskMatchesFilter(task, "supplement"),
  ).length;
  const returnedCount = allTasks.filter((task) =>
    taskMatchesFilter(task, "returned"),
  ).length;
  const openCount =
    openExecutionCount +
    openLeaderReviewCount +
    departmentTasks.length +
    pendingApprovalCount;
  const visibleApprovalTasks = approvalTasks.filter((task) =>
    taskMatchesFilter(task, taskFilter),
  );
  const visibleSubmittedApprovalTasks = submittedApprovalTasks.filter((task) => {
    if (taskFilter === "submitted") return true;
    if (taskFilter === "all") return true;
    if (taskFilter === "returned") return isReturnedTask(task);
    return false;
  });
  const visibleDepartmentTasks = departmentTasks.filter((task) =>
    taskMatchesFilter(task, taskFilter),
  );
  const visibleExecutionTasks = executionTasks.filter((task) =>
    taskMatchesFilter(task, taskFilter),
  );
  const visibleLeaderTasks = leaderTasks.filter((task) =>
    taskMatchesFilter(task, taskFilter),
  );
  const taskFilterOptions: Array<{
    value: TaskFilter;
    label: string;
    count: number;
  }> = [
    { value: "all", label: "全部待办", count: openCount },
    { value: "confirmation", label: "我的待确认", count: confirmationCount },
    { value: "signoff", label: "我的待签核", count: signoffCount },
    { value: "submitted", label: "我发起的", count: submittedApprovalCount },
    { value: "execution", label: "我的待执行", count: openExecutionCount },
    { value: "supplement", label: "我的待补资料", count: supplementCount },
    { value: "overdue", label: "超期任务", count: overdueCount },
    { value: "returned", label: "退回任务", count: returnedCount },
  ];

  const refreshAfterAction = async (nextMessage: string) => {
    setMessage(nextMessage);
    await refetch();
  };

  const openCase = async (caseId: string, target?: OpenTaskTarget) => {
    setMessage("Loading change package...");
    try {
      if (target && "approver_email" in target) {
        navigate({
          to: "/pd-ecr",
          search: {
            caseId,
            taskId: target.id,
          } as never,
        });
        setMessage("");
        return;
      }

      const detail = await getPdEcrCase(caseId);
      const modules = normalizeModules(
        mapCaseModules(detail.modules),
        fallbackGeneratedModules,
      );
      const label = detail.case.case_no || detail.case.dc_no || detail.case.id;
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
      });
      if (target?.module_id) {
        navigate({
          to: "/pd-ecr/content/$moduleId",
          params: { moduleId: target.module_id },
          search: {
            field: target.field_path || undefined,
            anchor: target.anchor_id || undefined,
            taskId: target.id,
          } as never,
        });
        return;
      }
      navigate({ to: "/pd-ecr/content" });
    } catch (err) {
      setMessage("");
      throw err;
    }
  };

  return (
    <div className="page-shell w-full min-w-0">
      <header className="enterprise-panel px-5 py-4">
        <div className="flex flex-col justify-between gap-3 lg:flex-row lg:items-center">
          <div>
            <p className="enterprise-section-title text-blue-700">
              Workflow inbox
            </p>
            <h1 className="mt-1 text-2xl font-semibold tracking-tight text-slate-900">
              PD-ECR My Tasks
            </h1>
            <p className="mt-1 text-sm text-slate-500">
              {openCount} open workflow items
            </p>
          </div>
          <Button
            type="button"
            variant="outline"
            className="w-fit bg-white hover:border-blue-300 hover:bg-blue-50"
            onClick={() => refetch()}
          >
            Refresh
          </Button>
        </div>
        {message ? (
          <p className="mt-2 rounded border border-emerald-200 bg-emerald-50 px-3 py-2 text-sm text-emerald-700">
            {message}
          </p>
        ) : null}
      </header>

      <div className="mb-4 grid grid-cols-2 gap-3 lg:grid-cols-5">
        <MetricCard label="待签核" value={signoffCount} tone="accent" />
        <MetricCard label="待确认" value={confirmationCount} />
        <MetricCard label="待执行" value={openExecutionCount} />
        <MetricCard label="待补资料" value={supplementCount} />
        <MetricCard label="超期任务" value={overdueCount} tone="accent" />
      </div>

      <div className="enterprise-panel flex flex-wrap gap-2 p-3">
        {taskFilterOptions.map((option) => (
          <button
            key={option.value}
            type="button"
            onClick={() => setTaskFilter(option.value)}
            className={
              taskFilter === option.value
                ? "rounded-md border border-blue-300 bg-blue-50 px-3 py-1 text-xs font-semibold text-blue-700"
                : "rounded-md border border-slate-200 bg-white px-3 py-1 text-xs font-semibold text-slate-600 hover:bg-slate-50"
            }
          >
            {option.label} · {option.count}
          </button>
        ))}
      </div>

      {/* Approval Tasks */}
      {visibleApprovalTasks.length > 0 && (
        <section className="enterprise-panel mb-4 overflow-hidden">
          <header className="flex items-center gap-3 border-b border-slate-200 bg-slate-50/70 px-5 py-3">
            <h2 className="text-sm font-semibold text-slate-900">
              Manager Approvals / 经理审批
            </h2>
            <span className="rounded-md bg-blue-100 px-2 py-0.5 text-[10px] font-semibold text-blue-700">
              {pendingApprovalCount} pending
            </span>
          </header>
          <div className="divide-y divide-slate-100">
            {visibleApprovalTasks.map((task) => (
              <ApprovalTaskRow
                key={task.id}
                task={task}
                onOpenCase={openCase}
                onRefresh={refetch}
              />
            ))}
          </div>
        </section>
      )}

      {visibleSubmittedApprovalTasks.length > 0 && (
        <section className="enterprise-panel mb-4 overflow-hidden">
          <header className="flex items-center gap-3 border-b border-slate-200 bg-slate-50/70 px-5 py-3">
            <h2 className="text-sm font-semibold text-slate-900">
              My Submitted Approvals / 我发起的领导确认
            </h2>
            <span className="rounded-md bg-blue-100 px-2 py-0.5 text-[10px] font-semibold text-blue-700">
              {submittedApprovalCount} pending
            </span>
          </header>
          <div className="divide-y divide-slate-100">
            {visibleSubmittedApprovalTasks.map((task) => (
              <ApprovalTaskRow
                key={task.id}
                task={task}
                onOpenCase={openCase}
                onRefresh={refetch}
                readOnly
              />
            ))}
          </div>
        </section>
      )}

      {/* Department Tasks */}
      {visibleDepartmentTasks.length > 0 && (
        <section className="enterprise-panel mb-4 overflow-hidden">
          <header className="flex items-center gap-3 border-b border-slate-200 bg-slate-50/70 px-5 py-3">
            <h2 className="text-sm font-semibold text-slate-900">
              Department Confirmation / 部门影响确认
            </h2>
            <span className="rounded-md bg-blue-100 px-2 py-0.5 text-[10px] font-semibold text-blue-700">
              {visibleDepartmentTasks.length} tasks
            </span>
          </header>
          <div className="divide-y divide-slate-100">
            {visibleDepartmentTasks.map((task) => (
              <DepartmentTaskRow
                key={task.id}
                task={task}
                onOpenCase={openCase}
              />
            ))}
          </div>
        </section>
      )}

      <section className="enterprise-panel overflow-hidden">
        <div className="flex items-center gap-2 border-b border-slate-200 bg-slate-50/70 px-5 py-3">
          <ClipboardCheck className="size-4 text-blue-700" />
          <h2 className="text-sm font-semibold text-slate-900">
            Execution Tasks
          </h2>
        </div>
        <div className="divide-y divide-slate-100">
          {visibleExecutionTasks.map((task) => (
            <ExecutionTaskRow
              key={task.id}
              task={task}
              onOpenCase={openCase}
              onChanged={refreshAfterAction}
            />
          ))}
          {!visibleExecutionTasks.length && (
            <p className="p-5 text-sm text-slate-500">No execution tasks.</p>
          )}
        </div>
      </section>

      <section className="enterprise-panel overflow-hidden">
        <div className="flex items-center gap-2 border-b border-slate-200 bg-slate-50/70 px-5 py-3">
          <UserCheck className="size-4 text-blue-700" />
          <h2 className="text-sm font-semibold text-slate-900">
            Leader Reviews
          </h2>
        </div>
        <div className="divide-y divide-slate-100">
          {visibleLeaderTasks.map((task) => (
            <LeaderReviewRow
              key={task.id}
              task={task}
              onOpenCase={openCase}
              onChanged={refreshAfterAction}
            />
          ))}
          {!visibleLeaderTasks.length && (
            <p className="p-5 text-sm text-slate-500">No leader reviews.</p>
          )}
        </div>
      </section>
    </div>
  );
}

function ExecutionTaskRow({
  task,
  onOpenCase,
  onChanged,
}: {
  task: PdEcrExecutionWorkflowTask;
  onOpenCase: (caseId: string, target?: OpenTaskTarget) => Promise<void>;
  onChanged: (message: string) => Promise<void>;
}) {
  const [result, setResult] = useState(task.execution_result || "completed");
  const [note, setNote] = useState(task.execution_note || "");
  const [evidence, setEvidence] = useState(task.evidence_note || "");
  const [error, setError] = useState("");
  const [isSaving, setIsSaving] = useState(false);
  const caseLabel = taskCaseLabel(task);
  const canOpenCase = canOpenTaskCase(task);

  const openCase = async () => {
    if (!canOpenCase) {
      setError("该任务指向的后端案例不存在，无法打开变更包。");
      return;
    }
    setIsSaving(true);
    setError("");
    try {
      await onOpenCase(taskCaseId(task), task);
    } catch (err) {
      setError(errorMessage(err));
      setIsSaving(false);
    }
  };

  const confirmAssignment = async () => {
    setIsSaving(true);
    setError("");
    try {
      await confirmPdEcrExecutionAssignment(task.id);
      await onChanged("Assignment confirmed. Execution can start.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Confirm failed");
    } finally {
      setIsSaving(false);
    }
  };

  const completeTask = async () => {
    setIsSaving(true);
    setError("");
    try {
      await completePdEcrExecutionTask(task.id, {
        execution_result: result,
        execution_note: note,
        evidence_note: evidence,
      });
      await onChanged("Execution result submitted.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Submit failed");
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <div className="grid gap-3 p-3 lg:grid-cols-[1fr_17rem] lg:items-start">
      <div className="min-w-0">
        <div className="flex flex-wrap items-center gap-2">
          <p className="text-sm font-semibold text-stone-800">
            {task.description}
          </p>
          <span
            className={`w-fit rounded-full border px-2 py-0.5 text-[10px] font-semibold shadow-sm ${statusClass(task.status)}`}
          >
            {task.status}
          </span>
        </div>
        <p className="mt-1 text-xs text-stone-500">
          {caseLabel} · {taskCaseTitle(task)} · {task.department} ·{" "}
          {task.assignee_name || task.assignee_email || "unassigned"}
        </p>
        {!canOpenCase ? (
          <p className="mt-2 rounded bg-rose-50 p-2 text-xs text-rose-700">
            该任务仍在列表中，但它关联的后端案例已经不存在或不可访问，因此不能打开变更包。
          </p>
        ) : null}
        {task.due_date && (
          <p
            className={`mt-1 text-xs ${isTaskOverdue(task) ? "font-semibold text-rose-600" : "text-stone-500"}`}
          >
            {workflowTaskDueLabel(task)} · Due{" "}
            {new Date(task.due_date).toLocaleDateString()}
          </p>
        )}
        {task.review_comment && (
          <p className="mt-2 rounded bg-rose-50 p-2 text-xs text-rose-700">
            {task.review_comment}
          </p>
        )}
        {task.status === "pending_confirmation" ? (
          <p className="mt-2 rounded bg-amber-50 p-2 text-xs text-amber-800">
            请先打开变更包确认变更描述、影响分析、验证计划和实施计划，再确认
            assignment。
          </p>
        ) : null}
      </div>

      <div className="space-y-2">
        <Button
          type="button"
          size="sm"
          variant="outline"
          className="w-full bg-white hover:bg-amber-50 hover:border-amber-300"
          onClick={openCase}
          disabled={isSaving || !canOpenCase}
        >
          <FileText className="size-4" />
          {openButtonLabel(task)}
        </Button>

        {(task.status === "pending_confirmation" ||
          task.status === "changes_requested") && (
          <Button
            type="button"
            size="sm"
            className="w-full bg-emerald-600 hover:bg-emerald-700"
            onClick={confirmAssignment}
            disabled={isSaving || !canOpenCase}
          >
            {task.status === "changes_requested"
              ? "Confirm rework"
              : "Confirm assignment"}
          </Button>
        )}

        {task.status === "in_progress" && (
          <>
            <input
              value={result}
              onChange={(event) => setResult(event.target.value)}
              className="h-8 w-full rounded border border-stone-200 px-2 text-xs outline-none focus:border-amber-500 focus:ring-2 focus:ring-amber-200/80"
              placeholder="Execution result"
            />
            <textarea
              value={note}
              onChange={(event) => setNote(event.target.value)}
              className="min-h-16 w-full rounded border border-stone-200 px-2 py-1.5 text-xs outline-none focus:border-amber-500 focus:ring-2 focus:ring-amber-200/80"
              placeholder="Execution note"
            />
            <textarea
              value={evidence}
              onChange={(event) => setEvidence(event.target.value)}
              className="min-h-16 w-full rounded border border-stone-200 px-2 py-1.5 text-xs outline-none focus:border-amber-500 focus:ring-2 focus:ring-amber-200/80"
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
            {task.execution_note && (
              <p className="mt-1">{task.execution_note}</p>
            )}
            {task.evidence_note && <p className="mt-1">{task.evidence_note}</p>}
          </div>
        )}

        {error && <p className="text-xs text-rose-600">{error}</p>}
      </div>
    </div>
  );
}

function ApprovalTaskRow({
  task,
  onOpenCase,
  onRefresh,
  readOnly = false,
}: {
  task: PdEcrApprovalTask;
  onOpenCase: (caseId: string, target?: OpenTaskTarget) => Promise<void>;
  onRefresh: () => void;
  readOnly?: boolean;
}) {
  const [comment, setComment] = useState("");
  const [error, setError] = useState("");
  const [isOpening, setIsOpening] = useState(false);
  const approveMutation = useMutation({
    mutationFn: () => approvePdEcrCase(task.case_id),
    onSuccess: () => {
      onRefresh();
    },
  });
  const rejectMutation = useMutation({
    mutationFn: () => rejectPdEcrCase(task.case_id, comment || undefined),
    onSuccess: () => {
      onRefresh();
    },
  });

  const caseInfo = task.case;
  const isPending = task.status === "pending";
  const canOpenCase = canOpenTaskCase(task);

  const openTarget = async () => {
    if (!canOpenCase) {
      setError("该任务指向的后端案例不存在，无法打开变更包。");
      return;
    }
    setIsOpening(true);
    setError("");
    try {
      await onOpenCase(taskCaseId(task), task);
    } catch (err) {
      setError(errorMessage(err));
      setIsOpening(false);
    }
  };

  return (
    <div className="px-5 py-3">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0 flex-1">
          <p className="text-sm font-semibold text-stone-800">
            {caseInfo?.title || "PD-ECR Change Request"}
          </p>
          <div className="mt-1 flex flex-wrap gap-x-4 gap-y-1 text-xs text-stone-500">
            <span>Case: {caseInfo?.case_no || task.case_id.slice(0, 8)}</span>
            <span>Initiator: {caseInfo?.initiator || "—"}</span>
            <span>
              Approver: {task.approver_name || task.approver_email || "—"}
            </span>
            <span>
              Submitted:{" "}
              {task.created_at
                ? new Date(task.created_at).toLocaleDateString()
                : "—"}
            </span>
          </div>
          {!isPending && task.status === "approved" && (
            <span className="mt-1.5 inline-flex items-center rounded-full bg-emerald-100 px-2 py-0.5 text-[10px] font-semibold text-emerald-700 shadow-sm">
              Approved{" "}
              {task.approved_at
                ? new Date(task.approved_at).toLocaleString()
                : ""}
            </span>
          )}
          {!isPending && task.status === "rejected" && (
            <div className="mt-1.5">
              <span className="inline-flex items-center rounded-full bg-red-100 px-2 py-0.5 text-[10px] font-semibold text-red-700 shadow-sm">
                Rejected
              </span>
              {task.rejection_reason && (
                <p className="mt-1 text-xs text-red-600">
                  {task.rejection_reason}
                </p>
              )}
            </div>
          )}
        </div>
        <Button
          type="button"
          size="sm"
          variant="outline"
          className="h-8 shrink-0 bg-white hover:bg-amber-50 hover:border-amber-300"
          onClick={openTarget}
          disabled={isOpening || !canOpenCase}
        >
          <FileText className="size-4" />
          {openButtonLabel(task)}
        </Button>
        {isPending && readOnly && (
          <span className="shrink-0 rounded-md border border-amber-200 bg-amber-50 px-3 py-1.5 text-xs font-semibold text-amber-700">
            Waiting for leader
          </span>
        )}
        {isPending && !readOnly && (
          <div className="flex items-center gap-2 shrink-0">
            <textarea
              value={comment}
              onChange={(e) => setComment(e.target.value)}
              placeholder="Rejection reason (optional)..."
              className="h-8 w-40 rounded border border-stone-200 bg-white px-2 py-1 text-xs outline-none focus:border-amber-500 focus:ring-2 focus:ring-amber-200/80"
            />
            <Button
              size="sm"
              onClick={() => rejectMutation.mutate()}
              disabled={rejectMutation.isPending}
              className="h-8 bg-red-600 px-3 text-xs text-white hover:bg-red-700 transition-all active:scale-[0.98]"
            >
              Reject
            </Button>
            <Button
              size="sm"
              onClick={() => approveMutation.mutate()}
              disabled={approveMutation.isPending}
              className="h-8 bg-emerald-600 px-3 text-xs text-white hover:bg-emerald-700 transition-all active:scale-[0.98]"
            >
              Approve
            </Button>
          </div>
        )}
      </div>
      {error && <p className="mt-2 text-xs text-rose-600">{error}</p>}
    </div>
  );
}

function DepartmentTaskRow({
  task,
  onOpenCase,
}: {
  task: PdEcrDepartmentWorkflowTask;
  onOpenCase: (caseId: string, target?: OpenTaskTarget) => Promise<void>;
}) {
  const [error, setError] = useState("");
  const [isOpening, setIsOpening] = useState(false);
  const canOpenCase = canOpenTaskCase(task);

  const openTarget = async () => {
    if (!canOpenCase) {
      setError("该任务指向的后端案例不存在，无法打开变更包。");
      return;
    }
    setIsOpening(true);
    setError("");
    try {
      await onOpenCase(taskCaseId(task), task);
    } catch (err) {
      setError(errorMessage(err));
      setIsOpening(false);
    }
  };

  return (
    <div className="px-5 py-3">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <div className="flex flex-wrap items-center gap-2">
            <p className="text-sm font-medium text-stone-800">
              {taskCaseTitle(task)}
            </p>
            <span
              className={`rounded-full border px-2 py-0.5 text-[10px] font-semibold ${statusClass(task.status)}`}
            >
              {task.status}
            </span>
            {isTaskOverdue(task) && (
              <span className="rounded-full border border-rose-200 bg-rose-50 px-2 py-0.5 text-[10px] font-semibold text-rose-700">
                Overdue
              </span>
            )}
          </div>
          <div className="mt-1 flex flex-wrap gap-x-4 gap-y-1 text-xs text-stone-500">
            <span>Case: {taskCaseLabel(task)}</span>
            <span>Department: {task.department}</span>
            {task.action_required && (
              <span>Action: {task.action_required}</span>
            )}
            {task.due_date && <span>{workflowTaskDueLabel(task)}</span>}
          </div>
        </div>
        <Button
          type="button"
          size="sm"
          variant="outline"
          className="h-8 shrink-0 bg-white hover:bg-amber-50 hover:border-amber-300"
          onClick={openTarget}
          disabled={isOpening || !canOpenCase}
        >
          <FileText className="size-4" />
          {openButtonLabel(task)}
        </Button>
      </div>
      {error && <p className="mt-2 text-xs text-rose-600">{error}</p>}
    </div>
  );
}

function LeaderReviewRow({
  task,
  onOpenCase,
  onChanged,
}: {
  task: PdEcrLeaderReviewWorkflowTask;
  onOpenCase: (caseId: string, target?: OpenTaskTarget) => Promise<void>;
  onChanged: (message: string) => Promise<void>;
}) {
  const [comment, setComment] = useState(task.review_comment || "");
  const [signature, setSignature] = useState(
    task.signature_name || task.reviewer_name || "",
  );
  const [error, setError] = useState("");
  const [isSaving, setIsSaving] = useState(false);
  const caseLabel = taskCaseLabel(task);
  const canOpenCase = canOpenTaskCase(task);

  const openCase = async () => {
    if (!canOpenCase) {
      setError("该任务指向的后端案例不存在，无法打开变更包。");
      return;
    }
    setIsSaving(true);
    setError("");
    try {
      await onOpenCase(taskCaseId(task), task);
    } catch (err) {
      setError(errorMessage(err));
      setIsSaving(false);
    }
  };

  const review = async (decision: "approved" | "changes_requested") => {
    setIsSaving(true);
    setError("");
    try {
      await reviewPdEcrLeaderTask(task.id, {
        decision,
        review_comment: comment,
        signature_name: signature,
      });
      await onChanged(
        decision === "approved"
          ? "Leader review approved."
          : "Changes requested and sent back.",
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : "Review failed");
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <div className="grid gap-3 p-3 lg:grid-cols-[1fr_17rem] lg:items-start">
      <div className="min-w-0">
        <div className="flex flex-wrap items-center gap-2">
          <p className="text-sm font-semibold capitalize text-stone-800">
            {task.department}
          </p>
          <span
            className={`w-fit rounded-full border px-2 py-0.5 text-[10px] font-semibold shadow-sm ${statusClass(task.status)}`}
          >
            {task.status}
          </span>
        </div>
        <p className="mt-1 text-xs text-stone-500">
          {caseLabel} · {taskCaseTitle(task)} ·{" "}
          {task.reviewer_name || task.reviewer_email || "unassigned reviewer"}
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
          <p>
            Signed by {task.signature_name || task.reviewer_name || "leader"}
          </p>
          {task.reviewed_at && (
            <p className="mt-1">
              {new Date(task.reviewed_at).toLocaleString()}
            </p>
          )}
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
            {openButtonLabel(task)}
          </Button>
          <input
            value={signature}
            onChange={(event) => setSignature(event.target.value)}
            className="h-8 w-full rounded border border-stone-200 px-2 text-xs outline-none focus:border-amber-500 focus:ring-2 focus:ring-amber-200/80"
            placeholder="Signature name"
          />
          <textarea
            value={comment}
            onChange={(event) => setComment(event.target.value)}
            className="min-h-16 w-full rounded border border-stone-200 px-2 py-1.5 text-xs outline-none focus:border-amber-500 focus:ring-2 focus:ring-amber-200/80"
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
              className="bg-white hover:bg-amber-50 hover:border-amber-300"
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
  );
}
