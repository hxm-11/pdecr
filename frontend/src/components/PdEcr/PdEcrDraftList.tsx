import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { useNavigate } from "@tanstack/react-router"
import {
  ArrowLeft,
  FileText,
  Inbox,
  Plus,
  Sparkles,
  Trash2,
} from "lucide-react"
import { useMemo, useState } from "react"

import { Button } from "@/components/ui/button"
import {
  deletePdEcrModuleDraft,
  listPdEcrModuleDrafts,
  type PdEcrDraftListItem,
} from "@/lib/pdEcrApi"
import {
  loadActiveResult,
  saveActiveResult,
} from "./pdEcrState"

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const MODULE_TITLES: Record<string, string> = {
  "change-description": "变更描述",
  "impact-analysis": "影响分析",
  "validation-plan": "验证计划",
  "validation-result": "验证结果",
  "implementation-plan": "实施计划",
  "implementation-result": "实施结果",
}

/** localStorage key prefixes that represent per-module drafts */
const LOCAL_DRAFT_PATTERNS: { prefix: string; moduleIdFromKey: (key: string) => string | null }[] = [
  {
    prefix: "pd-ecr-change-description-draft:",
    moduleIdFromKey: (key) => {
      const parts = key.slice("pd-ecr-change-description-draft:".length).split(":")
      return parts.length >= 2 ? parts.slice(1).join(":") : null
    },
  },
  {
    prefix: "pd-ecr-impact-analysis-",
    moduleIdFromKey: (key) => key.slice("pd-ecr-impact-analysis-".length) || null,
  },
  {
    prefix: "pd-ecr-validation-plan-",
    moduleIdFromKey: (key) => key.slice("pd-ecr-validation-plan-".length) || null,
  },
  {
    prefix: "pd-ecr-validation-result-",
    moduleIdFromKey: (key) => {
      // Skip the trial-run sub-key
      if (key.endsWith("-trial-run")) return null
      return key.slice("pd-ecr-validation-result-".length) || null
    },
  },
  {
    prefix: "pd-ecr-implementation-",
    moduleIdFromKey: (key) => key.slice("pd-ecr-implementation-".length) || null,
  },
]

const EXCLUDED_LOCAL_KEYS = new Set([
  "pd-ecr-active-result",
  "pd-ecr-generated-result",
  "pd-ecr-history-result",
  "pd-ecr-creation-workflow",
  "pd-ecr-draft-record-id",
])

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function extractTitleFromDraftData(
  data: Record<string, unknown> | null,
  moduleId: string,
): string {
  if (!data || typeof data !== "object") return MODULE_TITLES[moduleId] || moduleId

  const candidate =
    (data.title as string) ||
    (data.changeSummary as string) ||
    (data.reason as string) ||
    (data.description as string) ||
    ""

  if (candidate && candidate.length > 80) {
    return candidate.slice(0, 77) + "..."
  }
  return candidate || MODULE_TITLES[moduleId] || moduleId
}

function isDraftLike(value: unknown): boolean {
  if (!value || typeof value !== "object") return false
  const obj = value as Record<string, unknown>
  // Must have at least one meaningful key beyond a trivial wrapper
  const keys = Object.keys(obj).filter(
    (k) => !["rows", "impacts", "documents", "validations", "approvals"].includes(k) || Array.isArray(obj[k]),
  )
  // If it has specific PD-ECR fields, it's a draft
  if (keys.some((k) => ["source", "reason", "changeSummary", "label", "checked"].includes(k))) return true
  // If it has a `rows` array or `impacts` array, it's likely a module draft
  if (Array.isArray(obj.rows) || Array.isArray(obj.impacts)) return true
  // Generic object with content
  return keys.length >= 2
}

