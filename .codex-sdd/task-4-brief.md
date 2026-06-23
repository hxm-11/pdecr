### Task 4: Email notification service and reminder endpoints

**Files:**
- Create: `backend/app/services/pd_ecr_notification_service.py`
- Modify: `backend/app/api/routes/pd_ecr.py`
- Test: `backend/app/tests/services/test_pd_ecr_permissions_notifications.py`

**Interfaces:**
- Consumes:
  - `PdEcrNotification`, `PdEcrModule`, `PdEcrCase`, existing email utility
- Produces:
  - `send_module_assignment_email(session, case, module) -> PdEcrNotification`
  - `send_module_due_soon_email(session, case, module) -> PdEcrNotification`
  - `send_module_overdue_email(session, case, module) -> PdEcrNotification`
  - `run_due_reminders(session, now=None) -> dict[str, int]`
  - `POST /cases/{case_id}/modules/{module_id}/send-reminder`
  - `POST /notifications/run-due-reminders`

- [ ] **Step 1: Add failing notification service tests**

Append to `backend/app/tests/services/test_pd_ecr_permissions_notifications.py`:

```python
from app.models import PdEcrNotification
from app.services.pd_ecr_notification_service import (
    build_module_email_subject,
    run_due_reminders,
    send_module_assignment_email,
)


def test_send_module_assignment_email_records_notification(session: Session, monkeypatch):
    sent = []

    def fake_send_email(*, email_to, subject, html_content):
        sent.append({"email_to": email_to, "subject": subject, "html_content": html_content})

    monkeypatch.setattr("app.services.pd_ecr_notification_service.send_email", fake_send_email)
    owner = make_user(session, "notify-owner@example.com")
    assignee = make_user(session, "notify-assignee@example.com", role="module_owner")
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

    notification = send_module_assignment_email(session=session, case=case, module=module)

    assert notification.status == "sent"
    assert sent[0]["email_to"] == "notify-assignee@example.com"
    assert "PDECR-NOTIFY-001" in sent[0]["subject"]
    assert session.exec(select(PdEcrNotification)).one().notification_type == "module_assignment"


def test_due_reminder_scans_due_modules_once_per_day(session: Session, monkeypatch):
    sent = []

    def fake_send_email(*, email_to, subject, html_content):
        sent.append(subject)

    monkeypatch.setattr("app.services.pd_ecr_notification_service.send_email", fake_send_email)
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

    result = run_due_reminders(session=session, now=datetime(2026, 6, 19, tzinfo=timezone.utc))
    second = run_due_reminders(session=session, now=datetime(2026, 6, 19, 12, tzinfo=timezone.utc))

    assert result["sent"] == 1
    assert second["sent"] == 0
    assert sent
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```powershell
python -m pytest backend/app/tests/services/test_pd_ecr_permissions_notifications.py -v
```

Expected: FAIL because notification service does not exist.

- [ ] **Step 3: Implement notification service**

Create `backend/app/services/pd_ecr_notification_service.py`:

```python
from __future__ import annotations

from datetime import datetime, timezone

from sqlmodel import Session, select

from app.models import PdEcrCase, PdEcrModule, PdEcrNotification
from app.services.pd_ecr_audit_service import write_activity
from app.utils import send_email


DONE_STATUSES = {"done", "approved", "closed"}


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def build_module_email_subject(case: PdEcrCase, module: PdEcrModule, kind: str) -> str:
    prefix = {
        "module_assignment": "PD-ECR module assigned",
        "module_due_soon": "PD-ECR module due soon",
        "module_overdue": "PD-ECR module overdue",
        "review_request": "PD-ECR module review requested",
    }.get(kind, "PD-ECR module reminder")
    return f"{prefix}: {case.case_no} / {module.title or module.module_id}"


def build_module_email_html(case: PdEcrCase, module: PdEcrModule, action: str) -> str:
    due_date = module.due_date.isoformat() if module.due_date else "No due date"
    link = f"/pd-ecr/cases/{case.id}/modules/{module.module_id}"
    return f"""
    <h2>{action}</h2>
    <p><strong>PD-ECR:</strong> {case.case_no}</p>
    <p><strong>MCR:</strong> {case.mcr_no or "-"}</p>
    <p><strong>Case:</strong> {case.title or "-"}</p>
    <p><strong>Module:</strong> {module.title or module.module_id}</p>
    <p><strong>Status:</strong> {module.status}</p>
    <p><strong>Responsible:</strong> {module.assignee_name or module.assignee_email or "-"}</p>
    <p><strong>Due date:</strong> {due_date}</p>
    <p><strong>Open module:</strong> {link}</p>
    """


def _record_notification(
    *,
    session: Session,
    case: PdEcrCase,
    module: PdEcrModule,
    recipient_email: str,
    notification_type: str,
    subject: str,
    status: str,
    error_message: str | None = None,
) -> PdEcrNotification:
    notification = PdEcrNotification(
        case_id=case.id,
        module_id=module.module_id,
        recipient_email=recipient_email,
        notification_type=notification_type,
        subject=subject,
        status=status,
        provider="smtp",
        error_message=error_message,
        sent_at=now_utc() if status == "sent" else None,
    )
    session.add(notification)
    module.last_reminded_at = notification.sent_at or module.last_reminded_at
    session.add(module)
    write_activity(
        session=session,
        action=f"notification.{status}",
        case_id=case.id,
        target_type="module",
        target_id=module.module_id,
        metadata={
            "notification_type": notification_type,
            "recipient_email": recipient_email,
        },
    )
    session.commit()
    session.refresh(notification)
    return notification


