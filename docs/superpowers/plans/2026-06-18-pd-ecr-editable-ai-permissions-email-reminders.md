# PD-ECR Editable AI Permissions Email Reminders Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn AI one-click generation into persisted editable PD-ECR cases/modules, add module-level regeneration, enforce lightweight permissions, and email responsible people when modules need timely handling.

**Architecture:** The backend remains the source of truth: AI generation creates `PdEcrCase` and `PdEcrModule` records, module edits go through existing versioned update paths, and reminder delivery is isolated behind a notification service. The frontend stops treating AI output as local-only generated content and navigates users to persisted editable case/module records.

**Tech Stack:** FastAPI, SQLModel, Alembic, Pydantic v2, pytest, React 19, TypeScript 5.9, TanStack Query/Router, axios, Tailwind CSS.

## Global Constraints

- Keep existing `/api/v1/pd-ecr` route family and current V1 draft APIs compatible.
- Do not create Outlook calendar events in this phase.
- Implement Outlook-related reminder needs as email reminders to module responsible people.
- Use existing SMTP/email utility first; preserve a clean future path to Microsoft Graph `sendMail`.
- Backend permission checks are mandatory; frontend button disabling is only a convenience.
- Historical imported cases remain read-only unless copied/generated into a new editable draft.
- Use direct assignment fields on `PdEcrModule` for the first implementation.
- Use TDD for each task: failing test first, minimal implementation second, verification third.
- Preserve existing user changes and avoid broad refactors.

---

## File Structure

Create or modify these files:

- Modify: `backend/app/models.py`
  - Add user role field.
  - Add module assignment/reminder fields.
  - Add `PdEcrNotification` model.
  - Extend `PdEcrModuleUpdate` with assignment/reminder fields.
- Create: `backend/app/alembic/versions/9d7a4c2e6b18_add_pd_ecr_permissions_and_notifications.py`
  - Migration for role, module assignment fields, and notification log table.
- Modify: `backend/app/services/pd_ecr_case_service.py`
  - Add permission helpers and serialize assignment/reminder/permission fields.
  - Add assignment update helper.
- Create: `backend/app/services/pd_ecr_ai_case_service.py`
  - Create persisted editable case from generated draft.
  - Regenerate one module as preview.
  - Apply generated preview through normal update behavior.
- Create: `backend/app/services/pd_ecr_notification_service.py`
  - Build email payloads, send via existing email utility, persist notification results, and scan due reminders.
- Modify: `backend/app/api/routes/pd_ecr.py`
  - Add persisted generation, module regeneration, assignment, manual reminder, and due-reminder endpoints.
- Modify: `frontend/src/lib/pdEcrApi.ts`
  - Add types and API calls for persisted generation, assignment, regeneration, reminders, and permissions.
- Modify: `frontend/src/components/PdEcr/PdEcrCreationWorkflow.tsx`
  - Generate persisted AI case and redirect to editable modules.
- Modify: `frontend/src/components/PdEcr/PdEcrModuleDetail.tsx`
  - Add editable save path, regeneration preview, assignment panel, and reminder action.
- Test: `backend/app/tests/services/test_pd_ecr_permissions_notifications.py`
- Test: `backend/app/tests/services/test_pd_ecr_ai_case_service.py`
- Test: existing frontend build and relevant Playwright specs.

---

### Task 1: Backend module assignment, notification model, and permission helpers

**Files:**
- Modify: `backend/app/models.py`
- Modify: `backend/app/services/pd_ecr_case_service.py`
- Create: `backend/app/alembic/versions/9d7a4c2e6b18_add_pd_ecr_permissions_and_notifications.py`
- Test: `backend/app/tests/services/test_pd_ecr_permissions_notifications.py`

**Interfaces:**
- Consumes:
  - `PdEcrCase`, `PdEcrModule`, `PdEcrModuleUpdate`, `User`
  - existing `create_case`, `update_module`, `serialize_module`
- Produces:
  - `User.pd_ecr_role: str | None`
  - `PdEcrModule.assignee_id`, `assignee_email`, `assignee_name`, `department`, `due_date`, `reminder_policy`, `last_reminded_at`
  - `PdEcrNotification`
  - `can_manage_case(case: PdEcrCase, user: User) -> bool`
  - `can_edit_module(case: PdEcrCase, module: PdEcrModule | None, user: User) -> bool`
  - `ensure_case_manage_access(case: PdEcrCase, user: User) -> None`
  - `ensure_module_edit_access(case: PdEcrCase, module: PdEcrModule | None, user: User) -> None`
  - `module_permission_flags(case: PdEcrCase, module: PdEcrModule | None, user: User | None) -> dict[str, bool]`

- [ ] **Step 1: Write failing permission and serialization tests**

Add `backend/app/tests/services/test_pd_ecr_permissions_notifications.py`:

```python
from datetime import datetime, timezone

import pytest
from fastapi import HTTPException
from sqlmodel import SQLModel, Session, create_engine, select

from app.models import PdEcrCaseCreate, PdEcrModule, PdEcrModuleUpdate, User
from app.services.pd_ecr_case_service import (
    create_case,
    ensure_case_manage_access,
    module_permission_flags,
    serialize_module,
    update_module,
)


@pytest.fixture()
def session():
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)
    with Session(engine) as db:
        yield db


def make_user(session: Session, email: str, *, role: str | None = None, superuser: bool = False) -> User:
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
        module_in=PdEcrModuleUpdate(content_md="assigned edit", expected_version=module.version),
        current_user=assignee,
    )

    assert updated.content_md == "assigned edit"
    serialized = serialize_module(updated)
    assert serialized["assignee_email"] == "assignee@example.com"
    assert serialized["due_date"].startswith("2026-06-20")
    assert serialized["permissions"]["can_edit"] is True


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
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```powershell
python -m pytest backend/app/tests/services/test_pd_ecr_permissions_notifications.py -v
```

Expected: FAIL with missing `pd_ecr_role`, assignment fields, and permission helpers.

- [ ] **Step 3: Add model fields**

In `backend/app/models.py`, extend `UserBase`, `PdEcrModuleBase`, and `PdEcrModuleUpdate`, and add `PdEcrNotification`:

```python
class UserBase(SQLModel):
    email: EmailStr = Field(unique=True, index=True, max_length=255)
    is_active: bool = True
    is_superuser: bool = False
    full_name: str | None = Field(default=None, max_length=255)
    auth_provider: str = Field(default="local", max_length=32)
    external_subject: str | None = Field(default=None, index=True, max_length=255)
    department: str | None = Field(default=None, max_length=255)
    display_name: str | None = Field(default=None, max_length=255)
    pd_ecr_role: str | None = Field(default=None, index=True, max_length=64)
