import { useMutation } from "@tanstack/react-query";
import { useNavigate } from "@tanstack/react-router";
import {
  ArrowRight,
  ClipboardList,
  Database,
  FolderKanban,
  Upload,
} from "lucide-react";
import { type ReactNode, useEffect, useId, useRef, useState } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import useAuth from "@/hooks/useAuth";
import {
  approvePdEcrCase,
  createPdEcrCase,
  generatePdEcrReport,
  getPdEcrCase,
  rejectPdEcrCase,
  submitPdEcrForApproval,
  extractPdEcrMissingFields,
  pdEcrFieldLabel,
  type PdEcrCaseDetailResponse,
  type PdEcrInput,
  type PdEcrModule,
} from "@/lib/pdEcrApi";
import { departmentOptions } from "./PdEcrModuleDetail";
import { PdEcrProcessFlowButton } from "./PdEcrProcessFlow";
import {
  buildGeneratedResult,
  CHANGE_SOURCE_OPTIONS,
  loadGeneratedResult,
  saveGeneratedResult,
} from "./pdEcrState";

const SAMPLE_TYPE_OPTIONS = ["A", "B", "C", "D","FD"];

type ChangeAttachment = {
  name: string;
  type: string;
  size: number;
  previewUrl?: string;
};

type NewChangeForm = {
  nr: string;
  title: string;
  product: string;
  productNo: string;
  customer: string;
  source: string;
  sourceNote: string;
  reason: string;
  initiator: string;
  date: string;
  partNumber: string;
  sampleType: string;
  description: string;
  targetCloseDate: string;
  departments: string[];
  beforeAttachmentNote: string;
  afterAttachmentNote: string;
  initiatorConfirmed: boolean;
  leaderConfirmed: boolean;
};

const defaultNewChange: NewChangeForm = {
  nr: "",
  title: "",
  product: "",
  productNo: "",
  customer: "",
  source: "",
  sourceNote: "",
  reason: "",
  initiator: "",
  date: new Date().toISOString().slice(0, 10),
  partNumber: "",
  sampleType: "",
  description: "",
  targetCloseDate: "",
  departments: [],
  beforeAttachmentNote: "",
  afterAttachmentNote: "",
  initiatorConfirmed: false,
  leaderConfirmed: false,
};

type PdEcrActor = {
  email?: string | null;
  full_name?: string | null;
  display_name?: string | null;
  department?: string | null;
  pd_ecr_role?: string | null;
};

function normalizeActorText(value?: string | null) {
  return String(value || "")
    .trim()
    .toLowerCase()
    .replace(/\s+/g, " ");
}

function actorDisplayName(user?: PdEcrActor | null) {
  return user?.display_name || user?.full_name || user?.email || "";
}

function requestErrorMessage(error: unknown, fallback: string) {
  if (!error || typeof error !== "object") return fallback;
  const record = error as {
    message?: string;
    response?: { status?: number; data?: unknown };
  };
  const detail =
    record.response?.data && typeof record.response.data === "object"
      ? (record.response.data as { detail?: unknown }).detail
      : undefined;
  return [
    record.response?.status ? `HTTP ${record.response.status}` : "",
    typeof detail === "string" ? detail : record.message || fallback,
  ]
    .filter(Boolean)
    .join(": ");
}

function currentUserMatchesInitiator(
  user: PdEcrActor | null | undefined,
  initiator: string,
) {
  const target = normalizeActorText(initiator);
  if (!target) return false;
  return [user?.email, user?.display_name, user?.full_name].some(
    (candidate) => normalizeActorText(candidate) === target,
  );
}

function inferDepartmentFromInitiator(initiator: string) {
  const text = normalizeActorText(initiator);
  for (const department of departmentOptions) {
    const normalized = normalizeActorText(department);
    if (normalized && text.includes(normalized)) return normalized;
  }
  const emailDepartment = text.match(/^([a-z]+)[._-]/)?.[1];
  return emailDepartment || "";
}

function canConfirmInitiatorLeader(
  user: PdEcrActor | null | undefined,
  initiator: string,
) {
  if (user?.pd_ecr_role !== "department_leader") return false;
  if (currentUserMatchesInitiator(user, initiator)) return false;
  const initiatorDepartment = inferDepartmentFromInitiator(initiator);
  if (!initiatorDepartment) return true;
  return normalizeActorText(user.department) === initiatorDepartment;
}

function buildGenerationInput(form: NewChangeForm): PdEcrInput {
  const title = form.title.trim();
  return {
    title,
    dc_no: form.nr || `PD-ECR-${Date.now()}`,
    date: form.date || new Date().toISOString().slice(0, 10),
    customer_project: form.customer || "PD-ECR Platform",
    product_no: form.productNo || form.product,
    part_no: form.partNumber,
    component_no: form.partNumber,
    sample_type: form.sampleType,
    initiator: form.initiator || form.source,
    change_source: form.source,
    reason: form.reason,
    change_description: form.description,
    target_close_date: form.targetCloseDate,
    remarks: [
      `Nr: ${form.nr}`,
      `Title: ${title}`,
      `Product: ${form.product}`,
      `Product No.: ${form.productNo}`,
      `Sample type: ${form.sampleType}`,
      `Source: ${form.source}`,
      `Source notes: ${form.sourceNote}`,
      `Affected departments: ${form.departments.join(", ")}`,
      `Target Close date: ${form.targetCloseDate}`,
      `Before attachment note: ${form.beforeAttachmentNote}`,
      `After attachment note: ${form.afterAttachmentNote}`,
      `Initiator confirmed: ${form.initiatorConfirmed ? "Yes" : "No"}`,
      `Leader confirmed: ${form.leaderConfirmed ? "Yes" : "No"}`,
    ]
      .filter(Boolean)
      .join("\n"),
  };
}

function recordText(data: Record<string, unknown>, keys: string[], fallback = "") {
  for (const key of keys) {
    const value = data[key];
    if (value !== undefined && value !== null && String(value).trim()) {
      return String(value);
    }
  }
  return fallback;
}

function recordBoolean(data: Record<string, unknown>, keys: string[], fallback = false) {
  for (const key of keys) {
    const value = data[key];
    if (typeof value === "boolean") return value;
    if (typeof value === "string" && value.trim()) {
      return ["true", "yes", "1", "confirmed"].includes(value.trim().toLowerCase());
    }
  }
  return fallback;
}

function recordStringList(data: Record<string, unknown>, keys: string[]) {
  for (const key of keys) {
    const value = data[key];
    if (Array.isArray(value)) {
      return value.map((item) => String(item)).filter(Boolean);
    }
    if (typeof value === "string" && value.trim()) {
      return value
        .split(/[,;，；]/)
        .map((item) => item.trim())
        .filter(Boolean);
    }
  }
  return [];
}

