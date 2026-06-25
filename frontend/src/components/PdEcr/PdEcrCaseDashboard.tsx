import { useQuery } from "@tanstack/react-query"
import { useNavigate } from "@tanstack/react-router"
import {
  ArrowRight,
  Clock3,
  Database,
  FileText,
  Inbox,
  ListFilter,
  Plus,
  Search,
  Sparkles,
} from "lucide-react"
import { useMemo, useState } from "react"

import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import {
  getPdEcrKnowledgeBaseStatus,
  listPdEcrCases,
  type PdEcrCaseRecord,
  type PdEcrKnowledgeBaseStatus,
} from "@/lib/pdEcrApi"
import { PdEcrProcessFlowButton } from "./PdEcrProcessFlow"

type DashboardCase = {
  id: string
  caseNo: string
  title: string
  status: string
  source: string
  customerProject: string
  dcNo: string
  changeType: string
  createdDate: string
}

const statusLabels: Record<string, { label: string; className: string }> = {
  historical: {
    label: "Historical",
    className: "border-sky-200 bg-sky-50 text-sky-700",
  },
  draft: {
    label: "Draft",
    className: "border-stone-200 bg-stone-100 text-stone-700",
  },
  submitted: {
    label: "Submitted",
    className: "border-blue-200 bg-blue-50 text-blue-700",
  },
  in_review: {
    label: "In Review",
    className: "border-amber-200 bg-amber-50 text-amber-700",
  },
  changes_requested: {
    label: "Changes Requested",
    className: "border-red-200 bg-red-50 text-red-700",
  },
  approved: {
    label: "Approved",
    className: "border-emerald-200 bg-emerald-50 text-emerald-700",
  },
  implementation: {
    label: "Implementation",
    className: "border-violet-200 bg-violet-50 text-violet-700",
  },
  closed: {
    label: "Closed",
    className: "border-stone-200 bg-stone-50 text-stone-500",
  },
  cancelled: {
    label: "Cancelled",
    className: "border-red-200 bg-red-50 text-red-400",
  },
}

function pickString(record: PdEcrCaseRecord, keys: string[]) {
  for (const key of keys) {
    const value = record[key]
    if (Array.isArray(value)) {
      const text = value.filter(Boolean).join(" / ")
      if (text) return text
    }
    if (typeof value === "string" && value.trim()) return value.trim()
    if (typeof value === "number") return String(value)
  }
  return ""
}

function isHistoricalCase(record: PdEcrCaseRecord) {
  const source = pickString(record, ["source_type", "_source", "from"]).toLowerCase()
  return (
    record.is_historical === true ||
    source.includes("historical") ||
    source.includes("knowledge") ||
    source.includes("pdf") ||
    source.includes("normalized")
  )
}

function normalizeStatus(record: PdEcrCaseRecord) {
  if (isHistoricalCase(record)) return "historical"
  return pickString(record, ["status"]) || "draft"
}

function normalizeCase(record: PdEcrCaseRecord, index: number): DashboardCase {
  const metadata =
    record.metadata && typeof record.metadata === "object"
      ? (record.metadata as PdEcrCaseRecord)
      : {}
  const merged = { ...metadata, ...record }
  const id =
    pickString(merged, ["id", "case_id", "case_no", "source_file"]) ||
    `PD-ECR-${index + 1}`
  const caseNo = pickString(merged, ["case_no", "case_id", "id"]) || id
  const title =
    pickString(merged, ["title", "reason_for_change", "change_reason"]) ||
    caseNo

  return {
    id,
    caseNo,
    title,
    status: normalizeStatus(merged),
    source: pickString(merged, ["source_type", "_source", "from"]) || "PD-ECR",
    customerProject:
      pickString(merged, ["customer_project", "customer", "project"]) || "-",
    dcNo: pickString(merged, ["dc_no", "dcNo"]) || "-",
    changeType: pickString(merged, ["change_type", "changeType"]) || "-",
    createdDate:
      pickString(merged, ["created_at", "create_date", "date", "updated_at"]) ||
      "-",
  }
}

function formatDate(value: string) {
  if (!value || value === "-") return "-"
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value.slice(0, 10)
  return date.toLocaleDateString()
}

function matchesSearch(item: DashboardCase, query: string) {
  const q = query.trim().toLowerCase()
  if (!q) return true
  return [
    item.caseNo,
    item.title,
    item.dcNo,
    item.customerProject,
    item.changeType,
    item.source,
  ]
    .join(" ")
    .toLowerCase()
    .includes(q)
}