```

Add these fields inside `PdEcrModuleBase`:

```python
    assignee_id: uuid.UUID | None = Field(default=None, foreign_key="user.id", index=True)
    assignee_email: str | None = Field(default=None, index=True, max_length=255)
    assignee_name: str | None = Field(default=None, max_length=255)
    department: str | None = Field(default=None, index=True, max_length=255)
    due_date: datetime | None = Field(default=None, sa_type=DateTime(timezone=True))  # type: ignore
    reminder_policy: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    last_reminded_at: datetime | None = Field(default=None, sa_type=DateTime(timezone=True))  # type: ignore
```

Add this model after `PdEcrActivity`:

```python
class PdEcrNotificationBase(SQLModel):
    module_id: str | None = Field(default=None, index=True, max_length=128)
    recipient_email: str = Field(index=True, max_length=255)
    notification_type: str = Field(index=True, max_length=64)
    subject: str = Field(max_length=500)
    status: str = Field(default="pending", index=True, max_length=64)
    provider: str = Field(default="smtp", index=True, max_length=64)
    provider_message_id: str | None = Field(default=None, max_length=255)
    error_message: str | None = Field(default=None, sa_column=Column(Text))
    sent_at: datetime | None = Field(default=None, sa_type=DateTime(timezone=True))  # type: ignore


class PdEcrNotification(PdEcrNotificationBase, table=True):
    __tablename__ = "pd_ecr_notification"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    case_id: uuid.UUID = Field(foreign_key="pd_ecr_case.id", index=True, nullable=False)
    created_at: datetime = Field(default_factory=get_datetime_utc, sa_type=DateTime(timezone=True))  # type: ignore
```

Extend `PdEcrModuleUpdate`:

```python
class PdEcrModuleUpdate(SQLModel):
    title: str | None = None
    content_json: dict[str, Any] | None = None
    content_md: str | None = None
    source_cases: list[str] | None = None
    source_files: list[str] | None = None
    needs_human_input: bool | None = None
    status: str | None = None
    assignee_id: uuid.UUID | None = None
    assignee_email: str | None = None
    assignee_name: str | None = None
    department: str | None = None
    due_date: datetime | None = None
    reminder_policy: dict[str, Any] | None = None
    expected_version: int | None = None
```

- [ ] **Step 4: Add permission helpers and serialized fields**

In `backend/app/services/pd_ecr_case_service.py`, update imports to include `PdEcrNotification` only if needed later, then add helpers after `ensure_write_access`:

```python
MANAGER_ROLES = {"pd_ecr_manager"}
MODULE_EDIT_ROLES = {"pd_ecr_manager", "case_owner", "module_owner"}
REVIEW_ROLES = {"pd_ecr_manager", "reviewer"}


def user_pd_ecr_role(user: User) -> str:
    return str(getattr(user, "pd_ecr_role", "") or "").strip()


def can_manage_case(case: PdEcrCase, user: User) -> bool:
    if user.is_superuser:
        return True
    if user_pd_ecr_role(user) in MANAGER_ROLES:
        return True
    return case.owner_id == user.id or case.created_by_id == user.id


def can_edit_module(case: PdEcrCase, module: PdEcrModule | None, user: User) -> bool:
    if can_manage_case(case, user):
        return True
    if user_pd_ecr_role(user) not in MODULE_EDIT_ROLES:
        return False
    return bool(module and module.assignee_id == user.id)


def ensure_case_manage_access(case: PdEcrCase, user: User) -> None:
    if can_manage_case(case, user):
        return
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="No manage permission for this PD-ECR case",
    )


def ensure_module_edit_access(
    case: PdEcrCase, module: PdEcrModule | None, user: User
) -> None:
    if can_edit_module(case, module, user):
        return
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="No edit permission for this PD-ECR module",
    )


def module_permission_flags(
    case: PdEcrCase, module: PdEcrModule | None, user: User | None
) -> dict[str, bool]:
    if user is None:
        return {
            "can_edit": False,
            "can_assign": False,
            "can_regenerate": False,
            "can_send_reminder": False,
            "can_review": False,
            "can_close": False,
        }
    can_manage = can_manage_case(case, user)
    can_edit = can_edit_module(case, module, user)
    role = user_pd_ecr_role(user)
    return {
        "can_edit": can_edit,
        "can_assign": can_manage,
        "can_regenerate": can_edit,
        "can_send_reminder": can_manage,
        "can_review": can_manage or role in REVIEW_ROLES,
        "can_close": can_manage,
    }
```

In `update_module`, fetch the module before checking permission and replace `ensure_write_access(case, current_user)` with:

```python
    ensure_module_edit_access(case, module, current_user)
```

After module creation in `update_module`, call `ensure_module_edit_access` again if the module was just created:

```python
    if module is None:
        module = PdEcrModule(case_id=case.id, module_id=module_id, title=module_id)
        session.add(module)
        session.flush()
    ensure_module_edit_access(case, module, current_user)
```

Extend `serialize_module`:

```python
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
```

Then add an optional helper used by routes when current user is available:

```python
def serialize_module_for_user(
    *, case: PdEcrCase, module: PdEcrModule, user: User | None
) -> dict[str, Any]:
    payload = serialize_module(module)
    payload["permissions"] = module_permission_flags(case, module, user)
    return payload