/** Scan localStorage for PD-ECR module drafts that aren't in the backend list */
function scanLocalStorageDrafts(
  backendDrafts: PdEcrDraftListItem[],
): PdEcrDraftListItem[] {
  const backendKeys = new Set(
    backendDrafts.map((d) => `${d.record_id}:${d.module_id}`),
  )
  const result: PdEcrDraftListItem[] = []

  for (let i = 0; i < localStorage.length; i++) {
    const key = localStorage.key(i)
    if (!key || EXCLUDED_LOCAL_KEYS.has(key)) continue

    // Find matching pattern
    const pattern = LOCAL_DRAFT_PATTERNS.find((p) => key.startsWith(p.prefix))
    if (!pattern) continue

    const moduleId = pattern.moduleIdFromKey(key)
    if (!moduleId) continue

    // Extract record_id if present (for change-description keys)
    let recordId = ""
    if (key.startsWith("pd-ecr-change-description-draft:")) {
      const afterPrefix = key.slice("pd-ecr-change-description-draft:".length)
      const colonIdx = afterPrefix.indexOf(":")
      recordId = colonIdx >= 0 ? afterPrefix.slice(0, colonIdx) : afterPrefix
    } else {
      recordId = "local"
    }

    const backendKey = `${recordId}:${moduleId}`
    if (backendKeys.has(backendKey)) continue

    // Try to parse and validate
    try {
      const raw = localStorage.getItem(key)
      if (!raw) continue
      const parsed = JSON.parse(raw)
      if (!isDraftLike(parsed)) continue

      const title = extractTitleFromDraftData(parsed, moduleId)

      result.push({
        record_id: recordId,
        module_id: moduleId,
        title,
        data: parsed,
        created_at: null,
        updated_at: null, // localStorage has no timestamp
      })

      // Mark as seen so we don't duplicate across patterns for the same moduleId
      backendKeys.add(backendKey)
    } catch {
      // Not valid JSON, skip
    }
  }

  return result
}

// ---------------------------------------------------------------------------
// Main Component
// ---------------------------------------------------------------------------

