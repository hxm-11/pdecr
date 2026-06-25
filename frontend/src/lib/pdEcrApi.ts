import axios from "axios"

export const API_BASE_URL =
  import.meta.env.VITE_API_URL || "http://localhost:8000"

export function resolvePdEcrAssetUrl(url?: string) {
  if (!url) return ""

  if (/^(https?:)?\/\//i.test(url) || url.startsWith("data:")) {
    return url
  }

  return `${API_BASE_URL.replace(/\/$/, "")}/${url.replace(/^\//, "")}`
}

function getAccessToken() {
  return (
    localStorage.getItem("access_token") ||
    localStorage.getItem("accessToken") ||
    localStorage.getItem("token")
  )
}

const pdEcrApi = axios.create({
  baseURL: API_BASE_URL,
})

pdEcrApi.interceptors.request.use((config) => {
  const token = getAccessToken()

  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }

  return config
})

export type PdEcrInput = {
  dc_no?: string
  date?: string
  customer_project?: string
  mcr_no?: string
  product_no?: string
  part_no?: string
  component_no?: string
  change_type?: string
  initiator?: string
  change_source?: string
  reason?: string
  change_reason?: string
  change_description?: string
  target_close_date?: string
  current_design?: string
  change_proposal?: string
  remarks?: string
  top_k?: number
}

export type PdEcrModule = {
  id?: string
  module_id?: string
  title?: string
  subtitle?: string
  summary?: string
  description?: string
  content?: unknown
  source_cases?: string[]
  source_files?: string[]
  needs_human_input?: boolean
  warnings?: string[]
  data?: Record<string, unknown>
}

export type PdEcrModules = Record<string, PdEcrModule | undefined>

export type PdEcrHistoryResponse = {
  message?: string
  results_count?: number
  approval_results_count?: number
  approval_test_result?: Record<string, unknown>
  approval_debug_lines?: string[]
  results?: unknown[]
  approval_results?: unknown[]
  related_cases?: string[]
  matched_files?: string[]
  rag_context?: string
  rag_context_preview?: string
  modules?: PdEcrModules | PdEcrModule[]
}

export type PdEcrCaseRecord = Record<string, unknown>

export type PdEcrCaseListResponse = {
  source?: "database" | string
  cases?: PdEcrCaseRecord[]
}

export type PdEcrKnowledgeBaseStatus = {
  knowledge_files_on_disk: number
  knowledge_dir: string
  vector_store: {
    index_path: string
    meta_path: string
    index_exists: boolean
    meta_exists: boolean
    index_size_bytes?: number
    meta_size_bytes?: number
    index_updated_at?: string | null
    meta_updated_at?: string | null
    chunk_files: number
  }
  staged_documents: {
    pending: number
    confirmed: number
    total: number
    rejected?: number
    [key: string]: number | undefined
  }
  parser_capabilities: Record<string, boolean>
  last_rebuild?: {
    last_rebuild_at?: string
    success?: boolean
    total_documents?: number
    error?: string
  } | null
}

export type PdEcrCaseStatus =
  | "draft"
  | "submitted"
  | "department_confirmation"
  | "in_review"
  | "leader_review"
  | "changes_requested"
  | "approved"
  | "implementation"
  | "closed"
  | "cancelled"

export type PdEcrCase = {
  id: string
  case_no: string
  title?: string
  status: PdEcrCaseStatus
  source_type?: string
  is_historical?: boolean
  dc_no?: string | null
  mcr_no?: string | null
  customer_project?: string | null
  product_no?: string | null
  part_no?: string | null
  component_no?: string | null
  change_type?: string | null
  sample_type?: string | null
  initiator?: string | null
  target_close_date?: string | null
  created_at?: string | null
  updated_at?: string | null
  closed_at?: string | null
}

export type PdEcrPermissionFlags = {
  can_edit?: boolean
  can_assign?: boolean
  can_regenerate?: boolean
  can_send_reminder?: boolean
  can_review?: boolean
  can_close?: boolean
}