function recordAttachments(data: Record<string, unknown>, keys: string[]): ChangeAttachment[] {
  for (const key of keys) {
    const value = data[key];
    if (!Array.isArray(value)) continue;
    return value
      .filter((item): item is Record<string, unknown> => Boolean(item) && typeof item === "object")
      .map((item) => ({
        name: recordText(item, ["name", "fileName", "filename"], "attachment"),
        type: recordText(item, ["type", "contentType"], "application/octet-stream"),
        size: Number(item.size || 0),
      }));
  }
  return [];
}

function changeFormFromCaseDetail(detail: PdEcrCaseDetailResponse): NewChangeForm {
  const changeModule = detail.modules.find((module) => module.module_id === "change-description");
  const data = {
    ...(changeModule?.content_json || {}),
    ...(changeModule?.data || {}),
  };
  const caseRecord = detail.case;

  return {
    nr: recordText(data, ["nr", "Nr", "dc_no", "case_no"], caseRecord.dc_no || caseRecord.case_no || ""),
    title: recordText(data, ["changeTitle", "title", "change_title"], caseRecord.title || ""),
    product: recordText(data, ["product", "product_name"], caseRecord.product_no || ""),
    productNo: recordText(data, ["product_no", "productNo"], caseRecord.product_no || ""),
    customer: recordText(data, ["customer", "customer_project"], caseRecord.customer_project || ""),
    source: recordText(data, ["source", "change_source"]),
    sourceNote: recordText(data, ["sourceNote", "source_note"]),
    reason: recordText(data, ["reason", "change_reason"]),
    initiator: recordText(data, ["initiator", "owner"], caseRecord.initiator || ""),
    date: recordText(data, ["date", "create_date"], caseRecord.created_at?.slice(0, 10) || new Date().toISOString().slice(0, 10)),
    partNumber: recordText(data, ["partNumber", "part_no", "component_no", "part_number"], caseRecord.part_no || caseRecord.component_no || ""),
    sampleType: recordText(data, ["sample_type", "sampleType"], caseRecord.sample_type || ""),
    description: recordText(data, ["changeSummary", "change_proposal", "change_description", "summary", "content"], changeModule?.content_md || ""),
    targetCloseDate: recordText(data, ["target_close_date", "targetCloseDate"], caseRecord.target_close_date?.slice(0, 10) || ""),
    departments: recordStringList(data, ["departments", "affected_departments"]),
    beforeAttachmentNote: recordText(data, ["beforeAttachmentNote", "before_attachment_note"]),
    afterAttachmentNote: recordText(data, ["afterAttachmentNote", "after_attachment_note"]),
    initiatorConfirmed: recordBoolean(data, ["initiatorConfirmed", "initiator_confirmed"]),
    leaderConfirmed: recordBoolean(data, ["leaderConfirmed", "leader_confirmed"]),
  };
}

function WorkPanel({
  eyebrow,
  title,
  icon,
  children,
  className,
  hideHeader = false,
}: {
  eyebrow?: string;
  title?: string;
  icon?: ReactNode;
  children: ReactNode;
  className?: string;
  hideHeader?: boolean;
}) {
  return (
    <section
      className={`enterprise-panel flex flex-col overflow-hidden ${className ?? ""}`}
    >
      {!hideHeader && (
        <header className="flex shrink-0 items-center gap-3 border-b border-slate-200 bg-slate-50/70 px-4 py-3">
          <div className="flex size-9 items-center justify-center rounded-md bg-blue-50 text-blue-700 ring-1 ring-blue-100">
            {icon}
          </div>
          <div>
            <p className="enterprise-section-title">{eyebrow || "PD-ECR"}</p>
            <h2 className="text-lg font-semibold tracking-normal text-slate-900">
              {title || "Workspace"}
            </h2>
          </div>
        </header>
      )}
      <div className={`min-h-0 flex-1 ${hideHeader ? "p-3" : "p-4"}`}>
        {children}
      </div>
    </section>
  );
}

// 必填标记：视觉上一个红色星号，同时给屏幕阅读器一段隐藏的“必填”文本。
function RequiredMark() {
  return (
    <>
      <span className="ml-0.5 text-rose-500" aria-hidden="true">
        *
      </span>
      <span className="sr-only">必填</span>
    </>
  );
}

function FormField({
  label,
  value,
  onChange,
  placeholder,
  className,
  required,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
  className?: string;
  required?: boolean;
}) {
  const inputId = useId();

  return (
    <label className={`space-y-1 ${className ?? ""}`} htmlFor={inputId}>
      <span className="enterprise-field-label">
        {label}
        {required ? <RequiredMark /> : null}
      </span>
      <Input
        id={inputId}
        aria-label={label}
        value={value}
        onChange={(event) => onChange(event.target.value)}
        placeholder={placeholder}
        className="enterprise-input !h-8"
      />
    </label>
  );
}

function SelectField({
  label,
  value,
  onChange,
  options,
  placeholder = "请选择",
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  options: string[];
  placeholder?: string;
}) {
  const inputId = useId();

  return (
    <label className="space-y-1" htmlFor={inputId}>
      <span className="enterprise-field-label">{label}</span>
      <select
        id={inputId}
        aria-label={label}
        value={value}
        onChange={(event) => onChange(event.target.value)}
        className="enterprise-input !h-8"
      >
        <option value="">{placeholder}</option>
        {options.map((option) => (
          <option key={option} value={option}>
            {option}
          </option>
        ))}
      </select>
    </label>
  );
}

function DepartmentCheckboxGroup({
  selected,
  onChange,
  className,
}: {
  selected: string[];
  onChange: (value: string[]) => void;
  className?: string;
}) {
  const toggleDepartment = (department: string, checked: boolean) => {
    onChange(
      checked
        ? Array.from(new Set([...selected, department]))
        : selected.filter((item) => item !== department),
    );
  };

  return (
    <fieldset
      className={`enterprise-field-surface-muted ${
        className ?? ""
      } !px-3 !py-2`}
    >
      <legend className="px-1 text-xs font-semibold text-slate-600">
        影响部门
        <RequiredMark />
      </legend>
      <div className="flex flex-wrap gap-x-4 gap-y-1.5 text-sm text-slate-700">
        {departmentOptions.map((department) => (
          <label key={department} className="flex items-center gap-1.5">
            <input
              type="checkbox"
              checked={selected.includes(department)}
              onChange={(event) =>
                toggleDepartment(department, event.target.checked)
              }
              className="accent-blue-600"
            />
            {department}
          </label>
        ))}
      </div>
    </fieldset>
  );
}