function MetricTile({
  label,
  value,
  hint,
}: {
  label: string
  value: number | string
  hint: string
}) {
  return (
    <div className="rounded-lg border border-stone-200 bg-white px-4 py-3">
      <p className="text-2xl font-semibold text-stone-900">{value}</p>
      <p className="mt-1 text-sm font-semibold text-stone-700">{label}</p>
      <p className="mt-0.5 text-xs text-stone-500">{hint}</p>
    </div>
  )
}

function formatStatusDate(value?: string | null) {
  if (!value) return "-"
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value.slice(0, 19)
  return date.toLocaleString()
}

function parserLabel(key: string) {
  const labels: Record<string, string> = {
    xlsx_controls: "XLSX controls",
    excel_to_markdown: "Excel parser",
    pdf_to_markdown: "PDF parser",
    mineru: "MinerU OCR",
    libreoffice: "LibreOffice",
  }
  return labels[key] || key
}

function KnowledgeHealthPanel({
  status,
  isLoading,
  isError,
}: {
  status?: PdEcrKnowledgeBaseStatus
  isLoading: boolean
  isError: boolean
}) {
  const vectorReady = Boolean(
    status?.vector_store?.index_exists && status?.vector_store?.meta_exists,
  )
  const rebuildOk = status?.last_rebuild?.success
  const totalDocuments = status?.last_rebuild?.total_documents ?? "-"
  const pending = status?.staged_documents?.pending ?? 0
  const capabilities = Object.entries(status?.parser_capabilities ?? {})

  return (
    <section className="rounded-lg border border-stone-200 bg-white shadow-sm">
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-stone-200 px-4 py-3">
        <div>
          <p className="text-sm font-semibold text-stone-900">
            Knowledge Base Health
          </p>
          <p className="text-xs text-stone-500">
            RAG index, staged uploads, and parser capability checks.
          </p>
        </div>
        <span
          className={
            vectorReady && rebuildOk !== false
              ? "rounded-full border border-emerald-200 bg-emerald-50 px-3 py-1 text-xs font-semibold text-emerald-700"
              : "rounded-full border border-amber-200 bg-amber-50 px-3 py-1 text-xs font-semibold text-amber-700"
          }
        >
          {isLoading
            ? "Checking"
            : isError
              ? "Unavailable"
              : vectorReady
                ? "Ready"
                : "Needs rebuild"}
        </span>
      </div>

      <div className="grid gap-3 p-4 md:grid-cols-4">
        <MetricTile
          label="Indexed docs"
          value={isLoading ? "..." : totalDocuments}
          hint={`${status?.knowledge_files_on_disk ?? 0} source files`}
        />
        <MetricTile
          label="Vector chunks"
          value={isLoading ? "..." : status?.vector_store?.chunk_files ?? 0}
          hint={vectorReady ? "FAISS + metadata ready" : "Index missing"}
        />
        <MetricTile
          label="Upload review"
          value={isLoading ? "..." : pending}
          hint={`${pending} pending review`}
        />
        <MetricTile
          label="Last rebuild"
          value={rebuildOk === false ? "Failed" : rebuildOk ? "OK" : "-"}
          hint={formatStatusDate(status?.last_rebuild?.last_rebuild_at)}
        />
      </div>

      <div className="flex flex-wrap gap-2 border-t border-stone-100 px-4 py-3">
        {capabilities.length > 0 ? (
          capabilities.map(([key, enabled]) => (
            <span
              key={key}
              className={
                enabled
                  ? "rounded-full border border-emerald-200 bg-emerald-50 px-2.5 py-1 text-xs font-semibold text-emerald-700"
                  : "rounded-full border border-stone-200 bg-stone-50 px-2.5 py-1 text-xs font-semibold text-stone-500"
              }
            >
              {parserLabel(key)}
            </span>
          ))
        ) : (
          <span className="text-xs text-stone-500">
            Parser capability status not available.
          </span>
        )}
      </div>
    </section>
  )
}

