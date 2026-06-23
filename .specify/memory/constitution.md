<!--
Sync Impact Report
Version change: template -> 1.0.0
Modified principles:
- Template principle 1 -> I. MVP Scope Discipline
- Template principle 2 -> II. Source-Grounded AI Output
- Template principle 3 -> III. Unified Historical Metadata
- Template principle 4 -> IV. Modular PD-ECR Result Contract
- Template principle 5 -> V. Minimal Change in Existing Structure
- Added: VI. Demo-Ready, Non-Production V1
Added sections:
- V1 Product Boundaries
- Development Workflow and Quality Gates
Removed sections:
- Placeholder Section 2
- Placeholder Section 3
Templates requiring updates:
- ✅ .specify/templates/plan-template.md
- ✅ .specify/templates/spec-template.md
- ✅ .specify/templates/tasks-template.md
- ⚠ .specify/templates/commands/*.md not present in this repository
Runtime guidance docs reviewed:
- ✅ AGENTS.md
- ✅ README.md
- ✅ backend/README.md
- ✅ frontend/README.md
- ✅ docs/superpowers/plans/2026-06-05-pd-ecr-platform.md
- ✅ docs/superpowers/specs/2026-06-05-pd-ecr-platform-design.md
Follow-up TODOs: None
-->

# PD-ECR AI MVP Constitution

## Core Principles

### I. MVP Scope Discipline
V1 MUST implement only the minimum closed loop needed to validate historical
similar-case retrieval, AI-assisted draft generation, modular display, and basic
export. V1 MUST NOT implement a complete approval workflow, complex permissions,
Outlook notifications, or automatic SuperOPL synchronization. Any feature plan
that adds these excluded capabilities MUST move them to a post-V1 backlog unless
the constitution is amended first.

Rationale: The project exists to prove the smallest usable PD-ECR AI workflow,
not to replace the formal production process in its first release.

### II. Source-Grounded AI Output
Every AI-generated statement that appears as PD-ECR draft content MUST retain a
source case or source file reference. The system MUST NOT present unsupported
conclusions as factual output. If retrieval returns insufficient evidence, the
draft MUST clearly mark the affected content as requiring human input instead of
inventing a conclusion.

Rationale: PD-ECR content is engineering change material, so traceability is a
non-negotiable condition for review, trust, and later validation.

### III. Unified Historical Metadata
All historical cases used for retrieval, comparison, display, or generation MUST
use a shared metadata shape containing at least: case_id, DC No, MCR No,
change_type (变更类型), product_no (产品号), part_no (零件号),
customer_project (客户项目), and source_file. Ingestion, indexing, API responses,
and frontend display MUST preserve these fields when the source data provides
them. Missing fields MUST be represented explicitly rather than silently dropped.

Rationale: Consistent metadata is the link between retrieved evidence, generated
drafts, and the user's ability to inspect the historical basis.

### IV. Modular PD-ECR Result Contract
New PD-ECR results MUST be displayed as named modules: Basic Info, Change
Description, Reason for Change, Impact Analysis, Implementation Plan, and
Approval / Sign-off. APIs and frontend state MAY include additional internal
fields, but the user-facing result MUST expose these six modules or clearly show
which modules still need user-provided content.

Rationale: Modular output makes the MVP demonstrable, reviewable, and easier to
compare with existing PD-ECR documents.

### V. Minimal Change in Existing Structure
Backend and frontend implementation MUST use the existing FastAPI, React,
TanStack Router, TanStack Query, Tailwind, and local project structure wherever
practical. Large refactors, new architectural layers, or replacement frameworks
MUST be justified in the implementation plan with a simpler alternative that was
considered and rejected.

Rationale: V1 needs fast validation against the current codebase and available
PD-ECR RAG routes, not broad platform redesign.

### VI. Demo-Ready, Non-Production V1
V1 MUST be suitable for demonstration, trial use, and validation of workflow
value. V1 MUST NOT be represented as a formal production system or the official
system of record. User-facing copy, documentation, and export behavior MUST keep
the draft status clear where generated or incomplete content is shown.

Rationale: This keeps expectations aligned while still allowing practical
feedback from real users and historical case data.

## V1 Product Boundaries

The V1 product boundary is the PD-ECR AI-assisted MVP loop:

- Retrieve similar historical PD-ECR cases or files from the available knowledge
  base.
- Generate a draft using only available user input and retrieved evidence.
- Preserve source case or source file references through generation and display.
- Present the draft in the six required PD-ECR modules.
- Provide a basic export or export-ready representation suitable for demo review.

The following capabilities are out of scope for V1 unless this constitution is
amended: formal approval routing, role-based permission complexity, Outlook
notification flows, automatic SuperOPL synchronization, and claims of production
readiness.

## Development Workflow and Quality Gates

Every feature specification and implementation plan MUST include a Constitution
Check covering MVP scope, source grounding, metadata preservation, modular output,
minimal structural change, and non-production V1 positioning.

Feature requirements MUST identify:

- Which historical metadata fields are read, written, displayed, or exported.
- How each AI-generated module retains source case or source file references.
- Which of the six PD-ECR modules are affected.
- Which requested items are explicitly deferred as post-V1 scope.

Implementation tasks MUST preserve existing backend and frontend boundaries unless
the plan records a justified exception. Verification MUST include at least one
demonstrable path through search, draft generation, module display, and source
traceability. When automated tests are not added, the plan MUST record the manual
validation path used for the MVP demo.

## Governance

This constitution supersedes conflicting project practices for PD-ECR AI MVP
work. Amendments require an explicit change to this file, a version bump, and a
Sync Impact Report that lists affected templates and runtime guidance.

Versioning follows semantic versioning:

- MAJOR: Removes or redefines a core principle, or changes V1 scope in a way that
  invalidates existing plans.
- MINOR: Adds a principle or materially expands required governance, scope, or
  quality gates.
- PATCH: Clarifies wording, fixes errors, or updates references without changing
  obligations.

Compliance review is required during `/speckit-specify`, `/speckit-plan`, and
`/speckit-tasks`. Any violation MUST be documented in the plan's Complexity
Tracking section with the reason, the rejected simpler alternative, and the
expected impact on the MVP demo.

**Version**: 1.0.0 | **Ratified**: 2026-06-16 | **Last Amended**: 2026-06-16
