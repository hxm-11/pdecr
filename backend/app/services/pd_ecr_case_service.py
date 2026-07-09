import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, col, delete, select

from app.models import (
    PD_ECR_DEFAULT_MODULES,
    PD_ECR_STATUSES,
    PdEcrActivity,
    PdEcrAttachment,
    PdEcrApprovalTask,
    PdEcrCase,
    PdEcrCaseCreate,
    PdEcrCaseUpdate,
    PdEcrCollaborationSession,
    PdEcrComment,
    PdEcrCommentCreate,
    PdEcrDepartmentTask,
    PdEcrDepartmentVisibility,
    PdEcrExecutionTask,
    PdEcrLeaderReviewTask,
    PdEcrModule,
    PdEcrModuleUpdate,
    PdEcrNotification,
    PdEcrTask,
    PdEcrTaskCreate,
    PdEcrVersion,
    User,
)
from app.services.pd_ecr_audit_service import write_activity
from app.services.pd_ecr_lifecycle_service import (
    LIFECYCLE_APPLICANT_CONFIRMING,
    LIFECYCLE_CANCELLED,
    LIFECYCLE_CLOSED,
    LIFECYCLE_DRAFT,
    LIFECYCLE_EXPIRED,
    LIFECYCLE_LEADER_REVIEWING,
    LIFECYCLE_REJECTED,
    LIFECYCLE_RESULT_CONFIRMING,
    LIFECYCLE_SUBMITTED,
    LIFECYCLE_TASK_EXECUTING,
    allowed_next_statuses,
    lifecycle_payload,
    transition_case_lifecycle,
)


WRITE_TRANSITIONS: dict[str, set[str]] = {
    LIFECYCLE_DRAFT: {LIFECYCLE_SUBMITTED, LIFECYCLE_CANCELLED},
    LIFECYCLE_SUBMITTED: {
        LIFECYCLE_APPLICANT_CONFIRMING,
        LIFECYCLE_LEADER_REVIEWING,
        LIFECYCLE_TASK_EXECUTING,
        LIFECYCLE_REJECTED,
        LIFECYCLE_CANCELLED,
    },
    LIFECYCLE_REJECTED: {LIFECYCLE_DRAFT, LIFECYCLE_SUBMITTED, LIFECYCLE_CANCELLED},
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
    LIFECYCLE_EXPIRED: {LIFECYCLE_TASK_EXECUTING, LIFECYCLE_CANCELLED},
    LIFECYCLE_CLOSED: set(),
    LIFECYCLE_CANCELLED: set(),
    # Backward-compatible legacy transitions.
    "in_review": {"approved", "changes_requested", LIFECYCLE_LEADER_REVIEWING, LIFECYCLE_REJECTED},
    "changes_requested": {LIFECYCLE_SUBMITTED, LIFECYCLE_CANCELLED},
    "approved": {LIFECYCLE_TASK_EXECUTING, LIFECYCLE_CLOSED},
    "implementation": {LIFECYCLE_CLOSED, LIFECYCLE_REJECTED},
}

MODULE_MANAGEMENT_FIELDS = {
    "assignee_id",
    "assignee_email",
    "assignee_name",
    "department",
    "due_date",
    "reminder_policy",
    "last_reminded_at",
}

PROTECTED_DELETE_STATUSES = {"approved", "implementation", "closed"}


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def ensure_write_access(case: PdEcrCase, user: User) -> None:
    ensure_case_mutable(case)
    if user.is_superuser:
        return
    if case.owner_id == user.id or case.created_by_id == user.id:
        return
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="No write permission for this PD-ECR case",
    )


# ── Department-aware permission system ────────────────────────────────────
#
# Permission model:
#   can_view_case        → any authenticated user (everyone sees every case)
#   can_edit_module       → superuser / pd_ecr_manager / dept leader for
#                           responsible modules / explicit module assignee
#   can_assign_module     → superuser / pd_ecr_manager / dept leader for
#                           responsible modules / case owner
#   can_manage_case       → superuser / pd_ecr_manager / case owner /
#                           dept leader with modules in this case
#
# Roles (User.pd_ecr_role):
#   "department_leader"  — manages own department's modules
#   "department_member"  — only edits explicitly assigned modules
#   "pd_ecr_manager"     — cross-department, all permissions
#   "reviewer"           — read + review permission
# ──────────────────────────────────────────────────────────────────────────

