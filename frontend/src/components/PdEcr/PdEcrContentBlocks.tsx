import { useNavigate } from "@tanstack/react-router";
import {
  ArrowLeft,
  CheckCircle2,
  ClipboardList,
  Clock3,
  Download,
  FileText,
  Home,
  LockKeyhole,
  PlayCircle,
  Sparkles,
} from "lucide-react";
import { useMemo, useState } from "react";

import { Button } from "@/components/ui/button";
import useAuth from "@/hooks/useAuth";
import {
  exportPdEcrCase,
  exportPdEcrDraft,
  resolvePdEcrAssetUrl,
  transitionPdEcrCase,
} from "@/lib/pdEcrApi";
import { PdEcrModuleAccordion } from "./PdEcrModuleAccordion";
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

function prettyStatus(value: string | undefined, isHistory: boolean) {
  if (isHistory) return "Read only";
  const normalized = compactValue(value, "draft").replace(/_/g, " ");
  return normalized.charAt(0).toUpperCase() + normalized.slice(1);
}

function statusClassName(result: PdEcrStoredResult) {
  if (result.source === "history") {
    return "border-sky-200 bg-sky-50 text-sky-800";
  }
  if (
    ["approved", "closed", "implementation"].includes(
      String(result.draftStatus || "").toLowerCase(),
    )
  ) {
    return "border-emerald-200 bg-emerald-50 text-emerald-800";
  }
  return "border-amber-200 bg-amber-50 text-amber-800";
}

function CaseSummaryBar({ result }: { result: PdEcrStoredResult }) {
  const row = result.currentCase;
  const snapshot = result.inputSnapshot || {};
  const completeModules = result.modules.filter((module) => {
    const hasData = Object.keys(module.data || {}).length > 0;
    return hasData || Boolean(module.summary?.trim());
  }).length;
  const sourceCount = new Set(
    result.modules.flatMap((module) => [
      ...(module.sourceCases || []),
      ...(module.sourceFiles || []),
    ]),
  ).size;

  const items = [
    ["Case No.", compactValue(row?.dcNo, row?.mcrNo, row?.id, result.draftId)],
    [
      "Part No.",
      compactValue(
        row?.partNumber,
        row?.productNo,
        snapshot.part_number,
        snapshot.product_no,
      ),
    ],
    [
      "Project",
      compactValue(
        row?.project,
        row?.customer,
        snapshot.project,
        snapshot.customer_project,
      ),
    ],
    ["Change Type", compactValue(row?.changeType, snapshot.change_type)],
    ["Owner", compactValue(row?.initiator, snapshot.initiator)],
    ["Modules", `${completeModules}/${result.modules.length || 4}`],
  ];

  return (
    <div className="sticky top-0 z-20 border-y border-stone-200/60 bg-white/85 px-4 py-3 shadow-sm backdrop-blur">
      <div className="flex flex-col gap-3 xl:flex-row xl:items-center xl:justify-between">
        <div className="flex min-w-0 flex-wrap items-center gap-2">
          <span
            className={`inline-flex items-center gap-1.5 rounded-full border px-3 py-1 text-xs font-semibold shadow-sm ${statusClassName(result)}`}
          >
            {result.source === "history" ? (
              <LockKeyhole className="size-3.5" />
            ) : (
              <Clock3 className="size-3.5" />
            )}
            {prettyStatus(result.draftStatus, result.source === "history")}
          </span>
          <span className="inline-flex items-center gap-1.5 rounded-full border border-stone-200 bg-stone-50 px-3 py-1 text-xs font-semibold text-stone-600 shadow-sm">
            <FileText className="size-3.5" />
            {result.source === "history"
              ? "Historical PDF/parsed case"
              : "Editable PD-ECR draft"}
          </span>
          {sourceCount > 0 && (
            <span className="inline-flex items-center gap-1.5 rounded-full border border-emerald-200 bg-emerald-50 px-3 py-1 text-xs font-semibold text-emerald-800 shadow-sm">
              <CheckCircle2 className="size-3.5" />
              {sourceCount} source reference{sourceCount > 1 ? "s" : ""}
            </span>
          )}
        </div>
        <dl className="grid min-w-0 flex-1 grid-cols-2 gap-2 sm:grid-cols-3 xl:max-w-5xl xl:grid-cols-6">
          {items.map(([label, value]) => (
            <div
              key={label}
              className="min-w-0 rounded-md border border-stone-200 bg-stone-50 px-3 py-2"
            >
              <dt className="text-[10px] font-semibold uppercase text-stone-400">
                {label}
              </dt>
              <dd
                className="mt-0.5 truncate text-sm font-semibold text-stone-800"
                title={value}
              >
                {value}
              </dd>
            </div>
          ))}
        </dl>
      </div>
    </div>
  );
}

