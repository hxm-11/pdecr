from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from sqlmodel import Session, delete, select

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.core.db import engine  # noqa: E402
from app.core.security import get_password_hash  # noqa: E402
from app.models import (  # noqa: E402
    PdEcrCase,
    PdEcrDepartmentTask,
    PdEcrDepartmentVisibility,
    PdEcrExecutionTask,
    PdEcrLeaderReviewTask,
    PdEcrModule,
    PdEcrTask,
    User,
)


CASE_NO = "PDECR-VALIDATION-001"
PASSWORD = "PdecrValidation123!"

USERS = {
    "manager": {
        "email": "manager-validation@example.com",
        "full_name": "PD-ECR Validation Manager",
        "display_name": "Validation Manager",
        "department": "quality",
        "pd_ecr_role": "pd_ecr_manager",
        "is_superuser": False,
    },
    "assignee": {
        "email": "assignee-validation@example.com",
        "full_name": "PD-ECR Validation Assignee",
        "display_name": "Validation Assignee",
        "department": "quality",
        "pd_ecr_role": "department_member",
        "is_superuser": False,
    },
    "leader": {
        "email": "leader-validation@example.com",
        "full_name": "PD-ECR Validation Leader",
        "display_name": "Validation Leader",
        "department": "quality",
        "pd_ecr_role": "department_leader",
        "is_superuser": False,
    },
}


def upsert_user(session: Session, profile: dict[str, object]) -> User:
    user = session.exec(
        select(User).where(User.email == str(profile["email"]))
    ).first()
    if user is None:
        user = User(
            email=str(profile["email"]),
            hashed_password=get_password_hash(PASSWORD),
        )

    user.full_name = str(profile["full_name"])
    user.display_name = str(profile["display_name"])
    user.department = str(profile["department"])
    user.pd_ecr_role = str(profile["pd_ecr_role"])
    user.is_superuser = bool(profile["is_superuser"])
    user.is_active = True
    user.auth_provider = "local"
    user.hashed_password = get_password_hash(PASSWORD)
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


def reset_case_children(session: Session, case: PdEcrCase) -> None:
    for model in (
        PdEcrLeaderReviewTask,
        PdEcrExecutionTask,
        PdEcrDepartmentVisibility,
        PdEcrDepartmentTask,
        PdEcrTask,
        PdEcrModule,
    ):
        session.exec(delete(model).where(model.case_id == case.id))  # type: ignore[attr-defined]
    session.commit()


def module_content(module_id: str) -> tuple[str, dict[str, object], str]:
    shared_sources = [CASE_NO]
    if module_id == "change-description":
        title = "Change Description"
        content = (
            "Validation seed: replace the quality inspection label for product "
            "JP360-F03Z to align drawing, packaging, and outgoing inspection records."
        )
        data = {
            "summary": "Quality label text update for JP360-F03Z.",
            "content": content,
            "reason": "Customer requested label wording alignment before next shipment.",
            "changeSummary": "Update inspection label text and verify records.",
            "departments": ["Quality"],
        }
    elif module_id == "impact-analysis":
        title = "Impact Analysis"
        content = (
            "Impact is limited to quality inspection documentation and outgoing "
            "label verification. No tooling, BOM, or drawing geometry change is expected."
        )
        data = {
            "summary": "Limited documentation and inspection impact.",
            "content": content,
            "affectedDepartments": ["Quality"],
            "riskLevel": "Low",
        }
    elif module_id == "validation-plan":
        title = "Validation Plan"
        content = (
            "Quality checks one updated label sample, confirms the inspection "
            "record template, and attaches evidence before leader review."
        )
        data = {
            "summary": "One sample label and inspection record template check.",
            "content": content,
            "validationItems": [
                {
                    "item": "Updated label wording",
                    "method": "Visual check against approved text",
                    "owner": USERS["assignee"]["email"],
                },
                {
                    "item": "Inspection record template",
                    "method": "Record review",
                    "owner": USERS["assignee"]["email"],
                },
            ],
        }
    elif module_id == "implementation-plan":
        title = "Implementation Plan"
        content = (
            "Quality executes the label wording check and records evidence. "
            "Leader signs off after the execution result is submitted."
        )
        data = {
            "summary": "Quality executes one validation checklist row.",
            "content": content,
            "implementationDate": datetime.now(timezone.utc).date().isoformat(),
            "checklistRows": [
                {
                    "id": "quality-validation-row-001",
                    "department": "Quality",
                    "description": "Verify updated JP360-F03Z inspection label wording and attach evidence.",
                    "responsible": USERS["assignee"]["email"],
                    "yn": "Y",
                    "dueDate": (datetime.now(timezone.utc) + timedelta(days=7)).date().isoformat(),
                    "status": "pending_confirmation",
                },
                {
                    "id": "purchasing-validation-row-001",
                    "department": "Purchasing",
                    "description": "Supplier commercial update is not required for this validation seed.",
                    "responsible": "",
                    "yn": "N",
                    "dueDate": "",
                    "status": "not_required",
                },
            ],
        }
    else:
        raise ValueError(f"Unsupported module id: {module_id}")

    data["source_cases"] = shared_sources
    data["warnings"] = []
    return title, data, content