from app.services.pd_ecr_departments import (
    DEPARTMENT_LEADER_ROLE,
    MODULE_DEPARTMENT_MAP,
    REVIEW_ROLE,
    Department,
    get_module_departments,
    is_cross_dept_manager,
    is_department_leader,
    is_department_member,
    module_is_responsible_for,
    user_can_lead_module,
    user_department,
    user_is_assigned_to_module,
)

MANAGER_ROLES: set[str] = {"pd_ecr_manager"}  # kept for backward compat
MODULE_EDIT_ROLES: set[str] = {"pd_ecr_manager", "case_owner", "module_owner"}  # kept for backward compat
REVIEW_ROLES: set[str] = {"pd_ecr_manager", "reviewer"}

# Role that grants review permission in addition to dept leaders / managers
# (REVIEW_ROLE is imported from pd_ecr_departments above)


def user_pd_ecr_role(user: User) -> str:
    return str(getattr(user, "pd_ecr_role", "") or "").strip()


def ensure_case_mutable(case: PdEcrCase) -> None:
    if not case.is_historical:
        return
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Historical imported PD-ECR cases are read-only",
    )


# ── Core permission functions (rewritten with department awareness) ──────


def can_view_case(case: PdEcrCase, user: User | None) -> bool:
    """Anyone authenticated can view any case (cross-department visibility)."""
    return user is not None


def _case_has_modules_for_department(
    session: Session, case: PdEcrCase, department: str
) -> bool:
    """Check whether a case contains modules that belong to a department."""
    try:
        dept = Department(department)
    except ValueError:
        return False
    responsible_module_ids = [m for m, depts in MODULE_DEPARTMENT_MAP.items() if dept in depts]
    if not responsible_module_ids:
        return False
    count = session.exec(
        select(PdEcrModule).where(
            PdEcrModule.case_id == case.id,
            PdEcrModule.module_id.in_(responsible_module_ids),  # type: ignore[attr-defined]
        )
    ).first()
    return count is not None


def can_manage_case(
    case: PdEcrCase,
    user: User,
    *,
    session: Session | None = None,
) -> bool:
    """Can the user manage (edit metadata, assign modules, close) this case?

    True for: superuser, pd_ecr_manager, case owner/creator, OR
    department leader whose department owns at least one module in the case.
    """
    if case.is_historical:
        return False
    if user.is_superuser:
        return True
    if is_cross_dept_manager(user):
        return True
    if case.owner_id == user.id or case.created_by_id == user.id:
        return True

    # Department leader: can manage if case has modules in their department
    if is_department_leader(user) and session is not None:
        dept = user_department(user)
        if dept and _case_has_modules_for_department(session, case, dept):
            return True

    return False


def can_edit_module(
    case: PdEcrCase,
    module: PdEcrModule | None,
    user: User,
) -> bool:
    """Can the user edit the content of a specific module?

    True for:
    - superuser / pd_ecr_manager → always
    - department leader → if their department is responsible for this module
    - department member → if they are the explicit assignee of this module
    - case owner → can edit any module (backward compat)
    """
    if case.is_historical:
        return False
    if user.is_superuser:
        return True
    if is_cross_dept_manager(user):
        return True
    if case.owner_id == user.id or case.created_by_id == user.id:
        return True

    if module is None:
        return False

    if user_pd_ecr_role(user) == "module_owner" and user_is_assigned_to_module(user, module):
        return True

    # Department leader: edit modules their department owns
    if is_department_leader(user) and user_can_lead_module(user, module.module_id):
        return True

    # Department member: only if explicitly assigned AND module belongs to their dept
    if is_department_member(user) and user_is_assigned_to_module(user, module):
        dept = user_department(user)
        try:
            department = Department(dept)
            if module_is_responsible_for(module.module_id, department):
                return True
        except ValueError:
            pass

    return False


def can_assign_module(
    case: PdEcrCase,
    module: PdEcrModule | None,
    user: User,
) -> bool:
    """Can the user assign this module to someone?

    True for:
    - superuser / pd_ecr_manager → always
    - case owner → always
    - department leader → if their department is responsible for this module
      (can only assign to members of the same department)
    """
    if case.is_historical:
        return False
    if user.is_superuser:
        return True
    if is_cross_dept_manager(user):
        return True
    if case.owner_id == user.id or case.created_by_id == user.id:
        return True

    if module is None:
        return False

    if is_department_leader(user) and user_can_lead_module(user, module.module_id):
        return True

    return False


# ── Guard functions ──────────────────────────────────────────────────────


