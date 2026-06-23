# Tasks: PD-ECR V1 MVP

**Input**: Design documents from `/specs/001-pd-ecr-v1-mvp/`

**Prerequisites**: [spec.md](./spec.md), [plan.md](./plan.md), [research.md](./research.md), [data-model.md](./data-model.md), [contracts/pd-ecr-v1-api.yaml](./contracts/pd-ecr-v1-api.yaml), [quickstart.md](./quickstart.md)

**Tests**: Include backend pytest tasks and frontend Playwright/build checks because the user explicitly requested coverage for form submission, retrieval, AI JSON validation, module display, source references, and export.

**Organization**: Tasks follow the requested implementation order: data structure -> historical loading -> backend API -> retrieval -> AI generation -> frontend pages -> report export -> integration testing. User story mapping is included where a task primarily serves US1, US2, or US3.

## Format

- `- [ ] T### [P?] [US?] Description with file path`
- `[P]` means the task can run in parallel after its prerequisites are complete.
- `[US1]` Complete AI Draft MVP Loop, `[US2]` Browse Historical PD-ECR Cases, `[US3]` Review Traceability Before Use.

---

## Stage 1: Data Structure And Case Standard

- [X] T001 Define PD-ECR V1 case JSON and metadata standard in `backend/app/services/pd_ecr_schema.py`
  - 目标: Create the canonical backend schema for HistoricalCase, HistoricalMetadata, HistoricalModule, NewPdEcrRequest, SimilarCaseResult, GeneratedDraft, GeneratedModule, and BasicReportExport.
  - 修改文件: `backend/app/services/pd_ecr_schema.py`, `backend/app/tests/services/test_pd_ecr_schema.py`.
  - 实现步骤: Add Pydantic models matching `data-model.md`; define six V1 module IDs; add alias helpers for `component_no -> part_no` and `reason -> change_reason`; add a helper that returns all required metadata keys.
  - 完成标准: Backend code can import the schema models and instantiate valid objects for all V1 entities; no approval flow, Outlook, SuperOPL, or complex permission fields are introduced.
  - 测试方式: Run `cd backend; uv run pytest app/tests/services/test_pd_ecr_schema.py`.

- [X] T002 [P] Document and normalize historical case directory conventions in `backend/app/services/pd_ecr_case_paths.py`
  - 目标: Centralize where V1 reads Markdown, JSON, OCR metadata, clean text, generated reports, and curated case files.
  - 修改文件: `backend/app/services/pd_ecr_case_paths.py`, `backend/app/tests/services/test_pd_ecr_case_paths.py`.
  - 实现步骤: Define path constants for `backend/app/data/pd_ecr_cases`, `backend/app/rag/knowledge`, `backend/app/rag/pdecr_knowledge`, `backend/app/rag/jie_jim_knowledge_pdf`, and report output; add safe path iteration helpers that ignore binary files and duplicate copy files where appropriate.
  - 完成标准: Loader code has one source for all PD-ECR case paths and can list candidate Markdown/JSON files without scanning unrelated folders.
  - 测试方式: Run `cd backend; uv run pytest app/tests/services/test_pd_ecr_case_paths.py`.

- [X] T003 Implement historical case loading function in `backend/app/services/pd_ecr_case_loader.py`
  - 目标: Load historical PD-ECR cases from JSON metadata, parsed OCR JSON, Markdown, and clean text into the V1 HistoricalCase shape.
  - 修改文件: `backend/app/services/pd_ecr_case_loader.py`, `backend/app/tests/services/test_pd_ecr_case_loader.py`.
  - 实现步骤: Read structured JSON first; read OCR `*metadata.json` and companion Markdown files; fallback to Markdown/clean text; derive `case_id` from metadata or filename; normalize existing fields such as `component_no`, `affected_product_no`, and `Customer_project_Name`; extract module summaries when module content exists.
  - 完成标准: Loading returns a list of HistoricalCase-like objects with `case_id`, `metadata`, `source_file`, `modules`, and `missing_fields`.
  - 测试方式: Run `cd backend; uv run pytest app/tests/services/test_pd_ecr_case_loader.py`.

