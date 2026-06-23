from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlmodel import Session, select

from app.models import PdEcrCase, PdEcrModule, PdEcrNotification
from app.services.pd_ecr_audit_service import write_activity

try:
    from app.utils import send_email
except ModuleNotFoundError as exc:
    if exc.name != "emails":
        raise

    def send_email(
        *,
        email_to: str,
        subject: str = "",
        html_content: str = "",
    ) -> None:
        raise RuntimeError("Email utility dependency is not installed")


DONE_STATUSES = {"done", "approved", "closed", "completed", "cancelled"}


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def build_module_email_subject(
    case: PdEcrCase, module: PdEcrModule, kind: str
) -> str:
    prefix = {
        "module_assignment": "PD-ECR module assigned",
        "module_due_soon": "PD-ECR module due soon",
        "module_overdue": "PD-ECR module overdue",
        "review_request": "PD-ECR module review requested",
    }.get(kind, "PD-ECR module reminder")
    return f"{prefix}: {case.case_no} / {module.title or module.module_id}"


def build_module_email_html(
    case: PdEcrCase, module: PdEcrModule, action: str
) -> str:
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
    sent_at: datetime | None = None,
) -> PdEcrNotification:
    sent_at = (sent_at or now_utc()) if status == "sent" else None
    notification = PdEcrNotification(
        case_id=case.id,
        module_id=module.module_id,
        recipient_email=recipient_email,
        notification_type=notification_type,
        subject=subject,
        status=status,
        provider="smtp",
        error_message=error_message,
        sent_at=sent_at,
    )
    session.add(notification)
    if sent_at is not None:
        module.last_reminded_at = sent_at
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
    *,
    session: Session,
    case: PdEcrCase,
    module: PdEcrModule,
    notification_type: str,
    sent_at: datetime | None = None,
) -> PdEcrNotification:
    recipient = module.assignee_email or ""
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
            sent_at=sent_at,
        )

    try:
        send_email(
            email_to=recipient,
            subject=subject,
            html_content=build_module_email_html(case, module, subject),
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
            sent_at=sent_at,
        )

    return _record_notification(
        session=session,
        case=case,
        module=module,
        recipient_email=recipient,
        notification_type=notification_type,
        subject=subject,
        status="sent",
        sent_at=sent_at,
    )


def send_module_assignment_email(
    *, session: Session, case: PdEcrCase, module: PdEcrModule
) -> PdEcrNotification:
    return send_module_email(
        session=session,
        case=case,
        module=module,
        notification_type="module_assignment",
    )


def send_module_due_soon_email(
    *,
    session: Session,
    case: PdEcrCase,
    module: PdEcrModule,
    sent_at: datetime | None = None,
) -> PdEcrNotification:
    return send_module_email(
        session=session,
        case=case,
        module=module,
        notification_type="module_due_soon",
        sent_at=sent_at,
    )


def send_module_overdue_email(
    *,
    session: Session,
    case: PdEcrCase,
    module: PdEcrModule,
    sent_at: datetime | None = None,
) -> PdEcrNotification:
    return send_module_email(
        session=session,
        case=case,
        module=module,
        notification_type="module_overdue",
        sent_at=sent_at,
    )


def _already_sent_today(
    session: Session,
    *,
    case_id: object,
    module_id: str,
    notification_type: str,
    now: datetime,
) -> bool:
    records = session.exec(
        select(PdEcrNotification).where(
            PdEcrNotification.case_id == case_id,
            PdEcrNotification.module_id == module_id,
            PdEcrNotification.notification_type == notification_type,
            PdEcrNotification.status == "sent",
        )
    ).all()
    today = _as_utc(now).date()
    return any(
        record.sent_at is not None and _as_utc(record.sent_at).date() == today
        for record in records
    )


def _reminder_type_for_module(module: PdEcrModule, now: datetime) -> str | None:
    if module.due_date is None:
        return None

    due_at = _as_utc(module.due_date)
    current_time = _as_utc(now)
    if due_at <= current_time:
        return "module_overdue"

    policy = module.reminder_policy or {}
    days_before_due = policy.get("days_before_due") or []
    for raw_days in days_before_due:
        try:
            days = int(raw_days)
        except (TypeError, ValueError):
            continue
        if current_time >= due_at - timedelta(days=days):
            return "module_due_soon"

    return None


def run_due_reminders(
    *, session: Session, now: datetime | None = None
) -> dict[str, int]:
    current_time = now or now_utc()
    sent = 0
    failed = 0
    skipped = 0

    modules = session.exec(
        select(PdEcrModule).where(PdEcrModule.due_date.is_not(None))
    ).all()
    for module in modules:
        if module.status in DONE_STATUSES:
            skipped += 1
            continue

        notification_type = _reminder_type_for_module(module, current_time)
        if notification_type is None:
            skipped += 1
            continue

        if _already_sent_today(
            session,
            case_id=module.case_id,
            module_id=module.module_id,
            notification_type=notification_type,
            now=current_time,
        ):
            skipped += 1
            continue

        case = session.get(PdEcrCase, module.case_id)
        if case is None:
            skipped += 1
            continue

        if notification_type == "module_due_soon":
            notification = send_module_due_soon_email(
                session=session, case=case, module=module, sent_at=current_time
            )
        else:
            notification = send_module_overdue_email(
                session=session, case=case, module=module, sent_at=current_time
            )

        if notification.status == "sent":
            sent += 1
        else:
            failed += 1

    return {"sent": sent, "failed": failed, "skipped": skipped}
