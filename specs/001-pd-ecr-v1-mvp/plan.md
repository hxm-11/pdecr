# PD-ECR V1 MVP Implementation Plan

## 0. Plan Status

This plan is aligned with the current feature specification and the repository
state inspected on 2026-07-02.

The V1 MVP is not a full approval system. It is the AI-assisted PD-ECR loop:

```text
Browse historical PD-ECR cases
-> Fill a new PD-ECR request
-> Retrieve Top K similar historical cases
-> Generate a source-grounded six-module draft
-> Review module content and source references
-> Export a basic demo report
```

Any formal approval routing, enterprise permission matrix, Outlook automation,
SuperOPL synchronization, or production audit trail belongs outside this V1
feature unless the constitution is amended.

## 1. Goal

Build and stabilize a demo-ready PD-ECR V1 MVP that proves historical
case retrieval and AI-assisted draft generation can produce a usable,
traceable PD-ECR starting point.

The system must preserve source grounding:

```text
Generated content must carry source_cases or source_files when it uses
historical evidence. Unsupported content must be marked for human input.
```

## 2. Current System State

### 2.1 Backend

The backend is an existing FastAPI application using SQLModel, Alembic, and a
local SQLite default when `SQLALCHEMY_DATABASE_URI` is not configured.

Current facts from the repository:

- App entry and router composition:
  - `backend/app/main.py`
  - `backend/app/api/main.py`
  - `backend/app/api/routes/pd_ecr.py`
- PD-ECR router is mounted at:
  - `/api/v1/pd-ecr`
- Database default for local development:
  - `sqlite:///./pd_ecr.db`
- Current backend dependency stack includes:
  - FastAPI
  - SQLModel
  - Alembic
  - Pydantic v2
  - OpenAI SDK
  - numpy
  - faiss-cpu
  - sentence-transformers
  - docling
  - onnxruntime

Important existing PD-ECR models in `backend/app/models.py`:

- `PdEcrCase`
- `PdEcrModule`
- `PdEcrTask`
- `PdEcrDepartmentTask`
- `PdEcrDepartmentVisibility`
- `PdEcrExecutionTask`
- `PdEcrLeaderReviewTask`
- `PdEcrApprovalTask`
- `PdEcrComment`
- `PdEcrAttachment`
- `PdEcrVersion`
- `PdEcrActivity`
- `PdEcrNotification`
- `PdEcrCollaborationSession`
- `HistoricalSourceDocument`
- `PdEcrStagedDocument`

Important existing PD-ECR service modules:

- `pd_ecr_schema.py`: V1 request/result schemas and six-module contract helpers
- `pd_ecr_case_loader.py`: historical case loading
- `pd_ecr_import_service.py`: historical source discovery/import and upload
- `pd_ecr_retrieval.py`: similar case retrieval and ranking
- `pd_ecr_generation.py`: source-grounded draft generation
- `pd_ecr_four_module_generation.py`: legacy/four-module generation support
- `pd_ecr_ai_case_service.py`: create editable case/modules from generated draft
- `pd_ecr_export_service.py` and `pd_ecr_export.py`: report/export rendering
- `pd_ecr_case_service.py`: editable case/module persistence and permissions
- `pd_ecr_workflow.py`: existing post-MVP workflow/task capabilities
- `pd_ecr_notification_service.py`: existing notification records/reminders
- `pd_ecr_audit_service.py`: activity writing

Existing PD-ECR API surface includes, among others:

- Historical and editable cases:
  - `GET /api/v1/pd-ecr/cases`
  - `POST /api/v1/pd-ecr/cases`
  - `GET /api/v1/pd-ecr/cases/{case_id}`
  - `PATCH /api/v1/pd-ecr/cases/{case_id}`
  - `DELETE /api/v1/pd-ecr/cases/{case_id}`
- Historical source documents and upload:
  - `GET /api/v1/pd-ecr/source-documents/{source_doc_id}/preview`
  - `DELETE /api/v1/pd-ecr/source-documents/{source_doc_id}`
  - `POST /api/v1/pd-ecr/cases/upload-file`
  - `POST /api/v1/pd-ecr/import/historical`
  - `GET /api/v1/pd-ecr/knowledge-base/status`
