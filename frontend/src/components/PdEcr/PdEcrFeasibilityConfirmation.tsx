import { Check, FileText, Upload } from "lucide-react"
import { useEffect, useRef, useState } from "react"
import type { PdEcrDisplayModule } from "./pdEcrState"

// ── Types ──
type FeasibilityAttachment = {
  name: string
  type: string
  size: number
}

type FeasibilitySignerRow = {
  person: string
  date: string
}

type FeasibilityState = {
  infoText: string
  initiatorConfirmed: boolean
  initiatorConfirmDate: string
  attachments: FeasibilityAttachment[]
}

// ── Signer roles for leader signing ──
const SIGNER_ROLES = [
  "PD-ECR Initiator's manager",
  "Initiator's HoD",
  "Business owner/Product owner (HoD)",
] as const

// ── Constants ──
const STORAGE_KEY = "pd-ecr-feasibility-confirmation"
const SIGNER_STORAGE_KEY = "pd-ecr-feasibility-signers"

// ── localStorage helpers ──
function loadFeasibilityState(): FeasibilityState {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (raw) {
      const parsed = JSON.parse(raw)
      return {
        infoText: parsed.infoText || "",
        initiatorConfirmed: parsed.initiatorConfirmed || false,
        initiatorConfirmDate: parsed.initiatorConfirmDate || "",
        attachments: Array.isArray(parsed.attachments) ? parsed.attachments : [],
      }
    }
  } catch { /* ignore */ }
  return {
    infoText: "",
    initiatorConfirmed: false,
    initiatorConfirmDate: "",
    attachments: [],
  }
}

export function saveFeasibilityState(state: FeasibilityState) {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(state))
}

