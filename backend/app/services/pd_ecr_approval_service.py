from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from fastapi import HTTPException, status
from sqlmodel import Session, select

from app.models import PdEcrApprovalTask, PdEcrCase, PdEcrCaseCreate, PdEcrModule, User
from app.services.pd_ecr_audit_service import write_activity
from app.services.pd_ecr_case_service import create_case, serialize_case
from app.services.pd_ecr_form_service import (
    normalize_new_pdecr_form,
    parse_target_close_date,
    validate_new_pdecr_form,
)
from app.services.pd_ecr_lifecycle_service import (
    LIFECYCLE_DRAFT,
    LIFECYCLE_REJECTED,
    LIFECYCLE_SUBMITTED,
    LIFECYCLE_TASK_EXECUTING,
    normalize_lifecycle_status,
    transition_case_lifecycle,
)
from app.services.pd_ecr_notification_service import record_workflow_notification
from app.services.pd_ecr_person_directory_service import resolve_approver


APPROVAL_DRAFT_STATUS = LIFECYCLE_DRAFT
APPROVAL_SUBMITTED_STATUS = LIFECYCLE_SUBMITTED
APPROVAL_APPROVED_STATUS = LIFECYCLE_TASK_EXECUTING
APPROVAL_REJECTED_STATUS = LIFECYCLE_REJECTED


def now_utc() -> datetime:
    from app.models import get_datetime_utc

    return get_datetime_utc()


def _actor_name(user: User) -> str:
    return user.display_name or user.full_name or user.email or str(user.id)


def _ensure_approval_actor(task: PdEcrApprovalTask, user: User) -> None:
    if user.is_superuser or getattr(user, "pd_ecr_role", None) == "pd_ecr_manager":
        return
    if task.approver_id and task.approver_id == user.id:
        return
    if task.approver_email and task.approver_email == user.email:
        return
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Only the assigned approver can act on this approval task",
    )


def _pending_approval_task(
    *, session: Session, case_id: uuid.UUID
) -> PdEcrApprovalTask | None:
    return session.exec(
        select(PdEcrApprovalTask).where(
            PdEcrApprovalTask.case_id == case_id,
            PdEcrApprovalTask.status == "pending",
        )
    ).first()


def _serialize_approval_task(task: PdEcrApprovalTask) -> dict[str, Any]:
    return {
        "id": str(task.id),
        "case_id": str(task.case_id),
        "status": task.status,
        "approver_id": str(task.approver_id) if task.approver_id else None,
        "approver_email": task.approver_email,
        "approver_name": task.approver_name,
        "rejection_reason": task.rejection_reason,
        "approved_at": task.approved_at.isoformat() if task.approved_at else None,
        "created_at": task.created_at.isoformat() if task.created_at else None,
        "updated_at": task.updated_at.isoformat() if task.updated_at else None,
    }


def _upsert_change_description_module(
    *,
    session: Session,
    case: PdEcrCase,
    form_data: dict[str, Any],
    current_user: User,
) -> PdEcrModule:
    module = session.exec(
        select(PdEcrModule).where(
            PdEcrModule.case_id == case.id,
            PdEcrModule.module_id == "change-description",
        )
    ).first()
    if module is None:
        module = PdEcrModule(
            case_id=case.id,
            module_id="change-description",
            title="Change Request description",
            source_cases=[case.case_no],
            source_files=[],
            version=1,
        )

    content_json = {
        **form_data,
        "title": case.title or form_data.get("title") or "PD-ECR Change Request",
        "changeTitle": form_data.get("changeTitle") or case.title,
        "initiator": case.initiator or form_data.get("initiator") or _actor_name(current_user),
        "customer_project": case.customer_project or form_data.get("customer_project") or form_data.get("customer"),
        "product_no": case.product_no or form_data.get("product_no") or form_data.get("product"),
        "part_no": case.part_no or form_data.get("part_no") or form_data.get("component_no") or form_data.get("partNumber"),
        "component_no": case.part_no or form_data.get("component_no") or form_data.get("partNumber"),
        "target_close_date": case.target_close_date.isoformat() if case.target_close_date else form_data.get("target_close_date"),
        "leader_confirmed": False,
        "content": (
            form_data.get("changeSummary")
            or form_data.get("change_description")
            or form_data.get("change_proposal")
            or form_data.get("description")
            or case.title
            or ""
        ),
        "summary": (
            form_data.get("changeSummary")
            or form_data.get("change_description")
            or form_data.get("change_proposal")
            or case.title
            or ""
        ),
    }
    module.title = module.title or "Change Request description"
    module.content_json = content_json
    module.content_md = str(content_json.get("content") or "")
    module.needs_human_input = False
    module.status = APPROVAL_SUBMITTED_STATUS
    module.updated_by_id = current_user.id
    module.updated_at = now_utc()
    session.add(module)
    return module


