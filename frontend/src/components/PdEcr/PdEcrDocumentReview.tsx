import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { useNavigate, useParams } from "@tanstack/react-router"
import {
  ArrowLeft,
  CheckCircle,
  CheckSquare,
  FileText,
  Save,
  Sparkles,
} from "lucide-react"
import { useMemo, useState } from "react"
import ReactMarkdown from "react-markdown"
import remarkGfm from "remark-gfm"

import { Button } from "@/components/ui/button"
import {
  confirmStagedDocument,
  getStagedDocument,
  resolvePdEcrAssetUrl,
  updateStagedDocument,
  type PdEcrStagedSection,
  type PdEcrStagedTable,
} from "@/lib/pdEcrApi"
import { CHANGE_SOURCE_OPTIONS } from "./pdEcrState"

// ── Metadata fields — match the platform NewChangeForm exactly ──

type ReviewForm = {
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
  departments: string[]
  devDomains: string[]
}

type ReviewFormTextKey = Exclude<keyof ReviewForm, "departments" | "devDomains">

type ParsedControl = {
  type?: string
  sheet?: string
  cell?: string
  caption?: string
  checked?: boolean
  value?: string
  nearby_label?: string
  source?: string
}

const DEV_DOMAINS = ["SYS", "ME", "HW"]

const defaultForm: ReviewForm = {
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
  departments: [],
  devDomains: [],
}

// Map AI-parsed metadata keys → ReviewForm keys
const METADATA_TO_FORM: Record<string, ReviewFormTextKey> = {
  product_no: "product",
  customer_project: "customer",
  change_source: "source",
  reason: "reason",
  initiator: "initiator",
  date: "date",
  part_no: "partNumber",
  component_no: "partNumber",
  change_proposal: "description",
  change_description: "description",
}

const DIRECT_METADATA_KEYS: ReviewFormTextKey[] = [
  "product",
  "customer",
  "source",
  "reason",
  "department",
  "initiator",
  "date",
  "partNumber",
  "description",
]

function parseSourceNotes(sourceNoteRaw: string): Record<string, string> {
  const notes: Record<string, string> = {}
  if (!sourceNoteRaw) return notes
  for (const part of sourceNoteRaw.split("\n")) {
    const idx = part.indexOf(":")
    if (idx > 0) notes[part.slice(0, idx).trim()] = part.slice(idx + 1).trim()
  }
  return notes
}

function serializeSourceNotes(notes: Record<string, string>): string {
  return Object.entries(notes)
    .filter(([, v]) => v)
    .map(([k, v]) => `${k}: ${v}`)
    .join("\n")
}

// ── Component ──