- [X] T004 Add basic data quality checks in `backend/app/services/pd_ecr_quality.py`
  - 目标: Validate required V1 metadata and source traceability without blocking demo use when historical data is incomplete.
  - 修改文件: `backend/app/services/pd_ecr_quality.py`, `backend/app/tests/services/test_pd_ecr_quality.py`.
  - 实现步骤: Add checks for `case_id`, `dc_no`, `mcr_no`, `change_type`, `product_no`, `part_no`, `customer_project`, and `source_file`; return warnings and `missing_fields`; add duplicate `case_id` detection; add source-file existence checks.
  - 完成标准: Incomplete cases are kept but explicitly marked; no field disappears silently.
  - 测试方式: Run `cd backend; uv run pytest app/tests/services/test_pd_ecr_quality.py`.

---

## Stage 2: Backend Base API

- [X] T005 [US2] Implement historical case list API in `backend/app/api/routes/pd_ecr.py`
  - 目标: Extend the existing `GET /api/v1/pd-ecr/cases` endpoint to return normalized V1 metadata while preserving current frontend compatibility.
  - 修改文件: `backend/app/api/routes/pd_ecr.py`, `backend/app/services/pd_ecr_case_loader.py`, `backend/app/tests/api/routes/test_pd_ecr_v1.py`.
  - 实现步骤: Call the new loader; include `case_id`, `metadata`, `source_file`, `missing_fields`, and `module_summary`; keep legacy fields such as `case_no`, `customer`, `project`, and `part_number` for current UI fallback.
  - 完成标准: The endpoint returns historical cases with required metadata fields or explicit missing-field indicators.
  - 测试方式: Run `cd backend; uv run pytest app/tests/api/routes/test_pd_ecr_v1.py -k case_list`.

- [X] T006 [US2] Implement historical case detail API in `backend/app/api/routes/pd_ecr.py`
  - 目标: Add `GET /api/v1/pd-ecr/cases/{case_id}` for metadata and modular historical content.
  - 修改文件: `backend/app/api/routes/pd_ecr.py`, `backend/app/services/pd_ecr_case_loader.py`, `backend/app/tests/api/routes/test_pd_ecr_v1.py`.
  - 实现步骤: Resolve by `case_id`, DC No, filename stem, or source file; return metadata, modules, source trace, source file, and missing fields; keep `/cases/modules?case_no=` working as a compatibility endpoint.
  - 完成标准: A selected historical case can be opened without relying only on local frontend state.
  - 测试方式: Run `cd backend; uv run pytest app/tests/api/routes/test_pd_ecr_v1.py -k case_detail`.

- [X] T007 [US1] Implement new PD-ECR form submit API in `backend/app/api/routes/pd_ecr.py`
  - 目标: Add `POST /api/v1/pd-ecr/requests` to validate and echo the new PD-ECR input snapshot.
  - 修改文件: `backend/app/api/routes/pd_ecr.py`, `backend/app/services/pd_ecr_schema.py`, `backend/app/tests/api/routes/test_pd_ecr_v1.py`.
  - 实现步骤: Accept required fields DC No, MCR No, customer project, product number, part number, change type, change description, and change reason; map existing aliases; return a deterministic `request_id`; return validation errors for missing required fields.
  - 完成标准: Form submission can be validated before retrieval or generation.
  - 测试方式: Run `cd backend; uv run pytest app/tests/api/routes/test_pd_ecr_v1.py -k request_validation`.

- [X] T008 [US1] Implement generated module result API in `backend/app/api/routes/pd_ecr.py`
  - 目标: Add `GET /api/v1/pd-ecr/drafts/{draft_id}/modules` returning six V1 modules from cached or generated draft state.
  - 修改文件: `backend/app/api/routes/pd_ecr.py`, `backend/app/services/pd_ecr_generation.py`, `backend/app/tests/api/routes/test_pd_ecr_v1.py`.
  - 实现步骤: Add a minimal draft cache lookup; return `draft_status`, `draft_id`, and six modules; fallback to existing module-draft data only when it can be mapped to V1 modules.
  - 完成标准: Frontend can request generated modules by `draft_id` and receive the six required V1 module IDs.
  - 测试方式: Run `cd backend; uv run pytest app/tests/api/routes/test_pd_ecr_v1.py -k draft_modules`.

---

## Stage 3: Similar Case Retrieval