def ensure_case_manage_access(
    case: PdEcrCase,
    user: User,
    *,
    session: Session | None = None,
) -> None:
    if can_manage_case(case, user, session=session):
        return
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="No manage permission for this PD-ECR case",
    )


def ensure_module_edit_access(
    case: PdEcrCase, module: PdEcrModule | None, user: User
) -> None:
    ensure_case_mutable(case)
    if can_edit_module(case, module, user):
        return
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="No edit permission for this PD-ECR module",
    )


# ── Permission flags (returned to frontend per module) ───────────────────


def module_permission_flags(
    case: PdEcrCase, module: PdEcrModule | None, user: User | None,
    *,
    session: Session | None = None,
) -> dict[str, bool]:
    """Return the 6 permission flags for a module.

    These flags control which UI buttons are visible in the frontend.
    """
    if user is None:
        return {
            "can_edit": False,
            "can_assign": False,
            "can_regenerate": False,
            "can_send_reminder": False,
            "can_review": False,
            "can_close": False,
        }

    can_manage = can_manage_case(case, user, session=session)
    can_edit = can_edit_module(case, module, user)
    can_assign = can_assign_module(case, module, user)
    role = user_pd_ecr_role(user)

    return {
        "can_edit": can_edit,
        "can_assign": can_assign,
        "can_regenerate": can_edit,  # same as edit — you need edit rights to regenerate
        "can_send_reminder": can_assign,  # same as assign — managers/leaders send reminders
        "can_review": can_manage or can_assign or role in REVIEW_ROLES,
        "can_close": can_manage,
    }


# ── Helpers for the frontend ─────────────────────────────────────────────


def get_assignable_users_for_module(
    *,
    session: Session,
    module_id: str,
    user: User,
) -> list[User]:
    """Return users that the current user can assign to a module.

    Department leaders can only see members of their own department.
    pd_ecr_manager and superuser can see everyone.
    Case owners can see everyone (backward compat).
    """
    if user.is_superuser or is_cross_dept_manager(user):
        return list(session.exec(select(User).where(User.is_active == True)).all())

    if is_department_leader(user):
        dept = user_department(user)
        if dept and user_can_lead_module(user, module_id):
            return list(
                session.exec(
                    select(User).where(
                        User.is_active == True,
                        User.department == dept,
                    )
                ).all()
            )

    return []


def ensure_default_modules(
    *, session: Session, case: PdEcrCase, actor_id: uuid.UUID | None = None
) -> None:
    existing = session.exec(
        select(PdEcrModule.module_id).where(PdEcrModule.case_id == case.id)
    ).all()
    existing_ids = set(existing)
    for module_id, title in PD_ECR_DEFAULT_MODULES:
        if module_id in existing_ids:
            continue
        session.add(
            PdEcrModule(
                case_id=case.id,
                module_id=module_id,
                title=title,
                content_json={},
                content_md="",
                source_cases=[],
                source_files=[],
                updated_by_id=actor_id,
            )
        )


def create_case(
    *, session: Session, case_in: PdEcrCaseCreate, current_user: User
) -> PdEcrCase:
    case = PdEcrCase.model_validate(
        case_in,
        update={
            "created_by_id": current_user.id,
            "owner_id": case_in.model_dump().get("owner_id") or current_user.id,
            "updated_at": now_utc(),
        },
    )
    if case.status not in PD_ECR_STATUSES:
        raise HTTPException(status_code=422, detail=f"Invalid status: {case.status}")

    session.add(case)
    try:
        session.flush()
    except IntegrityError:
        session.rollback()
        raise HTTPException(
            status_code=409,
            detail=f"PD-ECR case already exists: {case.case_no}",
        )

    ensure_default_modules(session=session, case=case, actor_id=current_user.id)
    for raw_module in case_in.modules or []:
        module_id = str(raw_module.get("module_id") or raw_module.get("id") or "").strip()
        if not module_id:
            continue
        module = session.exec(
            select(PdEcrModule).where(
                PdEcrModule.case_id == case.id,
                PdEcrModule.module_id == module_id,
            )
        ).first()
        if not module:
            module = PdEcrModule(case_id=case.id, module_id=module_id)
            session.add(module)
        module.title = str(raw_module.get("title") or module.title or module_id)
        module.content_json = raw_module.get("content_json") or raw_module.get("data") or {}
        module.content_md = str(raw_module.get("content_md") or raw_module.get("content") or "")
        module.source_cases = list(raw_module.get("source_cases") or [])
        module.source_files = list(raw_module.get("source_files") or [])
        module.needs_human_input = bool(raw_module.get("needs_human_input") or False)
        module.updated_by_id = current_user.id

    write_activity(
        session=session,
        action="case.created",
        case_id=case.id,
        actor_id=current_user.id,
        target_id=str(case.id),
        message=f"Created PD-ECR {case.case_no}",
    )
    session.commit()
    session.refresh(case)
    return case