def send_module_email(
    *, session: Session, case: PdEcrCase, module: PdEcrModule, notification_type: str
) -> PdEcrNotification:
    recipient = module.assignee_email
    subject = build_module_email_subject(case, module, notification_type)
    if not recipient:
        return _record_notification(
            session=session,
            case=case,
            module=module,
            recipient_email="",
            notification_type=notification_type,
            subject=subject,
            status="failed",
            error_message="Module has no assignee_email",
        )
    try:
        send_email(
            email_to=recipient,
            subject=subject,
            html_content=build_module_email_html(case, module, subject),
        )
        return _record_notification(
            session=session,
            case=case,
            module=module,
            recipient_email=recipient,
            notification_type=notification_type,
            subject=subject,
            status="sent",
        )
    except Exception as exc:
        return _record_notification(
            session=session,
            case=case,
            module=module,
            recipient_email=recipient,
            notification_type=notification_type,
            subject=subject,
            status="failed",
            error_message=str(exc),
        )


def send_module_assignment_email(*, session: Session, case: PdEcrCase, module: PdEcrModule) -> PdEcrNotification:
    return send_module_email(
        session=session,
        case=case,
        module=module,
        notification_type="module_assignment",
    )


def send_module_due_soon_email(*, session: Session, case: PdEcrCase, module: PdEcrModule) -> PdEcrNotification:
    return send_module_email(
        session=session,
        case=case,
        module=module,
        notification_type="module_due_soon",
    )


def send_module_overdue_email(*, session: Session, case: PdEcrCase, module: PdEcrModule) -> PdEcrNotification:
    return send_module_email(
        session=session,
        case=case,
        module=module,
        notification_type="module_overdue",
    )


def _already_sent_today(session: Session, module: PdEcrModule, notification_type: str, now: datetime) -> bool:
    records = session.exec(
        select(PdEcrNotification).where(
            PdEcrNotification.module_id == module.module_id,
            PdEcrNotification.notification_type == notification_type,
            PdEcrNotification.status == "sent",
        )
    ).all()
    return any(record.sent_at and record.sent_at.date() == now.date() for record in records)


def run_due_reminders(*, session: Session, now: datetime | None = None) -> dict[str, int]:
    now = now or now_utc()
    sent = 0
    failed = 0
    skipped = 0
    modules = session.exec(select(PdEcrModule).where(PdEcrModule.due_date <= now)).all()
    for module in modules:
        if module.status in DONE_STATUSES:
            skipped += 1
            continue
        if _already_sent_today(session, module, "module_overdue", now):
            skipped += 1
            continue
        case = session.get(PdEcrCase, module.case_id)
        if case is None:
            skipped += 1
            continue
        notification = send_module_overdue_email(session=session, case=case, module=module)
        if notification.status == "sent":
            sent += 1
        else:
            failed += 1
    return {"sent": sent, "failed": failed, "skipped": skipped}
```

- [ ] **Step 4: Add routes**

In `backend/app/api/routes/pd_ecr.py`, import:

```python
from app.services.pd_ecr_notification_service import (
    run_due_reminders,
    send_module_assignment_email,
)
from app.services.pd_ecr_case_service import ensure_case_manage_access
```

Add endpoint after assignment endpoint in Task 5 or after module endpoints:

```python
@router.post("/cases/{case_id}/modules/{module_id}/send-reminder")
def send_pd_ecr_module_reminder(
    case_id: str,
    module_id: str,
    session: SessionDep,
    current_user: CurrentUser,
):
    case = get_case_or_404(session=session, case_id=case_id)
    ensure_case_manage_access(case, current_user)
    module = next(
        (item for item in list_modules(session=session, case_id=case.id) if item.module_id == module_id),
        None,
    )
    if module is None:
        raise HTTPException(status_code=404, detail="PD-ECR module not found")
    notification = send_module_assignment_email(session=session, case=case, module=module)
    return {"notification": notification.model_dump(mode="json")}


@router.post("/notifications/run-due-reminders")
def run_pd_ecr_due_reminders(
    session: SessionDep,
    current_user: CurrentUser,
):
    if not current_user.is_superuser and getattr(current_user, "pd_ecr_role", None) != "pd_ecr_manager":
        raise HTTPException(status_code=403, detail="No permission to run reminders")
    return run_due_reminders(session=session)
```

- [ ] **Step 5: Run tests**

Run:

```powershell
python -m pytest backend/app/tests/services/test_pd_ecr_permissions_notifications.py -v
```

Expected: PASS.

- [ ] **Step 6: Commit**

Run:

```bash
git add backend/app/services/pd_ecr_notification_service.py backend/app/api/routes/pd_ecr.py backend/app/tests/services/test_pd_ecr_permissions_notifications.py
git commit -m "feat: add pd-ecr module email reminders"
```

---