- [X] T009 [US1] Build historical case retrieval index adapter in `backend/app/services/pd_ecr_retrieval.py`
  - 目标: Create a V1 retrieval adapter over existing `backend/app/rag/retriever.py` and historical case loader output.
  - 修改文件: `backend/app/services/pd_ecr_retrieval.py`, `backend/app/rag/retriever.py`, `backend/app/tests/services/test_pd_ecr_retrieval.py`.
  - 实现步骤: Build query text from request fields; call existing FAISS/keyword retrieval; map raw retrieval chunks to normalized cases; deduplicate by `case_id` or `source_file`.
  - 完成标准: Service returns candidate SimilarCaseResult objects without changing the existing FAISS index format.
  - 测试方式: Run `cd backend; uv run pytest app/tests/services/test_pd_ecr_retrieval.py -k index_adapter`.

- [X] T010 [P] [US1] Implement metadata filter logic in `backend/app/services/pd_ecr_retrieval.py`
  - 目标: Boost or filter retrieval results by customer project, product number, part number, and change type.
  - 修改文件: `backend/app/services/pd_ecr_retrieval.py`, `backend/app/tests/services/test_pd_ecr_retrieval.py`.
  - 实现步骤: Add exact and fuzzy string matching helpers; compute `matched_fields`; add metadata score boost; ensure missing metadata does not crash retrieval.
  - 完成标准: Results that match metadata rank above otherwise similar results, and `matched_fields` explains why.
  - 测试方式: Run `cd backend; uv run pytest app/tests/services/test_pd_ecr_retrieval.py -k metadata_filter`.

- [X] T011 [P] [US1] Implement keyword retrieval enhancement in `backend/app/services/pd_ecr_retrieval.py`
  - 目标: Improve keyword fallback and hybrid scoring for change description and change reason.
  - 修改文件: `backend/app/services/pd_ecr_retrieval.py`, `backend/app/rag/retriever.py`, `backend/app/tests/services/test_pd_ecr_retrieval.py`.
  - 实现步骤: Extract meaningful tokens from request fields; ignore generic PD-ECR stop words; score keyword hits in metadata, raw text, and module summaries; record keyword hits in retrieval context.
  - 完成标准: Retrieval works when FAISS is unavailable and still returns source-backed results.
  - 测试方式: Run `cd backend; uv run pytest app/tests/services/test_pd_ecr_retrieval.py -k keyword`.

- [X] T012 [US1] Implement Top K similar case API in `backend/app/api/routes/pd_ecr.py`
  - 目标: Add `POST /api/v1/pd-ecr/retrieve` returning ranked Top K similar historical cases.
  - 修改文件: `backend/app/api/routes/pd_ecr.py`, `backend/app/services/pd_ecr_retrieval.py`, `backend/app/tests/api/routes/test_pd_ecr_v1.py`.
  - 实现步骤: Accept `input`, `top_k`, and optional filters; default Top K to 5; call retrieval adapter; return `query_input`, `top_k`, and ranked `results`; keep `/history/search` and `/test-rag` compatibility.
  - 完成标准: API returns no more than requested Top K and fewer results gracefully when fewer matches exist.
  - 测试方式: Run `cd backend; uv run pytest app/tests/api/routes/test_pd_ecr_v1.py -k retrieve`.

- [X] T013 [US1] Preserve retrieval trace fields in `backend/app/services/pd_ecr_retrieval.py`
  - 目标: Ensure every Top K result includes `case_id`, `source_file`, `matched_fields`, `similarity_score`, and module summary.
  - 修改文件: `backend/app/services/pd_ecr_retrieval.py`, `frontend/src/lib/pdEcrApi.ts`, `backend/app/tests/services/test_pd_ecr_retrieval.py`.
  - 实现步骤: Add response normalization for required result fields; include `source_cases` and `source_files`; update frontend TypeScript types to match the V1 retrieval contract.
  - 完成标准: The retrieval response can be used directly by AI generation and frontend display without losing source references.
  - 测试方式: Run `cd backend; uv run pytest app/tests/services/test_pd_ecr_retrieval.py -k trace_fields` and `cd frontend; npm run build`.

---

## Stage 4: AI Draft Generation

- [X] T014 [US1] Design AI generation prompt in `backend/app/services/pd_ecr_generation.py`
  - 目标: Build a prompt that uses user input and similar cases to generate only source-grounded V1 draft JSON.
  - 修改文件: `backend/app/services/pd_ecr_generation.py`, `backend/app/tests/services/test_pd_ecr_generation.py`.
  - 实现步骤: Add prompt template with six module names; include Top K evidence snippets; instruct the model to use `needs_human_input` when evidence is insufficient; require `draft_status: V1_MVP_DRAFT`.
  - 完成标准: Prompt text contains no production approval claims and explicitly requires source cases/files.
  - 测试方式: Run `cd backend; uv run pytest app/tests/services/test_pd_ecr_generation.py -k prompt`.