def create_case_and_submit_for_approval(
    *,
    session: Session,
    title: str = "",
    initiator: str | None = None,
    customer_project: str | None = None,
    product_no: str | None = None,
    part_no: str | None = None,
    target_close_date: str | datetime | None = None,
    form_data: dict[str, Any] | None = None,
    approver_email: str | None = None,
    approver_name: str | None = None,
    current_user: User,
) -> dict[str, Any]:
    case_no = f"PD-ECR-{uuid.uuid4().hex[:8].upper()}"
    normalized_form = normalize_new_pdecr_form(
        title=title,
        initiator=initiator,
        customer_project=customer_project,
        product_no=product_no,
        part_no=part_no,
        target_close_date=target_close_date,
        form_data=form_data,
    )
    validate_new_pdecr_form(normalized_form)
    parsed_target_close_date = parse_target_close_date(normalized_form.get("target_close_date"))

    case = create_case(
        session=session,
        case_in=PdEcrCaseCreate(
            case_no=case_no,
            title=normalized_form.get("title") or "PD-ECR Change Request",
            status=APPROVAL_DRAFT_STATUS,
            source_type="manual",
            initiator=normalized_form.get("initiator") or _actor_name(current_user),
            customer_project=normalized_form.get("customer_project"),
            product_no=normalized_form.get("product_no"),
            part_no=normalized_form.get("part_no"),
            target_close_date=parsed_target_close_date,
        ),
        current_user=current_user,
    )
    return submit_case_for_approval(
        session=session,
        case=case,
        form_data=normalized_form,
        approver_email=approver_email,
        approver_name=approver_name,
        current_user=current_user,
    )


def submit_case_for_approval(
    *,
    session: Session,
    case: PdEcrCase,
    current_user: User,
    form_data: dict[str, Any] | None = None,
    approver_email: str | None = None,
    approver_name: str | None = None,
) -> dict[str, Any]:
    if case.is_historical:
        raise HTTPException(status_code=403, detail="Historical cases cannot be submitted")
    lifecycle_status = normalize_lifecycle_status(case.status)
    if lifecycle_status not in {APPROVAL_DRAFT_STATUS, APPROVAL_REJECTED_STATUS}:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Case is {lifecycle_status}, not ready for approval submission",
        )
    if _pending_approval_task(session=session, case_id=case.id):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Case already has a pending approval task",
        )
    if not (
        current_user.is_superuser
        or case.owner_id == current_user.id
        or case.created_by_id == current_user.id
        or getattr(current_user, "pd_ecr_role", None) == "pd_ecr_manager"
    ):
        raise HTTPException(status_code=403, detail="No permission to submit this case")

    normalized_form = normalize_new_pdecr_form(
        title=case.title,
        initiator=case.initiator,
        customer_project=case.customer_project,
        product_no=case.product_no,
        part_no=case.part_no,
        target_close_date=case.target_close_date,
        form_data=form_data,
    )
    validate_new_pdecr_form(normalized_form)

    approver_id, resolved_email, resolved_name = resolve_approver(
        session=session,
        current_user=current_user,
        form_data=normalized_form,
        approver_email=approver_email,
        approver_name=approver_name,
    )

    transition_case_lifecycle(
        session=session,
        case=case,
        next_status=APPROVAL_SUBMITTED_STATUS,
        current_user=current_user,
        action="approval.submission_status_changed",
        commit=False,
    )
    _upsert_change_description_module(
        session=session,
        case=case,
        form_data=normalized_form,
        current_user=current_user,
    )
    task = PdEcrApprovalTask(
        case_id=case.id,
        approver_id=approver_id,
        approver_email=resolved_email,
        approver_name=resolved_name,
        status="pending",
    )
    session.add(task)
    write_activity(
        session=session,
        action="approval.submitted",
        case_id=case.id,
        actor_id=current_user.id,
        target_type="approval_task",
        target_id=str(task.id),
        metadata={
            "approver_id": str(approver_id) if approver_id else None,
            "approver_email": resolved_email,
            "from": APPROVAL_DRAFT_STATUS,
            "to": APPROVAL_SUBMITTED_STATUS,
        },
    )
    record_workflow_notification(
        session=session,
        case=case,
        recipient_email=resolved_email,
        notification_type="manager_approval_request",
        department=current_user.department or "manager_approval",
        comment=f"Submitted by {_actor_name(current_user)}",
    )
    session.commit()
    session.refresh(case)
    session.refresh(task)
    return {"case": serialize_case(case), "approval_task": _serialize_approval_task(task)}