const LEADER_SIGNOFF_ROLES = [
  "leader of initiator",
  "Section manager of function",
  "HOD/TCR",
] as const;

type LeaderSignoffState = Record<string, string>;

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

  const allSigned = LEADER_SIGNOFF_ROLES.every((role) => signed[role]);
  const signedCount = LEADER_SIGNOFF_ROLES.filter(
    (role) => signed[role],
  ).length;
  const nextUnsignedIndex = LEADER_SIGNOFF_ROLES.findIndex(
    (role) => !signed[role],
  );

  const toggleSigned = (role: string) => {
    if (!canCurrentUserSignRole(role)) return;
    setSigned((current) => {
      const next = { ...current };
      if (next[role]) {
        delete next[role];
      } else {
        next[role] = new Date().toLocaleString();
      }
      localStorage.setItem(
        leaderSignoffStorageKey(recordId),
        JSON.stringify(next),
      );
      return next;
    });
  };

  const canCurrentUserSignRole = (role: string) => {
    if (role === "leader of initiator") {
      return canConfirmInitiatorLeader(currentUser, initiator);
    }
    return ["department_leader", "pd_ecr_manager"].includes(
      currentUser?.pd_ecr_role || "",
    );
  };

  const startExecutionAssignment = async () => {
    if (!allSigned || isStartingExecution || executionStarted) return;

    setIsStartingExecution(true);
    setExecutionMessage("");
    try {
      if (caseId) {
        await transitionPdEcrCase(caseId, "execution_assignment");
      }
      localStorage.setItem(
        leaderExecutionStorageKey(recordId),
        JSON.stringify({
          status: "execution_assignment",
          startedAt: new Date().toISOString(),
        }),
      );
      setExecutionStarted(true);
      setExecutionMessage(
        caseId
          ? "已进入执行分配阶段，后续可分派 1.4 执行计划任务。"
          : "已记录进入执行分配阶段，生成正式 case 后可同步到后端流程。",
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
      <div className="flex flex-col justify-between gap-3 border-b border-slate-200 bg-slate-50/70 px-5 py-4 lg:flex-row lg:items-center">
        <div>
          <p className="enterprise-section-title">Approval gate</p>
          <h2 className="mt-1 text-lg font-semibold text-slate-900">
            领导签字与执行准入
          </h2>
          <p className="mt-1 text-sm leading-6 text-slate-500">
            三方签字完成后，流程进入 1.4 执行计划分配。
          </p>
        </div>
        <span
          className={`inline-flex w-fit items-center rounded-md border px-3 py-1.5 text-sm font-semibold ${
            allSigned
              ? "border-emerald-200 bg-emerald-50 text-emerald-700"
              : "border-blue-200 bg-blue-50 text-blue-700"
          }`}
        >
          {signedCount}/{LEADER_SIGNOFF_ROLES.length} signed
        </span>
      </div>

      <div className="grid gap-3 p-5 lg:grid-cols-3">
        {LEADER_SIGNOFF_ROLES.map((role) => {
          const signedAt = signed[role];
          const index = LEADER_SIGNOFF_ROLES.indexOf(role);
          const isCurrent = !signedAt && index === nextUnsignedIndex;
          const canSign = canCurrentUserSignRole(role);
          return (
            <button
              key={role}
              type="button"
              disabled={!canSign}
              onClick={() => toggleSigned(role)}
              title={
                canSign
                  ? undefined
                  : role === "leader of initiator"
                    ? "只能由发起人所在部门的 department_leader 签字。"
                    : "只能由 department_leader 或 pd_ecr_manager 签字。"
              }
              className={`flex min-h-28 flex-col items-start justify-between rounded-md border px-4 py-3 text-left transition ${
                signedAt
                  ? "border-emerald-300 bg-emerald-50 text-emerald-900"
                  : !canSign
                    ? "cursor-not-allowed border-slate-200 bg-slate-50/70 text-slate-400 opacity-70"
                    : isCurrent
                    ? "border-blue-300 bg-blue-50 text-blue-900"
                    : "border-slate-200 bg-slate-50/70 text-slate-700 hover:border-blue-300 hover:bg-white"
              }`}
            >
              <span className="flex items-center gap-3">
                <span
                  className={`flex size-7 shrink-0 items-center justify-center rounded-full text-xs font-bold ${
                    signedAt
                      ? "bg-emerald-600 text-white"
                      : isCurrent
                        ? "bg-blue-600 text-white"
                        : "bg-slate-200 text-slate-600"
                  }`}
                >
                  {signedAt ? <CheckCircle2 className="size-4" /> : index + 1}
                </span>
                <span className="text-base font-semibold">{role}</span>
              </span>
              <span className="mt-3 inline-flex items-center gap-1.5 text-sm font-medium">
                {signedAt
                  ? `Signed · ${signedAt}`
                  : !canSign
                    ? "No permission"
                    : isCurrent
                    ? "Current approval"
                    : "Waiting"}
              </span>
            </button>
          );
        })}
      </div>

      <div className="border-t border-slate-200 bg-white px-5 py-4">
        <div className="flex flex-col gap-3 rounded-md border border-blue-100 bg-blue-50/70 p-4 lg:flex-row lg:items-center lg:justify-between">
          <div>
            <p className="text-sm font-semibold text-blue-900">
              三方签字完成后进入执行分配
            </p>
            <p className="mt-1 text-sm leading-6 text-slate-600">
              下一步会把流程推进到 execution assignment，用 1.4
              执行计划生成执行任务。
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
              ? "Execution assignment started"
              : isStartingExecution
                ? "Starting..."
                : "Start execution assignment"}
          </Button>
        </div>
      </div>
    </section>
  );
}

