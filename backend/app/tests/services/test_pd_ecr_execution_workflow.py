import uuid

import pytest
from fastapi import HTTPException
from sqlmodel import SQLModel, Session, create_engine, select

from app.models import (
    PdEcrCase,
    PdEcrCaseCreate,
    PdEcrDepartmentVisibility,
    PdEcrExecutionTask,
    User,
)
from app.services.pd_ecr_case_service import create_case
from app.services.pd_ecr_workflow import (
    assign_execution_tasks,
    complete_execution_task,
    confirm_execution_assignment,
    publish_case_to_departments,
)


@pytest.fixture()
def session():
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)
    with Session(engine) as db:
        yield db


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
    assert [item["department"] for item in state["department_visibility"]] == [
        "design",
        "quality",
    ]


def test_assign_confirm_complete_then_starts_leader_review(session):
    creator = make_user(session, "creator2@example.com")
    employee = make_user(
        session,
        "quality.owner@example.com",
        role="department_member",
        department="quality",
    )
    leader = make_user(
        session,
        "quality.leader@example.com",
        role="department_leader",
        department="quality",
    )
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


def test_execution_task_cannot_be_completed_before_assignment_confirmation(session):
    creator = make_user(session, "creator3@example.com")
    employee = make_user(
        session,
        "quality.owner3@example.com",
        role="department_member",
        department="quality",
    )
    case = create_case(
        session=session,
        case_in=PdEcrCaseCreate(case_no="PDECR-EXEC-004", title="Guard execution"),
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

    with pytest.raises(HTTPException) as exc:
        complete_execution_task(
            session=session,
            task_id=task_id,
            execution_result="completed",
            execution_note="Skipped confirmation.",
            evidence_note=None,
            current_user=employee,
        )

    assert exc.value.status_code == 422
    assert "must be in_progress" in exc.value.detail


def test_in_progress_execution_task_cannot_be_reassigned_to_pending(session):
    creator = make_user(session, "creator4@example.com")
    employee = make_user(
        session,
        "quality.owner4@example.com",
        role="department_member",
        department="quality",
    )
    replacement = make_user(
        session,
        "quality.replacement@example.com",
        role="department_member",
        department="quality",
    )
    case = create_case(
        session=session,
        case_in=PdEcrCaseCreate(case_no="PDECR-EXEC-005", title="Guard reassignment"),
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
    confirm_execution_assignment(
        session=session,
        task_id=task_id,
        current_user=employee,
    )

    with pytest.raises(HTTPException) as exc:
        assign_execution_tasks(
            session=session,
            case=case,
            assignments=[
                {
                    "checklist_row_id": "ai-import-28",
                    "department": "quality",
                    "description": "Update testing program on testing equipment",
                    "assignee_id": str(replacement.id),
                    "assignee_email": replacement.email,
                    "assignee_name": replacement.full_name,
                }
            ],
            current_user=creator,
        )

    assert exc.value.status_code == 422
    assert "cannot be reassigned" in exc.value.detail