function CompactConfirmationCheck({
  label,
  checked,
  onChange,
  disabled,
  disabledReason,
}: {
  label: string;
  checked: boolean;
  onChange: (checked: boolean) => void;
  disabled?: boolean;
  disabledReason?: string;
}) {
  return (
    <label
      className={`inline-flex h-8 items-center gap-1.5 rounded-md border px-2.5 text-xs font-semibold transition ${
        checked
          ? "border-emerald-200 bg-emerald-50 text-emerald-800"
          : "border-slate-200 bg-white text-slate-600 hover:border-blue-200 hover:bg-blue-50"
      } ${disabled ? "cursor-not-allowed opacity-60" : "cursor-pointer"}`}
      title={disabled ? disabledReason : undefined}
    >
      <input
        type="checkbox"
        checked={checked}
        disabled={disabled}
        onChange={(event) => {
          if (disabled) return;
          onChange(event.target.checked);
        }}
        className="size-3.5 accent-emerald-600"
      />
      <span>{label}</span>
    </label>
  );
}

function fileSizeLabel(size: number) {
  if (!size) return "";
  if (size < 1024) return `${size} B`;
  if (size < 1024 * 1024) return `${Math.round(size / 1024)} KB`;
  return `${(size / 1024 / 1024).toFixed(1)} MB`;
}

function persistedAttachments(attachments: ChangeAttachment[]) {
  return attachments.map(({ name, type, size }) => ({ name, type, size }));
}

function NewChangeAttachmentPanel({
  title,
  attachments,
  note,
  onAdd,
  onRemove,
  onNoteChange,
}: {
  title: string;
  attachments: ChangeAttachment[];
  note: string;
  onAdd: (files: FileList | null) => void;
  onRemove: (index: number) => void;
  onNoteChange: (value: string) => void;
}) {
  return (
    <div className="enterprise-field-surface">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h4 className="text-base font-semibold text-slate-800">{title}</h4>
        </div>
        <label className="inline-flex cursor-pointer items-center gap-2 rounded-md border border-blue-200 bg-blue-50 px-3 py-2 text-sm font-semibold text-blue-700 transition hover:bg-blue-100">
          <Upload className="size-4" />
          上传文件
          <input
            type="file"
            multiple
            className="sr-only"
            onChange={(event) => {
              onAdd(event.target.files);
              event.target.value = "";
            }}
          />
        </label>
      </div>

      {attachments.length > 0 ? (
        <div className="mt-3 grid gap-2">
          {attachments.map((file, index) => (
            <div
              key={`${file.name}-${file.size}-${file.type}`}
              className="flex min-w-0 items-center gap-3 rounded-md border border-slate-200 bg-slate-50 px-3 py-2"
            >
              {file.previewUrl ? (
                <img
                  src={file.previewUrl}
                  alt={file.name}
                  className="size-10 rounded-md object-cover"
                />
              ) : (
                <div className="flex size-10 shrink-0 items-center justify-center rounded-md bg-white text-sm font-semibold text-slate-500">
                  FILE
                </div>
              )}
              <div className="min-w-0 flex-1">
                <p className="truncate text-sm font-medium text-slate-800">
                  {file.name}
                </p>
                <p className="truncate text-sm text-slate-500">
                  {file.type || "file"}{" "}
                  {file.size ? `· ${fileSizeLabel(file.size)}` : ""}
                </p>
              </div>
              <button
                type="button"
                onClick={() => onRemove(index)}
                className="rounded-md px-2 py-1 text-sm font-semibold text-slate-500 hover:bg-white hover:text-red-600"
              >
                删除
              </button>
            </div>
          ))}
        </div>
      ) : (
        <p className="mt-3 rounded-md border border-dashed border-slate-200 bg-slate-50 px-3 py-3 text-sm text-slate-500">
          No files
        </p>
      )}

      <label className="mt-3 block space-y-2">
        <span className="text-sm font-semibold text-slate-600">发起人备注</span>
        <textarea
          value={note}
          onChange={(event) => onNoteChange(event.target.value)}
          placeholder="Note"
          className="enterprise-textarea min-h-20"
        />
      </label>
    </div>
  );
}

function parseSourceNotes(raw: string): Record<string, string> {
  if (!raw) return {};
  try {
    const obj = JSON.parse(raw);
    return typeof obj === "object" && obj !== null && !Array.isArray(obj)
      ? (obj as Record<string, string>)
      : {};
  } catch {
    // Legacy: plain text stored as single note → assign to first source
    return {};
  }
}

function serializeSourceNotes(notes: Record<string, string>): string {
  const filtered: Record<string, string> = {};
  for (const [k, v] of Object.entries(notes)) {
    if (v.trim()) filtered[k] = v.trim();
  }
  return Object.keys(filtered).length > 0 ? JSON.stringify(filtered) : "";
}

function SourceMultiSelect({
  selected,
  onChange,
}: {
  selected: string;
  onChange: (value: string) => void;
}) {
  const [open, setOpen] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);

  // Close on outside click
  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (
        containerRef.current &&
        !containerRef.current.contains(e.target as Node)
      ) {
        setOpen(false);
      }
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  });

  const selectedSet = new Set(
    selected
      .split(",")
      .map((s) => s.trim())
      .filter(Boolean),
  );

  const toggle = (value: string) => {
    const next = selectedSet.has(value)
      ? [...selectedSet].filter((s) => s !== value)
      : [...selectedSet, value];
    onChange(next.join(", "));
  };

  const selectedList = [...selectedSet];

  return (
    <div ref={containerRef} className="relative">
      <button
        type="button"
        onClick={() => setOpen(!open)}
        className={`flex w-full items-center justify-between rounded-md border bg-white px-3 py-1.5 text-left text-sm shadow-sm transition-colors hover:border-slate-400 ${
          open ? "border-blue-500 ring-2 ring-blue-100" : "border-slate-300"
        }`}
      >
        <span
          className={
            selectedList.length > 0 ? "text-slate-900 flex-1" : "text-slate-400"
          }
        >
          {selectedList.length > 0
            ? selectedList.map((v) => (
                <span key={v} className="block text-sm leading-6">
                  {CHANGE_SOURCE_OPTIONS.find((o) => o.value === v)?.label || v}
                </span>
              ))
            : "请选择变更来源..."}
        </span>
        <span className="ml-2 shrink-0 self-start text-slate-400">▼</span>
      </button>
      {open && (
        <div className="absolute z-20 mt-1 w-full rounded-lg border border-slate-200 bg-white py-1 shadow-xl">
          {CHANGE_SOURCE_OPTIONS.map((opt) => (
            <label
              key={opt.value}
              className="flex cursor-pointer items-center gap-2 px-3 py-2 text-sm hover:bg-blue-50"
            >
              <input
                type="checkbox"
                checked={selectedSet.has(opt.value)}
                onChange={() => toggle(opt.value)}
                className="accent-blue-600"
              />
              {opt.label}
            </label>
          ))}
        </div>
      )}
    </div>
  );
}