- V1 request, retrieval, generation, and export:
  - `POST /api/v1/pd-ecr/requests`
  - `POST /api/v1/pd-ecr/retrieve`
  - `POST /api/v1/pd-ecr/history/search`
  - `POST /api/v1/pd-ecr/generate-draft`
  - `POST /api/v1/pd-ecr/generate-from-change-description`
  - `GET /api/v1/pd-ecr/drafts/{draft_id}/modules`
  - `POST /api/v1/pd-ecr/export`
  - `POST /api/v1/pd-ecr/generate-report`
- Editable module operations:
  - `GET /api/v1/pd-ecr/cases/{case_id}/modules`
  - `PATCH /api/v1/pd-ecr/cases/{case_id}/modules/{module_id}`
  - `POST /api/v1/pd-ecr/cases/{case_id}/modules/{module_id}/regenerate`
  - `POST /api/v1/pd-ecr/cases/{case_id}/modules/{module_id}/apply-generated`
- Existing post-MVP workflow APIs:
  - `/api/v1/pd-ecr/cases/{case_id}/workflow`
  - `/api/v1/pd-ecr/workflow/my-tasks`
  - manager approval, department confirmation, execution task, leader review,
    reminder, comment, activity, and collaboration endpoints

The workflow APIs already exist in the codebase, but they are not the V1 MVP
scope defined by `spec.md`. They should be treated as adjacent or post-V1
capabilities unless specifically required for the demo path.

### 2.2 Frontend

The frontend is an existing React 19 + TypeScript + Vite app using TanStack
Router, TanStack Query, Tailwind CSS, shadcn-style local UI components, and
lucide-react.

Current PD-ECR routes include:

- `/pd-ecr`
- `/pd-ecr/new`
- `/pd-ecr/cases`
- `/pd-ecr/history-case`
- `/pd-ecr/content`
- `/pd-ecr/content/$moduleId`
- `/pd-ecr/drafts`
- `/pd-ecr/documents/$docId`
- `/pd-ecr/dashboard`
- `/pd-ecr/tasks`

Current PD-ECR frontend modules include:

- `PdEcrPlatform`
- `PdEcrCreationWorkflow`
- `PdEcrCaseList`
- `PdEcrHistoryCase`
- `PdEcrModuleAccordion`
- `PdEcrModuleDetail`
- `PdEcrDraftList`
- `PdEcrCaseDashboard`
- `PdEcrDocumentReview`
- `PdEcrProcessFlow`
- `PdEcrExecutionWorkflowPanel`
- `PdEcrMyTasks`
- `pdEcrApi.ts`
- `pdEcrState.ts`
- `pdEcrExport.ts`

The frontend already contains workflow/task UI. For this V1 plan, the primary
journey is still the retrieval/generation/review/export loop. Workflow UI should
not be expanded unless needed to keep existing screens coherent.

### 2.3 Historical Knowledge Base

Historical PD-ECR inputs are already present under:

- `backend/app/data/pd_ecr_cases/`
- `backend/app/data/markdown/`
- `backend/app/data/raw_files/`
- `backend/app/knowledge_pre/`
- `backend/app/rag/`

The repository contains structured JSON cases, Markdown conversions, source
PDF/XLS/XLSX files, cleaned text, OCR output, and uploaded sample files. V1
should reuse this knowledge base and avoid adding a separate mock case source.

### 2.4 Tests

Existing backend PD-ECR tests include service and API coverage for:

- case loading
- schema behavior
- retrieval
- generation
- module draft generation
- permissions and notifications
- workflow
- PDF search
- execution workflow
- API routes

Existing frontend Playwright tests include PD-ECR flows such as:

- `pd-ecr.spec.ts`
- `pd-ecr-cases.spec.ts`
- `pd-ecr-content-export.spec.ts`
- `pd-ecr-dashboard.spec.ts`
- `pd-ecr-process-flow.spec.ts`

## 3. Technical Context