- [X] T015 [P] [US1] Define AI output JSON schema in `backend/app/services/pd_ecr_generation.py`
  - 目标: Define and validate the generated draft JSON schema for the six V1 modules.
  - 修改文件: `backend/app/services/pd_ecr_generation.py`, `backend/app/services/pd_ecr_schema.py`, `backend/app/tests/services/test_pd_ecr_generation.py`.
  - 实现步骤: Add parser/validator for `GeneratedDraft`; require exactly six module IDs; reject malformed JSON; normalize model output keys if they are close but not exact.
  - 完成标准: Invalid AI output fails with a clear validation error before frontend display.
  - 测试方式: Run `cd backend; uv run pytest app/tests/services/test_pd_ecr_generation.py -k schema`.

- [X] T016 [US1] Implement draft generation API in `backend/app/api/routes/pd_ecr.py`
  - 目标: Add `POST /api/v1/pd-ecr/generate-draft` using validated user input and similar cases.
  - 修改文件: `backend/app/api/routes/pd_ecr.py`, `backend/app/services/pd_ecr_generation.py`, `backend/app/tests/api/routes/test_pd_ecr_v1.py`.
  - 实现步骤: Accept input and optional precomputed similar cases; call retrieval if similar cases are absent; call LLM or existing generation internals; return GeneratedDraft; keep `/generate-report` compatibility.
  - 完成标准: API returns a six-module draft with `draft_id`, `draft_status`, input snapshot, similar cases, and modules.
  - 测试方式: Run `cd backend; uv run pytest app/tests/api/routes/test_pd_ecr_v1.py -k generate_draft`.

- [X] T017 [US3] Add source case and source file references in `backend/app/services/pd_ecr_generation.py`
  - 目标: Attach `source_cases` and `source_files` to each generated module wherever historical evidence was used.
  - 修改文件: `backend/app/services/pd_ecr_generation.py`, `backend/app/tests/services/test_pd_ecr_generation.py`.
  - 实现步骤: Pass source metadata into the prompt; post-process generated modules to add missing source references from retrieval context when evidence exists; mark modules with no evidence as `needs_human_input`.
  - 完成标准: Evidence-backed modules have at least one source case or source file; unsupported modules are visibly flagged.
  - 测试方式: Run `cd backend; uv run pytest app/tests/services/test_pd_ecr_generation.py -k source_refs`.

- [X] T018 [US3] Add AI output structure validation errors in `backend/app/api/routes/pd_ecr.py`
  - 目标: Surface actionable errors for malformed JSON, missing modules, missing sources, or empty generic output.
  - 修改文件: `backend/app/api/routes/pd_ecr.py`, `backend/app/services/pd_ecr_generation.py`, `backend/app/tests/api/routes/test_pd_ecr_v1.py`.
  - 实现步骤: Catch validation failures; return HTTP 422 for invalid structure; include safe detail messages; log generation failures without exposing secrets.
  - 完成标准: Bad AI output cannot be exported or displayed as a valid draft.
  - 测试方式: Run `cd backend; uv run pytest app/tests/api/routes/test_pd_ecr_v1.py -k generation_validation`.

---

## Stage 5: Frontend Pages

- [X] T019 [US2] Develop PD-ECR Case List page updates in `frontend/src/components/PdEcr/PdEcrCaseList.tsx`
  - 目标: Display V1 historical metadata in the existing case list page.
  - 修改文件: `frontend/src/components/PdEcr/PdEcrCaseList.tsx`, `frontend/src/lib/pdEcrApi.ts`, `frontend/tests/pd-ecr-cases.spec.ts`.
  - 实现步骤: Update API response types; add columns or compact fields for case_id, DC No, MCR No, customer project, product number, part number, change type, source file, and missing fields; keep existing filter/export actions working.
  - 完成标准: Users can scan and filter historical cases and see source file information.
  - 测试方式: Run `cd frontend; npm run build` and `cd frontend; npx playwright test tests/pd-ecr-cases.spec.ts --project=chromium`.