def get_case_or_404(*, session: Session, case_id: str) -> PdEcrCase:
    case: PdEcrCase | None = None
    try:
        case = session.get(PdEcrCase, uuid.UUID(case_id))
    except ValueError:
        case = None

    if case is None:
        case = session.exec(
            select(PdEcrCase).where(
                (PdEcrCase.case_no == case_id) | (PdEcrCase.dc_no == case_id)
            )
        ).first()

    if case is None:
        raise HTTPException(status_code=404, detail="PD-ECR case not found")
    return case


def list_cases(
    *,
    session: Session,
    status_filter: str | None = None,
    query: str | None = None,
    skip: int = 0,
    limit: int = 100,
) -> list[PdEcrCase]:
    statement = select(PdEcrCase)
    if status_filter:
        statement = statement.where(PdEcrCase.status == status_filter)
    if query:
        pattern = f"%{query}%"
        statement = statement.where(
            col(PdEcrCase.case_no).ilike(pattern)
            | col(PdEcrCase.title).ilike(pattern)
            | col(PdEcrCase.customer_project).ilike(pattern)
            | col(PdEcrCase.product_no).ilike(pattern)
            | col(PdEcrCase.part_no).ilike(pattern)
        )
    return list(
        session.exec(
            statement.order_by(PdEcrCase.updated_at.desc()).offset(skip).limit(limit)
        ).all()
    )


def update_case(
    *,
    session: Session,
    case: PdEcrCase,
    case_in: PdEcrCaseUpdate,
    current_user: User,
) -> PdEcrCase:
    ensure_write_access(case, current_user)
    update_data = case_in.model_dump(exclude_unset=True)
    if "status" in update_data and update_data["status"] not in PD_ECR_STATUSES:
        raise HTTPException(status_code=422, detail=f"Invalid status: {update_data['status']}")
    previous = serialize_case(case)
    case.sqlmodel_update(update_data)
    case.updated_at = now_utc()
    if case.status == "closed" and case.closed_at is None:
        case.closed_at = now_utc()
    session.add(case)
    write_version(
        session=session,
        case=case,
        entity_type="case",
        entity_id=str(case.id),
        actor_id=current_user.id,
        snapshot=previous,
        diff_metadata={"updated_fields": sorted(update_data.keys())},
    )
    write_activity(
        session=session,
        action="case.updated",
        case_id=case.id,
        actor_id=current_user.id,
        target_id=str(case.id),
        metadata={"updated_fields": sorted(update_data.keys())},
    )
    session.commit()
    session.refresh(case)
    return case


def delete_case(
    *,
    session: Session,
    case: PdEcrCase,
    current_user: User,
) -> dict[str, str]:
    ensure_case_manage_access(case, current_user, session=session)
    if case.status in PROTECTED_DELETE_STATUSES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                "Approved, implementation, and closed PD-ECR cases cannot be deleted. "
                "Cancel or archive them instead."
            ),
        )

    deleted = {"id": str(case.id), "case_no": case.case_no}
    for model in (
        PdEcrCollaborationSession,
        PdEcrNotification,
        PdEcrActivity,
        PdEcrVersion,
        PdEcrAttachment,
        PdEcrComment,
        PdEcrLeaderReviewTask,
        PdEcrApprovalTask,
        PdEcrExecutionTask,
        PdEcrDepartmentVisibility,
        PdEcrDepartmentTask,
        PdEcrTask,
        PdEcrModule,
    ):
        session.exec(delete(model).where(model.case_id == case.id))  # type: ignore[attr-defined]

    session.delete(case)
    session.commit()
    return deleted


def transition_case(
    *, session: Session, case: PdEcrCase, next_status: str, current_user: User
) -> PdEcrCase:
    ensure_write_access(case, current_user)
    return transition_case_lifecycle(
        session=session,
        case=case,
        next_status=next_status,
        current_user=current_user,
        action="case.transitioned",
    )


def list_modules(*, session: Session, case_id: uuid.UUID) -> list[PdEcrModule]:
    return list(
        session.exec(
            select(PdEcrModule)
            .where(PdEcrModule.case_id == case_id)
            .order_by(PdEcrModule.module_id)
        ).all()
    )