def approve_submitted_case(
    *,
    session: Session,
    case: PdEcrCase,
    current_user: User,
    comment: str | None = None,
) -> dict[str, Any]:
    if normalize_lifecycle_status(case.status) != APPROVAL_SUBMITTED_STATUS:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Case is {case.status}, not submitted",
        )
    task = _pending_approval_task(session=session, case_id=case.id)
    if task is None:
        raise HTTPException(status_code=404, detail="No pending approval task for this case")
    _ensure_approval_actor(task, current_user)

    now = now_utc()
    task.status = "approved"
    task.approved_at = now
    task.updated_at = now
    session.add(task)
    transition_case_lifecycle(
        session=session,
        case=case,
        next_status=APPROVAL_APPROVED_STATUS,
        current_user=current_user,
        action="approval.approval_status_changed",
        commit=False,
    )

    module = session.exec(
        select(PdEcrModule).where(
            PdEcrModule.case_id == case.id,
            PdEcrModule.module_id == "change-description",
        )
    ).first()
    if module is not None:
        content = dict(module.content_json or {})
        content["leaderConfirmed"] = True
        content["leader_confirmed"] = True
        content["leader_confirmed_by"] = _actor_name(current_user)
        content["leader_confirmed_at"] = now.isoformat()
        module.content_json = content
        module.status = APPROVAL_APPROVED_STATUS
        module.updated_by_id = current_user.id
        module.updated_at = now
        session.add(module)

    write_activity(
        session=session,
        action="approval.approved",
        case_id=case.id,
        actor_id=current_user.id,
        target_type="approval_task",
        target_id=str(task.id),
        message=comment,
        metadata={"from": APPROVAL_SUBMITTED_STATUS, "to": APPROVAL_APPROVED_STATUS},
    )
    recipient_email = _case_owner_email(session=session, case=case)
    notification = record_workflow_notification(
        session=session,
        case=case,
        recipient_email=recipient_email,
        notification_type="manager_approval_approved",
        department=current_user.department or "manager_approval",
        comment=comment or f"Approved by {_actor_name(current_user)}",
    )
    session.commit()
    session.refresh(case)
    session.refresh(task)
    session.refresh(notification)
    return {
        "case": serialize_case(case),
        "approval_task": _serialize_approval_task(task),
        "message": "Case approved.",
        "notification": notification.model_dump(mode="json"),
    }


def reject_submitted_case(
    *,
    session: Session,
    case: PdEcrCase,
    current_user: User,
    rejection_reason: str | None = None,
) -> dict[str, Any]:
    if normalize_lifecycle_status(case.status) != APPROVAL_SUBMITTED_STATUS:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Case is {case.status}, not submitted",
        )
    task = _pending_approval_task(session=session, case_id=case.id)
    if task is None:
        raise HTTPException(status_code=404, detail="No pending approval task for this case")
    _ensure_approval_actor(task, current_user)

    now = now_utc()
    task.status = "rejected"
    task.rejection_reason = rejection_reason
    task.updated_at = now
    session.add(task)
    transition_case_lifecycle(
        session=session,
        case=case,
        next_status=APPROVAL_REJECTED_STATUS,
        current_user=current_user,
        action="approval.rejection_status_changed",
        commit=False,
    )
    write_activity(
        session=session,
        action="approval.rejected",
        case_id=case.id,
        actor_id=current_user.id,
        target_type="approval_task",
        target_id=str(task.id),
        message=rejection_reason,
        metadata={"from": APPROVAL_SUBMITTED_STATUS, "to": APPROVAL_REJECTED_STATUS},
    )
    session.commit()
    session.refresh(case)
    session.refresh(task)
    return {
        "case": serialize_case(case),
        "approval_task": _serialize_approval_task(task),
        "message": "Case rejected. Initiator can revise and resubmit.",
    }


def _case_owner_email(*, session: Session, case: PdEcrCase) -> str | None:
    owner = session.get(User, case.owner_id) if case.owner_id else None
    creator = (
        session.get(User, case.created_by_id)
        if case.created_by_id and case.created_by_id != case.owner_id
        else owner
    )
    if owner and owner.email:
        return owner.email
    if creator and creator.email:
        return creator.email
    if case.initiator and "@" in case.initiator:
        return case.initiator
    return None
