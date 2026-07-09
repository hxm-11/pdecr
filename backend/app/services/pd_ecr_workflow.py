from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import HTTPException, status
from sqlmodel import Session, select

from app.models import (
    PdEcrApprovalTask,
    PdEcrCase,
    PdEcrDepartmentVisibility,
    PdEcrExecutionTask,
    PdEcrDepartmentTask,
    PdEcrLeaderReviewTask,
    User,
)
from app.services.pd_ecr_audit_service import write_activity
from app.services.pd_ecr_case_service import serialize_case
from app.services.pd_ecr_departments import DEPARTMENT_LEADER_ROLE
from app.services.pd_ecr_notification_service import record_workflow_notification


DEPARTMENT_CONFIRMATION_STATUS = "department_confirmation"
DEPARTMENT_ALIGNMENT_STATUS = "department_alignment"
EXECUTION_ASSIGNMENT_STATUS = "execution_assignment"
ASSIGNEE_CONFIRMATION_STATUS = "assignee_confirmation"
EXECUTION_IN_PROGRESS_STATUS = "execution_in_progress"
LEADER_REVIEW_STATUS = "leader_review"
CHANGES_REQUESTED_STATUS = "changes_requested"
APPROVED_STATUS = "approved"

DEPARTMENT_DONE_STATUSES = {"confirmed"}
LEADER_DONE_STATUSES = {"approved"}


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _parse_uuid(value: str | uuid.UUID | None) -> uuid.UUID | None:
    if value is None or isinstance(value, uuid.UUID):
        return value
    value = str(value).strip()
    if not value:
        return None
    return uuid.UUID(value)


def _parse_datetime(value: Any) -> datetime | None:
    if value is None or isinstance(value, datetime):
        return value
    value = str(value).strip()
    if not value:
        return None
    if value.endswith("Z"):
        value = f"{value[:-1]}+00:00"
    return datetime.fromisoformat(value)


def _actor_name(user: User) -> str:
    return (
        getattr(user, "display_name", None)
        or getattr(user, "full_name", None)
        or getattr(user, "email", "")
        or str(user.id)
    )


def _normalize_department(value: str) -> str:
    department = str(value or "").strip().lower()
    if not department:
        raise HTTPException(status_code=422, detail="Department is required")
    return department


def _department_tasks(session: Session, case_id: uuid.UUID) -> list[PdEcrDepartmentTask]:
    return list(
        session.exec(
            select(PdEcrDepartmentTask)
            .where(PdEcrDepartmentTask.case_id == case_id)
            .order_by(PdEcrDepartmentTask.department)
        ).all()
    )


def _leader_tasks(session: Session, case_id: uuid.UUID) -> list[PdEcrLeaderReviewTask]:
    return list(
        session.exec(
            select(PdEcrLeaderReviewTask)
            .where(PdEcrLeaderReviewTask.case_id == case_id)
            .order_by(PdEcrLeaderReviewTask.department)
        ).all()
    )


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


def _approval_tasks(session: Session, case_id: uuid.UUID) -> list[PdEcrApprovalTask]:
    return list(
        session.exec(
            select(PdEcrApprovalTask)
            .where(PdEcrApprovalTask.case_id == case_id)
            .order_by(PdEcrApprovalTask.created_at.desc())
        ).all()
    )


def _serialize_department_task(task: PdEcrDepartmentTask) -> dict[str, Any]:
    target = _target_payload(
        task_type="department_confirmation",
        task_bucket=_bucket_for_status(task.status, "confirmation"),
        module_id="impact-analysis",
        field_path=f"department_confirmation.{task.department}",
        anchor_id=_task_anchor(task.department, prefix="impact-department"),
        case_id=task.case_id,
    )
    return {
        "id": str(task.id),
        "case_id": str(task.case_id),
        "department": task.department,
        "status": task.status,
        "assignee_id": str(task.assignee_id) if task.assignee_id else None,
        "assignee_email": task.assignee_email,
        "assignee_name": task.assignee_name,
        "impact_result": task.impact_result,
        "impact_remark": task.impact_remark,
        "action_required": task.action_required,
        "confirmed_by_id": str(task.confirmed_by_id) if task.confirmed_by_id else None,
        "confirmed_by_name": task.confirmed_by_name,
        "confirmed_at": task.confirmed_at.isoformat() if task.confirmed_at else None,
        "due_date": task.due_date.isoformat() if task.due_date else None,
        "created_at": task.created_at.isoformat() if task.created_at else None,
        "updated_at": task.updated_at.isoformat() if task.updated_at else None,
        **target,
    }


