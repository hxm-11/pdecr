from __future__ import annotations

import uuid
from datetime import datetime, timezone
import json
from typing import Any

from app.core.config import settings
from app.integrations.flowable.client import FlowableClient, FlowableClientError
from app.models import PdEcrApprovalTask, PdEcrCase, User


class FlowableIntegrationError(RuntimeError):
    """Raised when Flowable orchestration cannot be completed safely."""


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def flowable_enabled() -> bool:
    return settings.FLOWABLE_ENABLED


def _actor_name(user: User) -> str:
    return (
        getattr(user, "display_name", None)
        or getattr(user, "full_name", None)
        or getattr(user, "email", "")
        or str(user.id)
    )


def _build_case_variables(
    *,
    case: PdEcrCase,
    approver_id: uuid.UUID | None,
    approver_email: str | None,
    approver_name: str | None,
    form_data: dict[str, Any] | None,
) -> dict[str, Any]:
    return {
        "caseId": str(case.id),
        "caseNo": case.case_no,
        "title": case.title,
        "initiator": case.initiator or "",
        "customerProject": case.customer_project or "",
        "productNo": case.product_no or "",
        "partNo": case.part_no or "",
        "approverId": str(approver_id) if approver_id else "",
        "approverEmail": approver_email or "",
        "approverName": approver_name or "",
        "formDataJson": json.dumps(form_data or {}, ensure_ascii=False, sort_keys=True),
    }


def _require_process_definition_key() -> str:
    process_definition_key = settings.FLOWABLE_PROCESS_DEFINITION_KEY.strip()
    if not process_definition_key:
        raise FlowableIntegrationError(
            "FLOWABLE_PROCESS_DEFINITION_KEY must be configured when Flowable is enabled"
        )
    return process_definition_key


def start_manager_approval_process(
    *,
    case: PdEcrCase,
    approver_id: uuid.UUID | None,
    approver_email: str | None,
    approver_name: str | None,
    form_data: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if not flowable_enabled():
        return {}

    client = FlowableClient()
    process_definition_key = _require_process_definition_key()
    business_key = case.flowable_business_key or str(case.id)

    try:
        process = client.start_process_instance(
            process_definition_key=process_definition_key,
            business_key=business_key,
            variables=_build_case_variables(
                case=case,
                approver_id=approver_id,
                approver_email=approver_email,
                approver_name=approver_name,
                form_data=form_data,
            ),
        )
    except FlowableClientError as exc:
        raise FlowableIntegrationError(str(exc)) from exc

    process_instance_id = str(process.get("id") or "").strip()
    if not process_instance_id:
        raise FlowableIntegrationError(
            "Flowable did not return a process instance id for the approval process"
        )

    case.flowable_process_instance_id = process_instance_id
    case.flowable_process_definition_key = process_definition_key
    case.flowable_business_key = business_key
    case.flowable_status = str(process.get("businessStatus") or "running")
    case.flowable_last_synced_at = now_utc()

    try:
        tasks = client.get_tasks_for_process_instance(process_instance_id)
    except FlowableClientError as exc:
        raise FlowableIntegrationError(str(exc)) from exc

    return {
        "process": process,
        "task": tasks[0] if tasks else None,
    }


def sync_approval_task_from_flowable(
    *,
    approval_task: PdEcrApprovalTask,
    flowable_task: dict[str, Any] | None,
) -> None:
    if not flowable_task:
        return
    approval_task.flowable_task_id = str(flowable_task.get("id") or "") or None
    approval_task.flowable_task_definition_key = (
        str(flowable_task.get("taskDefinitionKey") or "") or None
    )


def complete_manager_approval_task(
    *,
    case: PdEcrCase,
    approval_task: PdEcrApprovalTask,
    current_user: User,
    approved: bool,
    rejection_reason: str | None = None,
) -> None:
    if not flowable_enabled() or not case.flowable_process_instance_id:
        return

    client = FlowableClient()
    task_id = approval_task.flowable_task_id

    if not task_id:
        try:
            tasks = client.get_tasks_for_process_instance(case.flowable_process_instance_id)
        except FlowableClientError as exc:
            raise FlowableIntegrationError(str(exc)) from exc
        task = tasks[0] if tasks else None
        if task is None:
            raise FlowableIntegrationError(
                "No active Flowable approval task was found for this PD-ECR case"
            )
        sync_approval_task_from_flowable(
            approval_task=approval_task,
            flowable_task=task,
        )
        task_id = approval_task.flowable_task_id

    if not task_id:
        raise FlowableIntegrationError("Flowable approval task id is missing")

    variables = {
        "approved": approved,
        "approvedBy": _actor_name(current_user),
        "approvedByEmail": current_user.email,
        "rejectionReason": rejection_reason or "",
    }

    try:
        client.complete_task(task_id=task_id, variables=variables)
    except FlowableClientError as exc:
        raise FlowableIntegrationError(str(exc)) from exc

    case.flowable_status = "approved" if approved else "rejected"
    case.flowable_last_synced_at = now_utc()