```

- [ ] **Step 5: Add Alembic migration**

Create `backend/app/alembic/versions/9d7a4c2e6b18_add_pd_ecr_permissions_and_notifications.py`:

```python
"""Add PD-ECR permissions and notifications

Revision ID: 9d7a4c2e6b18
Revises: 7b4f2d9c6a10
Create Date: 2026-06-18 12:00:00.000000

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "9d7a4c2e6b18"
down_revision = "7b4f2d9c6a10"
branch_labels = None
depends_on = None


uuid_type = postgresql.UUID(as_uuid=True)


def upgrade():
    op.add_column("user", sa.Column("pd_ecr_role", sa.String(length=64), nullable=True))
    op.create_index("ix_user_pd_ecr_role", "user", ["pd_ecr_role"], unique=False)

    op.add_column("pd_ecr_module", sa.Column("assignee_id", uuid_type, nullable=True))
    op.add_column("pd_ecr_module", sa.Column("assignee_email", sa.String(length=255), nullable=True))
    op.add_column("pd_ecr_module", sa.Column("assignee_name", sa.String(length=255), nullable=True))
    op.add_column("pd_ecr_module", sa.Column("department", sa.String(length=255), nullable=True))
    op.add_column("pd_ecr_module", sa.Column("due_date", sa.DateTime(timezone=True), nullable=True))
    op.add_column("pd_ecr_module", sa.Column("reminder_policy", sa.JSON(), nullable=True))
    op.add_column("pd_ecr_module", sa.Column("last_reminded_at", sa.DateTime(timezone=True), nullable=True))
    op.execute("UPDATE pd_ecr_module SET reminder_policy = '{}' WHERE reminder_policy IS NULL")
    op.alter_column("pd_ecr_module", "reminder_policy", nullable=False)
    op.create_foreign_key(
        "fk_pd_ecr_module_assignee_id_user",
        "pd_ecr_module",
        "user",
        ["assignee_id"],
        ["id"],
    )
    for column in ("assignee_id", "assignee_email", "department"):
        op.create_index(f"ix_pd_ecr_module_{column}", "pd_ecr_module", [column], unique=False)

    op.create_table(
        "pd_ecr_notification",
        sa.Column("module_id", sa.String(length=128), nullable=True),
        sa.Column("recipient_email", sa.String(length=255), nullable=False),
        sa.Column("notification_type", sa.String(length=64), nullable=False),
        sa.Column("subject", sa.String(length=500), nullable=False),
        sa.Column("status", sa.String(length=64), nullable=False),
        sa.Column("provider", sa.String(length=64), nullable=False),
        sa.Column("provider_message_id", sa.String(length=255), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", uuid_type, nullable=False),
        sa.Column("case_id", uuid_type, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["case_id"], ["pd_ecr_case.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    for column in ("module_id", "recipient_email", "notification_type", "status", "provider", "case_id"):
        op.create_index(f"ix_pd_ecr_notification_{column}", "pd_ecr_notification", [column], unique=False)


def downgrade():
    op.drop_table("pd_ecr_notification")
    for column in ("department", "assignee_email", "assignee_id"):
        op.drop_index(f"ix_pd_ecr_module_{column}", table_name="pd_ecr_module")
    op.drop_constraint("fk_pd_ecr_module_assignee_id_user", "pd_ecr_module", type_="foreignkey")
    op.drop_column("pd_ecr_module", "last_reminded_at")
    op.drop_column("pd_ecr_module", "reminder_policy")
    op.drop_column("pd_ecr_module", "due_date")
    op.drop_column("pd_ecr_module", "department")
    op.drop_column("pd_ecr_module", "assignee_name")
    op.drop_column("pd_ecr_module", "assignee_email")
    op.drop_column("pd_ecr_module", "assignee_id")
    op.drop_index("ix_user_pd_ecr_role", table_name="user")
    op.drop_column("user", "pd_ecr_role")
```

- [ ] **Step 6: Run backend tests**

Run:

```powershell
python -m pytest backend/app/tests/services/test_pd_ecr_permissions_notifications.py backend/app/tests/services/test_pd_ecr_collaboration.py -v
```

Expected: PASS.

- [ ] **Step 7: Commit**

Run:

```bash
git add backend/app/models.py backend/app/services/pd_ecr_case_service.py backend/app/alembic/versions/9d7a4c2e6b18_add_pd_ecr_permissions_and_notifications.py backend/app/tests/services/test_pd_ecr_permissions_notifications.py
git commit -m "feat: add pd-ecr module permissions and notification data"
```

---

### Task 2: Persist AI generation into editable case/modules

**Files:**
- Create: `backend/app/services/pd_ecr_ai_case_service.py`
- Modify: `backend/app/api/routes/pd_ecr.py`
- Test: `backend/app/tests/services/test_pd_ecr_ai_case_service.py`

**Interfaces:**
- Consumes:
  - `generate_grounded_draft(data: dict[str, Any], similar_cases: list[dict[str, Any]] | None) -> GeneratedDraft`
  - `create_case(session: Session, case_in: PdEcrCaseCreate, current_user: User) -> PdEcrCase`
- Produces:
  - `create_case_from_ai(session: Session, input_data: dict[str, Any], current_user: User, similar_cases: list[dict[str, Any]] | None = None) -> dict[str, Any]`
  - `POST /api/v1/pd-ecr/cases/generate-from-ai`

- [ ] **Step 1: Write failing persisted-generation tests**

Create `backend/app/tests/services/test_pd_ecr_ai_case_service.py`:

```python
from sqlmodel import SQLModel, Session, create_engine, select

from app.models import PdEcrModule, User
from app.services.pd_ecr_ai_case_service import create_case_from_ai


VALID_INPUT = {
    "dc_no": "PD-ECR-AI-001",
    "mcr_no": "MCR-AI-001",
    "customer_project": "JIM-493",
    "product_no": "F01ZH003G1-00",
    "part_no": "F01ZH003G1-00",
    "change_type": "A Sample release",
    "change_description": "Release detachable and integrated sample parts",
    "change_reason": "Customer request and design optimization",
}


def test_create_case_from_ai_persists_editable_modules():
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        user = User(email="ai-owner@example.com", hashed_password="not-used")
        session.add(user)
        session.commit()
        session.refresh(user)

        result = create_case_from_ai(
            session=session,
            input_data=VALID_INPUT,
            current_user=user,
            similar_cases=[],
        )

        assert result["case"]["case_no"] == "PD-ECR-AI-001"
        assert result["case"]["status"] == "draft"
        assert result["redirect_to"].endswith(f"/pd-ecr/cases/{result['case']['id']}")
        modules = session.exec(select(PdEcrModule)).all()
        assert len(modules) >= 6
        change_module = next(module for module in modules if module.module_id == "change-description")
        assert "Release detachable" in (change_module.content_md or "")
        assert change_module.version == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```powershell
python -m pytest backend/app/tests/services/test_pd_ecr_ai_case_service.py -v
```

Expected: FAIL because `pd_ecr_ai_case_service.py` does not exist.

- [ ] **Step 3: Create AI case persistence service**

Create `backend/app/services/pd_ecr_ai_case_service.py`:

```python
from __future__ import annotations

from typing import Any

from sqlmodel import Session

from app.models import PdEcrCaseCreate, User
from app.services.pd_ecr_case_service import create_case, list_modules, serialize_case, serialize_module
from app.services.pd_ecr_generation import generate_grounded_draft


def _case_no_from_input(input_data: dict[str, Any], draft_id: str) -> str:
    return str(
        input_data.get("dc_no")
        or input_data.get("case_no")
        or input_data.get("mcr_no")
        or draft_id
    )


def _module_payloads_from_draft(draft) -> list[dict[str, Any]]:
    modules: list[dict[str, Any]] = []
    for module in draft.modules:
        module_data = module.model_dump(mode="json")
        modules.append(
            {
                "module_id": module_data["module_id"],
                "title": module_data["title"],
                "content_md": module_data.get("content") or "",
                "content_json": {
                    "summary": module_data.get("summary") or "",
                    "warnings": module_data.get("warnings") or [],
                    "generated_from": "ai",
                    "draft_id": draft.draft_id,
                },
                "source_cases": module_data.get("source_cases") or [],
                "source_files": module_data.get("source_files") or [],
                "needs_human_input": bool(module_data.get("needs_human_input")),
            }
        )
    return modules


def create_case_from_ai(
    *,
    session: Session,
    input_data: dict[str, Any],
    current_user: User,
    similar_cases: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    draft = generate_grounded_draft(input_data, similar_cases=similar_cases)
    case_in = PdEcrCaseCreate(
        case_no=_case_no_from_input(input_data, draft.draft_id),
        title=str(input_data.get("change_description") or input_data.get("title") or "AI generated PD-ECR draft")[:500],
        status="draft",
        source_type="ai_generated",
        is_historical=False,
        dc_no=input_data.get("dc_no"),
        mcr_no=input_data.get("mcr_no"),
        customer_project=input_data.get("customer_project"),
        product_no=input_data.get("product_no"),
        part_no=input_data.get("part_no") or input_data.get("component_no"),
        change_type=input_data.get("change_type"),
        initiator=input_data.get("initiator"),
        modules=_module_payloads_from_draft(draft),
    )
    case = create_case(session=session, case_in=case_in, current_user=current_user)
    modules = list_modules(session=session, case_id=case.id)
    return {
        "case": serialize_case(case),
        "modules": [serialize_module(module) for module in modules],
        "draft_id": draft.draft_id,
        "draft_status": draft.draft_status.value,
        "warnings": [
            warning
            for module in draft.modules
            for warning in module.warnings
        ],
        "redirect_to": f"/pd-ecr/cases/{case.id}",
    }
```

- [ ] **Step 4: Add route payload and endpoint**

In `backend/app/api/routes/pd_ecr.py`, import the service:

```python
from app.services.pd_ecr_ai_case_service import create_case_from_ai
```

Add payload class near `PdEcrGenerateDraftPayload`:

```python
class PdEcrGenerateCasePayload(BaseModel):
    input: Dict[str, Any]
    similar_cases: list[Dict[str, Any]] | None = None
```

Add route after `create_pd_ecr_case`:

```python
@router.post("/cases/generate-from-ai")
def create_pd_ecr_case_from_ai(
    payload: PdEcrGenerateCasePayload,
    session: SessionDep,
    current_user: CurrentUser,
):
    try:
        return create_case_from_ai(
            session=session,
            input_data=payload.input,
            similar_cases=payload.similar_cases,
            current_user=current_user,
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=422,
            detail=f"PD-ECR AI case creation failed: {e}",
        )
```

- [ ] **Step 5: Run tests**

Run:

```powershell
python -m pytest backend/app/tests/services/test_pd_ecr_ai_case_service.py backend/app/tests/services/test_pd_ecr_generation.py -v
```

Expected: PASS.

- [ ] **Step 6: Commit**

Run:

```bash
git add backend/app/services/pd_ecr_ai_case_service.py backend/app/api/routes/pd_ecr.py backend/app/tests/services/test_pd_ecr_ai_case_service.py
git commit -m "feat: persist ai generated pd-ecr drafts"
```

---

### Task 3: Module regeneration preview and apply flow

**Files:**
- Modify: `backend/app/services/pd_ecr_ai_case_service.py`
- Modify: `backend/app/api/routes/pd_ecr.py`
- Test: `backend/app/tests/services/test_pd_ecr_ai_case_service.py`

**Interfaces:**
- Consumes:
  - Task 1 permission helpers
  - Task 2 AI case service
- Produces:
  - `regenerate_module_preview(...) -> dict[str, Any]`
  - `apply_generated_module(...) -> dict[str, Any]`
  - `POST /cases/{case_id}/modules/{module_id}/regenerate`
  - `POST /cases/{case_id}/modules/{module_id}/apply-generated`

- [ ] **Step 1: Add failing regeneration tests**

Append to `backend/app/tests/services/test_pd_ecr_ai_case_service.py`:

```python
from app.models import PdEcrModuleUpdate
from app.services.pd_ecr_ai_case_service import apply_generated_module, regenerate_module_preview


def test_regenerate_module_preview_does_not_overwrite_until_applied():
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        user = User(email="regen-owner@example.com", hashed_password="not-used")
        session.add(user)
        session.commit()
        session.refresh(user)
        created = create_case_from_ai(
            session=session,
            input_data=VALID_INPUT | {"dc_no": "PD-ECR-AI-REGEN-001"},
            current_user=user,
            similar_cases=[],
        )

        preview = regenerate_module_preview(
            session=session,
            case_id=created["case"]["id"],
            module_id="impact-analysis",
            current_user=user,
            instruction="Focus on manufacturing impact.",
        )
        module = session.exec(
            select(PdEcrModule).where(PdEcrModule.module_id == "impact-analysis")
        ).one()
        before_version = module.version
        assert preview["module_id"] == "impact-analysis"
        assert preview["content_md"]
        assert module.version == before_version

        applied = apply_generated_module(
            session=session,
            case_id=created["case"]["id"],
            module_id="impact-analysis",
            generated=preview,
            expected_version=before_version,
            current_user=user,
        )

        assert applied["module"]["version"] == before_version + 1
        assert applied["module"]["content_md"] == preview["content_md"]
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```powershell
python -m pytest backend/app/tests/services/test_pd_ecr_ai_case_service.py::test_regenerate_module_preview_does_not_overwrite_until_applied -v
```

Expected: FAIL because functions do not exist.

- [ ] **Step 3: Implement preview and apply helpers**

Append to `backend/app/services/pd_ecr_ai_case_service.py`:

```python
from fastapi import HTTPException
from app.models import PdEcrModuleUpdate
from app.services.pd_ecr_case_service import (
    ensure_module_edit_access,
    get_case_or_404,
    update_module,
)


def _module_by_id(session: Session, case, module_id: str):
    for module in list_modules(session=session, case_id=case.id):
        if module.module_id == module_id:
            return module
    raise HTTPException(status_code=404, detail="PD-ECR module not found")


def regenerate_module_preview(
    *,
    session: Session,
    case_id: str,
    module_id: str,
    current_user: User,
    instruction: str | None = None,
) -> dict[str, Any]:
    case = get_case_or_404(session=session, case_id=case_id)
    module = _module_by_id(session, case, module_id)
    ensure_module_edit_access(case, module, current_user)
    input_data = {
        "dc_no": case.dc_no or case.case_no,
        "mcr_no": case.mcr_no or "",
        "customer_project": case.customer_project or "",
        "product_no": case.product_no or "",
        "part_no": case.part_no or "",
        "change_type": case.change_type or "",
        "change_description": case.title or module.content_md or "",
        "change_reason": instruction or module.content_json.get("summary") or "",
    }
    draft = generate_grounded_draft(input_data, similar_cases=[])
    generated_module = next(
        (item for item in draft.modules if item.module_id.value == module_id),
        None,
    )
    if generated_module is None:
        raise HTTPException(status_code=404, detail=f"Generated module not found: {module_id}")
    payload = generated_module.model_dump(mode="json")
    return {
        "case_id": str(case.id),
        "module_id": module_id,
        "title": payload["title"],
        "content_md": payload.get("content") or "",
        "content_json": {
            "summary": payload.get("summary") or "",
            "warnings": payload.get("warnings") or [],
            "generated_from": "module_regenerate",
            "draft_id": draft.draft_id,
            "instruction": instruction or "",
        },
        "source_cases": payload.get("source_cases") or [],
        "source_files": payload.get("source_files") or [],
        "needs_human_input": bool(payload.get("needs_human_input")),
    }


def apply_generated_module(
    *,
    session: Session,
    case_id: str,
    module_id: str,
    generated: dict[str, Any],
    expected_version: int,
    current_user: User,
) -> dict[str, Any]:
    case = get_case_or_404(session=session, case_id=case_id)
    updated = update_module(
        session=session,
        case=case,
        module_id=module_id,
        module_in=PdEcrModuleUpdate(
            title=generated.get("title"),
            content_md=generated.get("content_md") or "",
            content_json=generated.get("content_json") or {},
            source_cases=generated.get("source_cases") or [],
            source_files=generated.get("source_files") or [],
            needs_human_input=bool(generated.get("needs_human_input")),
            expected_version=expected_version,
        ),
        current_user=current_user,
    )
    return {"module": serialize_module(updated)}
```

- [ ] **Step 4: Add route payloads and endpoints**

In `backend/app/api/routes/pd_ecr.py`, import:

```python
from app.services.pd_ecr_ai_case_service import (
    apply_generated_module,
    create_case_from_ai,
    regenerate_module_preview,
)
```

Add payloads:

```python
class PdEcrRegenerateModulePayload(BaseModel):
    instruction: str | None = None


class PdEcrApplyGeneratedModulePayload(BaseModel):
    generated: Dict[str, Any]
    expected_version: int
```

Add endpoints after module patch endpoint:

```python
@router.post("/cases/{case_id}/modules/{module_id}/regenerate")
def regenerate_pd_ecr_case_module(
    case_id: str,
    module_id: str,
    payload: PdEcrRegenerateModulePayload,
    session: SessionDep,
    current_user: CurrentUser,
):
    return regenerate_module_preview(
        session=session,
        case_id=case_id,
        module_id=module_id,
        instruction=payload.instruction,
        current_user=current_user,
    )


@router.post("/cases/{case_id}/modules/{module_id}/apply-generated")
def apply_generated_pd_ecr_case_module(
    case_id: str,
    module_id: str,
    payload: PdEcrApplyGeneratedModulePayload,
    session: SessionDep,
    current_user: CurrentUser,
):
    return apply_generated_module(
        session=session,
        case_id=case_id,
        module_id=module_id,
        generated=payload.generated,
        expected_version=payload.expected_version,
        current_user=current_user,
    )
```

- [ ] **Step 5: Run tests**

Run:

```powershell
python -m pytest backend/app/tests/services/test_pd_ecr_ai_case_service.py -v
```

Expected: PASS.

- [ ] **Step 6: Commit**

Run:

```bash
git add backend/app/services/pd_ecr_ai_case_service.py backend/app/api/routes/pd_ecr.py backend/app/tests/services/test_pd_ecr_ai_case_service.py
git commit -m "feat: add pd-ecr module regeneration flow"
```

---

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

### Task 5: Assignment endpoint and automatic assignment email

**Files:**
- Modify: `backend/app/services/pd_ecr_case_service.py`
- Modify: `backend/app/api/routes/pd_ecr.py`
- Test: `backend/app/tests/services/test_pd_ecr_permissions_notifications.py`

**Interfaces:**
- Consumes:
  - Task 1 module assignment fields
  - Task 4 notification service
- Produces:
  - `assign_module(...) -> PdEcrModule`
  - `PATCH /cases/{case_id}/modules/{module_id}/assignment`

- [ ] **Step 1: Add failing assignment test**

Append to `backend/app/tests/services/test_pd_ecr_permissions_notifications.py`:

```python
from app.services.pd_ecr_case_service import assign_module


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
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```powershell
python -m pytest backend/app/tests/services/test_pd_ecr_permissions_notifications.py::test_assign_module_updates_owner_and_due_date -v
```

Expected: FAIL because `assign_module` does not exist.

- [ ] **Step 3: Implement `assign_module`**

In `backend/app/services/pd_ecr_case_service.py`, add:

```python
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
    previous = serialize_module(module)
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
        snapshot=previous,
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
```

- [ ] **Step 4: Add route payload and assignment endpoint**

In `backend/app/api/routes/pd_ecr.py`, import:

```python
from datetime import datetime

from app.services.pd_ecr_case_service import assign_module
```

Add payload:

```python
class PdEcrModuleAssignmentPayload(BaseModel):
    assignee_id: uuid.UUID | None = None
    assignee_email: str | None = None
    assignee_name: str | None = None
    department: str | None = None
    due_date: datetime | None = None
    reminder_policy: Dict[str, Any] | None = None
    send_assignment_email: bool = True
```

Add endpoint:

```python
@router.patch("/cases/{case_id}/modules/{module_id}/assignment")
def assign_pd_ecr_case_module(
    case_id: str,
    module_id: str,
    payload: PdEcrModuleAssignmentPayload,
    session: SessionDep,
    current_user: CurrentUser,
):
    case = get_case_or_404(session=session, case_id=case_id)
    module = assign_module(
        session=session,
        case=case,
        module_id=module_id,
        assignee_id=payload.assignee_id,
        assignee_email=payload.assignee_email,
        assignee_name=payload.assignee_name,
        department=payload.department,
        due_date=payload.due_date,
        reminder_policy=payload.reminder_policy,
        current_user=current_user,
    )
    notification = None
    if payload.send_assignment_email and module.reminder_policy.get("on_assignment", True):
        notification = send_module_assignment_email(session=session, case=case, module=module)
    return {
        "module": serialize_module(module),
        "notification": notification.model_dump(mode="json") if notification else None,
    }
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
git add backend/app/services/pd_ecr_case_service.py backend/app/api/routes/pd_ecr.py backend/app/tests/services/test_pd_ecr_permissions_notifications.py
git commit -m "feat: add pd-ecr module assignment endpoint"
```

---

### Task 6: Frontend API support for persisted AI, assignment, regeneration, and reminders

**Files:**
- Modify: `frontend/src/lib/pdEcrApi.ts`

**Interfaces:**
- Consumes:
  - Backend endpoints from Tasks 2-5
- Produces:
  - `PdEcrPermissionFlags`
  - `PdEcrGeneratedCaseResponse`
  - `PdEcrGeneratedModulePreview`
  - `generatePdEcrEditableCase(...)`
  - `regeneratePdEcrModule(...)`
  - `applyGeneratedPdEcrModule(...)`
  - `assignPdEcrModule(...)`
  - `sendPdEcrModuleReminder(...)`

- [ ] **Step 1: Add types and functions**

Modify `frontend/src/lib/pdEcrApi.ts` by extending `PdEcrDbModule`:

```ts
export type PdEcrPermissionFlags = {
  can_edit?: boolean
  can_assign?: boolean
  can_regenerate?: boolean
  can_send_reminder?: boolean
  can_review?: boolean
  can_close?: boolean
}
```

Add fields to `PdEcrDbModule`:

```ts
  assignee_id?: string | null
  assignee_email?: string | null
  assignee_name?: string | null
  department?: string | null
  due_date?: string | null
  reminder_policy?: Record<string, unknown>
  last_reminded_at?: string | null
  permissions?: PdEcrPermissionFlags
```

Add these types:

```ts
export type PdEcrGeneratedCaseResponse = {
  case: PdEcrCase
  modules: PdEcrDbModule[]
  draft_id?: string
  draft_status?: string
  warnings?: string[]
  redirect_to?: string
}

export type PdEcrGeneratedModulePreview = {
  case_id: string
  module_id: string
  title?: string
  content_md: string
  content_json?: Record<string, unknown>
  source_cases?: string[]
  source_files?: string[]
  needs_human_input?: boolean
}

export type PdEcrModuleAssignmentPayload = {
  assignee_id?: string | null
  assignee_email?: string | null
  assignee_name?: string | null
  department?: string | null
  due_date?: string | null
  reminder_policy?: Record<string, unknown>
  send_assignment_email?: boolean
}
```

Add functions near existing generation functions:

```ts
export async function generatePdEcrEditableCase(
  input: Record<string, unknown>,
  similarCases?: PdEcrSimilarCase[],
): Promise<PdEcrGeneratedCaseResponse> {
  const res = await pdEcrApi.post<PdEcrGeneratedCaseResponse>(
    "/api/v1/pd-ecr/cases/generate-from-ai",
    { input, similar_cases: similarCases },
  )
  return res.data
}

export async function regeneratePdEcrModule(
  caseId: string,
  moduleId: string,
  instruction?: string,
): Promise<PdEcrGeneratedModulePreview> {
  const res = await pdEcrApi.post<PdEcrGeneratedModulePreview>(
    `/api/v1/pd-ecr/cases/${encodeURIComponent(caseId)}/modules/${encodeURIComponent(moduleId)}/regenerate`,
    { instruction },
  )
  return res.data
}

export async function applyGeneratedPdEcrModule(
  caseId: string,
  moduleId: string,
  generated: PdEcrGeneratedModulePreview,
  expectedVersion: number,
): Promise<{ module: PdEcrDbModule }> {
  const res = await pdEcrApi.post<{ module: PdEcrDbModule }>(
    `/api/v1/pd-ecr/cases/${encodeURIComponent(caseId)}/modules/${encodeURIComponent(moduleId)}/apply-generated`,
    { generated, expected_version: expectedVersion },
  )
  return res.data
}

export async function assignPdEcrModule(
  caseId: string,
  moduleId: string,
  payload: PdEcrModuleAssignmentPayload,
): Promise<{ module: PdEcrDbModule; notification?: Record<string, unknown> | null }> {
  const res = await pdEcrApi.patch<{
    module: PdEcrDbModule
    notification?: Record<string, unknown> | null
  }>(
    `/api/v1/pd-ecr/cases/${encodeURIComponent(caseId)}/modules/${encodeURIComponent(moduleId)}/assignment`,
    payload,
  )
  return res.data
}

export async function sendPdEcrModuleReminder(
  caseId: string,
  moduleId: string,
): Promise<{ notification: Record<string, unknown> }> {
  const res = await pdEcrApi.post<{ notification: Record<string, unknown> }>(
    `/api/v1/pd-ecr/cases/${encodeURIComponent(caseId)}/modules/${encodeURIComponent(moduleId)}/send-reminder`,
  )
  return res.data
}
```

- [ ] **Step 2: Build frontend**

Run:

```powershell
cd frontend
npm run build
```

Expected: PASS with no TypeScript errors.

- [ ] **Step 3: Commit**

Run:

```bash
git add frontend/src/lib/pdEcrApi.ts
git commit -m "feat: add pd-ecr editable ai api client"
```

---

### Task 7: Frontend creation workflow uses persisted editable AI generation

**Files:**
- Modify: `frontend/src/components/PdEcr/PdEcrCreationWorkflow.tsx`

**Interfaces:**
- Consumes:
  - `generatePdEcrEditableCase(input, similarCases)`
- Produces:
  - Generate button creates backend case and navigates to the editable case detail route.

- [ ] **Step 1: Replace local-only generation mutation**

Modify imports in `PdEcrCreationWorkflow.tsx`:

```ts
import {
  createPdEcrRequest,
  generatePdEcrEditableCase,
  type PdEcrInput,
  type PdEcrSimilarCase,
  retrievePdEcrSimilarCases,
} from "@/lib/pdEcrApi"
```

Update the mutation:

```ts
  const generateMutation = useMutation({
    mutationFn: async () => {
      const missing = missingRequiredFields(data)
      if (missing.length) {
        throw new Error(`Please fill required fields: ${missing.join(", ")}`)
      }
      const input = buildInput(data)
      const cases =
        similarCases.length > 0
          ? similarCases
          : (await retrievePdEcrSimilarCases(input, 5)).results
      setSimilarCases(cases)
      return generatePdEcrEditableCase(input, cases)
    },
    onSuccess: (response) => {
      setStatus("Generated an editable PD-ECR draft. Opening the case now.")
      navigate({
        to: "/pd-ecr/cases",
        search: { view: "all" },
      })
    },
    onError: (error) => {
      const result = buildGeneratedResult({ message: "fallback" })
      saveGeneratedResult(result)
      setStatus(
        error instanceof Error
          ? error.message
          : "Generation service unavailable. Fallback modules were prepared.",
      )
    },
  })
```

If a route exists for a single case detail page, use that route instead of the case list. If no route exists, navigating to the case list is acceptable for this task because the created case appears at the top by updated time.

- [ ] **Step 2: Update button copy**

Change the Generate button label:

```tsx
{generateMutation.isPending ? "Generating editable draft" : "Generate editable draft"}
```

- [ ] **Step 3: Build frontend**

Run:

```powershell
cd frontend
npm run build
```

Expected: PASS.

- [ ] **Step 4: Commit**

Run:

```bash
git add frontend/src/components/PdEcr/PdEcrCreationWorkflow.tsx
git commit -m "feat: create editable pd-ecr draft from ai workflow"
```

---

### Task 8: Frontend module detail supports assignment, reminders, and regeneration preview

**Files:**
- Modify: `frontend/src/components/PdEcr/PdEcrModuleDetail.tsx`

**Interfaces:**
- Consumes:
  - `PdEcrDbModule.permissions`
  - `regeneratePdEcrModule`
  - `applyGeneratedPdEcrModule`
  - `assignPdEcrModule`
  - `sendPdEcrModuleReminder`
- Produces:
  - Assignment panel
  - Reminder button
  - Regenerate preview/apply/discard UI

- [ ] **Step 1: Add API imports**

In `PdEcrModuleDetail.tsx`, extend imports from `@/lib/pdEcrApi`:

```ts
import {
  applyGeneratedPdEcrModule,
  assignPdEcrModule,
  getPdEcrModuleDraft,
  regeneratePdEcrModule,
  savePdEcrModuleDraft,
  sendPdEcrModuleReminder,
  type PdEcrGeneratedModulePreview,
} from "@/lib/pdEcrApi"
```

- [ ] **Step 2: Add component state**

Near existing module state:

```ts
  const [assignmentEmail, setAssignmentEmail] = useState(module.assignee_email || "")
  const [assignmentName, setAssignmentName] = useState(module.assignee_name || "")
  const [assignmentDepartment, setAssignmentDepartment] = useState(module.department || "")
  const [assignmentDueDate, setAssignmentDueDate] = useState(
    module.due_date ? module.due_date.slice(0, 10) : "",
  )
  const [regenerateInstruction, setRegenerateInstruction] = useState("")
  const [generatedPreview, setGeneratedPreview] =
    useState<PdEcrGeneratedModulePreview | null>(null)
  const [actionStatus, setActionStatus] = useState("")
```

- [ ] **Step 3: Add handlers**

Add these handlers in the component:

```ts
  const caseId = module.case_id
  const canAssign = Boolean(module.permissions?.can_assign)
  const canRegenerate = Boolean(module.permissions?.can_regenerate)
  const canSendReminder = Boolean(module.permissions?.can_send_reminder)

  const handleAssignModule = async () => {
    if (!caseId || !module.id) return
    const response = await assignPdEcrModule(caseId, module.id, {
      assignee_email: assignmentEmail || null,
      assignee_name: assignmentName || null,
      department: assignmentDepartment || null,
      due_date: assignmentDueDate || null,
      reminder_policy: { on_assignment: true, overdue: true },
      send_assignment_email: true,
    })
    setActionStatus(
      response.notification
        ? "Assignment saved and reminder email was queued."
        : "Assignment saved.",
    )
  }

  const handleRegenerate = async () => {
    if (!caseId || !module.id) return
    const preview = await regeneratePdEcrModule(
      caseId,
      module.id,
      regenerateInstruction,
    )
    setGeneratedPreview(preview)
    setActionStatus("Generated preview is ready. Review before applying.")
  }

  const handleApplyGenerated = async () => {
    if (!caseId || !module.id || !generatedPreview) return
    await applyGeneratedPdEcrModule(
      caseId,
      module.id,
      generatedPreview,
      module.version,
    )
    setActionStatus("Generated module content applied. Refresh the module to see the latest version.")
    setGeneratedPreview(null)
  }

  const handleSendReminder = async () => {
    if (!caseId || !module.id) return
    await sendPdEcrModuleReminder(caseId, module.id)
    setActionStatus("Reminder email was sent or recorded.")
  }
```

If `module.id` is a database UUID and `module.module_id` is the business module ID, pass `module.module_id` to backend module endpoints. Use:

```ts
  const moduleRouteId = module.module_id || module.id
```

and replace `module.id` in endpoint calls with `moduleRouteId`.

- [ ] **Step 4: Add assignment and regeneration UI**

Add this block above the source references section:

```tsx
<section className="rounded-lg border border-stone-200 bg-white p-4">
  <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
    <div>
      <h3 className="text-sm font-semibold text-stone-900">
        Module owner and reminder
      </h3>
      <p className="mt-1 text-sm text-stone-500">
        Assign the responsible person and send email reminders when this module needs action.
      </p>
    </div>
    {canSendReminder ? (
      <Button type="button" variant="outline" onClick={handleSendReminder}>
        Send reminder
      </Button>
    ) : null}
  </div>

  <div className="mt-4 grid gap-3 md:grid-cols-2">
    <Input
      value={assignmentEmail}
      onChange={(event) => setAssignmentEmail(event.target.value)}
      disabled={!canAssign}
      placeholder="Responsible email"
    />
    <Input
      value={assignmentName}
      onChange={(event) => setAssignmentName(event.target.value)}
      disabled={!canAssign}
      placeholder="Responsible name"
    />
    <Input
      value={assignmentDepartment}
      onChange={(event) => setAssignmentDepartment(event.target.value)}
      disabled={!canAssign}
      placeholder="Department"
    />
    <Input
      type="date"
      value={assignmentDueDate}
      onChange={(event) => setAssignmentDueDate(event.target.value)}
      disabled={!canAssign}
    />
  </div>

  {canAssign ? (
    <Button type="button" className="mt-3" onClick={handleAssignModule}>
      Save assignment
    </Button>
  ) : null}
</section>

<section className="rounded-lg border border-stone-200 bg-white p-4">
  <h3 className="text-sm font-semibold text-stone-900">
    Regenerate this module
  </h3>
  <textarea
    value={regenerateInstruction}
    onChange={(event) => setRegenerateInstruction(event.target.value)}
    disabled={!canRegenerate}
    className="mt-3 min-h-24 w-full rounded-lg border border-stone-300 px-3 py-2 text-sm"
    placeholder="Optional instruction, for example: focus on manufacturing impact."
  />
  {canRegenerate ? (
    <Button type="button" className="mt-3" onClick={handleRegenerate}>
      Regenerate preview
    </Button>
  ) : null}

  {generatedPreview ? (
    <div className="mt-4 rounded-lg border border-amber-200 bg-amber-50 p-3">
      <p className="text-sm font-semibold text-amber-900">Preview</p>
      <pre className="mt-2 whitespace-pre-wrap text-sm text-stone-800">
        {generatedPreview.content_md}
      </pre>
      <div className="mt-3 flex gap-2">
        <Button type="button" onClick={handleApplyGenerated}>
          Apply preview
        </Button>
        <Button
          type="button"
          variant="outline"
          onClick={() => setGeneratedPreview(null)}
        >
          Discard
        </Button>
      </div>
    </div>
  ) : null}
</section>

{actionStatus ? (
  <p className="rounded-lg bg-stone-50 px-3 py-2 text-sm text-stone-700">
    {actionStatus}
  </p>
) : null}
```

- [ ] **Step 5: Build frontend**

Run:

```powershell
cd frontend
npm run build
```

Expected: PASS. If the module detail component uses `module.id` differently, change the route parameter to `module.module_id || module.id` and rebuild.

- [ ] **Step 6: Commit**

Run:

```bash
git add frontend/src/components/PdEcr/PdEcrModuleDetail.tsx
git commit -m "feat: add pd-ecr module assignment and regeneration ui"
```

---

### Task 9: Final verification

**Files:**
- Verify all changed files.

**Interfaces:**
- Consumes all earlier tasks.
- Produces verified implementation.

- [ ] **Step 1: Run backend targeted tests**

Run:

```powershell
python -m pytest backend/app/tests/services/test_pd_ecr_permissions_notifications.py backend/app/tests/services/test_pd_ecr_ai_case_service.py backend/app/tests/services/test_pd_ecr_generation.py backend/app/tests/services/test_pd_ecr_collaboration.py -v
```

Expected: PASS.

- [ ] **Step 2: Run frontend build**

Run:

```powershell
cd frontend
npm run build
```

Expected: PASS.

- [ ] **Step 3: Run relevant Playwright specs if local services are available**

Run:

```powershell
cd frontend
npx playwright test tests/pd-ecr.spec.ts tests/pd-ecr-cases.spec.ts tests/pd-ecr-cases-actions.spec.ts
```

Expected: PASS when backend and frontend dev servers are running. If local services are not running, record that Playwright verification was not executed and keep backend/unit verification as the minimum completed check.

- [ ] **Step 4: Manual smoke flow**

Run the app and verify:

1. Open new PD-ECR creation workflow.
2. Fill required fields.
3. Click Generate editable draft.
4. Confirm a persisted case is created.
5. Open a module.
6. Assign responsible email and due date.
7. Send reminder.
8. Regenerate module preview.
9. Apply preview.
10. Confirm module version increments and content remains editable.

- [ ] **Step 5: Commit verification notes if any docs changed**

Run:

```bash
git status --short
git add docs/superpowers/plans/2026-06-18-pd-ecr-editable-ai-permissions-email-reminders.md
git commit -m "docs: add pd-ecr editable ai implementation plan"
```

Expected: commit succeeds if Git is available.
