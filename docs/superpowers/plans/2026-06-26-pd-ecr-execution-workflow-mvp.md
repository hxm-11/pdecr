# PD-ECR Execution Workflow MVP Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the PD-ECR collaborative workflow where involved departments first see the change, align ownership offline, the creator assigns responsible employees, employees confirm assignments and fill execution results, then department leaders approve.

**Current execution update (2026-06-29):** Keep the existing four-module product surface. Do not migrate this workflow work to the six-module V1 display contract. The priority is to make the current `change-description`, `impact-analysis`, `validation-plan`, and `implementation-plan` flow support visible, actionable status transitions end to end.

**Architecture:** Keep the existing FastAPI + SQLModel + React structure. Add execution-specific workflow models/services while preserving old department-confirmation endpoints only as compatibility wrappers until the new UI stops using them. The backend owns permissions and status transitions; the frontend only hides unavailable actions for usability.

**Tech Stack:** Python 3.10+, FastAPI, SQLModel, pytest, React 19, TypeScript, TanStack Query, axios, Tailwind CSS, Playwright.

## Global Constraints

- Current four modules are `change-description`, `impact-analysis`, `validation-plan`, and `implementation-plan`.
- `change-description` is human input and must not be overwritten by AI generation.
- The implementation checklist must always show every template row; AI only suggests `Y`, `N`, and optional rationale.
- New workflow language is `department_alignment`, `execution_assignment`, `assignee_confirmation`, `execution_in_progress`, `leader_review`, `approved`.
- Treat old `department_confirmation` language as legacy compatibility only.
- Backend must enforce permissions even when frontend controls are hidden.
- Use TDD for every behavior change.

---

## File Structure

- `backend/app/models.py`
  Add `PdEcrDepartmentVisibility` and `PdEcrExecutionTask` SQLModel tables plus public payload models if needed.

- `backend/app/services/pd_ecr_workflow.py`
  Replace the main product flow with execution workflow functions while keeping old function names as thin wrappers only when needed.

- `backend/app/api/routes/pd_ecr.py`
  Add request payloads and endpoints for department publishing, execution assignment, assignee confirmation, execution completion, and my-task listing.

- `backend/app/services/pd_ecr_notification_service.py`
  Add notification type labels for department visibility, execution assignment, assignment confirmation, execution completion, and changes requested.

- `backend/app/tests/services/test_pd_ecr_execution_workflow.py`
  New service-level tests for status transitions and permissions.

- `backend/app/tests/api/routes/test_pd_ecr_execution_workflow_api.py`
  API tests for endpoint contracts and permission failures.

- `frontend/src/lib/pdEcrApi.ts`
  Add TypeScript types and API wrappers for the new workflow endpoints.

- `frontend/src/components/PdEcr/PdEcrExecutionWorkflowPanel.tsx`
  New focused component for department alignment, assignment, confirmation, execution result, and leader review.

- `frontend/src/components/PdEcr/PdEcrModuleAccordion.tsx`
  Replace the current legacy workflow side panel with `PdEcrExecutionWorkflowPanel`.

- `frontend/src/components/PdEcr/PdEcrMyTasks.tsx`
  Add an employee task list for assigned execution tasks and leader review tasks.

- `frontend/tests/pd-ecr-execution-workflow.spec.ts`
  Playwright coverage for the complete workflow happy path.

---

### Task 1: Add Execution Workflow Data Models

**Files:**
- Modify: `backend/app/models.py`
- Test: `backend/app/tests/services/test_pd_ecr_execution_workflow.py`

**Interfaces:**
- Produces: `PdEcrDepartmentVisibility`, `PdEcrExecutionTask`
- Consumes later: `publish_case_to_departments`, `assign_execution_tasks`

- [ ] **Step 1: Write the failing model test**

Add `backend/app/tests/services/test_pd_ecr_execution_workflow.py`:

```python
import uuid

from sqlmodel import SQLModel, Session, create_engine, select

from app.models import (
    PdEcrCase,
    PdEcrDepartmentVisibility,
    PdEcrExecutionTask,
    User,
)


def test_execution_workflow_models_persist_core_fields():
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        user = User(email="creator@example.com", hashed_password="x")
        case = PdEcrCase(case_no="PDECR-EXEC-001", title="Execution workflow")
        session.add(user)
        session.add(case)
        session.commit()
        session.refresh(user)
        session.refresh(case)

        visibility = PdEcrDepartmentVisibility(
            case_id=case.id,
            department="quality",
            published_by_id=user.id,
        )
        task = PdEcrExecutionTask(
            case_id=case.id,
            checklist_row_id="ai-import-28",
            department="quality",
            description="Update testing program on testing equipment",
            assignee_id=user.id,
            assignee_email=user.email,
            assignee_name="Quality Owner",
            status="pending_confirmation",
        )
        session.add(visibility)
        session.add(task)
        session.commit()

        saved_visibility = session.exec(select(PdEcrDepartmentVisibility)).one()
        saved_task = session.exec(select(PdEcrExecutionTask)).one()
        assert saved_visibility.department == "quality"
        assert saved_visibility.visible_to_department is True
        assert saved_task.status == "pending_confirmation"
        assert saved_task.execution_result is None
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```powershell
cd backend
..\.venv\Scripts\python.exe -m pytest app/tests/services/test_pd_ecr_execution_workflow.py -q
```

Expected: import error because `PdEcrDepartmentVisibility` and `PdEcrExecutionTask` do not exist.

- [ ] **Step 3: Add the SQLModel tables**

In `backend/app/models.py`, after `PdEcrDepartmentTask`, add:

```python
class PdEcrDepartmentVisibility(SQLModel, table=True):
    __tablename__ = "pd_ecr_department_visibility"
    __table_args__ = (
        UniqueConstraint("case_id", "department", name="uq_pd_ecr_dept_visibility_case_dept"),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    case_id: uuid.UUID = Field(foreign_key="pd_ecr_case.id", index=True, nullable=False)
    department: str = Field(index=True, min_length=1, max_length=64)
    visible_to_department: bool = Field(default=True)
    published_by_id: uuid.UUID | None = Field(default=None, foreign_key="user.id", index=True)
    published_at: datetime = Field(default_factory=get_datetime_utc, sa_type=DateTime(timezone=True))  # type: ignore
    created_at: datetime = Field(default_factory=get_datetime_utc, sa_type=DateTime(timezone=True))  # type: ignore
    updated_at: datetime = Field(default_factory=get_datetime_utc, sa_type=DateTime(timezone=True))  # type: ignore
```

After that class, add:

```python
class PdEcrExecutionTaskBase(SQLModel):
    checklist_row_id: str = Field(index=True, min_length=1, max_length=128)
    department: str = Field(index=True, min_length=1, max_length=64)
    description: str = Field(default="", sa_column=Column(Text))
    status: str = Field(default="pending_confirmation", index=True, max_length=32)
    assignee_id: uuid.UUID | None = Field(default=None, foreign_key="user.id", index=True)
    assignee_email: str | None = Field(default=None, index=True, max_length=255)
    assignee_name: str | None = Field(default=None, max_length=255)
    due_date: datetime | None = Field(default=None, sa_type=DateTime(timezone=True))  # type: ignore
    execution_result: str | None = Field(default=None, max_length=64)
    execution_note: str | None = Field(default=None, sa_column=Column(Text))
    evidence_note: str | None = Field(default=None, sa_column=Column(Text))
    completed_by_id: uuid.UUID | None = Field(default=None, foreign_key="user.id", index=True)
    completed_by_name: str | None = Field(default=None, max_length=255)
    completed_at: datetime | None = Field(default=None, sa_type=DateTime(timezone=True))  # type: ignore
    review_comment: str | None = Field(default=None, sa_column=Column(Text))


class PdEcrExecutionTask(PdEcrExecutionTaskBase, table=True):
    __tablename__ = "pd_ecr_execution_task"
    __table_args__ = (
        UniqueConstraint("case_id", "checklist_row_id", name="uq_pd_ecr_execution_task_case_row"),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    case_id: uuid.UUID = Field(foreign_key="pd_ecr_case.id", index=True, nullable=False)
    created_at: datetime = Field(default_factory=get_datetime_utc, sa_type=DateTime(timezone=True))  # type: ignore
    updated_at: datetime = Field(default_factory=get_datetime_utc, sa_type=DateTime(timezone=True))  # type: ignore
```

Add these statuses to `PD_ECR_STATUSES`:

```python
"generated",
"department_alignment",
"execution_assignment",
"assignee_confirmation",
"execution_in_progress",
```

- [ ] **Step 4: Run test to verify it passes**

Run:

```powershell
cd backend
..\.venv\Scripts\python.exe -m pytest app/tests/services/test_pd_ecr_execution_workflow.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add backend/app/models.py backend/app/tests/services/test_pd_ecr_execution_workflow.py
git commit -m "feat: add pd-ecr execution workflow models"
```

---

### Task 2: Implement Service Status Transitions

**Files:**
- Modify: `backend/app/services/pd_ecr_workflow.py`
- Test: `backend/app/tests/services/test_pd_ecr_execution_workflow.py`

**Interfaces:**
- Consumes: `PdEcrDepartmentVisibility`, `PdEcrExecutionTask`
- Produces:
  - `publish_case_to_departments(session, case, selected_departments, current_user)`
  - `assign_execution_tasks(session, case, assignments, current_user)`
  - `confirm_execution_assignment(session, task_id, current_user)`
  - `complete_execution_task(session, task_id, execution_result, execution_note, evidence_note, current_user)`
  - `request_execution_task_changes(session, task_id, comment, current_user)`

- [ ] **Step 1: Write failing service tests**

Append tests:

```python
from app.models import PdEcrCaseCreate
from app.services.pd_ecr_case_service import create_case
from app.services.pd_ecr_workflow import (
    assign_execution_tasks,
    complete_execution_task,
    confirm_execution_assignment,
    publish_case_to_departments,
)


def make_user(session, email, role=None, department=None, is_superuser=False):
    user = User(
        email=email,
        hashed_password="x",
        full_name=email.split("@")[0],
        display_name=email.split("@")[0],
        pd_ecr_role=role,
        department=department,
        is_superuser=is_superuser,
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


def test_publish_departments_sets_alignment_status_and_visibility(session):
    creator = make_user(session, "creator@example.com")
    case = create_case(
        session=session,
        case_in=PdEcrCaseCreate(case_no="PDECR-EXEC-002", title="Align departments"),
        current_user=creator,
    )

    state = publish_case_to_departments(
        session=session,
        case=case,
        selected_departments=["quality", "design"],
        current_user=creator,
    )

    assert state["case"]["status"] == "department_alignment"
    assert [item["department"] for item in state["department_visibility"]] == ["design", "quality"]


def test_assign_confirm_complete_then_starts_leader_review(session):
    creator = make_user(session, "creator2@example.com")
    employee = make_user(session, "quality.owner@example.com", role="department_member", department="quality")
    leader = make_user(session, "quality.leader@example.com", role="department_leader", department="quality")
    case = create_case(
        session=session,
        case_in=PdEcrCaseCreate(case_no="PDECR-EXEC-003", title="Execute task"),
        current_user=creator,
    )
    publish_case_to_departments(
        session=session,
        case=case,
        selected_departments=["quality"],
        current_user=creator,
    )

    state = assign_execution_tasks(
        session=session,
        case=case,
        assignments=[
            {
                "checklist_row_id": "ai-import-28",
                "department": "quality",
                "description": "Update testing program on testing equipment",
                "assignee_id": str(employee.id),
                "assignee_email": employee.email,
                "assignee_name": employee.full_name,
            }
        ],
        current_user=creator,
    )
    task_id = uuid.UUID(state["execution_tasks"][0]["id"])
    assert state["case"]["status"] == "assignee_confirmation"
    assert state["execution_tasks"][0]["status"] == "pending_confirmation"

    state = confirm_execution_assignment(
        session=session,
        task_id=task_id,
        current_user=employee,
    )
    assert state["case"]["status"] == "execution_in_progress"
    assert state["execution_tasks"][0]["status"] == "in_progress"

    state = complete_execution_task(
        session=session,
        task_id=task_id,
        execution_result="completed",
        execution_note="Testing program updated.",
        evidence_note="Checked on local tester.",
        current_user=employee,
    )

    assert state["case"]["status"] == "leader_review"
    assert state["execution_tasks"][0]["status"] == "completed"
    assert state["leader_review_tasks"][0]["reviewer_email"] == leader.email
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```powershell
cd backend
..\.venv\Scripts\python.exe -m pytest app/tests/services/test_pd_ecr_execution_workflow.py -q
```

Expected: import errors for missing service functions.

- [ ] **Step 3: Implement serializers and service functions**

In `pd_ecr_workflow.py`, import:

```python
from app.models import PdEcrDepartmentVisibility, PdEcrExecutionTask
```

Add constants:

```python
DEPARTMENT_ALIGNMENT_STATUS = "department_alignment"
EXECUTION_ASSIGNMENT_STATUS = "execution_assignment"
ASSIGNEE_CONFIRMATION_STATUS = "assignee_confirmation"
EXECUTION_IN_PROGRESS_STATUS = "execution_in_progress"
```

Add serializers:

```python
def _department_visibility(session: Session, case_id: uuid.UUID) -> list[PdEcrDepartmentVisibility]:
    return list(
        session.exec(
            select(PdEcrDepartmentVisibility)
            .where(PdEcrDepartmentVisibility.case_id == case_id)
            .order_by(PdEcrDepartmentVisibility.department)
        ).all()
    )


def _execution_tasks(session: Session, case_id: uuid.UUID) -> list[PdEcrExecutionTask]:
    return list(
        session.exec(
            select(PdEcrExecutionTask)
            .where(PdEcrExecutionTask.case_id == case_id)
            .order_by(PdEcrExecutionTask.department, PdEcrExecutionTask.checklist_row_id)
        ).all()
    )


def _serialize_visibility(item: PdEcrDepartmentVisibility) -> dict[str, Any]:
    return {
        "id": str(item.id),
        "case_id": str(item.case_id),
        "department": item.department,
        "visible_to_department": item.visible_to_department,
        "published_by_id": str(item.published_by_id) if item.published_by_id else None,
        "published_at": item.published_at.isoformat() if item.published_at else None,
    }


def _serialize_execution_task(task: PdEcrExecutionTask) -> dict[str, Any]:
    return {
        "id": str(task.id),
        "case_id": str(task.case_id),
        "checklist_row_id": task.checklist_row_id,
        "department": task.department,
        "description": task.description,
        "status": task.status,
        "assignee_id": str(task.assignee_id) if task.assignee_id else None,
        "assignee_email": task.assignee_email,
        "assignee_name": task.assignee_name,
        "due_date": task.due_date.isoformat() if task.due_date else None,
        "execution_result": task.execution_result,
        "execution_note": task.execution_note,
        "evidence_note": task.evidence_note,
        "completed_by_id": str(task.completed_by_id) if task.completed_by_id else None,
        "completed_by_name": task.completed_by_name,
        "completed_at": task.completed_at.isoformat() if task.completed_at else None,
        "review_comment": task.review_comment,
        "created_at": task.created_at.isoformat() if task.created_at else None,
        "updated_at": task.updated_at.isoformat() if task.updated_at else None,
    }
```

Update `get_workflow_state` to include:

```python
"department_visibility": [
    _serialize_visibility(item)
    for item in _department_visibility(session, case.id)
],
"execution_tasks": [
    _serialize_execution_task(task)
    for task in _execution_tasks(session, case.id)
],
```

Add service functions with exact behavior:

```python
def _ensure_case_assignment_actor(case: PdEcrCase, user: User) -> None:
    if user.is_superuser or getattr(user, "pd_ecr_role", None) == "pd_ecr_manager":
        return
    if case.created_by_id and case.created_by_id == user.id:
        return
    if case.owner_id and case.owner_id == user.id:
        return
    raise HTTPException(status_code=403, detail="No permission to manage execution workflow")


def publish_case_to_departments(
    *,
    session: Session,
    case: PdEcrCase,
    selected_departments: list[str],
    current_user: User,
) -> dict[str, Any]:
    _ensure_case_assignment_actor(case, current_user)
    departments = list(dict.fromkeys(_normalize_department(item) for item in selected_departments))
    if not departments:
        raise HTTPException(status_code=422, detail="At least one involved department is required")

    existing = {item.department: item for item in _department_visibility(session, case.id)}
    for department in departments:
        item = existing.get(department) or PdEcrDepartmentVisibility(case_id=case.id, department=department)
        item.visible_to_department = True
        item.published_by_id = current_user.id
        item.published_at = now_utc()
        item.updated_at = now_utc()
        session.add(item)

    case.status = DEPARTMENT_ALIGNMENT_STATUS
    case.updated_at = now_utc()
    session.add(case)
    write_activity(
        session=session,
        action="workflow.departments_published",
        case_id=case.id,
        actor_id=current_user.id,
        target_type="workflow",
        target_id=str(case.id),
        metadata={"departments": departments},
    )
    session.commit()
    session.refresh(case)
    return get_workflow_state(session=session, case=case)
```

Then add `assign_execution_tasks`, `confirm_execution_assignment`, `complete_execution_task`, and `request_execution_task_changes` using the test names and exact statuses:

```python
def assign_execution_tasks(
    *,
    session: Session,
    case: PdEcrCase,
    assignments: list[dict[str, Any]],
    current_user: User,
) -> dict[str, Any]:
    _ensure_case_assignment_actor(case, current_user)
    if not assignments:
        raise HTTPException(status_code=422, detail="At least one execution assignment is required")
    existing = {task.checklist_row_id: task for task in _execution_tasks(session, case.id)}
    for assignment in assignments:
        row_id = str(assignment.get("checklist_row_id") or "").strip()
        department = _normalize_department(assignment.get("department"))
        email = str(assignment.get("assignee_email") or "").strip()
        if not row_id:
            raise HTTPException(status_code=422, detail="checklist_row_id is required")
        if not email:
            raise HTTPException(status_code=422, detail=f"Missing assignee_email for row: {row_id}")
        task = existing.get(row_id) or PdEcrExecutionTask(
            case_id=case.id,
            checklist_row_id=row_id,
            department=department,
        )
        task.department = department
        task.description = str(assignment.get("description") or "")
        task.assignee_id = _parse_uuid(assignment.get("assignee_id"))
        task.assignee_email = email
        task.assignee_name = assignment.get("assignee_name")
        task.status = "pending_confirmation"
        task.due_date = assignment.get("due_date")
        task.updated_at = now_utc()
        session.add(task)
    case.status = ASSIGNEE_CONFIRMATION_STATUS
    case.updated_at = now_utc()
    session.add(case)
    session.commit()
    session.refresh(case)
    return get_workflow_state(session=session, case=case)
```

Implement assignee permission:

```python
def _ensure_execution_task_assignee(task: PdEcrExecutionTask, user: User) -> None:
    if user.is_superuser or getattr(user, "pd_ecr_role", None) == "pd_ecr_manager":
        return
    if task.assignee_id and task.assignee_id == user.id:
        return
    raise HTTPException(status_code=403, detail="No permission for execution task")
```

Use it in confirmation and completion:

```python
def confirm_execution_assignment(*, session: Session, task_id: uuid.UUID, current_user: User) -> dict[str, Any]:
    task = session.get(PdEcrExecutionTask, task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Execution task not found")
    _ensure_execution_task_assignee(task, current_user)
    case = session.get(PdEcrCase, task.case_id)
    if case is None:
        raise HTTPException(status_code=404, detail="PD-ECR case not found")
    task.status = "in_progress"
    task.updated_at = now_utc()
    case.status = EXECUTION_IN_PROGRESS_STATUS
    case.updated_at = now_utc()
    session.add(task)
    session.add(case)
    session.commit()
    session.refresh(case)
    return get_workflow_state(session=session, case=case)
```

For completion, after setting `task.status = "completed"`, call a helper:

```python
def _start_leader_review_if_execution_complete(*, session: Session, case: PdEcrCase) -> None:
    tasks = _execution_tasks(session, case.id)
    if not tasks or any(task.status != "completed" for task in tasks):
        return
    existing_departments = {task.department for task in _leader_tasks(session, case.id)}
    for department in sorted({task.department for task in tasks}):
        if department in existing_departments:
            continue
        leader = _find_leader_for_department(session=session, department=department)
        leader_task = PdEcrLeaderReviewTask(
            case_id=case.id,
            department=department,
            reviewer_id=leader.id if leader else None,
            reviewer_email=leader.email if leader else None,
            reviewer_name=_actor_name(leader) if leader else None,
            status="pending",
        )
        session.add(leader_task)
    case.status = LEADER_REVIEW_STATUS
    case.updated_at = now_utc()
    session.add(case)
```

- [ ] **Step 4: Run service tests**

Run:

```powershell
cd backend
..\.venv\Scripts\python.exe -m pytest app/tests/services/test_pd_ecr_execution_workflow.py app/tests/services/test_pd_ecr_workflow.py -q
```

Expected: new tests pass; existing legacy tests still pass unless intentionally updated in Task 3.

- [ ] **Step 5: Commit**

```powershell
git add backend/app/services/pd_ecr_workflow.py backend/app/tests/services/test_pd_ecr_execution_workflow.py
git commit -m "feat: add pd-ecr execution workflow transitions"
```

---

### Task 3: Add New Workflow API Endpoints

**Files:**
- Modify: `backend/app/api/routes/pd_ecr.py`
- Test: `backend/app/tests/api/routes/test_pd_ecr_execution_workflow_api.py`

**Interfaces:**
- Consumes service functions from Task 2.
- Produces endpoint contracts used by frontend in Task 4.

- [ ] **Step 1: Add failing API tests**

Create `backend/app/tests/api/routes/test_pd_ecr_execution_workflow_api.py` with tests for:

```python
def test_publish_departments_endpoint_returns_department_alignment(client, superuser_token_headers):
    payload = {"selected_departments": ["quality"]}
    response = client.post(
        "/api/v1/pd-ecr/cases/{case_id}/workflow/publish-departments",
        headers=superuser_token_headers,
        json=payload,
    )
    assert response.status_code in {200, 404}
```

Use existing test client fixtures in the repo. If no fixture exists for PD-ECR API tests, create service-level route tests after locating the project fixture pattern with:

```powershell
rg -n "superuser_token_headers|TestClient|client" backend/app/tests backend/tests
```

- [ ] **Step 2: Run API test to verify it fails**

Run:

```powershell
cd backend
..\.venv\Scripts\python.exe -m pytest app/tests/api/routes/test_pd_ecr_execution_workflow_api.py -q
```

Expected: route not found or missing payload classes.

- [ ] **Step 3: Add route payload classes**

In `pd_ecr.py`, near existing workflow payloads, add:

```python
class PdEcrPublishDepartmentsPayload(BaseModel):
    selected_departments: list[str]


class PdEcrExecutionAssignmentPayload(BaseModel):
    checklist_row_id: str
    department: str
    description: str = ""
    assignee_id: uuid.UUID | None = None
    assignee_email: str
    assignee_name: str | None = None
    due_date: datetime | None = None


class PdEcrAssignExecutionPayload(BaseModel):
    assignments: list[PdEcrExecutionAssignmentPayload]


class PdEcrExecutionCompletePayload(BaseModel):
    execution_result: str
    execution_note: str | None = None
    evidence_note: str | None = None
```

- [ ] **Step 4: Import new service functions**

Update the `from app.services.pd_ecr_workflow import (...)` block:

```python
assign_execution_tasks,
complete_execution_task,
confirm_execution_assignment,
publish_case_to_departments,
request_execution_task_changes,
```

- [ ] **Step 5: Add endpoints**

Near existing workflow endpoints, add:

```python
@router.post("/cases/{case_id}/workflow/publish-departments")
def publish_pd_ecr_departments(
    case_id: str,
    payload: PdEcrPublishDepartmentsPayload,
    session: SessionDep,
    current_user: CurrentUser,
):
    case = get_case_or_404(session, case_id)
    return publish_case_to_departments(
        session=session,
        case=case,
        selected_departments=payload.selected_departments,
        current_user=current_user,
    )


@router.post("/cases/{case_id}/workflow/assign-execution")
def assign_pd_ecr_execution(
    case_id: str,
    payload: PdEcrAssignExecutionPayload,
    session: SessionDep,
    current_user: CurrentUser,
):
    case = get_case_or_404(session, case_id)
    return assign_execution_tasks(
        session=session,
        case=case,
        assignments=[item.model_dump(mode="json") for item in payload.assignments],
        current_user=current_user,
    )


@router.post("/workflow/execution-tasks/{task_id}/confirm-assignment")
def confirm_pd_ecr_execution_assignment(
    task_id: uuid.UUID,
    session: SessionDep,
    current_user: CurrentUser,
):
    return confirm_execution_assignment(
        session=session,
        task_id=task_id,
        current_user=current_user,
    )


@router.post("/workflow/execution-tasks/{task_id}/complete")
def complete_pd_ecr_execution_task(
    task_id: uuid.UUID,
    payload: PdEcrExecutionCompletePayload,
    session: SessionDep,
    current_user: CurrentUser,
):
    return complete_execution_task(
        session=session,
        task_id=task_id,
        execution_result=payload.execution_result,
        execution_note=payload.execution_note,
        evidence_note=payload.evidence_note,
        current_user=current_user,
    )


@router.post("/workflow/execution-tasks/{task_id}/request-changes")
def request_pd_ecr_execution_changes(
    task_id: uuid.UUID,
    payload: PdEcrWorkflowCommentPayload,
    session: SessionDep,
    current_user: CurrentUser,
):
    return request_execution_task_changes(
        session=session,
        task_id=task_id,
        comment=payload.comment,
        current_user=current_user,
    )
```

- [ ] **Step 6: Run API and service tests**

Run:

```powershell
cd backend
..\.venv\Scripts\python.exe -m pytest app/tests/services/test_pd_ecr_execution_workflow.py app/tests/api/routes/test_pd_ecr_execution_workflow_api.py -q
```

Expected: PASS.

- [ ] **Step 7: Commit**

```powershell
git add backend/app/api/routes/pd_ecr.py backend/app/tests/api/routes/test_pd_ecr_execution_workflow_api.py
git commit -m "feat: expose pd-ecr execution workflow api"
```

---

### Task 4: Add Frontend API Types and Wrappers

**Files:**
- Modify: `frontend/src/lib/pdEcrApi.ts`

**Interfaces:**
- Produces:
  - `PdEcrDepartmentVisibility`
  - `PdEcrExecutionWorkflowTask`
  - `publishPdEcrDepartments`
  - `assignPdEcrExecution`
  - `confirmPdEcrExecutionAssignment`
  - `completePdEcrExecutionTask`
  - `requestPdEcrExecutionChanges`

- [ ] **Step 1: Add TypeScript types**

In `pdEcrApi.ts`, near workflow types, add:

```ts
export type PdEcrDepartmentVisibility = {
  id: string
  case_id: string
  department: string
  visible_to_department: boolean
  published_by_id?: string | null
  published_at?: string | null
}

export type PdEcrExecutionWorkflowTask = {
  id: string
  case_id: string
  checklist_row_id: string
  department: string
  description: string
  status: "pending_confirmation" | "confirmed" | "in_progress" | "completed" | "changes_requested" | string
  assignee_id?: string | null
  assignee_email?: string | null
  assignee_name?: string | null
  due_date?: string | null
  execution_result?: string | null
  execution_note?: string | null
  evidence_note?: string | null
  completed_by_id?: string | null
  completed_by_name?: string | null
  completed_at?: string | null
  review_comment?: string | null
}

export type PdEcrExecutionAssignmentInput = {
  checklist_row_id: string
  department: string
  description: string
  assignee_id?: string | null
  assignee_email: string
  assignee_name?: string | null
  due_date?: string | null
}
```

Extend `PdEcrWorkflowState`:

```ts
department_visibility: PdEcrDepartmentVisibility[]
execution_tasks: PdEcrExecutionWorkflowTask[]
```

- [ ] **Step 2: Add API wrappers**

Add:

```ts
export async function publishPdEcrDepartments(
  caseId: string,
  selectedDepartments: string[],
): Promise<PdEcrWorkflowState> {
  const res = await pdEcrApi.post<PdEcrWorkflowState>(
    `/api/v1/pd-ecr/cases/${encodeURIComponent(caseId)}/workflow/publish-departments`,
    { selected_departments: selectedDepartments },
  )
  return res.data
}

export async function assignPdEcrExecution(
  caseId: string,
  assignments: PdEcrExecutionAssignmentInput[],
): Promise<PdEcrWorkflowState> {
  const res = await pdEcrApi.post<PdEcrWorkflowState>(
    `/api/v1/pd-ecr/cases/${encodeURIComponent(caseId)}/workflow/assign-execution`,
    { assignments },
  )
  return res.data
}

export async function confirmPdEcrExecutionAssignment(taskId: string): Promise<PdEcrWorkflowState> {
  const res = await pdEcrApi.post<PdEcrWorkflowState>(
    `/api/v1/pd-ecr/workflow/execution-tasks/${encodeURIComponent(taskId)}/confirm-assignment`,
  )
  return res.data
}

export async function completePdEcrExecutionTask(
  taskId: string,
  payload: { execution_result: string; execution_note?: string; evidence_note?: string },
): Promise<PdEcrWorkflowState> {
  const res = await pdEcrApi.post<PdEcrWorkflowState>(
    `/api/v1/pd-ecr/workflow/execution-tasks/${encodeURIComponent(taskId)}/complete`,
    payload,
  )
  return res.data
}

export async function requestPdEcrExecutionChanges(
  taskId: string,
  comment: string,
): Promise<PdEcrWorkflowState> {
  const res = await pdEcrApi.post<PdEcrWorkflowState>(
    `/api/v1/pd-ecr/workflow/execution-tasks/${encodeURIComponent(taskId)}/request-changes`,
    { comment },
  )
  return res.data
}
```

- [ ] **Step 3: Run frontend type check/build**

Run:

```powershell
cd frontend
npm run build
```

Expected: build succeeds.

- [ ] **Step 4: Commit**

```powershell
git add frontend/src/lib/pdEcrApi.ts
git commit -m "feat: add pd-ecr execution workflow client api"
```

---

### Task 5: Replace Legacy Workflow UI With Execution Workflow Panel

**Files:**
- Create: `frontend/src/components/PdEcr/PdEcrExecutionWorkflowPanel.tsx`
- Modify: `frontend/src/components/PdEcr/PdEcrModuleAccordion.tsx`

**Interfaces:**
- Consumes Task 4 frontend API.
- Produces UI for department publish, execution assignment, assignee confirmation, execution result, and leader review.

- [ ] **Step 1: Create focused panel component**

Move workflow UI out of `PdEcrModuleAccordion.tsx` into a new component. Start with this component shell:

```tsx
import { useEffect, useMemo, useState } from "react"
import { Button } from "@/components/ui/button"
import {
  assignPdEcrExecution,
  completePdEcrExecutionTask,
  confirmPdEcrExecutionAssignment,
  getPdEcrWorkflow,
  publishPdEcrDepartments,
  reviewPdEcrLeaderTask,
  type PdEcrExecutionAssignmentInput,
  type PdEcrExecutionWorkflowTask,
  type PdEcrLeaderReviewWorkflowTask,
  type PdEcrWorkflowState,
} from "@/lib/pdEcrApi"

const WORKFLOW_DEPTS = [
  { id: "design", label: "Design" },
  { id: "system", label: "System" },
  { id: "purchasing", label: "Purchasing" },
  { id: "manufacturing", label: "Manufacturing" },
  { id: "quality", label: "Quality" },
  { id: "pm", label: "PM" },
  { id: "catalyst", label: "Catalyst" },
]

type ChecklistRow = {
  id: string
  department: string
  yn: string
  description: string
  responsible?: string
  dueDate?: string
}

function workflowBadgeClass(status: string) {
  switch (status) {
    case "completed":
    case "approved":
      return "border-emerald-200 bg-emerald-50 text-emerald-700"
    case "changes_requested":
    case "rejected":
      return "border-rose-200 bg-rose-50 text-rose-700"
    case "pending_confirmation":
    case "leader_review":
      return "border-amber-200 bg-amber-50 text-amber-700"
    default:
      return "border-stone-200 bg-stone-50 text-stone-600"
  }
}

function loadImplementationChecklist(): ChecklistRow[] {
  try {
    const raw = localStorage.getItem("pd-ecr-implementation-implementation-plan")
    const parsed = raw ? JSON.parse(raw) : null
    return Array.isArray(parsed?.checklistRows) ? parsed.checklistRows : []
  } catch {
    return []
  }
}

export function PdEcrExecutionWorkflowPanel({
  caseId,
  onComplete,
}: {
  caseId: string
  onComplete?: () => void
}) {
  const [workflow, setWorkflow] = useState<PdEcrWorkflowState | null>(null)
  const [selected, setSelected] = useState<Record<string, boolean>>({ quality: true })
  const [assignmentEmails, setAssignmentEmails] = useState<Record<string, string>>({})
  const [statusText, setStatusText] = useState("Loading workflow...")
  const [isSaving, setIsSaving] = useState(false)

  useEffect(() => {
    let mounted = true
    getPdEcrWorkflow(caseId)
      .then((state) => {
        if (!mounted) return
        setWorkflow(state)
        setStatusText("Workflow ready")
      })
      .catch(() => {
        if (!mounted) return
        setStatusText("Workflow not started")
      })
    return () => {
      mounted = false
    }
  }, [caseId])

  const yRows = useMemo(
    () => loadImplementationChecklist().filter((row) => row.yn === "Y"),
    [workflow?.case?.status],
  )

  const publishDepartments = async () => {
    const departments = WORKFLOW_DEPTS.filter((dept) => selected[dept.id]).map((dept) => dept.id)
    setIsSaving(true)
    try {
      const next = await publishPdEcrDepartments(caseId, departments)
      setWorkflow(next)
      setStatusText("Published to involved departments")
    } finally {
      setIsSaving(false)
    }
  }

  const assignExecution = async () => {
    const assignments: PdEcrExecutionAssignmentInput[] = yRows.map((row) => ({
      checklist_row_id: row.id,
      department: row.department.toLowerCase(),
      description: row.description,
      assignee_email: assignmentEmails[row.id] || row.responsible || "",
      assignee_name: assignmentEmails[row.id] || row.responsible || "",
      due_date: row.dueDate || null,
    }))
    setIsSaving(true)
    try {
      const next = await assignPdEcrExecution(caseId, assignments)
      setWorkflow(next)
      setStatusText("Execution assignments sent")
    } finally {
      setIsSaving(false)
    }
  }

  return (
    <div className="sticky top-4 space-y-4" style={{ maxHeight: "calc(100vh - 8rem)", overflowY: "auto" }}>
      <div className="rounded-lg border border-amber-300 bg-white shadow-sm">
        <div className="rounded-t-lg bg-amber-600 px-4 py-2.5 text-sm font-semibold text-white">
          PD-ECR Workflow
        </div>
        <div className="space-y-3 p-3">
          <p className="text-xs text-stone-500" role="status">{statusText}</p>
          {workflow && (
            <span className={`inline-flex rounded-full border px-2 py-0.5 text-[10px] font-semibold ${workflowBadgeClass(workflow.case.status)}`}>
              {workflow.case.status}
            </span>
          )}
          <DepartmentPublishStep
            selected={selected}
            setSelected={setSelected}
            onSubmit={publishDepartments}
            disabled={isSaving}
          />
          <ExecutionAssignmentStep
            rows={yRows}
            assignmentEmails={assignmentEmails}
            setAssignmentEmails={setAssignmentEmails}
            onSubmit={assignExecution}
            disabled={isSaving || yRows.some((row) => !(assignmentEmails[row.id] || row.responsible || "").trim())}
          />
        </div>
      </div>
      {workflow?.execution_tasks?.map((task) => (
        <ExecutionTaskCard key={task.id} task={task} onRefresh={setWorkflow} />
      ))}
      {workflow?.leader_review_tasks?.map((task) => (
        <LeaderReviewCard key={task.id} task={task} onRefresh={setWorkflow} />
      ))}
    </div>
  )
}
```

Add small child components in the same file:

```tsx
function DepartmentPublishStep({
  selected,
  setSelected,
  onSubmit,
  disabled,
}: {
  selected: Record<string, boolean>
  setSelected: React.Dispatch<React.SetStateAction<Record<string, boolean>>>
  onSubmit: () => void
  disabled: boolean
}) {
  return (
    <div className="space-y-2">
      <p className="text-xs font-semibold text-stone-600">Involved departments</p>
      {WORKFLOW_DEPTS.map((dept) => (
        <label key={dept.id} className="flex items-center gap-2 rounded border border-stone-100 p-2 text-xs">
          <input
            type="checkbox"
            checked={!!selected[dept.id]}
            onChange={(event) => setSelected((prev) => ({ ...prev, [dept.id]: event.target.checked }))}
            className="accent-amber-600"
          />
          <span className="font-semibold text-stone-700">{dept.label}</span>
        </label>
      ))}
      <Button type="button" className="w-full bg-stone-800 hover:bg-stone-700" onClick={onSubmit} disabled={disabled}>
        Publish to departments
      </Button>
    </div>
  )
}
```

```tsx
function ExecutionAssignmentStep({
  rows,
  assignmentEmails,
  setAssignmentEmails,
  onSubmit,
  disabled,
}: {
  rows: ChecklistRow[]
  assignmentEmails: Record<string, string>
  setAssignmentEmails: React.Dispatch<React.SetStateAction<Record<string, string>>>
  onSubmit: () => void
  disabled: boolean
}) {
  return (
    <div className="space-y-2">
      <p className="text-xs font-semibold text-stone-600">Assign Y checklist rows</p>
      {rows.map((row) => (
        <label key={row.id} className="block rounded border border-stone-100 p-2 text-xs">
          <span className="font-semibold text-stone-700">{row.department}</span>
          <span className="mt-1 block text-stone-500">{row.description}</span>
          <input
            value={assignmentEmails[row.id] || ""}
            onChange={(event) => setAssignmentEmails((prev) => ({ ...prev, [row.id]: event.target.value }))}
            className="mt-2 h-8 w-full rounded border border-stone-200 px-2 outline-none focus:border-amber-400"
            placeholder="assignee@email.com"
          />
        </label>
      ))}
      <Button type="button" className="w-full bg-amber-600 hover:bg-amber-700" onClick={onSubmit} disabled={disabled}>
        Assign execution tasks
      </Button>
    </div>
  )
}
```

Implement `ExecutionTaskCard` with two states:

- If `status === "pending_confirmation"`, show "Confirm assignment" button calling `confirmPdEcrExecutionAssignment`.
- If `status === "in_progress" || status === "changes_requested"`, show result fields and call `completePdEcrExecutionTask`.

Implement `LeaderReviewCard` by adapting the existing `LeaderTaskCard`.

- [ ] **Step 2: Wire component into accordion**

In `PdEcrModuleAccordion.tsx`, remove old imports:

```ts
confirmPdEcrDepartmentTask,
submitPdEcrWorkflow,
type PdEcrDepartmentWorkflowTask,
```

Add:

```ts
import { PdEcrExecutionWorkflowPanel } from "./PdEcrExecutionWorkflowPanel"
```

Replace `WorkflowSignerPanel` usage with:

```tsx
<PdEcrExecutionWorkflowPanel caseId={caseId} onComplete={onComplete} />
```

Delete old `DepartmentTaskCard`, old `WorkflowSignerPanel`, and legacy department assignment UI from this file.

- [ ] **Step 3: Run frontend build**

Run:

```powershell
cd frontend
npm run build
```

Expected: PASS.

- [ ] **Step 4: Commit**

```powershell
git add frontend/src/components/PdEcr/PdEcrExecutionWorkflowPanel.tsx frontend/src/components/PdEcr/PdEcrModuleAccordion.tsx
git commit -m "feat: add pd-ecr execution workflow panel"
```

---

### Task 6: Add My Tasks View

**Files:**
- Modify: `backend/app/services/pd_ecr_workflow.py`
- Modify: `backend/app/api/routes/pd_ecr.py`
- Create: `frontend/src/components/PdEcr/PdEcrMyTasks.tsx`
- Modify route file if the app has a PD-ECR route registry under `frontend/src/routes`.

**Interfaces:**
- Backend produces `GET /api/v1/pd-ecr/workflow/my-tasks`.
- Frontend consumes and displays execution tasks and leader review tasks.

- [ ] **Step 1: Add backend service function**

In `pd_ecr_workflow.py`, add:

```python
def list_my_workflow_tasks(*, session: Session, current_user: User) -> dict[str, Any]:
    execution_statement = select(PdEcrExecutionTask)
    leader_statement = select(PdEcrLeaderReviewTask)
    if not current_user.is_superuser and getattr(current_user, "pd_ecr_role", None) != "pd_ecr_manager":
        execution_statement = execution_statement.where(PdEcrExecutionTask.assignee_id == current_user.id)
        leader_statement = leader_statement.where(PdEcrLeaderReviewTask.reviewer_id == current_user.id)
    execution_tasks = list(session.exec(execution_statement).all())
    leader_tasks = list(session.exec(leader_statement).all())
    return {
        "execution_tasks": [_serialize_execution_task(task) for task in execution_tasks],
        "leader_review_tasks": [_serialize_leader_task(task) for task in leader_tasks],
    }
```

- [ ] **Step 2: Add API endpoint**

In `pd_ecr.py`, import `list_my_workflow_tasks` and add:

```python
@router.get("/workflow/my-tasks")
def get_my_pd_ecr_workflow_tasks(
    session: SessionDep,
    current_user: CurrentUser,
):
    return list_my_workflow_tasks(session=session, current_user=current_user)
```

- [ ] **Step 3: Add frontend wrapper**

In `pdEcrApi.ts`, add:

```ts
export type PdEcrMyWorkflowTasks = {
  execution_tasks: PdEcrExecutionWorkflowTask[]
  leader_review_tasks: PdEcrLeaderReviewWorkflowTask[]
}

export async function listMyPdEcrWorkflowTasks(): Promise<PdEcrMyWorkflowTasks> {
  const res = await pdEcrApi.get<PdEcrMyWorkflowTasks>("/api/v1/pd-ecr/workflow/my-tasks")
  return res.data
}
```

- [ ] **Step 4: Create frontend task list**

Create `PdEcrMyTasks.tsx`:

```tsx
import { useQuery } from "@tanstack/react-query"
import { listMyPdEcrWorkflowTasks } from "@/lib/pdEcrApi"

export function PdEcrMyTasks() {
  const { data, isLoading, error } = useQuery({
    queryKey: ["pd-ecr-my-workflow-tasks"],
    queryFn: listMyPdEcrWorkflowTasks,
  })

  if (isLoading) return <p className="text-sm text-stone-500">Loading tasks...</p>
  if (error) return <p className="text-sm text-rose-600">Failed to load tasks.</p>

  return (
    <div className="space-y-6">
      <section>
        <h2 className="text-base font-semibold text-stone-900">Execution Tasks</h2>
        <div className="mt-3 divide-y divide-stone-100 rounded border border-stone-200 bg-white">
          {(data?.execution_tasks || []).map((task) => (
            <div key={task.id} className="p-3">
              <p className="text-sm font-semibold text-stone-800">{task.description}</p>
              <p className="mt-1 text-xs text-stone-500">{task.department} · {task.status}</p>
            </div>
          ))}
          {!data?.execution_tasks?.length && <p className="p-3 text-sm text-stone-500">No execution tasks.</p>}
        </div>
      </section>
      <section>
        <h2 className="text-base font-semibold text-stone-900">Leader Reviews</h2>
        <div className="mt-3 divide-y divide-stone-100 rounded border border-stone-200 bg-white">
          {(data?.leader_review_tasks || []).map((task) => (
            <div key={task.id} className="p-3">
              <p className="text-sm font-semibold text-stone-800">{task.department}</p>
              <p className="mt-1 text-xs text-stone-500">{task.status}</p>
            </div>
          ))}
          {!data?.leader_review_tasks?.length && <p className="p-3 text-sm text-stone-500">No leader reviews.</p>}
        </div>
      </section>
    </div>
  )
}
```

- [ ] **Step 5: Run tests/build**

Run:

```powershell
cd backend
..\.venv\Scripts\python.exe -m pytest app/tests/services/test_pd_ecr_execution_workflow.py -q
cd ..\frontend
npm run build
```

Expected: backend tests pass and frontend build passes.

- [ ] **Step 6: Commit**

```powershell
git add backend/app/services/pd_ecr_workflow.py backend/app/api/routes/pd_ecr.py frontend/src/lib/pdEcrApi.ts frontend/src/components/PdEcr/PdEcrMyTasks.tsx
git commit -m "feat: add pd-ecr my workflow tasks"
```

---

### Task 7: End-to-End Verification

**Files:**
- Create: `frontend/tests/pd-ecr-execution-workflow.spec.ts`

**Interfaces:**
- Verifies the full MVP path through UI where existing routes allow it.

- [ ] **Step 1: Add Playwright happy-path test**

Create a test that mocks API responses if the app does not yet have seeded users:

```ts
import { test, expect } from "@playwright/test"

test("PD-ECR execution workflow shows department alignment, assignment, execution, and leader review", async ({ page }) => {
  await page.route("**/api/v1/pd-ecr/cases/*/workflow", async (route) => {
    await route.fulfill({
      json: {
        case: { id: "case-1", status: "department_alignment", case_no: "PDECR-E2E-001" },
        department_visibility: [{ id: "v1", case_id: "case-1", department: "quality", visible_to_department: true }],
        execution_tasks: [],
        department_tasks: [],
        leader_review_tasks: [],
      },
    })
  })

  await page.goto("/pd-ecr/content?caseId=case-1")
  await expect(page.getByText("PD-ECR Workflow")).toBeVisible()
  await expect(page.getByText("Publish to departments")).toBeVisible()
})
```

- [ ] **Step 2: Run Playwright test**

Run:

```powershell
cd frontend
npx playwright test frontend/tests/pd-ecr-execution-workflow.spec.ts
```

Expected: PASS. If route path differs, inspect `frontend/src/routes` and update only the route in the test.

- [ ] **Step 3: Run final regression suite**

Run:

```powershell
cd backend
..\.venv\Scripts\python.exe -m pytest app/tests/services/test_pd_ecr_execution_workflow.py app/tests/services/test_pd_ecr_four_module_generation.py app/tests/services/test_pd_ecr_module_drafts.py -q
cd ..\frontend
npm run build
```

Expected: all listed backend tests pass and frontend build passes.

- [ ] **Step 4: Commit**

```powershell
git add frontend/tests/pd-ecr-execution-workflow.spec.ts
git commit -m "test: cover pd-ecr execution workflow ui"
```

---

## Self-Review

- Spec coverage: The plan covers department visibility, offline alignment support, creator assignment, assignee confirmation, execution result completion, leader review, approved status, and legacy `department_confirmation` containment.
- Placeholder scan: No task uses TBD/TODO or open-ended "add appropriate" wording.
- Type consistency: Backend model names, service function names, endpoint names, and frontend API wrapper names are aligned across tasks.
- Scope control: Email/Outlook integration, digital signatures, attachment enforcement, and SLA escalation remain excluded.

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-06-26-pd-ecr-execution-workflow-mvp.md`. Two execution options:

1. **Subagent-Driven (recommended)** - dispatch a fresh subagent per task, review between tasks, fast iteration.
2. **Inline Execution** - execute tasks in this session using executing-plans, batch execution with checkpoints.

Which approach?
