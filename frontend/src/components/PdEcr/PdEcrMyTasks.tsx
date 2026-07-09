import { useMutation, useQuery } from "@tanstack/react-query";
import { useNavigate } from "@tanstack/react-router";
import { ClipboardCheck, FileText, UserCheck } from "lucide-react";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import useAuth from "@/hooks/useAuth";
import {
  approvePdEcrCase,
  completePdEcrExecutionTask,
  confirmPdEcrDepartmentTask,
  confirmPdEcrExecutionAssignment,
  getPdEcrCase,
  listMyPdEcrWorkflowTasks,
  rejectPdEcrCase,
  requestPdEcrDepartmentChanges,
  reviewPdEcrLeaderTask,
  type PdEcrApprovalTask,
  type PdEcrCurrentUser,
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

type WorkbenchLane = "submitted" | "inbox" | "overdue" | "closed";

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
      return "border-blue-200 bg-blue-50 text-blue-700";
    default:
      return "border-slate-200 bg-slate-50 text-slate-600";
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

function taskMatchesLane(task: WorkflowTask, lane: WorkbenchLane) {
  if (lane === "overdue") return isTaskOverdue(task);
  if (lane === "closed") return isClosedTask(task);
  // "inbox" (待我处理) — every open action assigned to me, including leader review.
  return !isClosedTask(task) || isReturnedTask(task);
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

function roleLabel(user?: PdEcrCurrentUser | null) {
  if (user?.is_superuser || user?.pd_ecr_role === "pd_ecr_manager") {
    return "Manager overview";
  }
  if (user?.pd_ecr_role === "department_leader") {
    return "Leader workspace";
  }
  if (user?.pd_ecr_role === "department_member") {
    return "Engineer workspace";
  }
  return "Personal workspace";
}

function actorLabel(user?: PdEcrCurrentUser | null) {
  return user?.display_name || user?.full_name || user?.email || "Current user";
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

function CaseSummaryStrip({ task }: { task: WorkflowTask }) {
  const caseInfo = task.case;
  const details = [
    caseInfo?.dc_no ? `DC ${caseInfo.dc_no}` : "",
    caseInfo?.mcr_no ? `MCR ${caseInfo.mcr_no}` : "",
    caseInfo?.customer_project || "",
    caseInfo?.product_no ? `Product ${caseInfo.product_no}` : "",
    caseInfo?.part_no ? `Part ${caseInfo.part_no}` : "",
    caseInfo?.change_type || "",
  ].filter(Boolean);

  return (
    <div className="mt-2 rounded-md border border-slate-200 bg-slate-50 px-3 py-2">
      <p className="truncate text-xs font-semibold text-slate-800">
        {taskCaseLabel(task)} · {taskCaseTitle(task)}
      </p>
      {details.length ? (
        <p className="mt-1 line-clamp-2 text-[11px] leading-4 text-slate-500">
          {details.join(" · ")}
        </p>
      ) : (
        <p className="mt-1 text-[11px] text-slate-500">
          Open the change package to review the complete PD-ECR context.
        </p>
      )}
    </div>
  );
}

export function PdEcrMyTasks() {
  const navigate = useNavigate();
  const { user } = useAuth();
  const currentUser = user as PdEcrCurrentUser | null | undefined;
  const [message, setMessage] = useState("");
  const [workbenchLane, setWorkbenchLane] = useState<WorkbenchLane>("inbox");
  const taskFilter: TaskFilter =
    workbenchLane === "overdue"
      ? "overdue"
      : workbenchLane === "closed"
        ? "all"
        : "all";
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
  const openCount =
    openExecutionCount +
    openLeaderReviewCount +
    departmentTasks.length +
    pendingApprovalCount;
  const closedCount = allTasks.filter(isClosedTask).length;
  const visibleApprovalTasks = approvalTasks.filter((task) =>
    taskMatchesLane(task, workbenchLane) && taskMatchesFilter(task, taskFilter),
  );
  const visibleSubmittedApprovalTasks = submittedApprovalTasks.filter((task) => {
    if (workbenchLane === "submitted") return true;
    if (workbenchLane === "overdue") return isTaskOverdue(task);
    if (workbenchLane === "closed") return isClosedTask(task);
    return false;
  });
  const visibleDepartmentTasks = departmentTasks.filter((task) =>
    taskMatchesLane(task, workbenchLane) && taskMatchesFilter(task, taskFilter),
  );
  const visibleExecutionTasks = executionTasks.filter((task) =>
    taskMatchesLane(task, workbenchLane) && taskMatchesFilter(task, taskFilter),
  );
  const visibleLeaderTasks = leaderTasks.filter((task) =>
    taskMatchesLane(task, workbenchLane) && taskMatchesFilter(task, taskFilter),
  );
  const visibleTaskCount =
    visibleApprovalTasks.length +
    visibleSubmittedApprovalTasks.length +
    visibleDepartmentTasks.length +
    visibleExecutionTasks.length +
    visibleLeaderTasks.length;
  const workbenchLaneOptions: Array<{
    value: WorkbenchLane;
    label: string;
    helper: string;
    count: number;
  }> = [
    {
      value: "submitted",
      label: "我发起的",
      helper: "我创建/负责、等待他人处理的变更",
      count: submittedApprovalCount,
    },
    {
      value: "inbox",
      label: "待我处理",
      helper: "分派给我、待我操作的任务(含领导审批)",
      count: openCount,
    },
    {
      value: "overdue",
      label: "超期",
      helper: "已过期、待我处理的任务",
      count: overdueCount,
    },
    {
      value: "closed",
      label: "已完成",
      helper: "我可见的已办结任务",
      count: closedCount,
    },
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
              {roleLabel(currentUser)}
            </p>
            <h1 className="mt-1 text-2xl font-semibold tracking-tight text-slate-900">
              PD-ECR Workbench
            </h1>
            <p className="mt-1 text-sm text-slate-500">
              {actorLabel(currentUser)} · {openCount} open workflow items
              {currentUser?.department ? ` · ${currentUser.department}` : ""}
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

      <div className="mb-4 grid grid-cols-2 gap-3 lg:grid-cols-4">
        <MetricCard label="我发起的" value={submittedApprovalCount} />
        <MetricCard label="待我处理" value={openCount} tone="accent" />
        <MetricCard label="超期" value={overdueCount} tone="accent" />
        <MetricCard label="已完成" value={closedCount} />
      </div>

      <div className="enterprise-panel grid gap-2 p-3 md:grid-cols-2 xl:grid-cols-4">
        {workbenchLaneOptions.map((option) => (
          <button
            key={option.value}
            type="button"
            onClick={() => setWorkbenchLane(option.value)}
            className={
              workbenchLane === option.value
                ? "rounded-md border border-blue-300 bg-blue-50 px-3 py-2 text-left shadow-sm"
                : "rounded-md border border-slate-200 bg-white px-3 py-2 text-left hover:bg-slate-50"
            }
          >
            <span
              className={
                workbenchLane === option.value
                  ? "block text-xs font-semibold text-blue-700"
                  : "block text-xs font-semibold text-slate-700"
              }
            >
              {option.label} · {option.count}
            </span>
            <span className="mt-0.5 block text-[11px] leading-4 text-slate-500">
              {option.helper}
            </span>
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
              onChanged={refreshAfterAction}
            />
          ))}
          </div>
        </section>
      )}

      {visibleExecutionTasks.length > 0 && (
        <section className="enterprise-panel mb-4 overflow-hidden">
          <div className="flex items-center gap-2 border-b border-slate-200 bg-slate-50/70 px-5 py-3">
            <ClipboardCheck className="size-4 text-blue-700" />
            <h2 className="text-sm font-semibold text-slate-900">
              Execution Tasks / 工程师执行
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
          </div>
        </section>
      )}

      {visibleLeaderTasks.length > 0 && (
        <section className="enterprise-panel mb-4 overflow-hidden">
          <div className="flex items-center gap-2 border-b border-slate-200 bg-slate-50/70 px-5 py-3">
            <UserCheck className="size-4 text-blue-700" />
            <h2 className="text-sm font-semibold text-slate-900">
              Leader Reviews / 领导签核
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
          </div>
        </section>
      )}

      {!visibleTaskCount && (
        <div className="enterprise-panel p-8 text-center">
          <p className="text-sm font-semibold text-slate-800">
            No tasks in this workbench lane.
          </p>
          <p className="mt-1 text-sm text-slate-500">
            Choose another lane above or refresh after workflow assignments are
            created.
          </p>
        </div>
      )}
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
    <div className="grid gap-4 px-5 py-4 transition-colors hover:bg-slate-50/60 lg:grid-cols-[minmax(0,1fr)_18rem] lg:items-start">
      <div className="min-w-0">
        <div className="flex flex-wrap items-center gap-2">
          <p className="text-sm font-semibold text-slate-900">
            {task.description}
          </p>
          <span
            className={`w-fit rounded-full border px-2 py-0.5 text-[10px] font-semibold shadow-sm ${statusClass(task.status)}`}
          >
            {task.status}
          </span>
        </div>
        <p className="mt-1 text-xs text-slate-500">
          {caseLabel} · {taskCaseTitle(task)} · {task.department} ·{" "}
          {task.assignee_name || task.assignee_email || "unassigned"}
        </p>
        <CaseSummaryStrip task={task} />
        {!canOpenCase ? (
          <p className="mt-2 rounded bg-rose-50 p-2 text-xs text-rose-700">
            该任务仍在列表中，但它关联的后端案例已经不存在或不可访问，因此不能打开变更包。
          </p>
        ) : null}
        {task.due_date && (
          <p
            className={`mt-1 text-xs ${isTaskOverdue(task) ? "font-semibold text-rose-600" : "text-slate-500"}`}
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
          <p className="mt-2 rounded-md border border-blue-100 bg-blue-50 p-2 text-xs text-blue-800">
            Step 1: review the package, then confirm assignment to start
            execution.
          </p>
        ) : null}
        {task.status === "in_progress" ? (
          <p className="mt-2 rounded bg-blue-50 p-2 text-xs text-blue-800">
            Step 2: submit execution result and evidence for downstream review.
          </p>
        ) : null}
      </div>

      <div className="space-y-2 rounded-lg border border-slate-200 bg-white p-3 shadow-sm">
        <Button
          type="button"
          size="sm"
          variant="outline"
          className="w-full bg-white hover:border-blue-300 hover:bg-blue-50"
          onClick={openCase}
          disabled={isSaving || !canOpenCase}
        >
          <FileText className="size-4" />
          Review assignment
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
              className="enterprise-input h-8 text-xs"
              placeholder="Execution result"
            />
            <textarea
              value={note}
              onChange={(event) => setNote(event.target.value)}
              className="enterprise-textarea min-h-16 text-xs"
              placeholder="Execution note"
            />
            <textarea
              value={evidence}
              onChange={(event) => setEvidence(event.target.value)}
              className="enterprise-textarea min-h-16 text-xs"
              placeholder="Evidence note / file reference / test record"
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
    <div className="px-5 py-4 transition-colors hover:bg-slate-50/60">
      <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_auto] lg:items-start">
        <div className="min-w-0 flex-1">
          <p className="text-sm font-semibold text-slate-900">
            {caseInfo?.title || "PD-ECR Change Request"}
          </p>
          <div className="mt-1 flex flex-wrap gap-x-4 gap-y-1 text-xs text-slate-500">
            <span>Case: {caseInfo?.case_no || task.case_id.slice(0, 8)}</span>
            <span>Initiator: {caseInfo?.initiator || "—"}</span>
            <span>Project: {caseInfo?.customer_project || "—"}</span>
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
          <CaseSummaryStrip task={task} />
          {isPending && !readOnly ? (
            <p className="mt-2 rounded bg-blue-50 p-2 text-xs text-blue-800">
              Initial leader confirm: review business necessity, affected scope,
              target close date, then approve or return for supplement.
            </p>
          ) : null}
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
              <span className="inline-flex items-center rounded-full bg-rose-100 px-2 py-0.5 text-[10px] font-semibold text-rose-700 shadow-sm">
                Rejected
              </span>
              {task.rejection_reason && (
                <p className="mt-1 text-xs text-rose-600">
                  {task.rejection_reason}
                </p>
              )}
            </div>
          )}
        </div>
        <div className="w-full space-y-2 rounded-lg border border-slate-200 bg-white p-3 shadow-sm lg:w-72">
          <Button
            type="button"
            size="sm"
            variant="outline"
            className="h-8 w-full bg-white hover:border-blue-300 hover:bg-blue-50"
            onClick={openTarget}
            disabled={isOpening || !canOpenCase}
          >
            <FileText className="size-4" />
            {openButtonLabel(task)}
          </Button>
          {isPending && readOnly && (
            <span className="flex h-8 items-center justify-center rounded-md border border-blue-200 bg-blue-50 px-3 text-xs font-semibold text-blue-700">
              Waiting for leader
            </span>
          )}
          {isPending && !readOnly && (
            <>
              <textarea
                value={comment}
                onChange={(e) => setComment(e.target.value)}
                placeholder="Return reason..."
                className="enterprise-textarea min-h-16 text-xs"
              />
              <div className="grid grid-cols-2 gap-2">
                <Button
                  size="sm"
                  onClick={() => rejectMutation.mutate()}
                  disabled={rejectMutation.isPending}
                  className="h-8 bg-rose-600 px-3 text-xs text-white transition-all hover:bg-rose-700 active:scale-[0.98]"
                >
                  Return
                </Button>
                <Button
                  size="sm"
                  onClick={() => approveMutation.mutate()}
                  disabled={approveMutation.isPending}
                  className="h-8 bg-emerald-600 px-3 text-xs text-white transition-all hover:bg-emerald-700 active:scale-[0.98]"
                >
                  Confirm
                </Button>
              </div>
            </>
          )}
        </div>
      </div>
      {error && <p className="mt-2 text-xs text-rose-600">{error}</p>}
    </div>
  );
}