def update_module(
    *,
    session: Session,
    case: PdEcrCase,
    module_id: str,
    module_in: PdEcrModuleUpdate,
    current_user: User,
) -> PdEcrModule:
    ensure_case_mutable(case)
    module = session.exec(
        select(PdEcrModule).where(
            PdEcrModule.case_id == case.id,
            PdEcrModule.module_id == module_id,
        )
    ).first()
    if module is None:
        module = PdEcrModule(case_id=case.id, module_id=module_id, title=module_id)
        session.add(module)
        session.flush()
    ensure_module_edit_access(case, module, current_user)
    update_data = module_in.model_dump(exclude_unset=True)
    update_data.pop("expected_version", None)
    management_fields = MODULE_MANAGEMENT_FIELDS.intersection(update_data)
    if management_fields and not can_manage_case(case, current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No manage permission for PD-ECR module assignment or reminders",
        )
    if (
        module_in.expected_version is not None
        and module_in.expected_version != module.version
    ):
        raise HTTPException(
            status_code=409,
            detail={
                "message": "Module version conflict",
                "current_version": module.version,
            },
        )

    previous_snapshot = serialize_module(module)
    module.sqlmodel_update(update_data)
    module.version += 1
    module.updated_at = now_utc()
    module.updated_by_id = current_user.id
    session.add(module)

    write_version(
        session=session,
        case=case,
        entity_type="module",
        entity_id=str(module.id),
        actor_id=current_user.id,
        snapshot=previous_snapshot,
        diff_metadata={
            "module_id": module.module_id,
            "updated_fields": sorted(update_data.keys()),
            "new_version": module.version,
        },
    )
    write_activity(
        session=session,
        action="module.updated",
        case_id=case.id,
        actor_id=current_user.id,
        target_type="module",
        target_id=module.module_id,
        metadata={"version": module.version, "updated_fields": sorted(update_data.keys())},
    )
    session.commit()
    session.refresh(module)
    return module


def assign_module(
    *,
    session: Session,
    case: PdEcrCase,
    module_id: str,
    assignee_id: uuid.UUID | None,
    assignee_email: str | None,
    assignee_name: str | None,
    department: str | None,
    due_date: datetime | None,
    reminder_policy: dict[str, Any] | None,
    current_user: User,
) -> PdEcrModule:
    ensure_case_manage_access(case, current_user)
    module = session.exec(
        select(PdEcrModule).where(
            PdEcrModule.case_id == case.id,
            PdEcrModule.module_id == module_id,
        )
    ).first()
    if module is None:
        raise HTTPException(status_code=404, detail="PD-ECR module not found")

    previous_snapshot = serialize_module(module)
    module.assignee_id = assignee_id
    module.assignee_email = assignee_email
    module.assignee_name = assignee_name
    module.department = department
    module.due_date = due_date
    module.reminder_policy = reminder_policy or {}
    module.updated_at = now_utc()
    module.updated_by_id = current_user.id
    session.add(module)

    write_version(
        session=session,
        case=case,
        entity_type="module",
        entity_id=str(module.id),
        actor_id=current_user.id,
        snapshot=previous_snapshot,
        diff_metadata={
            "module_id": module.module_id,
            "updated_fields": [
                "assignee_id",
                "assignee_email",
                "assignee_name",
                "department",
                "due_date",
                "reminder_policy",
            ],
        },
    )
    write_activity(
        session=session,
        action="module.assigned",
        case_id=case.id,
        actor_id=current_user.id,
        target_type="module",
        target_id=module.module_id,
        metadata={
            "assignee_id": str(assignee_id) if assignee_id else None,
            "assignee_email": assignee_email,
            "department": department,
        },
    )
    session.commit()
    session.refresh(module)
    return module


def create_task(
    *, session: Session, case: PdEcrCase, task_in: PdEcrTaskCreate, current_user: User
) -> PdEcrTask:
    ensure_write_access(case, current_user)
    task = PdEcrTask.model_validate(
        task_in,
        update={"case_id": case.id, "created_by_id": current_user.id},
    )
    session.add(task)
    write_activity(
        session=session,
        action="task.created",
        case_id=case.id,
        actor_id=current_user.id,
        target_type="task",
        metadata={"title": task.title, "assignee_id": str(task.assignee_id) if task.assignee_id else None},
    )
    session.commit()
    session.refresh(task)
    return task


