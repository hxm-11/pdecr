# PD-ECR Lightweight RAG Schedule Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Support lightweight RAG generation from change source/reason/description and deterministic signature date suggestions from target close date.

**Architecture:** Add one focused backend schedule helper, relax the existing request schema to accept lightweight inputs, extend retrieval scoring to include change source, and update the existing React workflow in place. Keep V1 draft generation source-grounded and mark missing formal data for human review.

**Tech Stack:** Python 3.10+/Pydantic v2/FastAPI backend; React 19/TypeScript/Playwright frontend.

## Global Constraints

- Keep existing PD-ECR API routes and frontend pages stable.
- Do not add approval workflow, Outlook automation, SuperOPL sync, or audit logging.
- Use source references for generated modules when historical evidence is used.
- Use deterministic business-day schedule rules for V1.

---

### Task 1: Backend Lightweight Request And Schedule Rules

**Files:**
- Modify: `backend/app/services/pd_ecr_schema.py`
- Modify: `backend/app/services/pd_ecr_retrieval.py`
- Create: `backend/app/services/pd_ecr_schedule.py`
- Test: `backend/app/tests/services/test_pd_ecr_schema.py`
- Test: `backend/app/tests/services/test_pd_ecr_schedule.py`

**Interfaces:**
- Produces: `compute_signature_schedule(target_close_date: str) -> SignatureSchedule`
- Produces: `NewPdEcrRequest.change_source` and `NewPdEcrRequest.target_close_date`

- [ ] Write failing schema and schedule tests.
- [ ] Run the tests and confirm lightweight input fails today.
- [ ] Add schedule helper and relax schema defaults.
- [ ] Extend retrieval keyword scoring to include `change_source`.
- [ ] Run backend service tests.

### Task 2: Frontend Required Fields And Schedule Preview

**Files:**
- Modify: `frontend/src/components/PdEcr/PdEcrCreationWorkflow.tsx`
- Test: `frontend/tests/pd-ecr.spec.ts`

**Interfaces:**
- Consumes backend-compatible fields `change_source`, `change_reason`,
  `change_description`, and `target_close_date`.
- Produces visible labels `First signature target` and `Second signature target`.

- [ ] Write failing Playwright assertions for schedule preview.
- [ ] Reduce required fields in the workflow to source, reason, description.
- [ ] Include `change_source` and `target_close_date` in submitted input.
- [ ] Render first/second signature dates when target close date is valid.
- [ ] Run frontend build and Playwright PD-ECR tests.