export function PdEcrCaseDashboard() {
  const navigate = useNavigate()
  const [searchText, setSearchText] = useState("")
  const [statusFilter, setStatusFilter] = useState<string>("all")

  const { data, isLoading, isError } = useQuery({
    queryKey: ["pd-ecr-cases"],
    queryFn: listPdEcrCases,
    refetchOnWindowFocus: true,
  })
  const {
    data: knowledgeStatus,
    isLoading: isKnowledgeLoading,
    isError: isKnowledgeError,
  } = useQuery({
    queryKey: ["pd-ecr-knowledge-base-status"],
    queryFn: getPdEcrKnowledgeBaseStatus,
    refetchOnWindowFocus: true,
  })

  const allCases = useMemo(
    () => (data?.cases ?? []).map(normalizeCase),
    [data],
  )

  const visibleCases = useMemo(
    () =>
      allCases.filter((item) => {
        if (!matchesSearch(item, searchText)) return false
        if (statusFilter === "all") return true
        return item.status === statusFilter
      }),
    [allCases, searchText, statusFilter],
  )

  const stats = useMemo(
    () => ({
      total: allCases.length,
      historical: allCases.filter((item) => item.status === "historical").length,
      draft: allCases.filter((item) => item.status === "draft").length,
      inReview: allCases.filter((item) =>
        ["submitted", "in_review", "changes_requested"].includes(item.status),
      ).length,
      closed: allCases.filter((item) =>
        ["approved", "implementation", "closed"].includes(item.status),
      ).length,
    }),
    [allCases],
  )

  const filterOptions = [
    ["all", "All"],
    ["historical", "Historical"],
    ["draft", "Draft"],
    ["submitted", "Submitted"],
    ["in_review", "In Review"],
    ["approved", "Approved"],
    ["closed", "Closed"],
  ]

  return (
    <div className="min-h-[calc(100vh-7rem)] bg-stone-50 text-stone-900">
      <div className="w-full min-w-0 space-y-4">
        <header className="rounded-lg border border-stone-200 bg-white px-5 py-4 shadow-sm">
          <div className="flex flex-col justify-between gap-4 lg:flex-row lg:items-center">
            <div>
              <p className="text-xs font-semibold uppercase tracking-wide text-amber-600">
                PD-ECR control center
              </p>
              <h1 className="text-3xl font-semibold tracking-normal text-stone-900">
                PD-ECR Dashboard
              </h1>
              <p className="mt-1 text-sm text-stone-500">
                {stats.total} total cases · historical knowledge, active drafts,
                and review status in one place.
              </p>
            </div>
            <div className="flex flex-wrap items-center gap-2">
              <Button
                variant="outline"
                className="bg-white"
                onClick={() => navigate({ to: "/pd-ecr/cases", search: { view: "all" } })}
              >
                <ListFilter className="size-4" />
                All PD-ECR List
              </Button>
              <Button
                className="bg-amber-600 text-white hover:bg-amber-700"
                onClick={() => navigate({ to: "/pd-ecr" })}
              >
                <Plus className="size-4" />
                New PD-ECR
              </Button>
            </div>
          </div>
        </header>

        <section className="grid gap-3 md:grid-cols-5">
          <MetricTile label="Total" value={stats.total} hint="All loaded cases" />
          <MetricTile label="Historical" value={stats.historical} hint="Knowledge base" />
          <MetricTile label="Draft" value={stats.draft} hint="Editable work" />
          <MetricTile label="In Review" value={stats.inReview} hint="Open workflow" />
          <MetricTile label="Ready" value={stats.closed} hint="Approved or closed" />
        </section>

        <KnowledgeHealthPanel
          status={knowledgeStatus}
          isLoading={isKnowledgeLoading}
          isError={isKnowledgeError}
        />

        <section className="grid gap-3 lg:grid-cols-[1fr_18rem]">
          <div className="rounded-lg border border-stone-200 bg-white px-4 py-3 shadow-sm">
            <div className="grid gap-3 lg:grid-cols-[1fr_auto] lg:items-center">
              <label className="relative block">
                <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-stone-400" />
                <Input
                  value={searchText}
                  onChange={(event) => setSearchText(event.target.value)}
                  placeholder="Search case no, DC no, customer, source, or change type"
                  className="h-10 border-stone-300 bg-white pl-9 shadow-none"
                />
              </label>
              <div className="flex flex-wrap gap-1.5">
                {filterOptions.map(([value, label]) => (
                  <button
                    key={value}
                    type="button"
                    onClick={() => setStatusFilter(value)}
                    className={
                      statusFilter === value
                        ? "rounded-full border border-amber-400 bg-amber-100 px-3 py-1 text-xs font-semibold text-amber-800"
                        : "rounded-full border border-stone-200 bg-white px-3 py-1 text-xs font-semibold text-stone-600 hover:bg-stone-50"
                    }
                  >
                    {label}
                  </button>
                ))}
              </div>
            </div>
          </div>

          <div className="grid grid-cols-3 gap-2 rounded-lg border border-stone-200 bg-white p-3 shadow-sm">
            <Button
              variant="outline"
              className="h-10 bg-white px-2"
              onClick={() => navigate({ to: "/pd-ecr" })}
            >
              <Sparkles className="size-4" />
              New
            </Button>
            <Button
              variant="outline"
              className="h-10 bg-white px-2"
              onClick={() => navigate({ to: "/pd-ecr/drafts" })}
            >
              <Inbox className="size-4" />
              Drafts
            </Button>
            <Button
              variant="outline"
              className="h-10 bg-white px-2"
              onClick={() => navigate({ to: "/pd-ecr/cases", search: { view: "all" } })}
            >
              <Database className="size-4" />
              List
            </Button>
          </div>
        </section>

        <section className="overflow-hidden rounded-lg border border-stone-200 bg-white shadow-sm">
          <div className="flex flex-wrap items-center justify-between gap-3 border-b border-stone-200 px-4 py-3">
            <div>
              <p className="text-sm font-semibold text-stone-900">
                Recent PD-ECR Cases
              </p>
              <p className="text-xs text-stone-500">
                {visibleCases.length} visible cases
              </p>
            </div>
            <PdEcrProcessFlowButton />
          </div>

          {isLoading ? (
            <div className="flex items-center justify-center py-20 text-stone-400">
              <Sparkles className="size-5 animate-pulse" />
              <span className="ml-2">Loading cases...</span>
            </div>
          ) : isError ? (
            <div className="flex flex-col items-center justify-center gap-3 py-20 text-stone-500">
              <p>Failed to load PD-ECR cases. Check the backend API address.</p>
              <Button variant="outline" onClick={() => navigate({ to: "/pd-ecr" })}>
                Open PD-ECR Platform
              </Button>
            </div>
          ) : visibleCases.length === 0 ? (
            <div className="flex flex-col items-center justify-center gap-3 py-20 text-stone-500">
              <FileText className="size-10" />
              <p>No matching PD-ECR cases.</p>
              <Button
                className="bg-amber-600 text-white hover:bg-amber-700"
                onClick={() => {
                  setSearchText("")
                  setStatusFilter("all")
                }}
              >
                Show all
              </Button>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full min-w-180 border-collapse text-left text-sm">
                <thead className="bg-stone-800 text-white">
                  <tr>
                    <th className="px-4 py-3 font-semibold">Case No.</th>
                    <th className="px-4 py-3 font-semibold">Title</th>
                    <th className="px-4 py-3 font-semibold">Status</th>
                    <th className="hidden px-4 py-3 font-semibold md:table-cell">Customer</th>
                    <th className="hidden px-4 py-3 font-semibold lg:table-cell">Change Type</th>
                    <th className="hidden px-4 py-3 font-semibold lg:table-cell">Date</th>
                    <th className="px-4 py-3 text-right font-semibold">Action</th>
                  </tr>
                </thead>
                <tbody>
                  {visibleCases.slice(0, 12).map((item, index) => {
                    const status = statusLabels[item.status] || statusLabels.draft
                    return (
                      <tr
                        key={`${item.id}-${index}`}
                        className="border-t border-stone-200 odd:bg-white even:bg-stone-50/60"
                      >
                        <td className="whitespace-nowrap px-4 py-3 font-semibold text-amber-700">
                          {item.caseNo}
                        </td>
                        <td className="max-w-72 truncate px-4 py-3 text-stone-700">
                          {item.title}
                        </td>
                        <td className="px-4 py-3">
                          <span
                            className={`inline-flex rounded-full border px-2.5 py-0.5 text-xs font-semibold ${status.className}`}
                          >
                            {status.label}
                          </span>
                        </td>
                        <td className="hidden px-4 py-3 text-stone-600 md:table-cell">
                          {item.customerProject}
                        </td>
                        <td className="hidden max-w-64 truncate px-4 py-3 text-stone-600 lg:table-cell">
                          {item.changeType}
                        </td>
                        <td className="hidden px-4 py-3 text-stone-500 lg:table-cell">
                          <span className="inline-flex items-center gap-1">
                            <Clock3 className="size-3" />
                            {formatDate(item.createdDate)}
                          </span>
                        </td>
                        <td className="px-4 py-3 text-right">
                          <Button
                            type="button"
                            size="sm"
                            variant="outline"
                            className="h-8 bg-white"
                            onClick={() =>
                              navigate({ to: "/pd-ecr/cases", search: { view: "all" } })
                            }
                          >
                            Open
                            <ArrowRight className="size-3" />
                          </Button>
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
          )}
        </section>
      </div>
    </div>
  )
}