export function PdEcrDraftList() {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const [deleteConfirm, setDeleteConfirm] = useState<string | null>(null)

  const { data, isLoading, isError } = useQuery({
    queryKey: ["pd-ecr-module-drafts"],
    queryFn: () => listPdEcrModuleDrafts(),
    refetchOnWindowFocus: true,
  })

  const backendDrafts = data?.drafts ?? []

  // Merge backend + localStorage drafts
  const drafts = useMemo(() => {
    const local = scanLocalStorageDrafts(backendDrafts)
    // Backend first (newest), then local
    return [
      ...backendDrafts.map((d) => ({ ...d, source: "backend" as const })),
      ...local.map((d) => ({ ...d, source: "local" as const })),
    ]
  }, [backendDrafts])

  const deleteMutation = useMutation({
    mutationFn: ({ recordId, moduleId }: { recordId: string; moduleId: string }) =>
      deletePdEcrModuleDraft(recordId, moduleId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["pd-ecr-module-drafts"] })
      setDeleteConfirm(null)
    },
  })

  const handleDelete = (recordId: string, moduleId: string) => {
    // For local-only drafts, just remove from localStorage
    const isLocal = !backendDrafts.some(
      (d) => d.record_id === recordId && d.module_id === moduleId,
    )
    if (isLocal) {
      // Find and remove the localStorage key(s)
      for (let i = 0; i < localStorage.length; i++) {
        const key = localStorage.key(i)
        if (!key) continue
        if (
          (key.includes(moduleId) && key.startsWith("pd-ecr-")) ||
          key.includes(`${recordId}:${moduleId}`)
        ) {
          localStorage.removeItem(key)
        }
      }
      queryClient.invalidateQueries({ queryKey: ["pd-ecr-module-drafts"] })
      setDeleteConfirm(null)
      return
    }
    deleteMutation.mutate({ recordId, moduleId })
  }

  const handleContinue = (draft: PdEcrDraftListItem & { source: string }) => {
    const active = loadActiveResult()

    // Merge draft data into the matching module (or create one)
    const existingIdx = active.modules.findIndex((m) => m.id === draft.module_id)
    const moduleData = (draft.data as Record<string, unknown>) || {}

    if (existingIdx >= 0) {
      active.modules = active.modules.map((m, idx) =>
        idx === existingIdx
          ? {
              ...m,
              data: { ...m.data, ...moduleData },
              summary: draft.title || m.summary,
            }
          : m,
      )
    } else {
      // Create a minimal module entry so navigation works
      const moduleId = (draft.module_id as import("./pdEcrState").PdEcrModuleId)
      active.modules = [
        ...active.modules,
        {
          id: moduleId,
          title: MODULE_TITLES[draft.module_id] || draft.module_id,
          subtitle: draft.module_id,
          summary: draft.title,
          description: "",
          sourceCases: [],
          sourceFiles: [],
          needsHumanInput: false,
          warnings: [],
          data: moduleData,
        },
      ]
    }

    saveActiveResult(active)
    navigate({
      to: "/pd-ecr/content/$moduleId",
      params: { moduleId: draft.module_id },
      search: { field: undefined, anchor: undefined, taskId: undefined },
    })
  }

  // -----------------------------------------------------------------------
  // Render
  // -----------------------------------------------------------------------

  return (
    <div className="min-h-[calc(100vh-7rem)] bg-slate-50 text-slate-900">
      <div className="w-full min-w-0 space-y-5">
        {/* Header */}
        <header className="rounded-lg border border-slate-200/60 glass-header px-5 py-4 shadow-sm">
          <div className="flex flex-col justify-between gap-4 lg:flex-row lg:items-center">
            <div>
              <div className="flex flex-wrap items-center gap-3">
                <h1 className="text-2xl font-semibold tracking-normal text-slate-900">
                  草稿箱
                </h1>
                <span className="inline-flex items-center rounded-full border border-blue-200 bg-blue-50 px-3 py-1 text-xs font-semibold text-blue-700 shadow-sm">
                  Drafts
                </span>
              </div>
              <p className="mt-1 text-sm text-slate-500">
                未完成的模块草稿 · {drafts.length} 个草稿
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
              <Button
                className="bg-blue-700 transition-all hover:bg-blue-800 active:scale-[0.98]"
                onClick={() => navigate({ to: "/pd-ecr" })}
              >
                <Plus className="size-4" />
                新建变更
              </Button>
            </div>
          </div>
        </header>

        {/* Draft Table */}
        <section className="overflow-hidden rounded-xl border border-slate-200/60 bg-white shadow-sm card-hover">
          {isLoading ? (
            <div className="flex items-center justify-center py-20 text-slate-400">
              <Sparkles className="size-5 animate-pulse" />
              <span className="ml-2">加载草稿中...</span>
            </div>
          ) : isError ? (
            <div className="flex flex-col items-center justify-center gap-3 py-20 text-slate-400">
              <p>无法加载后端草稿。</p>
              {drafts.length > 0 ? (
                <p className="text-xs">已展示 {drafts.length} 个本地草稿</p>
              ) : (
                <Button variant="outline" className="hover:border-blue-300 hover:bg-blue-50" onClick={() => navigate({ to: "/pd-ecr" })}>
                  返回平台
                </Button>
              )}
            </div>
          ) : drafts.length === 0 ? (
            <div className="flex flex-col items-center justify-center gap-3 py-20 text-slate-400">
              <Inbox className="size-10" />
              <p>暂无草稿</p>
              <p className="text-xs">在 PD-ECR 平台填写模块内容后，草稿会自动出现在这里</p>
              <Button
                className="bg-blue-700 transition-all hover:bg-blue-800 active:scale-[0.98]"
                onClick={() => navigate({ to: "/pd-ecr" })}
              >
                <Plus className="size-4" />
                创建新的 PD-ECR
              </Button>
            </div>
          ) : (
            <table className="w-full border-collapse text-left text-sm">
              <thead className="bg-slate-800 text-white">
                <tr>
                  <th className="px-4 py-3 font-semibold">标题</th>
                  <th className="px-4 py-3 font-semibold">模块类型</th>
                  <th className="px-4 py-3 font-semibold hidden md:table-cell">存储位置</th>
                  <th className="px-4 py-3 font-semibold hidden lg:table-cell">最后更新</th>
                  <th className="px-4 py-3 font-semibold text-right">操作</th>
                </tr>
              </thead>
              <tbody>
                {drafts.map((draft) => {
                  const moduleTitle = MODULE_TITLES[draft.module_id] || draft.module_id
                  const isLocal = draft.source === "local"
                  const confirmKey = `${draft.record_id}:${draft.module_id}`
                  const isDeleting = deleteConfirm === confirmKey

                  return (
                    <tr
                      key={confirmKey}
                      className="border-t border-slate-200 odd:bg-white even:bg-slate-50/50 hover:bg-blue-50/50 transition-colors"
                    >
                      {/* Title */}
                      <td className="px-4 py-3 max-w-56 truncate font-medium text-slate-900">
                        {draft.title || moduleTitle}
                      </td>

                      {/* Module type badge */}
                      <td className="px-4 py-3">
                        <span className="inline-flex rounded-full border border-blue-200 bg-blue-50 px-2.5 py-0.5 text-xs font-semibold text-blue-700 shadow-sm">
                          {moduleTitle}
                        </span>
                      </td>

                      {/* Storage location */}
                      <td className="px-4 py-3 text-slate-500 hidden md:table-cell">
                        {isLocal ? (
                          <span className="inline-flex items-center gap-1 rounded-full border border-slate-200 bg-slate-100 px-2 py-0.5 text-xs text-slate-500 shadow-sm">
                            本地
                          </span>
                        ) : (
                          <span className="inline-flex items-center gap-1 rounded-full border border-emerald-200 bg-emerald-50 px-2 py-0.5 text-xs text-emerald-700 shadow-sm">
                            服务器
                          </span>
                        )}
                      </td>

                      {/* Last modified */}
                      <td className="px-4 py-3 text-slate-500 hidden lg:table-cell">
                        {draft.updated_at ? (
                          new Date(draft.updated_at).toLocaleString()
                        ) : draft.created_at ? (
                          new Date(draft.created_at).toLocaleString()
                        ) : (
                          <span className="text-slate-400">仅本地</span>
                        )}
                      </td>

                      {/* Actions */}
                      <td className="px-4 py-3 text-right">
                        <div className="flex items-center justify-end gap-1.5">
                          <Button
                            type="button"
                            size="sm"
                            variant="outline"
                            className="h-8 bg-white hover:border-blue-300 hover:bg-blue-50"
                            onClick={() => handleContinue(draft)}
                          >
                            <FileText className="size-3" />
                            继续编辑
                          </Button>
                          {isDeleting ? (
                            <div className="flex items-center gap-1">
                              <Button
                                type="button"
                                size="sm"
                                variant="outline"
                                className="h-8 border-red-300 bg-red-50 text-red-700 hover:bg-red-100"
                                onClick={() => handleDelete(draft.record_id, draft.module_id)}
                              >
                                确认删除
                              </Button>
                              <Button
                                type="button"
                                size="sm"
                                variant="ghost"
                                className="h-8"
                                onClick={() => setDeleteConfirm(null)}
                              >
                                取消
                              </Button>
                            </div>
                          ) : (
                            <Button
                              type="button"
                              size="sm"
                              variant="ghost"
                              className="h-8 text-slate-400 hover:text-red-600"
                              onClick={() => setDeleteConfirm(confirmKey)}
                            >
                              <Trash2 className="size-3.5" />
                            </Button>
                          )}
                        </div>
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          )}
        </section>

        <footer className="flex items-center gap-3 pb-2">
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
