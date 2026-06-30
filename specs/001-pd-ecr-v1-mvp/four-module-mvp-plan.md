# PD-ECR Four-Module MVP Completion Plan

**Date**: 2026-06-29  
**Status**: Active correction plan  
**Supersedes**: Any earlier MVP wording that says the generated MVP output must use six modules.

## 1. MVP Decision

The PD-ECR MVP must generate and display **four modules only**:

1. Change Description / 变更描述
2. Impact Analysis / 影响分析
3. Validation Plan / 验证计划
4. Implementation Plan / 实施计划

The following are **not standalone MVP modules**:

- Basic Information
- Reason for Change
- Validation Result
- Implementation Result
- Approval / Sign-off

These fields may still appear inside the four modules as data sections, source evidence, form fields, or export details, but they must not appear as primary generated MVP modules.

## 2. MVP User Flow

The MVP user flow is:

1. User uploads or selects historical PD-ECR cases.
2. System preserves the original display file:
   - PDF stays PDF.
   - Excel is converted to PDF for viewing.
   - Parsed text/metadata enters the knowledge base.
3. User creates a new PD-ECR request.
4. System retrieves Top K similar historical cases.
5. System generates four modules.
6. User reviews each module and checks source references.
7. User exports a draft report.

No formal approval routing, department workflow, Outlook notification, SuperOPL sync, or production release claim belongs to MVP.

## 3. Four-Module Contract

Every generated module must include:

- `id`
- `title`
- `summary`
- `content` or structured `data`
- `source_cases`
- `source_files`
- `needs_human_input`
- `warnings`

If historical evidence is insufficient, the module must set:

```json
{
  "needs_human_input": true,
  "warnings": ["No sufficient historical evidence was available."]
}
```

The system must not invent unsupported conclusions.

## 4. Module Definitions

### 4.1 Change Description / 变更描述

Purpose:

- Describe what is changing.
- Preserve user-entered change reason, current design, and proposed design.
- Summarize related historical changes if available.

Expected content:

- Change source
- Reason for change
- Current state
- Proposed state
- Affected product / part information
- Historical reference summary

Primary source:

- User input
- Similar historical case summaries
- Parsed source files

### 4.2 Impact Analysis / 影响分析

Purpose:

- Analyze which areas may be affected by the change.

Expected content:

- Function and performance impact
- Interface and appearance impact
- Reliability / robustness impact
- Supplier part impact
- Manufacturing / assembly / testing impact
- Document / BOM / drawing impact
- Inventory / delivery impact when applicable
- Cost impact note when applicable

Primary source:

- Retrieved historical impact sections
- Structured extracted checkboxes and tables
- User-provided change description

### 4.3 Validation Plan / 验证计划

Purpose:

- Turn impact risks into validation actions.

Expected content:

- Validation item
- Acceptance criteria
- Responsible person or department
- Planned due date
- Required report / evidence
- QAC or trial-run requirement when applicable

Primary source:

- Historical validation plan sections
- QAC tables
- Impact analysis output

### 4.4 Implementation Plan / 实施计划

Purpose:

- Define execution tasks needed to introduce or control the change.

Expected content:

- Task description
- Responsible department
- Owner
- Due date
- Required documents
- Open risks
- Closure evidence needed

Primary source:

- Historical implementation plans
- Document influence tables
- User input and retrieved similar cases

## 5. Historical Case Storage Rule

The system must separate **display artifact** from **knowledge artifact**.

### Display Artifact

Used when the user clicks the PDF button in historical case list/detail pages.

- Original PDF file for PDF cases.
- Converted PDF file for Excel cases.
- Must be linked from list rows using `pdf_url` where possible.
- Must preserve original visual layout as much as practical.

### Knowledge Artifact

Used for retrieval and generation.

- Parsed Markdown text.
- Extracted metadata.
- Extracted table / checkbox structure.
- Vector chunks.

The list/detail page must open the display artifact, not the parsed Markdown.

## 6. Current Code Gaps To Fix

### Gap 1: Old six-module schema remains active

Current file:

- `backend/app/services/pd_ecr_schema.py`

Current problem:

- `V1_MODULE_IDS` still defines six modules.
- `MODULE_TITLES` still maps to old template names.

Required change:

- Replace the generated MVP module contract with four module IDs:
  - `change-description`
  - `impact-analysis`
  - `validation-plan`
  - `implementation-plan`

### Gap 2: Four-module backend generator returns only three modules

Current file:

- `backend/app/services/pd_ecr_four_module_generation.py`

Current problem:

- `FOUR_GENERATED_MODULE_IDS` lists only:
  - `impact-analysis`
  - `validation-plan`
  - `implementation-plan`
- The function output omits `change-description`.

Required change:

- Add `change-description` as the first generated module.
- Ensure the returned `modules` array has exactly four modules.

### Gap 3: Frontend state still accepts mixed module systems

Current files:

- `frontend/src/components/PdEcr/pdEcrState.ts`
- `frontend/src/components/PdEcr/PdEcrModuleAccordion.tsx`
- `frontend/src/components/PdEcr/PdEcrModuleDetail.tsx`
- `frontend/src/components/PdEcr/PdEcrContentBlocks.tsx`