- [X] T020 [US2] Develop Case Detail page behavior in `frontend/src/components/PdEcr/PdEcrModuleDetail.tsx`
  - 目标: Show selected historical case metadata and module content from the detail API.
  - 修改文件: `frontend/src/components/PdEcr/PdEcrCaseList.tsx`, `frontend/src/components/PdEcr/PdEcrModuleDetail.tsx`, `frontend/src/components/PdEcr/pdEcrState.ts`, `frontend/tests/pd-ecr-cases.spec.ts`.
  - 实现步骤: Fetch case detail when a case is opened; persist active case result; show metadata and source file above module content; fallback to `/cases/modules` if the V1 detail endpoint is unavailable.
  - 完成标准: Opening a historical case shows metadata and module content together.
  - 测试方式: Run `cd frontend; npx playwright test tests/pd-ecr-cases.spec.ts --project=chromium`.

- [X] T021 [US1] Develop New PD-ECR Form page fields in `frontend/src/components/PdEcr/PdEcrCreationWorkflow.tsx`
  - 目标: Capture all required V1 input fields before retrieval and AI generation.
  - 修改文件: `frontend/src/components/PdEcr/PdEcrCreationWorkflow.tsx`, `frontend/src/lib/pdEcrApi.ts`, `frontend/tests/pd-ecr.spec.ts`.
  - 实现步骤: Add MCR No and change type fields if absent; map component number to `part_no`; map reason/change proposal to V1 input; block retrieve/generate until required fields are filled; show clear validation messages.
  - 完成标准: Users can submit DC No, MCR No, customer project, product number, part number, change type, change description, and change reason.
  - 测试方式: Run `cd frontend; npm run build` and `cd frontend; npx playwright test tests/pd-ecr.spec.ts --project=chromium`.

- [X] T022 [US1] Develop Similar Cases display area in `frontend/src/components/PdEcr/PdEcrCreationWorkflow.tsx`
  - 目标: Show Top K similar historical cases with V1 trace fields after retrieval.
  - 修改文件: `frontend/src/components/PdEcr/PdEcrCreationWorkflow.tsx`, `frontend/src/components/PdEcr/pdEcrState.ts`, `frontend/src/lib/pdEcrApi.ts`, `frontend/tests/pd-ecr.spec.ts`.
  - 实现步骤: Call `/retrieve`; display case_id, DC No, change type, matched fields, similarity score, source file, and module summary; store similar cases for generation and export.
  - 完成标准: Users can understand why each historical case matched.
  - 测试方式: Run `cd frontend; npx playwright test tests/pd-ecr.spec.ts --project=chromium`.

- [X] T023 [US1] Develop Generated Modules page in `frontend/src/components/PdEcr/PdEcrContentBlocks.tsx`
  - 目标: Display the six required V1 generated modules instead of only the legacy four-module set.
  - 修改文件: `frontend/src/components/PdEcr/PdEcrContentBlocks.tsx`, `frontend/src/components/PdEcr/pdEcrState.ts`, `frontend/tests/pd-ecr.spec.ts`.
  - 实现步骤: Update module order to Basic Information, Change Description, Reason for Change, Impact Analysis, Implementation Plan, and Approval / Sign-off Information; normalize legacy responses into this shape; show draft/demo status.
  - 完成标准: The generated modules page always shows six V1 module cards.
  - 测试方式: Run `cd frontend; npm run build` and `cd frontend; npx playwright test tests/pd-ecr.spec.ts --project=chromium`.

- [X] T024 [US1] Implement module switching display in `frontend/src/components/PdEcr/PdEcrModuleDetail.tsx`
  - 目标: Allow users to click each V1 module and view corresponding content.
  - 修改文件: `frontend/src/components/PdEcr/PdEcrContentBlocks.tsx`, `frontend/src/components/PdEcr/PdEcrModuleDetail.tsx`, `frontend/src/routes/_layout/pd-ecr_.content_.$moduleId.tsx`, `frontend/tests/pd-ecr.spec.ts`.
  - 实现步骤: Support V1 module IDs in route params; map old module IDs only as fallbacks; render strings and structured JSON content cleanly; preserve back navigation.
  - 完成标准: Clicking all six module cards opens a readable detail view.
  - 测试方式: Run `cd frontend; npx playwright test tests/pd-ecr.spec.ts --project=chromium`.

