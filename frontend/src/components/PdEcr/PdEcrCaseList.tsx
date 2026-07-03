import { useNavigate } from "@tanstack/react-router"
import {
  ArrowLeft,
  ArrowUpDown,
  Database,
  ExternalLink,
  FileText,
  Filter,
  Home,
  ListFilter,
  Printer,
  Share2,
  Trash2,
  Upload,
  X,
} from "lucide-react"
import { useCallback, useEffect, useMemo, useState } from "react"

import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import {
  deletePdEcrCase,
  deletePdEcrSourceDocument,
  getPdEcrCase,
  importHistoricalPdEcrCases,
  listPdEcrCases,
} from "@/lib/pdEcrApi"
import { PdEcrProcessFlowButton } from "./PdEcrProcessFlow"
import {
  downloadText,
  exportPdEcrOnePage,
  type PdEcrCaseSummary,
} from "./pdEcrExport"
import {
  loadHistoryResult,
  fallbackHistoryModules,
  normalizePdEcrCaseRows,
  normalizeModules,
  resolveRowPdfUrl,
  hasPdfForRow,
  type PdEcrPdEcrCaseRow,
  type PdEcrStoredResult,
  saveActiveResult,
} from "./pdEcrState"
import { PdEcrCaseStatusFlow } from "./PdEcrCaseStatusFlow"
import { getPdEcrCaseWorkbenchState } from "./PdEcrWorkflowRules"

const API_BASE_URL = import.meta.env.VITE_API_URL || "http://localhost:8000"

type PdEcrCaseRow = PdEcrPdEcrCaseRow
type PdEcrCaseListView = "all" | "similar"

type SearchField =
  | "all"
  | "id"
  | "dcNo"
  | "createDate"
  | "customer"
  | "reasonForChange"
  | "changeType"
  | "sampleType"

type SortKey = keyof Pick<
  PdEcrCaseRow,
  "id" | "createDate" | "dcNo" | "reasonForChange" | "changeType" | "sampleType" | "customer" | "similarity"
>

type SortState = {
  key: SortKey
  direction: "asc" | "desc"
}

type FilterOption = {
  label: string
  value: SearchField
}

const filterOptions: FilterOption[] = [
  { label: "DC No", value: "dcNo" },
  { label: "Date", value: "createDate" },
  { label: "Customer", value: "customer" },
  { label: "Reason for Change", value: "reasonForChange" },
  { label: "Change type", value: "changeType" },
  { label: "Sample type", value: "sampleType" },
]

function buildPdEcrCaseRows(result: PdEcrStoredResult): PdEcrCaseRow[] {
  if (result.caseRows?.length) {
    return result.caseRows
  }

  if (result.relatedCases?.length) {
    return result.relatedCases.map((caseNo) => ({
      id: caseNo,
      createDate: "-",
      productClass: "-",
      from: "-",
      sampleType: "-",
      initiator: "-",
      customer: "-",
      project: "-",
      partNumber: "-",
      reasonForChange: "-",
      dept: "-",
      link: "Open modules",
    }))
  }

  return []
}

function searchableText(row: PdEcrCaseRow) {
  return [
    row.id,
    row.dcNo,
    row.createDate,
    row.reasonForChange,
    row.changeType,
    row.sampleType,
    row.customer,
  ].join(" ")
}

function fieldLabel(field: SearchField) {
  if (field === "all") return "case number, dc no, date, customer, part, change type, sample type"
  return (
    filterOptions
      .find((option) => option.value === field)
      ?.label.toLowerCase() || "case number"
  )
}

function displayFieldLabel(field: SearchField) {
  if (field === "all") return "All fields"
  return (
    filterOptions.find((option) => option.value === field)?.label ||
    "PD-ECR Nr."
  )
}

function filterRows(rows: PdEcrCaseRow[], field: SearchField, query: string) {
  const normalizedQuery = query.trim().toLowerCase()
  if (!normalizedQuery) return rows

  return rows.filter((row) => {
    const value = field === "all" ? searchableText(row) : (row[field] ?? "")
    return value.toLowerCase().includes(normalizedQuery)
  })
}

function sortRows(rows: PdEcrCaseRow[], sortState: SortState | null) {
  if (!sortState) return rows

  return [...rows].sort((left, right) => {
    const leftVal = left[sortState.key] ?? ""
    const rightVal = right[sortState.key] ?? ""

    if (typeof leftVal === "number" && typeof rightVal === "number") {
      return sortState.direction === "asc" ? leftVal - rightVal : rightVal - leftVal
    }

    const result = String(leftVal).toLowerCase().localeCompare(String(rightVal).toLowerCase())
    return sortState.direction === "asc" ? result : -result
  })
}

