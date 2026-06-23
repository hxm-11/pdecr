import { useMutation } from "@tanstack/react-query"
import { useNavigate } from "@tanstack/react-router"
import {
  ArrowLeft,
  ArrowRight,
  CheckCircle2,
  Circle,
  Download,
  FileCheck2,
  Home,
  Search,
  Sparkles,
  Upload,
} from "lucide-react"
import { type ReactNode, useEffect, useMemo, useRef, useState } from "react"

import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import {
  createPdEcrRequest,
  generatePdEcrEditableCase,
  type PdEcrInput,
  type PdEcrSimilarCase,
  retrievePdEcrSimilarCases,
} from "@/lib/pdEcrApi"
import { PdEcrProcessFlowButton } from "./PdEcrProcessFlow"
import {
  buildGeneratedResult,
  buildHistoryResult,
  loadGeneratedResult,
  loadHistoryResult,
  resolveRowPdfUrl,
  hasPdfForRow,
  saveActiveResult,
  saveGeneratedResult,
  saveHistoryResult,
  type PdEcrApprovalSuggestion,
  type PdEcrDisplayModule,
  type PdEcrPdEcrCaseRow,
} from "./pdEcrState"
import { downloadText } from "./pdEcrExport"

type CreationData = {
  dcNo: string
  mcrNo: string
  date: string
  customerProject: string
  productNo: string
  componentNo: string
  changeType: string
  initiator: string
  source: string
  reason: string
  currentDesign: string
  changeProposal: string
  targetCloseDate: string
  changeDescription: string
  impactAnalysis: string
  affectedDocuments: string
  validationPlan: string
  trialRunResult: string
  implementationPlan: string
  implementationResult: string
  firstApprovalOwner: string
  firstApprovalComment: string
  secondApprovalOwner: string
  secondApprovalComment: string
  closeSummary: string
}

type FieldGroup = {
  label: string
  fields: (keyof CreationData)[]
  highlight?: boolean
}

type StepConfig = {
  title: string
  eyebrow: string
  description: string
  groups?: FieldGroup[]
  kind: "input" | "search" | "review"
}

const STORAGE_KEY = "pd-ecr-creation-workflow"

const defaultCreationData: CreationData = {
  dcNo: `PD-ECR-${new Date().toISOString().slice(0, 10).replace(/-/g, "")}`,
  mcrNo: "",
  date: new Date().toISOString().slice(0, 10),
  customerProject: "",
  productNo: "",
  componentNo: "",
  changeType: "",
  initiator: "",
  source: "",
  reason: "",
  currentDesign: "",
  changeProposal: "",
  targetCloseDate: "",
  changeDescription: "",
  impactAnalysis: "",
  affectedDocuments: "",
  validationPlan: "",
  trialRunResult: "",
  implementationPlan: "",
  implementationResult: "",
  firstApprovalOwner: "",
  firstApprovalComment: "",
  secondApprovalOwner: "",
  secondApprovalComment: "",
  closeSummary: "",
}

const stepConfigs: StepConfig[] = [
  {
    eyebrow: "Step 1",
    title: "填写变更信息",
    description: "填写关键字段用于检索历史相似案例，黄底字段会驱动RAG搜索。",
    groups: [
      {
        label: "检索关键字段",
        fields: ["dcNo", "source", "initiator", "productNo", "customerProject", "componentNo"],
        highlight: true,
      },
      {
        label: "补充信息",
        fields: ["date", "mcrNo", "changeType", "reason", "currentDesign", "changeProposal", "targetCloseDate", "changeDescription"],
      },
    ],
    kind: "input",
  },
  {
    eyebrow: "Step 2",
    title: "检索相似案例 & AI 生成",
    description: "基于填写的信息检索历史相似案例，确认后一键生成全部6个模块。",
    kind: "search",
  },
  {
    eyebrow: "Step 3",
    title: "审核模块 & 导出报告",
    description: "逐模块审核生成内容，确认无误后导出PD-ECR报告。",
    kind: "review",
  },
]

const fieldLabels: Record<keyof CreationData, string> = {
  dcNo: "PD-ECR No.",
  mcrNo: "MCR No.",
  date: "Date",
  customerProject: "Customer / Project",
  productNo: "Product No.",
  componentNo: "Component No.",
  changeType: "Change type",
  initiator: "Initiator",
  source: "Change source",
  reason: "Reason",
  currentDesign: "Current design",
  changeProposal: "Change proposal",
  targetCloseDate: "Target close date",
  changeDescription: "Change description",
  impactAnalysis: "Impact analysis",
  affectedDocuments: "Affected documents",
  validationPlan: "Validation plan",
  trialRunResult: "Validation result",
  implementationPlan: "Implementation plan",
  implementationResult: "Implementation result",
  firstApprovalOwner: "Approver",
  firstApprovalComment: "Approval comment",
  secondApprovalOwner: "Approver",
  secondApprovalComment: "Approval comment",
  closeSummary: "Close summary",
}

function loadWorkflowData() {
  const raw = localStorage.getItem(STORAGE_KEY)
  if (!raw) return defaultCreationData

  try {
    return {
      ...defaultCreationData,
      ...(JSON.parse(raw) as Partial<CreationData>),
    }
  } catch {
    return defaultCreationData
  }
}

function saveWorkflowData(data: CreationData) {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(data))
}