def create_comment(
    *,
    session: Session,
    case: PdEcrCase,
    comment_in: PdEcrCommentCreate,
    current_user: User,
) -> PdEcrComment:
    ensure_case_mutable(case)
    comment = PdEcrComment.model_validate(
        comment_in,
        update={"case_id": case.id, "author_id": current_user.id},
    )
    session.add(comment)
    write_activity(
        session=session,
        action="comment.created",
        case_id=case.id,
        actor_id=current_user.id,
        target_type=comment.target_type,
        target_id=comment.target_id,
    )
    session.commit()
    session.refresh(comment)
    return comment


def write_version(
    *,
    session: Session,
    case: PdEcrCase,
    entity_type: str,
    entity_id: str,
    actor_id: uuid.UUID | None,
    snapshot: dict[str, Any],
    diff_metadata: dict[str, Any] | None = None,
) -> PdEcrVersion:
    latest = session.exec(
        select(PdEcrVersion)
        .where(PdEcrVersion.entity_type == entity_type, PdEcrVersion.entity_id == entity_id)
        .order_by(PdEcrVersion.version.desc())
    ).first()
    version = (latest.version + 1) if latest else 1
    record = PdEcrVersion(
        case_id=case.id,
        entity_type=entity_type,
        entity_id=entity_id,
        version=version,
        snapshot=snapshot,
        diff_metadata=diff_metadata or {},
        created_by_id=actor_id,
    )
    session.add(record)
    return record


def serialize_case(case: PdEcrCase) -> dict[str, Any]:
    display_status = "historical" if case.is_historical else case.status
    lifecycle = lifecycle_payload(case.status)
    return {
        "id": str(case.id),
        "case_no": case.case_no,
        "title": case.title,
        "status": display_status,
        "raw_status": case.status,
        "lifecycle_status": "historical" if case.is_historical else lifecycle["lifecycle_status"],
        "lifecycle_label": "Historical" if case.is_historical else lifecycle["lifecycle_label"],
        "is_legacy_status": lifecycle["is_legacy_status"],
        "allowed_next_statuses": [] if case.is_historical else allowed_next_statuses(case.status),
        "source_type": case.source_type,
        "is_historical": case.is_historical,
        "created_by_id": str(case.created_by_id) if case.created_by_id else None,
        "owner_id": str(case.owner_id) if case.owner_id else None,
        "dc_no": case.dc_no,
        "mcr_no": case.mcr_no,
        "customer_project": case.customer_project,
        "product_no": case.product_no,
        "part_no": case.part_no,
        "component_no": case.part_no,
        "part_number": case.part_no,
        "change_type": case.change_type,
        "sample_type": case.sample_type,
        "initiator": case.initiator,
        "target_close_date": case.target_close_date.isoformat() if case.target_close_date else None,
        "created_at": case.created_at.isoformat() if case.created_at else None,
        "updated_at": case.updated_at.isoformat() if case.updated_at else None,
        "closed_at": case.closed_at.isoformat() if case.closed_at else None,
        "source_file": case.case_no,
        "customer": case.customer_project,
        "project": case.customer_project,
        "product_class": "PD-ECR",
    }


def serialize_module(module: PdEcrModule) -> dict[str, Any]:
    return {
        "id": str(module.id),
        "case_id": str(module.case_id),
        "module_id": module.module_id,
        "title": module.title,
        "content_json": module.content_json,
        "content_md": module.content_md,
        "source_cases": module.source_cases,
        "source_files": module.source_files,
        "needs_human_input": module.needs_human_input,
        "status": module.status,
        "version": module.version,
        "assignee_id": str(module.assignee_id) if module.assignee_id else None,
        "assignee_email": module.assignee_email,
        "assignee_name": module.assignee_name,
        "department": module.department,
        "due_date": module.due_date.isoformat() if module.due_date else None,
        "reminder_policy": module.reminder_policy,
        "last_reminded_at": module.last_reminded_at.isoformat()
        if module.last_reminded_at
        else None,
        "permissions": {},
        "updated_by_id": str(module.updated_by_id) if module.updated_by_id else None,
        "updated_at": module.updated_at.isoformat() if module.updated_at else None,
        "data": {
            "content": module.content_md or "",
            **(module.content_json or {}),
        },
    }


def serialize_module_for_user(
    *, case: PdEcrCase, module: PdEcrModule, user: User | None
) -> dict[str, Any]:
    payload = serialize_module(module)
    payload["permissions"] = module_permission_flags(case, module, user)
    return payload