function escapeCsv(value: string | number) {
  return `"${String(value).replace(/"/g, '""')}"`
}

function buildCsv(rows: PdEcrCaseRow[]) {
  const headers = [
    "PD-ECR Nr.",
    "DC No",
    "Date",
    "Customer",
    "Reason for Change",
    "Change Type",
    "Sample Type",
    "Score",
  ]
  const body = rows.map((row) =>
    [
      row.id,
      row.dcNo ?? "-",
      row.createDate,
      row.customer,
      row.reasonForChange ?? "-",
      row.changeType ?? "-",
      row.sampleType ?? "-",
      typeof row.similarity === "number" ? row.similarity : "-",
    ]
      .map(escapeCsv)
      .join(","),
  )

  return [headers.map(escapeCsv).join(","), ...body].join("\n")
}

function errorMessage(error: unknown) {
  if (!error || typeof error !== "object") return "Request failed"
  const record = error as {
    message?: string
    response?: { status?: number; data?: unknown }
  }
  const detail =
    record.response?.data && typeof record.response.data === "object"
      ? (record.response.data as { detail?: unknown }).detail
      : undefined
  return [
    record.response?.status ? `HTTP ${record.response.status}` : "",
    typeof detail === "string" ? detail : record.message || "Request failed",
  ]
    .filter(Boolean)
    .join(": ")
}

function deleteTargetId(row: PdEcrCaseRow) {
  return row.backendCaseId || ""
}

function sourceDeleteTargetId(row: PdEcrCaseRow) {
  return row.sourceDocumentId || ""
}

function ActionRail({
  onShowAll,
  onNew,
  onEdit,
  onShare,
  onPrint,
  hasSelection,
}: {
  onShowAll: () => void
  onNew: () => void
  onEdit: () => void
  onShare: () => void
  onPrint: () => void
  hasSelection: boolean
}) {
  const actions = [
    { label: "Show all", icon: ListFilter, onClick: onShowAll },
    { label: "New PD-ECR", icon: FileText, onClick: onNew },
    {
      label: "Edit PD-ECR",
      icon: Database,
      onClick: onEdit,
      requiresSelection: true,
    },
    {
      label: "Share PD-ECR",
      icon: Share2,
      onClick: onShare,
      requiresSelection: true,
    },
    {
      label: "Print one page",
      icon: Printer,
      onClick: onPrint,
      requiresSelection: true,
    },
  ]

  return (
    <aside className="flex gap-2 lg:w-36 lg:flex-col">
      {actions.map(({ label, icon: Icon, onClick, requiresSelection }) => (
        <Button
          key={label}
          variant="outline"
          className="h-10 justify-start bg-white text-sm lg:w-full hover:border-blue-300 hover:bg-blue-50"
          type="button"
          onClick={onClick}
          disabled={requiresSelection && !hasSelection}
        >
          <Icon className="size-4" />
          {label}
        </Button>
      ))}
    </aside>
  )
}

function FilterPanel({
  field,
  onSelect,
}: {
  field: SearchField
  onSelect: (field: SearchField) => void
}) {
  return (
    <aside className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm lg:w-44">
      <div className="flex items-center gap-2 text-sm font-semibold text-slate-800">
        <Filter className="size-4 text-blue-600" />
        Filters
      </div>
      <div className="mt-4 grid gap-2">
        {filterOptions.map((filter) => (
          <button
            type="button"
            key={filter.value}
            onClick={() => onSelect(filter.value)}
            className={
              field === filter.value
                ? "rounded-md border border-blue-300 bg-blue-50 px-3 py-2 text-left text-sm font-semibold text-blue-700"
                : "rounded-md border border-slate-200 bg-slate-50 px-3 py-2 text-left text-sm font-medium text-slate-700 transition hover:border-blue-300 hover:bg-blue-50 hover:text-blue-700"
            }
          >
            {filter.label}
          </button>
        ))}
      </div>
    </aside>
  )
}