// ── Component ──
export function PdEcrFeasibilityConfirmation({
  module: _module,
  hideApproval: _hideApproval,
}: {
  module: PdEcrDisplayModule
  hideApproval?: boolean
}) {
  const [state, setState] = useState<FeasibilityState>(() => loadFeasibilityState())
  const autoSaveTimer = useRef<ReturnType<typeof setTimeout>>(undefined)

  const stepsComplete =
    state.infoText.trim().length > 0 &&
    state.initiatorConfirmed &&
    state.attachments.length > 0

  // Auto-save with 1s debounce
  useEffect(() => {
    if (!autoSaveTimer.current) {
      autoSaveTimer.current = setTimeout(() => {}, 0)
      return
    }
    clearTimeout(autoSaveTimer.current)
    autoSaveTimer.current = setTimeout(() => {
      saveFeasibilityState(state)
    }, 1000)
    return () => clearTimeout(autoSaveTimer.current)
  }, [state])

  const handleFiles = (files: FileList | null) => {
    const incoming = Array.from(files || []).map((f) => ({
      name: f.name,
      type: f.type || "application/octet-stream",
      size: f.size,
    }))
    if (!incoming.length) return
    setState((prev) => ({
      ...prev,
      attachments: [...prev.attachments, ...incoming],
    }))
  }

  const removeAttachment = (index: number) => {
    setState((prev) => ({
      ...prev,
      attachments: prev.attachments.filter((_, j) => j !== index),
    }))
  }

  return (
    <div className="space-y-6">
      {/* Step 1: Info Text + Initiator Confirmation */}
      <div className="rounded-lg border border-stone-200 bg-white p-5">
        <h3 className="text-sm font-semibold text-stone-700 mb-3">
          2.1  变更可行性确认信息
        </h3>

        <label className="space-y-1.5">
          <span className="text-sm font-semibold text-stone-700">
            变更可行性信息
          </span>
          <textarea
            value={state.infoText}
            onChange={(e) =>
              setState((prev) => ({ ...prev, infoText: e.target.value }))
            }
            placeholder="请输入变更可行性相关信息，包括技术可行性、时间可行性、成本可行性等..."
            className="min-h-32 w-full rounded-lg border border-stone-300 bg-white px-3 py-2 text-sm leading-6 resize-none outline-none focus:border-amber-500 focus:ring-2 focus:ring-amber-100"
          />
        </label>

        <div className="mt-4 rounded-lg border border-amber-200 bg-amber-50 p-3">
          <label className="flex items-start gap-3 cursor-pointer">
            <input
              type="checkbox"
              checked={state.initiatorConfirmed}
              onChange={(e) => {
                const checked = e.target.checked
                setState((prev) => ({
                  ...prev,
                  initiatorConfirmed: checked,
                  initiatorConfirmDate: checked
                    ? `${new Date().getFullYear()}-${String(new Date().getMonth() + 1).padStart(2, "0")}-${String(new Date().getDate()).padStart(2, "0")} ${String(new Date().getHours()).padStart(2, "0")}:${String(new Date().getMinutes()).padStart(2, "0")}:${String(new Date().getSeconds()).padStart(2, "0")}`
                    : "",
                }))
              }}
              className="mt-0.5 size-4 rounded border-amber-400 text-amber-600 focus:ring-amber-500 accent-amber-600"
            />
            <div>
              <span className="text-sm font-semibold text-stone-700">
                发起人确认
              </span>
              <p className="text-xs text-stone-500 mt-0.5">
                本人作为变更发起人，已确认上述可行性信息真实有效。
              </p>
            </div>
          </label>
          {state.initiatorConfirmDate && (
            <p className="mt-2 text-xs font-medium text-emerald-600 ml-7">
              ✓ 确认时间: {state.initiatorConfirmDate}
            </p>
          )}
        </div>
      </div>

      {/* Step 2: File Upload */}
      <div className="rounded-lg border border-stone-200 bg-white p-5">
        <h3 className="text-sm font-semibold text-stone-700 mb-3">
          2.2:  附件上传
        </h3>
        <p className="text-xs text-stone-500 mb-4">
          上传相关的可行性分析文档、图纸、测试报告等附件。
        </p>

        <label
          className="relative block rounded-lg border-2 border-dashed p-6 text-center transition cursor-pointer border-stone-300 bg-stone-50 hover:border-amber-400 hover:bg-amber-50/50"
          onDragOver={(e) => {
            e.preventDefault()
          }}
          onDragLeave={(e) => {
            e.preventDefault()
          }}
          onDrop={(e) => {
            e.preventDefault()
            handleFiles(e.dataTransfer.files)
          }}
        >
          <input
            type="file"
            multiple
            accept=".xlsx,.xls,.xlsm,.pdf,.docx,.doc,.png,.jpg,.jpeg"
            className="absolute inset-0 cursor-pointer opacity-0"
            onChange={(e) => {
              handleFiles(e.target.files)
              e.target.value = ""
            }}
          />
          <div className="flex items-center justify-center gap-3 text-stone-500">
            <Upload className="size-5" />
            <span className="text-sm">拖拽文件到此处，或点击上传</span>
          </div>
        </label>

        {state.attachments.length > 0 && (
          <div className="mt-4 space-y-2">
            {state.attachments.map((file, idx) => (
              <div
                key={`${file.name}-${file.size}`}
                className="flex items-center justify-between rounded border border-stone-200 bg-stone-50 px-3 py-2"
              >
                <div className="flex items-center gap-2 min-w-0">
                  <FileText className="size-4 shrink-0 text-stone-400" />
                  <span className="text-xs text-stone-700 truncate">
                    {file.name}
                  </span>
                </div>
                <div className="flex items-center gap-2 shrink-0">
                  <span className="text-[10px] text-stone-400">
                    {(file.size / 1024).toFixed(0)} KB
                  </span>
                  <button
                    type="button"
                    onClick={() => removeAttachment(idx)}
                    className="text-stone-400 hover:text-red-500 text-xs"
                  >
                    ✕
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Completion Banner */}
      {stepsComplete && (
        <div className="rounded-lg border border-emerald-200 bg-emerald-50 p-3 flex items-center gap-2">
          <Check className="size-4 text-emerald-600" />
          <span className="text-sm font-semibold text-emerald-700">
            可行性确认已完成，可进入领导签字页面
          </span>
        </div>
      )}
    </div>
  )
}

// ── Leader Signing Component (used on Page 2) ──
function loadSigners(): FeasibilitySignerRow[] {
  try {
    const raw = localStorage.getItem(SIGNER_STORAGE_KEY)
    if (raw) {
      const parsed = JSON.parse(raw)
      if (parsed?.signers?.length === SIGNER_ROLES.length) return parsed.signers
    }
  } catch { /* ignore */ }
  return SIGNER_ROLES.map(() => ({ person: "", date: "" }))
}

function saveSigners(signers: FeasibilitySignerRow[]) {
  localStorage.setItem(SIGNER_STORAGE_KEY, JSON.stringify({ signers }))
}

export function PdEcrLeaderSigning() {
  const [signers, setSigners] = useState<FeasibilitySignerRow[]>(() => loadSigners())
  const autoSaveTimer = useRef<ReturnType<typeof setTimeout>>(undefined)

  useEffect(() => {
    if (!autoSaveTimer.current) {
      autoSaveTimer.current = setTimeout(() => {}, 0)
      return
    }
    clearTimeout(autoSaveTimer.current)
    autoSaveTimer.current = setTimeout(() => {
      saveSigners(signers)
    }, 1000)
    return () => clearTimeout(autoSaveTimer.current)
  }, [signers])

  const updateSigner = (i: number, value: string) => {
    setSigners((prev) =>
      prev.map((r, j) => {
        if (j !== i) return r
        const next = { ...r, person: value }
        if (value.trim()) {
          const now = new Date()
          next.date = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}-${String(now.getDate()).padStart(2, "0")} ${String(now.getHours()).padStart(2, "0")}:${String(now.getMinutes()).padStart(2, "0")}:${String(now.getSeconds()).padStart(2, "0")}`
        } else {
          next.date = ""
        }
        return next
      })
    )
  }

  return (
    <div className="rounded-lg border border-stone-200 bg-white p-5">
      <p className="text-xs font-semibold uppercase tracking-wide text-sky-700 mb-1">
        Step 4
      </p>
      <h3 className="text-xl font-bold tracking-normal text-sky-900 mb-4">
        领导签核
      </h3>
      <p className="text-xs text-stone-500 mb-5">
        以下三位角色需签字确认本变更的可行性。所有签字完成后即可提交。
      </p>

      <div className="rounded-lg border border-amber-300 bg-white shadow-sm">
        <div className="rounded-t-lg bg-amber-600 px-4 py-2.5 text-sm font-semibold text-white">
          Result Sign-off / 结果签核
        </div>
        <div className="divide-y divide-stone-100">
          {SIGNER_ROLES.map((role, i) => (
            <div key={role} className="px-4 py-2.5">
              <p className="text-xs font-semibold text-stone-700">{role}</p>
              <input
                value={signers[i].person}
                onChange={(e) => updateSigner(i, e.target.value)}
                className="mt-1 h-8 w-full rounded border border-stone-200 bg-white px-2 text-xs outline-none focus:border-amber-400"
                placeholder="签字人..."
              />
              {signers[i].date ? (
                <p className="mt-1 text-[10px] font-medium text-emerald-600">
                  ✓ {signers[i].date}
                </p>
              ) : (
                <p className="mt-1 text-[10px] text-stone-300">待签字</p>
              )}
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