function DepartmentTaskRow({
  task,
  onOpenCase,
  onChanged,
}: {
  task: PdEcrDepartmentWorkflowTask;
  onOpenCase: (caseId: string, target?: OpenTaskTarget) => Promise<void>;
  onChanged: (message: string) => Promise<void>;
}) {
  const [impactResult, setImpactResult] = useState(
    task.impact_result || "No impact",
  );
  const [impactRemark, setImpactRemark] = useState(task.impact_remark || "");
  const [actionRequired, setActionRequired] = useState(
    task.action_required || "",
  );
  const [changeComment, setChangeComment] = useState("");
  const [error, setError] = useState("");
  const [isSaving, setIsSaving] = useState(false);
  const canOpenCase = canOpenTaskCase(task);
  const isEditable = !["confirmed"].includes(task.status);

  const openTarget = async () => {
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

  const confirmImpact = async () => {
    setIsSaving(true);
    setError("");
    try {
      await confirmPdEcrDepartmentTask(task.id, {
        impact_result: impactResult,
        impact_remark: impactRemark || null,
        action_required: actionRequired || null,
      });
      await onChanged("Department impact confirmed.");
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setIsSaving(false);
    }
  };

  const requestChanges = async () => {
    setIsSaving(true);
    setError("");
    try {
      await requestPdEcrDepartmentChanges(
        task.id,
        changeComment || impactRemark || "Need more information.",
      );
      await onChanged("Department requested supplement.");
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <div className="grid gap-4 px-5 py-4 transition-colors hover:bg-slate-50/60 lg:grid-cols-[minmax(0,1fr)_20rem] lg:items-start">
      <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <p className="text-sm font-semibold text-slate-900">
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
          <CaseSummaryStrip task={task} />
          <div className="mt-1 flex flex-wrap gap-x-4 gap-y-1 text-xs text-slate-500">
            <span>Case: {taskCaseLabel(task)}</span>
            <span>Department: {task.department}</span>
            {task.impact_result && <span>Impact: {task.impact_result}</span>}
            {task.action_required && (
              <span>Action: {task.action_required}</span>
            )}
            {task.due_date && <span>{workflowTaskDueLabel(task)}</span>}
          </div>
          {task.impact_remark && (
            <p className="mt-2 rounded bg-slate-50 p-2 text-xs text-slate-600">
              {task.impact_remark}
            </p>
          )}
      </div>

      <div className="space-y-2 rounded-lg border border-slate-200 bg-white p-3 shadow-sm">
        <Button
          type="button"
          size="sm"
          variant="outline"
          className="w-full bg-white hover:border-blue-300 hover:bg-blue-50"
          onClick={openTarget}
          disabled={isSaving || !canOpenCase}
        >
          <FileText className="size-4" />
          Review impact field
        </Button>
        {isEditable ? (
          <>
            <select
              value={impactResult}
              onChange={(event) => setImpactResult(event.target.value)}
              className="enterprise-input h-8 text-xs"
            >
              <option value="No impact">No impact</option>
              <option value="Impacted - action required">
                Impacted - action required
              </option>
              <option value="Impacted - monitor only">
                Impacted - monitor only
              </option>
              <option value="Need more information">
                Need more information
              </option>
            </select>
            <textarea
              value={actionRequired}
              onChange={(event) => setActionRequired(event.target.value)}
              className="enterprise-textarea min-h-14 text-xs"
              placeholder="Action required / owner / timing"
            />
            <textarea
              value={impactRemark}
              onChange={(event) => setImpactRemark(event.target.value)}
              className="enterprise-textarea min-h-14 text-xs"
              placeholder="Impact remark"
            />
            <div className="grid grid-cols-2 gap-2">
              <Button
                type="button"
                size="sm"
                className="bg-emerald-600 hover:bg-emerald-700"
                onClick={confirmImpact}
                disabled={isSaving || !canOpenCase || !impactResult.trim()}
              >
                Confirm impact
              </Button>
              <Button
                type="button"
                size="sm"
                variant="outline"
                className="bg-white hover:border-blue-300 hover:bg-blue-50"
                onClick={requestChanges}
                disabled={isSaving || !canOpenCase}
              >
                Request info
              </Button>
            </div>
            <input
              value={changeComment}
              onChange={(event) => setChangeComment(event.target.value)}
              className="enterprise-input h-8 text-xs"
              placeholder="Request-info comment, optional"
            />
          </>
        ) : (
          <div className="rounded bg-emerald-50 p-2 text-xs text-emerald-800">
            <p>{task.impact_result || "confirmed"}</p>
            {task.action_required && (
              <p className="mt-1">Action: {task.action_required}</p>
            )}
          </div>
        )}
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
    <div className="grid gap-4 px-5 py-4 transition-colors hover:bg-slate-50/60 lg:grid-cols-[minmax(0,1fr)_18rem] lg:items-start">
      <div className="min-w-0">
        <div className="flex flex-wrap items-center gap-2">
          <p className="text-sm font-semibold capitalize text-slate-900">
            {task.department}
          </p>
          <span
            className={`w-fit rounded-full border px-2 py-0.5 text-[10px] font-semibold shadow-sm ${statusClass(task.status)}`}
          >
            {task.status}
          </span>
        </div>
        <p className="mt-1 text-xs text-slate-500">
          {caseLabel} · {taskCaseTitle(task)} ·{" "}
          {task.reviewer_name || task.reviewer_email || "unassigned reviewer"}
        </p>
        <CaseSummaryStrip task={task} />
        {task.status !== "approved" ? (
          <p className="mt-2 rounded bg-blue-50 p-2 text-xs text-blue-800">
            Review department closure, execution evidence, open risks, then sign
            off or request changes.
          </p>
        ) : null}
        {!canOpenCase ? (
          <p className="mt-2 rounded bg-rose-50 p-2 text-xs text-rose-700">
            该签核任务关联的后端案例已经不存在或不可访问，因此不能打开变更包。
          </p>
        ) : null}
        {task.review_comment && (
          <p className="mt-2 rounded-md border border-slate-200 bg-slate-50 p-2 text-xs text-slate-600">
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
        <div className="space-y-2 rounded-lg border border-slate-200 bg-white p-3 shadow-sm">
          <Button
            type="button"
            size="sm"
            variant="outline"
            className="w-full bg-white hover:border-blue-300 hover:bg-blue-50"
            onClick={openCase}
            disabled={isSaving || !canOpenCase}
          >
            <FileText className="size-4" />
            Review package summary
          </Button>
          <input
            value={signature}
            onChange={(event) => setSignature(event.target.value)}
            className="enterprise-input h-8 text-xs"
            placeholder="Signature name"
          />
          <textarea
            value={comment}
            onChange={(event) => setComment(event.target.value)}
            className="enterprise-textarea min-h-16 text-xs"
            placeholder="Review comment / open risk / return reason"
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
              className="bg-white hover:border-blue-300 hover:bg-blue-50"
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