export type PdEcrDbModule = {
  id: string
  case_id: string
  module_id: string
  title?: string
  content_json?: Record<string, unknown>
  content_md?: string | null
  source_cases?: string[]
  source_files?: string[]
  needs_human_input?: boolean
  status?: string
  version: number
  assignee_id?: string | null
  assignee_email?: string | null
  assignee_name?: string | null
  department?: string | null
  due_date?: string | null
  reminder_policy?: Record<string, unknown>
  last_reminded_at?: string | null
  permissions?: PdEcrPermissionFlags
  data?: Record<string, unknown>
}

export type PdEcrCaseDetailResponse = {
  case: PdEcrCase
  modules: PdEcrDbModule[]
}

export type PdEcrCaseCreatePayload = {
  case_no: string
  title?: string
  status?: PdEcrCaseStatus
  source_type?: string
  is_historical?: boolean
  dc_no?: string
  mcr_no?: string
  customer_project?: string
  product_no?: string
  part_no?: string
  change_type?: string
  sample_type?: string
  initiator?: string
  target_close_date?: string
}

export type PdEcrModuleUpdatePayload = {
  title?: string
  content_json?: Record<string, unknown>
  content_md?: string
  source_cases?: string[]
  source_files?: string[]
  needs_human_input?: boolean
  status?: string
  expected_version?: number
}

export type PdEcrImportResponse = {
  sources_seen: number
  created_cases: number
  updated_sources: number
  skipped_sources: number
  warnings_by_file: Record<string, string[]>
}

export type PdEcrRetrieveResponse = {
  query_input: Record<string, unknown>
  top_k: number
  results: PdEcrSimilarCase[]
}

export type PdEcrGenerateResponse = {
  message?: string
  url?: string
  draft_id?: string
  draft_status?: string
  input_snapshot?: Record<string, unknown>
  similar_cases?: PdEcrSimilarCase[]
  generated_at?: string
  modules?: PdEcrModules | PdEcrModule[]
  llm_result?: Record<string, unknown>
  approval_lead_days?: number
  impact?: string
  implementation?: string
  example_of_affected_actions?: string
  revision_history?: string
}

export type PdEcrSimilarCase = {
  rank?: number
  case_id?: string
  dc_no?: string
  change_type?: string
  matched_fields?: string[]
  similarity_score?: number
  similarity_reason?: string
  source_file?: string
  module_summary?: string
  source_cases?: string[]
  source_files?: string[]
  retrieval_mode?: string
  retrieval_context?: Record<string, unknown>
}

export type PdEcrModuleDraftPayload = {
  record_id: string
  module_id: string
  data: Record<string, unknown>
  title?: string
}

export type PdEcrModuleDraftResponse = {
  id?: string
  record_id: string
  module_id: string
  title?: string
  data: Record<string, unknown> | null
  created_at?: string | null
  updated_at?: string | null
}

export type PdEcrDraftListItem = {
  record_id: string
  module_id: string
  title: string
  data: Record<string, unknown> | null
  created_at?: string | null
  updated_at?: string | null
}

export type PdEcrDraftListResponse = {
  drafts: PdEcrDraftListItem[]
}

export type PdEcrGeneratedCaseResponse = {
  case: PdEcrCase
  modules: PdEcrDbModule[]
  draft_id?: string
  draft_status?: string
  warnings?: string[]
  redirect_to?: string
}

export type PdEcrGeneratedModulePreview = {
  case_id: string
  module_id: string
  title?: string
  content_md: string
  content_json?: Record<string, unknown>
  source_cases?: string[]
  source_files?: string[]
  needs_human_input?: boolean
}

export type PdEcrModuleAssignmentPayload = {
  assignee_id?: string | null
  assignee_email?: string | null
  assignee_name?: string | null
  department?: string | null
  due_date?: string | null
  reminder_policy?: Record<string, unknown>
  send_assignment_email?: boolean
}

