import { useMutation } from "@tanstack/react-query"
import { useNavigate } from "@tanstack/react-router"
import {
  ArrowRight,
  Database,
  FolderKanban,
  Search,
  Sparkles,
  Upload,
} from "lucide-react"
import { type ReactNode, useEffect, useId, useRef, useState } from "react"

import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import {
  createPdEcrCase,
  generatePdEcrReport,
  type PdEcrInput,
  type PdEcrModule,
  searchPdEcrHistory,
  uploadAndStageDocument,
} from "@/lib/pdEcrApi"
import { departmentOptions } from "./PdEcrModuleDetail"
import { PdEcrProcessFlowButton } from "./PdEcrProcessFlow"
import {
  buildGeneratedResult,
  buildHistoryResult,
  CHANGE_SOURCE_OPTIONS,
  fallbackHistoryModules,
  loadActiveResult,
  loadGeneratedResult,
  loadHistoryResult,
  moduleOrder,
  saveGeneratedResult,
  saveHistoryResult,
} from "./pdEcrState"

type NewChangeForm = {
  product: string
  customer: string
  source: string
  sourceNote: string
  reason: string
  department: string
  initiator: string
  date: string
  partNumber: string
  description: string
  targetCloseDate: string
  departments: string[]
}

const defaultSearchText = ""

