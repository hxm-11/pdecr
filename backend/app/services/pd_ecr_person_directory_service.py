from __future__ import annotations

import uuid
from typing import Any

from sqlmodel import Session, col, select

from app.models import User


ROLE_APPLICANT = "applicant"
ROLE_ENGINEER = "engineer"
ROLE_LEADER = "leader"
ROLE_ADMIN = "admin"


PD_ECR_ROLE_ALIASES = {
    "pd_ecr_manager": ROLE_ADMIN,
    "admin": ROLE_ADMIN,
    "administrator": ROLE_ADMIN,
    "department_leader": ROLE_LEADER,
    "leader": ROLE_LEADER,
    "reviewer": ROLE_LEADER,
    "approver": ROLE_LEADER,
    "department_member": ROLE_ENGINEER,
    "engineer": ROLE_ENGINEER,
    "applicant": ROLE_APPLICANT,
    "initiator": ROLE_APPLICANT,
}


def display_name(user: User) -> str:
    return user.display_name or user.full_name or user.email or str(user.id)


def local_role_for_user(user: User) -> str:
    if user.is_superuser:
        return ROLE_ADMIN
    raw_role = str(user.pd_ecr_role or "").strip().lower()
    return PD_ECR_ROLE_ALIASES.get(raw_role, ROLE_APPLICANT)


def serialize_person(user: User) -> dict[str, Any]:
    role = local_role_for_user(user)
    return {
        "id": str(user.id),
        "email": user.email,
        "name": display_name(user),
        "display_name": user.display_name,
        "full_name": user.full_name,
        "department": user.department,
        "pd_ecr_role": user.pd_ecr_role,
        "local_role": role,
        "is_active": user.is_active,
        "is_superuser": user.is_superuser,
        "can_initiate": role in {ROLE_APPLICANT, ROLE_ENGINEER, ROLE_LEADER, ROLE_ADMIN},
        "can_execute": role in {ROLE_ENGINEER, ROLE_ADMIN},
        "can_approve": role in {ROLE_LEADER, ROLE_ADMIN},
        "can_admin": role == ROLE_ADMIN,
    }


def get_person_by_email(*, session: Session, email: str | None) -> User | None:
    value = str(email or "").strip()
    if not value:
        return None
    return session.exec(
        select(User).where(
            User.email == value,
            User.is_active == True,  # noqa: E712
        )
    ).first()


def get_person(*, session: Session, person_id: uuid.UUID | str | None = None, email: str | None = None) -> User | None:
    if person_id:
        try:
            parsed_id = person_id if isinstance(person_id, uuid.UUID) else uuid.UUID(str(person_id))
        except ValueError:
            parsed_id = None
        if parsed_id:
            user = session.get(User, parsed_id)
            if user and user.is_active:
                return user
    return get_person_by_email(session=session, email=email)


def search_people(
    *,
    session: Session,
    query: str | None = None,
    department: str | None = None,
    role: str | None = None,
    active_only: bool = True,
    limit: int = 50,
) -> list[dict[str, Any]]:
    statement = select(User)
    if active_only:
        statement = statement.where(User.is_active == True)  # noqa: E712
    if department:
        statement = statement.where(User.department == department)
    if role:
        raw_roles = {
            raw
            for raw, mapped in PD_ECR_ROLE_ALIASES.items()
            if mapped == role or raw == role
        }
        if role == ROLE_ADMIN:
            raw_roles.add("pd_ecr_manager")
        statement = statement.where(col(User.pd_ecr_role).in_(sorted(raw_roles)))
    if query:
        pattern = f"%{query.strip()}%"
        statement = statement.where(
            col(User.email).ilike(pattern)
            | col(User.full_name).ilike(pattern)
            | col(User.display_name).ilike(pattern)
            | col(User.department).ilike(pattern)
        )
    users = session.exec(statement.order_by(User.department, User.email).limit(limit)).all()
    return [serialize_person(user) for user in users]


def get_department_leader(*, session: Session, department: str | None) -> User | None:
    value = str(department or "").strip()
    if not value:
        return None
    return session.exec(
        select(User)
        .where(
            User.department == value,
            User.pd_ecr_role == "department_leader",
            User.is_active == True,  # noqa: E712
        )
        .order_by(User.email)
    ).first()


def resolve_approver(
    *,
    session: Session,
    current_user: User,
    form_data: dict[str, Any] | None = None,
    approver_email: str | None = None,
    approver_name: str | None = None,
) -> tuple[uuid.UUID | None, str | None, str | None]:
    form_data = form_data or {}
    resolved_email = str(approver_email or "").strip() or None
    resolved_name = str(approver_name or "").strip() or None
    resolved_id: uuid.UUID | None = None

    if not resolved_email:
        members = form_data.get("members") if isinstance(form_data.get("members"), list) else []
        owner = next(
            (
                item
                for item in members
                if isinstance(item, dict) and str(item.get("role") or "").lower() in {"owner", "approver", "leader"}
            ),
            None,
        )
        if owner:
            resolved_email = str(owner.get("email") or "").strip() or None
            resolved_name = str(owner.get("displayName") or owner.get("display_name") or "").strip() or None

    if not resolved_email:
        leader = get_department_leader(session=session, department=current_user.department)
        if leader:
            resolved_id = leader.id
            resolved_email = leader.email
            resolved_name = display_name(leader)

    if resolved_email and resolved_id is None:
        approver = get_person_by_email(session=session, email=resolved_email)
        if approver:
            resolved_id = approver.id
            resolved_name = resolved_name or display_name(approver)

    return resolved_id, resolved_email, resolved_name


def directory_contract() -> dict[str, Any]:
    return {
        "roles": [
            {"role": ROLE_APPLICANT, "label": "Applicant"},
            {"role": ROLE_ENGINEER, "label": "Engineer"},
            {"role": ROLE_LEADER, "label": "Leader / Approver"},
            {"role": ROLE_ADMIN, "label": "Admin"},
        ],
        "role_aliases": dict(PD_ECR_ROLE_ALIASES),
    }
