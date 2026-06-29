import uuid

import pytest
from fastapi import HTTPException
from sqlmodel import SQLModel, Session, create_engine, select

from app.models import (
    PdEcrCase,
    PdEcrCaseCreate,
    PdEcrDepartmentVisibility,
    PdEcrExecutionTask,
    PdEcrLeaderReviewTask,
    PdEcrModule,
    User,
)
from app.services.pd_ecr_case_service import create_case, delete_case
from app.services.pd_ecr_workflow import (
    assign_execution_tasks,
    complete_execution_task,
    confirm_execution_assignment,
    list_my_workflow_tasks,
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


def test_list_my_workflow_tasks_filters_by_assignee_and_reviewer(session):
    assignee = make_user(session, "assignee@example.com", department="quality")
    reviewer = make_user(
        session,
        "leader@example.com",
        role="department_leader",
        department="quality",
    )
    other_user = make_user(session, "other@example.com", department="manufacturing")
    case = PdEcrCase(case_no="PDECR-MY-TASKS-001", title="My tasks")
    session.add(case)
    session.commit()
    session.refresh(case)

    session.add(
        PdEcrExecutionTask(
            case_id=case.id,
            checklist_row_id="quality-row",
            department="quality",
            description="Update testing program",
            assignee_id=assignee.id,
            assignee_email=assignee.email,
            assignee_name=assignee.full_name,
        )
    )
    session.add(
        PdEcrExecutionTask(
            case_id=case.id,
            checklist_row_id="mfg-row",
            department="manufacturing",
            description="Update work instruction",
            assignee_id=other_user.id,
            assignee_email=other_user.email,
            assignee_name=other_user.full_name,
        )
    )
    session.add(
        PdEcrLeaderReviewTask(
            case_id=case.id,
            department="quality",
            reviewer_id=reviewer.id,
            reviewer_email=reviewer.email,
            reviewer_name=reviewer.full_name,
        )
    )
    session.commit()

    assignee_tasks = list_my_workflow_tasks(session=session, current_user=assignee)
    reviewer_tasks = list_my_workflow_tasks(session=session, current_user=reviewer)

    assert [task["checklist_row_id"] for task in assignee_tasks["execution_tasks"]] == [
        "quality-row"
    ]
    assert assignee_tasks["execution_tasks"][0]["case_exists"] is True
    assert assignee_tasks["execution_tasks"][0]["case"]["case_no"] == "PDECR-MY-TASKS-001"
    assert assignee_tasks["leader_review_tasks"] == []
    assert reviewer_tasks["execution_tasks"] == []
    assert [task["department"] for task in reviewer_tasks["leader_review_tasks"]] == [
        "quality"
    ]
    assert reviewer_tasks["leader_review_tasks"][0]["case_exists"] is True
    assert reviewer_tasks["leader_review_tasks"][0]["case"]["case_no"] == "PDECR-MY-TASKS-001"


def test_list_my_workflow_tasks_manager_sees_all_tasks(session):
    manager = make_user(session, "manager@example.com", role="pd_ecr_manager")
    assignee = make_user(session, "assignee2@example.com", department="quality")
    reviewer = make_user(session, "leader2@example.com", department="quality")
    case = PdEcrCase(case_no="PDECR-MY-TASKS-002", title="Manager tasks")
    session.add(case)
    session.commit()
    session.refresh(case)

    session.add(
        PdEcrExecutionTask(
            case_id=case.id,
            checklist_row_id="quality-row",
            department="quality",
            description="Update testing program",
            assignee_id=assignee.id,
            assignee_email=assignee.email,
            assignee_name=assignee.full_name,
        )
    )
    session.add(
        PdEcrLeaderReviewTask(
            case_id=case.id,
            department="quality",
            reviewer_id=reviewer.id,
            reviewer_email=reviewer.email,
            reviewer_name=reviewer.full_name,
        )
    )
    session.commit()

    tasks = list_my_workflow_tasks(session=session, current_user=manager)

    assert len(tasks["execution_tasks"]) == 1
    assert len(tasks["leader_review_tasks"]) == 1
    assert tasks["execution_tasks"][0]["case"]["case_no"] == "PDECR-MY-TASKS-002"
    assert tasks["leader_review_tasks"][0]["case"]["case_no"] == "PDECR-MY-TASKS-002"


def test_delete_case_removes_workflow_children(session):
    manager = make_user(session, "cleanup-manager@example.com", role="pd_ecr_manager")
    case = PdEcrCase(case_no="PDECR-CLEANUP-001", title="Cleanup draft")
    session.add(case)
    session.commit()
    session.refresh(case)

    session.add(
        PdEcrModule(
            case_id=case.id,
            module_id="change-description",
            title="Change Description",
        )
    )
    session.add(
        PdEcrExecutionTask(
            case_id=case.id,
            checklist_row_id="cleanup-row",
            department="quality",
            description="Cleanup task",
            assignee_email="cleanup@example.com",
        )
    )
    session.commit()

    deleted = delete_case(session=session, case=case, current_user=manager)

    assert deleted["case_no"] == "PDECR-CLEANUP-001"
    assert session.get(PdEcrCase, case.id) is None
    assert session.exec(select(PdEcrModule).where(PdEcrModule.case_id == case.id)).all() == []
    assert session.exec(select(PdEcrExecutionTask).where(PdEcrExecutionTask.case_id == case.id)).all() == []


def test_delete_case_rejects_approved_case(session):
    manager = make_user(session, "cleanup-manager2@example.com", role="pd_ecr_manager")
    case = PdEcrCase(
        case_no="PDECR-CLEANUP-APPROVED-001",
        title="Approved",
        status="approved",
    )
    session.add(case)
    session.commit()
    session.refresh(case)

    with pytest.raises(HTTPException) as exc:
        delete_case(session=session, case=case, current_user=manager)

    assert exc.value.status_code == 422
    assert session.get(PdEcrCase, case.id) is not None