- [X] T025 [US3] Show AI source references in `frontend/src/components/PdEcr/PdEcrModuleDetail.tsx`
  - 目标: Make source cases, source files, and human-input warnings visible in generated module detail.
  - 修改文件: `frontend/src/components/PdEcr/PdEcrModuleDetail.tsx`, `frontend/src/components/PdEcr/pdEcrState.ts`, `frontend/tests/pd-ecr.spec.ts`.
  - 实现步骤: Render `source_cases`, `source_files`, `needs_human_input`, and `warnings`; add empty-state copy for modules without evidence; ensure export data includes these fields.
  - 完成标准: Users can trace AI content sources or see that human input is required.
  - 测试方式: Run `cd frontend; npx playwright test tests/pd-ecr.spec.ts --project=chromium`.

---

## Stage 6: Report Export

- [X] T026 [US1] Implement basic report export API in `backend/app/api/routes/pd_ecr.py`
  - 目标: Add `POST /api/v1/pd-ecr/export` for HTML or CSV report export from a V1 generated draft.
  - 修改文件: `backend/app/api/routes/pd_ecr.py`, `backend/app/services/pd_ecr_export.py`, `backend/app/tests/api/routes/test_pd_ecr_v1.py`.
  - 实现步骤: Accept `draft_id`, format, and optional draft payload; render report with submitted input, similar cases, six modules, source references, and `V1_MVP_DRAFT`; reuse existing report directory.
  - 完成标准: Export response includes `export_id`, `draft_id`, `format`, `draft_status`, `source_files`, and optional download URL.
  - 测试方式: Run `cd backend; uv run pytest app/tests/api/routes/test_pd_ecr_v1.py -k export`.

- [X] T027 [US1] Ensure frontend export includes input, modules, and source cases in `frontend/src/components/PdEcr/pdEcrExport.ts`
  - 目标: Update client-side export to include V1 source traceability and draft/demo status.
  - 修改文件: `frontend/src/components/PdEcr/pdEcrExport.ts`, `frontend/src/components/PdEcr/PdEcrContentBlocks.tsx`, `frontend/tests/pd-ecr-content-export.spec.ts`.
  - 实现步骤: Add submitted input snapshot, similar case table, six module sections, source case/source file fields, warnings, and V1 MVP draft badge; keep existing HTML/CSV download helpers.
  - 完成标准: Downloaded report contains user input, generated module content, similar case references, and source references.
  - 测试方式: Run `cd frontend; npx playwright test tests/pd-ecr-content-export.spec.ts --project=chromium`.

---

## Stage 7: Integration Testing And Pilot Readiness

- [X] T028 [US1] Run and fix full MVP flow integration in `frontend/tests/pd-ecr.spec.ts`
  - 目标: Validate fill form -> retrieve cases -> AI generate -> module display -> export report as one continuous demo flow.
  - 修改文件: `frontend/tests/pd-ecr.spec.ts`, `backend/app/tests/api/routes/test_pd_ecr_v1.py`, any files required by failures.
  - 实现步骤: Mock or seed backend responses for stable CI; run the real local flow when services are available; fix broken field mappings, route params, and response normalization.
  - 完成标准: The full MVP flow passes with visible source references and exported output.
  - 测试方式: Run `cd frontend; npx playwright test tests/pd-ecr.spec.ts --project=chromium` and `cd backend; uv run pytest app/tests/api/routes/test_pd_ecr_v1.py`.

- [X] T029 [P] Prepare 5-10 pilot test cases in `backend/app/data/pd_ecr_cases/pilot_cases.json`
  - 目标: Create a small repeatable dataset for retrieval, generation, and demo validation.
  - 修改文件: `backend/app/data/pd_ecr_cases/pilot_cases.json`, `backend/app/tests/services/test_pd_ecr_case_loader.py`.
  - 实现步骤: Select 5-10 historical cases from existing Markdown/JSON sources; record canonical metadata and source files; include at least one incomplete metadata case; avoid copying large source documents.
  - 完成标准: Pilot cases cover different customer projects, product/part numbers, and change types.
  - 测试方式: Run `cd backend; uv run pytest app/tests/services/test_pd_ecr_case_loader.py -k pilot`.

