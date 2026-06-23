# Feature Specification: PD-ECR V1 MVP

**Feature Branch**: `001-pd-ecr-v1-mvp`

**Created**: 2026-06-16

**Status**: Draft

**Input**: User description: "开发 PD-ECR V1 MVP，用于验证历史相似案例检索和 AI 辅助生成 PD-ECR 草稿的核心流程。用户可以查看历史 PD-ECR case 列表和详情，填写新建 PD-ECR 表单，检索 Top K 相似案例，生成模块化 AI 草稿，追溯来源案例或文件，并导出基础报告。V1 不包含完整审批流、多人会签、复杂角色权限、Outlook 自动通知、SuperOPL 自动同步和企业级审计日志。"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Complete AI Draft MVP Loop (Priority: P1)

A PD-ECR user fills in a new-change form, requests similar historical cases,
reviews the Top K results, generates a new PD-ECR draft, inspects the generated
modules, and exports a basic report for review.

**Why this priority**: This is the core MVP loop that proves whether historical
retrieval plus AI-assisted drafting can produce a usable PD-ECR starting point.

**Independent Test**: Start with an available historical knowledge base, complete
the new PD-ECR form, submit it, confirm similar cases are shown, generate the
draft, open each module, verify source references are visible, and export the
report.

**Acceptance Scenarios**:

1. **Given** historical cases are available and the user has entered DC No, MCR No,
   customer project, product number, part number, change type, change description,
   and change reason, **When** the user submits the form, **Then** the system
   returns a ranked list of similar historical cases.
2. **Given** similar historical cases are displayed, **When** the user requests AI
   draft generation, **Then** the system creates a PD-ECR draft with the six
   required modules and visible source references where evidence exists.
3. **Given** a generated draft is displayed, **When** the user exports the report,
   **Then** the exported report includes the form information, generated modules,
   similar case references, and draft/demo status.

---

### User Story 2 - Browse Historical PD-ECR Cases (Priority: P2)

A PD-ECR user opens the historical case area, scans the case list, opens a case
detail page, and reviews the case metadata and modular content before using it as
context for a new draft.

**Why this priority**: Users need confidence in the historical knowledge base and
must be able to inspect the evidence behind retrieval results.

**Independent Test**: Open the historical case list, select one case, and verify
that the detail view shows required metadata, source file information, and
available PD-ECR module content.

**Acceptance Scenarios**:

1. **Given** historical cases are available, **When** the user opens the historical
   case list, **Then** each listed case shows enough identifying information to
   distinguish it from other cases.
2. **Given** the user selects a historical case, **When** the case detail opens,
   **Then** metadata and module content are shown together with the source file.

---

### User Story 3 - Review Traceability Before Use (Priority: P3)

A PD-ECR user reviews generated modules and similar-case summaries to understand
which historical cases or files support the generated content before using the
draft outside the MVP.

**Why this priority**: Source traceability is required for trust and for preventing
unsupported AI conclusions from being treated as approved engineering content.

**Independent Test**: Generate a draft from a form submission, open each major
module, and verify that source cases or source files are shown for generated
content where historical evidence contributed to the output.

**Acceptance Scenarios**:

1. **Given** a generated module contains AI-assisted content based on retrieved
   cases, **When** the user opens the module, **Then** the module shows associated
   source cases or source files.
2. **Given** no sufficient evidence exists for a module or statement, **When** the
   draft is displayed, **Then** the unsupported area is marked as requiring human
   input rather than shown as a sourced conclusion.

### Edge Cases

- Historical case list is empty: the user sees an empty-state message and can
  still fill in a new PD-ECR form, but generated content must mark unsupported
  areas as requiring human input.
- A historical case is missing one or more metadata fields: the detail and result
  views show the missing fields explicitly rather than hiding them.
- Similarity search finds fewer than the requested Top K cases: the system shows
  all available matches and states that fewer matches were found.
- User submits an incomplete new PD-ECR form: the system identifies required
  missing fields before retrieval or draft generation.
- Retrieved cases have source files but limited module summaries: result cards
  still show source files and mark unavailable summaries clearly.
- AI generation cannot complete: the user keeps the submitted form values and
  similar-case results, and receives a clear retry or fallback message.
- Export is requested before draft generation: the system prevents export or
  exports only clearly marked available content.

## Requirements *(mandatory)*

### Constitution Alignment *(mandatory for PD-ECR work)*

- **V1 Scope**: This feature covers historical case browsing, similar-case
  retrieval, AI draft generation, modular display, and basic report export. Full
  approval flow, multi-person sign-off, complex role permissions, Outlook
  notification, SuperOPL synchronization, and enterprise audit logs are deferred
  to post-V1.
- **Source Grounding**: Generated draft modules must retain source_cases or
  source_files where historical evidence contributes to the content. Unsupported
  conclusions must be marked as requiring human input.
- **Historical Metadata**: The feature reads, displays, and carries through
  case_id, DC No, MCR No, change_type, product_no, part_no, customer_project, and
  source_file.