def _serialize_visibility(item: PdEcrDepartmentVisibility) -> dict[str, Any]:
    return {
        "id": str(item.id),
        "case_id": str(item.case_id),
        "department": item.department,
        "visible_to_department": item.visible_to_department,
        "published_by_id": str(item.published_by_id) if item.published_by_id else None,
        "published_at": item.published_at.isoformat() if item.published_at else None,
    }


def _case_summary(case: PdEcrCase | None) -> dict[str, Any] | None:
    if case is None:
        return None
    return serialize_case(case)


def _task_anchor(value: str | None, *, prefix: str) -> str:
    raw = str(value or "").strip().lower()
    cleaned = "".join(ch if ch.isalnum() else "-" for ch in raw).strip("-")
    return f"{prefix}-{cleaned or 'target'}"


def _target_payload(
    *,
    task_type: str,
    task_bucket: str,
    module_id: str,
    field_path: str | None = None,
    anchor_id: str | None = None,
    case_id: uuid.UUID | str | None = None,
) -> dict[str, Any]:
    action_url = None
    if case_id:
        query = f"?caseId={case_id}"
        if field_path:
            query += f"&field={field_path}"
        if anchor_id:
            query += f"&anchor={anchor_id}"
        action_url = f"/pd-ecr/content/{module_id}{query}"

    return {
        "task_type": task_type,
        "task_bucket": task_bucket,
        "module_id": module_id,
        "field_path": field_path,
        "anchor_id": anchor_id,
        "action_url": action_url,
    }


def _bucket_for_status(status_value: str, default_bucket: str) -> str:
    status_text = str(status_value or "").strip().lower()
    if status_text in {"changes_requested", "rejected"}:
        return "supplement"
    return default_bucket


def _serialize_execution_task(
    task: PdEcrExecutionTask,
    *,
    case: PdEcrCase | None = None,
) -> dict[str, Any]:
    target = _target_payload(
        task_type="execution",
        task_bucket=_bucket_for_status(
            task.status,
            "confirmation" if task.status == "pending_confirmation" else "execution",
        ),
        module_id="implementation-plan",
        field_path=f"checklistRows.{task.checklist_row_id}",
        anchor_id=_task_anchor(task.checklist_row_id, prefix="implementation-task"),
        case_id=task.case_id,
    )
    return {
        "id": str(task.id),
        "case_id": str(task.case_id),
        "case": _case_summary(case),
        "case_exists": case is not None,
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
        **target,
    }


def _serialize_leader_task(
    task: PdEcrLeaderReviewTask,
    *,
    case: PdEcrCase | None = None,
) -> dict[str, Any]:
    target = _target_payload(
        task_type="leader_review",
        task_bucket=_bucket_for_status(task.status, "signoff"),
        module_id="validation-plan",
        field_path=f"leader_review.{task.department}",
        anchor_id=_task_anchor(task.department, prefix="leader-review"),
        case_id=task.case_id,
    )
    return {
        "id": str(task.id),
        "case_id": str(task.case_id),
        "case": _case_summary(case),
        "case_exists": case is not None,
        "department": task.department,
        "status": task.status,
        "reviewer_id": str(task.reviewer_id) if task.reviewer_id else None,
        "reviewer_email": task.reviewer_email,
        "reviewer_name": task.reviewer_name,
        "review_comment": task.review_comment,
        "signature_name": task.signature_name,
        "reviewed_at": task.reviewed_at.isoformat() if task.reviewed_at else None,
        "created_at": task.created_at.isoformat() if task.created_at else None,
        "updated_at": task.updated_at.isoformat() if task.updated_at else None,
        **target,
    }