| Area | Current Decision |
|---|---|
| Backend framework | FastAPI |
| Backend data layer | SQLModel + Alembic |
| Local database | SQLite default via `sqlite:///./pd_ecr.db`; PostgreSQL remains supported by template config |
| Frontend | React, TypeScript, Vite |
| Routing | TanStack Router |
| Data fetching | TanStack Query plus local `pdEcrApi.ts` axios client |
| Styling | Tailwind CSS and local shadcn-style UI components |
| Retrieval | Existing PD-ECR RAG services with FAISS/semantic search and fallback matching |
| AI generation | Existing source-grounded generation services; requires configured LLM credentials for live AI validation |
| Export | Existing PD-ECR export/report services and frontend export helper |
| Auth | Existing template JWT auth plus current-user APIs; V1 does not introduce a new auth model |

No new framework should be introduced for V1.

## 4. Constitution Check

### MVP Scope Discipline

Pass. This plan limits V1 to historical case browsing, retrieval, AI draft
generation, modular review, and basic export.

Formal approval workflow, complex permissions, Outlook automation, SuperOPL
sync, and enterprise audit are explicitly deferred.

### Source-Grounded AI Output

Pass with implementation verification required. Generated modules must retain
`source_cases` or `source_files` when evidence contributes to content. Unsupported
sections must set human-review warnings rather than presenting invented facts.

### Unified Historical Metadata

Pass with compatibility mapping required. V1 APIs and UI must preserve:

- `case_id`
- `dc_no`
- `mcr_no`
- `change_type`
- `product_no`
- `part_no`
- `customer_project`
- `source_file`

Existing aliases such as `component_no`, `case_no`, or source-specific metadata
may be normalized internally, but the V1 response shape must expose canonical
fields or explicit missing-field indicators.

### Modular PD-ECR Result Contract

Pass. The user-facing V1 draft must expose exactly these six modules:

- Basic Information
- Change Description
- Reason for Change
- Impact Analysis
- Implementation Plan
- Approval / Sign-off Information

Existing internal four-module or editable-module structures can remain, but the
V1 display/export path must normalize to the six-module contract.

### Minimal Change in Existing Structure

Pass. The repository already contains the required backend and frontend
architecture. Work should be additive and focused on aligning behavior,
contracts, and validation rather than replacing the current app structure.

### Demo-Ready, Non-Production V1

Pass. Generated drafts and exports must remain marked as V1 MVP/demo draft
content and must not imply official approval.

## 5. In Scope

V1 implementation and verification covers:

- Historical case list and detail display.
- Canonical metadata normalization with explicit missing-field indicators.
- New PD-ECR request validation.
- Top K similar-case retrieval, defaulting to 5.
- Similar-case result cards with rank, similarity reason, source file, and module
  summary.
- Source-grounded AI draft generation.
- Six-module draft display.
- Per-module source reference display.
- Human-input warnings for unsupported generated content.
- Basic export that includes request data, similar cases, modules, sources, and
  V1 MVP draft/demo status.
- Automated or manual validation of the closed demo loop.

## 6. Out of Scope for V1

The following are deferred even if some code already exists:

- Complete approval workflow.
- Multi-person sign-off routing.
- Complex role/permission matrix.
- Outlook or real email automation.
- SuperOPL automatic synchronization.
- Enterprise-grade audit logging.
- Production system-of-record behavior.
- New BPMN/workflow engine.
- New frontend redesign unrelated to the PD-ECR MVP loop.

## 7. Primary User Journey

```text
1. User opens /pd-ecr/cases.
2. User scans historical cases and opens a case detail.
3. User opens /pd-ecr/new.
4. User fills DC No, MCR No, customer project, product number, part number,
   change type, change description, and change reason.
5. User retrieves Top K similar cases.
6. User reviews ranked results and source files.
7. User generates a PD-ECR draft.
8. User opens /pd-ecr/content and reviews the six modules.
9. User checks source references or human-input warnings.
10. User exports a basic demo report.
```

## 8. Data and Contract Alignment

The authoritative planning artifacts for V1 are:

- `specs/001-pd-ecr-v1-mvp/spec.md`
- `specs/001-pd-ecr-v1-mvp/data-model.md`
- `specs/001-pd-ecr-v1-mvp/contracts/pd-ecr-v1-api.yaml`
- `specs/001-pd-ecr-v1-mvp/quickstart.md`

