# Quickstart: PD-ECR V1 MVP Validation

## Prerequisites

- Backend dependencies installed with `uv sync` from `backend/`.
- Frontend dependencies installed with `npm install` or the repository's current
  frontend package workflow.
- Historical PD-ECR Markdown/JSON files present under `backend/app/rag/**`.
- Local embedding model and FAISS index available for semantic search, or keyword
  fallback accepted for demo validation.
- LLM environment variables configured when validating AI generation:
  - `LLM_API_KEY`
  - optional `LLM_BASE_URL`

## Start Backend

```powershell
cd backend
uv run fastapi dev app/main.py
```

Expected outcome: backend serves `/api/v1` locally and PD-ECR routes are
reachable.

## Start Frontend

```powershell
cd frontend
npm run dev
```

Expected outcome: frontend opens locally and the authenticated app can navigate
to `/pd-ecr`.

## Validate Historical Case List

1. Open `/pd-ecr/cases`.
2. Confirm the case list loads.
3. Confirm each visible case has case identity, source file, and available
   metadata.
4. Confirm missing metadata is shown explicitly.

Expected outcome: historical cases are visible and source files are inspectable.

## Validate Historical Case Detail

1. From `/pd-ecr/cases`, open one case.
2. Confirm metadata and module content are displayed.
3. Confirm the source file appears in the detail/module view.

Expected outcome: a user can inspect the evidence behind a historical case.

## Validate Retrieval

Submit a request similar to:

```json
{
  "dc_no": "PD-ECR-DEMO-001",
  "mcr_no": "MCR-DEMO-001",
  "customer_project": "JIM-493",
  "product_no": "F01ZH003G1-00",
  "part_no": "F01ZH003G1-00",
  "change_type": "A Sample release",
  "change_description": "Release detachable and integrated DOC+SDPF sample parts",
  "change_reason": "Customer request and design optimization",
  "top_k": 5
}
```

Expected outcome: Top K results include `case_id`, `dc_no`, `change_type`,
`matched_fields`, `similarity_score`, `source_file`, and `module_summary`.

## Validate AI Draft Generation

1. Open `/pd-ecr/new`.
2. Fill required fields: DC No, MCR No, customer project, product number, part
   number, change type, change description, and change reason.
3. Retrieve similar cases.
4. Generate the AI draft.
5. Open `/pd-ecr/content`.

Expected outcome: the draft displays six modules:

- Basic Information
- Change Description
- Reason for Change
- Impact Analysis
- Implementation Plan
- Approval / Sign-off Information

Each evidence-backed module shows source cases or source files. Unsupported
content is marked as requiring human input.

## Validate Module Detail

1. Click each generated module.
2. Confirm module content is readable.
3. Confirm source references or human-input warnings are visible.

Expected outcome: users can trace generated content to historical evidence.

## Validate Export

1. From generated modules view, click the report export button.
2. Open the exported file.
3. Confirm it contains submitted form data, similar cases, six modules, source
   references, and `V1 MVP draft` status.

Expected outcome: the report is suitable for demo review and does not imply
formal approval.

## Automated Validation Commands

Backend:

```powershell
cd backend
uv run pytest app/tests/api/routes/test_pd_ecr_v1.py app/tests/services/test_pd_ecr_case_loader.py
```

Frontend:

```powershell
cd frontend
npm run build
npx playwright test tests/pd-ecr.spec.ts tests/pd-ecr-cases.spec.ts tests/pd-ecr-content-export.spec.ts --project=chromium
```

Expected outcome: backend contract tests, frontend build, and Playwright MVP
flow tests pass.