def _serialize_approval_task(task: Any) -> dict[str, Any]:
    target = _target_payload(
        task_type="manager_approval",
        task_bucket=_bucket_for_status(task.status, "signoff"),
        module_id="change-description",
        field_path="manager_approval",
        anchor_id="manager-approval",
        case_id=task.case_id,
    )
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
        **target,
    }


def get_workflow_state(*, session: Session, case: PdEcrCase) -> dict[str, Any]:
    return {
        "case": serialize_case(case),
        "department_visibility": [
            _serialize_visibility(item)
            for item in _department_visibility(session, case.id)
        ],
        "execution_tasks": [
            _serialize_execution_task(task, case=case)
            for task in _execution_tasks(session, case.id)
        ],
        "department_tasks": [
            _serialize_department_task(task)
            for task in _department_tasks(session, case.id)
        ],
        "leader_review_tasks": [
            _serialize_leader_task(task, case=case)
            for task in _leader_tasks(session, case.id)
        ],
        "approval_tasks": [
            _serialize_approval_task(task)
            for task in _approval_tasks(session, case.id)
        ],
    }


def list_my_workflow_tasks(*, session: Session, current_user: User) -> dict[str, Any]:
    execution_statement = select(PdEcrExecutionTask).order_by(
        PdEcrExecutionTask.department,
        PdEcrExecutionTask.checklist_row_id,
    ).where(
        PdEcrExecutionTask.status.notin_(["completed", "cancelled"]),
    )
    leader_statement = select(PdEcrLeaderReviewTask).order_by(
        PdEcrLeaderReviewTask.department,
    ).where(
        PdEcrLeaderReviewTask.status != "approved",
    )
    if not current_user.is_superuser and getattr(current_user, "pd_ecr_role", None) != "pd_ecr_manager":
        execution_statement = execution_statement.where(
            PdEcrExecutionTask.assignee_id == current_user.id
        )
        leader_statement = leader_statement.where(
            PdEcrLeaderReviewTask.reviewer_id == current_user.id
        )

    execution_tasks = list(session.exec(execution_statement).all())
    leader_tasks = list(session.exec(leader_statement).all())
    case_ids = {
        task.case_id
        for task in [*execution_tasks, *leader_tasks]
        if task.case_id is not None
    }
    cases_by_id: dict[uuid.UUID, PdEcrCase] = {}
    if case_ids:
        cases = session.exec(
            select(PdEcrCase).where(PdEcrCase.id.in_(list(case_ids)))  # type: ignore[attr-defined]
        ).all()
        cases_by_id = {case.id: case for case in cases}

    approval_statement = select(PdEcrApprovalTask).order_by(
        PdEcrApprovalTask.created_at.desc()
    )
    if not current_user.is_superuser and getattr(current_user, "pd_ecr_role", None) != "pd_ecr_manager":
        approval_statement = approval_statement.where(
            (PdEcrApprovalTask.approver_id == current_user.id)
            | (PdEcrApprovalTask.approver_email == current_user.email),
        )
    approval_tasks_raw = session.exec(approval_statement).all()
    approval_case_ids = list({t.case_id for t in approval_tasks_raw})
    approval_cases: dict[uuid.UUID, dict[str, Any]] = {}
    if approval_case_ids:
        case_statement = select(PdEcrCase).where(PdEcrCase.id.in_(approval_case_ids))
        approval_cases = {c.id: serialize_case(c) for c in session.exec(case_statement).all()}

    submitted_case_statement = select(PdEcrCase).where(
        (PdEcrCase.created_by_id == current_user.id) | (PdEcrCase.owner_id == current_user.id)
    )
    submitted_cases_raw = session.exec(submitted_case_statement).all()
    submitted_cases = {case.id: serialize_case(case) for case in submitted_cases_raw}
    submitted_approval_tasks_raw = []
    if submitted_cases:
        submitted_approval_statement = select(PdEcrApprovalTask).where(
            PdEcrApprovalTask.case_id.in_(list(submitted_cases.keys()))  # type: ignore[attr-defined]
        ).order_by(PdEcrApprovalTask.created_at.desc())
        submitted_approval_tasks_raw = session.exec(submitted_approval_statement).all()

    # — Department tasks —
    dept_statement = select(PdEcrDepartmentTask).where(
        PdEcrDepartmentTask.assignee_id == current_user.id,
        PdEcrDepartmentTask.status.notin_(["confirmed"]),
    ).order_by(PdEcrDepartmentTask.created_at.desc())
    department_tasks_raw = session.exec(dept_statement).all()
    dept_case_ids = list({t.case_id for t in department_tasks_raw})
    dept_cases: dict[uuid.UUID, dict[str, Any]] = {}
    if dept_case_ids:
        cs = select(PdEcrCase).where(PdEcrCase.id.in_(dept_case_ids))
        dept_cases = {c.id: serialize_case(c) for c in session.exec(cs).all()}

    return {
        "execution_tasks": [
            _serialize_execution_task(task, case=cases_by_id.get(task.case_id))
            for task in execution_tasks
        ],
        "leader_review_tasks": [
            _serialize_leader_task(task, case=cases_by_id.get(task.case_id))
            for task in leader_tasks
        ],
        "approval_tasks": [
            {
                **_serialize_approval_task(t),
                "case": approval_cases.get(t.case_id),
                "case_exists": t.case_id in approval_cases,
            }
            for t in approval_tasks_raw
        ],
        "submitted_approval_tasks": [
            {
                **_serialize_approval_task(t),
                "case": submitted_cases.get(t.case_id),
                "case_exists": t.case_id in submitted_cases,
            }
            for t in submitted_approval_tasks_raw
        ],
        "department_tasks": [
            {
                **_serialize_department_task(t),
                "case": dept_cases.get(t.case_id),
                "case_exists": t.case_id in dept_cases,
            }
            for t in department_tasks_raw
        ],
    }