function buildInput(data: CreationData): PdEcrInput {
  return {
    dc_no: data.dcNo,
    mcr_no: data.mcrNo,
    date: data.date,
    customer_project: data.customerProject,
    product_no: data.productNo,
    part_no: data.componentNo,
    component_no: data.componentNo,
    change_type: data.changeType,
    initiator: data.initiator,
    change_source: data.source,
    reason: data.reason,
    change_reason: data.reason,
    change_description: data.changeDescription || data.changeProposal,
    target_close_date: data.targetCloseDate,
    current_design: data.currentDesign,
    change_proposal: data.changeProposal,
    remarks: [
      `Source: ${data.source}`,
      `Target close date: ${data.targetCloseDate}`,
      data.changeDescription,
      data.impactAnalysis,
      data.affectedDocuments,
      data.validationPlan,
      data.trialRunResult,
      data.implementationPlan,
      data.implementationResult,
    ]
      .filter(Boolean)
      .join("\n"),
  }
}

function missingRequiredFields(data: CreationData) {
  const required: { field: keyof CreationData; label: string }[] = [
    { field: "source", label: "Change source" },
    { field: "reason", label: "Reason" },
    { field: "changeDescription", label: "Change description" },
  ]

  return required
    .filter((item) => !String(data[item.field] || "").trim())
    .map((item) => item.label)
}

function fieldIsLong(field: keyof CreationData) {
  return [
    "currentDesign",
    "changeProposal",
    "changeDescription",
    "impactAnalysis",
    "affectedDocuments",
    "validationPlan",
    "trialRunResult",
    "implementationPlan",
    "implementationResult",
    "firstApprovalComment",
    "secondApprovalComment",
    "closeSummary",
  ].includes(field)
}

/** Build a structured summary from the key fields to seed the Change Description. */
function buildChangeDescriptionSeed(data: CreationData) {
  const lines = [
    data.source && `变更来源：${data.source}`,
    data.dcNo && `变更编号：${data.dcNo}`,
    data.customerProject && `客户项目：${data.customerProject}`,
    data.productNo && `产品号：${data.productNo}`,
    data.componentNo && `零部件号：${data.componentNo}`,
    data.initiator && `发起部门：${data.initiator}`,
  ].filter(Boolean)
  return lines.join("\n")
}

const workflowApprovalFields: { role: string; field: string }[] = [
  { role: "Development", field: "approval_development_person" },
  { role: "Purchasing", field: "approval_purchasing_person" },
  { role: "MFE", field: "approval_mfe_person" },
  { role: "Quality", field: "approval_quality_person" },
]

function parseWorkflowDate(value?: string) {
  if (!value) return undefined

  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? undefined : date
}

function addWorkflowBusinessDays(date: Date, days: number) {
  const next = new Date(date)
  let remaining = days

  while (remaining > 0) {
    next.setDate(next.getDate() + 1)
    const day = next.getDay()
    if (day !== 0 && day !== 6) remaining -= 1
  }

  return next
}

function subtractWorkflowBusinessDays(date: Date, days: number) {
  const next = new Date(date)
  let remaining = Math.max(0, days)

  while (remaining > 0) {
    next.setDate(next.getDate() - 1)
    const day = next.getDay()
    if (day !== 0 && day !== 6) remaining -= 1
  }

  return next
}

function formatWorkflowDate(date: Date) {
  return date.toISOString().slice(0, 10)
}

/**
 * 从 CreationData 中尝试提取 Target Close date。
 * 支持 "Jun. 11" 或 "2026-06-11" 等格式。
 */
function extractTargetCloseDateFromData(data: CreationData): Date | undefined {
  // 直接字段
  const raw = data.targetCloseDate?.trim()
  if (raw) {
    const date = parseWorkflowDate(raw)
    if (date) return date
    // 试着解析 "Jun. 11" 这类格式(Mmm. dd → 补齐年份)
    const withYear = `${raw}, ${new Date().getFullYear()}`
    const date2 = new Date(withYear)
    if (!Number.isNaN(date2.getTime())) return date2
  }
  // 从 remarks 中二次提取
  const remarks = String(data.changeDescription || "")
  const match = remarks.match(
    /Target\s*[Cc]lose\s*date\s*[:：]\s*([A-Za-z]+\s*\d{1,2}|\d{4}-\d{2}-\d{2})/,
  )
  if (match) {
    const d = parseWorkflowDate(match[1])
    if (d) return d
  }
  return undefined
}

function getWorkflowApprovalLeadDays(): number {
  const generated = loadGeneratedResult()
  return generated.approvalLeadDays || 12
}

export function workflowSuggestedApprovalDate(baseDate: string, targetClose?: Date) {
  // 如果有 Target Close date，反向推算：截止日 - 历史案例估算工作日
  if (targetClose) {
    const start = new Date(targetClose)
    let remaining = getWorkflowApprovalLeadDays()
    while (remaining > 0) {
      start.setDate(start.getDate() - 1)
      const day = start.getDay()
      if (day !== 0 && day !== 6) remaining -= 1
    }
    return start.toISOString().slice(0, 10)
  }

  // 兜底：baseDate + 2 工作日
  const date = parseWorkflowDate(baseDate) || new Date()
  return addWorkflowBusinessDays(date, 2).toISOString().slice(0, 10)
}

function workflowSignatureSchedule(targetClose?: Date) {
  if (!targetClose) return undefined

  return {
    firstSignatureDate: formatWorkflowDate(
      subtractWorkflowBusinessDays(targetClose, 10),
    ),
    secondSignatureDate: formatWorkflowDate(
      subtractWorkflowBusinessDays(targetClose, 5),
    ),
  }
}

