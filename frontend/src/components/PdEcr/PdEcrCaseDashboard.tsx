import { useQuery } from "@tanstack/react-query"
import { useNavigate } from "@tanstack/react-router"
import {
  ArrowLeft,
  Clock3,
  FileText,
  Plus,
  Search,
  Sparkles,
} from "lucide-react"
import { useMemo, useState } from "react"

import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { listPdEcrCases, type PdEcrCase } from "@/lib/pdEcrApi"
import { PdEcrProcessFlowButton } from "./PdEcrProcessFlow"
import {
  loadGeneratedResult,
  loadHistoryResult,
  saveActiveResult,
} from "./pdEcrState"

const statusLabels: Record<string, { label: string; className: string }> = {
  draft: { label: "Draft", className: "bg-stone-100 text-stone-700 border-stone-200" },
  submitted: { label: "Submitted", className: "bg-blue-50 text-blue-700 border-blue-200" },
  in_review: { label: "In Review", className: "bg-amber-50 text-amber-700 border-amber-200" },
  changes_requested: { label: "Changes Requested", className: "bg-red-50 text-red-700 border-red-200" },
  approved: { label: "Approved", className: "bg-emerald-50 text-emerald-700 border-emerald-200" },
  implementation: { label: "Implementation", className: "bg-purple-50 text-purple-700 border-purple-200" },
  closed: { label: "Closed", className: "bg-stone-50 text-stone-500 border-stone-200" },
  cancelled: { label: "Cancelled", className: "bg-red-50 text-red-400 border-red-200" },
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

  const cases = useMemo(() => {
    if (!data?.cases) return []
    let filtered = data.cases as unknown as PdEcrCase[]

    if (searchText.trim()) {
      const q = searchText.toLowerCase()
      filtered = filtered.filter(
        (c) =>
          c.case_no?.toLowerCase().includes(q) ||
          c.title?.toLowerCase().includes(q) ||
          c.dc_no?.toLowerCase().includes(q) ||
          c.customer_project?.toLowerCase().includes(q),
      )
    }
    if (statusFilter !== "all") {
      filtered = filtered.filter((c) => c.status === statusFilter)
    }
    return filtered
  }, [data, searchText, statusFilter])

  const stats = useMemo(() => {
    if (!data?.cases) return { total: 0, draft: 0, inReview: 0, approved: 0, closed: 0 }
    const all = data.cases as unknown as PdEcrCase[]
    return {
      total: all.length,
      draft: all.filter((c) => c.status === "draft").length,
      inReview: all.filter((c) => c.status === "in_review" || c.status === "submitted").length,
      approved: all.filter((c) => c.status === "approved").length,
      closed: all.filter((c) => c.status === "closed").length,
    }
  }, [data])

  const openCase = (c: PdEcrCase) => {
    // Load existing modules from localStorage as the active result
    const generated = loadGeneratedResult()
    const history = loadHistoryResult()
    const active = generated.modules.length ? generated : history
    saveActiveResult({
      ...active,
      currentCase: {
        id: c.case_no || c.id,
        createDate: c.created_at?.slice(0, 10) || "-",
        productClass: c.product_no || "-",
        from: c.source_type || "Database",
        initiator: c.initiator || "-",
        customer: c.customer_project || "-",
        project: c.customer_project || "-",
        partNumber: c.part_no || c.component_no || "-",
        dept: "-",
        link: "Open modules",
        dcNo: c.dc_no || undefined,
        mcrNo: c.mcr_no || undefined,
        changeType: c.change_type || undefined,
      },
    })
    navigate({ to: "/pd-ecr/content" })
  }

  return (
    <div className="min-h-[calc(100vh-7rem)] bg-stone-50 text-stone-900">
      <div className="w-full min-w-0 space-y-5">
        {/* Header */}
        <header className="rounded-lg border border-stone-200 bg-white px-5 py-4 shadow-sm">
          <div className="flex flex-col justify-between gap-4 lg:flex-row lg:items-center">
            <div>
              <div className="flex flex-wrap items-center gap-3">
                <h1 className="text-3xl font-semibold tracking-normal text-stone-900">
                  PD-ECR Cases
                </h1>
                <span className="inline-flex items-center rounded-full border border-amber-200 bg-amber-50 px-3 py-1 text-xs font-semibold text-amber-700">
                  Dashboard
                </span>
              </div>
              <p className="mt-1 text-sm text-stone-500">
                Manage all PD-ECR change requests · {stats.total} total cases
              </p>
            </div>
            <div className="flex flex-wrap items-center gap-2">
              <Button
                variant="outline"
                className="bg-white"
                onClick={() => navigate({ to: "/pd-ecr" })}
              >
                <ArrowLeft className="size-4" />
                Back to Platform
              </Button>
              <Button
                className="bg-amber-600 hover:bg-amber-700"
                onClick={() => navigate({ to: "/pd-ecr" })}
              >
                <Plus className="size-4" />
                New Change
              </Button>
            </div>
          </div>
        </header>

        {/* Stats */}
        <div className="grid grid-cols-2 gap-3 md:grid-cols-5">
          {[
            { label: "Total", value: stats.total, color: "text-stone-900" },
            { label: "Draft", value: stats.draft, color: "text-stone-600" },
            { label: "In Review", value: stats.inReview, color: "text-amber-600" },
            { label: "Approved", value: stats.approved, color: "text-emerald-600" },
            { label: "Closed", value: stats.closed, color: "text-stone-400" },
          ].map((stat) => (
            <div
              key={stat.label}
              className="rounded-lg border border-stone-200 bg-white px-4 py-3 text-center"
            >
              <p className={`text-lg font-semibold ${stat.color}`}>{stat.value}</p>
              <p className="text-xs text-stone-500">{stat.label}</p>
            </div>
          ))}
        </div>

        {/* Filters */}
        <div className="flex flex-wrap items-center gap-3 rounded-lg border border-stone-200 bg-white px-4 py-3">
          <Search className="size-4 text-stone-400" />
          <Input
            value={searchText}
            onChange={(e) => setSearchText(e.target.value)}
            placeholder="Search by case no, title, DC no..."
            className="h-9 w-64 border-stone-300 bg-white shadow-none"
          />
          <div className="flex flex-wrap gap-1.5">
            {[
              ["all", "All"],
              ["draft", "Draft"],
              ["submitted", "Submitted"],
              ["in_review", "In Review"],
              ["approved", "Approved"],
              ["closed", "Closed"],
            ].map(([value, label]) => (
              <button
                key={value}
                type="button"
                onClick={() => setStatusFilter(value)}
                className={`rounded-full border px-3 py-1 text-xs font-semibold transition ${
                  statusFilter === value
                    ? "border-amber-400 bg-amber-100 text-amber-800"
                    : "border-stone-200 bg-white text-stone-600 hover:bg-stone-50"
                }`}
              >
                {label}
              </button>
            ))}
          </div>
        </div>

        {/* Case Table */}
        <section className="overflow-hidden rounded-lg border border-stone-200 bg-white shadow-sm">
          {isLoading ? (
            <div className="flex items-center justify-center py-20 text-stone-400">
              <Sparkles className="size-5 animate-pulse" />
              <span className="ml-2">Loading cases...</span>
            </div>
          ) : isError ? (
            <div className="flex flex-col items-center justify-center gap-3 py-20 text-stone-400">
              <p>Failed to load cases. The backend may not be running.</p>
              <Button variant="outline" onClick={() => navigate({ to: "/pd-ecr" })}>
                Back to Platform
              </Button>
            </div>
          ) : cases.length === 0 ? (
            <div className="flex flex-col items-center justify-center gap-3 py-20 text-stone-400">
              <FileText className="size-10" />
              <p>No cases found.</p>
              <Button
                className="bg-amber-600 hover:bg-amber-700"
                onClick={() => navigate({ to: "/pd-ecr" })}
              >
                <Plus className="size-4" />
                Create your first PD-ECR
              </Button>
            </div>
          ) : (
            <table className="w-full border-collapse text-left text-sm">
              <thead className="bg-stone-800 text-white">
                <tr>
                  <th className="px-4 py-3 font-semibold">Case No.</th>
                  <th className="px-4 py-3 font-semibold">Title</th>
                  <th className="px-4 py-3 font-semibold">Status</th>
                  <th className="px-4 py-3 font-semibold hidden md:table-cell">Source</th>
                  <th className="px-4 py-3 font-semibold hidden lg:table-cell">Customer / Project</th>
                  <th className="px-4 py-3 font-semibold hidden lg:table-cell">Created</th>
                  <th className="px-4 py-3 font-semibold text-right">Actions</th>
                </tr>
              </thead>
              <tbody>
                {cases.map((c) => {
                  const status = statusLabels[c.status] || statusLabels.draft
                  return (
                    <tr
                      key={c.id}
                      className="border-t border-stone-200 odd:bg-white even:bg-stone-50/50 hover:bg-amber-50/50 cursor-pointer transition-colors"
                      onClick={() => openCase(c)}
                    >
                      <td className="px-4 py-3 font-medium text-stone-900">
                        {c.case_no || c.id?.slice(0, 12) || "-"}
                      </td>
                      <td className="px-4 py-3 max-w-48 truncate text-stone-700">
                        {c.title || "-"}
                      </td>
                      <td className="px-4 py-3">
                        <span
                          className={`inline-flex rounded-full border px-2.5 py-0.5 text-xs font-semibold ${status.className}`}
                        >
                          {status.label}
                        </span>
                      </td>
                      <td className="px-4 py-3 text-stone-500 hidden md:table-cell">
                        {c.source_type || "-"}
                      </td>
                      <td className="px-4 py-3 text-stone-500 hidden lg:table-cell">
                        {c.customer_project || "-"}
                      </td>
                      <td className="px-4 py-3 text-stone-500 hidden lg:table-cell">
                        {c.created_at ? (
                          <span className="inline-flex items-center gap-1">
                            <Clock3 className="size-3" />
                            {new Date(c.created_at).toLocaleDateString()}
                          </span>
                        ) : (
                          "-"
                        )}
                      </td>
                      <td className="px-4 py-3 text-right">
                        <Button
                          type="button"
                          size="sm"
                          variant="outline"
                          className="h-8 bg-white"
                          onClick={(e) => {
                            e.stopPropagation()
                            openCase(c)
                          }}
                        >
                          <FileText className="size-3" />
                          Open
                        </Button>
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          )}
        </section>

        <footer className="flex flex-wrap items-center gap-3 pb-2">
          <PdEcrProcessFlowButton />
          <Button
            variant="ghost"
            size="icon"
            onClick={() => navigate({ to: "/pd-ecr" })}
          >
            <ArrowLeft className="size-5" />
          </Button>
        </footer>
      </div>
    </div>
  )
}