def _find_leader_for_department(
    *, session: Session, department: str
) -> User | None:
    return session.exec(
        select(User).where(
            User.department == department,
            User.pd_ecr_role == DEPARTMENT_LEADER_ROLE,
            User.is_active == True,  # noqa: E712
        )
    ).first()


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
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="At least one involved department is required",
        )

    existing = {item.department: item for item in _department_visibility(session, case.id)}
    for department in departments:
        item = existing.get(department) or PdEcrDepartmentVisibility(
            case_id=case.id,
            department=department,
        )
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


def assign_execution_tasks(
    *,
    session: Session,
    case: PdEcrCase,
    assignments: list[dict[str, Any]],
    current_user: User,
) -> dict[str, Any]:
    _ensure_case_assignment_actor(case, current_user)
    if not assignments:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="At least one execution assignment is required",
        )

    existing = {task.checklist_row_id: task for task in _execution_tasks(session, case.id)}
    for assignment in assignments:
        row_id = str(assignment.get("checklist_row_id") or "").strip()
        department = _normalize_department(assignment.get("department"))
        email = str(assignment.get("assignee_email") or "").strip()
        if not row_id:
            raise HTTPException(status_code=422, detail="checklist_row_id is required")
        if not email:
            raise HTTPException(status_code=422, detail=f"Missing assignee_email for row: {row_id}")

        task = existing.get(row_id)
        if task is not None:
            _ensure_execution_task_status(
                task,
                {"pending_confirmation", "changes_requested"},
                "Execution task cannot be reassigned after execution has started",
            )
        else:
            task = PdEcrExecutionTask(
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
        task.due_date = _parse_datetime(assignment.get("due_date"))
        task.execution_result = None
        task.execution_note = None
        task.evidence_note = None
        task.completed_by_id = None
        task.completed_by_name = None
        task.completed_at = None
        task.review_comment = None
        task.updated_at = now_utc()
        session.add(task)

    case.status = ASSIGNEE_CONFIRMATION_STATUS
    case.updated_at = now_utc()
    session.add(case)
    session.commit()
    session.refresh(case)
    return get_workflow_state(session=session, case=case)


def _ensure_execution_task_assignee(task: PdEcrExecutionTask, user: User) -> None:
    if user.is_superuser or getattr(user, "pd_ecr_role", None) == "pd_ecr_manager":
        return
    if task.assignee_id and task.assignee_id == user.id:
        return
    raise HTTPException(status_code=403, detail="No permission for execution task")


def _ensure_execution_task_reviewer(task: PdEcrExecutionTask, user: User) -> None:
    if user.is_superuser or getattr(user, "pd_ecr_role", None) == "pd_ecr_manager":
        return
    if (
        getattr(user, "pd_ecr_role", None) == DEPARTMENT_LEADER_ROLE
        and getattr(user, "department", None) == task.department
    ):
        return
    raise HTTPException(status_code=403, detail="No permission to review execution task")


def _ensure_execution_task_status(
    task: PdEcrExecutionTask,
    allowed: set[str],
    message: str,
) -> None:
    if task.status not in allowed:
        raise HTTPException(status_code=422, detail=message)


def confirm_execution_assignment(
    *,
    session: Session,
    task_id: uuid.UUID,
    current_user: User,
) -> dict[str, Any]:
    task = session.get(PdEcrExecutionTask, task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Execution task not found")
    _ensure_execution_task_assignee(task, current_user)
    case = session.get(PdEcrCase, task.case_id)
    if case is None:
        raise HTTPException(status_code=404, detail="PD-ECR case not found")
    _ensure_execution_task_status(
        task,
        {"pending_confirmation", "changes_requested"},
        "Execution task must be pending_confirmation or changes_requested before confirmation",
    )

    task.status = "in_progress"
    task.updated_at = now_utc()
    case.status = EXECUTION_IN_PROGRESS_STATUS
    case.updated_at = now_utc()
    session.add(task)
    session.add(case)
    write_activity(
        session=session,
        action="workflow.execution_assignment_confirmed",
        case_id=case.id,
        actor_id=current_user.id,
        target_type="execution_task",
        target_id=str(task.id),
        metadata={"department": task.department, "checklist_row_id": task.checklist_row_id},
    )
    session.commit()
    session.refresh(case)
    return get_workflow_state(session=session, case=case)


def _start_leader_review_if_execution_complete(
    *,
    session: Session,
    case: PdEcrCase,
) -> None:
    tasks = _execution_tasks(session, case.id)
    if not tasks or any(task.status != "completed" for task in tasks):
        return
    existing_departments = {task.department for task in _leader_tasks(session, case.id)}
    departments = sorted({task.department for task in tasks})
    for department in departments:
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
        record_workflow_notification(
            session=session,
            case=case,
            recipient_email=leader_task.reviewer_email,
            notification_type="leader_review_request",
            department=department,
        )
    case.status = LEADER_REVIEW_STATUS
    case.updated_at = now_utc()
    session.add(case)
    write_activity(
        session=session,
        action="workflow.execution_leader_review_started",
        case_id=case.id,
        target_type="workflow",
        target_id=str(case.id),
        metadata={"departments": departments},
    )


def complete_execution_task(
    *,
    session: Session,
    task_id: uuid.UUID,
    execution_result: str,
    execution_note: str | None,
    evidence_note: str | None,
    current_user: User,
) -> dict[str, Any]:
    task = session.get(PdEcrExecutionTask, task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Execution task not found")
    _ensure_execution_task_assignee(task, current_user)
    case = session.get(PdEcrCase, task.case_id)
    if case is None:
        raise HTTPException(status_code=404, detail="PD-ECR case not found")
    _ensure_execution_task_status(
        task,
        {"in_progress"},
        "Execution task must be in_progress before completion",
    )

    task.status = "completed"
    task.execution_result = str(execution_result or "").strip()
    task.execution_note = execution_note
    task.evidence_note = evidence_note
    task.completed_by_id = current_user.id
    task.completed_by_name = _actor_name(current_user)
    task.completed_at = now_utc()
    task.updated_at = now_utc()
    session.add(task)
    write_activity(
        session=session,
        action="workflow.execution_task_completed",
        case_id=case.id,
        actor_id=current_user.id,
        target_type="execution_task",
        target_id=str(task.id),
        metadata={"department": task.department, "execution_result": task.execution_result},
    )
    _start_leader_review_if_execution_complete(session=session, case=case)
    session.commit()
    session.refresh(case)
    return get_workflow_state(session=session, case=case)


def request_execution_task_changes(
    *,
    session: Session,
    task_id: uuid.UUID,
    comment: str,
    current_user: User,
) -> dict[str, Any]:
    task = session.get(PdEcrExecutionTask, task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Execution task not found")
    _ensure_execution_task_reviewer(task, current_user)
    case = session.get(PdEcrCase, task.case_id)
    if case is None:
        raise HTTPException(status_code=404, detail="PD-ECR case not found")
    _ensure_execution_task_status(
        task,
        {"completed"},
        "Execution task must be completed before requesting changes",
    )

    task.status = "changes_requested"
    task.review_comment = comment
    task.updated_at = now_utc()
    case.status = CHANGES_REQUESTED_STATUS
    case.updated_at = now_utc()
    session.add(task)
    session.add(case)
    write_activity(
        session=session,
        action="workflow.execution_changes_requested",
        case_id=case.id,
        actor_id=current_user.id,
        target_type="execution_task",
        target_id=str(task.id),
        message=comment,
        metadata={"department": task.department},
    )
    session.commit()
    session.refresh(case)
    return get_workflow_state(session=session, case=case)


def submit_for_department_confirmation(
    *,
    session: Session,
    case: PdEcrCase,
    selected_departments: list[str],
    assignees: dict[str, dict[str, Any]] | None,
    current_user: User,
) -> dict[str, Any]:
    departments = [_normalize_department(item) for item in selected_departments]
    departments = list(dict.fromkeys(departments))
    if not departments:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="At least one affected department is required",
        )

    assignees = assignees or {}
    existing = {
        task.department: task
        for task in _department_tasks(session, case.id)
    }
    for department in departments:
        assignment = assignees.get(department) or {}
        email = str(assignment.get("assignee_email") or "").strip()
        if not email:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Missing assignee_email for department: {department}",
            )
        task = existing.get(department)
        if task is None:
            task = PdEcrDepartmentTask(case_id=case.id, department=department)
        task.status = "pending"
        task.assignee_id = _parse_uuid(assignment.get("assignee_id"))
        task.assignee_email = email
        task.assignee_name = assignment.get("assignee_name")
        task.impact_result = None
        task.impact_remark = None
        task.action_required = None
        task.confirmed_by_id = None
        task.confirmed_by_name = None
        task.confirmed_at = None
        task.updated_at = now_utc()
        session.add(task)
        record_workflow_notification(
            session=session,
            case=case,
            recipient_email=task.assignee_email,
            notification_type="department_confirmation_request",
            department=department,
        )

    case.status = DEPARTMENT_CONFIRMATION_STATUS
    case.updated_at = now_utc()
    session.add(case)
    write_activity(
        session=session,
        action="workflow.department_confirmation_started",
        case_id=case.id,
        actor_id=current_user.id,
        target_type="workflow",
        target_id=str(case.id),
        metadata={"departments": departments},
    )
    session.commit()
    session.refresh(case)
    return get_workflow_state(session=session, case=case)


def _ensure_department_task_actor(task: PdEcrDepartmentTask, user: User) -> None:
    if user.is_superuser or getattr(user, "pd_ecr_role", None) == "pd_ecr_manager":
        return
    if task.assignee_id and task.assignee_id == user.id:
        return
    if (
        getattr(user, "pd_ecr_role", None) == DEPARTMENT_LEADER_ROLE
        and getattr(user, "department", None) == task.department
    ):
        return
    raise HTTPException(status_code=403, detail="No permission for department task")


def _all_department_tasks_confirmed(tasks: list[PdEcrDepartmentTask]) -> bool:
    return bool(tasks) and all(task.status in DEPARTMENT_DONE_STATUSES for task in tasks)


def _start_leader_review_if_ready(
    *, session: Session, case: PdEcrCase
) -> None:
    tasks = _department_tasks(session, case.id)
    if not _all_department_tasks_confirmed(tasks):
        return
    existing_departments = {task.department for task in _leader_tasks(session, case.id)}
    for department_task in tasks:
        if department_task.department in existing_departments:
            continue
        leader = _find_leader_for_department(
            session=session, department=department_task.department
        )
        leader_task = PdEcrLeaderReviewTask(
            case_id=case.id,
            department=department_task.department,
            reviewer_id=leader.id if leader else None,
            reviewer_email=leader.email if leader else None,
            reviewer_name=_actor_name(leader) if leader else None,
            status="pending",
        )
        session.add(leader_task)
        record_workflow_notification(
            session=session,
            case=case,
            recipient_email=leader_task.reviewer_email,
            notification_type="leader_review_request",
            department=department_task.department,
        )
    case.status = LEADER_REVIEW_STATUS
    case.updated_at = now_utc()
    session.add(case)
    write_activity(
        session=session,
        action="workflow.leader_review_started",
        case_id=case.id,
        target_type="workflow",
        target_id=str(case.id),
        metadata={"departments": [task.department for task in tasks]},
    )


def confirm_department_task(
    *,
    session: Session,
    task_id: uuid.UUID,
    impact_result: str,
    impact_remark: str | None,
    action_required: str | None,
    current_user: User,
) -> dict[str, Any]:
    task = session.get(PdEcrDepartmentTask, task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Department task not found")
    _ensure_department_task_actor(task, current_user)
    case = session.get(PdEcrCase, task.case_id)
    if case is None:
        raise HTTPException(status_code=404, detail="PD-ECR case not found")

    task.status = "confirmed"
    task.impact_result = impact_result
    task.impact_remark = impact_remark
    task.action_required = action_required
    task.confirmed_by_id = current_user.id
    task.confirmed_by_name = _actor_name(current_user)
    task.confirmed_at = now_utc()
    task.updated_at = now_utc()
    session.add(task)
    write_activity(
        session=session,
        action="workflow.department_task_confirmed",
        case_id=case.id,
        actor_id=current_user.id,
        target_type="department_task",
        target_id=str(task.id),
        metadata={"department": task.department, "impact_result": impact_result},
    )
    _start_leader_review_if_ready(session=session, case=case)
    session.commit()
    session.refresh(case)
    return get_workflow_state(session=session, case=case)


def request_department_changes(
    *,
    session: Session,
    task_id: uuid.UUID,
    comment: str,
    current_user: User,
) -> dict[str, Any]:
    task = session.get(PdEcrDepartmentTask, task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Department task not found")
    _ensure_department_task_actor(task, current_user)
    case = session.get(PdEcrCase, task.case_id)
    if case is None:
        raise HTTPException(status_code=404, detail="PD-ECR case not found")
    task.status = "changes_requested"
    task.impact_remark = comment
    task.updated_at = now_utc()
    case.status = CHANGES_REQUESTED_STATUS
    case.updated_at = now_utc()
    session.add(task)
    session.add(case)
    write_activity(
        session=session,
        action="workflow.department_changes_requested",
        case_id=case.id,
        actor_id=current_user.id,
        target_type="department_task",
        target_id=str(task.id),
        message=comment,
        metadata={"department": task.department},
    )
    session.commit()
    session.refresh(case)
    return get_workflow_state(session=session, case=case)


def _ensure_leader_task_actor(task: PdEcrLeaderReviewTask, user: User) -> None:
    if user.is_superuser or getattr(user, "pd_ecr_role", None) == "pd_ecr_manager":
        return
    if task.reviewer_id and task.reviewer_id == user.id:
        return
    raise HTTPException(status_code=403, detail="No permission for leader review task")


def _all_leader_tasks_approved(tasks: list[PdEcrLeaderReviewTask]) -> bool:
    return bool(tasks) and all(task.status in LEADER_DONE_STATUSES for task in tasks)


def review_leader_task(
    *,
    session: Session,
    task_id: uuid.UUID,
    decision: str,
    review_comment: str | None,
    signature_name: str | None,
    current_user: User,
) -> dict[str, Any]:
    decision = str(decision or "").strip().lower()
    if decision not in {"approved", "rejected", "changes_requested"}:
        raise HTTPException(status_code=422, detail=f"Invalid review decision: {decision}")

    task = session.get(PdEcrLeaderReviewTask, task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Leader review task not found")
    _ensure_leader_task_actor(task, current_user)
    case = session.get(PdEcrCase, task.case_id)
    if case is None:
        raise HTTPException(status_code=404, detail="PD-ECR case not found")

    task.status = decision
    task.review_comment = review_comment
    task.signature_name = signature_name or _actor_name(current_user)
    task.reviewed_at = now_utc()
    task.updated_at = now_utc()
    session.add(task)

    notification_type = (
        "leader_review_approved" if decision == "approved" else "leader_review_rejected"
    )
    record_workflow_notification(
        session=session,
        case=case,
        recipient_email=case.initiator,
        notification_type=notification_type,
        department=task.department,
        comment=review_comment,
    )

    if decision in {"rejected", "changes_requested"}:
        case.status = CHANGES_REQUESTED_STATUS
    elif _all_leader_tasks_approved(_leader_tasks(session, case.id)):
        case.status = APPROVED_STATUS
    case.updated_at = now_utc()
    session.add(case)
    write_activity(
        session=session,
        action=f"workflow.leader_review_{decision}",
        case_id=case.id,
        actor_id=current_user.id,
        target_type="leader_review_task",
        target_id=str(task.id),
        message=review_comment,
        metadata={"department": task.department},
    )
    session.commit()
    session.refresh(case)
    return get_workflow_state(session=session, case=case)


def create_approval_task(
    *,
    session: Session,
    case: Any,
    approver_id: uuid.UUID | None = None,
    approver_email: str | None = None,
    approver_name: str | None = None,
    commit: bool = True,
) -> Any:
    """Create a manager approval task for a submitted case."""
    from app.models import PdEcrApprovalTask
    task = PdEcrApprovalTask(
        case_id=case.id,
        approver_id=approver_id,
        approver_email=approver_email,
        approver_name=approver_name,
        status="pending",
    )
    session.add(task)
    if commit:
        session.commit()
        session.refresh(task)
    return task


def approve_case(
    *,
    session: Session,
    case: Any,
    approval_task: Any,
    current_user: Any,
    module: Any | None = None,
    commit: bool = True,
) -> Any:
    """Approve a case — transition to generated and trigger AI."""
    from app.models import get_datetime_utc

    now = get_datetime_utc()

    # Update approval task
    approval_task.status = "approved"
    approval_task.approved_at = now
    approval_task.updated_at = now
    session.add(approval_task)

    if module is not None:
        content = dict(getattr(module, "content_json", {}) or {})
        content["leaderConfirmed"] = True
        content["leader_confirmed"] = True
        content["leader_confirmed_by"] = _actor_name(current_user)
        content["leader_confirmed_at"] = now.isoformat()
        module.content_json = content
        module.updated_by_id = current_user.id
        module.updated_at = now
        session.add(module)

    # Update case status
    case.status = "generated"
    case.updated_at = now
    session.add(case)

    if commit:
        session.commit()
        session.refresh(case)
    return case


def reject_case(
    *,
    session: Session,
    case: Any,
    approval_task: Any,
    rejection_reason: str | None = None,
    commit: bool = True,
) -> Any:
    """Reject a case — send back to draft."""
    from app.models import get_datetime_utc

    now = get_datetime_utc()

    approval_task.status = "rejected"
    approval_task.rejection_reason = rejection_reason
    approval_task.updated_at = now
    session.add(approval_task)

    case.status = "draft"
    case.updated_at = now
    session.add(case)

    if commit:
        session.commit()
        session.refresh(case)
    return case