- [X] T030 [P] Record retrieval and generation issue log in `specs/001-pd-ecr-v1-mvp/pilot-issue-log.md`
  - 目标: Track retrieval errors, field gaps, missing sources, and generic AI output during V1 validation.
  - 修改文件: `specs/001-pd-ecr-v1-mvp/pilot-issue-log.md`.
  - 实现步骤: Add sections for retrieval errors, missing fields, missing source references, generic generated content, export defects, and follow-up owner/status; fill initial entries from test runs.
  - 完成标准: Pilot defects are captured in a repeatable review format without adding production audit logging.
  - 测试方式: Manual review that the log includes at least one template row for each issue category.

- [X] T031 [P] Create V1 pilot feedback form in `specs/001-pd-ecr-v1-mvp/pilot-feedback-form.md`
  - 目标: Prepare a lightweight feedback form for trial users to evaluate V1 usefulness and source traceability.
  - 修改文件: `specs/001-pd-ecr-v1-mvp/pilot-feedback-form.md`.
  - 实现步骤: Add questions for task completion, retrieval relevance, generated module usefulness, source-reference clarity, export quality, and next-priority feedback; include a clear note that V1 is not production approval.
  - 完成标准: The form can be used after a pilot session without implying formal production readiness.
  - 测试方式: Manual review that all success criteria from `spec.md` are represented in feedback questions.

---

## Dependencies & Execution Order

### Phase Dependencies

- Stage 1 blocks all later stages because schemas, paths, loader, and quality checks define the shared contract.
- Stage 2 depends on Stage 1 and creates stable API surfaces for historical browsing and request validation.
- Stage 3 depends on Stages 1-2 and creates source-preserving Top K retrieval.
- Stage 4 depends on Stage 3 because AI generation must consume similar cases and source context.
- Stage 5 depends on Stages 2-4 for typed API responses and generated draft shape.
- Stage 6 depends on Stage 4 and Stage 5 data shape.
- Stage 7 depends on the full vertical slice.

### User Story Mapping

- **US1 Complete AI Draft MVP Loop**: T007-T018, T021-T024, T026-T028.
- **US2 Browse Historical PD-ECR Cases**: T005-T006, T019-T020.
- **US3 Review Traceability Before Use**: T017-T018, T025.
- **Foundational / Cross-cutting**: T001-T004, T029-T031.

### Parallel Opportunities

- T002 can run after T001 starts if path helpers avoid schema internals.
- T010 and T011 can run in parallel after T009.
- T014 and T015 can run in parallel after T013.
- T019 and T021 can run in parallel after API types in T013 are stable.
- T029, T030, and T031 can run in parallel after Stage 1, but final content should be refreshed after integration testing.

---

## Independent Test Criteria

- **US1**: Fill a new PD-ECR form, retrieve Top K cases, generate a six-module draft, open every module, see source references, and export a report.
- **US2**: Open the historical case list, select one case, and see metadata, missing-field indicators, source file, and module content.
- **US3**: Open generated modules and verify every evidence-backed module shows source cases or source files, while unsupported content is marked for human input.

---

## Implementation Strategy

### MVP First

1. Complete T001-T004.
2. Complete T005, T007, T009, T012, T013.
3. Complete T014-T018.
4. Complete T021-T025.
5. Complete T026-T028.
6. Validate the end-to-end flow before adding pilot polish tasks T029-T031.

### Incremental Delivery

1. Historical data contract and loader.
2. Case list/detail APIs and UI.
3. Retrieval response with source references.
4. Six-module generated draft.
5. Frontend module display and source traceability.
6. Export and pilot validation.

### Out Of Scope For All Tasks

- Complete approval workflow.
- Multi-person sign-off routing.
- Complex role permissions.
- Outlook automatic notification.
- SuperOPL automatic synchronization.
- Enterprise-grade audit logs.

---

## Validation Commands

```powershell
cd backend
uv run pytest app/tests/services/test_pd_ecr_schema.py app/tests/services/test_pd_ecr_case_loader.py app/tests/services/test_pd_ecr_retrieval.py app/tests/services/test_pd_ecr_generation.py app/tests/api/routes/test_pd_ecr_v1.py
```

```powershell
cd frontend
npm run build
npx playwright test tests/pd-ecr.spec.ts tests/pd-ecr-cases.spec.ts tests/pd-ecr-content-export.spec.ts --project=chromium
```

## Notes

- Each task is intentionally small enough for stepwise Codex implementation.
- Every top-level task uses the required checkbox + task ID + optional story label + file path format.
- Tests should be run per task where practical; full validation should run after T028.
