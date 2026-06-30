import { useNavigate } from "@tanstack/react-router"
import {
  ArrowLeft,
  CheckCircle2,
  ClipboardList,
  Clock3,
  Download,
  FileText,
  Home,
  LockKeyhole,
  Sparkles,
} from "lucide-react"
import { useMemo, useState } from "react"

import { Button } from "@/components/ui/button"
import { exportPdEcrDraft, resolvePdEcrAssetUrl } from "@/lib/pdEcrApi"
import { PdEcrModuleAccordion, PdEcrResultModuleAccordion } from "./PdEcrModuleAccordion"
import { PdEcrProcessFlowButton } from "./PdEcrProcessFlow"
import { buildPdEcrOnePageHtml, downloadText } from "./pdEcrExport"
import { loadActiveResult, type PdEcrStoredResult } from "./pdEcrState"
import { PdEcrFeasibilityConfirmation, PdEcrLeaderSigning } from "./PdEcrFeasibilityConfirmation"

function compactValue(...values: unknown[]) {
  for (const value of values) {
    const text = String(value ?? "").trim()
    if (text) return text
  }
  return "-"
}

function prettyStatus(value: string | undefined, isHistory: boolean) {
  if (isHistory) return "Read only"
  const normalized = compactValue(value, "draft").replace(/_/g, " ")
  return normalized.charAt(0).toUpperCase() + normalized.slice(1)
}

function statusClassName(result: PdEcrStoredResult) {
  if (result.source === "history") {
    return "border-sky-200 bg-sky-50 text-sky-800"
  }
  if (["approved", "closed", "implementation"].includes(String(result.draftStatus || "").toLowerCase())) {
    return "border-emerald-200 bg-emerald-50 text-emerald-800"
  }
  return "border-amber-200 bg-amber-50 text-amber-800"
}

function CaseSummaryBar({ result }: { result: PdEcrStoredResult }) {
  const row = result.currentCase
  const snapshot = result.inputSnapshot || {}
  const completeModules = result.modules.filter((module) => {
    const hasData = Object.keys(module.data || {}).length > 0
    return hasData || Boolean(module.summary?.trim())
  }).length
  const sourceCount = new Set(
    result.modules.flatMap((module) => [
      ...(module.sourceCases || []),
      ...(module.sourceFiles || []),
    ]),
  ).size

  const items = [
    ["Case No.", compactValue(row?.dcNo, row?.mcrNo, row?.id, result.draftId)],
    ["Part No.", compactValue(row?.partNumber, row?.productNo, snapshot.part_number, snapshot.product_no)],
    ["Project", compactValue(row?.project, row?.customer, snapshot.project, snapshot.customer_project)],
    ["Change Type", compactValue(row?.changeType, snapshot.change_type)],
    ["Owner", compactValue(row?.initiator, snapshot.initiator)],
    ["Modules", `${completeModules}/${result.modules.length || 4}`],
  ]

  return (
    <div className="sticky top-0 z-20 border-y border-stone-200 bg-white/95 px-4 py-3 shadow-sm backdrop-blur">
      <div className="flex flex-col gap-3 xl:flex-row xl:items-center xl:justify-between">
        <div className="flex min-w-0 flex-wrap items-center gap-2">
          <span className={`inline-flex items-center gap-1.5 rounded-full border px-3 py-1 text-xs font-semibold ${statusClassName(result)}`}>
            {result.source === "history" ? <LockKeyhole className="size-3.5" /> : <Clock3 className="size-3.5" />}
            {prettyStatus(result.draftStatus, result.source === "history")}
          </span>
          <span className="inline-flex items-center gap-1.5 rounded-full border border-stone-200 bg-stone-50 px-3 py-1 text-xs font-semibold text-stone-600">
            <FileText className="size-3.5" />
            {result.source === "history" ? "Historical PDF/parsed case" : "Editable PD-ECR draft"}
          </span>
          {sourceCount > 0 && (
            <span className="inline-flex items-center gap-1.5 rounded-full border border-emerald-200 bg-emerald-50 px-3 py-1 text-xs font-semibold text-emerald-800">
              <CheckCircle2 className="size-3.5" />
              {sourceCount} source reference{sourceCount > 1 ? "s" : ""}
            </span>
          )}
        </div>
        <dl className="grid min-w-0 flex-1 grid-cols-2 gap-2 sm:grid-cols-3 xl:max-w-5xl xl:grid-cols-6">
          {items.map(([label, value]) => (
            <div key={label} className="min-w-0 rounded-md border border-stone-200 bg-stone-50 px-3 py-2">
              <dt className="text-[10px] font-semibold uppercase text-stone-400">{label}</dt>
              <dd className="mt-0.5 truncate text-sm font-semibold text-stone-800" title={value}>
                {value}
              </dd>
            </div>
          ))}
        </dl>
      </div>
    </div>
  )
}

