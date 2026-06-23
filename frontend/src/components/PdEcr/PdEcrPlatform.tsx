import { useMutation } from "@tanstack/react-query"
import { useNavigate } from "@tanstack/react-router"
import {
  CalendarClock,
  Database,
  FolderKanban,
  Search,
  Sparkles,
} from "lucide-react"
import { type ReactNode, useId, useState } from "react"

import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import {
  createPdEcrCase,
  generatePdEcrReport,
  type PdEcrInput,
  searchPdEcrHistory,
} from "@/lib/pdEcrApi"
import { PdEcrProcessFlowButton } from "./PdEcrProcessFlow"
import {
  buildGeneratedResult,
  buildHistoryResult,
  fallbackHistoryModules,
  loadActiveResult,
  loadHistoryResult,
  moduleOrder,
  saveGeneratedResult,
  saveHistoryResult,
} from "./pdEcrState"

type NewChangeForm = {
  source: string
  reason: string
  description: string
  targetCloseDate: string
}

const defaultSearchText = ""

const defaultNewChange: NewChangeForm = {
  source: "",
  reason: "",
  description: "",
  targetCloseDate: "",
}

function buildSearchInput(query: string): PdEcrInput {
  return {
    dc_no: "PD-ECR-search",
    date: new Date().toISOString().slice(0, 10),
    customer_project: "PD-ECR Platform",
    reason: query,
    change_proposal: query,
    remarks: "AI Search historical PD-ECR cases",
  }
}

function buildGenerationInput(form: NewChangeForm): PdEcrInput {
  return {
    dc_no: `PD-ECR-${Date.now()}`,
    date: new Date().toISOString().slice(0, 10),
    customer_project: "PD-ECR Platform",
    initiator: form.source,
    reason: form.reason,
    change_proposal: form.description,
    remarks: `Target Close date: ${form.targetCloseDate}`,
  }
}

function MetricCard({
  label,
  value,
  tone = "default",
}: {
  label: string
  value: string | number
  tone?: "default" | "accent"
}) {
  return (
    <div className="rounded-lg border border-stone-200 bg-white px-4 py-3 text-center">
      <p
        className={
          tone === "accent"
            ? "text-lg font-semibold text-amber-600"
            : "text-lg font-semibold text-stone-900"
        }
      >
        {value}
      </p>
      <p className="text-xs text-stone-500">{label}</p>
    </div>
  )
}

function WorkPanel({
  eyebrow,
  title,
  icon,
  children,
}: {
  eyebrow: string
  title: string
  icon: ReactNode
  children: ReactNode
}) {
  return (
    <section className="rounded-lg border border-stone-200 bg-white shadow-sm">
      <header className="flex items-center gap-3 border-b border-stone-200 px-5 py-4">
        <div className="flex size-10 items-center justify-center rounded-lg bg-stone-100 text-stone-700">
          {icon}
        </div>
        <div>
          <p className="text-xs font-semibold uppercase tracking-wide text-stone-500">
            {eyebrow}
          </p>
          <h2 className="text-xl font-semibold tracking-normal text-stone-900">
            {title}
          </h2>
        </div>
      </header>
      <div className="p-5">{children}</div>
    </section>
  )
}

function FormField({
  label,
  value,
  onChange,
}: {
  label: string
  value: string
  onChange: (value: string) => void
}) {
  const inputId = useId()

  return (
    <label className="space-y-2" htmlFor={inputId}>
      <span className="text-sm font-semibold text-stone-700">{label}</span>
      <Input
        id={inputId}
        aria-label={label}
        value={value}
        onChange={(event) => onChange(event.target.value)}
        className="h-10 border-stone-300 bg-white text-stone-900 shadow-none"
      />
    </label>
  )
}