const defaultNewChange: NewChangeForm = {
  product: "",
  customer: "",
  source: "",
  sourceNote: "",
  reason: "",
  department: "",
  initiator: "",
  date: new Date().toISOString().slice(0, 10),
  partNumber: "",
  description: "",
  targetCloseDate: "",
  departments: [],
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
    date: form.date || new Date().toISOString().slice(0, 10),
    customer_project: form.customer || "PD-ECR Platform",
    product_no: form.product,
    part_no: form.partNumber,
    component_no: form.partNumber,
    initiator: form.initiator || form.source,
    change_source: form.source,
    reason: form.reason,
    change_description: form.description,
    target_close_date: form.targetCloseDate,
    remarks: [
      `Source: ${form.source}`,
      `Source notes: ${form.sourceNote}`,
      `Department: ${form.department}`,
      `Affected departments: ${form.departments.join(", ")}`,
      `Target Close date: ${form.targetCloseDate}`,
    ]
      .filter(Boolean)
      .join("\n"),
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

function parseSourceNotes(raw: string): Record<string, string> {
  if (!raw) return {}
  try {
    const obj = JSON.parse(raw)
    return typeof obj === "object" && obj !== null && !Array.isArray(obj)
      ? obj as Record<string, string>
      : {}
  } catch {
    // Legacy: plain text stored as single note → assign to first source
    return {}
  }
}

function serializeSourceNotes(notes: Record<string, string>): string {
  const filtered: Record<string, string> = {}
  for (const [k, v] of Object.entries(notes)) {
    if (v.trim()) filtered[k] = v.trim()
  }
  return Object.keys(filtered).length > 0 ? JSON.stringify(filtered) : ""
}

function SourceMultiSelect({
  selected,
  onChange,
}: {
  selected: string
  onChange: (value: string) => void
}) {
  const [open, setOpen] = useState(false)
  const containerRef = useRef<HTMLDivElement>(null)

  // Close on outside click
  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setOpen(false)
      }
    }
    document.addEventListener("mousedown", handler)
    return () => document.removeEventListener("mousedown", handler)
  })

  const selectedSet = new Set(
    selected
      .split(",")
      .map((s) => s.trim())
      .filter(Boolean),
  )

  const toggle = (value: string) => {
    const next = selectedSet.has(value)
      ? [...selectedSet].filter((s) => s !== value)
      : [...selectedSet, value]
    onChange(next.join(", "))
  }

  const selectedList = [...selectedSet]

  return (
    <div ref={containerRef} className="relative">
      <button
        type="button"
        onClick={() => setOpen(!open)}
        className={`flex w-full items-center justify-between rounded-lg border bg-white px-3 py-2 text-left text-sm shadow-none transition ${
          open
            ? "border-amber-500 ring-2 ring-amber-100"
            : "border-stone-300"
        }`}
      >
        <span className={selectedList.length > 0 ? "text-stone-900 flex-1" : "text-stone-400"}>
          {selectedList.length > 0
            ? selectedList.map((v) => (
                <span key={v} className="block text-sm leading-6">
                  {CHANGE_SOURCE_OPTIONS.find((o) => o.value === v)?.label || v}
                </span>
              ))
            : "请选择变更来源..."}
        </span>
        <span className="ml-2 shrink-0 self-start text-stone-400">▼</span>
      </button>
      {open && (
        <div className="absolute z-20 mt-1 w-full rounded-lg border border-stone-200 bg-white py-1 shadow-lg">
          {CHANGE_SOURCE_OPTIONS.map((opt) => (
            <label
              key={opt.value}
              className="flex cursor-pointer items-center gap-2 px-3 py-2 text-sm hover:bg-amber-50"
            >
              <input
                type="checkbox"
                checked={selectedSet.has(opt.value)}
                onChange={() => toggle(opt.value)}
                className="accent-amber-600"
              />
              {opt.label}
            </label>
          ))}
        </div>
      )}
    </div>
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

  const handleNextStep = () => {
    // 1. Write form data directly to change-description localStorage draft
    //    so ChangeDescriptionView picks it up immediately with zero transformation
    const draftData = {
      source: newChange.source,
      reason: newChange.reason,
      department: newChange.department,
      initiator: newChange.initiator,
      date: newChange.date,
      product: newChange.product,
      customer: newChange.customer,
      partNumber: newChange.partNumber,
      title: newChange.description || "New PD-ECR Change Request",
      changeSummary: newChange.description,
      notChange: "",
      departments: newChange.departments,
    }
    // Use a stable record id so the draft key is predictable
    const recordId = `pd-ecr-${Date.now()}`
    localStorage.setItem(
      `pd-ecr-change-description-draft:${recordId}:change-description`,
      JSON.stringify(draftData),
    )

    // 2. Also save as generated result so the content page loads
    const seedData: Record<string, unknown> = {
      source: newChange.source,
      change_source: newChange.source,
      reason: newChange.reason,
      change_reason: newChange.reason,
      product_no: newChange.product,
      customer: newChange.customer,
      customer_project: newChange.customer,
      component_no: newChange.partNumber,
      part_no: newChange.partNumber,
      initiator: newChange.initiator,
      department: newChange.department,
      date: newChange.date,
      change_proposal: newChange.description,
      affected_departments: newChange.departments.join(", "),
      target_close_date: newChange.targetCloseDate,
    }
    const seedModule: PdEcrModule = {
      id: "change-description",
      title: "Change Description",
      summary: newChange.description || "",
      data: seedData,
    }
    const seedResult = buildGeneratedResult({
      message: "seed",
      draft_id: recordId,
      modules: [seedModule],
      url: undefined,
      approval_lead_days: 12,
    })
    // Ensure recordId is used as the draft lookup key by getActiveRecordId
    seedResult.relatedCases = [recordId, ...seedResult.relatedCases]
    saveGeneratedResult(seedResult)
    setRelatedCasesCount(seedResult.relatedCases.length)

    // 3. Navigate immediately — ChangeDescriptionView loads the draft
    navigate({ to: "/pd-ecr/content/$moduleId", params: { moduleId: "change-description" } })

    // 4. Fire AI generation in background — updates modules when done
    generateMutation.mutate()
  }

  const generateMutation = useMutation({
    mutationFn: () => generatePdEcrReport(buildGenerationInput(newChange)),
    onSuccess: (response) => {
      const result = buildGeneratedResult(response)
      // Preserve pre-filled change-description data — user input takes priority over AI markdown
      try {
        const prev = loadGeneratedResult()
        const prevCd = prev?.modules?.find((m: { id: string }) => m.id === "change-description")
        if (prevCd?.data) {
          const aiCd = result.modules.find((m) => m.id === "change-description")
          if (aiCd) {
            aiCd.data = { ...aiCd.data, ...prevCd.data }
          }
        }
      } catch { /* best effort */ }
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
        initiator: newChange.initiator || newChange.source || "AI Generated",
        customer_project: newChange.customer || "PD-ECR Platform",
        product_no: newChange.product || undefined,
        part_no: newChange.partNumber || undefined,
        target_close_date: newChange.targetCloseDate || undefined,
        change_type: "Engineering Change",
      }).catch(() => {
        // Case creation is non-blocking — draft is already saved locally
      })
    },
    onError: () => {
      const result = buildGeneratedResult({
        message: "fallback",
        modules: undefined,
      })
      saveGeneratedResult(result)
      setRelatedCasesCount(result.relatedCases.length)
    },
  })

  const updateNewChange = (key: keyof NewChangeForm, value: string) => {
    setNewChange((current) => ({ ...current, [key]: value }))
  }

  const toggleDepartment = (dept: string, checked: boolean) => {
    setNewChange((current) => ({
      ...current,
      departments: checked
        ? [...current.departments, dept]
        : current.departments.filter((d) => d !== dept),
    }))
  }

  const fileInputRef = useRef<HTMLInputElement>(null)
  const [uploadStatus, setUploadStatus] = useState<string | null>(null)
  const [isDragging, setIsDragging] = useState(false)

  const uploadMutation = useMutation({
    mutationFn: (file: File) => uploadAndStageDocument(file),
    onSuccess: (staged) => {
      setUploadStatus(`✅ ${staged.original_filename} 解析完成，进入审核`)
      // Navigate to the review page instead of auto-filling the form
      navigate({
        to: "/pd-ecr/documents/$docId",
        params: { docId: staged.id },
      })
    },
    onError: (error: Error) => {
      setUploadStatus(`❌ 上传失败: ${error.message}`)
    },
  })

  const handleFileDrop = (files: FileList | null) => {
    const file = files?.[0]
    if (!file) return
    const suffix = file.name.split(".").pop()?.toLowerCase()
    if (!suffix || !["xlsx", "xls", "xlsm", "pdf", "docx", "doc"].includes(suffix)) {
      setUploadStatus("❌ 仅支持 .xlsx / .xls / .pdf / .docx 文件")
      return
    }
    setUploadStatus(`⏳ 正在解析 ${file.name}...`)
    uploadMutation.mutate(file)
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

        <main className="grid min-h-0 flex-1 gap-4 overflow-y-auto xl:grid-cols-2">
          {/* ═══ LEFT COLUMN — Upload + AI Search ═══ */}
          <div className="flex min-h-0 flex-col gap-4">
            {/* ── File Upload Panel ── */}
            <WorkPanel
              eyebrow="Upload"
              title="文件上传"
              icon={<Upload className="size-5" />}
            >
              <label
                className={`relative block rounded-lg border-2 border-dashed p-4 text-center transition cursor-pointer ${
                  isDragging
                    ? "border-amber-500 bg-amber-50"
                    : "border-stone-300 bg-stone-50 hover:border-amber-400 hover:bg-amber-50/50"
                }`}
                onDragOver={(e) => { e.preventDefault(); setIsDragging(true) }}
                onDragLeave={(e) => { e.preventDefault(); setIsDragging(false) }}
                onDrop={(e) => { e.preventDefault(); setIsDragging(false); handleFileDrop(e.dataTransfer.files) }}
              >
                <input
                  ref={fileInputRef}
                  type="file"
                  accept=".xlsx,.xls,.xlsm,.pdf,.docx,.doc"
                  className="absolute inset-0 cursor-pointer opacity-0"
                  onChange={(e) => handleFileDrop(e.target.files)}
                />
                {uploadMutation.isPending ? (
                  <div className="flex items-center justify-center gap-2 text-amber-700">
                    <span className="inline-block size-4 animate-spin rounded-full border-2 border-amber-600 border-t-transparent" />
                    <span className="text-sm font-semibold">解析文件中...</span>
                  </div>
                ) : (
                  <div className="flex items-center justify-center gap-3 text-stone-500">
                    <Upload className="size-5" />
                    <span className="text-sm">
                      拖拽 Excel / PDF 文件到此处，或点击上传
                    </span>
                  </div>
                )}
              </label>

              {uploadStatus && (
                <p
                  className={`mt-2 text-xs ${
                    uploadStatus.startsWith("✅")
                      ? "text-green-700"
                      : uploadStatus.startsWith("❌")
                        ? "text-red-600"
                        : "text-amber-700"
                  }`}
                >
                  {uploadStatus}
                </p>
              )}
            </WorkPanel>

            {/* ── AI Search Panel ── */}
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
          </div>

          {/* ═══ RIGHT COLUMN — New Change Form ═══ */}
          <WorkPanel
            eyebrow="New creation"
            title="新建变更"
            icon={<Sparkles className="size-5" />}
          >
            {/* 产品 & 客户 — 最优先 */}
            <div className="grid gap-3 sm:grid-cols-2">
              <FormField
                label="产品"
                value={newChange.product}
                onChange={(value) => updateNewChange("product", value)}
              />
              <FormField
                label="客户"
                value={newChange.customer}
                onChange={(value) => updateNewChange("customer", value)}
              />
            </div>

            {/* 变更来源 — 多选 + 一行一个 + 各自备注 */}
            <div className="mt-3 space-y-2">
              <span className="text-sm font-semibold text-stone-700">
                变更来源
              </span>
              <SourceMultiSelect
                selected={newChange.source}
                onChange={(value) => updateNewChange("source", value)}
              />
              {(() => {
                const selectedValues = newChange.source
                  .split(",")
                  .map((s) => s.trim())
                  .filter(Boolean)
                if (!selectedValues.length) return null
                const notes = parseSourceNotes(newChange.sourceNote)
                return (
                  <div className="mt-2 space-y-2 rounded-lg border border-stone-200 bg-stone-50 p-3">
                    {selectedValues.map((val) => {
                      const label =
                        CHANGE_SOURCE_OPTIONS.find((o) => o.value === val)?.label || val
                      return (
                        <div key={val} className="flex items-center gap-3">
                          <span className="w-40 shrink-0 text-sm font-medium text-stone-700 truncate">
                            {label}
                          </span>
                          <input
                            type="text"
                            placeholder="备注..."
                            value={notes[val] || ""}
                            onChange={(e) => {
                              const next = { ...notes, [val]: e.target.value }
                              updateNewChange("sourceNote", serializeSourceNotes(next))
                            }}
                            className="h-9 flex-1 rounded-lg border border-stone-300 bg-white px-3 text-sm text-stone-900 shadow-none outline-none focus:border-amber-500 focus:ring-2 focus:ring-amber-100"
                          />
                        </div>
                      )
                    })}
                  </div>
                )
              })()}
            </div>
            <div className="mt-3 grid gap-3 sm:grid-cols-2">
              <FormField
                label="变更背景原因"
                value={newChange.reason}
                onChange={(value) => updateNewChange("reason", value)}
              />
              <FormField
                label="变更发起部门"
                value={newChange.department}
                onChange={(value) => updateNewChange("department", value)}
              />
              <FormField
                label="变更发起人"
                value={newChange.initiator}
                onChange={(value) => updateNewChange("initiator", value)}
              />
              <FormField
                label="变更发起日期"
                value={newChange.date}
                onChange={(value) => updateNewChange("date", value)}
              />
              <FormField
                label="零部件号"
                value={newChange.partNumber}
                onChange={(value) => updateNewChange("partNumber", value)}
              />
              <FormField
                label="变更描述"
                value={newChange.description}
                onChange={(value) => updateNewChange("description", value)}
              />
            </div>

            {/* Target Close date & 影响的部门 */}
            <div className="mt-3 grid gap-3 sm:grid-cols-2">
              <label className="space-y-2">
                <span className="text-sm font-semibold text-stone-700">
                  Target Close date
                </span>
                <input
                  type="date"
                  value={newChange.targetCloseDate}
                  onChange={(e) => updateNewChange("targetCloseDate", e.target.value)}
                  className="h-10 w-full rounded-lg border border-stone-300 bg-white px-3 text-sm text-stone-900 shadow-none outline-none focus:border-amber-500 focus:ring-2 focus:ring-amber-100"
                />
              </label>
            </div>

            {/* 影响的部门 */}
            <fieldset className="mt-4 rounded-lg border border-stone-200 bg-stone-50 p-4">
              <legend className="px-2 text-sm font-semibold text-stone-700">
                影响的部门有
              </legend>
              <div className="mt-2 flex flex-wrap gap-x-6 gap-y-2 text-sm">
                {departmentOptions.map((dept) => (
                  <label key={dept} className="flex items-center gap-2">
                    <input
                      type="checkbox"
                      checked={newChange.departments.includes(dept)}
                      onChange={(event) =>
                        toggleDepartment(dept, event.target.checked)
                      }
                      className="accent-amber-600"
                    />
                    {dept}
                  </label>
                ))}
              </div>
            </fieldset>

            <div className="mt-4 flex items-center justify-end gap-3 rounded-lg border border-stone-200 bg-stone-50 px-4 py-3">
              <span className="text-sm text-stone-500">
                填写完成后进入变更描述模块，AI 将根据历史相似案例辅助填写
              </span>
              <Button
                type="button"
                onClick={handleNextStep}
                disabled={generateMutation.isPending}
                className="h-10 shrink-0 bg-amber-600 px-6 text-white hover:bg-amber-700"
              >
                {generateMutation.isPending ? "生成中..." : "下一步"}
                <ArrowRight className="size-4" />
              </Button>
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