export function PdEcrPlatform() {
  const navigate = useNavigate();
  const { user } = useAuth();
  const currentUser = user as PdEcrActor | null | undefined;
  const [newChange, setNewChange] = useState(defaultNewChange);
  const [beforeAttachments, setBeforeAttachments] = useState<
    ChangeAttachment[]
  >([]);
  const [afterAttachments, setAfterAttachments] = useState<ChangeAttachment[]>(
    [],
  );
  const [isAttachmentExpanded, setIsAttachmentExpanded] = useState(false);
  const [draftStatus, setDraftStatus] = useState<string | null>(null);
  const [leaderSubmitMessage, setLeaderSubmitMessage] = useState("");
  const [reviewCaseId, setReviewCaseId] = useState<string | null>(null);
  const [reviewTaskId, setReviewTaskId] = useState<string | null>(null);
  const [reviewCaseStatus, setReviewCaseStatus] = useState<string | null>(null);
  const [reviewMessage, setReviewMessage] = useState("");
  const loadedReviewCaseRef = useRef("");
  const canContinue = newChange.initiatorConfirmed && newChange.leaderConfirmed;
  const isReviewClosed = Boolean(reviewCaseId && reviewCaseStatus && reviewCaseStatus !== "submitted");
  const isManagerApprovalReview = Boolean(reviewCaseId && reviewCaseStatus === "submitted");
  const initiatorName = newChange.initiator.trim();
  const userLabel = actorDisplayName(currentUser);
  const canConfirmInitiator = currentUserMatchesInitiator(currentUser, initiatorName);
  const canConfirmLeader =
    isManagerApprovalReview || canConfirmInitiatorLeader(currentUser, initiatorName);
  const approvalComplete = newChange.initiatorConfirmed && newChange.leaderConfirmed;
  const workspaceStatus = reviewCaseId
    ? reviewCaseStatus || "Review"
    : approvalComplete
      ? "Ready for next step"
      : newChange.initiatorConfirmed
        ? "Leader pending"
        : "Drafting";
  const statusTone = approvalComplete
    ? "emerald"
    : newChange.initiatorConfirmed
      ? "amber"
      : "blue";

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const caseId = params.get("caseId");
    const taskId = params.get("taskId");
    if (!caseId || loadedReviewCaseRef.current === caseId) return;

    loadedReviewCaseRef.current = caseId;
    setReviewCaseId(caseId);
    setReviewTaskId(taskId);
    setReviewMessage("Loading submitted change request...");
    getPdEcrCase(caseId)
      .then((detail) => {
        const changeModule = detail.modules.find((module) => module.module_id === "change-description");
        const data = {
          ...(changeModule?.content_json || {}),
          ...(changeModule?.data || {}),
        };
        setNewChange(changeFormFromCaseDetail(detail));
        setReviewCaseStatus(detail.case.status);
        setBeforeAttachments(recordAttachments(data, ["beforeAttachments", "before_attachments"]));
        setAfterAttachments(recordAttachments(data, ["afterAttachments", "after_attachments"]));
        if (detail.case.status === "submitted") {
          setDraftStatus("领导审批模式：正在查看发起人提交的新建变更表单。");
          setReviewMessage("");
        } else {
          setDraftStatus("该领导审批已处理，当前为只读查看。");
          setReviewMessage(`该审批已处理，当前 case 状态为 ${detail.case.status}。`);
        }
      })
      .catch((error) => {
        setReviewMessage(requestErrorMessage(error, "加载提交的变更失败"));
      });
  }, []);

  useEffect(() => {
    if (!userLabel || newChange.initiator.trim()) return;
    setNewChange((current) => ({ ...current, initiator: userLabel }));
  }, [newChange.initiator, userLabel]);

  const addAttachments = (side: "before" | "after", files: FileList | null) => {
    const incoming = Array.from(files ?? []).map((file) => ({
      name: file.name,
      type: file.type || "application/octet-stream",
      size: file.size,
      previewUrl: file.type.startsWith("image/")
        ? URL.createObjectURL(file)
        : undefined,
    }));
    if (!incoming.length) return;

    if (side === "before") {
      setBeforeAttachments((current) => [...current, ...incoming]);
    } else {
      setAfterAttachments((current) => [...current, ...incoming]);
    }
  };

  const removeAttachment = (side: "before" | "after", index: number) => {
    if (side === "before") {
      setBeforeAttachments((current) =>
        current.filter((_, itemIndex) => itemIndex !== index),
      );
    } else {
      setAfterAttachments((current) =>
        current.filter((_, itemIndex) => itemIndex !== index),
      );
    }
  };

  const persistBeforeAfterAttachments = (recordId: string) => {
    localStorage.setItem(
      `pd-ecr-before-after-attachments:${recordId}:change-description:before`,
      JSON.stringify(persistedAttachments(beforeAttachments)),
    );
    localStorage.setItem(
      `pd-ecr-before-after-attachments:${recordId}:change-description:after`,
      JSON.stringify(persistedAttachments(afterAttachments)),
    );
  };

  const submitLeaderApprovalMutation = useMutation({
    mutationFn: () => {
      const title = newChange.title.trim();
      // Client-side pre-check of required fields, so users see what's missing
      // before the round-trip. product/customer/title/product_no/reason/
      // description/departments are also re-validated by the backend.
      // change_source is enforced on the client only for now — the backend
      // does not yet include it in its required-field check.
      const requiredValues: Record<string, unknown> = {
        product: newChange.product,
        customer_project: newChange.customer,
        change_title: title,
        product_no: newChange.productNo || newChange.product,
        change_source: newChange.source,
        change_reason: newChange.reason,
        change_description: newChange.description,
        affected_departments: newChange.departments,
      };
      const missing = Object.entries(requiredValues)
        .filter(([, value]) =>
          Array.isArray(value)
            ? value.length === 0
            : !String(value ?? "").trim(),
        )
        .map(([field]) => pdEcrFieldLabel(field));
      if (missing.length > 0) {
        throw new Error(`请补齐必填项：${missing.join("、")}`);
      }
      if (!newChange.initiatorConfirmed) {
        throw new Error("请先由发起人本人完成确认");
      }
      return submitPdEcrForApproval({
        title,
        initiator: newChange.initiator,
        customer_project: newChange.customer || "PD-ECR Platform",
        product_no: newChange.productNo || newChange.product || undefined,
        part_no: newChange.partNumber || undefined,
        target_close_date: newChange.targetCloseDate || undefined,
        form_data: {
          nr: newChange.nr,
          dc_no: newChange.nr,
          title,
          changeTitle: title,
          source: newChange.source,
          change_source: newChange.source,
          reason: newChange.reason,
          change_reason: newChange.reason,
          department: currentUser?.department || "",
          initiator: newChange.initiator,
          date: newChange.date,
          product: newChange.product,
          product_no: newChange.productNo || newChange.product,
          customer: newChange.customer,
          customer_project: newChange.customer,
          component_no: newChange.partNumber,
          part_no: newChange.partNumber,
          partNumber: newChange.partNumber,
          sample_type: newChange.sampleType,
          changeSummary: newChange.description,
          change_proposal: newChange.description,
          departments: newChange.departments,
          affected_departments: newChange.departments.join(", "),
          target_close_date: newChange.targetCloseDate,
          initiatorConfirmed: newChange.initiatorConfirmed,
          initiator_confirmed: newChange.initiatorConfirmed,
          leaderConfirmed: false,
          leader_confirmed: false,
          before_attachments: persistedAttachments(beforeAttachments),
          beforeAttachments: persistedAttachments(beforeAttachments),
          after_attachments: persistedAttachments(afterAttachments),
          afterAttachments: persistedAttachments(afterAttachments),
          before_attachment_note: newChange.beforeAttachmentNote,
          beforeAttachmentNote: newChange.beforeAttachmentNote,
          after_attachment_note: newChange.afterAttachmentNote,
          afterAttachmentNote: newChange.afterAttachmentNote,
        },
      });
    },
    onSuccess: (response) => {
      setLeaderSubmitMessage(
        response.approval_task.approver_email
          ? `已提交给 ${response.approval_task.approver_name || response.approval_task.approver_email}，对方可在 My Tasks 的 Manager Approvals 中确认。`
          : "已提交领导确认，但未解析到审批人；请检查发起人部门是否配置 department_leader。",
      );
      setDraftStatus("已提交给发起人领导确认，等待领导在 My Tasks 审批。");
    },
    onError: (error) => {
      const missing = extractPdEcrMissingFields(error);
      if (missing.length > 0) {
        setLeaderSubmitMessage(
          `提交失败，缺少必填项：${missing.map(pdEcrFieldLabel).join("、")}`,
        );
        return;
      }
      setLeaderSubmitMessage(
        error instanceof Error ? error.message : "提交给领导确认失败",
      );
    },
  });

  const approveReviewMutation = useMutation({
    mutationFn: () => {
      if (!reviewCaseId) throw new Error("未找到审批 case");
      return approvePdEcrCase(reviewCaseId);
    },
    onSuccess: (response) => {
      updateNewChange("leaderConfirmed", true);
      setReviewCaseStatus("generated");
      const notification = response.notification;
      const mailMessage =
        notification?.status === "sent"
          ? `系统已邮件通知 ${notification.recipient_email || "对应负责人"}。`
          : notification?.status === "failed"
            ? `审批已通过，但邮件发送失败：${notification.error_message || "请检查 SMTP 配置或收件人邮箱"}。`
            : "";
      setReviewMessage(
        ["已完成领导审批。", mailMessage, "你可以回到 My Tasks 查看状态。"]
          .filter(Boolean)
          .join(""),
      );
      setDraftStatus("领导审批已通过。");
    },
    onError: (error) => {
      setReviewMessage(requestErrorMessage(error, "审批失败"));
    },
  });

  const rejectReviewMutation = useMutation({
    mutationFn: (reason: string) => {
      if (!reviewCaseId) throw new Error("未找到审批 case");
      return rejectPdEcrCase(reviewCaseId, reason);
    },
    onSuccess: () => {
      setReviewCaseStatus("changes_requested");
      setReviewMessage("已退回给发起人补充。你可以回到 My Tasks 查看状态。");
      setDraftStatus("领导审批已退回。");
    },
    onError: (error) => {
      setReviewMessage(requestErrorMessage(error, "退回失败"));
    },
  });

  const rejectSubmittedChange = () => {
    const reason = window.prompt("请输入退回原因", "请补充变更说明或附件");
    if (reason === null) return;
    rejectReviewMutation.mutate(reason);
  };

  const handleNextStep = () => {
    const title = newChange.title.trim();
    if (!title) {
      setDraftStatus("请先填写变更名称");
      return;
    }
    if (!canContinue) {
      setDraftStatus("请先完成发起人确认和发起人的领导确认");
      return;
    }

    // Write form data to localStorage (existing draft save)
    const draftData = {
      nr: newChange.nr,
      dc_no: newChange.nr,
      title,
      changeTitle: title,
      source: newChange.source,
      reason: newChange.reason,
      department: "",
      initiator: newChange.initiator,
      date: newChange.date,
      product: newChange.product,
      productNo: newChange.productNo,
      customer: newChange.customer,
      partNumber: newChange.partNumber,
      sampleType: newChange.sampleType,
      changeSummary: newChange.description,
      notChange: "",
      departments: newChange.departments,
      initiatorConfirmed: newChange.initiatorConfirmed,
      leaderConfirmed: newChange.leaderConfirmed,
      beforeAttachments: persistedAttachments(beforeAttachments),
      afterAttachments: persistedAttachments(afterAttachments),
      beforeAttachmentNote: newChange.beforeAttachmentNote,
      afterAttachmentNote: newChange.afterAttachmentNote,
    };
    const recordId = `pd-ecr-${Date.now()}`;
    localStorage.setItem(
      `pd-ecr-change-description-draft:${recordId}:change-description`,
      JSON.stringify(draftData),
    );

    // Save seed result (existing pattern)
    const seedData: Record<string, unknown> = {
      source: newChange.source,
      change_source: newChange.source,
      nr: newChange.nr,
      dc_no: newChange.nr,
      title,
      change_title: title,
      reason: newChange.reason,
      change_reason: newChange.reason,
      product: newChange.product,
      product_no: newChange.productNo || newChange.product,
      customer: newChange.customer,
      customer_project: newChange.customer,
      component_no: newChange.partNumber,
      part_no: newChange.partNumber,
      sample_type: newChange.sampleType,
      initiator: newChange.initiator,
      date: newChange.date,
      change_proposal: newChange.description,
      affected_departments: newChange.departments.join(", "),
      target_close_date: newChange.targetCloseDate,
      initiator_confirmed: newChange.initiatorConfirmed,
      leader_confirmed: newChange.leaderConfirmed,
      before_attachments: persistedAttachments(beforeAttachments),
      after_attachments: persistedAttachments(afterAttachments),
      before_attachment_note: newChange.beforeAttachmentNote,
      after_attachment_note: newChange.afterAttachmentNote,
    };
    const seedModule: PdEcrModule = {
      id: "change-description",
      title: "Change Description",
      summary: newChange.description || title,
      data: seedData,
    };
    const seedResult = buildGeneratedResult({
      message: "seed",
      draft_id: recordId,
      modules: [seedModule],
      url: undefined,
      approval_lead_days: 12,
    });
    seedResult.relatedCases = [recordId, ...seedResult.relatedCases];
    saveGeneratedResult(seedResult);
    persistBeforeAfterAttachments(recordId);

    setDraftStatus("Draft prepared. Continue with impact and execution plan.");
    navigate({ to: "/pd-ecr/content" });
  };

  const generateMutation = useMutation({
    mutationFn: () => generatePdEcrReport(buildGenerationInput(newChange)),
    onSuccess: (response) => {
      const result = buildGeneratedResult(response);
      // Preserve pre-filled change-description data — user input takes priority over AI markdown
      try {
        const prev = loadGeneratedResult();
        const prevCd = prev?.modules?.find(
          (m: { id: string }) => m.id === "change-description",
        );
        if (prevCd?.data) {
          const aiCd = result.modules.find(
            (m) => m.id === "change-description",
          );
          if (aiCd) {
            aiCd.data = { ...aiCd.data, ...prevCd.data };
          }
        }
      } catch {
        /* best effort */
      }
      saveGeneratedResult(result);

      // Create DB case in background (non-blocking)
      const caseNo = response.draft_id || `PD-ECR-${Date.now()}`;
      createPdEcrCase({
        case_no: caseNo,
        title:
          newChange.title.trim() ||
          newChange.description ||
          "New PD-ECR Change Request",
        status: "draft",
        source_type: "ai_generated",
        dc_no: newChange.nr || `PD-ECR-${Date.now()}`,
        initiator: newChange.initiator || newChange.source || "AI Generated",
        customer_project: newChange.customer || "PD-ECR Platform",
        product_no: newChange.productNo || newChange.product || undefined,
        part_no: newChange.partNumber || undefined,
        sample_type: newChange.sampleType || undefined,
        target_close_date: newChange.targetCloseDate || undefined,
        change_type: "Engineering Change",
      }).catch(() => {
        // Case creation is non-blocking — draft is already saved locally
      });
    },
    onError: () => {
      const result = buildGeneratedResult({
        message: "fallback",
        modules: undefined,
      });
      saveGeneratedResult(result);
    },
  });

  const updateNewChange = <K extends keyof NewChangeForm>(
    key: K,
    value: NewChangeForm[K],
  ) => {
    if (
      key === "title" &&
      typeof value === "string" &&
      value.trim() &&
      draftStatus === "请先填写变更名称"
    ) {
      setDraftStatus(null);
    }
    if (
      (key === "initiatorConfirmed" || key === "leaderConfirmed") &&
      value === true &&
      draftStatus === "请先完成发起人确认和发起人的领导确认"
    ) {
      setDraftStatus(null);
    }
    setNewChange((current) => {
      const next = { ...current, [key]: value };
      if (key === "initiator" && value !== current.initiator) {
        next.initiatorConfirmed = false;
        next.leaderConfirmed = false;
      }
      return next;
    });
  };

  return (
    <div className="page-shell w-full">
      <div className="mx-auto flex w-full max-w-7xl min-w-0 flex-col gap-3">
        <header className="enterprise-panel overflow-hidden">
          <div className="border-b border-slate-200 bg-white px-4 py-2">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <div className="flex flex-wrap items-center gap-2">
                <span className="inline-flex h-7 items-center rounded-md border border-slate-200 bg-slate-50 px-2.5 text-xs font-bold uppercase tracking-[0.08em] text-slate-500">
                  PD-ECR
                </span>
                <span
                  className={`inline-flex h-7 items-center rounded-md border px-2.5 text-xs font-semibold ${
                    statusTone === "emerald"
                      ? "border-emerald-200 bg-emerald-50 text-emerald-700"
                      : statusTone === "amber"
                        ? "border-amber-200 bg-amber-50 text-amber-700"
                        : "border-blue-200 bg-blue-50 text-blue-700"
                  }`}
                >
                  {workspaceStatus}
                </span>
                {reviewCaseId ? (
                  <span className="inline-flex h-7 items-center rounded-md border border-slate-200 bg-white px-2.5 text-xs font-semibold text-slate-600">
                    Review case
                  </span>
                ) : null}
              </div>
              <div className="flex flex-wrap items-center gap-2">
                <Button
                  type="button"
                  variant="outline"
                  className="h-9 rounded-md bg-white text-sm hover:border-blue-300 hover:bg-blue-50"
                  onClick={() => navigate({ to: "/pd-ecr/tasks" })}
                >
                  <ClipboardList className="size-4" />
                  My Tasks
                </Button>
                <Button
                  type="button"
                  variant="outline"
                  className="h-9 rounded-md bg-white text-sm hover:border-blue-300 hover:bg-blue-50"
                  onClick={() =>
                    navigate({ to: "/pd-ecr/cases", search: { view: "all" } })
                  }
                >
                  <Database className="size-4" />
                  All Cases
                </Button>
                <Button
                  type="button"
                  variant="outline"
                  className="h-9 rounded-md bg-white text-sm hover:border-blue-300 hover:bg-blue-50"
                  onClick={() => navigate({ to: "/pd-ecr/dashboard" })}
                >
                  <FolderKanban className="size-4" />
                  Dashboard
                </Button>
                <PdEcrProcessFlowButton />
              </div>
            </div>
            <div className="mt-2 flex flex-col gap-2 border-t border-slate-100 pt-2 lg:flex-row lg:items-center lg:justify-between">
              <h1 className="min-w-0 truncate text-xl font-semibold tracking-tight text-slate-950">
                {newChange.title.trim() || "New PD-ECR Change"}
              </h1>
              <div className="flex shrink-0 flex-wrap items-center gap-2 lg:justify-end">
                <label className="flex h-9 items-center gap-2 rounded-md border border-slate-200 bg-slate-50/80 px-2.5 shadow-sm transition-colors focus-within:border-blue-300 focus-within:bg-white focus-within:ring-2 focus-within:ring-blue-100">
                  <span className="text-xs font-semibold uppercase tracking-wider text-slate-400">
                    Nr
                  </span>
                  <Input
                    aria-label="Nr"
                    value={newChange.nr}
                    onChange={(event) =>
                      updateNewChange("nr", event.target.value)
                    }
                    className="h-7 w-32 border-0 bg-transparent px-0 text-sm font-semibold text-slate-800 shadow-none focus-visible:ring-0"
                  />
                </label>
                <label className="flex h-9 items-center gap-2 rounded-md border border-slate-200 bg-slate-50/80 px-2.5 shadow-sm transition-colors focus-within:border-blue-300 focus-within:bg-white focus-within:ring-2 focus-within:ring-blue-100">
                  <span className="whitespace-nowrap text-xs font-semibold uppercase tracking-wider text-slate-400">
                    Target close date
                  </span>
                  <input
                    type="date"
                    value={newChange.targetCloseDate}
                    onChange={(e) =>
                      updateNewChange("targetCloseDate", e.target.value)
                    }
                    className="h-7 w-36 border-0 bg-transparent px-0 text-sm font-semibold text-slate-800 outline-none"
                  />
                </label>
              </div>
            </div>
          </div>
          
        </header>

        <main className="min-w-0">
          <div className="flex min-w-0 flex-col">
            <WorkPanel
              eyebrow="New creation"
              className="min-w-0"
              hideHeader
            >
              <div className="enterprise-field-surface-muted mt-2 !px-3 !py-2">
                <div className="grid gap-2 sm:grid-cols-3">
                <FormField
                  label="产品"
                  value={newChange.product}
                  onChange={(value) => updateNewChange("product", value)}
                  required
                />
                <FormField
                  label="客户/平台"
                  value={newChange.customer}
                  onChange={(value) => updateNewChange("customer", value)}
                  required
                />
                <FormField
                  label="变更发起人"
                  value={newChange.initiator}
                  onChange={(value) => updateNewChange("initiator", value)}
                />
                </div>
              </div>

              <div className="enterprise-field-surface mt-2 !px-3 !py-2">
                <FormField
                  label="变更名称"
                  value={newChange.title}
                  onChange={(value) => updateNewChange("title", value)}
                  placeholder="例如：JIM 493 C-sample release / 螺栓供应商切换"
                  required
                />
              </div>

              <div className="enterprise-field-surface-muted mt-2 !px-3 !py-2">
                <div className="grid gap-2 sm:grid-cols-3">
                <FormField
                  label="产品号"
                  value={newChange.productNo}
                  onChange={(value) => updateNewChange("productNo", value)}
                />
                <FormField
                  label="零部件号"
                  value={newChange.partNumber}
                  onChange={(value) => updateNewChange("partNumber", value)}
                />
                <SelectField
                  label="样品类型"
                  value={newChange.sampleType}
                  onChange={(value) => updateNewChange("sampleType", value)}
                  options={SAMPLE_TYPE_OPTIONS}
                />
                </div>
              </div>

              {/* 变更来源 — 多选 + 一行一个 + 各自备注 */}
              <section className="enterprise-field-surface mt-2 !px-3 !py-2">
                <label className="block space-y-1">
                  <span className="enterprise-field-label">
                    变更来源
                    <RequiredMark />
                  </span>
                  <SourceMultiSelect
                    selected={newChange.source}
                    onChange={(value) => updateNewChange("source", value)}
                  />
                </label>
                {(() => {
                  const selectedValues = newChange.source
                    .split(",")
                    .map((s) => s.trim())
                    .filter(Boolean);
                  if (!selectedValues.length) return null;
                  const notes = parseSourceNotes(newChange.sourceNote);
                  return (
                    <div className="enterprise-field-surface-muted mt-2 space-y-1 !px-3 !py-2">
                      {selectedValues.map((val) => {
                        const label =
                          CHANGE_SOURCE_OPTIONS.find((o) => o.value === val)
                            ?.label || val;
                        return (
                          <div key={val} className="flex items-center gap-2">
                            <span className="w-40 shrink-0 truncate text-sm font-medium text-slate-700">
                              {label}
                            </span>
                            <input
                              type="text"
                              placeholder="备注..."
                              value={notes[val] || ""}
                              onChange={(e) => {
                                const next = {
                                  ...notes,
                                  [val]: e.target.value,
                                };
                                updateNewChange(
                                  "sourceNote",
                                  serializeSourceNotes(next),
                                );
                              }}
                              className="enterprise-input !h-8 flex-1"
                            />
                          </div>
                        );
                      })}
                    </div>
                  );
                })()}
              </section>

              <section className="enterprise-field-surface mt-2 !px-3 !py-1.5">
                <label className="block space-y-1">
                  <span className="flex items-baseline justify-between gap-2">
                    <span className="enterprise-field-label">
                      变更背景原因
                      <RequiredMark />
                    </span>
                    <span className="text-[11px] tabular-nums text-slate-400">
                      {newChange.reason.trim().length} 字
                    </span>
                  </span>
                  <textarea
                    value={newChange.reason}
                    onChange={(event) =>
                      updateNewChange("reason", event.target.value)
                    }
                    placeholder="为什么需要变更：客户要求、质量问题、供应风险、成本或工艺优化等背景。"
                    className="enterprise-textarea min-h-14 !py-1.5"
                  />
                </label>
              </section>

              <div className="mt-2">
                <DepartmentCheckboxGroup
                  selected={newChange.departments}
                  onChange={(value) => updateNewChange("departments", value)}
                  className="min-h-full"
                />
              </div>

              <section className="enterprise-field-surface mt-2 !px-3 !py-1.5">
                <label className="block space-y-1">
                  <span className="flex items-baseline justify-between gap-2">
                    <span className="enterprise-field-label">
                      变更描述
                      <RequiredMark />
                    </span>
                    <span className="text-[11px] tabular-nums text-slate-400">
                      {newChange.description.trim().length} 字
                    </span>
                  </span>
                  <textarea
                    value={newChange.description}
                    onChange={(event) =>
                      updateNewChange("description", event.target.value)
                    }
                    placeholder="当前状态、拟变更内容、影响范围与期望结果。"
                    className="enterprise-textarea min-h-14 !py-1.5"
                  />
                </label>
              </section>

              <section className="enterprise-field-surface mt-2 !px-3 !py-2">
                <button
                  type="button"
                  onClick={() => setIsAttachmentExpanded((value) => !value)}
                  className="flex w-full flex-col gap-2 rounded-lg px-1 py-1 text-left transition hover:bg-white sm:flex-row sm:items-center sm:justify-between"
                  aria-expanded={isAttachmentExpanded}
                >
                  <div>
                    <h3 className="text-base font-semibold text-slate-800">
                      Before / After 附件
                    </h3>
                    <p className="mt-1 text-sm text-slate-500">
                      {beforeAttachments.length} before ·{" "}
                      {afterAttachments.length} after
                    </p>
                  </div>
                  <span className="rounded-sm border border-slate-200 bg-white px-2.5 py-1 text-sm font-semibold text-slate-600">
                    {isAttachmentExpanded ? "收起" : "展开"}
                  </span>
                </button>

                {isAttachmentExpanded ? (
                  <div className="mt-3 grid gap-3 lg:grid-cols-2">
                    <NewChangeAttachmentPanel
                      title="Before"
                      attachments={beforeAttachments}
                      note={newChange.beforeAttachmentNote}
                      onAdd={(files) => addAttachments("before", files)}
                      onRemove={(index) => removeAttachment("before", index)}
                      onNoteChange={(value) =>
                        updateNewChange("beforeAttachmentNote", value)
                      }
                    />
                    <NewChangeAttachmentPanel
                      title="After"
                      attachments={afterAttachments}
                      note={newChange.afterAttachmentNote}
                      onAdd={(files) => addAttachments("after", files)}
                      onRemove={(index) => removeAttachment("after", index)}
                      onNoteChange={(value) =>
                        updateNewChange("afterAttachmentNote", value)
                      }
                    />
                  </div>
                ) : null}
              </section>

              <section className="mt-2 flex flex-wrap items-center justify-end gap-2 rounded-md border border-slate-200 bg-slate-50/80 px-3 py-2">
                <CompactConfirmationCheck
                  label="发起人确认"
                  checked={newChange.initiatorConfirmed}
                  disabled={!canConfirmInitiator}
                  disabledReason={
                    initiatorName
                      ? `只能由发起人本人确认。当前登录用户：${userLabel || "未登录"}`
                      : "请先填写变更发起人。"
                  }
                  onChange={(checked) =>
                    updateNewChange("initiatorConfirmed", checked)
                  }
                />
                <CompactConfirmationCheck
                  label="领导确认"
                  checked={newChange.leaderConfirmed}
                  disabled={!canConfirmLeader}
                  disabledReason={
                    isManagerApprovalReview
                      ? undefined
                      : initiatorName
                      ? "只能由发起人所在部门的 department_leader 确认，且不能由发起人本人确认。"
                      : "请先填写变更发起人。"
                  }
                  onChange={(checked) =>
                    updateNewChange("leaderConfirmed", checked)
                  }
                />
                <span className="text-xs font-medium text-slate-500">
                  {newChange.initiatorConfirmed && newChange.leaderConfirmed
                    ? "确认完成"
                    : "等待确认"}
                </span>
              </section>

              {reviewCaseId ? (
                <section className="mt-2 rounded-md border border-emerald-100 bg-emerald-50/70 p-3">
                  <div className="flex flex-col gap-2 lg:flex-row lg:items-center lg:justify-between">
                    <div>
                      <p className="text-sm font-semibold text-emerald-900">
                        领导审批当前新建变更表单
                      </p>
                      <p className="mt-1 text-xs text-slate-500">
                        Case: {reviewCaseId}{reviewTaskId ? ` · Task: ${reviewTaskId}` : ""}{reviewCaseStatus ? ` · Status: ${reviewCaseStatus}` : ""}
                      </p>
                      {reviewMessage ? (
                        <p className="mt-2 text-sm font-medium text-emerald-800">
                          {reviewMessage}
                        </p>
                      ) : null}
                    </div>
                    {isReviewClosed ? (
                      <div className="rounded-md border border-slate-200 bg-white px-3 py-2 text-sm font-semibold text-slate-600">
                        已处理，只读查看
                      </div>
                    ) : (
                      <div className="flex flex-col gap-2 sm:flex-row">
                        <Button
                          type="button"
                          variant="outline"
                          className="border-rose-200 text-rose-700 hover:bg-rose-50"
                          disabled={approveReviewMutation.isPending || rejectReviewMutation.isPending}
                          onClick={rejectSubmittedChange}
                        >
                          退回补充
                        </Button>
                        <Button
                          type="button"
                          className="bg-emerald-700 hover:bg-emerald-800"
                          disabled={
                            approveReviewMutation.isPending ||
                            rejectReviewMutation.isPending ||
                            (!isManagerApprovalReview && !newChange.leaderConfirmed)
                          }
                          onClick={() => approveReviewMutation.mutate()}
                        >
                          {approveReviewMutation.isPending ? "Approving..." : "确认通过"}
                        </Button>
                      </div>
                    )}
                  </div>
                </section>
              ) : (
                <section className="mt-2 rounded-md border border-blue-100 bg-blue-50/70 p-3">
                  <div className="flex flex-col gap-2 lg:flex-row lg:items-center lg:justify-between">
                    <div>
                      <p className="text-sm font-semibold text-blue-900">
                        Submit to leader
                      </p>
                      {leaderSubmitMessage ? (
                        <p className="mt-2 text-sm font-medium text-blue-800">
                          {leaderSubmitMessage}
                        </p>
                      ) : null}
                    </div>
                    <Button
                      type="button"
                      className="w-full bg-blue-700 hover:bg-blue-800 lg:w-fit"
                      disabled={
                        submitLeaderApprovalMutation.isPending ||
                        !newChange.initiatorConfirmed ||
                        !canConfirmInitiator
                      }
                      onClick={() => submitLeaderApprovalMutation.mutate()}
                    >
                      {submitLeaderApprovalMutation.isPending
                        ? "Submitting..."
                        : "Submit to leader"}
                    </Button>
                  </div>
                </section>
              )}

              {/* 操作按钮 */}
              <div className="mt-3 flex flex-wrap items-center justify-between gap-2 rounded-md border border-slate-200 bg-slate-50/80 px-3 py-2">
                {draftStatus ? (
                  <p
                    className={`text-sm font-medium ${
                      draftStatus === "请先填写变更名称" ||
                      draftStatus === "请先完成发起人确认和发起人的领导确认"
                        ? "text-red-600"
                        : "text-blue-700"
                    }`}
                  >
                    {draftStatus}
                  </p>
                ) : !canContinue ? (
                  <p className="text-sm font-medium text-slate-500">
                    勾选发起人确认和领导确认后，才能进入后续流程。
                  </p>
                ) : (
                  <span />
                )}
                <Button
                  type="button"
                  onClick={handleNextStep}
                  disabled={generateMutation.isPending || !canContinue}
                  className="h-10 shrink-0 rounded-md bg-blue-600 px-5 text-sm font-semibold text-white hover:bg-blue-700 transition-all active:scale-[0.98]"
                >
                  {generateMutation.isPending ? "处理中..." : "下一步"}
                  <ArrowRight className="size-4" />
                </Button>
              </div>
            </WorkPanel>
          </div>
        </main>
      </div>
    </div>
  );
}