export function PdEcrPlatform() {
  const navigate = useNavigate()
  const [searchText, setSearchText] = useState(defaultSearchText)
  const [newChange, setNewChange] = useState(defaultNewChange)
  const [relatedCasesCount, setRelatedCasesCount] = useState(
    () => {
      const activeResult = loadActiveResult()
      const historyResult = loadHistoryResult()
      return activeResult.relatedCases.length || historyResult.relatedCases.length
    },
  )
  const [modulesCount] = useState(
    () => loadActiveResult().modules.length || moduleOrder.length,
  )

  const historyMutation = useMutation({
    mutationFn: () => searchPdEcrHistory(buildSearchInput(searchText)),
    onSuccess: (response) => {
      const result = buildHistoryResult(response)
      saveHistoryResult(result)
      setRelatedCasesCount(result.relatedCases.length)
      navigate({ to: "/pd-ecr/cases", search: { view: "similar" } })
    },
    onError: () => {
      const fallback = {
        source: "history" as const,
        relatedCases: [],
        caseRows: [],
        modules: fallbackHistoryModules,
      }
      saveHistoryResult(fallback)
      setRelatedCasesCount(0)
      navigate({ to: "/pd-ecr/cases", search: { view: "similar" } })
    },
  })

  const generateMutation = useMutation({
    mutationFn: () => generatePdEcrReport(buildGenerationInput(newChange)),
    onSuccess: (response) => {
      const result = buildGeneratedResult(response)
      saveGeneratedResult(result)
      setRelatedCasesCount(result.relatedCases.length)

      // Create DB case in background (non-blocking)
      const caseNo = response.draft_id || `PD-ECR-${Date.now()}`
      createPdEcrCase({
        case_no: caseNo,
        title: newChange.description || "New PD-ECR Change Request",
        status: "draft",
        source_type: "ai_generated",
        dc_no: `PD-ECR-${Date.now()}`,
        initiator: newChange.source || "AI Generated",
        customer_project: "PD-ECR Platform",
        target_close_date: newChange.targetCloseDate || undefined,
        change_type: "Engineering Change",
      }).catch(() => {
        // Case creation is non-blocking — draft is already saved locally
      })

      navigate({ to: "/pd-ecr/content/$moduleId", params: { moduleId: "change-description" } })
    },
    onError: () => {
      const result = buildGeneratedResult({
        message: "fallback",
        modules: undefined,
      })
      saveGeneratedResult(result)
      setRelatedCasesCount(result.relatedCases.length)
      navigate({ to: "/pd-ecr/content/$moduleId", params: { moduleId: "change-description" } })
    },
  })

  const updateNewChange = (key: keyof NewChangeForm, value: string) => {
    setNewChange((current) => ({ ...current, [key]: value }))
  }

  return (
    <div className="h-[calc(100vh-7rem)] overflow-hidden bg-stone-50 text-stone-900">
      <div className="flex h-full w-full min-w-0 flex-col gap-4">
        <header className="shrink-0 rounded-lg border border-stone-200 bg-white px-5 py-4 shadow-sm">
          <div className="flex flex-col justify-between gap-4 lg:flex-row lg:items-center">
            <div>
              <div className="flex flex-wrap items-center gap-3">
                <h1 className="text-3xl font-semibold tracking-normal text-stone-900">
                  PD-ECR Platform
                </h1>
                <span className="inline-flex items-center rounded-full border border-amber-200 bg-amber-50 px-3 py-1 text-xs font-semibold text-amber-700">
                  AI + Knowledge Base
                </span>
              </div>
              {/* <p className="mt-1 text-sm text-stone-500">
                {user?.full_name || "Fan Xiaofeng"} · RBCD/ETC6 · Engineering
                change workflow
              </p> */}
            </div>
            <div className="grid grid-cols-3 gap-3">
              <MetricCard label="Related cases" value={relatedCasesCount} />
              <MetricCard label="Modules" value={modulesCount} />
              <MetricCard label="Status" value="Ready" tone="accent" />
            </div>
          </div>
        </header>

        <main className="grid min-h-0 flex-1 gap-4 overflow-y-auto xl:grid-cols-[1.05fr_.95fr]">
          <WorkPanel
            eyebrow="AI Search"
            title="历史数据检索"
            icon={<Database className="size-5" />}
          >
            <div className="space-y-4">
              <label className="space-y-2">
                <span className="text-sm font-semibold text-stone-700">
                  AI Search
                </span>
                <textarea
                  aria-label="AI Search"
                  value={searchText}
                  onChange={(event) => setSearchText(event.target.value)}
                  placeholder="输入变更原因、变更描述等关键词进行模糊搜索..."
                  className="min-h-24 w-full resize-none rounded-lg border border-stone-300 bg-white px-4 py-3 text-base leading-7 text-stone-900 shadow-none outline-none placeholder:text-stone-400 focus:border-amber-500 focus:ring-2 focus:ring-amber-100"
                />
              </label>

              <div className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-amber-100 bg-amber-50 px-4 py-3">
                <p className="text-sm text-amber-800">
                  点击 Run 后进入数据库相似 CASE 列表页。
                </p>
                <Button
                  type="button"
                  onClick={() => historyMutation.mutate()}
                  disabled={historyMutation.isPending}
                  className="h-11 bg-stone-800 px-6 text-white hover:bg-stone-700"
                >
                  <Search className="size-4" />
                  {historyMutation.isPending ? "Running" : "Run"}
                </Button>
              </div>
            </div>
          </WorkPanel>

          <WorkPanel
            eyebrow="New creation"
            title="新建变更"
            icon={<Sparkles className="size-5" />}
          >
            <div className="grid gap-3 sm:grid-cols-2">
              <FormField
                label="变更来源"
                value={newChange.source}
                onChange={(value) => updateNewChange("source", value)}
              />
              <FormField
                label="变更背景原因"
                value={newChange.reason}
                onChange={(value) => updateNewChange("reason", value)}
              />
              <FormField
                label="变更描述"
                value={newChange.description}
                onChange={(value) => updateNewChange("description", value)}
              />
              <FormField
                label="Target Close date"
                value={newChange.targetCloseDate}
                onChange={(value) => updateNewChange("targetCloseDate", value)}
              />
            </div>

            <div className="mt-3 flex flex-col justify-between gap-3 rounded-lg border border-stone-200 bg-stone-50 px-4 py-3 lg:flex-row lg:items-center">
              <div className="flex items-start gap-3">
                <CalendarClock className="mt-0.5 size-5 text-amber-600" />
                <div>
                  <p className="text-sm font-semibold text-stone-800">
                    AI 一键生成每页内容
                  </p>
                  <p className="mt-1 text-sm leading-5 text-stone-500">
                    生成后直接进入变更描述页面，可继续填写完整报告字段。
                  </p>
                </div>
              </div>
              <div className="flex shrink-0 flex-wrap gap-2">
                <Button
                  type="button"
                  variant="outline"
                  className="h-10 bg-white px-5"
                  onClick={() => navigate({ to: "/pd-ecr/new" })}
                >
                  Open workflow
                </Button>
                <Button
                  type="button"
                  onClick={() => generateMutation.mutate()}
                  disabled={generateMutation.isPending}
                  className="h-10 shrink-0 bg-amber-600 px-5 text-white hover:bg-amber-700"
                >
                  <Sparkles className="size-4" />
                  {generateMutation.isPending ? "AI 生成中" : "AI 一键生成"}
                </Button>
              </div>
            </div>
          </WorkPanel>
        </main>

        <footer className="shrink-0 flex flex-wrap items-center gap-3 pb-1">
          <Button
            variant="outline"
            className="bg-white"
            onClick={() => navigate({ to: "/pd-ecr/dashboard" })}
          >
            <FolderKanban className="size-4" />
            Case Dashboard
          </Button>
          <Button
            variant="outline"
            className="bg-white"
            onClick={() => navigate({ to: "/pd-ecr/cases", search: { view: "all" } })}
          >
            All Pd-ECR list
          </Button>
          <PdEcrProcessFlowButton />
        </footer>
      </div>
    </div>
  )
}