export function PdEcrContentBlocks() {
  const navigate = useNavigate()
  const result = useMemo(() => loadActiveResult(), [])
  const [status, setStatus] = useState("Ready")
  const [activePage, setActivePage] = useState<"page1" | "page2">("page1")
  const reportUrl = resolvePdEcrAssetUrl(result.reportUrl)

  const exportOnePage = async () => {
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
        )
        const downloadUrl = resolvePdEcrAssetUrl(
          String(response.download_url || ""),
        )
        if (downloadUrl) {
          window.open(downloadUrl, "_blank", "noopener,noreferrer")
        }
        setStatus("Exported backend PD-ECR V1 HTML report.")
        return
      } catch {
        setStatus("Backend export failed. Downloaded local HTML instead.")
      }
    }

    downloadText(
      "pd-ecr-one-page.html",
      buildPdEcrOnePageHtml({
        cases: [],
        result,
      }),
      "text/html;charset=utf-8",
    )
    setStatus("Exported PD-ECR one-page HTML.")
  }

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
    ]

    const csv = rows
      .map((row) =>
        row
          .map((value) => `"${String(value ?? "").replace(/"/g, '""')}"`)
          .join(","),
      )
      .join("\n")

    downloadText("pd-ecr-modules.csv", csv, "text/csv;charset=utf-8")
    setStatus("Exported PD-ECR module CSV.")
  }

  const shareSharePointList = async () => {
    const text = [
      `PD-ECR: ${result.currentCase?.id || result.reportUrl || "Generated content"}`,
      `Source: ${result.source}`,
      ...result.modules.map((module) => `${module.title}: ${module.summary}`),
    ].join("\n")

    try {
      if (navigator.share) {
        await navigator.share({
          title: "PD-ECR SharePoint list item",
          text,
          url: window.location.href,
        })
      } else {
        await navigator.clipboard?.writeText(text)
      }
      setStatus("Prepared SharePoint list content.")
    } catch {
      await navigator.clipboard?.writeText(text)
      setStatus("Copied SharePoint list content to clipboard.")
    }
  }

  return (
    <div className="min-h-[calc(100vh-7rem)] bg-stone-50 text-stone-900">
      <div className="w-full min-w-0 space-y-6">
        <header className="rounded-lg border border-stone-200 bg-white px-6 py-5 shadow-sm">
          <div className="flex flex-col justify-between gap-4 lg:flex-row lg:items-center">
            <div>
              <div className="flex flex-wrap items-center gap-3">
                <h1 className="text-3xl font-semibold tracking-normal text-stone-900">
                  {result.currentCase?.id || "PD-ECR AI"}
                </h1>
                <span className="inline-flex items-center rounded-full border border-amber-200 bg-amber-50 px-3 py-1 text-xs font-semibold text-amber-800">
                  {result.source === "history"
                    ? "Historical case"
                    : "Generated content"}
                </span>
              </div>
              <p className="mt-2 text-sm text-stone-500">
                PD-ECR 内容模块 · 点击展开查看详细内容与签字状态
              </p>
            </div>
            <div className="flex flex-wrap gap-2">
              <Button
                variant="outline"
                onClick={() => navigate({ to: "/pd-ecr/tasks" })}
                className="bg-white"
              >
                <ClipboardList className="size-4" />
                My Tasks
              </Button>
              <Button
                variant="outline"
                onClick={() =>
                  navigate({
                    to: result.source === "history" ? "/pd-ecr/cases" : "/pd-ecr",
                  })
                }
                className="bg-white"
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
                Historical cases are opened as read-only references. You can review
                the preserved content and export/copy references, while workflow
                assignment and approval actions stay disabled for source records.
              </p>
            </div>
          </div>
        )}

        {/* ═══ Page Tabs ═══ */}
        <div className="flex flex-wrap items-center gap-2 rounded-lg border border-stone-200 bg-white p-1 shadow-sm">
          <button
            type="button"
            onClick={() => setActivePage("page1")}
            aria-pressed={activePage === "page1"}
            className={`flex min-h-11 items-center gap-2 rounded-md px-4 py-2 text-sm font-semibold transition ${
              activePage === "page1"
                ? "bg-stone-900 text-white shadow-sm"
                : "text-stone-500 hover:bg-stone-50 hover:text-stone-800"
            }`}
          >
            <span className="flex size-6 items-center justify-center rounded-full border border-current text-xs">1</span>
            <span>变更描述与可行性确认</span>
          </button>
          <button
            type="button"
            onClick={() => setActivePage("page2")}
            aria-pressed={activePage === "page2"}
            className={`flex min-h-11 items-center gap-2 rounded-md px-4 py-2 text-sm font-semibold transition ${
              activePage === "page2"
                ? "bg-stone-900 text-white shadow-sm"
                : "text-stone-500 hover:bg-stone-50 hover:text-stone-800"
            }`}
          >
            <span className="flex size-6 items-center justify-center rounded-full border border-current text-xs">2</span>
            <span>验证结果与领导签核</span>
          </button>
        </div>

        {/* ═══ Page 1: Accordion + Feasibility Confirmation ═══ */}
        {activePage === "page1" && (
          <>
            <section className="rounded-lg border border-stone-200 bg-white p-5 shadow-sm">
              <div className="mb-5 flex flex-col justify-between gap-3 lg:flex-row lg:items-center">
                <div>
                  <p className="text-xs font-semibold uppercase tracking-wide text-sky-700">
                    Step 1
                  </p>
                  <h2 className="text-xl font-bold tracking-normal text-sky-900">
                    Change description
                  </h2>
                </div>
                <div className="flex items-center gap-2 text-sm text-amber-800">
                  <Sparkles className="size-4" />
                  <span>
                    {result.source === "history"
                      ? "Reference view"
                      : "AI-assisted editable draft"}
                  </span>
                </div>
              </div>
              <p className="mb-4 text-sm text-stone-500" role="status">
                {status}
              </p>

              <PdEcrModuleAccordion
                modules={result.modules}
                caseId={result.currentCase?.backendCaseId}
                workflowEnabled={result.source !== "history"}
              />
            </section>

            {/* Feasibility Confirmation (Step 2) */}
            <section className="rounded-lg border border-stone-200 bg-white p-5 shadow-sm">
              <div className="mb-5">
                <p className="text-xs font-semibold uppercase tracking-wide text-sky-700">
                  Step 2
                </p>
                <h2 className="text-xl font-bold tracking-normal text-sky-900">
                  Change feasibility confirmation
                </h2>
              </div>
              <PdEcrFeasibilityConfirmation
                module={{
                  id: "feasibility-confirmation",
                  title: "变更可行性确认",
                  subtitle: "Feasibility Confirmation",
                  summary: "",
                  data: {},
                }}
              />
            </section>
          </>
        )}

        {/* ═══ Page 2: Results (left) + Leader Signing (right) ═══ */}
        {activePage === "page2" && (
          <div className="grid gap-5 xl:grid-cols-[1fr_22rem]">
            {/* LEFT: Validation & Implementation Results — same format as Page 1 modules */}
            <div className="min-w-0 space-y-5">
              <section className="rounded-lg border border-stone-200 bg-white shadow-sm">
                <div className="border-b border-stone-200 px-5 py-4">
                  <p className="text-xs font-semibold uppercase tracking-wide text-sky-700">
                    Step 3
                  </p>
                  <h2 className="text-xl font-bold tracking-normal text-sky-900">
                    QAC & Implementation Results
                  </h2>
                </div>
                <div className="p-5">
                  <PdEcrResultModuleAccordion modules={result.modules} />
                </div>
              </section>
            </div>

            {/* RIGHT: Leader Signing (sticky) */}
            <div className="hidden xl:block">
              <div className="sticky top-4" style={{ maxHeight: "calc(100vh - 8rem)", overflowY: "auto" }}>
                <PdEcrLeaderSigning />
              </div>
            </div>

            {/* Mobile: Leader Signing below */}
            <div className="xl:hidden">
              <PdEcrLeaderSigning />
            </div>
          </div>
        )}

        <footer className="flex flex-wrap items-center gap-3 pb-2">
          <PdEcrProcessFlowButton />
          <Button
            type="button"
            variant="outline"
            className="bg-white"
            onClick={exportExcelCsv}
          >
            <Download className="size-4" />
            Export Excel-compatible CSV
          </Button>
          <Button
            type="button"
            variant="outline"
            className="bg-white"
            onClick={exportOnePage}
          >
            <Download className="size-4" />
            Export PD-ECR One Page
          </Button>
          {reportUrl ? (
            <Button asChild className="ml-auto bg-stone-800 hover:bg-stone-700">
              <a href={reportUrl} target="_blank" rel="noreferrer">
                打开完整报告
              </a>
            </Button>
          ) : (
            <Button
              type="button"
              className="ml-auto bg-stone-800 hover:bg-stone-700"
              onClick={shareSharePointList}
            >
              <ClipboardList className="size-4" />
              Copy SharePoint content
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
  )
}