function approvalPerson(
  suggestions: PdEcrApprovalSuggestion[],
  field: string,
) {
  return suggestions.find((item) => item.field === field)?.person || "-"
}

function FirstApprovalPreview({
  suggestions,
  suggestedDate,
}: {
  suggestions: PdEcrApprovalSuggestion[]
  suggestedDate: string
}) {
  return (
    <div className="overflow-hidden rounded-lg border border-amber-200 bg-white">
      <table className="w-full text-left text-sm">
        <thead className="bg-amber-700 text-white">
          <tr>
            {[
              "Function",
              "Historical approver",
              "AI suggested date",
              "Status",
            ].map((head) => (
              <th key={head} className="px-3 py-2 font-semibold">
                {head}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {workflowApprovalFields.map((item) => {
            const person = approvalPerson(suggestions, item.field)

            return (
              <tr
                key={item.field}
                className="border-t border-amber-100 even:bg-stone-50"
              >
                <td className="px-3 py-2 font-medium text-stone-800">
                  {item.role}
                </td>
                <td className="px-3 py-2 text-stone-700">{person}</td>
                <td className="px-3 py-2 text-stone-700">{suggestedDate}</td>
                <td className="px-3 py-2 text-stone-600">
                  {person === "-" ? "Need confirmation" : "AI suggested"}
                </td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}

function StepIcon({ done, active }: { done: boolean; active: boolean }) {
  if (done) return <CheckCircle2 className="size-4 text-amber-700" />
  if (active) return <Circle className="size-4 fill-amber-600 text-amber-700" />
  return <Circle className="size-4 text-slate-300" />
}

export function ActionBanner({
  icon,
  title,
  children,
}: {
  icon: ReactNode
  title: string
  children: ReactNode
}) {
  return (
    <div className="rounded-lg border border-amber-100 bg-amber-50 p-4">
      <div className="flex items-start gap-3">
        <div className="mt-0.5 text-amber-700">{icon}</div>
        <div>
          <p className="text-sm font-semibold text-stone-900">{title}</p>
          <div className="mt-2 text-sm leading-6 text-stone-700">
            {children}
          </div>
        </div>
      </div>
    </div>
  )
}

export function StepTemplatePreview({
  title,
  data,
  approvalSuggestions,
  suggestedApprovalDate,
}: {
  title: string
  data: CreationData
  approvalSuggestions: PdEcrApprovalSuggestion[]
  suggestedApprovalDate: string
}) {
  if (title.includes("Change Request description")) {
    const rows = [
      ["PD-ECR No.", data.dcNo],
      ["MCR No.", data.mcrNo],
      ["Date", data.date],
      ["Customer / Project", data.customerProject],
      ["Product No.", data.productNo],
      ["Component No.", data.componentNo],
      ["Change type", data.changeType],
      ["Initiator", data.initiator],
      ["Change source", data.source],
      ["Reason", data.reason],
      ["Current design", data.currentDesign],
      ["Change proposal", data.changeProposal],
    ]

    return (
      <div className="overflow-hidden rounded-lg border border-stone-200">
        <table className="w-full text-left text-sm">
          <thead className="bg-amber-700 text-white">
            <tr>
              <th className="w-56 px-3 py-2 font-semibold">Field</th>
              <th className="px-3 py-2 font-semibold">Content</th>
            </tr>
          </thead>
          <tbody>
            {rows.map(([label, value]) => (
              <tr key={label} className="border-t border-stone-200 even:bg-stone-50">
                <td className="px-3 py-2 font-medium text-stone-800">
                  {label}
                </td>
                <td className="whitespace-pre-wrap px-3 py-2 text-stone-700">
                  {value || "-"}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    )
  }

  if (title.includes("Affection analysis")) {
    const rows = [
      "Function & Performance",
      "Interface and Appearance",
      "Reliability and robustness",
      "Manufacturing / assembly / testing",
      "Supplier part",
      "System HW / SW / calibration / mechanical",
      "Affected documents",
    ]

    return (
      <div className="overflow-hidden rounded-lg border border-stone-200">
        <table className="w-full text-left text-sm">
          <thead className="bg-amber-700 text-white">
            <tr>
              <th className="w-64 px-3 py-2 font-semibold">Impact area</th>
              <th className="px-3 py-2 font-semibold">AI suggested answer</th>
              <th className="w-40 px-3 py-2 font-semibold">Engineer check</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row} className="border-t border-stone-200 even:bg-stone-50">
                <td className="px-3 py-2 font-medium text-stone-800">{row}</td>
                <td className="px-3 py-2 text-stone-500">AI generated from similar historical cases</td>
                <td className="px-3 py-2 text-stone-500">Open / Confirmed</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    )
  }

  if (title.includes("Validation &trial run plan")) {
    const rows = [
      "Try run",
      "Capability Studies CMK",
      "MSA",
      "MAE release",
      "Cleanness test",
      "QZ test",
      "BOM check",
      "Test report",
      "PAV release",
    ]
    return (
      <div className="overflow-hidden rounded-lg border border-stone-200">
        <table className="w-full text-left text-sm">
          <thead className="bg-amber-700 text-white">
            <tr>
              {[
                "Validation",
                "Evaluation criteria",
                "Plan finish date",
                "Resp. person",
                "Comments",
              ].map((head) => (
                <th key={head} className="px-3 py-2 font-semibold">
                  {head}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr
                key={row}
                className="border-t border-stone-200 even:bg-stone-50"
              >
                <td className="px-3 py-2">
                  <input type="checkbox" className="mr-2" />
                  {row}
                </td>
                <td className="px-3 py-2 text-stone-400">AI suggestion</td>
                <td className="px-3 py-2 text-stone-400">Target date</td>
                <td className="px-3 py-2 text-stone-400">Owner</td>
                <td className="px-3 py-2 text-stone-400">Remark</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    )
  }

  if (title.includes("Validation &Trial run plan result")) {
    const rows = ["Try run", "Capability Studies CMK", "MSA", "MAE release", "BOM check", "Test report"]

    return (
      <div className="overflow-hidden rounded-lg border border-stone-200">
        <table className="w-full text-left text-sm">
          <thead className="bg-amber-700 text-white">
            <tr>
              {["Validation item", "Status", "Result / evidence", "Signer", "Date"].map((head) => (
                <th key={head} className="px-3 py-2 font-semibold">{head}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row} className="border-t border-stone-200 even:bg-stone-50">
                <td className="px-3 py-2 font-medium text-stone-800">{row}</td>
                <td className="px-3 py-2 text-stone-500">OK / NOK</td>
                <td className="px-3 py-2 text-stone-500">Evidence</td>
                <td className="px-3 py-2 text-stone-500">Signer</td>
                <td className="px-3 py-2 text-stone-500">Date</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    )
  }

  if (title.includes("Implementation")) {
    const rows = [
      "Change BOMs and drawings",
      "Inform document update",
      "Update offer drawing / TCD / D-FMEA",
      "Related equipment ready on site",
      "Old tooling disposal",
      "Old materials disposal",
    ]
    return (
      <div className="overflow-hidden rounded-lg border border-stone-200">
        <table className="w-full text-left text-sm">
          <thead className="bg-amber-700 text-white">
            <tr>
              {[
                "Department",
                "Y/N",
                "Description",
                "Responsible",
                "Due date",
                "Implementation result",
              ].map((head) => (
                <th key={head} className="px-3 py-2 font-semibold">
                  {head}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((row, index) => (
              <tr
                key={row}
                className="border-t border-stone-200 even:bg-stone-50"
              >
                <td className="px-3 py-2">
                  {index < 3 ? "Development" : "Manufacturing"}
                </td>
                <td className="px-3 py-2">{index % 2 ? "N" : "Y"}</td>
                <td className="px-3 py-2">{row}</td>
                <td className="px-3 py-2 text-stone-400">Resp.</td>
                <td className="px-3 py-2 text-stone-400">Due</td>
                <td className="px-3 py-2 text-stone-400">
                  Closed / Ongoing / Open
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    )
  }

  if (title.includes("approval") || title.includes("Approval") || title.includes("signature")) {
    return (
      <FirstApprovalPreview
        suggestions={approvalSuggestions}
        suggestedDate={suggestedApprovalDate}
      />
    )
  }

  if (title.includes("Close status")) {
    return (
      <div className="rounded-lg border border-stone-200 bg-stone-50 p-5">
        <p className="text-sm font-semibold text-stone-800">Close summary</p>
        <p className="mt-2 text-sm leading-6 text-stone-600">
          Final implementation evidence, approval records, and open measures are summarized here before PD-ECR closure.
        </p>
      </div>
    )
  }

  return null
}

export function PdEcrCreationWorkflow() {
  const navigate = useNavigate()
  const initialHistoryResult = useMemo(() => loadHistoryResult(), [])
  const [data, setData] = useState(loadWorkflowData)
  const [step, setStep] = useState(0)
  const [status, setStatus] = useState("Draft saved locally.")
  const [uploadedFiles, setUploadedFiles] = useState<string[]>([])
  const [relatedCases, setRelatedCases] = useState<PdEcrPdEcrCaseRow[]>(
    () => initialHistoryResult.caseRows?.slice(0, 3) ?? [],
  )
  const [similarCases, setSimilarCases] = useState<PdEcrSimilarCase[]>([])
  const [generatedModules, setGeneratedModules] = useState<PdEcrDisplayModule[]>([])
  const targetCloseDate = useMemo(
    () => extractTargetCloseDateFromData(data),
    [data],
  )
  const signatureSchedule = useMemo(
    () => workflowSignatureSchedule(targetCloseDate),
    [targetCloseDate],
  )
  const showSimilarCases = step === 1 && relatedCases.length > 0
  const showUploadedFiles = step === 1 && uploadedFiles.length > 0

  const API_BASE = import.meta.env.VITE_API_URL || "http://localhost:8000"

  const openSimilarPdf = (row: PdEcrPdEcrCaseRow) => {
    const url = resolveRowPdfUrl(row, API_BASE)
    if (url) {
      window.open(url, "_blank", "noopener,noreferrer")
      setStatus(`Opening PDF for ${row.id}...`)
    }
  }

  const openSimilarModules = (row: PdEcrPdEcrCaseRow) => {
    const caseResult = {
      source: "history" as const,
      relatedCases: relatedCases.map((item) => item.id),
      caseRows: relatedCases,
      currentCase: row,
      modules: loadHistoryResult().modules,
    }
    saveHistoryResult(caseResult)
    navigate({ to: "/pd-ecr/content" })
  }

  const currentStep = stepConfigs[step]
  const completedSteps = useMemo(() => {
    return stepConfigs.map((config) => {
      const fields = config.groups?.flatMap((g) => g.fields) ?? []
      if (config.kind === "search") return step > 1 || relatedCases.length > 0
      if (config.kind === "review") return step > 1
      return fields.some((field) => String(data[field] || "").trim())
    })
  }, [data, step, relatedCases])

  const searchMutation = useMutation({
    mutationFn: async () => {
      const missing = missingRequiredFields(data)
      if (missing.length) {
        throw new Error(`Please fill required fields: ${missing.join(", ")}`)
      }
      const input = buildInput(data)
      await createPdEcrRequest(input)
      return retrievePdEcrSimilarCases(input, 5)
    },
    onSuccess: (response) => {
      const result = buildHistoryResult(response)
      saveHistoryResult(result)
      setSimilarCases(response.results)
      setRelatedCases(result.caseRows?.slice(0, 3) ?? [])
      setStatus(
        `Found ${result.relatedCases.length} related historical case(s).`,
      )
    },
    onError: (error) => {
      const fallback = loadHistoryResult()
      setRelatedCases(fallback.caseRows?.slice(0, 3) ?? [])
      setStatus(
        error instanceof Error
          ? error.message
          : "Search service unavailable. Please try again later.",
      )
    },
  })

  const generateMutation = useMutation({
    mutationFn: async () => {
      const missing = missingRequiredFields(data)
      if (missing.length) {
        throw new Error(`Please fill required fields: ${missing.join(", ")}`)
      }
      const input = buildInput(data)
      const cases =
        similarCases.length > 0
          ? similarCases
          : (await retrievePdEcrSimilarCases(input, 5)).results
      setSimilarCases(cases)
      const response = await generatePdEcrEditableCase(input, cases)
      return { response, input, cases }
    },
    onSuccess: ({ response, input, cases }) => {
      const caseLabel =
        response.case.case_no || response.case.dc_no || response.case.id
      const currentCase = {
        id: caseLabel,
        createDate: response.case.created_at?.slice(0, 10) || "-",
        productClass: response.case.product_no || "-",
        from: "Generated draft",
        initiator: response.case.initiator || "-",
        customer: response.case.customer_project || "-",
        project: response.case.customer_project || "-",
        partNumber:
          response.case.part_no || response.case.component_no || "-",
        dept: "-",
        link: "Open modules",
        dcNo: response.case.dc_no || undefined,
        mcrNo: response.case.mcr_no || undefined,
        changeType: response.case.change_type || undefined,
      }
      const generatedResult = buildGeneratedResult({
        draft_id: response.draft_id,
        draft_status: response.draft_status || "V1_MVP_DRAFT",
        input_snapshot: input,
        similar_cases: cases,
        modules: response.modules.map((module) => {
          const contentJson = module.content_json || {}
          const content =
            contentJson.content || module.content_md || module.title || ""
          const warnings = Array.isArray(contentJson.warnings)
            ? contentJson.warnings
            : []

          return {
            id: module.module_id,
            module_id: module.module_id,
            title: module.title,
            summary:
              String(contentJson.summary || "") ||
              module.content_md ||
              module.title,
            content,
            data: {
              ...contentJson,
              content,
              source_cases: module.source_cases || [],
              source_files: module.source_files || [],
              needs_human_input: module.needs_human_input || false,
              warnings,
            },
            source_cases: module.source_cases || [],
            source_files: module.source_files || [],
            needs_human_input: module.needs_human_input || false,
            warnings,
          }
        }),
      })

      saveGeneratedResult({
        ...generatedResult,
        currentCase,
        caseRows: [currentCase],
        relatedCases: generatedResult.relatedCases.length
          ? generatedResult.relatedCases
          : [caseLabel],
      })
      setGeneratedModules(generatedResult.modules)
      setStatus(
        `Generated editable PD-ECR draft ${caseLabel}. Review modules in Step 3.`,
      )
      setStep(2) // go to review step
    },
    onError: (error) => {
      const result = buildGeneratedResult({ message: "fallback" })
      saveGeneratedResult(result)
      setStatus(
        error instanceof Error
          ? error.message
          : "Generation service unavailable. Fallback modules were prepared.",
      )
    },
  })

  const updateField = (field: keyof CreationData, value: string) => {
    setData((current) => {
      const next = { ...current, [field]: value }
      saveWorkflowData(next)
      return next
    })
    setStatus("Draft saved locally.")
  }

  // Auto-fill Change Description from RAG key fields when entering Content 1/6 (once only)
  const content1StepIndex = stepConfigs.findIndex(
    (config) =>
      config.groups?.some(
        (group) =>
          group.fields.length === 1 && group.fields[0] === "changeDescription",
      ) ?? false,
  )
  const autoFilledRef = useRef(false)
  useEffect(() => {
    if (step !== content1StepIndex || autoFilledRef.current) return
    setData((current) => {
      if (current.changeDescription.trim()) return current
      const seed = buildChangeDescriptionSeed(current)
      if (!seed) return current
      autoFilledRef.current = true
      const next = { ...current, changeDescription: seed }
      saveWorkflowData(next)
      return next
    })
  }, [step, content1StepIndex])

  const nextStep = () =>
    setStep((current) => Math.min(current + 1, stepConfigs.length - 1))
  const previousStep = () => setStep((current) => Math.max(current - 1, 0))
  const handleUpload = (files: FileList | null) => {
    const names = Array.from(files ?? []).map((file) => file.name)
    if (!names.length) return
    setUploadedFiles((current) => [...current, ...names])
    setStatus(`Uploaded file reference: ${names.join(", ")}`)
  }

  return (
    <div className="min-h-[calc(100vh-7rem)] bg-stone-50 text-stone-900">
      <div className="w-full min-w-0 space-y-5">
        <header className="rounded-lg border border-stone-200 bg-white px-5 py-4 shadow-sm">
          <div className="flex flex-col justify-between gap-4 lg:flex-row lg:items-center">
            <div>
              <div className="flex flex-wrap items-center gap-3">
                <h1 className="text-3xl font-semibold tracking-normal">
                  New creation
                </h1>
                <span className="inline-flex items-center rounded-full border border-amber-200 bg-amber-50 px-3 py-1 text-xs font-semibold text-amber-800">
                  V1 MVP draft workflow
                </span>
              </div>
              <p className="mt-1 text-sm text-stone-500">
                Fill required fields, retrieve similar cases, generate six
                source-grounded modules, then export for review.
              </p>
            </div>
            <div className="flex flex-wrap items-center gap-2">
              <Button
                variant="outline"
                className="bg-white"
                onClick={() => navigate({ to: "/pd-ecr" })}
              >
                <ArrowLeft className="size-4" />
                Back
              </Button>
              <PdEcrProcessFlowButton />
            </div>
          </div>
        </header>

        <main className="grid gap-5 xl:grid-cols-[18rem_1fr]">
          <aside className="rounded-lg border border-stone-200 bg-white p-4 shadow-sm">
            <p className="text-xs font-semibold uppercase tracking-wide text-stone-500">
              Workflow
            </p>
            <div className="mt-4 space-y-2">
              {stepConfigs.map((config, index) => (
                <button
                  key={config.title}
                  type="button"
                  onClick={() => setStep(index)}
                  className={`flex w-full items-center gap-3 rounded-md px-3 py-2 text-left text-sm transition ${
                    index === step
                      ? "bg-amber-50 font-semibold text-amber-900"
                      : "text-stone-600 hover:bg-stone-50"
                  }`}
                >
                  <StepIcon
                    done={completedSteps[index]}
                    active={index === step}
                  />
                  <span>{config.eyebrow}</span>
                </button>
              ))}
            </div>
          </aside>

          <section className="rounded-lg border border-stone-200 bg-white shadow-sm">
            <header className="border-b border-stone-200 px-5 py-4">
              <p className="text-xs font-semibold uppercase tracking-wide text-amber-700">
                {currentStep.eyebrow}
              </p>
              <h2 className="mt-1 text-2xl font-semibold tracking-normal">
                {currentStep.title}
              </h2>
              <p className="mt-1 text-sm text-stone-500">
                {currentStep.description}
              </p>
            </header>

            <div className="space-y-5 p-5">
              {/* ── Step 1: Input ── */}
              {currentStep.kind === "input" && currentStep.groups ? (
                <div className="space-y-5">
                  {currentStep.groups.map((group) => (
                    <fieldset key={group.label}
                      className={`rounded-lg border p-4 ${group.highlight ? "border-amber-300 bg-amber-50/50" : "border-stone-200 bg-white"}`}
                    >
                      <legend className={`px-2 text-xs font-semibold uppercase tracking-wide ${group.highlight ? "text-amber-700" : "text-stone-500"}`}>
                        {group.highlight ? "◆ " : ""}{group.label}
                      </legend>
                      <div className="mt-3 grid gap-4 md:grid-cols-2">
                        {group.fields.map((field) => {
                          const fieldId = `pd-ecr-${field}`
                          const highlighted = Boolean(group.highlight)
                          return (
                            <label key={field} htmlFor={fieldId}
                              className={fieldIsLong(field) ? "space-y-2 md:col-span-2" : "space-y-2"}
                            >
                              <span className={`text-sm font-semibold ${highlighted ? "text-amber-800" : "text-stone-700"}`}>
                                {fieldLabels[field]}
                              </span>
                              {fieldIsLong(field) ? (
                                <textarea id={fieldId} value={data[field]}
                                  onChange={(e) => updateField(field, e.target.value)}
                                  className={`min-h-24 w-full resize-y rounded-lg border px-4 py-3 text-sm leading-6 outline-none focus:border-amber-500 focus:ring-2 focus:ring-amber-100 ${highlighted ? "border-amber-300 bg-amber-50 text-stone-900" : "border-stone-300 bg-white text-stone-900"}`}
                                />
                              ) : (
                                <Input id={fieldId} value={data[field]}
                                  onChange={(e) => updateField(field, e.target.value)}
                                  className={`h-10 shadow-none ${highlighted ? "border-amber-300 bg-amber-50" : "border-stone-300 bg-white"}`}
                                />
                              )}
                            </label>
                          )
                        })}
                      </div>
                    </fieldset>
                  ))}
                  {signatureSchedule ? (
                    <div className="grid gap-3 rounded-lg border border-amber-200 bg-amber-50 p-4 md:grid-cols-2">
                      <div>
                        <p className="text-xs font-semibold uppercase tracking-wide text-amber-700">First signature target</p>
                        <p className="mt-1 text-lg font-semibold text-stone-900">{signatureSchedule.firstSignatureDate}</p>
                        <p className="mt-1 text-xs text-stone-600">Target close date minus 10 business days</p>
                      </div>
                      <div>
                        <p className="text-xs font-semibold uppercase tracking-wide text-amber-700">Second signature target</p>
                        <p className="mt-1 text-lg font-semibold text-stone-900">{signatureSchedule.secondSignatureDate}</p>
                        <p className="mt-1 text-xs text-stone-600">Target close date minus 5 business days</p>
                      </div>
                    </div>
                  ) : null}
                </div>
              ) : null}

              {/* ── Step 2: Search & Generate ── */}
              {currentStep.kind === "search" ? (
                <div className="space-y-5">
                  <div className="rounded-lg border border-amber-200 bg-amber-50 p-5">
                    <div className="flex items-start gap-4">
                      <div className="flex size-12 shrink-0 items-center justify-center rounded-lg bg-amber-100 text-amber-700">
                        <Search className="size-6" />
                      </div>
                      <div className="flex-1">
                        <h3 className="text-lg font-semibold text-amber-900">检索相似历史案例</h3>
                        <p className="mt-1 text-sm text-amber-700">基于 Step 1 填写的信息在 {20} 个历史案例中模糊匹配，按相关性排序。</p>
                        <Button type="button" onClick={() => searchMutation.mutate()} disabled={searchMutation.isPending}
                          className="mt-4 h-11 bg-amber-600 px-6 text-white hover:bg-amber-700"
                        >
                          <Search className="size-4" />
                          {searchMutation.isPending ? "搜索中..." : "搜索相似案例"}
                        </Button>
                      </div>
                    </div>
                  </div>

                  {showSimilarCases ? (
                    <div className="rounded-lg border border-stone-200 bg-stone-50 p-4">
                      <div className="mb-3 flex items-center justify-between gap-3">
                        <p className="text-sm font-semibold text-stone-800">
                          匹配到 {relatedCases.length} 个相似历史案例
                        </p>
                        <Button type="button" variant="outline" className="h-8 bg-white"
                          onClick={() => navigate({ to: "/pd-ecr/cases", search: { view: "all" } })}>
                          Open list
                        </Button>
                      </div>
                      <div className="grid gap-2 lg:grid-cols-2 xl:grid-cols-3">
                        {relatedCases.map((item) => {
                          const sim = similarCases.find(
                            (c) => c.case_id === item.id || c.source_file === item.sourceFile,
                          )
                          const score = item.similarity ?? sim?.similarity_score
                          const matched = item.matchedKeywords ?? sim?.matched_fields ?? []
                          const srcFile = sim?.source_file || item.sourceFile || ""
                          const summary = sim?.module_summary || item.reasonForChange || ""
                          return (
                            <div key={item.id} className="rounded-md border border-stone-200 bg-white p-3 flex flex-col gap-1.5">
                              <div className="flex items-start justify-between gap-1">
                                <button type="button" onClick={() => openSimilarModules(item)}
                                  className="truncate text-left text-sm font-semibold text-amber-700 hover:text-amber-900">
                                  {item.id}
                                </button>
                                {typeof score === "number" && score > 0 ? (
                                  <span className="shrink-0 rounded-full bg-amber-100 px-1.5 py-0.5 text-xs font-bold text-amber-800">
                                    {Math.round(score)}
                                  </span>
                                ) : null}
                              </div>
                              <p className="text-xs text-stone-500">{item.customer || item.project} · {item.sampleType || item.productClass || "-"}</p>
                              {matched.length > 0 ? (
                                <div className="flex flex-wrap gap-1">
                                  {matched.slice(0, 5).map((f) => (
                                    <span key={f} className="rounded border border-amber-200 bg-amber-50 px-1 py-0 text-xs text-amber-700">{f}</span>
                                  ))}
                                </div>
                              ) : null}
                              {summary ? (
                                <p className="line-clamp-2 text-xs text-stone-400">{summary.slice(0, 120)}</p>
                              ) : srcFile ? (
                                <p className="truncate text-xs text-stone-400">{srcFile}</p>
                              ) : null}
                              <div className="mt-1 flex items-center gap-1.5">
                                {hasPdfForRow(item) ? (
                                  <button type="button" onClick={() => openSimilarPdf(item)}
                                    className="inline-flex items-center gap-0.5 rounded border border-amber-200 bg-amber-50 px-1.5 py-0.5 text-xs font-medium text-amber-700 hover:bg-amber-100">
                                    PDF
                                  </button>
                                ) : null}
                                <button type="button" onClick={() => openSimilarModules(item)}
                                  className="text-xs text-stone-500 hover:text-stone-700 underline">
                                  Modules
                                </button>
                              </div>
                            </div>
                          )
                        })}
                      </div>
                    </div>
                  ) : null}

                  {relatedCases.length > 0 ? (
                    <div className="rounded-lg border border-stone-200 bg-white p-5">
                      <div className="flex items-start gap-4">
                        <div className="flex size-12 shrink-0 items-center justify-center rounded-lg bg-stone-100 text-stone-700">
                          <Sparkles className="size-6" />
                        </div>
                        <div className="flex-1">
                          <h3 className="text-lg font-semibold text-stone-900">AI 一键生成 6 模块</h3>
                          <p className="mt-1 text-sm text-stone-500">基于以上相似案例，AI 生成完整的 PD-ECR 报告（变更描述、影响分析、验证计划、验证结果、实施计划、实施结果）。</p>
                          <Button type="button" onClick={() => generateMutation.mutate()} disabled={generateMutation.isPending}
                            className="mt-4 h-11 bg-stone-800 px-6 text-white hover:bg-stone-700"
                          >
                            <Sparkles className="size-4" />
                            {generateMutation.isPending ? "AI 生成中..." : "AI 一键生成"}
                          </Button>
                        </div>
                      </div>
                    </div>
                  ) : null}

                  {showUploadedFiles ? (
                    <div className="rounded-lg border border-stone-200 bg-stone-50 p-4">
                      <p className="text-sm font-semibold text-stone-800">Uploaded file references</p>
                      <div className="mt-2 flex flex-wrap gap-2">
                        {uploadedFiles.map((name) => (
                          <span key={name} className="rounded-md border border-stone-200 bg-white px-3 py-1 text-xs text-stone-600">{name}</span>
                        ))}
                      </div>
                    </div>
                  ) : null}
                </div>
              ) : null}

              {/* ── Step 3: Review & Export ── */}
              {currentStep.kind === "review" ? (
                <div className="space-y-5">
                  <div className="rounded-lg border border-stone-200 bg-white p-5">
                    <h3 className="text-lg font-semibold text-stone-900">AI 生成的 6 个模块</h3>
                    <p className="mt-1 text-sm text-stone-500">点击模块卡片查看详情，确认内容后导出报告。</p>
                    <div className="mt-4 grid gap-3 md:grid-cols-2 xl:grid-cols-3">
                      {generatedModules.length > 0 ? generatedModules.map((mod) => (
                        <button key={mod.id} type="button" onClick={() => {
                          saveActiveResult({ source: "generated", relatedCases: [], modules: generatedModules })
                          navigate({ to: "/pd-ecr/content/$moduleId", params: { moduleId: mod.id } })
                        }}
                          className="rounded-lg border border-stone-200 bg-stone-50 p-4 text-left transition hover:border-amber-300 hover:shadow-sm"
                        >
                          <p className="text-xs font-semibold uppercase text-stone-400">{mod.subtitle}</p>
                          <p className="mt-1 font-semibold text-stone-800">{mod.title}</p>
                          <p className="mt-1 line-clamp-2 text-xs text-stone-500">{mod.summary?.slice(0, 80) || "点击查看详情 →"}</p>
                        </button>
                      )) : (
                        <p className="col-span-full py-8 text-center text-sm text-stone-400">尚未生成模块，请返回 Step 2 进行 AI 生成。</p>
                      )}
                    </div>
                  </div>

                  {generatedModules.length > 0 ? (
                    <div className="flex flex-wrap gap-2">
                      <Button variant="outline" className="bg-white" onClick={() => navigate({ to: "/pd-ecr/content" })}>
                        <FileCheck2 className="size-4" /> 查看全部模块
                      </Button>
                      <Button variant="outline" className="bg-white" onClick={() => {
                        downloadText("pd-ecr-modules.csv",
                          [["Module","Field","Value"], ...generatedModules.flatMap(m => Object.entries(m.data).map(([k,v]) => [m.title, k, typeof v === "string" ? v : JSON.stringify(v)]))]
                            .map(r => r.map(c => `"${String(c??"").replace(/"/g,'""')}"`).join(",")).join("\n"),
                          "text/csv;charset=utf-8")
                      }}>
                        <Download className="size-4" /> 导出 CSV
                      </Button>
                    </div>
                  ) : null}
                </div>
              ) : null}

              <p className="text-sm text-amber-800" role="status">{status}</p>
            </div>

            <footer className="flex flex-wrap items-center justify-between gap-3 border-t border-stone-200 px-5 py-4">
              <div className="flex items-center gap-2">
                <Button
                  asChild
                  type="button"
                  variant="outline"
                  className="bg-white"
                >
                  <label>
                    <Upload className="size-4" />
                    Upload files
                    <input
                      type="file"
                      multiple
                      className="hidden"
                      onChange={(event) => handleUpload(event.target.files)}
                    />
                  </label>
                </Button>
                <Button
                  type="button"
                  variant="outline"
                  className="bg-white"
                  onClick={previousStep}
                  disabled={step === 0}
                >
                  <ArrowLeft className="size-4" />
                  Previous
                </Button>
                <Button
                  type="button"
                  className="bg-stone-800 hover:bg-stone-700"
                  onClick={nextStep}
                  disabled={step === stepConfigs.length - 1}
                >
                  Next
                  <ArrowRight className="size-4" />
                </Button>
              </div>
              <div className="flex items-center gap-2">
                <Button
                  type="button"
                  variant="outline"
                  className="bg-white"
                  onClick={() => navigate({ to: "/pd-ecr/content" })}
                >
                  Open modules
                </Button>
                <Button
                  type="button"
                  className="bg-amber-700 hover:bg-amber-700"
                  onClick={() => generateMutation.mutate()}
                  disabled={generateMutation.isPending}
                >
                  <Sparkles className="size-4" />
                  {generateMutation.isPending
                    ? "Generating editable draft"
                    : "Generate editable draft"}
                </Button>
                <Button
                  variant="ghost"
                  size="icon"
                  onClick={() => navigate({ to: "/pd-ecr" })}
                >
                  <Home className="size-5" />
                </Button>
              </div>
            </footer>
          </section>
        </main>
      </div>
    </div>
  )
}
