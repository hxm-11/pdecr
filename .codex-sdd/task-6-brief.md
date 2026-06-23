### Task 6: Frontend API support for persisted AI, assignment, regeneration, and reminders

**Files:**
- Modify: `frontend/src/lib/pdEcrApi.ts`

**Interfaces:**
- Consumes:
  - Backend endpoints from Tasks 2-5
- Produces:
  - `PdEcrPermissionFlags`
  - `PdEcrGeneratedCaseResponse`
  - `PdEcrGeneratedModulePreview`
  - `generatePdEcrEditableCase(...)`
  - `regeneratePdEcrModule(...)`
  - `applyGeneratedPdEcrModule(...)`
  - `assignPdEcrModule(...)`
  - `sendPdEcrModuleReminder(...)`

- [ ] **Step 1: Add types and functions**

Modify `frontend/src/lib/pdEcrApi.ts` by extending `PdEcrDbModule`:

```ts
export type PdEcrPermissionFlags = {
  can_edit?: boolean
  can_assign?: boolean
  can_regenerate?: boolean
  can_send_reminder?: boolean
  can_review?: boolean
  can_close?: boolean
}
```

Add fields to `PdEcrDbModule`:

```ts
  assignee_id?: string | null
  assignee_email?: string | null
  assignee_name?: string | null
  department?: string | null
  due_date?: string | null
  reminder_policy?: Record<string, unknown>
  last_reminded_at?: string | null
  permissions?: PdEcrPermissionFlags
```

Add these types:

```ts
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
```

Add functions near existing generation functions:

```ts
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
): Promise<{ module: PdEcrDbModule; notification?: Record<string, unknown> | null }> {
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
```

- [ ] **Step 2: Build frontend**

Run:

```powershell
cd frontend
npm run build
```

Expected: PASS with no TypeScript errors.

- [ ] **Step 3: Commit**

Run:

```bash
git add frontend/src/lib/pdEcrApi.ts
git commit -m "feat: add pd-ecr editable ai api client"
```

---