export function PdEcrCaseList({ view = "all" }: { view?: PdEcrCaseListView }) {
  const navigate = useNavigate()
  const historyResult = useMemo(() => loadHistoryResult(), [])
  const isAllListView = view === "all"
  const [field, setField] = useState<SearchField>("all")
  const [pendingQuery, setPendingQuery] = useState("")
  const [appliedQuery, setAppliedQuery] = useState("")
  const [selectedIds, setSelectedIds] = useState<string[]>([])
  const [sortState, setSortState] = useState<SortState | null>(null)
  const [status, setStatus] = useState(
    isAllListView
      ? "Loading all real PD-ECR cases..."
      : `Loaded ${historyResult.relatedCases.length} similar PD-ECR case(s).`,
  )
  const [isImporting, setIsImporting] = useState(false)
  const [allRows, setAllRows] = useState<PdEcrCaseRow[]>(() =>
    isAllListView ? [] : buildPdEcrCaseRows(historyResult),
  )
  const [isDeleting, setIsDeleting] = useState(false)
  const [deleteNotice, setDeleteNotice] = useState<{
    kind: "success" | "error"
    message: string
  } | null>(null)
  const rows = allRows
  const filteredRows = useMemo(
    () => sortRows(filterRows(rows, field, appliedQuery), sortState),
    [rows, field, appliedQuery, sortState],
  )
  const selectedRows = rows.filter((row) => selectedIds.includes(row.id))
  const targetRows = selectedRows.length ? selectedRows : filteredRows

  const buildVisibleResult = useCallback(
    (currentRows: PdEcrCaseRow[] = rows): PdEcrStoredResult => ({
      source: "history",
      relatedCases: currentRows.map((item) => item.id),
      caseRows: currentRows,
      currentCase: currentRows[0],
      approvalSuggestions: historyResult.approvalSuggestions,
      modules: historyResult.modules,
    }),
    [historyResult.approvalSuggestions, historyResult.modules, rows],
  )

  const loadAllRealCases = useCallback(async () => {
    setStatus("Loading all real PD-ECR cases...")

    try {
      const response = await listPdEcrCases()
      const realRows = normalizePdEcrCaseRows(response.cases ?? [])

      setAllRows(realRows)
      setStatus(
        realRows.length
          ? `Loaded ${realRows.length} real PD-ECR case(s).`
          : "No PD-ECR cases found.",
      )
    } catch {
      setAllRows([])
      setStatus("Backend not available. Please try again later.")
    }
  }, [])

  useEffect(() => {
    let ignore = false

    async function loadAllCases() {
      if (!isAllListView) {
        const similarRows = buildPdEcrCaseRows(historyResult)
        setAllRows(similarRows)
        setStatus(`Loaded ${similarRows.length} similar PD-ECR case(s).`)
        return
      }

      try {
        const response = await listPdEcrCases()
        const realRows = normalizePdEcrCaseRows(response.cases ?? [])

        if (ignore) return

        setAllRows(realRows)
        setStatus(
          realRows.length
            ? `Loaded ${realRows.length} real PD-ECR case(s).`
            : "No PD-ECR cases found.",
        )
      } catch {
        if (ignore) return
        setAllRows([])
        setStatus("Backend not available. Please try again later.")
      }
    }

    loadAllCases()

    return () => {
      ignore = true
    }
  }, [historyResult, isAllListView])

  const openPdf = (row: PdEcrCaseRow) => {
    const url = resolveRowPdfUrl(row, API_BASE_URL)
    if (url) {
      window.open(url, "_blank", "noopener,noreferrer")
      setStatus(`Opening PDF for ${row.id}...`)
    }
  }

  const openCase = async (row: PdEcrCaseRow) => {
    const caseNo = row.sourceFile || row.id
    setStatus(`Opening modules for ${row.id}...`)

    try {
      const detail = await getPdEcrCase(row.backendCaseId || row.id)
      const activeResult = {
        source: "history" as const,
        relatedCases: rows.map((item) => item.id),
        caseRows: rows,
        currentCase: row,
        modules: normalizeModules(
          detail.modules.map((module) => ({
            id: module.module_id,
            title: module.title,
            summary:
              (module as unknown as { summary?: string }).summary ||
              module.content_md ||
              undefined,
            description:
              (module as unknown as { content?: string }).content ||
              module.content_md ||
              undefined,
            data: {
              ...(module.content_json || {}),
              content:
                (module as unknown as { content?: string }).content ||
                module.content_md ||
                "",
              source_cases: module.source_cases || [],
              source_files: module.source_files || [],
              warnings:
                (module as unknown as { warnings?: string[] }).warnings || [],
              needs_human_input:
                (module as unknown as { needs_human_input?: boolean })
                  .needs_human_input || false,
              version: module.version || 1,
              status: module.status,
            },
            source_cases: module.source_cases || [],
            source_files: module.source_files || [],
            needs_human_input:
              (module as unknown as { needs_human_input?: boolean })
                .needs_human_input || false,
            warnings:
              (module as unknown as { warnings?: string[] }).warnings || [],
          })),
          fallbackHistoryModules,
        ),
      }

      saveActiveResult(activeResult)
      navigate({ to: "/pd-ecr/content" })
    } catch {
      try {
        const response = await fetch(
          `${API_BASE_URL}/api/v1/pd-ecr/cases/modules?case_no=${encodeURIComponent(caseNo)}`,
        )

        if (!response.ok) {
          throw new Error("Failed to load case modules")
        }

        const data = await response.json()

        const activeResult = {
          source: "history" as const,
          relatedCases: rows.map((item) => item.id),
          caseRows: rows,
          currentCase: row,
          modules: normalizeModules(data.modules, fallbackHistoryModules),
        }

        saveActiveResult(activeResult)

        navigate({
          to: "/pd-ecr/content",
        })
      } catch {
        setStatus(
          `Backend unavailable. Could not load modules for ${row.id}.`,
        )
      }
    }
  }

  const applyFilter = () => {
    const nextRows = filterRows(rows, field, pendingQuery)
    setAppliedQuery(pendingQuery)
    setSelectedIds([])
    setStatus(`Showing ${nextRows.length} matching case(s).`)
  }

  const showAll = async () => {
    navigate({ to: "/pd-ecr/cases", search: { view: "all" } })
    setField("all")
    setPendingQuery("")
    setAppliedQuery("")
    setSelectedIds([])
    setSortState(null)
    await loadAllRealCases()
  }

  const importHistoricalCases = async () => {
    setIsImporting(true)
    setStatus("Importing historical PD-ECR OCR/Markdown/JSON sources...")
    try {
      const result = await importHistoricalPdEcrCases()
      await loadAllRealCases()
      setStatus(
        `Imported ${result.created_cases} case(s), registered ${result.updated_sources} source document(s).`,
      )
    } catch {
      setStatus("Historical import failed. Check admin permission and backend logs.")
    } finally {
      setIsImporting(false)
    }
  }

  const selectField = (nextField: SearchField) => {
    setField(nextField)
    setStatus(`Filter field set to ${fieldLabel(nextField)}.`)
  }

  const toggleRow = (rowId: string, checked: boolean) => {
    setSelectedIds((current) =>
      checked ? [...current, rowId] : current.filter((id) => id !== rowId),
    )
  }

  const clearFilter = () => {
    setPendingQuery("")
    setAppliedQuery("")
    setSelectedIds([])
    setStatus("Filter cleared.")
  }

  const clearSelection = () => {
    setSelectedIds([])
    setStatus("Selection cleared.")
  }

  const toggleSort = (key: SortKey) => {
    setSortState((current) => {
      const nextState: SortState =
        current?.key === key
          ? {
              key,
              direction: current.direction === "asc" ? "desc" : "asc",
            }
          : { key, direction: "asc" }

      setStatus(
        `Sorted by ${displayFieldLabel(key as SearchField)} ${nextState.direction}.`,
      )
      return nextState
    })
  }

  const editSelected = () => {
    if (!selectedIds.length) {
      setStatus("Select one PD-ECR to edit.")
      return
    }

    const row = rows.find((item) => item.id === selectedIds[0])
    if (!row) {
      setStatus(
        "Selected PD-ECR is no longer visible. Use Show all and try again.",
      )
      return
    }

    openCase(row)
  }

  const shareSelected = async () => {
    const ids = targetRows.map((row) => row.id)
    const text = [
      `PD-ECR cases (${ids.length})`,
      ...targetRows.map(
        (row) =>
          `${row.id} | ${row.project} | ${row.reasonForChange || "-"} | ${row.sourceFile || "-"}`,
      ),
    ].join("\n")

    try {
      if (navigator.share) {
        await navigator.share({
          title: "PD-ECR cases",
          text,
          url: window.location.href,
        })
      } else {
        await navigator.clipboard?.writeText(text)
      }
      setStatus(`Shared ${ids.length} case(s).`)
    } catch {
      await navigator.clipboard?.writeText(text)
      setStatus(`Copied ${ids.length} case(s) to clipboard.`)
    }
  }

  const printSelected = () => {
    const html = exportPdEcrOnePage({
      cases: targetRows as PdEcrCaseSummary[],
      result: buildVisibleResult(targetRows),
      returnHtml: true,
    })

    const printWindow = window.open("", "_blank")
    if (!printWindow) {
      setStatus(
        "Popup blocked. Allow popups to print the selected PD-ECR cases.",
      )
      return
    }

    printWindow.document.write(html)
    printWindow.document.close()
    printWindow.focus()
    printWindow.print()
    setStatus(`Print preview opened for ${targetRows.length} case(s).`)
  }

  const deleteSelected = async () => {
    if (!selectedRows.length) {
      setStatus("Select database PD-ECR cases to delete.")
      setDeleteNotice({
        kind: "error",
        message: "Select one or more database PD-ECR cases before deleting.",
      })
      return
    }

    const deletableRows = selectedRows.filter((row) => deleteTargetId(row))
    const sourceRows = selectedRows.filter((row) => !deleteTargetId(row) && sourceDeleteTargetId(row))
    const skippedRows = selectedRows.filter((row) => !deleteTargetId(row) && !sourceDeleteTargetId(row))

    if (!deletableRows.length && !sourceRows.length) {
      const message =
        "Selected rows do not have database case IDs. They may be source/PDF knowledge rows, so use source management rather than case deletion."
      setStatus(message)
      setDeleteNotice({ kind: "error", message })
      return
    }

    const names = [...deletableRows, ...sourceRows].map((row) => row.id).join(", ")
    const confirmed = window.confirm(
      `Delete ${deletableRows.length} PD-ECR case(s) and ${sourceRows.length} source document(s)?\n\n${names}\n\nApproved, implementation, and closed cases are protected by the backend. Source document deletion removes the database source record, not the physical original file.${
        skippedRows.length
          ? `\n\n${skippedRows.length} selected row(s) will be skipped because they do not have database IDs.`
          : ""
      }`,
    )
    if (!confirmed) return

    setIsDeleting(true)
    setDeleteNotice(null)
    setStatus(`Deleting ${deletableRows.length} case(s) and ${sourceRows.length} source document(s)...`)
    const results = await Promise.allSettled(
      [
        ...deletableRows.map((row) => deletePdEcrCase(deleteTargetId(row))),
        ...sourceRows.map((row) => deletePdEcrSourceDocument(sourceDeleteTargetId(row))),
      ],
    )
    const attemptedRows = [...deletableRows, ...sourceRows]
    const deletedIds = attemptedRows
      .filter((_, index) => results[index].status === "fulfilled")
      .map((row) => row.id)
    const failures = results.filter((result) => result.status === "rejected")

    setAllRows((current) =>
      current.filter((row) => !deletedIds.includes(row.id)),
    )
    setSelectedIds((current) =>
      current.filter((id) => !deletedIds.includes(id)),
    )
    setIsDeleting(false)

    if (failures.length) {
      const firstFailure = failures[0]
      const message = `Deleted ${deletedIds.length} case(s). ${failures.length} failed${
          skippedRows.length ? `, ${skippedRows.length} skipped` : ""
        }: ${
          firstFailure.status === "rejected"
            ? errorMessage(firstFailure.reason)
            : "Unknown error"
        }`
      setStatus(message)
      setDeleteNotice({ kind: "error", message })
      if (deletedIds.length) await loadAllRealCases()
      return
    }
    await loadAllRealCases()
    const message = `Deleted ${deletedIds.length} case(s).${
      skippedRows.length ? ` Skipped ${skippedRows.length} row(s) without database IDs.` : ""
    }`
    setStatus(message)
    setDeleteNotice({ kind: "success", message })
  }

  const exportList = () => {
    downloadText(
      "pd-ecr-cases.csv",
      buildCsv(filteredRows),
      "text/csv;charset=utf-8",
    )
    setStatus(`Exported ${filteredRows.length} visible case(s).`)
  }

  const exportOnePage = () => {
    exportPdEcrOnePage({
      cases: targetRows as PdEcrCaseSummary[],
      result: buildVisibleResult(targetRows),
    })
    setStatus(`Exported one-page report for ${targetRows.length} case(s).`)
  }

  return (
    <div className="min-h-[calc(100vh-7rem)] bg-slate-50 text-slate-900">
      <div className="w-full min-w-0 space-y-4">
        <header className="rounded-lg border border-slate-200/60 glass-header px-5 py-4 shadow-sm">
          <div className="flex flex-col justify-between gap-4 lg:flex-row lg:items-center">
            <div>
              <p className="text-xs font-semibold uppercase tracking-wide text-blue-600">
                Knowledge base
              </p>
              <h1 className="text-2xl font-semibold tracking-normal text-slate-900">
                ALL PD-ECR List
              </h1>
              <p className="mt-1 text-sm text-slate-500">
                数据库中检索到的历史相似
                CASE，可用于参考变更描述、影响分析、验证计划和执行清单。
              </p>
            </div>
            <div className="flex flex-wrap items-center gap-2">
              <Button
                variant="outline"
                className="bg-white hover:border-blue-300 hover:bg-blue-50"
                onClick={() => navigate({ to: "/pd-ecr" })}
              >
                <ArrowLeft className="size-4" />
                返回平台
              </Button>
              <PdEcrProcessFlowButton />
              <Button
                variant="outline"
                className="bg-white hover:border-blue-300 hover:bg-blue-50"
                onClick={importHistoricalCases}
                disabled={isImporting}
              >
                <Upload className="size-4" />
                {isImporting ? "Importing" : "Import history"}
              </Button>
            </div>
          </div>
        </header>

        <section className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
          <div className="grid gap-3 lg:grid-cols-[12rem_1fr_auto]">
            <select
              aria-label="Search field"
              className="h-11 rounded-lg border border-slate-300 bg-white px-3 text-sm text-slate-700 outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-100"
              value={field}
              onChange={(event) => setField(event.target.value as SearchField)}
            >
              <option value="all">Select</option>
              <option value="id">PD-ECR Nr.</option>
              <option value="dcNo">DC No</option>
              <option value="createDate">Date</option>
              <option value="customer">Customer</option>
              <option value="reasonForChange">Reason for Change</option>
              <option value="changeType">Change type</option>
              <option value="sampleType">Sample type</option>
            </select>
            <Input
              aria-label="Filter similar cases"
              value={pendingQuery}
              onChange={(event) => setPendingQuery(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === "Enter") applyFilter()
              }}
              placeholder={`Filter by ${fieldLabel(field)}`}
              className="h-11 border-slate-300 bg-white shadow-none"
            />
            <Button
              className="h-11 bg-blue-700 px-6 text-white transition-colors hover:bg-blue-800"
              onClick={applyFilter}
            >
              Run
            </Button>
          </div>
          {appliedQuery.trim() ? (
            <div className="mt-3 flex flex-wrap items-center gap-2">
              <span className="rounded-full border border-blue-200 bg-blue-50 px-3 py-1 text-xs font-semibold text-blue-700 shadow-sm">
                {displayFieldLabel(field)}: {appliedQuery}
              </span>
              <Button
                type="button"
                variant="ghost"
                size="sm"
                onClick={clearFilter}
                className="h-7 text-xs text-slate-600"
              >
                <X className="size-3" />
                Clear filter
              </Button>
            </div>
          ) : null}
        </section>

        <main className="grid gap-4 lg:grid-cols-[9rem_1fr_11rem]">
          <ActionRail
            onShowAll={showAll}
            onNew={() => navigate({ to: "/pd-ecr" })}
            onEdit={editSelected}
            onShare={shareSelected}
            onPrint={printSelected}
            hasSelection={selectedIds.length > 0}
          />

          <section className="overflow-hidden rounded-xl border border-slate-200/60 bg-white shadow-sm card-hover">
            {deleteNotice ? (
              <div
                className={
                  deleteNotice.kind === "success"
                    ? "border-b border-emerald-100 bg-emerald-50 px-4 py-3 text-sm font-semibold text-emerald-700"
                    : "border-b border-rose-100 bg-rose-50 px-4 py-3 text-sm font-semibold text-rose-700"
                }
              >
                {deleteNotice.message}
              </div>
            ) : null}
            {selectedIds.length ? (
              <div className="flex flex-wrap items-center justify-between gap-3 border-b border-blue-100 bg-blue-50 px-4 py-3">
                <div>
                  <p className="text-sm font-semibold text-blue-900">
                    Bulk actions
                  </p>
                  <p className="text-xs text-blue-700">
                    {selectedIds.length} selected: {selectedIds.join(", ")}
                  </p>
                </div>
                <div className="flex flex-wrap items-center gap-2">
                  <Button
                    size="sm"
                    className="bg-blue-700 text-white transition-all hover:bg-blue-800 active:scale-[0.98]"
                    onClick={editSelected}
                  >
                    Edit selected
                  </Button>
                  <Button size="sm" variant="outline" onClick={shareSelected}>
                    Share
                  </Button>
                  <Button
                    size="sm"
                    variant="outline"
                    className="border-rose-200 bg-white text-rose-700 hover:bg-rose-50"
                    onClick={deleteSelected}
                    disabled={isDeleting}
                  >
                    <Trash2 className="size-4" />
                    {isDeleting ? "Deleting..." : "Delete selected"}
                  </Button>
                  <Button size="sm" variant="ghost" onClick={clearSelection}>
                    Clear selection
                  </Button>
                </div>
              </div>
            ) : null}
            <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-200 px-4 py-3">
              <p className="text-sm text-slate-600" role="status">
                {selectedIds.length ? `${selectedIds.length} selected · ` : ""}
                {status}
              </p>
              <p className="text-sm font-medium text-slate-700">
                {filteredRows.length} / {rows.length} cases
              </p>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full min-w-[148rem] border-collapse table-fixed text-left text-sm">
                <thead>
                  <tr className="bg-slate-800 text-white">
                    <th className="sticky left-0 z-20 w-12 bg-slate-800 px-3 py-3 font-semibold">
                      <span className="sr-only">Selection</span>
                    </th>
                    <th className="sticky left-12 z-20 w-36 bg-slate-800 px-3 py-3 font-semibold">
                      <button type="button" onClick={() => toggleSort("id")} className="inline-flex items-center gap-1 rounded-sm text-left hover:text-blue-100">
                        PD-ECR Nr. <ArrowUpDown className="size-3" />
                      </button>
                    </th>
                    <th className="hidden lg:table-cell px-3 py-3 font-semibold whitespace-nowrap">DC No</th>
                    <th className="hidden lg:table-cell px-3 py-3 font-semibold whitespace-nowrap">Date</th>
                    <th className="px-3 py-3 font-semibold">
                      <button type="button" aria-label="Sort by customer" onClick={() => toggleSort("customer")} className="inline-flex items-center gap-1 rounded-sm text-left hover:text-blue-100">
                        Customer <ArrowUpDown className="size-3" />
                      </button>
                    </th>
<th className="hidden xl:table-cell px-3 py-3 font-semibold whitespace-nowrap w-40">
  <button type="button" aria-label="Sort by reason" onClick={() => toggleSort("reasonForChange")} className="inline-flex items-center gap-1 rounded-sm text-left hover:text-blue-100">
    Reason for Change <ArrowUpDown className="size-3" />
  </button>
</th>
                    <th className="hidden lg:table-cell px-3 py-3 font-semibold whitespace-nowrap">Change Type</th>
                    <th className="w-28 px-3 py-3 font-semibold whitespace-nowrap">Sample Type</th>
                    <th className="w-24 px-3 py-3 font-semibold whitespace-nowrap">
                      <button type="button" aria-label="Sort by score" onClick={() => toggleSort("similarity")} className="inline-flex items-center gap-1 rounded-sm text-left hover:text-blue-100">
                        Score <ArrowUpDown className="size-3" />
                      </button>
                    </th>
                    <th className="w-28 px-3 py-3 font-semibold whitespace-nowrap">Actions</th>
                    <th className="w-56 px-3 py-3 font-semibold whitespace-nowrap">Source File</th>
                    <th className="w-44 px-3 py-3 font-semibold whitespace-nowrap">Missing Metadata</th>
                    <th className="w-[22rem] px-3 py-3 font-semibold whitespace-nowrap">Status flow</th>
                    <th className="w-40 px-3 py-3 font-semibold whitespace-nowrap">Owner</th>
                    <th className="w-36 px-3 py-3 font-semibold whitespace-nowrap">Gate</th>
                    <th className="w-28 px-3 py-3 font-semibold whitespace-nowrap">Risk</th>
                  </tr>
                </thead>
                <tbody>
                  {filteredRows.map((row, index) => {
                    const workbench = getPdEcrCaseWorkbenchState({
                      row,
                      status: row.status,
                      source: view === "similar" ? "history" : row.from,
                    })
                    return (
                    <tr
                      key={row.id}
                      data-testid="case-row"
                      className={
                        index % 2 === 0
                          ? "border-t border-slate-200 bg-white"
                          : "border-t border-slate-200 bg-slate-50"
                      }
                    >
                      <td className={index % 2 === 0 ? "sticky left-0 z-10 bg-white px-3 py-3" : "sticky left-0 z-10 bg-slate-50 px-3 py-3"}>
                        <input aria-label={`Select ${row.id}`} type="checkbox" checked={selectedIds.includes(row.id)} onChange={(event) => toggleRow(row.id, event.target.checked)} className="size-4 rounded border-slate-300 text-blue-600" />
                      </td>
                      <td className={index % 2 === 0 ? "sticky left-12 z-10 w-36 bg-white px-3 py-3 font-semibold text-blue-700" : "sticky left-12 z-10 w-36 bg-slate-50 px-3 py-3 font-semibold text-blue-700"}>
                        <span className="block truncate" title={row.id}>{row.id}</span>
                      </td>
                      <td className="hidden lg:table-cell px-3 py-3 text-slate-700 text-xs">{row.dcNo || "-"}</td>
                      <td className="hidden lg:table-cell px-3 py-3 text-slate-700 text-xs">{row.createDate || "-"}</td>
                      <td className="px-3 py-3 text-slate-700 text-xs max-w-32 truncate">{row.customer}</td>
                      <td className="hidden xl:table-cell px-3 py-3 text-slate-700 text-xs max-w-xl whitespace-normal wrap-break-word w-20">{row.reasonForChange || "-"}</td>
                      <td className="hidden lg:table-cell px-3 py-3 text-slate-700 text-xs">{row.changeType || "-"}</td>
                      <td className="px-3 py-3 text-slate-700 text-xs max-w-28 truncate">{row.sampleType || "-"}</td>
                      <td className="px-3 py-3 text-center">
                        {typeof row.similarity === "number" && row.similarity > 0 ? (
                          <span className="inline-flex items-center justify-center rounded-full bg-blue-100 px-2 py-0.5 text-xs font-bold text-blue-800 min-w-10 shadow-sm">
                            {Math.round(row.similarity)}
                          </span>
                        ) : (
                          <span className="text-xs text-slate-300">-</span>
                        )}
                      </td>
                      <td className="px-3 py-3">
                        <div className="flex items-center gap-1.5">
                         
                          {hasPdfForRow(row) ? (
                            <button type="button" onClick={() => openPdf(row)} className="inline-flex items-center gap-1 whitespace-nowrap rounded-md border border-blue-200 bg-blue-50 px-1.5 py-0.5 text-xs font-semibold text-blue-700 transition hover:bg-blue-100">
                              <ExternalLink className="size-3" /> PDF
                            </button>
                          ) : null}
                        </div>
                      </td>
                      <td className="px-3 py-3 text-xs text-slate-700">
                        <span className="block truncate" title={row.sourceFile || "-"}>
                          {row.sourceFile || "-"}
                        </span>
                      </td>
                      <td className="px-3 py-3 text-xs">
                        {row.missingFields?.length ? (
                          <span
                            className="inline-flex max-w-full rounded-full border border-blue-200 bg-blue-50 px-2 py-0.5 font-semibold text-blue-700"
                            title={row.missingFields.join(", ")}
                          >
                            <span className="truncate">
                              {row.missingFields.join(", ")}
                            </span>
                          </span>
                        ) : (
                          <span className="text-slate-300">-</span>
                        )}
                      </td>
                      <td className="px-3 py-3">
                        <PdEcrCaseStatusFlow
                          status={row.status}
                          source={view === "similar" ? "history" : row.from}
                          compact
                        />
                      </td>
                      <td className="px-3 py-3 text-xs text-slate-700">
                        <span className="block truncate" title={workbench.owner}>{workbench.owner}</span>
                      </td>
                      <td className="px-3 py-3">
                        <span
                          className={`inline-flex rounded-full border px-2 py-0.5 text-[10px] font-semibold ${
                            workbench.gate.tone === "ready"
                              ? "border-emerald-200 bg-emerald-50 text-emerald-700"
                              : workbench.gate.tone === "blocked"
                                ? "border-rose-200 bg-rose-50 text-rose-700"
                                : workbench.gate.tone === "readonly"
                                  ? "border-sky-200 bg-sky-50 text-sky-700"
                                  : "border-blue-200 bg-blue-50 text-blue-700"
                          }`}
                          title={workbench.gate.detail}
                        >
                          {workbench.gate.label}
                        </span>
                      </td>
                      <td className="px-3 py-3">
                        <span
                          className={`inline-flex rounded-full border px-2 py-0.5 text-[10px] font-semibold ${
                            workbench.risk === "High"
                              ? "border-rose-200 bg-rose-50 text-rose-700"
                              : workbench.risk === "Medium"
                                ? "border-blue-200 bg-blue-50 text-blue-700"
                                : workbench.risk === "Low"
                                  ? "border-emerald-200 bg-emerald-50 text-emerald-700"
                                  : "border-slate-200 bg-slate-50 text-slate-500"
                          }`}
                        >
                          {workbench.risk}
                        </span>
                      </td>
                    </tr>
                  )})}
                  {!filteredRows.length ? (
                    <tr>
                      <td className="px-4 py-8 text-center text-sm text-slate-500" colSpan={16}>
                        No matching PD-ECR cases. Use Show all to reset.
                      </td>
                    </tr>
                  ) : null}
                </tbody>
              </table>
            </div>
          </section>

          <FilterPanel field={field} onSelect={selectField} />
        </main>

        <footer className="flex flex-wrap items-center gap-3 pb-2">
          <Button
            variant="outline"
            className="bg-white hover:border-blue-300 hover:bg-blue-50"
            onClick={() => navigate({ to: "/pd-ecr" })}
          >
            <Home className="size-4" />
            Main UI
          </Button>
          <Button variant="outline" className="bg-white hover:border-blue-300 hover:bg-blue-50" onClick={exportList}>
            Export list
          </Button>
          <Button
            variant="outline"
            className="bg-white hover:border-blue-300 hover:bg-blue-50"
            onClick={exportOnePage}
          >
            Export PD-ECR one page
          </Button>
        </footer>
      </div>
    </div>
  )
}