def seed_case(session: Session, users: dict[str, User]) -> PdEcrCase:
    case = session.exec(select(PdEcrCase).where(PdEcrCase.case_no == CASE_NO)).first()
    if case is None:
        case = PdEcrCase(case_no=CASE_NO)

    case.title = "Validation Seed - Four Module Workflow"
    case.status = "assignee_confirmation"
    case.source_type = "validation_seed"
    case.is_historical = False
    case.dc_no = "DC-VALIDATION-001"
    case.mcr_no = "MCR-VALIDATION-001"
    case.customer_project = "Validation Project"
    case.product_no = "JP360-F03Z"
    case.part_no = "F03Z20088M-00"
    case.change_type = "Label wording update"
    case.sample_type = "Validation seed"
    case.initiator = users["manager"].full_name
    case.created_by_id = users["manager"].id
    case.owner_id = users["manager"].id
    case.updated_at = datetime.now(timezone.utc)
    session.add(case)
    session.commit()
    session.refresh(case)

    reset_case_children(session, case)

    for module_id in (
        "change-description",
        "impact-analysis",
        "validation-plan",
        "implementation-plan",
    ):
        title, data, content = module_content(module_id)
        session.add(
            PdEcrModule(
                case_id=case.id,
                module_id=module_id,
                title=title,
                content_json=data,
                content_md=content,
                source_cases=[CASE_NO],
                source_files=[],
                needs_human_input=False,
                status="draft",
                version=1,
                department="quality" if module_id != "change-description" else None,
                updated_by_id=users["manager"].id,
            )
        )

    session.add(
        PdEcrDepartmentVisibility(
            case_id=case.id,
            department="quality",
            visible_to_department=True,
            published_by_id=users["manager"].id,
            published_at=datetime.now(timezone.utc),
        )
    )
    session.add(
        PdEcrExecutionTask(
            case_id=case.id,
            checklist_row_id="quality-validation-row-001",
            department="quality",
            description="Verify updated JP360-F03Z inspection label wording and attach evidence.",
            status="pending_confirmation",
            assignee_id=users["assignee"].id,
            assignee_email=users["assignee"].email,
            assignee_name=users["assignee"].full_name,
            due_date=datetime.now(timezone.utc) + timedelta(days=7),
        )
    )
    session.add(case)
    session.commit()
    session.refresh(case)
    return case


def main() -> None:
    with Session(engine) as session:
        users = {name: upsert_user(session, profile) for name, profile in USERS.items()}
        case = seed_case(session, users)
        task = session.exec(
            select(PdEcrExecutionTask).where(PdEcrExecutionTask.case_id == case.id)
        ).first()

    print("Seeded PD-ECR validation data")
    print(f"Case: {CASE_NO}")
    print(f"Backend case id: {case.id}")
    print(f"Execution task id: {task.id if task else '-'}")
    print("")
    print("Login users, all with password:")
    print(f"  {PASSWORD}")
    for name, profile in USERS.items():
        print(f"  {name}: {profile['email']}")
    print("")
    print("Recommended check:")
    print("  1. Login as assignee-validation@example.com")
    print("  2. Open PD-ECR My Tasks")
    print("  3. Click Open change package, then Confirm assignment")
    print("  4. Submit execution result")
    print("  5. Login as leader-validation@example.com and approve the leader review")


if __name__ == "__main__":
    main()
