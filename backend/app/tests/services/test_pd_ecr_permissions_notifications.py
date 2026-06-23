from datetime import datetime, timezone

import pytest
from fastapi import HTTPException
from sqlmodel import SQLModel, Session, create_engine, select

from app.models import (
    PdEcrCaseCreate,
    PdEcrModule,
    PdEcrModuleUpdate,
    PdEcrNotification,
    User,
)
from app.services.pd_ecr_case_service import (
    assign_module,
    create_case,
    ensure_case_manage_access,
    module_permission_flags,
    serialize_module,
    serialize_module_for_user,
    update_module,
)
from app.services.pd_ecr_notification_service import (
    build_module_email_subject,
    run_due_reminders,
    send_module_assignment_email,
)


@pytest.fixture()
def session():
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)
    with Session(engine) as db:
        yield db


def make_user(
    session: Session, email: str, *, role: str | None = None, superuser: bool = False
) -> User:
    user = User(
        email=email,
        hashed_password="not-used",
        full_name=email.split("@")[0],
        pd_ecr_role=role,
        is_superuser=superuser,
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


def test_assign_module_updates_owner_and_due_date(session: Session):
    owner = make_user(session, "assign-owner@example.com")
    assignee = make_user(session, "module-owner@example.com", role="module_owner")
    case = create_case(
        session=session,
        case_in=PdEcrCaseCreate(case_no="PDECR-ASSIGN-001", title="Assign"),
        current_user=owner,
    )

    module = assign_module(
        session=session,
        case=case,
        module_id="implementation-plan",
        assignee_id=assignee.id,
        assignee_email=assignee.email,
        assignee_name=assignee.full_name,
        department="Manufacturing",
        due_date=datetime(2026, 6, 21, tzinfo=timezone.utc),
        reminder_policy={"on_assignment": True, "overdue": True},
        current_user=owner,
    )

    assert module.assignee_id == assignee.id
    assert module.department == "Manufacturing"
    assert module.reminder_policy["on_assignment"] is True


def test_case_manager_can_assign_but_viewer_cannot(session: Session):
    owner = make_user(session, "owner@example.com")
    manager = make_user(session, "manager@example.com", role="pd_ecr_manager")
    viewer = make_user(session, "viewer@example.com", role="viewer")
    case = create_case(
        session=session,
        case_in=PdEcrCaseCreate(case_no="PDECR-PERM-001", title="Permissions"),
        current_user=owner,
    )

    ensure_case_manage_access(case, manager)

    with pytest.raises(HTTPException) as exc:
        ensure_case_manage_access(case, viewer)
    assert exc.value.status_code == 403


def test_module_owner_can_update_assigned_module(session: Session):
    owner = make_user(session, "owner2@example.com")
    assignee = make_user(session, "assignee@example.com", role="module_owner")
    case = create_case(
        session=session,
        case_in=PdEcrCaseCreate(case_no="PDECR-PERM-002", title="Assigned"),
        current_user=owner,
    )
    module = session.exec(
        select(PdEcrModule).where(
            PdEcrModule.case_id == case.id,
            PdEcrModule.module_id == "change-description",
        )
    ).one()
    module.assignee_id = assignee.id
    module.assignee_email = assignee.email
    module.assignee_name = assignee.full_name
    module.due_date = datetime(2026, 6, 20, tzinfo=timezone.utc)
    session.add(module)
    session.commit()

    updated = update_module(
        session=session,
        case=case,
        module_id="change-description",
        module_in=PdEcrModuleUpdate(
            content_md="assigned edit", expected_version=module.version
        ),
        current_user=assignee,
    )

    assert updated.content_md == "assigned edit"
    serialized = serialize_module(updated)
    assert serialized["assignee_email"] == "assignee@example.com"
    assert serialized["due_date"].startswith("2026-06-20")
    assert serialized["permissions"] == {}
    assert module_permission_flags(case, updated, assignee)["can_edit"] is True
    assert (
        serialize_module_for_user(case=case, module=updated, user=assignee)[
            "permissions"
        ]["can_edit"]
        is True
    )


def test_module_owner_cannot_change_assignment_due_or_reminder_fields(
    session: Session,
):
    owner = make_user(session, "owner-assignment@example.com")
    assignee = make_user(
        session, "assignee-assignment@example.com", role="module_owner"
    )
    replacement = make_user(session, "replacement@example.com", role="module_owner")
    case = create_case(
        session=session,
        case_in=PdEcrCaseCreate(case_no="PDECR-PERM-004", title="Field guard"),
        current_user=owner,
    )
    module = session.exec(
        select(PdEcrModule).where(
            PdEcrModule.case_id == case.id,
            PdEcrModule.module_id == "change-description",
        )
    ).one()
    module.assignee_id = assignee.id
    module.assignee_email = assignee.email
    module.assignee_name = assignee.full_name
    module.department = "PD"
    module.due_date = datetime(2026, 6, 20, tzinfo=timezone.utc)
    module.reminder_policy = {"days_before_due": [1]}
    session.add(module)
    session.commit()
    session.refresh(module)

    content_update = update_module(
        session=session,
        case=case,
        module_id="change-description",
        module_in=PdEcrModuleUpdate(
            content_md="allowed content update",
            expected_version=module.version,
        ),
        current_user=assignee,
    )
    assert content_update.content_md == "allowed content update"

    guarded_updates = [
        PdEcrModuleUpdate(
            assignee_id=replacement.id,
            expected_version=content_update.version,
        ),
        PdEcrModuleUpdate(
            assignee_email=replacement.email,
            expected_version=content_update.version,
        ),
        PdEcrModuleUpdate(
            assignee_name=replacement.full_name,
            expected_version=content_update.version,
        ),
        PdEcrModuleUpdate(
            department="Quality",
            expected_version=content_update.version,
        ),
        PdEcrModuleUpdate(
            due_date=datetime(2026, 6, 25, tzinfo=timezone.utc),
            expected_version=content_update.version,
        ),
        PdEcrModuleUpdate(
            reminder_policy={"days_before_due": [3]},
            expected_version=content_update.version,
        ),
    ]
    for guarded_update in guarded_updates:
        with pytest.raises(HTTPException) as exc:
            update_module(
                session=session,
                case=case,
                module_id="change-description",
                module_in=guarded_update,
                current_user=assignee,
            )
        assert exc.value.status_code == 403

    session.refresh(content_update)
    assert content_update.assignee_id == assignee.id
    assert content_update.assignee_email == assignee.email
    assert content_update.assignee_name == assignee.full_name
    assert content_update.department == "PD"
    assert content_update.due_date.date().isoformat() == "2026-06-20"
    assert content_update.reminder_policy == {"days_before_due": [1]}


def test_owner_cannot_update_module_on_historical_case(session: Session):
    owner = make_user(session, "owner-historical@example.com")
    case = create_case(
        session=session,
        case_in=PdEcrCaseCreate(
            case_no="PDECR-HIST-001",
            title="Historical read only",
            is_historical=True,
        ),
        current_user=owner,
    )
    module = session.exec(
        select(PdEcrModule).where(
            PdEcrModule.case_id == case.id,
            PdEcrModule.module_id == "change-description",
        )
    ).one()

    with pytest.raises(HTTPException) as exc:
        update_module(
            session=session,
            case=case,
            module_id="change-description",
            module_in=PdEcrModuleUpdate(
                content_md="should not change",
                expected_version=module.version,
            ),
            current_user=owner,
        )

    assert exc.value.status_code == 403
    session.refresh(module)
    assert module.content_md == ""


def test_permission_flags_for_viewer_are_read_only(session: Session):
    owner = make_user(session, "owner3@example.com")
    viewer = make_user(session, "viewer3@example.com", role="viewer")
    case = create_case(
        session=session,
        case_in=PdEcrCaseCreate(case_no="PDECR-PERM-003", title="Read only"),
        current_user=owner,
    )
    module = session.exec(
        select(PdEcrModule).where(
            PdEcrModule.case_id == case.id,
            PdEcrModule.module_id == "impact-analysis",
        )
    ).one()

    flags = module_permission_flags(case, module, viewer)

    assert flags == {
        "can_edit": False,
        "can_assign": False,
        "can_regenerate": False,
        "can_send_reminder": False,
        "can_review": False,
        "can_close": False,
    }


def test_send_module_assignment_email_records_notification(
    session: Session,
    monkeypatch,
):
    sent = []

    def fake_send_email(*, email_to, subject, html_content):
        sent.append(
            {
                "email_to": email_to,
                "subject": subject,
                "html_content": html_content,
            }
        )

    monkeypatch.setattr(
        "app.services.pd_ecr_notification_service.send_email",
        fake_send_email,
    )
    owner = make_user(session, "notify-owner@example.com")
    assignee = make_user(
        session,
        "notify-assignee@example.com",
        role="module_owner",
    )
    case = create_case(
        session=session,
        case_in=PdEcrCaseCreate(case_no="PDECR-NOTIFY-001", title="Notify"),
        current_user=owner,
    )
    module = session.exec(
        select(PdEcrModule).where(
            PdEcrModule.case_id == case.id,
            PdEcrModule.module_id == "change-description",
        )
    ).one()
    module.assignee_id = assignee.id
    module.assignee_email = assignee.email
    module.assignee_name = assignee.full_name
    session.add(module)
    session.commit()

    notification = send_module_assignment_email(
        session=session,
        case=case,
        module=module,
    )

    assert notification.status == "sent"
    assert sent[0]["email_to"] == "notify-assignee@example.com"
    assert "PDECR-NOTIFY-001" in sent[0]["subject"]
    assert (
        build_module_email_subject(case, module, "module_assignment")
        == sent[0]["subject"]
    )
    assert (
        session.exec(select(PdEcrNotification)).one().notification_type
        == "module_assignment"
    )


def test_due_reminder_scans_due_modules_once_per_day(
    session: Session,
    monkeypatch,
):
    sent = []

    def fake_send_email(*, email_to, subject, html_content):
        sent.append(subject)

    monkeypatch.setattr(
        "app.services.pd_ecr_notification_service.send_email",
        fake_send_email,
    )
    owner = make_user(session, "due-owner@example.com")
    assignee = make_user(session, "due-assignee@example.com", role="module_owner")
    case = create_case(
        session=session,
        case_in=PdEcrCaseCreate(case_no="PDECR-NOTIFY-002", title="Due"),
        current_user=owner,
    )
    module = session.exec(
        select(PdEcrModule).where(
            PdEcrModule.case_id == case.id,
            PdEcrModule.module_id == "impact-analysis",
        )
    ).one()
    module.assignee_id = assignee.id
    module.assignee_email = assignee.email
    module.assignee_name = assignee.full_name
    module.due_date = datetime(2026, 6, 18, 9, 0, tzinfo=timezone.utc)
    module.status = "in_progress"
    session.add(module)
    session.commit()

    result = run_due_reminders(
        session=session,
        now=datetime(2026, 6, 19, tzinfo=timezone.utc),
    )
    second = run_due_reminders(
        session=session,
        now=datetime(2026, 6, 19, 12, tzinfo=timezone.utc),
    )

    assert result["sent"] == 1
    assert second["sent"] == 0
    assert sent