export type PdEcrDepartmentWorkflowTask = {
  id: string
  case_id: string
  department: string
  status: string
  assignee_id?: string | null
  assignee_email?: string | null
  assignee_name?: string | null
  impact_result?: string | null
  impact_remark?: string | null
  action_required?: string | null
  confirmed_by_id?: string | null
  confirmed_by_name?: string | null
  confirmed_at?: string | null
  due_date?: string | null
}

export type PdEcrLeaderReviewWorkflowTask = {
  id: string
  case_id: string
  department: string
  status: string
  reviewer_id?: string | null
  reviewer_email?: string | null
  reviewer_name?: string | null
  review_comment?: string | null
  signature_name?: string | null
  reviewed_at?: string | null
}

export type PdEcrWorkflowState = {
  case: PdEcrCase
  department_tasks: PdEcrDepartmentWorkflowTask[]
  leader_review_tasks: PdEcrLeaderReviewWorkflowTask[]
}

export type PdEcrWorkflowSubmitPayload = {
  selected_departments: string[]
  assignees: Record<
    string,
    {
      assignee_id?: string | null
      assignee_email: string
      assignee_name?: string | null
    }
  >
}

export type PdEcrDepartmentTaskConfirmPayload = {
  impact_result: string
  impact_remark?: string | null
  action_required?: string | null
}

export type PdEcrLeaderTaskReviewPayload = {
  decision: "approved" | "rejected" | "changes_requested"
  review_comment?: string | null
  signature_name?: string | null
}

export async function searchPdEcrHistory(
  data: PdEcrInput,
): Promise<PdEcrHistoryResponse> {
  const res = await pdEcrApi.post<PdEcrHistoryResponse>(
    "/api/v1/pd-ecr/history/search",
    data,
  )
  return res.data
}

export async function listPdEcrCases(): Promise<PdEcrCaseListResponse> {
  const res = await pdEcrApi.get<PdEcrCaseListResponse>("/api/v1/pd-ecr/cases")
  return res.data
}

export async function getPdEcrKnowledgeBaseStatus(): Promise<PdEcrKnowledgeBaseStatus> {
  const res = await pdEcrApi.get<PdEcrKnowledgeBaseStatus>(
    "/api/v1/pd-ecr/knowledge-base/status",
  )
  return res.data
}

export async function createPdEcrCase(
  payload: PdEcrCaseCreatePayload,
): Promise<PdEcrCaseDetailResponse> {
  const res = await pdEcrApi.post<PdEcrCaseDetailResponse>(
    "/api/v1/pd-ecr/cases",
    payload,
  )
  return res.data
}

export async function getPdEcrCase(
  caseId: string,
): Promise<PdEcrCaseDetailResponse> {
  const res = await pdEcrApi.get<PdEcrCaseDetailResponse>(
    `/api/v1/pd-ecr/cases/${encodeURIComponent(caseId)}`,
  )
  return res.data
}

export async function updatePdEcrCase(
  caseId: string,
  payload: Partial<PdEcrCaseCreatePayload>,
): Promise<{ case: PdEcrCase }> {
  const res = await pdEcrApi.patch<{ case: PdEcrCase }>(
    `/api/v1/pd-ecr/cases/${encodeURIComponent(caseId)}`,
    payload,
  )
  return res.data
}

export async function transitionPdEcrCase(
  caseId: string,
  status: PdEcrCaseStatus,
): Promise<{ case: PdEcrCase }> {
  const res = await pdEcrApi.post<{ case: PdEcrCase }>(
    `/api/v1/pd-ecr/cases/${encodeURIComponent(caseId)}/transition`,
    { status },
  )
  return res.data
}

