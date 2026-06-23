# Implementation Plan: PD-ECR V1 MVP

**Branch**: `001-pd-ecr-v1-mvp` | **Date**: 2026-06-16 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/001-pd-ecr-v1-mvp/spec.md`

## Summary

Deliver the PD-ECR V1 MVP by tightening the existing FastAPI + React PD-ECR
workflow around one shared data contract: load historical Markdown/JSON cases,
validate unified metadata, retrieve Top K similar cases with metadata/keyword/
semantic signals, generate a structured six-module PD-ECR draft with source
references, show the draft in modular frontend views, and export a basic report.

The implementation will keep the current `backend/app/api/routes/pd_ecr.py`
router, `backend/app/rag/retriever.py` retrieval path, and
`frontend/src/components/PdEcr/*` pages. New work should be small adapters and
schema helpers rather than a broad rewrite.

## Technical Context

**Language/Version**: Python >=3.10 for backend; TypeScript 5.9 with React 19 for frontend

**Primary Dependencies**: FastAPI, Pydantic v2, OpenAI client, Markdown/Jinja2,
FAISS, sentence-transformers, React, TanStack Router, TanStack Query, axios,
Tailwind CSS, Playwright, pytest

**Storage**: File-based historical PD-ECR knowledge in Markdown/JSON under
`backend/app/rag/**`; generated reports under `backend/app/reports`; existing
SQLite module-draft cache may remain for editable module drafts

**Testing**: pytest for backend schema/retrieval/generation contract tests;
Playwright for frontend MVP flow and export tests; frontend build via
`npm run build`

**Target Platform**: Local web application MVP using existing backend and
frontend development servers

**Project Type**: Web application with FastAPI backend and React frontend

**Performance Goals**: Historical case list loads within 3 seconds for the V1
dataset; Top K retrieval returns within 10 seconds with FAISS available and
within 20 seconds with keyword fallback; cached identical generation returns
within 2 seconds

**Constraints**: V1 must use Markdown/JSON historical files as source of truth;
generated content must include source case or source file references when
evidence is used; no approval workflow, complex permission model, Outlook
notification, SuperOPL sync, or enterprise audit log

**Scale/Scope**: MVP dataset of tens to low hundreds of PD-ECR cases, one primary
internal user journey, six required generated modules, basic HTML/CSV export

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **MVP Scope Discipline**: PASS. The plan covers only historical case browsing,
  similar-case retrieval, AI draft generation, modular display, and basic export.
  Approval routing, multi-person sign-off workflow, complex permissions, Outlook
  notification, SuperOPL sync, and enterprise audit logs are explicitly deferred.
- **Source-Grounded AI Output**: PASS. Retrieval responses will normalize
  `source_file`, `source_cases`, matched fields, and module summaries. AI prompt
  and response schema require each generated module to include `source_cases` or
  `source_files`; unsupported content is marked `needs_human_input`.
- **Unified Historical Metadata**: PASS. Case loading validates and preserves
  `case_id`, `dc_no`, `mcr_no`, `change_type`, `product_no`, `part_no`,
  `customer_project`, and `source_file` across list, detail, retrieval,
  generation, module display, and export.
- **Modular Result Contract**: PASS. V1 generated output exposes Basic
  Information, Change Description, Reason for Change, Impact Analysis,
  Implementation Plan, and Approval / Sign-off Information. Existing legacy
  module IDs remain as compatibility inputs only.
- **Minimal Existing-Structure Change**: PASS. Reuse existing FastAPI router,
  RAG retriever, local report generation, React `PdEcr` components, TanStack
  routes, and `pdEcrApi.ts`; add focused schema/service helpers and adapters.
- **Demo-Ready, Non-Production V1**: PASS. Generated drafts and exports carry
  draft/demo status. No formal production or system-of-record claim is added.

Post-design re-check: PASS. Research, data model, contracts, and quickstart keep
the implementation inside the V1 boundaries and avoid broad refactoring.

## Technical Design

### 1. Data Structure Design

Add a V1 normalized case model used by backend responses and frontend types:

- `case_id`: stable case identifier, derived from explicit JSON metadata first,
  then filename stem.
- `metadata`: canonical fields:
  - `case_id`
  - `dc_no`
  - `mcr_no`
  - `change_type`
  - `product_no`
  - `part_no`
  - `customer_project`
  - `source_file`
  - optional `date`, `initiator`, `sample_status`
- `modules`: map of module ID to content:
  - `basic_information`
  - `change_description`
  - `reason_for_change`
  - `impact_analysis`
  - `implementation_plan`
  - `approval_signoff_information`
- `source_file`: original Markdown/PDF/JSON filename.
- `retrieval_context`: generated per request, containing matched fields,
  keyword hits, semantic score, module summary, and evidence snippets.
- `source_trace`: optional source-page/raw-path/confidence metadata already seen
  in OCR JSON files.

Keep existing historical extraction output as inputs. Add a normalization adapter
so existing keys such as `component_no`, `affected_product_no`,
`change_request_description`, `validation_trial_run_plan`, or current six-step
template modules can feed the V1 six-module contract.

### 2. Historical Case Loading

Implement or extend a focused loader, preferably
`backend/app/services/pd_ecr_case_loader.py`, while keeping route wiring in
`backend/app/api/routes/pd_ecr.py`.

Loading order:

1. Read structured JSON cases from `backend/app/data/pd_ecr_cases/` if present.
2. Read parsed OCR JSON from `backend/app/rag/jie_jim_knowledge_pdf/**/ocr/*metadata.json`
   and related parsed module JSON when available.
3. Read Markdown/Text from `backend/app/rag/knowledge`, `backend/app/rag/pdecr_knowledge`,
   and curated JIE/JIM clean text directories as fallback.
4. Derive missing display fields from filename or Markdown headings only as a
   fallback, marking the field as missing/derived in validation warnings.

Validation rules:

- `case_id` and `source_file` are required after normalization.
- `dc_no`, `mcr_no`, `product_no`, `part_no`, `customer_project`, and
  `change_type` must be represented even when missing.
- Missing fields return explicit `missing_fields` entries; they are not silently
  omitted.
- `DC No`, `MCR No`, and frontend labels may be displayed with business names,
  but API payloads use snake_case canonical keys.

### 3. Similar Case Retrieval

Keep `backend/app/rag/retriever.py` as the retrieval engine and add a V1 response
adapter around `retrieve_pd_ecr_results`.

Retrieval flow:

1. Build query text from DC No, MCR No, customer project, product number, part
   number, change type, change description, and change reason.
2. Apply metadata filters when provided:
   - exact or fuzzy `customer_project`
   - exact/fuzzy `product_no`
   - exact/fuzzy `part_no`
   - exact/fuzzy `change_type`
3. Run keyword search over Markdown/JSON text and metadata fields.
4. Run semantic similarity using the existing local sentence-transformer + FAISS
   index when available.
5. Combine scores with a simple V1 hybrid score:
   - semantic score as primary signal when FAISS is available
   - metadata match boost for customer/product/part/change type
   - keyword boost for change reason and change description terms
6. Deduplicate by `case_id` or `source_file`.
7. Return Top K, default 5.

Top K response fields:

- `case_id`
- `dc_no`
- `change_type`
- `matched_fields`
- `similarity_score`
- `source_file`
- `module_summary`
- `source_cases`
- `source_files`
- `retrieval_mode`

### 4. AI Draft Generation

Keep the existing `/generate-report` LLM path and post-processing helpers, but
add a V1 structured draft adapter.

Prompt requirements:

- Inputs: normalized user request, Top K similar cases, matched fields, module
  summaries, and evidence snippets.
- Instruction: generate only JSON that matches the V1 schema.
- Source rule: every generated module must include `source_cases` or
  `source_files` when it uses retrieved evidence.
- Unsupported rule: if evidence is insufficient, set `needs_human_input: true`
  and explain the missing evidence instead of inventing facts.
- Draft rule: include `draft_status: "V1_MVP_DRAFT"` in the response.

Output JSON schema:

- `draft_id`
- `draft_status`
- `input_snapshot`
- `similar_cases`
- `modules`
  - `basic_information`
  - `change_description`
  - `reason_for_change`
  - `impact_analysis`
  - `implementation_plan`
  - `approval_signoff_information`
- each module:
  - `title`
  - `summary`
  - `content`
  - `source_cases`
  - `source_files`
  - `needs_human_input`
  - `warnings`
- `export`
  - `report_url`
  - `generated_at`

Compatibility:

- Existing template-rendered module content can populate the new modules where it
  already maps cleanly.
- Existing validation/implementation-result modules can stay available in detail
  views as secondary fields, but the V1 generated module list must show the six
  constitution modules first.

### 5. Backend API Design

Reuse the existing `/api/v1/pd-ecr` prefix. Add stable V1 endpoint names while
keeping current aliases during transition.

- `GET /api/v1/pd-ecr/cases`
  - Historical case list.
  - Extend existing endpoint to return normalized metadata and `missing_fields`.
- `GET /api/v1/pd-ecr/cases/{case_id}`
  - Historical case detail.
  - New endpoint resolving by `case_id`, `dc_no`, filename stem, or source file.
- `POST /api/v1/pd-ecr/requests`
  - Validate and echo a new PD-ECR input snapshot.
  - V1 may be stateless and return a generated request ID derived from input hash.
- `POST /api/v1/pd-ecr/retrieve`
  - Retrieve Top K similar cases.
  - Alias current `/history/search` and `/test-rag` behavior through V1 response
    normalization.
- `POST /api/v1/pd-ecr/generate-draft`
  - Generate V1 structured draft JSON.
  - May call the existing generation internals used by `/generate-report`.
- `GET /api/v1/pd-ecr/drafts/{draft_id}/modules`
  - Return generated modules from cache or persisted report state.
- `POST /api/v1/pd-ecr/export`
  - Export a basic report from draft JSON.
  - Existing `/generate-report` report file can be reused, but export response
    must include draft/demo status and source references.

Existing endpoints to preserve:

- `GET /api/v1/pd-ecr/cases`
- `GET /api/v1/pd-ecr/cases/modules`
- `POST /api/v1/pd-ecr/history/search`
- `POST /api/v1/pd-ecr/test-rag`
- `POST /api/v1/pd-ecr/generate-report`
- `GET/POST /api/v1/pd-ecr/module-drafts`

### 6. Frontend Page Design

Reuse `frontend/src/components/PdEcr` and existing routes.

- **PD-ECR Case List**
  - Existing: `PdEcrCaseList.tsx`, route `/pd-ecr/cases`.
  - Update columns/types to show case_id, DC No, MCR No, customer project,
    product number, part number, change type, source file, and missing metadata.
- **PD-ECR Case Detail**
  - Existing behavior opens modules through `/pd-ecr/content`.
  - Add direct detail state for selected case and call `GET /cases/{case_id}` or
    keep `/cases/modules` as fallback.
- **New PD-ECR Form**
  - Existing: `PdEcrCreationWorkflow.tsx`, route `/pd-ecr/new`.
  - Add MCR No and change type if missing from current UI state; validate required
    fields before retrieve/generate.
- **Similar Cases Panel**
  - Existing search panel in creation workflow.
  - Show Top K with case_id, DC No, change type, matched fields, similarity score,
    similarity reason, source file, and module summary.
- **Generated Modules View**
  - Existing: `PdEcrContentBlocks.tsx` and `PdEcrModuleDetail.tsx`.
  - Change module order and normalization to the six V1 modules. Display
    `source_cases`, `source_files`, `needs_human_input`, and warnings in detail.
- **Report Export Button**
  - Existing: `pdEcrExport.ts` and content view export buttons.
  - Include six modules, source references, similar cases, submitted form data,
    and `V1 MVP draft` status in HTML/CSV export.

### 7. Testing Plan

Backend pytest coverage:

- Case loader normalizes JSON/Markdown historical cases.
- Missing metadata produces explicit `missing_fields`.
- Retrieval returns Top K objects with required V1 fields.
- Metadata filters affect result ranking or filtering.
- AI generation parser validates six-module JSON schema.
- Generated modules preserve `source_cases` or `source_files`.
- Unsupported/no-evidence path sets `needs_human_input`.
- Export payload includes draft/demo status and source references.

Frontend Playwright coverage:

- Case list loads and filters historical cases.
- Case detail opens and shows metadata/module content.
- New PD-ECR form validates required fields.
- Similar cases panel shows Top K fields and source file.
- Generate action stores and displays six modules.
- Module detail shows source references or human-input warning.
- Export button downloads a report containing module and source text.

Existing tests to extend:

- `frontend/tests/pd-ecr.spec.ts`
- `frontend/tests/pd-ecr-cases.spec.ts`
- `frontend/tests/pd-ecr-content-export.spec.ts`
- add backend tests under `backend/app/tests/api/routes/` or existing backend
  test layout.

## Project Structure

### Documentation (this feature)

```text
specs/001-pd-ecr-v1-mvp/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   └── pd-ecr-v1-api.yaml
└── tasks.md
```

### Source Code (repository root)

```text
backend/
├── app/
│   ├── api/routes/pd_ecr.py              # keep router; add V1 endpoints/adapters
│   ├── rag/retriever.py                  # reuse retrieval; add normalized result adapter
│   ├── services/
│   │   ├── pd_ecr_case_loader.py         # new focused loader/normalizer
│   │   ├── pd_ecr_retrieval.py           # new focused Top K adapter
│   │   ├── pd_ecr_generation.py          # new structured draft adapter
│   │   └── pd_ecr_export.py              # optional extraction from current route
│   ├── data/pd_ecr_cases/
│   └── reports/
└── app/tests/
    ├── api/routes/test_pd_ecr_v1.py
    └── services/test_pd_ecr_*.py

frontend/
├── src/
│   ├── lib/pdEcrApi.ts                   # extend typed V1 API wrapper
│   ├── components/PdEcr/
│   │   ├── PdEcrCaseList.tsx
│   │   ├── PdEcrCreationWorkflow.tsx
│   │   ├── PdEcrContentBlocks.tsx
│   │   ├── PdEcrModuleDetail.tsx
│   │   ├── pdEcrState.ts
│   │   └── pdEcrExport.ts
│   └── routes/_layout/pd-ecr*.tsx
└── tests/
    ├── pd-ecr.spec.ts
    ├── pd-ecr-cases.spec.ts
    └── pd-ecr-content-export.spec.ts
```

**Structure Decision**: Use the existing web application structure. Add narrow
backend service modules only to prevent `pd_ecr.py` from growing further, but
keep route behavior and frontend routes stable for the MVP demo.

## Complexity Tracking

No constitutional violations. The only added abstraction is a small backend
service/adapter layer for case loading, retrieval normalization, generation
schema validation, and export. This is justified because the current route file
already contains list, retrieval, LLM, extraction, and report logic in one place;
the adapter layer reduces risk while preserving existing routes.
