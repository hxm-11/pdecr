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

