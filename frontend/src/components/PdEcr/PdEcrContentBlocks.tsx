import { useNavigate } from "@tanstack/react-router"
import {
  ArrowLeft,
  ArrowRight,
  ClipboardList,
  Download,
  FileCheck2,
  Home,
  Sparkles,
} from "lucide-react"
import { useMemo, useState } from "react"

import { Button } from "@/components/ui/button"
import { exportPdEcrDraft, resolvePdEcrAssetUrl } from "@/lib/pdEcrApi"
import { PdEcrProcessFlowButton } from "./PdEcrProcessFlow"
import { buildPdEcrOnePageHtml, downloadText } from "./pdEcrExport"
import {
  loadActiveResult,
  type PdEcrDisplayModule,
  saveActiveResult,
} from "./pdEcrState"

function normalizePreviewToken(text: string) {
  return text
    .toLowerCase()
    .replace(/[^a-z0-9\u4e00-\u9fa5]+/g, "")
    .trim()
}

function isTemplateNoiseLine(line: string, module: PdEcrDisplayModule) {
  const normalizedLine = normalizePreviewToken(line)
  const normalizedTitle = normalizePreviewToken(module.title)
  const normalizedSubtitle = normalizePreviewToken(module.subtitle)

  if (!normalizedLine) return true
  if (normalizedLine === normalizedTitle || normalizedLine === normalizedSubtitle) {
    return true
  }

  return (
    /^[-:|\s]+$/.test(line) ||
    /^field\s*\/.*content\s*\//i.test(line) ||
    /^content\s*\d+\s*\/\s*\d+$/i.test(line) ||
    /^step\s*\d+(\.\d+)?\b/i.test(line) ||
    /^sheet\s*:/i.test(line)
  )
}

/** Strip template markdown for clean card preview text. */
function cleanModulePreviewText(module: PdEcrDisplayModule) {
  const source = String(module.summary || module.data.content || "")
  const lines = source
    .replace(/```[\s\S]*?```/g, " ")
    .split(/\r?\n/)
    .map((line) =>
      line
        .replace(/^#{1,6}\s*/, "")
        .replace(/^>\s*/, "")
        .replace(/^[-*+]\s+/, "")
        .replace(/\*\*(.+?)\*\*/g, "$1")
        .replace(/\*(.+?)\*/g, "$1")
        .replace(/`([^`]+)`/g, "$1")
        .replace(/\[(.+?)\]\(.*?\)/g, "$1")
        .trim(),
    )
    .filter((line) => !line.includes("|"))
    .filter((line) => !isTemplateNoiseLine(line, module))

  return lines
    .join(" ")
    .replace(/\s+/g, " ")
    .trim()
}

function GeneratedBlock({
  module,
  onOpen,
}: {
  module: PdEcrDisplayModule
  onOpen: (module: PdEcrDisplayModule) => void
}) {
  const cleanSummary = cleanModulePreviewText(module)
  const empty =
    !cleanSummary ||
    cleanSummary === "暂无内容" ||
    cleanSummary === "-" ||
    cleanSummary.startsWith("No extracted")

  return (
    <button
      type="button"
      onClick={() => onOpen(module)}
      className="group flex min-h-44 flex-col rounded-lg border border-stone-200 bg-white p-5 text-left shadow-sm transition hover:border-amber-300 hover:shadow-md focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-amber-500"
    >
      <div className="flex items-start justify-between gap-4">
        <div className={`flex size-11 items-center justify-center rounded-lg ${empty ? "bg-stone-100 text-stone-400" : "bg-amber-50 text-amber-700"}`}>
          <FileCheck2 className="size-5" />
        </div>
        <ArrowRight className="size-4 text-stone-400 transition group-hover:translate-x-1 group-hover:text-amber-700" />
      </div>
      <p className="mt-5 text-xs font-semibold uppercase tracking-wide text-stone-500">
        {module.subtitle}
      </p>
      <h2 className="mt-1 text-xl font-semibold tracking-normal text-stone-900">
        {module.title}
      </h2>
      <p className={`mt-3 line-clamp-3 text-sm leading-6 ${empty ? "italic text-stone-400" : "text-stone-600"}`}>
        {empty ? "Waiting for AI generation — click to configure" : cleanSummary}
      </p>
    </button>
  )
}

export function PdEcrContentBlocks() {
  const navigate = useNavigate()
  const result = useMemo(() => loadActiveResult(), [])
  const [status, setStatus] = useState("Ready")
  const reportUrl = resolvePdEcrAssetUrl(result.reportUrl)

  const openModule = (module: PdEcrDisplayModule) => {
    saveActiveResult(result)
    navigate({
      to: "/pd-ecr/content/$moduleId",
      params: { moduleId: module.id },
    })
  }

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
                PD-ECR content block · 点击模块查看对应报告内容
              </p>
            </div>
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
        </header>

        <section className="rounded-lg border border-stone-200 bg-white p-5 shadow-sm">
          <div className="mb-5 flex flex-col justify-between gap-3 lg:flex-row lg:items-center">
            <div>
              <p className="text-xs font-semibold uppercase tracking-wide text-stone-500">
                AI output
              </p>
              <h2 className="text-xl font-semibold tracking-normal text-stone-900">
                每页内容模块
              </h2>
            </div>
            <div className="flex items-center gap-2 text-sm text-amber-800">
              <Sparkles className="size-4" />
              <span>已按 PD-ECR 报告结构整理</span>
            </div>
          </div>
          <p className="mb-4 text-sm text-stone-500" role="status">
            {status}
          </p>

          <div className="grid gap-5 md:grid-cols-2 xl:grid-cols-3">
            {result.modules.map((module) => (
              <GeneratedBlock
                key={module.id}
                module={module}
                onOpen={openModule}
              />
            ))}
          </div>
        </section>

        <footer className="flex flex-wrap items-center gap-3 pb-2">
          <PdEcrProcessFlowButton />
          <Button
            type="button"
            variant="outline"
            className="bg-white"
            onClick={exportExcelCsv}
          >
            <Download className="size-4" />
            Export PD-ECR Excel file
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
              SharePoint list
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
