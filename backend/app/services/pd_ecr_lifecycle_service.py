from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import HTTPException, status
from sqlmodel import Session

from app.models import PdEcrCase, User
from app.services.pd_ecr_audit_service import write_activity


LIFECYCLE_DRAFT = "draft"
LIFECYCLE_SUBMITTED = "submitted"
LIFECYCLE_APPLICANT_CONFIRMING = "applicant_confirming"
LIFECYCLE_LEADER_REVIEWING = "leader_reviewing"
LIFECYCLE_TASK_EXECUTING = "task_executing"
LIFECYCLE_RESULT_CONFIRMING = "result_confirming"
LIFECYCLE_CLOSED = "closed"
LIFECYCLE_CANCELLED = "cancelled"
LIFECYCLE_EXPIRED = "expired"
LIFECYCLE_REJECTED = "rejected"

PD_ECR_LIFECYCLE_STATUSES = {
    LIFECYCLE_DRAFT,
    LIFECYCLE_SUBMITTED,
    LIFECYCLE_APPLICANT_CONFIRMING,
    LIFECYCLE_LEADER_REVIEWING,
    LIFECYCLE_TASK_EXECUTING,
    LIFECYCLE_RESULT_CONFIRMING,
    LIFECYCLE_CLOSED,
    LIFECYCLE_CANCELLED,
    LIFECYCLE_EXPIRED,
    LIFECYCLE_REJECTED,
}

PD_ECR_LIFECYCLE_TRANSITIONS: dict[str, set[str]] = {
    LIFECYCLE_DRAFT: {LIFECYCLE_SUBMITTED, LIFECYCLE_CANCELLED},
    LIFECYCLE_REJECTED: {LIFECYCLE_DRAFT, LIFECYCLE_SUBMITTED, LIFECYCLE_CANCELLED},
    LIFECYCLE_SUBMITTED: {
        LIFECYCLE_APPLICANT_CONFIRMING,
        LIFECYCLE_LEADER_REVIEWING,
        LIFECYCLE_TASK_EXECUTING,
        LIFECYCLE_REJECTED,
        LIFECYCLE_CANCELLED,
    },
    LIFECYCLE_APPLICANT_CONFIRMING: {
        LIFECYCLE_LEADER_REVIEWING,
        LIFECYCLE_REJECTED,
        LIFECYCLE_CANCELLED,
    },
    LIFECYCLE_LEADER_REVIEWING: {
        LIFECYCLE_TASK_EXECUTING,
        LIFECYCLE_REJECTED,
        LIFECYCLE_CANCELLED,
    },
    LIFECYCLE_TASK_EXECUTING: {
        LIFECYCLE_RESULT_CONFIRMING,
        LIFECYCLE_REJECTED,
        LIFECYCLE_EXPIRED,
        LIFECYCLE_CANCELLED,
    },
    LIFECYCLE_RESULT_CONFIRMING: {
        LIFECYCLE_CLOSED,
        LIFECYCLE_TASK_EXECUTING,
        LIFECYCLE_REJECTED,
        LIFECYCLE_CANCELLED,
    },
    LIFECYCLE_CLOSED: set(),
    LIFECYCLE_CANCELLED: set(),
    LIFECYCLE_EXPIRED: {LIFECYCLE_TASK_EXECUTING, LIFECYCLE_CANCELLED},
}

LEGACY_STATUS_ALIASES = {
    "generated": LIFECYCLE_DRAFT,
    "approved": LIFECYCLE_TASK_EXECUTING,
    "implementation": LIFECYCLE_TASK_EXECUTING,
    "execution_assignment": LIFECYCLE_TASK_EXECUTING,
    "assignee_confirmation": LIFECYCLE_TASK_EXECUTING,
    "execution_in_progress": LIFECYCLE_TASK_EXECUTING,
    "in_review": LIFECYCLE_LEADER_REVIEWING,
    "leader_review": LIFECYCLE_LEADER_REVIEWING,
    "department_confirmation": LIFECYCLE_APPLICANT_CONFIRMING,
    "department_alignment": LIFECYCLE_APPLICANT_CONFIRMING,
    "changes_requested": LIFECYCLE_REJECTED,
}