Current problem:

- Some code supports six-module snake_case modules.
- Some code supports four-module kebab-case modules.
- Some pages still show approval/result concepts as if they are generated modules.

Required change:

- Use four-module order for MVP display:
  1. `change-description`
  2. `impact-analysis`
  3. `validation-plan`
  4. `implementation-plan`
- Keep legacy IDs only as input adapters.
- Do not show Basic Information, Reason for Change, Approval, Validation Result, or Implementation Result as primary MVP module cards.

### Gap 4: Tests and spec documents still say six modules

Current files:

- `specs/001-pd-ecr-v1-mvp/spec.md`
- `specs/001-pd-ecr-v1-mvp/plan.md`
- `specs/001-pd-ecr-v1-mvp/tasks.md`
- `backend/app/tests/services/test_pd_ecr_schema.py`
- `backend/app/tests/services/test_pd_ecr_generation.py`
- `frontend/tests/pd-ecr.spec.ts`
- `frontend/tests/pd-ecr-content-export.spec.ts`

Required change:

- Update expectations from six modules to four modules.
- Add explicit assertion that generated MVP output contains exactly:
  - Change Description
  - Impact Analysis
  - Validation Plan
  - Implementation Plan

## 7. Implementation Tasks

### Phase 1: Contract Correction

1. Update backend module schema to define the four MVP modules.
2. Add a compatibility adapter that maps legacy six-module fields into the four-module shape.
3. Ensure `/generate-draft` and `/generate-from-change-description` return the same four-module contract.

Acceptance criteria:

- Backend generated payload contains exactly four modules.
- Every module has sources or `needs_human_input`.
- No generated MVP API response claims six modules.

### Phase 2: Generator Correction

1. Add `change-description` generation to `pd_ecr_four_module_generation.py`.
2. Make `FOUR_GENERATED_MODULE_IDS` equal:

```python
[
    "change-description",
    "impact-analysis",
    "validation-plan",
    "implementation-plan",
]
```

3. Ensure source references are preserved in all four modules.

Acceptance criteria:

- `generate_modules_from_change_description()` returns four modules.
- First module is `change-description`.
- Existing historical evidence is attached to each generated module.

### Phase 3: Frontend Display Correction

1. Update module ordering to four modules.
2. Hide non-MVP workflow panels from historical/generated MVP review.
3. Rename visible labels consistently:
   - Change Description / 变更描述
   - Impact Analysis / 影响分析
   - Validation Plan / 验证计划
   - Implementation Plan / 实施计划

Acceptance criteria:

- Content page shows exactly four primary module cards.
- Detail route works for all four module IDs.
- No six-module wording appears in MVP generation UI.

### Phase 4: Export Correction

1. Export report includes the four modules only.
2. Export includes:
   - input snapshot
   - similar cases
   - source cases
   - source files
   - draft status
3. Export keeps clear non-production wording.

Acceptance criteria:

- Exported HTML/CSV contains four module sections.
- Export does not include six-module headings.

### Phase 5: Data And Historical PDF Cleanup

1. Remove test upload data from default retrieval/demo dataset.
2. Keep historical display PDF separate from parsed knowledge text.
3. Show PDF availability status in historical case list.
4. Ensure Excel-derived historical cases link to converted PDF where conversion exists.

Acceptance criteria:

- Retrieval Top K does not include `test_upload` demo noise.
- PDF button opens full original or converted PDF.
- Missing metadata is explicit.

### Phase 6: Verification

Backend checks:

```powershell
cd backend
python -m compileall app/services/pd_ecr_schema.py app/services/pd_ecr_four_module_generation.py app/api/routes/pd_ecr.py
python -m pytest app/tests/services/test_pd_ecr_schema.py app/tests/services/test_pd_ecr_four_module_generation.py app/tests/services/test_pd_ecr_generation.py
```

Frontend checks:

```powershell
cd frontend
npm run build
npx playwright test tests/pd-ecr.spec.ts tests/pd-ecr-content-export.spec.ts --project=chromium
```

If `pytest` or Playwright is unavailable in the local shell, record the failed command and run at least:

```powershell
cd frontend
npm run build
```

## 8. MVP Done Criteria

The four-module MVP is done only when all of the following are true:

- Historical case list loads.
- PDF button opens full original PDF or converted Excel PDF.
- New PD-ECR request can retrieve similar cases.
- Draft generation returns exactly four modules.
- Frontend displays exactly four generated module cards.
- Each module shows source cases/files or a human-input warning.
- Export contains exactly four module sections.
- No primary MVP screen says six modules.
- No primary MVP generation result shows Basic Information, Reason for Change, Validation Result, Implementation Result, or Approval / Sign-off as standalone modules.
- Build passes.

## 9. Priority Order

1. Fix backend four-module contract.
2. Fix generator to return change-description plus the other three modules.
3. Fix frontend module order and labels.
4. Fix export output.
5. Clean retrieval demo data.
6. Update tests/spec wording.

## 10. Notes

This plan intentionally keeps the product narrower than the earlier six-module plan. The four-module MVP is the source of truth for the next implementation pass.

Older six-module artifacts may remain in the repository temporarily only as compatibility inputs. They must not define the generated MVP user experience.