export function PdEcrContentBlocks() {
  const navigate = useNavigate();
  const result = useMemo(() => loadActiveResult(), []);
  const [status, setStatus] = useState("Ready");
  const reportUrl = resolvePdEcrAssetUrl(result.reportUrl);
  const recordId =
    result.currentCase?.backendCaseId ||
    result.draftId ||
    result.currentCase?.id ||
    "active-draft";

  const exportOnePage = async () => {
    const backendCaseId = result.currentCase?.backendCaseId;
    if (backendCaseId) {
      try {
        const response = await exportPdEcrCase(backendCaseId, "html");
        const downloadUrl = resolvePdEcrAssetUrl(String(response.url || ""));
        if (downloadUrl) {
          window.open(downloadUrl, "_blank", "noopener,noreferrer");
          setStatus(
            "Exported official backend PD-ECR HTML report. Use browser Print to save as PDF.",
          );
          return;
        }
      } catch {
        setStatus(
          "Backend case export failed. Trying draft/local export instead.",
        );
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
        setStatus(
          "Exported backend PD-ECR V1 HTML report. Use browser Print to save as PDF.",
        );
        return;
      } catch {
        setStatus("Backend export failed. Downloaded local HTML instead.");
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
    setStatus("Exported PD-ECR one-page HTML.");
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
    setStatus("Exported PD-ECR module CSV.");
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
      setStatus("Prepared PD-ECR list summary.");
    } catch {
      await navigator.clipboard?.writeText(text);
      setStatus("Copied PD-ECR list summary to clipboard.");
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
                <span className="inline-flex items-center rounded-md border border-blue-200 bg-blue-50 px-3 py-1 text-xs font-semibold text-blue-700">
                  {result.source === "history"
                    ? "Historical case"
                    : "Generated content"}
                </span>
              </div>
              <p className="mt-2 text-sm text-slate-500">
                PD-ECR 内容模块 · 影响分析、验证计划、执行计划与签核准入
              </p>
            </div>
            <div className="flex flex-wrap gap-2">
              <Button
                variant="outline"
                onClick={() => navigate({ to: "/pd-ecr/tasks" })}
                className="bg-white hover:border-blue-300 hover:bg-blue-50"
              >
                <ClipboardList className="size-4" />
                My Tasks
              </Button>
              <Button
                variant="outline"
                onClick={() =>
                  navigate({
                    to:
                      result.source === "history" ? "/pd-ecr/cases" : "/pd-ecr",
                  })
                }
                className="bg-white hover:border-blue-300 hover:bg-blue-50"
                aria-label="返回 PD-ECR Platform"
              >
                <ArrowLeft className="size-4" />
                返回平台
              </Button>
            </div>
          </div>
        </header>

        <CaseSummaryBar result={result} />

        {result.source === "history" && (
          <div className="rounded-lg border border-sky-200 bg-sky-50 px-4 py-3 text-sm text-sky-800">
            <div className="flex items-start gap-2">
              <LockKeyhole className="mt-0.5 size-4 shrink-0" />
              <p>
                Historical cases are opened as read-only references. You can
                review the preserved content and export/copy references, while
                workflow assignment and approval actions stay disabled for
                source records.
              </p>
            </div>
          </div>
        )}

        <section className="enterprise-panel p-5">
          <div className="mb-5 flex flex-col justify-between gap-3 lg:flex-row lg:items-center">
            <div>
              <p className="enterprise-section-title text-blue-700">Step 2</p>
              <h2 className="mt-1 text-xl font-semibold tracking-tight text-slate-900">
                Impact, QAC validation and implementation
              </h2>
            </div>
            <div className="flex items-center gap-2 rounded-md border border-blue-100 bg-blue-50 px-3 py-1.5 text-sm font-medium text-blue-700">
              <Sparkles className="size-4" />
              <span>
                {result.source === "history"
                  ? "Reference view"
                  : "AI-assisted editable draft"}
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

        <LeaderSignOffButtons
          recordId={recordId}
          caseId={result.currentCase?.backendCaseId}
          initiator={compactValue(
            result.currentCase?.initiator,
            result.inputSnapshot?.initiator,
          )}
        />

        <footer className="flex flex-wrap items-center gap-3 pb-2">
          <PdEcrProcessFlowButton />
          <Button
            type="button"
            variant="outline"
            className="bg-white hover:border-blue-300 hover:bg-blue-50"
            onClick={exportExcelCsv}
          >
            <Download className="size-4" />
            Export Excel-compatible CSV
          </Button>
          <Button
            type="button"
            variant="outline"
            className="bg-white hover:border-blue-300 hover:bg-blue-50"
            onClick={exportOnePage}
          >
            <Download className="size-4" />
            Export official HTML/PDF
          </Button>
          {reportUrl ? (
            <Button asChild className="ml-auto bg-blue-700 hover:bg-blue-800">
              <a href={reportUrl} target="_blank" rel="noreferrer">
                打开完整报告
              </a>
            </Button>
          ) : (
            <Button
              type="button"
              className="ml-auto bg-blue-700 hover:bg-blue-800"
              onClick={copyListSummary}
            >
              <ClipboardList className="size-4" />
              Copy list summary
            </Button>
          )}
          <Button
            variant="ghost"
            size="icon"
            onClick={() => navigate({ to: "/pd-ecr" })}
          >
            <Home className="size-5" />
          </Button>
        </footer>
      </div>
    </div>
  );
}