- **PD-ECR Modules**: The generated draft must include Basic Information, Change
  Description, Reason for Change, Impact Analysis, Implementation Plan, and
  Approval / Sign-off Information.
- **Non-Production Positioning**: Generated content and exported reports must
  remain clearly marked as V1 MVP drafts for demo, trial, or validation use.

### Functional Requirements

- **FR-001**: Users MUST be able to view a historical PD-ECR case list.
- **FR-002**: Each historical case list item MUST show case_id, DC No when
  available, change type when available, customer project when available, and
  source_file.
- **FR-003**: Users MUST be able to open a historical case detail view.
- **FR-004**: Historical case details MUST show available metadata and available
  modular content for that case.
- **FR-005**: The system MUST explicitly show when required historical metadata is
  missing rather than silently omitting the field.
- **FR-006**: Users MUST be able to fill in a new PD-ECR form with DC No, MCR No,
  customer project, product number, part number, change type, change description,
  and change reason.
- **FR-007**: The system MUST prevent retrieval and draft generation until all
  required new PD-ECR form fields are present.
- **FR-008**: After form submission, the system MUST retrieve and display Top K
  similar historical cases. If the user does not select K, the default MUST be 5.
- **FR-009**: Each similar-case result MUST show case_id, DC No when available,
  change type, similarity reason, source_file, and relevant module summary.
- **FR-010**: Similar-case results MUST be ranked so the user can distinguish the
  strongest matches from weaker matches.
- **FR-011**: The system MUST generate a new PD-ECR draft from user input and
  retrieved similar historical cases.
- **FR-012**: The generated draft MUST be organized into these modules: Basic
  Information, Change Description, Reason for Change, Impact Analysis,
  Implementation Plan, and Approval / Sign-off Information.
- **FR-013**: Users MUST be able to click or select each generated module to view
  its corresponding content.
- **FR-014**: Each major generated module MUST show source_cases or source_files
  when generated content is based on historical evidence.
- **FR-015**: Generated content without adequate historical evidence MUST be
  labeled as requiring human input or review.
- **FR-016**: Users MUST be able to export a basic report containing submitted
  form data, similar-case references, generated modules, source references, and
  draft/demo status.
- **FR-017**: The system MUST keep the complete MVP flow available in one
  continuous user journey: fill form, retrieve cases, generate draft, review
  modules, and export report.
- **FR-018**: V1 MUST NOT include complete approval workflow, multi-person
  sign-off routing, complex role permissions, Outlook automatic notification,
  SuperOPL automatic synchronization, or enterprise-grade audit logs.

### Key Entities *(include if feature involves data)*

- **Historical Case**: A prior PD-ECR case available for browsing, retrieval, and
  evidence. Key attributes include case_id, DC No, MCR No, change_type,
  product_no, part_no, customer_project, source_file, and available module
  content.
- **Historical Metadata**: The standardized identifying information attached to a
  historical case and preserved through list, detail, retrieval, generation, and
  export views.
- **New PD-ECR Request**: User-entered input for a new draft, including DC No,
  MCR No, customer project, product number, part number, change type, change
  description, and change reason.
- **Similar Case Result**: A ranked retrieval result that links a Historical Case
  to the New PD-ECR Request with a similarity reason, source file, and relevant
  module summary.
- **Generated Draft**: The AI-assisted PD-ECR output created from user input and
  similar historical cases, organized into six required modules.
- **Generated Module**: One section of the Generated Draft, with module name,
  content, review status, and source_cases or source_files when available.
- **Basic Report Export**: A report-ready output containing request data,
  retrieval results, generated modules, source references, and draft/demo status.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A user can complete the full MVP flow from form entry to report
  export in 10 minutes or less using available historical case data.
- **SC-002**: 100% of generated drafts contain all six required PD-ECR modules,
  even when some modules are marked as requiring human input.
- **SC-003**: 100% of generated modules based on historical evidence display at
  least one source case or source file reference.
- **SC-004**: For a standard submitted form, users see up to 5 similar cases by
  default and can identify each match by case_id, change type, similarity reason,
  and source file.
- **SC-005**: 100% of historical case detail views display the required metadata
  fields or explicit missing-field indicators.
- **SC-006**: During MVP validation, at least 80% of trial users can locate the
  generated module content and source references without assistance.
- **SC-007**: Exported reports include submitted form data, generated module
  content, source references, and draft/demo status in 100% of successful exports.

## Assumptions

- The initial user is an internal PD-ECR contributor or reviewer validating an MVP
  workflow, not an external production user.
- Historical case data and source files already exist in the project knowledge
  base, though some records may have incomplete metadata.
- Authentication and basic access to the application already exist; V1 does not
  add a new permission model.
- Basic report export means a simple report-ready file or download suitable for
  review, not a formally approved production PD-ECR package.
- Top K defaults to 5 when the user does not choose a different number.
- Generated drafts are editable or reviewable outside the formal production
  approval process; V1 does not submit them for official approval.
