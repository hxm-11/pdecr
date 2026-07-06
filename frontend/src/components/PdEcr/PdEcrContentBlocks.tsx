import { useNavigate } from "@tanstack/react-router";
import {
  ArrowLeft,
  CheckCircle2,
  ClipboardList,
  Download,
  Home,
  LockKeyhole,
  PlayCircle,
  Sparkles,
} from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import { Button } from "@/components/ui/button";
import useAuth from "@/hooks/useAuth";
import {
  exportPdEcrCase,
  exportPdEcrDraft,
  resolvePdEcrAssetUrl,
  transitionPdEcrCase,
} from "@/lib/pdEcrApi";
import {
  getModuleCompletionState,
  PdEcrModuleAccordion,
} from "./PdEcrModuleAccordion";
import { PdEcrProcessFlowButton } from "./PdEcrProcessFlow";
import { buildPdEcrOnePageHtml, downloadText } from "./pdEcrExport";
import { loadActiveResult, type PdEcrStoredResult } from "./pdEcrState";

function compactValue(...values: unknown[]) {
  for (const value of values) {
    const text = String(value ?? "").trim();
    if (text) return text;
  }
  return "-";
}

function StatusPill({
  children,
  tone = "blue",
}: {
  children: React.ReactNode;
  tone?: "blue" | "green" | "amber" | "slate" | "sky";
}) {
  const className =
    tone === "green"
      ? "border-emerald-200 bg-emerald-50 text-emerald-700"
      : tone === "amber"
        ? "border-amber-200 bg-amber-50 text-amber-700"
        : tone === "slate"
          ? "border-slate-200 bg-slate-50 text-slate-600"
          : tone === "sky"
            ? "border-sky-200 bg-sky-50 text-sky-700"
            : "border-blue-200 bg-blue-50 text-blue-700";

  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full border px-3 py-1 text-xs font-semibold ${className}`}
    >
      {children}
    </span>
  );
}

const LEADER_SIGNOFF_ROLES = [
  {
    key: "leader of initiator",
    label: "发起人直属领导",
    hint: "由发起人所在部门负责人确认",
  },
  {
    key: "Section manager of function",
    label: "职能部门经理",
    hint: "由相关职能部门经理确认",
  },
  {
    key: "HOD/TCR",
    label: "HOD / TCR",
    hint: "最终准入确认",
  },
] as const;

type LeaderSignoffState = Record<string, string>;

function leaderSignoffStorageKey(recordId: string) {
  return `pd-ecr-leader-signoff-buttons:${recordId}`;
}

function leaderExecutionStorageKey(recordId: string) {
  return `pd-ecr-leader-execution-start:${recordId}`;
}

function loadLeaderSignoffs(recordId: string): LeaderSignoffState {
  const raw = localStorage.getItem(leaderSignoffStorageKey(recordId));
  if (!raw) return {};
  try {
    return JSON.parse(raw) as LeaderSignoffState;
  } catch {
    return {};
  }
}

function getContentProgress(result: PdEcrStoredResult) {
  const total = result.modules.length || 4;
  const completed = result.modules.filter((module) => {
    const hasData = Object.keys(module.data || {}).length > 0;
    return hasData || Boolean(module.summary?.trim());
  }).length;

  return { completed, total };
}

const AI_REVIEW_MODULE_IDS = [
  "impact-analysis",
  "validation-plan",
  "implementation-plan",
] as const;

function asRecord(value: unknown): Record<string, unknown> {
  return value && typeof value === "object"
    ? (value as Record<string, unknown>)
    : {};
}

function booleanValue(value: unknown) {
  if (typeof value === "boolean") return value;
  if (typeof value === "string" && value.trim()) {
    const normalized = value.trim().toLowerCase();
    if (["true", "yes", "1", "confirmed", "approved"].includes(normalized)) {
      return true;
    }
    if (["false", "no", "0", "pending"].includes(normalized)) return false;
  }
  return undefined;
}

function firstBoolean(records: Record<string, unknown>[], keys: string[]) {
  for (const record of records) {
    for (const key of keys) {
      const value = booleanValue(record[key]);
      if (value !== undefined) return value;
    }
  }
  return undefined;
}

function getPreGenerationGate(result: PdEcrStoredResult) {
  const moduleRecords = result.modules.map((module) => asRecord(module.data));
  const records = [asRecord(result.inputSnapshot), ...moduleRecords];
  const aiModules = getAiGenerationProgress(result);
  const implicitConfirmed = result.source === "generated" && aiModules.completed > 0;

  return {
    initiatorConfirmed:
      firstBoolean(records, ["initiatorConfirmed", "initiator_confirmed"]) ??
      implicitConfirmed,
    leaderConfirmed:
      firstBoolean(records, ["leaderConfirmed", "leader_confirmed"]) ??
      implicitConfirmed,
  };
}

function hasMeaningfulGeneratedContent(module?: PdEcrStoredResult["modules"][number]) {
  if (!module) return false;
  const text = [
    module.summary,
    module.description,
    ...Object.entries(module.data || {})
      .filter(([key]) => !["v01_module", "module"].includes(key))
      .map(([, value]) => String(value ?? "")),
  ]
    .join(" ")
    .trim();

  if (!text) return false;
  return !/(尚未生成|暂无内容|等待生成|no content yet)/i.test(text);
}

function getAiGenerationProgress(result: PdEcrStoredResult) {
  const modules = AI_REVIEW_MODULE_IDS.map((id) =>
    result.modules.find((module) => module.id === id),
  );
  const completed = modules.filter(hasMeaningfulGeneratedContent).length;
  return { completed, total: modules.length };
}

function getEngineerConfirmationProgress(result: PdEcrStoredResult) {
  const modules = AI_REVIEW_MODULE_IDS.map((id) =>
    result.modules.find((module) => module.id === id),
  ).filter(Boolean) as PdEcrStoredResult["modules"];
  const completed = modules.filter(
    (module) => getModuleCompletionState(module).label === "Complete",
  ).length;

  return { completed, total: modules.length || AI_REVIEW_MODULE_IDS.length };
}

function getSignoffProgress(recordId: string) {
  const signed = loadLeaderSignoffs(recordId);
  const signedCount = LEADER_SIGNOFF_ROLES.filter((role) => signed[role.key])
    .length;

  return {
    signed,
    signedCount,
    total: LEADER_SIGNOFF_ROLES.length,
    allSigned: signedCount === LEADER_SIGNOFF_ROLES.length,
  };
}

function getWorkflowStage(result: PdEcrStoredResult, recordId: string) {
  if (result.source === "history") return "readonly";

  const executionStarted =
    localStorage.getItem(leaderExecutionStorageKey(recordId)) !== null;
  const { signedCount, allSigned } = getSignoffProgress(recordId);
  const gate = getPreGenerationGate(result);
  const aiModules = getAiGenerationProgress(result);
  const engineerModules = getEngineerConfirmationProgress(result);

  if (!gate.initiatorConfirmed) return "initiator";
  if (!gate.leaderConfirmed) return "leader";
  if (aiModules.completed < aiModules.total) return "ai-generation";
  if (engineerModules.completed < engineerModules.total) {
    return "engineer-confirmation";
  }
  if (!signedCount) return "notification";
  if (!allSigned) return "final-signoff";
  if (executionStarted) return "closed";

  return "closed";
}

function WorkflowOverview({
  result,
  recordId,
}: {
  result: PdEcrStoredResult;
  recordId: string;
}) {
  const stage = getWorkflowStage(result, recordId);
  const { completed, total } = getContentProgress(result);
  const gate = getPreGenerationGate(result);
  const aiModules = getAiGenerationProgress(result);
  const engineerModules = getEngineerConfirmationProgress(result);
  const { signedCount, total: signTotal } = getSignoffProgress(recordId);

  const steps = [
    {
      key: "initiator",
      label: "发起人确认",
      desc: gate.initiatorConfirmed ? "已确认第一页信息" : "等待发起人确认",
    },
    {
      key: "leader",
      label: "Leader 确认",
      desc: gate.leaderConfirmed ? "已准入 AI 生成" : "等待直属领导确认",
    },
    {
      key: "ai-generation",
      label: "AI 生成 1.2/1.3/1.4",
      desc: `${aiModules.completed}/${aiModules.total} 模块已生成`,
    },
    {
      key: "engineer-confirmation",
      label: "工程师确认",
      desc: `${engineerModules.completed}/${engineerModules.total} 模块已确认`,
    },
    {
      key: "notification",
      label: "邮件通知",
      desc: "通知 leader 和相关签字人",
    },
    {
      key: "final-signoff",
      label: "最终签字",
      desc: `${signedCount}/${signTotal} 已签字`,
    },
    {
      key: "closed",
      label: "关闭归档",
      desc: "签字完成后归档追溯",
    },
  ];

  const activeIndex =
    stage === "readonly"
      ? 0
      : Math.max(
          0,
          steps.findIndex((step) => step.key === stage),
        );

  return (
    <section className="enterprise-panel px-5 py-4">
      <div className="flex flex-col justify-between gap-3 lg:flex-row lg:items-center">
        <div>
          <p className="enterprise-section-title text-blue-700">
            PDECR 流程状态
          </p>
          <h2 className="mt-1 text-lg font-semibold tracking-tight text-slate-900">
            {stage === "readonly"
              ? "当前为历史案例，只读查看"
              : `当前阶段：${steps[activeIndex]?.label || "内容准备"}`}
          </h2>
        </div>

        <div className="flex flex-wrap gap-2">
          <StatusPill tone="blue">内容 {completed}/{total}</StatusPill>
          <StatusPill tone={signedCount === signTotal ? "green" : "slate"}>
            签字 {signedCount}/{signTotal}
          </StatusPill>
        </div>
      </div>

      <div className="mt-5 grid gap-3 md:grid-cols-2 xl:grid-cols-7">
        {steps.map((step, index) => {
          const current = stage !== "readonly" && index === activeIndex;
          const done = stage !== "readonly" && index < activeIndex;

          return (
            <div
              key={step.key}
              className={`rounded-xl border px-3 py-3 ${
                current
                  ? "border-blue-300 bg-blue-50"
                  : done
                    ? "border-emerald-200 bg-emerald-50"
                    : "border-slate-200 bg-slate-50"
              }`}
            >
              <div className="flex items-center gap-2">
                <span
                  className={`flex size-6 items-center justify-center rounded-full text-xs font-bold ${
                    current
                      ? "bg-blue-600 text-white"
                      : done
                        ? "bg-emerald-600 text-white"
                        : "bg-slate-200 text-slate-500"
                  }`}
                >
                  {done ? <CheckCircle2 className="size-4" /> : index + 1}
                </span>
                <p
                  className={`text-sm font-semibold ${
                    current
                      ? "text-blue-800"
                      : done
                        ? "text-emerald-800"
                        : "text-slate-600"
                  }`}
                >
                  {step.label}
                </p>
              </div>
              <p className="mt-2 text-xs leading-5 text-slate-500">
                {step.desc}
              </p>
            </div>
          );
        })}
      </div>
    </section>
  );
}

// function CaseSummaryBar({ result }: { result: PdEcrStoredResult }) {
//   const row = result.currentCase;
//   const snapshot = result.inputSnapshot || {};
//   const { completed, total } = getContentProgress(result);

//   const sourceCount = new Set(
//     result.modules.flatMap((module) => [
//       ...(module.sourceCases || []),
//       ...(module.sourceFiles || []),
//     ]),
//   ).size;

//   const items = [
//     // ["Case No.", compactValue(row?.dcNo, row?.mcrNo, row?.id, result.draftId)],
//     // [
//     //   "Part No.",
//     //   compactValue(
//     //     row?.partNumber,
//     //     row?.productNo,
//     //     snapshot.part_number,
//     //     snapshot.product_no,
//     //   ),
//     // ],
//     // [
//     //   "Project",
//     //   compactValue(
//     //     row?.project,
//     //     row?.customer,
//     //     snapshot.project,
//     //     snapshot.customer_project,
//     //   ),
//     // ],
//     // ["Change Type", compactValue(row?.changeType, snapshot.change_type)],
//     // ["Owner", compactValue(row?.initiator, snapshot.initiator)],
//     // ["Modules", `${completed}/${total}`],
//   ];

//   return (
//     <section className="enterprise-panel px-4 py-3">
//       <div className="flex flex-col gap-3 xl:flex-row xl:items-center xl:justify-between">
//         <div className="flex min-w-0 flex-wrap items-center gap-2">
//           {sourceCount > 0 && (
//             <StatusPill tone="green">
//               <CheckCircle2 className="size-3.5" />
//               {sourceCount} 个来源引用
//             </StatusPill>
//           )}
//         </div>

//         <dl className="grid min-w-0 flex-1 grid-cols-2 gap-2 sm:grid-cols-3 xl:max-w-5xl xl:grid-cols-6">
//           {items.map(([label, value]) => (
//             <div
//               key={label}
//               className="min-w-0 rounded-lg border border-slate-200 bg-slate-50 px-3 py-2"
//             >
//               <dt className="text-xs font-semibold uppercase tracking-wide text-slate-500">
//                 {label}
//               </dt>
//               <dd
//                 className="mt-0.5 truncate text-sm font-semibold text-slate-900"
//                 title={value}
//               >
//                 {value}
//               </dd>
//             </div>
//           ))}
//         </dl>
//       </div>
//     </section>
//   );
// }

type PdEcrActor = {
  email?: string | null;
  full_name?: string | null;
  display_name?: string | null;
  department?: string | null;
  pd_ecr_role?: string | null;
};

function normalizeActorText(value?: string | null) {
  return String(value || "")
    .trim()
    .toLowerCase()
    .replace(/\s+/g, " ");
}

function currentUserMatchesInitiator(
  user: PdEcrActor | null | undefined,
  initiator: string,
) {
  const target = normalizeActorText(initiator);
  if (!target) return false;

  return [user?.email, user?.display_name, user?.full_name].some(
    (candidate) => normalizeActorText(candidate) === target,
  );
}

function inferDepartmentFromInitiator(initiator: string) {
  const text = normalizeActorText(initiator);
  const emailDepartment = text.match(/^([a-z]+)[._-]/)?.[1];

  if (emailDepartment) return emailDepartment;

  for (const department of [
    "design",
    "system",
    "purchasing",
    "manufacturing",
    "quality",
    "pm",
    "catalyst",
  ]) {
    if (text.includes(department)) return department;
  }

  return "";
}

function canConfirmInitiatorLeader(
  user: PdEcrActor | null | undefined,
  initiator: string,
) {
  if (user?.pd_ecr_role !== "department_leader") return false;
  if (currentUserMatchesInitiator(user, initiator)) return false;

  const initiatorDepartment = inferDepartmentFromInitiator(initiator);
  if (!initiatorDepartment) return true;

  return normalizeActorText(user.department) === initiatorDepartment;
}

function LeaderSignOffButtons({
  recordId,
  caseId,
  initiator,
}: {
  recordId: string;
  caseId?: string;
  initiator: string;
}) {
  const { user } = useAuth();
  const currentUser = user as PdEcrActor | null | undefined;

  const [signed, setSigned] = useState<LeaderSignoffState>(() =>
    loadLeaderSignoffs(recordId),
  );
  const [isStartingExecution, setIsStartingExecution] = useState(false);
  const [executionStarted, setExecutionStarted] = useState(
    () => localStorage.getItem(leaderExecutionStorageKey(recordId)) !== null,
  );
  const [executionMessage, setExecutionMessage] = useState(() =>
    localStorage.getItem(leaderExecutionStorageKey(recordId))
      ? "已进入执行分配阶段。"
      : "",
  );

  const signedCount = LEADER_SIGNOFF_ROLES.filter(
    (role) => signed[role.key],
  ).length;
  const allSigned = signedCount === LEADER_SIGNOFF_ROLES.length;
  const nextUnsignedIndex = LEADER_SIGNOFF_ROLES.findIndex(
    (role) => !signed[role.key],
  );

  const canCurrentUserSignRole = (roleKey: string) => {
    if (roleKey === "leader of initiator") {
      return canConfirmInitiatorLeader(currentUser, initiator);
    }

    return ["department_leader", "pd_ecr_manager"].includes(
      currentUser?.pd_ecr_role || "",
    );
  };

  const toggleSigned = (roleKey: string) => {
    if (!canCurrentUserSignRole(roleKey)) return;

    setSigned((current) => {
      const next = { ...current };

      if (next[roleKey]) {
        delete next[roleKey];
      } else {
        next[roleKey] = new Date().toLocaleString();
      }

      localStorage.setItem(
        leaderSignoffStorageKey(recordId),
        JSON.stringify(next),
      );

      window.dispatchEvent(new Event("pd-ecr-leader-signoff-updated"));

      return next;
    });
  };

  const startExecutionAssignment = async () => {
    if (!allSigned || isStartingExecution || executionStarted) return;

    setIsStartingExecution(true);
    setExecutionMessage("");

    try {
      if (caseId) {
        await transitionPdEcrCase(caseId, "approved");
      }

      localStorage.setItem(
        leaderExecutionStorageKey(recordId),
        JSON.stringify({
          status: "final_signoff_complete",
          startedAt: new Date().toISOString(),
        }),
      );

      setExecutionStarted(true);
      setExecutionMessage(
        caseId
          ? "已完成最终签核，正式 case 已尝试标记为 approved。"
          : "已记录最终签核完成，生成正式 case 后可同步到后端流程。",
      );

      window.dispatchEvent(new Event("pd-ecr-workflow-updated"));
    } catch {
      setExecutionMessage("进入执行分配失败，请稍后重试。");
    } finally {
      setIsStartingExecution(false);
    }
  };

  return (
    <section className="enterprise-panel overflow-hidden">
      <div className="flex flex-col justify-between gap-3 border-b border-slate-200 bg-white px-5 py-4 lg:flex-row lg:items-center">
        <div>
          <p className="enterprise-section-title text-blue-700">最终签核</p>
          <h2 className="mt-1 text-lg font-semibold tracking-tight text-slate-900">
            邮件通知后的 Leader / 相关人签字
          </h2>
          <p className="mt-1 text-sm text-slate-500">
            1.2、1.3、1.4 由对应工程师确认完成后，再通知相关 leader 与签字人完成最终签核。
          </p>
        </div>

        <StatusPill tone={allSigned ? "green" : "blue"}>
          {signedCount}/{LEADER_SIGNOFF_ROLES.length} 已签字
        </StatusPill>
      </div>

      <div className="grid gap-3 bg-slate-50/60 p-5 lg:grid-cols-3">
        {LEADER_SIGNOFF_ROLES.map((role, index) => {
          const signedAt = signed[role.key];
          const isCurrent = !signedAt && index === nextUnsignedIndex;
          const canSign = canCurrentUserSignRole(role.key);

          return (
            <button
              key={role.key}
              type="button"
              disabled={!canSign}
              onClick={() => toggleSigned(role.key)}
              title={
                canSign
                  ? undefined
                  : role.key === "leader of initiator"
                    ? "仅发起人所在部门的 department_leader 可签字。"
                    : "仅 department_leader 或 pd_ecr_manager 可签字。"
              }
              className={`flex min-h-32 flex-col items-start justify-between rounded-xl border px-4 py-4 text-left shadow-sm transition ${
                signedAt
                  ? "border-emerald-200 bg-white text-emerald-900"
                  : !canSign
                    ? "cursor-not-allowed border-slate-200 bg-white/70 text-slate-400 opacity-70"
                    : isCurrent
                      ? "border-blue-300 bg-white text-blue-900 ring-2 ring-blue-100"
                      : "border-slate-200 bg-white text-slate-700 hover:border-blue-300 hover:bg-blue-50/40"
              }`}
            >
              <span className="flex items-start gap-3">
                <span
                  className={`flex size-8 shrink-0 items-center justify-center rounded-full text-xs font-bold ${
                    signedAt
                      ? "bg-emerald-600 text-white"
                      : isCurrent
                        ? "bg-blue-600 text-white"
                        : "bg-slate-200 text-slate-600"
                  }`}
                >
                  {signedAt ? <CheckCircle2 className="size-4" /> : index + 1}
                </span>

                <span>
                  <span className="block text-sm font-semibold">
                    {role.label}
                  </span>
                  <span className="mt-1 block text-xs leading-5 text-slate-500">
                    {role.hint}
                  </span>
                </span>
              </span>

              <span className="mt-4 inline-flex items-center gap-1.5 text-sm font-medium">
                {signedAt
                  ? `已签字 · ${signedAt}`
                  : !canSign
                    ? "当前用户不可操作"
                    : isCurrent
                      ? "当前待审批"
                      : "待处理"}
              </span>
            </button>
          );
        })}
      </div>

      <div className="border-t border-slate-200 bg-white px-5 py-4">
        <div className="flex flex-col gap-3 rounded-xl border border-slate-200 bg-slate-50 p-4 lg:flex-row lg:items-center lg:justify-between">
          <div>
            <p className="text-sm font-semibold text-slate-900">
              关闭准入
            </p>
            <p className="mt-1 text-sm text-slate-500">
              最终签字完成后，PD-ECR 可进入批准/归档状态。
            </p>
            {executionMessage ? (
              <p className="mt-2 text-sm font-medium text-blue-800">
                {executionMessage}
              </p>
            ) : null}
          </div>

          <Button
            type="button"
            disabled={!allSigned || isStartingExecution || executionStarted}
            onClick={startExecutionAssignment}
            className={
              executionStarted
                ? "bg-emerald-600 hover:bg-emerald-600"
                : "bg-blue-700 hover:bg-blue-800"
            }
          >
            {executionStarted ? (
              <CheckCircle2 className="size-4" />
            ) : (
              <PlayCircle className="size-4" />
            )}
            {executionStarted
              ? "已完成最终签核"
              : isStartingExecution
                ? "正在启动..."
                : "标记签核完成"}
          </Button>
        </div>
      </div>
    </section>
  );
}

function HistoryReadOnlyApprovalPanel() {
  return (
    <section className="enterprise-panel px-5 py-4">
      <div className="flex items-start gap-3">
        <div className="flex size-9 shrink-0 items-center justify-center rounded-xl bg-sky-50 text-sky-700">
          <LockKeyhole className="size-5" />
        </div>
        <div>
          <p className="enterprise-section-title text-sky-700">只读模式</p>
          <h2 className="mt-1 text-lg font-semibold tracking-tight text-slate-900">
            历史案例不可进入审批流
          </h2>
          <p className="mt-2 text-sm leading-6 text-slate-600">
            当前记录作为历史参考打开，可查看内容、来源和导出报告，但不会触发新的签字、分配或执行任务。
          </p>
        </div>
      </div>
    </section>
  );
}

export function PdEcrContentBlocks() {
  const navigate = useNavigate();
  const result = useMemo(() => loadActiveResult(), []);
  const [status, setStatus] = useState("Ready");
  const [, setWorkflowVersion] = useState(0);

  const reportUrl = resolvePdEcrAssetUrl(result.reportUrl);
  const recordId =
    result.currentCase?.backendCaseId ||
    result.draftId ||
    result.currentCase?.id ||
    "active-draft";

  useEffect(() => {
    const refresh = () => setWorkflowVersion((value) => value + 1);

    window.addEventListener("pd-ecr-leader-signoff-updated", refresh);
    window.addEventListener("pd-ecr-workflow-updated", refresh);

    return () => {
      window.removeEventListener("pd-ecr-leader-signoff-updated", refresh);
      window.removeEventListener("pd-ecr-workflow-updated", refresh);
    };
  }, []);

  const exportOnePage = async () => {
    const backendCaseId = result.currentCase?.backendCaseId;

    if (backendCaseId) {
      try {
        const response = await exportPdEcrCase(backendCaseId, "html");
        const downloadUrl = resolvePdEcrAssetUrl(String(response.url || ""));

        if (downloadUrl) {
          window.open(downloadUrl, "_blank", "noopener,noreferrer");
          setStatus("已导出后端正式 PD-ECR HTML 报告，可通过浏览器打印为 PDF。");
          return;
        }
      } catch {
        setStatus("后端 case 导出失败，正在尝试草稿或本地导出。");
      }
    }

    if (result.draftId) {
      try {
        const response = await exportPdEcrDraft(
          result.draftId,
          {
            draft_id: result.draftId,
            draft_status: result.draftStatus,
            input_snapshot: result.inputSnapshot,
            similar_cases: [],
            modules: result.modules.map((module) => ({
              id: module.id,
              module_id: module.id,
              title: module.title,
              summary: module.summary,
              content: module.data.content || module.summary,
              source_cases: module.sourceCases || [],
              source_files: module.sourceFiles || [],
              needs_human_input: module.needsHumanInput || false,
              warnings: module.warnings || [],
              data: module.data,
            })),
            generated_at: new Date().toISOString(),
          },
          "html",
        );

        const downloadUrl = resolvePdEcrAssetUrl(
          String(response.download_url || ""),
        );

        if (downloadUrl) {
          window.open(downloadUrl, "_blank", "noopener,noreferrer");
        }

        setStatus("已导出后端 PD-ECR V1 HTML 报告，可通过浏览器打印为 PDF。");
        return;
      } catch {
        setStatus("后端导出失败，已改用本地 HTML 导出。");
      }
    }

    downloadText(
      "pd-ecr-one-page.html",
      buildPdEcrOnePageHtml({
        cases: [],
        result,
      }),
      "text/html;charset=utf-8",
    );

    setStatus("已导出 PD-ECR 单页 HTML。");
  };

  const exportExcelCsv = () => {
    const rows = [
      ["Module", "Field", "Value"],
      ...result.modules.flatMap((module) =>
        Object.entries(module.data).map(([field, value]) => [
          module.title,
          field,
          typeof value === "string" ? value : JSON.stringify(value),
        ]),
      ),
    ];

    const csv = rows
      .map((row) =>
        row
          .map((value) => `"${String(value ?? "").replace(/"/g, '""')}"`)
          .join(","),
      )
      .join("\n");

    downloadText("pd-ecr-modules.csv", csv, "text/csv;charset=utf-8");
    setStatus("已导出 PD-ECR 模块 CSV。");
  };

  const copyListSummary = async () => {
    const text = [
      `PD-ECR: ${result.currentCase?.id || result.reportUrl || "Generated content"}`,
      `Source: ${result.source}`,
      ...result.modules.map((module) => `${module.title}: ${module.summary}`),
    ].join("\n");

    try {
      if (navigator.share) {
        await navigator.share({
          title: "PD-ECR list summary",
          text,
          url: window.location.href,
        });
      } else {
        await navigator.clipboard?.writeText(text);
      }

      setStatus("已准备 PD-ECR 列表摘要。");
    } catch {
      await navigator.clipboard?.writeText(text);
      setStatus("已复制 PD-ECR 列表摘要到剪贴板。");
    }
  };

  return (
    <div className="page-shell">
      <div className="w-full min-w-0 space-y-6">
        <header className="enterprise-panel px-5 py-4">
          <div className="flex flex-col justify-between gap-4 lg:flex-row lg:items-center">
            <div>
              <div className="flex flex-wrap items-center gap-3">
                <h1 className="text-2xl font-semibold tracking-tight text-slate-900">
                  {result.currentCase?.id || "PD-ECR AI"}
                </h1>

                <StatusPill tone={result.source === "history" ? "sky" : "blue"}>
                  {result.source === "history" ? "历史案例" : "AI 生成草稿"}
                </StatusPill>
              </div>

              <p className="mt-2 text-sm text-slate-500">
                PD-ECR 内容总览 · 发起确认、Leader 准入、AI 生成、工程师确认与最终签核
              </p>
            </div>

            <div className="flex flex-wrap gap-2">
              <Button
                variant="outline"
                onClick={() => navigate({ to: "/pd-ecr/tasks" })}
                className="bg-white hover:border-blue-300 hover:bg-blue-50"
              >
                <ClipboardList className="size-4" />
                我的任务
              </Button>

              <PdEcrProcessFlowButton />

              {reportUrl ? (
                <Button asChild className="bg-blue-700 hover:bg-blue-800">
                  <a href={reportUrl} target="_blank" rel="noreferrer">
                    打开完整报告
                  </a>
                </Button>
              ) : null}

              <Button
                variant="outline"
                onClick={() =>
                  navigate({
                    to:
                      result.source === "history" ? "/pd-ecr/cases" : "/pd-ecr",
                  })
                }
                className="bg-white hover:border-blue-300 hover:bg-blue-50"
                aria-label="返回 PD-ECR 平台"
              >
                <ArrowLeft className="size-4" />
                返回平台
              </Button>
            </div>
          </div>
        </header>

        {/* <CaseSummaryBar result={result} /> */}

        <WorkflowOverview result={result} recordId={recordId} />

        {result.source === "history" && (
          <div className="rounded-xl border border-sky-200 bg-sky-50 px-4 py-3 text-sm text-sky-800">
            <div className="flex items-start gap-2">
              <LockKeyhole className="mt-0.5 size-4 shrink-0" />
              <p>
                当前为历史案例只读视图，可查看内容、来源和导出参考报告，但不会触发审批、执行分配或任务流转。
              </p>
            </div>
          </div>
        )}

        <section className="enterprise-panel p-5">
          <div className="mb-5 flex flex-col justify-between gap-3 lg:flex-row lg:items-center">
            <div>
              <p className="enterprise-section-title text-blue-700">内容模块</p>
              <h2 className="mt-1 text-lg font-semibold tracking-tight text-slate-900">
                影响分析、验证计划与执行计划
              </h2>
              <p className="mt-2 text-sm text-slate-500">
                AI 生成 1.2、1.3、1.4 后，由对应工程师确认模块信息；全部确认后再通知相关 leader 与签字人。
              </p>
            </div>

            <div className="flex items-center gap-2 rounded-lg border border-blue-100 bg-blue-50 px-3 py-1.5 text-sm font-medium text-blue-700">
              <Sparkles className="size-4" />
              <span>
                {result.source === "history" ? "历史参考视图" : "AI 辅助可编辑草稿"}
              </span>
            </div>
          </div>

          <p className="mb-4 text-sm text-slate-500" role="status">
            {status}
          </p>

          <PdEcrModuleAccordion
            modules={result.modules}
            caseId={result.currentCase?.backendCaseId}
            workflowEnabled={result.source !== "history"}
          />
        </section>

        {result.source !== "history" ? (
          <LeaderSignOffButtons
            recordId={recordId}
            caseId={result.currentCase?.backendCaseId}
            initiator={compactValue(
              result.currentCase?.initiator,
              result.inputSnapshot?.initiator,
            )}
          />
        ) : (
          <HistoryReadOnlyApprovalPanel />
        )}

        <footer className="enterprise-panel flex flex-wrap items-center gap-3 px-5 py-4">
          <div className="mr-auto">
            <p className="text-sm font-semibold text-slate-900">导出与分享</p>
            <p className="mt-1 text-sm text-slate-500">
              用于评审、归档或线下沟通。
            </p>
          </div>

          <Button
            type="button"
            variant="outline"
            className="bg-white hover:border-blue-300 hover:bg-blue-50"
            onClick={exportExcelCsv}
          >
            <Download className="size-4" />
            导出 CSV
          </Button>

          <Button
            type="button"
            variant="outline"
            className="bg-white hover:border-blue-300 hover:bg-blue-50"
            onClick={exportOnePage}
          >
            <Download className="size-4" />
            导出 HTML / PDF
          </Button>

          {!reportUrl ? (
            <Button
              type="button"
              className="bg-blue-700 hover:bg-blue-800"
              onClick={copyListSummary}
            >
              <ClipboardList className="size-4" />
              复制摘要
            </Button>
          ) : null}

          <Button
            variant="ghost"
            size="icon"
            onClick={() => navigate({ to: "/pd-ecr" })}
            aria-label="回到主页"
          >
            <Home className="size-5" />
          </Button>
        </footer>
      </div>
    </div>
  );
}