export async function updatePdEcrModule(
  caseId: string,
  moduleId: string,
  payload: PdEcrModuleUpdatePayload,
): Promise<{ module: PdEcrDbModule }> {
  const res = await pdEcrApi.patch<{ module: PdEcrDbModule }>(
    `/api/v1/pd-ecr/cases/${encodeURIComponent(caseId)}/modules/${encodeURIComponent(moduleId)}`,
    payload,
  )
  return res.data
}

export async function importHistoricalPdEcrCases(
  limit?: number,
): Promise<PdEcrImportResponse> {
  const res = await pdEcrApi.post<PdEcrImportResponse>(
    "/api/v1/pd-ecr/import/historical",
    { limit },
  )
  return res.data
}

export type PdEcrUploadResult = {
  status: string
  filename: string
  case_id: string
  case_no: string
  is_new: boolean
  parsed_by: string
  metadata: Record<string, unknown>
  content_preview: string
}

export async function uploadPdEcrFile(
  file: File,
): Promise<PdEcrUploadResult> {
  const formData = new FormData()
  formData.append("file", file)

  const res = await pdEcrApi.post<PdEcrUploadResult>(
    "/api/v1/pd-ecr/cases/upload-file",
    formData,
    {
      headers: { "Content-Type": "multipart/form-data" },
    },
  )
  return res.data
}

export async function retrievePdEcrSimilarCases(
  input: Record<string, unknown>,
  topK = 5,
): Promise<PdEcrRetrieveResponse> {
  const res = await pdEcrApi.post<PdEcrRetrieveResponse>(
    "/api/v1/pd-ecr/retrieve",
    { input, top_k: topK },
  )
  return res.data
}

export async function createPdEcrRequest(
  input: Record<string, unknown>,
): Promise<{ request_id: string; input: Record<string, unknown>; missing_fields: string[] }> {
  const res = await pdEcrApi.post<{
    request_id: string
    input: Record<string, unknown>
    missing_fields: string[]
  }>("/api/v1/pd-ecr/requests", input)
  return res.data
}

export async function generatePdEcrDraft(
  input: Record<string, unknown>,
  similarCases?: PdEcrSimilarCase[],
): Promise<PdEcrGenerateResponse> {
  const res = await pdEcrApi.post<PdEcrGenerateResponse>(
    "/api/v1/pd-ecr/generate-draft",
    { input, similar_cases: similarCases },
  )
  return res.data
}

export async function generatePdEcrEditableCase(
  input: Record<string, unknown>,
  similarCases?: PdEcrSimilarCase[],
): Promise<PdEcrGeneratedCaseResponse> {
  const res = await pdEcrApi.post<PdEcrGeneratedCaseResponse>(
    "/api/v1/pd-ecr/cases/generate-from-ai",
    { input, similar_cases: similarCases },
  )
  return res.data
}

export async function regeneratePdEcrModule(
  caseId: string,
  moduleId: string,
  instruction?: string,
): Promise<PdEcrGeneratedModulePreview> {
  const res = await pdEcrApi.post<PdEcrGeneratedModulePreview>(
    `/api/v1/pd-ecr/cases/${encodeURIComponent(caseId)}/modules/${encodeURIComponent(moduleId)}/regenerate`,
    { instruction },
  )
  return res.data
}

export async function applyGeneratedPdEcrModule(
  caseId: string,
  moduleId: string,
  generated: PdEcrGeneratedModulePreview,
  expectedVersion: number,
): Promise<{ module: PdEcrDbModule }> {
  const res = await pdEcrApi.post<{ module: PdEcrDbModule }>(
    `/api/v1/pd-ecr/cases/${encodeURIComponent(caseId)}/modules/${encodeURIComponent(moduleId)}/apply-generated`,
    { generated, expected_version: expectedVersion },
  )
  return res.data
}