`workflow-contract.md` describes workflow/task behavior that is mostly post-V1
relative to the current feature spec. Do not use it to expand V1 scope.

Implementation must ensure the live API behavior matches the V1 API contract for
the MVP endpoints:

- `GET /cases`
- `GET /cases/{case_id}`
- `POST /requests`
- `POST /retrieve`
- `POST /generate-draft`
- `GET /drafts/{draft_id}/modules`
- `POST /export`

If existing endpoints return a richer shape, they must still preserve the
required contract fields for V1 consumers.

## 9. Implementation Phases

### Phase 1: Contract and Scope Reconciliation

Review current routes, schemas, and frontend API types against:

- `spec.md`
- `data-model.md`
- `contracts/pd-ecr-v1-api.yaml`
- `quickstart.md`

Tasks:

- Confirm whether `pd_ecr_schema.py` already exposes all canonical V1 fields.
- Confirm whether `pdEcrApi.ts` matches current backend responses.
- Identify any endpoint shape drift between the OpenAPI contract and live code.
- Mark workflow-only endpoints as outside V1 acceptance unless they block the MVP
  journey.

Acceptance criteria:

- A short gap list exists before code changes.
- No approval-flow scope is added to the V1 MVP.

### Phase 2: Historical Case Browsing Stabilization

Tasks:

- Verify `GET /api/v1/pd-ecr/cases` returns historical cases with canonical
  metadata and explicit missing fields.
- Verify `GET /api/v1/pd-ecr/cases/{case_id}` returns detail metadata, module
  content, source file, and source trace where available.
- Ensure frontend `/pd-ecr/cases` and historical detail views display missing
  metadata explicitly.
- Reuse existing imported data and source documents.

Acceptance criteria:

- User can browse and inspect historical cases.
- Missing canonical fields are visible instead of silently omitted.
- Source file links/previews work for available documents.

### Phase 3: Retrieval Stabilization

Tasks:

- Verify `POST /api/v1/pd-ecr/requests` validates required input fields.
- Verify `POST /api/v1/pd-ecr/retrieve` and/or
  `POST /api/v1/pd-ecr/history/search` return ranked Top K results.
- Default `top_k` to 5 and bound it for demo use.
- Preserve rank, case ID, similarity reason, source file, module summary,
  source cases/files, and retrieval context.
- Ensure frontend result cards expose enough evidence for user trust.

Acceptance criteria:

- Incomplete requests are rejected before retrieval/generation.
- A valid demo request returns up to 5 ranked results by default.
- Results can be traced to source cases or source files.

### Phase 4: Six-Module Draft Generation

Tasks:

- Verify `POST /api/v1/pd-ecr/generate-draft` produces exactly six user-facing
  modules.
- Normalize legacy/four-module/internal editable module output into the V1
  six-module contract when needed.
- Ensure every evidence-backed module contains `source_cases` or `source_files`.
- Ensure unsupported content is marked with `needs_human_input` and warnings.
- Keep `draft_status` as `V1_MVP_DRAFT` or equivalent demo status.

Acceptance criteria:

- Generated drafts always show all six required modules.
- No unsupported AI conclusion appears as a sourced fact.
- Source references are visible in module detail and export data.

### Phase 5: Frontend Review and Export Loop

Tasks:

- Verify `/pd-ecr/new` supports the complete form -> retrieve -> generate flow.
- Verify `/pd-ecr/content` and `/pd-ecr/content/$moduleId` display generated
  module content, source references, and human-input warnings.
- Verify export includes input data, similar cases, generated modules, source
  references, and demo draft status.
- Avoid broad UI redesign; use existing PD-ECR components and local UI patterns.

Acceptance criteria:

- User can complete the full MVP loop in one continuous journey.
- Exported content is clearly marked as a V1 MVP draft/demo report.

### Phase 6: Validation and Cleanup

Tasks:

- Run targeted backend tests for schema, case loading, retrieval, generation,
  export, and relevant API routes.
- Run frontend build and targeted Playwright PD-ECR tests.
- Fix critical bugs only; do not introduce new workflow scope.
- Update quickstart or contract docs only if live behavior intentionally differs.

Acceptance criteria:

- MVP validation path passes via automated tests or documented manual run.
- Remaining gaps are listed clearly.
- No company API keys or secrets appear in frontend code.

## 10. Recommended Validation Commands

Backend:

```powershell
cd backend
uv run pytest app/tests/services/test_pd_ecr_schema.py app/tests/services/test_pd_ecr_case_loader.py app/tests/services/test_pd_ecr_retrieval.py app/tests/services/test_pd_ecr_generation.py tests/api/routes/test_pd_ecr_knowledge_status.py
```

Frontend:

```powershell
cd frontend
npm run build
npx playwright test tests/pd-ecr.spec.ts tests/pd-ecr-cases.spec.ts tests/pd-ecr-content-export.spec.ts --project=chromium
```

Full local demo:

```powershell
cd backend
uv run fastapi dev app/main.py
```

```powershell
cd frontend
npm run dev
```

Then open `/pd-ecr` and complete:

```text
historical cases -> new request -> retrieve -> generate -> module review -> export
```

## 11. Risks and Mitigations

| Risk | Mitigation |
|---|---|
| Existing workflow code expands V1 beyond spec | Treat workflow/task APIs as adjacent/post-V1 unless needed for navigation coherence |
| API contract drift between docs and live code | Reconcile `pd_ecr_schema.py`, `pdEcrApi.ts`, and `pd-ecr-v1-api.yaml` before feature work |
| Historical data has incomplete metadata | Normalize canonical fields and expose missing-field indicators |
| AI output lacks evidence | Require source references for evidence-backed content and human-input warnings otherwise |
| LLM unavailable during local validation | Validate retrieval and deterministic fallback generation; document that live AI requires LLM env vars |
| Frontend uses cached/localStorage draft data | Ensure current backend response remains the source for new generation and export paths |

## 12. Definition of Done

The V1 MVP is done when:

```text
A user can browse historical PD-ECR cases.
A user can inspect a historical case and its source file.
A user can fill the required new PD-ECR request fields.
The backend rejects incomplete requests before retrieval/generation.
The backend retrieves ranked Top K similar cases, defaulting to 5.
Similar case results show source files and similarity reasons.
The backend generates a six-module V1 MVP draft.
Generated modules show source_cases or source_files when evidence is used.
Unsupported generated content is marked as requiring human input.
The frontend displays the six modules and traceability information.
The user can export a basic report with request data, similar cases, modules,
source references, and V1 MVP draft/demo status.
No frontend code contains company API keys, email API keys, or database secrets.
Formal approval workflow remains outside the V1 acceptance criteria.
```

## 13. First Implementation Prompt

Use this prompt when implementation starts:

```text
Please implement the PD-ECR V1 MVP according to specs/001-pd-ecr-v1-mvp/plan.md.

Start with Phase 1 and Phase 2 only:
1. Compare current backend/frontend behavior with spec.md, data-model.md, and contracts/pd-ecr-v1-api.yaml.
2. Fix historical case list/detail contract gaps.
3. Preserve canonical metadata and explicit missing-field indicators.
4. Do not expand approval workflow scope.

Before editing files, summarize the exact gaps and proposed files to change.
After editing, run targeted backend tests if available.
```

## 14. Follow-Up Implementation Prompt

After Phase 1 and Phase 2 are complete:

```text
Continue PD-ECR V1 MVP implementation from specs/001-pd-ecr-v1-mvp/plan.md.

Implement Phase 3 and Phase 4:
- request validation
- Top K retrieval
- source-grounded six-module draft generation
- source reference and human-input warning preservation

Do not implement or expand formal approval workflow.
Run targeted backend tests and explain the local validation path.
```

## 15. Final Verification Prompt

After implementation:

```text
Review the implemented PD-ECR V1 MVP against specs/001-pd-ecr-v1-mvp/plan.md.

Check:
1. Historical case list/detail behavior
2. Required request validation
3. Top K retrieval default and ranking
4. Six-module generated draft contract
5. Source_cases/source_files traceability
6. Human-input warnings for unsupported output
7. Basic export content and demo status
8. Frontend completion of the full MVP loop
9. Absence of frontend secrets
10. No V1 scope creep into formal approval workflow

List remaining gaps and fix critical bugs only.
```
