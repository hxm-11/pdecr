import uuid

import pytest
from fastapi import HTTPException
from sqlmodel import SQLModel, Session, create_engine, select

from app.models import (
    PdEcrActivity,
    PdEcrApprovalTask,
    PdEcrCase,
    PdEcrCaseCreate,
    PdEcrModule,
    User,
)
from app.services.pd_ecr_approval_service import (
    approve_submitted_case,
    create_case_and_submit_for_approval,
    reject_submitted_case,
    submit_case_for_approval,
)
from app.services.pd_ecr_case_service import create_case, delete_case


VALID_FORM = {
    "product": "Injector",
    "customer_project": "Customer A",
    "product_no": "PN-001",
    "changeTitle": "Approval MVP",
    "change_reason": "Improve label traceability.",
    "changeSummary": "Change one label.",
    "affected_departments": ["quality"],
}


@pytest.fixture()
def session():
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)
    with Session(engine) as db:
        yield db


@pytest.fixture(autouse=True)
def disable_email(monkeypatch):
    monkeypatch.setattr(
        "app.services.pd_ecr_notification_service.send_email",
        lambda **kwargs: None,
    )


def make_user(session: Session, email: str, *, role: str | None = None) -> User:
    user = User(
        email=email,
        hashed_password="not-used",
        full_name=email.split("@")[0],
        display_name=email.split("@")[0],
        pd_ecr_role=role,
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


def test_create_case_and_submit_creates_pending_approval_task(session: Session):
    creator = make_user(session, "creator@example.com")
    approver = make_user(session, "approver@example.com")

    result = create_case_and_submit_for_approval(
        session=session,
        title="Approval MVP",
        form_data=VALID_FORM,
        approver_email=approver.email,
        current_user=creator,
    )

    assert result["case"]["status"] == "submitted"
    assert result["approval_task"]["status"] == "pending"
    assert result["approval_task"]["approver_id"] == str(approver.id)

    module = session.exec(select(PdEcrModule)).one()
    assert module.module_id == "change-description"
    assert module.status == "submitted"
    assert "Change one label" in (module.content_md or "")


def test_existing_case_submit_rejects_duplicate_pending_task(session: Session):
    creator = make_user(session, "creator2@example.com")
    approver = make_user(session, "approver2@example.com")
    case = create_case(
        session=session,
        case_in=PdEcrCaseCreate(case_no="PDECR-APP-001", title="Approval"),
        current_user=creator,
    )

    submit_case_for_approval(
        session=session,
        case=case,
        form_data=VALID_FORM,
        approver_email=approver.email,
        current_user=creator,
    )

    with pytest.raises(HTTPException) as exc:
        submit_case_for_approval(
            session=session,
            case=case,
            form_data=VALID_FORM,
            approver_email=approver.email,
            current_user=creator,
        )

    assert exc.value.status_code == 409
    assert "not ready" in exc.value.detail or "pending approval" in exc.value.detail


def test_assigned_approver_can_approve_submitted_case(session: Session):
    creator = make_user(session, "creator3@example.com")
    approver = make_user(session, "approver3@example.com")
    result = create_case_and_submit_for_approval(
        session=session,
        title="Approve me",
        form_data=VALID_FORM,
        approver_email=approver.email,
        current_user=creator,
    )
    case_id = result["case"]["id"]
    case = session.get(PdEcrCase, uuid.UUID(case_id))

    approved = approve_submitted_case(
        session=session,
        case=case,
        current_user=approver,
        comment="Looks good.",
    )

    assert approved["case"]["status"] == "task_executing"
    assert approved["case"]["lifecycle_status"] == "task_executing"
    assert approved["approval_task"]["status"] == "approved"
    assert session.exec(select(PdEcrApprovalTask)).one().approved_at is not None
    actions = [item.action for item in session.exec(select(PdEcrActivity)).all()]
    assert "approval.approved" in actions


def test_unassigned_user_cannot_approve(session: Session):
    creator = make_user(session, "creator4@example.com")
    approver = make_user(session, "approver4@example.com")
    stranger = make_user(session, "stranger@example.com")
    result = create_case_and_submit_for_approval(
        session=session,
        title="Do not approve",
        form_data=VALID_FORM,
        approver_email=approver.email,
        current_user=creator,
    )
    case = session.get(PdEcrCase, uuid.UUID(result["case"]["id"]))

    with pytest.raises(HTTPException) as exc:
        approve_submitted_case(
            session=session,
            case=case,
            current_user=stranger,
        )

    assert exc.value.status_code == 403


def test_assigned_approver_can_reject_and_case_can_be_deleted(session: Session):
    creator = make_user(session, "creator5@example.com")
    approver = make_user(session, "approver5@example.com")
    result = create_case_and_submit_for_approval(
        session=session,
        title="Reject me",
        form_data=VALID_FORM,
        approver_email=approver.email,
        current_user=creator,
    )
    case = session.get(PdEcrCase, uuid.UUID(result["case"]["id"]))

    rejected = reject_submitted_case(
        session=session,
        case=case,
        current_user=approver,
        rejection_reason="Missing details.",
    )

    assert rejected["case"]["status"] == "rejected"
    assert rejected["approval_task"]["rejection_reason"] == "Missing details."

    deleted = delete_case(session=session, case=case, current_user=creator)
    assert deleted["case_no"] == rejected["case"]["case_no"]
    assert session.exec(select(PdEcrApprovalTask)).all() == []