export async function assignPdEcrModule(
  caseId: string,
  moduleId: string,
  payload: PdEcrModuleAssignmentPayload,
): Promise<{
  module: PdEcrDbModule
  notification?: Record<string, unknown> | null
}> {
  const res = await pdEcrApi.patch<{
    module: PdEcrDbModule
    notification?: Record<string, unknown> | null
  }>(
    `/api/v1/pd-ecr/cases/${encodeURIComponent(caseId)}/modules/${encodeURIComponent(moduleId)}/assignment`,
    payload,
  )
  return res.data
}

export async function sendPdEcrModuleReminder(
  caseId: string,
  moduleId: string,
): Promise<{ notification: Record<string, unknown> }> {
  const res = await pdEcrApi.post<{ notification: Record<string, unknown> }>(
    `/api/v1/pd-ecr/cases/${encodeURIComponent(caseId)}/modules/${encodeURIComponent(moduleId)}/send-reminder`,
  )
  return res.data
}

export async function getPdEcrWorkflow(
  caseId: string,
): Promise<PdEcrWorkflowState> {
  const res = await pdEcrApi.get<PdEcrWorkflowState>(
    `/api/v1/pd-ecr/cases/${encodeURIComponent(caseId)}/workflow`,
  )
  return res.data
}

export async function submitPdEcrWorkflow(
  caseId: string,
  payload: PdEcrWorkflowSubmitPayload,
): Promise<PdEcrWorkflowState> {
  const res = await pdEcrApi.post<PdEcrWorkflowState>(
    `/api/v1/pd-ecr/cases/${encodeURIComponent(caseId)}/workflow/submit`,
    payload,
  )
  return res.data
}

export async function confirmPdEcrDepartmentTask(
  taskId: string,
  payload: PdEcrDepartmentTaskConfirmPayload,
): Promise<PdEcrWorkflowState> {
  const res = await pdEcrApi.post<PdEcrWorkflowState>(
    `/api/v1/pd-ecr/workflow/department-tasks/${encodeURIComponent(taskId)}/confirm`,
    payload,
  )
  return res.data
}

export async function requestPdEcrDepartmentChanges(
  taskId: string,
  comment: string,
): Promise<PdEcrWorkflowState> {
  const res = await pdEcrApi.post<PdEcrWorkflowState>(
    `/api/v1/pd-ecr/workflow/department-tasks/${encodeURIComponent(taskId)}/request-changes`,
    { comment },
  )
  return res.data
}

export async function reviewPdEcrLeaderTask(
  taskId: string,
  payload: PdEcrLeaderTaskReviewPayload,
): Promise<PdEcrWorkflowState> {
  const res = await pdEcrApi.post<PdEcrWorkflowState>(
    `/api/v1/pd-ecr/workflow/leader-tasks/${encodeURIComponent(taskId)}/review`,
    payload,
  )
  return res.data
}

export async function exportPdEcrDraft(
  draftId: string,
  draft: PdEcrGenerateResponse,
  format: "html" | "csv" = "html",
): Promise<Record<string, unknown>> {
  const res = await pdEcrApi.post<Record<string, unknown>>(
    "/api/v1/pd-ecr/export",
    { draft_id: draftId, draft, format },
  )
  return res.data
}

export async function exportPdEcrCase(
  caseId: string,
  format: "html" | "json" = "html",
): Promise<Record<string, unknown>> {
  const res = await pdEcrApi.post<Record<string, unknown>>(
    "/api/v1/pd-ecr/export",
    { format },
    { params: { case_id: caseId } },
  )
  return res.data
}

export function buildPdEcrCollaborationUrl(caseId: string, userLabel: string) {
  const wsBase = API_BASE_URL.replace(/^http/i, "ws").replace(/\/$/, "")
  const params = new URLSearchParams({
    session_id: crypto.randomUUID(),
    user_label: userLabel,
  })
  return `${wsBase}/api/v1/pd-ecr/cases/${encodeURIComponent(caseId)}/collaboration?${params}`
}

export async function generatePdEcrReport(
  data: PdEcrInput,
): Promise<PdEcrGenerateResponse> {
  const res = await pdEcrApi.post<PdEcrGenerateResponse>(
    "/api/v1/pd-ecr/generate-report",
    data,
  )
  return res.data
}