LIFECYCLE_LABELS = {
    LIFECYCLE_DRAFT: "Draft",
    LIFECYCLE_SUBMITTED: "Submitted",
    LIFECYCLE_APPLICANT_CONFIRMING: "Applicant Confirming",
    LIFECYCLE_LEADER_REVIEWING: "Leader Reviewing",
    LIFECYCLE_TASK_EXECUTING: "Task Executing",
    LIFECYCLE_RESULT_CONFIRMING: "Result Confirming",
    LIFECYCLE_CLOSED: "Closed",
    LIFECYCLE_CANCELLED: "Cancelled",
    LIFECYCLE_EXPIRED: "Expired",
    LIFECYCLE_REJECTED: "Rejected",
}


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def normalize_lifecycle_status(status_value: str | None) -> str:
    value = str(status_value or "").strip()
    if value in PD_ECR_LIFECYCLE_STATUSES:
        return value
    if value in LEGACY_STATUS_ALIASES:
        return LEGACY_STATUS_ALIASES[value]
    return value


def lifecycle_payload(status_value: str | None) -> dict[str, Any]:
    lifecycle_status = normalize_lifecycle_status(status_value)
    return {
        "lifecycle_status": lifecycle_status,
        "lifecycle_label": LIFECYCLE_LABELS.get(lifecycle_status, lifecycle_status),
        "raw_status": status_value,
        "is_legacy_status": lifecycle_status != status_value,
    }


def allowed_next_statuses(status_value: str | None) -> list[str]:
    lifecycle_status = normalize_lifecycle_status(status_value)
    return sorted(PD_ECR_LIFECYCLE_TRANSITIONS.get(lifecycle_status, set()))


def ensure_lifecycle_transition_allowed(
    *,
    current_status: str,
    next_status: str,
    current_user: User,
) -> None:
    current = normalize_lifecycle_status(current_status)
    target = normalize_lifecycle_status(next_status)
    if target not in PD_ECR_LIFECYCLE_STATUSES:
        raise HTTPException(status_code=422, detail=f"Invalid lifecycle status: {next_status}")
    allowed = PD_ECR_LIFECYCLE_TRANSITIONS.get(current, set())
    if target not in allowed and not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Cannot transition from {current} to {target}",
        )


def transition_case_lifecycle(
    *,
    session: Session,
    case: PdEcrCase,
    next_status: str,
    current_user: User,
    action: str = "case.lifecycle_transitioned",
    message: str | None = None,
    metadata: dict[str, Any] | None = None,
    commit: bool = True,
) -> PdEcrCase:
    previous_raw = case.status
    previous = normalize_lifecycle_status(previous_raw)
    target = normalize_lifecycle_status(next_status)
    ensure_lifecycle_transition_allowed(
        current_status=previous,
        next_status=target,
        current_user=current_user,
    )
    case.status = target
    case.updated_at = now_utc()
    if target == LIFECYCLE_CLOSED and case.closed_at is None:
        case.closed_at = now_utc()
    session.add(case)
    write_activity(
        session=session,
        action=action,
        case_id=case.id,
        actor_id=current_user.id,
        target_type="case",
        target_id=str(case.id),
        message=message or f"{previous} -> {target}",
        metadata={
            "from": previous,
            "from_raw": previous_raw,
            "to": target,
            **(metadata or {}),
        },
    )
    if commit:
        session.commit()
        session.refresh(case)
    return case


def lifecycle_contract() -> dict[str, Any]:
    return {
        "statuses": [
            {
                "status": status_value,
                "label": LIFECYCLE_LABELS[status_value],
                "next": sorted(PD_ECR_LIFECYCLE_TRANSITIONS.get(status_value, set())),
            }
            for status_value in [
                LIFECYCLE_DRAFT,
                LIFECYCLE_SUBMITTED,
                LIFECYCLE_APPLICANT_CONFIRMING,
                LIFECYCLE_LEADER_REVIEWING,
                LIFECYCLE_TASK_EXECUTING,
                LIFECYCLE_RESULT_CONFIRMING,
                LIFECYCLE_CLOSED,
                LIFECYCLE_CANCELLED,
                LIFECYCLE_EXPIRED,
                LIFECYCLE_REJECTED,
            ]
        ],
        "legacy_aliases": dict(LEGACY_STATUS_ALIASES),
    }
