# PD-ECR Workflow Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a backend-driven PD-ECR department confirmation and leader review workflow where each affected department needs one confirmation before leader sign-off starts.

**Architecture:** Add focused SQLModel workflow task tables, a `pd_ecr_workflow.py` service that owns state transitions and email triggers, thin FastAPI endpoints in the existing PD-ECR router, typed frontend API wrappers, and a workflow-aware panel in the existing PD-ECR module accordion. Keep the current PD-ECR module/content structure intact.

**Tech Stack:** Python 3.10+, FastAPI, SQLModel, pytest, TypeScript 5.9, React 19, TanStack Query, axios.

## Global Constraints

- Reuse existing FastAPI router `backend/app/api/routes/pd_ecr.py`.
- Reuse existing notification persistence through `PdEcrNotification`.
- Each affected department creates exactly one active confirmation task in MVP.
- Leader review starts only after all department confirmation tasks are `confirmed`.
- Frontend workflow state must come from backend APIs, not localStorage-only state.
- Preserve unrelated user changes in `frontend/src/components/PdEcr/PdEcrModuleAccordion.tsx`.

---

### Task 1: Backend Workflow Models and Service

**Files:**
- Modify: `backend/app/models.py`
- Create: `backend/app/services/pd_ecr_workflow.py`
- Test: `backend/app/tests/services/test_pd_ecr_workflow.py`

**Interfaces:**
- Produces: `PdEcrDepartmentTask`, `PdEcrLeaderReviewTask`
- Produces: `submit_for_department_confirmation(session, case, selected_departments, assignees, current_user) -> dict`
- Produces: `confirm_department_task(session, task_id, impact_result, impact_remark, action_required, current_user) -> dict`
- Produces: `review_leader_task(session, task_id, decision, review_comment, signature_name, current_user) -> dict`
- Produces: `get_workflow_state(session, case) -> dict`

- [ ] **Step 1: Write failing workflow service tests**

Create tests that verify department submission creates one task per department, confirmation triggers leader review after all departments confirm, and leader approval marks the case approved.

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest backend/app/tests/services/test_pd_ecr_workflow.py -q`
Expected: FAIL because workflow models/service do not exist.

- [ ] **Step 3: Implement models and service**

Add the two workflow task models and the workflow service functions. Use existing `PdEcrCase`, `User`, `PdEcrActivity`, and `PdEcrNotification` patterns.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest backend/app/tests/services/test_pd_ecr_workflow.py -q`
Expected: PASS.

### Task 2: Workflow Email Notification Types

**Files:**
- Modify: `backend/app/services/pd_ecr_notification_service.py`
- Test: `backend/app/tests/services/test_pd_ecr_workflow.py`

**Interfaces:**
- Consumes: workflow task dictionaries from Task 1.
- Produces: `record_workflow_notification(...) -> PdEcrNotification`
- Produces email subjects for `department_confirmation_request`, `leader_review_request`, and `changes_requested`.

- [ ] **Step 1: Write failing notification assertions**

Extend workflow tests to monkeypatch `send_email` and assert notifications are recorded when department tasks and leader review tasks are created.

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest backend/app/tests/services/test_pd_ecr_workflow.py -q`
Expected: FAIL because workflow notifications are not sent.

- [ ] **Step 3: Implement workflow notification helper**

Add focused helpers to the existing notification service and call them from workflow transitions.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest backend/app/tests/services/test_pd_ecr_workflow.py -q`
Expected: PASS.

### Task 3: Workflow API Endpoints

**Files:**
- Modify: `backend/app/api/routes/pd_ecr.py`
- Test: `backend/app/tests/api/routes/test_pd_ecr_workflow.py`

**Interfaces:**
- Consumes: workflow service from Task 1.
- Produces:
  - `POST /api/v1/pd-ecr/cases/{case_id}/workflow/submit`
  - `GET /api/v1/pd-ecr/cases/{case_id}/workflow`
  - `POST /api/v1/pd-ecr/workflow/department-tasks/{task_id}/confirm`
  - `POST /api/v1/pd-ecr/workflow/department-tasks/{task_id}/request-changes`
  - `POST /api/v1/pd-ecr/workflow/leader-tasks/{task_id}/review`

- [ ] **Step 1: Write failing API route tests**

Use the existing FastAPI test patterns to submit a workflow and read workflow state.

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest backend/app/tests/api/routes/test_pd_ecr_workflow.py -q`
Expected: FAIL because endpoints do not exist.

- [ ] **Step 3: Implement route payloads and handlers**

Add Pydantic payload models and route functions that delegate to workflow service.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest backend/app/tests/api/routes/test_pd_ecr_workflow.py -q`
Expected: PASS.

### Task 4: Frontend API Types and Workflow Panel

**Files:**
- Modify: `frontend/src/lib/pdEcrApi.ts`
- Modify: `frontend/src/components/PdEcr/PdEcrModuleAccordion.tsx`

**Interfaces:**
- Consumes backend workflow endpoints from Task 3.
- Produces typed functions:
  - `getPdEcrWorkflow(caseId)`
  - `submitPdEcrWorkflow(caseId, payload)`
  - `confirmPdEcrDepartmentTask(taskId, payload)`
  - `reviewPdEcrLeaderTask(taskId, payload)`

- [ ] **Step 1: Add typed API wrappers**

Add workflow types and functions to `pdEcrApi.ts`.

- [ ] **Step 2: Wire workflow state into accordion panel**

Replace localStorage-only approval progress with backend workflow progress when a database case id is available; keep local fallback for generated/offline modules.

- [ ] **Step 3: Build frontend**

Run: `cd frontend; npm run build`
Expected: PASS.

### Task 5: Verification

**Files:**
- All touched files.

- [ ] **Step 1: Run backend workflow tests**

Run: `pytest backend/app/tests/services/test_pd_ecr_workflow.py -q`
Expected: PASS.

- [ ] **Step 2: Run related backend tests**

Run: `pytest backend/app/tests/services/test_pd_ecr_permissions_notifications.py -q`
Expected: PASS.

- [ ] **Step 3: Run frontend build**

Run: `cd frontend; npm run build`
Expected: PASS.