export async function getPdEcrModuleDraft(
  recordId: string,
  moduleId: string,
): Promise<PdEcrModuleDraftResponse> {
  const res = await pdEcrApi.get<PdEcrModuleDraftResponse>(
    "/api/v1/pd-ecr/module-drafts",
    {
      params: {
        record_id: recordId,
        module_id: moduleId,
      },
    },
  )
  return res.data
}

export async function savePdEcrModuleDraft(
  payload: PdEcrModuleDraftPayload,
): Promise<PdEcrModuleDraftResponse> {
  const res = await pdEcrApi.post<PdEcrModuleDraftResponse>(
    "/api/v1/pd-ecr/module-drafts",
    payload,
  )
  return res.data
}

export async function listPdEcrModuleDrafts(
  recordId?: string,
): Promise<PdEcrDraftListResponse> {
  const res = await pdEcrApi.get<PdEcrDraftListResponse>(
    "/api/v1/pd-ecr/module-drafts/list",
    { params: recordId ? { record_id: recordId } : {} },
  )
  return res.data
}

export async function deletePdEcrModuleDraft(
  recordId: string,
  moduleId: string,
): Promise<{ deleted: boolean }> {
  const res = await pdEcrApi.delete<{ deleted: boolean }>(
    "/api/v1/pd-ecr/module-drafts",
    { params: { record_id: recordId, module_id: moduleId } },
  )
  return res.data
}

// ── Staged Document Review Flow ──

export type PdEcrStagedSection = {
  index: number
  heading: string
  level: number
  content: string
  page_no: number
}

export type PdEcrStagedTable = {
  index: number
  caption: string
  headers: string[]
  rows: string[][]
  page_no: number
}

export type PdEcrStagedDocument = {
  id: string
  status: string
  original_filename: string
  file_type: string
  preview_pdf_url: string | null
  parsed_text: string
  metadata: Record<string, unknown>
  sections: PdEcrStagedSection[]
  tables: PdEcrStagedTable[]
  created_at: string | null
  updated_at: string | null
}

export type PdEcrStagedDocumentUpdate = {
  metadata_json?: Record<string, unknown>
  sections_json?: PdEcrStagedSection[]
  tables_json?: PdEcrStagedTable[]
}

export type PdEcrConfirmResponse = {
  status: string
  case_id: string
  case_no: string
  is_new_case: boolean
  chunks_created: number
  indexing: { pending: boolean; message: string }
}

export async function uploadAndStageDocument(
  file: File,
): Promise<PdEcrStagedDocument> {
  const formData = new FormData()
  formData.append("file", file)
  const res = await pdEcrApi.post<PdEcrStagedDocument>(
    "/api/v1/pd-ecr/documents/upload",
    formData,
    { headers: { "Content-Type": "multipart/form-data" } },
  )
  return res.data
}

export async function getStagedDocument(
  docId: string,
): Promise<PdEcrStagedDocument> {
  const res = await pdEcrApi.get<PdEcrStagedDocument>(
    `/api/v1/pd-ecr/documents/${encodeURIComponent(docId)}`,
  )
  return res.data
}

export async function updateStagedDocument(
  docId: string,
  payload: PdEcrStagedDocumentUpdate,
): Promise<PdEcrStagedDocument> {
  const res = await pdEcrApi.patch<PdEcrStagedDocument>(
    `/api/v1/pd-ecr/documents/${encodeURIComponent(docId)}`,
    payload,
  )
  return res.data
}

export async function confirmStagedDocument(
  docId: string,
): Promise<PdEcrConfirmResponse> {
  const res = await pdEcrApi.post<PdEcrConfirmResponse>(
    `/api/v1/pd-ecr/documents/${encodeURIComponent(docId)}/confirm`,
  )
  return res.data
}