export function PdEcrDocumentReview() {
  const { docId } = useParams({ from: "/_layout/pd-ecr_/documents/$docId" }) as { docId: string }
  const navigate = useNavigate()
  const queryClient = useQueryClient()

  const { data, isLoading, isError } = useQuery({
    queryKey: ["pd-ecr-staged-document", docId],
    queryFn: () => getStagedDocument(docId),
  })

  const [form, setForm] = useState<ReviewForm>(defaultForm)
  const [sourceNotes, setSourceNotes] = useState<Record<string, string>>({})
  const [sections, setSections] = useState<PdEcrStagedSection[]>([])
  const [tables, setTables] = useState<PdEcrStagedTable[]>([])
  const [initialised, setInitialised] = useState(false)
  const [saveMsg, setSaveMsg] = useState("")

  // Init local state from AI-parsed metadata
  if (data && !initialised) {
    const meta = data.metadata as Record<string, unknown>
    const next: ReviewForm = { ...defaultForm }
    for (const [metaKey, formKey] of Object.entries(METADATA_TO_FORM)) {
      const val = meta[metaKey]
      if (val !== undefined && val !== null && String(val).trim()) {
        next[formKey] = String(val).trim()
      }
    }
    // Also copy any direct matches
    for (const key of DIRECT_METADATA_KEYS) {
      if (!next[key] && meta[key]) {
        next[key] = String(meta[key]).trim()
      }
    }
    setForm(next)
    setSourceNotes(parseSourceNotes(String(meta.source_note || meta.sourceNote || "")))
    setSections(data.sections)
    setTables(data.tables)
    setInitialised(true)
  }

  const updateForm = (key: keyof ReviewForm, value: string) =>
    setForm((prev) => ({ ...prev, [key]: value }))

  const previewUrl = useMemo(
    () => (data?.preview_pdf_url ? resolvePdEcrAssetUrl(data.preview_pdf_url) : null),
    [data?.preview_pdf_url],
  )

  const selectedSources = form.source.split(",").map((s) => s.trim()).filter(Boolean)
  const parsedControls = useMemo(() => {
    const raw = data?.metadata?.controls_json
    return Array.isArray(raw) ? (raw as ParsedControl[]) : []
  }, [data?.metadata])
  const checkedControls = parsedControls.filter((control) => control.checked).length
  const qualityWarnings = [
    !data?.parsed_text?.trim() ? "未解析到正文文本" : "",
    sections.length === 0 ? "未识别到章节" : "",
    tables.length === 0 ? "未识别到表格" : "",
    data?.file_type?.match(/^xls/) && parsedControls.length === 0
      ? "Excel 未识别到控件"
      : "",
  ].filter(Boolean)

  // ── Save draft ──
  const saveMutation = useMutation({
    mutationFn: () => {
      const metadata = {
        product_no: form.product,
        customer_project: form.customer,
        change_source: form.source,
        reason: form.reason,
        initiator: form.initiator,
        date: form.date,
        part_no: form.partNumber,
        change_proposal: form.description,
        source_note: serializeSourceNotes(sourceNotes),
        department: form.department,
        affected_departments: form.departments.join(", "),
        dev_domains: form.devDomains.join(", "),
      }
      return updateStagedDocument(docId, {
        metadata_json: metadata as Record<string, unknown>,
        sections_json: sections,
        tables_json: tables,
      })
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["pd-ecr-staged-document", docId] })
      setSaveMsg("已保存")
      setTimeout(() => setSaveMsg(""), 2000)
    },
  })

  // ── Confirm ──
  const confirmMutation = useMutation({
    mutationFn: () => confirmStagedDocument(docId),
    onSuccess: () => {
      navigate({ to: "/pd-ecr/cases", search: { view: "all" } })
    },
  })

  // ── Loading / Error ──
  if (isLoading) {
    return (
      <div className="flex min-h-[60vh] items-center justify-center bg-stone-50">
        <Sparkles className="size-5 animate-pulse text-amber-500" />
        <span className="ml-2 text-stone-500">加载解析结果...</span>
      </div>
    )
  }
  if (isError || !data) {
    return (
      <div className="flex min-h-[60vh] items-center justify-center bg-stone-50">
        <p className="text-stone-500">无法加载文档，请返回重试。</p>
      </div>
    )
  }

  return (
    <div className="min-h-[calc(100vh-7rem)] bg-stone-50 text-stone-900">
      {/* ── Header ── */}
      <header className="sticky top-0 z-10 flex flex-wrap items-center justify-between gap-3 rounded-lg border border-stone-200 bg-white px-5 py-3 shadow-sm">
        <div className="flex items-center gap-3">
          <Button variant="outline" onClick={() => navigate({ to: "/pd-ecr" })}>
            <ArrowLeft className="size-4" /> 返回
          </Button>
          <div>
            <h1 className="text-lg font-semibold">{data.original_filename}</h1>
            <p className="text-xs text-stone-500">
              AI 解析完成 · 请核对并修改后确认入库
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          {saveMsg && (
            <span className="rounded-full bg-emerald-50 px-3 py-1 text-xs font-semibold text-emerald-700">
              {saveMsg}
            </span>
          )}
          <Button
            variant="outline"
            className="bg-white"
            onClick={() => saveMutation.mutate()}
            disabled={saveMutation.isPending}
          >
            <Save className="size-4" /> 保存草稿
          </Button>
          <Button
            className="bg-amber-600 hover:bg-amber-700"
            onClick={() => confirmMutation.mutate()}
            disabled={confirmMutation.isPending}
          >
            <CheckCircle className="size-4" />
            {confirmMutation.isPending ? "入库中..." : "确认入库"}
          </Button>
        </div>
      </header>

      {/* ── Body ── */}
      <div className="mt-4 grid gap-4 xl:grid-cols-[1fr_1fr]">
        {/* LEFT: PDF preview + parsed text */}
        <div className="space-y-4">
          {previewUrl ? (
            <section className="overflow-hidden rounded-lg border border-stone-200 bg-white shadow-sm">
              <div className="border-b border-stone-200 bg-stone-100 px-4 py-2 text-sm font-semibold">
                文件预览
              </div>
              <iframe
                src={previewUrl}
                className="h-[70vh] w-full border-0"
                title="PDF Preview"
              />
            </section>
          ) : (
            <section className="rounded-lg border border-stone-200 bg-white p-5 shadow-sm">
              <h2 className="text-sm font-semibold">解析文本</h2>
              <div className="prose prose-stone prose-sm mt-3 max-h-[70vh] max-w-none overflow-y-auto">
                <ReactMarkdown remarkPlugins={[remarkGfm]}>
                  {data.parsed_text}
                </ReactMarkdown>
              </div>
            </section>
          )}
        </div>

        {/* RIGHT: Metadata form + Sections + Tables */}
        <div className="space-y-4" style={{ maxHeight: "calc(100vh - 8rem)", overflowY: "auto" }}>
          <section className="rounded-lg border border-stone-200 bg-white shadow-sm">
            <div className="flex items-center gap-2 border-b border-stone-200 bg-stone-100 px-4 py-2.5 text-sm font-semibold">
              <FileText className="size-4 text-amber-700" />
              解析质量报告
            </div>
            <div className="grid gap-3 p-4 sm:grid-cols-4">
              <div className="rounded-md border border-stone-200 bg-stone-50 px-3 py-2">
                <p className="text-lg font-semibold text-stone-900">{sections.length}</p>
                <p className="text-xs font-semibold text-stone-600">
                  {sections.length} sections
                </p>
              </div>
              <div className="rounded-md border border-stone-200 bg-stone-50 px-3 py-2">
                <p className="text-lg font-semibold text-stone-900">{tables.length}</p>
                <p className="text-xs font-semibold text-stone-600">
                  {tables.length} tables
                </p>
              </div>
              <div className="rounded-md border border-stone-200 bg-stone-50 px-3 py-2">
                <p className="text-lg font-semibold text-stone-900">{parsedControls.length}</p>
                <p className="text-xs font-semibold text-stone-600">
                  {parsedControls.length} controls
                </p>
              </div>
              <div className="rounded-md border border-stone-200 bg-stone-50 px-3 py-2">
                <p className="text-lg font-semibold text-stone-900">{checkedControls}</p>
                <p className="text-xs font-semibold text-stone-600">
                  checked controls
                </p>
              </div>
            </div>
            <div className="border-t border-stone-100 px-4 py-3">
              <p className="text-xs font-semibold uppercase tracking-wide text-stone-500">
                入库提示
              </p>
              <p className="mt-1 text-sm text-stone-600">
                确认入库后会按章节、表格行和 Excel 控件生成 RAG chunks，并触发知识库后台重建。
              </p>
              {qualityWarnings.length > 0 ? (
                <div className="mt-2 flex flex-wrap gap-2">
                  {qualityWarnings.map((warning) => (
                    <span
                      key={warning}
                      className="rounded-full border border-amber-200 bg-amber-50 px-2.5 py-1 text-xs font-semibold text-amber-700"
                    >
                      {warning}
                    </span>
                  ))}
                </div>
              ) : (
                <span className="mt-2 inline-flex rounded-full border border-emerald-200 bg-emerald-50 px-2.5 py-1 text-xs font-semibold text-emerald-700">
                  结构化解析可用于审核和入库
                </span>
              )}
            </div>
          </section>

          {/* ── Metadata form — matches platform NewChangeForm ── */}
          <section className="rounded-lg border border-stone-200 bg-white shadow-sm">
            <div className="border-b border-stone-200 bg-amber-50 px-4 py-2.5 text-sm font-semibold text-amber-900">
              AI 提取的变更信息（可修改）
            </div>
            <div className="p-4 space-y-3">
              {/* 产品 & 客户 */}
              <div className="grid gap-3 sm:grid-cols-2">
                <label className="space-y-1">
                  <span className="text-xs font-semibold text-stone-500">产品</span>
                  <input value={form.product} onChange={(e) => updateForm("product", e.target.value)}
                    className="h-9 w-full rounded-md border border-stone-300 bg-white px-2.5 text-sm outline-none focus:border-amber-500" />
                </label>
                <label className="space-y-1">
                  <span className="text-xs font-semibold text-stone-500">客户</span>
                  <input value={form.customer} onChange={(e) => updateForm("customer", e.target.value)}
                    className="h-9 w-full rounded-md border border-stone-300 bg-white px-2.5 text-sm outline-none focus:border-amber-500" />
                </label>
              </div>

              {/* 变更来源 — multi-select dropdown + per-source notes */}
              <div className="space-y-2">
                <span className="text-xs font-semibold text-stone-500">变更来源</span>
                <div className="flex flex-wrap gap-2">
                  {CHANGE_SOURCE_OPTIONS.map((opt) => {
                    const checked = selectedSources.includes(opt.value)
                    return (
                      <label key={opt.value} className={`inline-flex cursor-pointer items-center gap-1.5 rounded-full border px-3 py-1 text-xs transition ${
                        checked ? "border-amber-400 bg-amber-100 text-amber-900" : "border-stone-200 bg-white text-stone-600 hover:border-stone-300"
                      }`}>
                        <input type="checkbox" checked={checked} onChange={(e) => {
                          const next = e.target.checked
                            ? [...selectedSources, opt.value]
                            : selectedSources.filter((s) => s !== opt.value)
                          updateForm("source", next.join(", "))
                        }} className="sr-only" />
                        {opt.label}
                      </label>
                    )
                  })}
                </div>
                {selectedSources.length > 0 && (
                  <div className="space-y-1.5 rounded-lg border border-stone-200 bg-stone-50 p-2.5">
                    {selectedSources.map((val) => {
                      const label = CHANGE_SOURCE_OPTIONS.find((o) => o.value === val)?.label || val
                      return (
                        <div key={val} className="flex items-center gap-2">
                          <span className="w-36 shrink-0 truncate text-xs font-medium text-stone-600">{label}</span>
                          <input type="text" placeholder="备注..."
                            value={sourceNotes[val] || ""}
                            onChange={(e) => setSourceNotes((prev) => ({ ...prev, [val]: e.target.value }))}
                            className="h-8 flex-1 rounded border border-stone-200 bg-white px-2 text-xs outline-none focus:border-amber-400" />
                        </div>
                      )
                    })}
                  </div>
                )}
              </div>

              {/* 变更原因 & 发起部门 */}
              <div className="grid gap-3 sm:grid-cols-2">
                <label className="space-y-1">
                  <span className="text-xs font-semibold text-stone-500">变更背景原因</span>
                  <input value={form.reason} onChange={(e) => updateForm("reason", e.target.value)}
                    className="h-9 w-full rounded-md border border-stone-300 bg-white px-2.5 text-sm outline-none focus:border-amber-500" />
                </label>
                <label className="space-y-1">
                  <span className="text-xs font-semibold text-stone-500">变更发起部门</span>
                  <input value={form.department} onChange={(e) => updateForm("department", e.target.value)}
                    className="h-9 w-full rounded-md border border-stone-300 bg-white px-2.5 text-sm outline-none focus:border-amber-500" />
                </label>
              </div>

              {/* 发起人 & 日期 & 零部件号 */}
              <div className="grid gap-3 sm:grid-cols-2">
                <label className="space-y-1">
                  <span className="text-xs font-semibold text-stone-500">变更发起人</span>
                  <input value={form.initiator} onChange={(e) => updateForm("initiator", e.target.value)}
                    className="h-9 w-full rounded-md border border-stone-300 bg-white px-2.5 text-sm outline-none focus:border-amber-500" />
                </label>
                <label className="space-y-1">
                  <span className="text-xs font-semibold text-stone-500">变更发起日期</span>
                  <input type="date" value={form.date} onChange={(e) => updateForm("date", e.target.value)}
                    className="h-9 w-full rounded-md border border-stone-300 bg-white px-2.5 text-sm outline-none focus:border-amber-500" />
                </label>
                <label className="space-y-1">
                  <span className="text-xs font-semibold text-stone-500">零部件号</span>
                  <input value={form.partNumber} onChange={(e) => updateForm("partNumber", e.target.value)}
                    className="h-9 w-full rounded-md border border-stone-300 bg-white px-2.5 text-sm outline-none focus:border-amber-500" />
                </label>
              </div>

              {/* 变更描述 */}
              <label className="space-y-1">
                <span className="text-xs font-semibold text-stone-500">变更描述</span>
                <textarea value={form.description} onChange={(e) => updateForm("description", e.target.value)}
                  className="min-h-20 w-full resize-y rounded-md border border-stone-300 bg-white px-2.5 py-2 text-sm leading-relaxed outline-none focus:border-amber-500" />
              </label>

              {/* 影响的开发域 */}
              <fieldset className="rounded-lg border border-stone-200 bg-stone-50 p-3">
                <legend className="px-1.5 text-xs font-semibold text-stone-500">影响的开发域</legend>
                <div className="flex flex-wrap gap-x-5 gap-y-1.5 text-sm">
                  {DEV_DOMAINS.map((d) => (
                    <label key={d} className="flex items-center gap-1.5">
                      <input type="checkbox" checked={form.devDomains.includes(d)}
                        onChange={(e) => setForm((prev) => ({
                          ...prev,
                          devDomains: e.target.checked
                            ? [...prev.devDomains, d]
                            : prev.devDomains.filter((x) => x !== d),
                        }))}
                        className="accent-amber-600" />
                      {d}
                    </label>
                  ))}
                </div>
              </fieldset>
            </div>
          </section>

          {/* ── Parsed Excel controls ── */}
          {parsedControls.length > 0 && (
            <section className="rounded-lg border border-stone-200 bg-white shadow-sm">
              <div className="flex items-center gap-2 border-b border-stone-200 bg-stone-100 px-4 py-2.5 text-sm font-semibold">
                <CheckSquare className="size-4 text-amber-700" />
                控件状态 · {parsedControls.length} 个
              </div>
              <div className="divide-y divide-stone-100">
                {parsedControls.map((control, index) => (
                  <div key={`${control.sheet}-${control.cell}-${index}`} className="grid gap-2 p-3 text-sm sm:grid-cols-[minmax(0,1fr)_8rem_5rem] sm:items-center">
                    <div className="min-w-0">
                      <p className="truncate font-semibold text-stone-800">
                        {control.nearby_label || control.caption || "Checkbox"}
                      </p>
                      <p className="mt-0.5 truncate text-xs text-stone-500">
                        {control.sheet || "-"} · {control.cell || "-"} · {control.source || "-"}
                      </p>
                    </div>
                    <span className="inline-flex w-fit items-center rounded border border-stone-200 bg-stone-50 px-2 py-1 text-xs font-semibold text-stone-700">
                      {control.caption || control.value || "-"}
                    </span>
                    <label className="inline-flex items-center gap-2 text-xs font-semibold text-stone-700">
                      <input
                        type="checkbox"
                        checked={Boolean(control.checked)}
                        readOnly
                        className="accent-amber-600"
                      />
                      {control.checked ? "checked" : "unchecked"}
                    </label>
                  </div>
                ))}
              </div>
            </section>
          )}

          {/* ── Sections ── */}
          {sections.length > 0 && (
            <section className="rounded-lg border border-stone-200 bg-white shadow-sm">
              <div className="border-b border-stone-200 bg-stone-100 px-4 py-2.5 text-sm font-semibold">
                章节内容（可修改）· {sections.length} 个章节
              </div>
              <div className="divide-y divide-stone-100">
                {sections.map((sec, i) => (
                  <div key={i} className="p-4">
                    <div className="mb-1.5 flex items-center gap-2">
                      <span className="rounded bg-stone-200 px-1.5 py-0.5 text-[10px] font-semibold text-stone-500">
                        {sec.heading ? `H${sec.level}` : `§${sec.index + 1}`}
                      </span>
                      <input value={sec.heading}
                        onChange={(e) => setSections((prev) => prev.map((s, j) => j === i ? { ...s, heading: e.target.value } : s))}
                        className="flex-1 rounded border border-stone-200 bg-stone-50 px-2 py-0.5 text-sm font-semibold outline-none focus:border-amber-400"
                        placeholder="Section heading" />
                      <span className="text-[10px] text-stone-400">p.{sec.page_no}</span>
                    </div>
                    <textarea value={sec.content}
                      onChange={(e) => setSections((prev) => prev.map((s, j) => j === i ? { ...s, content: e.target.value } : s))}
                      className="mt-1 min-h-20 w-full resize-y rounded-md border border-stone-200 bg-white px-3 py-2 text-sm leading-relaxed outline-none focus:border-amber-400" />
                  </div>
                ))}
              </div>
            </section>
          )}

          {/* ── Tables ── */}
          {tables.length > 0 && (
            <section className="rounded-lg border border-stone-200 bg-white shadow-sm">
              <div className="border-b border-stone-200 bg-stone-100 px-4 py-2.5 text-sm font-semibold">
                表格（可修改）· {tables.length} 个表格
              </div>
              <div className="divide-y divide-stone-100">
                {tables.map((table, ti) => (
                  <div key={ti} className="p-4">
                    <div className="mb-2 flex items-center gap-2">
                      <FileText className="size-3 text-stone-400" />
                      <span className="text-xs font-semibold text-stone-500">Table {ti + 1}</span>
                      <span className="text-[10px] text-stone-400">p.{table.page_no}</span>
                    </div>
                    <input value={table.caption}
                      onChange={(e) => setTables((prev) => prev.map((t, j) => j === ti ? { ...t, caption: e.target.value } : t))}
                      className="mb-2 w-full rounded border border-stone-200 bg-stone-50 px-2 py-0.5 text-sm outline-none focus:border-amber-400"
                      placeholder="Table caption" />
                    <div className="overflow-x-auto rounded border border-stone-200">
                      <table className="w-full text-left text-xs">
                        <thead className="bg-stone-800 text-white">
                          <tr>
                            {table.headers.map((h, hi) => (
                              <th key={hi} className="px-2 py-1.5 font-semibold">
                                <input value={h}
                                  onChange={(e) => setTables((prev) => prev.map((t, j) => {
                                    if (j !== ti) return t
                                    const headers = [...t.headers]; headers[hi] = e.target.value
                                    return { ...t, headers }
                                  }))}
                                  className="w-full rounded border-0 bg-transparent px-1 py-0.5 text-white outline-none focus:bg-white/10" />
                              </th>
                            ))}
                          </tr>
                        </thead>
                        <tbody>
                          {table.rows.map((row, ri) => (
                            <tr key={ri} className="even:bg-stone-50">
                              {row.map((cell, ci) => (
                                <td key={ci} className="px-2 py-1">
                                  <input value={cell}
                                    onChange={(e) => setTables((prev) => prev.map((t, j) => {
                                      if (j !== ti) return t
                                      const rows = t.rows.map((r, rj) => rj === ri ? r.map((c, cj) => cj === ci ? e.target.value : c) : r)
                                      return { ...t, rows }
                                    }))}
                                    className="w-full rounded border-0 bg-transparent px-1 py-0.5 text-xs outline-none focus:bg-amber-50" />
                                </td>
                              ))}
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </div>
                ))}
              </div>
            </section>
          )}
        </div>
      </div>
    </div>
  )
}
