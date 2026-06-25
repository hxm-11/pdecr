import uuid

import pytest
from sqlmodel import SQLModel, Session, create_engine, select

from app.models import PdEcrCaseCreate, PdEcrNotification, User
from app.services.pd_ecr_case_service import create_case
from app.services.pd_ecr_workflow import (
    confirm_department_task,
    get_workflow_state,
    review_leader_task,
    submit_for_department_confirmation,
)


@pytest.fixture()
def session():
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)
    with Session(engine) as db:
        yield db


def make_user(
    session: Session,
    email: str,
    *,
    role: str | None = None,
    department: str | None = None,
) -> User:
    user = User(
        email=email,
        hashed_password="not-used",
        full_name=email.split("@")[0],
        display_name=email.split("@")[0],
        pd_ecr_role=role,
        department=department,
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


def test_submit_creates_one_department_task_per_selected_department(
    session: Session, monkeypatch
):
    sent = []

    def fake_send_email(*, email_to, subject, html_content):
        sent.append({"email_to": email_to, "subject": subject})

    monkeypatch.setattr(
        "app.services.pd_ecr_notification_service.send_email",
        fake_send_email,
    )
    initiator = make_user(session, "initiator@example.com")
    design = make_user(
        session,
        "design.member@example.com",
        role="department_member",
        department="design",
    )
    quality = make_user(
        session,
        "quality.member@example.com",
        role="department_member",
        department="quality",
    )
    case = create_case(
        session=session,
        case_in=PdEcrCaseCreate(case_no="PDECR-WF-001", title="Workflow"),
        current_user=initiator,
    )

    state = submit_for_department_confirmation(
        session=session,
        case=case,
        selected_departments=["design", "quality"],
        assignees={
            "design": {
                "assignee_id": str(design.id),
                "assignee_email": design.email,
                "assignee_name": design.full_name,
            },
            "quality": {
                "assignee_id": str(quality.id),
                "assignee_email": quality.email,
                "assignee_name": quality.full_name,
            },
        },
        current_user=initiator,
    )

    assert state["case"]["status"] == "department_confirmation"
    assert [task["department"] for task in state["department_tasks"]] == [
        "design",
        "quality",
    ]
    assert {task["status"] for task in state["department_tasks"]} == {"pending"}
    assert [item["email_to"] for item in sent] == [
        "design.member@example.com",
        "quality.member@example.com",
    ]
    assert (
        session.exec(select(PdEcrNotification)).first().notification_type
        == "department_confirmation_request"
    )


def test_all_department_confirmations_start_leader_review(session: Session, monkeypatch):
    sent = []

    def fake_send_email(*, email_to, subject, html_content):
        sent.append({"email_to": email_to, "subject": subject})

    monkeypatch.setattr(
        "app.services.pd_ecr_notification_service.send_email",
        fake_send_email,
    )
    initiator = make_user(session, "initiator2@example.com")
    design = make_user(
        session,
        "design.confirm@example.com",
        role="department_member",
        department="design",
    )
    quality = make_user(
        session,
        "quality.confirm@example.com",
        role="department_member",
        department="quality",
    )
    design_leader = make_user(
        session,
        "design.leader@example.com",
        role="department_leader",
        department="design",
    )
    quality_leader = make_user(
        session,
        "quality.leader@example.com",
        role="department_leader",
        department="quality",
    )
    case = create_case(
        session=session,
        case_in=PdEcrCaseCreate(case_no="PDECR-WF-002", title="Workflow"),
        current_user=initiator,
    )
    state = submit_for_department_confirmation(
        session=session,
        case=case,
        selected_departments=["design", "quality"],
        assignees={
            "design": {"assignee_id": str(design.id), "assignee_email": design.email},
            "quality": {
                "assignee_id": str(quality.id),
                "assignee_email": quality.email,
            },
        },
        current_user=initiator,
    )

    first, second = state["department_tasks"]
    confirm_department_task(
        session=session,
        task_id=uuid.UUID(first["id"]),
        impact_result="no_impact",
        impact_remark="Design checked.",
        action_required="No action.",
        current_user=design,
    )
    state = confirm_department_task(
        session=session,
        task_id=uuid.UUID(second["id"]),
        impact_result="impact",
        impact_remark="Quality needs validation.",
        action_required="Add QZ report.",
        current_user=quality,
    )

    assert state["case"]["status"] == "leader_review"
    assert [task["reviewer_email"] for task in state["leader_review_tasks"]] == [
        design_leader.email,
        quality_leader.email,
    ]
    assert {task["status"] for task in state["leader_review_tasks"]} == {"pending"}
    assert sent[-2:] == [
        {
            "email_to": "design.leader@example.com",
            "subject": "PD-ECR leader review requested: PDECR-WF-002 / design",
        },
        {
            "email_to": "quality.leader@example.com",
            "subject": "PD-ECR leader review requested: PDECR-WF-002 / quality",
        },
    ]


def test_all_leader_approvals_mark_case_approved(session: Session, monkeypatch):
    monkeypatch.setattr(
        "app.services.pd_ecr_notification_service.send_email",
        lambda **kwargs: None,
    )
    initiator = make_user(session, "initiator3@example.com")
    design = make_user(
        session,
        "design.confirm3@example.com",
        role="department_member",
        department="design",
    )
    leader = make_user(
        session,
        "design.leader3@example.com",
        role="department_leader",
        department="design",
    )
    case = create_case(
        session=session,
        case_in=PdEcrCaseCreate(case_no="PDECR-WF-003", title="Workflow"),
        current_user=initiator,
    )
    state = submit_for_department_confirmation(
        session=session,
        case=case,
        selected_departments=["design"],
        assignees={
            "design": {"assignee_id": str(design.id), "assignee_email": design.email}
        },
        current_user=initiator,
    )
    state = confirm_department_task(
        session=session,
        task_id=uuid.UUID(state["department_tasks"][0]["id"]),
        impact_result="no_impact",
        impact_remark="No design impact.",
        action_required="No action.",
        current_user=design,
    )

    state = review_leader_task(
        session=session,
        task_id=uuid.UUID(state["leader_review_tasks"][0]["id"]),
        decision="approved",
        review_comment="Approved.",
        signature_name="Design Leader",
        current_user=leader,
    )

    assert state["case"]["status"] == "approved"
    assert state["leader_review_tasks"][0]["signature_name"] == "Design Leader"
    assert get_workflow_state(session=session, case=case)["case"]["status"] == "approved"
