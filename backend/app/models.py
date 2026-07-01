import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from pydantic import EmailStr
from sqlalchemy import Column, DateTime, JSON, Text, UniqueConstraint
from sqlmodel import Field, Relationship, SQLModel


def get_datetime_utc() -> datetime:
    return datetime.now(timezone.utc)


# Shared properties
class UserBase(SQLModel):
    email: EmailStr = Field(unique=True, index=True, max_length=255)
    is_active: bool = True
    is_superuser: bool = False
    full_name: str | None = Field(default=None, max_length=255)
    auth_provider: str = Field(default="local", max_length=32)
    external_subject: str | None = Field(default=None, index=True, max_length=255)
    # Department: must match a Department enum value from pd_ecr_departments.py
    # (design / system / purchasing / manufacturing / quality / pm / catalyst)
    department: str | None = Field(default=None, max_length=255)
    display_name: str | None = Field(default=None, max_length=255)
    # pd_ecr_role convention:
    #   "department_leader"  — 部长：管理本部门所有模块
    #   "department_member"  — 部员：只编辑分配给自己的模块
    #   "pd_ecr_manager"     — 跨部门管理员：全部权限
    #   "reviewer"           — 审核者：只读 + 可审核
    pd_ecr_role: str | None = Field(default=None, index=True, max_length=64)


# Properties to receive via API on creation
class UserCreate(UserBase):
    password: str = Field(min_length=8, max_length=128)


class UserRegister(SQLModel):
    email: EmailStr = Field(max_length=255)
    password: str = Field(min_length=8, max_length=128)
    full_name: str | None = Field(default=None, max_length=255)


# Properties to receive via API on update, all are optional
class UserUpdate(UserBase):
    email: EmailStr | None = Field(default=None, max_length=255)  # type: ignore[assignment]
    password: str | None = Field(default=None, min_length=8, max_length=128)


class UserUpdateMe(SQLModel):
    full_name: str | None = Field(default=None, max_length=255)
    email: EmailStr | None = Field(default=None, max_length=255)


class UpdatePassword(SQLModel):
    current_password: str = Field(min_length=8, max_length=128)
    new_password: str = Field(min_length=8, max_length=128)


# Database model, database table inferred from class name
class User(UserBase, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    hashed_password: str
    created_at: datetime | None = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
    )
    items: list["Item"] = Relationship(back_populates="owner", cascade_delete=True)


# Properties to return via API, id is always required
class UserPublic(UserBase):
    id: uuid.UUID
    created_at: datetime | None = None


class UsersPublic(SQLModel):
    data: list[UserPublic]
    count: int


# Shared properties
class ItemBase(SQLModel):
    title: str = Field(min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=255)


# Properties to receive on item creation
class ItemCreate(ItemBase):
    pass


# Properties to receive on item update
class ItemUpdate(ItemBase):
    title: str | None = Field(default=None, min_length=1, max_length=255)  # type: ignore[assignment]


# Database model, database table inferred from class name
class Item(ItemBase, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    created_at: datetime | None = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
    )
    owner_id: uuid.UUID = Field(
        foreign_key="user.id", nullable=False, ondelete="CASCADE"
    )
    owner: User | None = Relationship(back_populates="items")


# Properties to return via API, id is always required
class ItemPublic(ItemBase):
    id: uuid.UUID
    owner_id: uuid.UUID
    created_at: datetime | None = None


class ItemsPublic(SQLModel):
    data: list[ItemPublic]
    count: int


# Generic message
class Message(SQLModel):
    message: str


# JSON payload containing access token
class Token(SQLModel):
    access_token: str
    token_type: str = "bearer"


# Contents of JWT token
class TokenPayload(SQLModel):
    sub: str | None = None


class NewPassword(SQLModel):
    token: str
    new_password: str = Field(min_length=8, max_length=128)


# 项目管理相关模型

class ProjectBase(SQLModel):
    name: str = Field(min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=255)

class Project(ProjectBase, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    owner_id: uuid.UUID = Field(foreign_key="user.id", nullable=False)
    created_at: datetime | None = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),
    )
    owner: "User" = Relationship()
    tasks: list["Task"] = Relationship(back_populates="project", sa_relationship_kwargs={"cascade": "all, delete-orphan"})

class TaskBase(SQLModel):
    title: str = Field(min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=255)
    status: str = Field(default="todo", max_length=32)

from typing import Optional

class Task(TaskBase, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    project_id: uuid.UUID = Field(foreign_key="project.id", nullable=False)
    assignee_id: Optional[uuid.UUID] = Field(foreign_key="user.id", default=None)
    created_at: datetime | None = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),
    )
    project: Project = Relationship(back_populates="tasks")
    assignee: Optional["User"] = Relationship()


# 项目管理相关 schemas

class ProjectCreate(ProjectBase):
    pass

class ProjectRead(ProjectBase):
    id: uuid.UUID
    owner_id: uuid.UUID
    created_at: datetime | None = None

class ProjectUpdate(ProjectBase):
    name: str | None = None
    description: str | None = None

class TaskCreate(TaskBase):
    project_id: uuid.UUID
    assignee_id: Optional[uuid.UUID] = None

class TaskRead(TaskBase):
    id: uuid.UUID
    project_id: uuid.UUID
    assignee_id: Optional[uuid.UUID] = None
    created_at: datetime | None = None

class TaskUpdate(TaskBase):
    title: str | None = None
    description: str | None = None
    status: str | None = None
    assignee_id: Optional[uuid.UUID] = None


# PD-ECR collaborative management models

PD_ECR_STATUSES = {
    "draft",
    "generated",
    "submitted",
    "department_confirmation",
    "department_alignment",
    "execution_assignment",
    "assignee_confirmation",
    "execution_in_progress",
    "in_review",
    "leader_review",
    "changes_requested",
    "approved",
    "implementation",
    "closed",
    "cancelled",
}

PD_ECR_DEFAULT_MODULES: list[tuple[str, str]] = [
    ("basic-information", "Basic Information"),
    ("change-description", "Change Description"),
    ("reason-for-change", "Reason for Change"),
    ("impact-analysis", "Impact Analysis"),
    ("validation-plan", "Validation & Trial Run Plan"),
    ("validation-result", "Validation & Trial Run Result"),
    ("implementation-plan", "Implementation Plan"),
    ("implementation-result", "Implementation Result"),
    ("approval-signoff", "Approval / Sign-off Information"),
    ("close-summary", "Close Summary"),
]


class PdEcrCaseBase(SQLModel):
    case_no: str = Field(index=True, min_length=1, max_length=255)
    title: str = Field(default="", max_length=500)
    status: str = Field(default="draft", index=True, max_length=32)
    source_type: str = Field(default="manual", index=True, max_length=64)
    is_historical: bool = Field(default=False, index=True)
    dc_no: str | None = Field(default=None, index=True, max_length=255)
    mcr_no: str | None = Field(default=None, index=True, max_length=255)
    customer_project: str | None = Field(default=None, index=True, max_length=255)
    product_no: str | None = Field(default=None, index=True, max_length=255)
    part_no: str | None = Field(default=None, index=True, max_length=255)
    change_type: str | None = Field(default=None, index=True, max_length=255)
    sample_type: str | None = Field(default=None, max_length=255)
    initiator: str | None = Field(default=None, max_length=255)
    target_close_date: datetime | None = Field(default=None, sa_type=DateTime(timezone=True))  # type: ignore


class PdEcrCase(PdEcrCaseBase, table=True):
    __tablename__ = "pd_ecr_case"
    __table_args__ = (UniqueConstraint("case_no", name="uq_pd_ecr_case_case_no"),)

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    created_by_id: uuid.UUID | None = Field(default=None, foreign_key="user.id", index=True)
    owner_id: uuid.UUID | None = Field(default=None, foreign_key="user.id", index=True)
    created_at: datetime = Field(default_factory=get_datetime_utc, sa_type=DateTime(timezone=True))  # type: ignore
    updated_at: datetime = Field(default_factory=get_datetime_utc, sa_type=DateTime(timezone=True))  # type: ignore
    closed_at: datetime | None = Field(default=None, sa_type=DateTime(timezone=True))  # type: ignore


class PdEcrModuleBase(SQLModel):
    module_id: str = Field(index=True, min_length=1, max_length=128)
    title: str = Field(default="", max_length=255)
    content_json: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    content_md: str | None = Field(default=None, sa_column=Column(Text))
    source_cases: list[str] = Field(default_factory=list, sa_column=Column(JSON, nullable=False))
    source_files: list[str] = Field(default_factory=list, sa_column=Column(JSON, nullable=False))
    needs_human_input: bool = Field(default=False)
    status: str = Field(default="draft", index=True, max_length=64)
    version: int = Field(default=1)
    assignee_id: uuid.UUID | None = Field(default=None, foreign_key="user.id", index=True)
    assignee_email: str | None = Field(default=None, index=True, max_length=255)
    assignee_name: str | None = Field(default=None, max_length=255)
    department: str | None = Field(default=None, index=True, max_length=255)
    due_date: datetime | None = Field(default=None, sa_type=DateTime(timezone=True))  # type: ignore
    reminder_policy: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    last_reminded_at: datetime | None = Field(default=None, sa_type=DateTime(timezone=True))  # type: ignore


class PdEcrModule(PdEcrModuleBase, table=True):
    __tablename__ = "pd_ecr_module"
    __table_args__ = (
        UniqueConstraint("case_id", "module_id", name="uq_pd_ecr_module_case_module"),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    case_id: uuid.UUID = Field(foreign_key="pd_ecr_case.id", index=True, nullable=False)
    updated_by_id: uuid.UUID | None = Field(default=None, foreign_key="user.id", index=True)
    created_at: datetime = Field(default_factory=get_datetime_utc, sa_type=DateTime(timezone=True))  # type: ignore
    updated_at: datetime = Field(default_factory=get_datetime_utc, sa_type=DateTime(timezone=True))  # type: ignore


class PdEcrTaskBase(SQLModel):
    module_id: str | None = Field(default=None, index=True, max_length=128)
    title: str = Field(min_length=1, max_length=255)
    description: str | None = Field(default=None, sa_column=Column(Text))
    status: str = Field(default="todo", index=True, max_length=32)
    due_date: datetime | None = Field(default=None, sa_type=DateTime(timezone=True))  # type: ignore


class PdEcrTask(PdEcrTaskBase, table=True):
    __tablename__ = "pd_ecr_task"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    case_id: uuid.UUID = Field(foreign_key="pd_ecr_case.id", index=True, nullable=False)
    assignee_id: uuid.UUID | None = Field(default=None, foreign_key="user.id", index=True)
    created_by_id: uuid.UUID | None = Field(default=None, foreign_key="user.id", index=True)
    created_at: datetime = Field(default_factory=get_datetime_utc, sa_type=DateTime(timezone=True))  # type: ignore
    updated_at: datetime = Field(default_factory=get_datetime_utc, sa_type=DateTime(timezone=True))  # type: ignore


class PdEcrDepartmentTaskBase(SQLModel):
    department: str = Field(index=True, min_length=1, max_length=64)
    status: str = Field(default="pending", index=True, max_length=32)
    assignee_id: uuid.UUID | None = Field(default=None, foreign_key="user.id", index=True)
    assignee_email: str | None = Field(default=None, index=True, max_length=255)
    assignee_name: str | None = Field(default=None, max_length=255)
    impact_result: str | None = Field(default=None, max_length=64)
    impact_remark: str | None = Field(default=None, sa_column=Column(Text))
    action_required: str | None = Field(default=None, sa_column=Column(Text))
    confirmed_by_id: uuid.UUID | None = Field(default=None, foreign_key="user.id", index=True)
    confirmed_by_name: str | None = Field(default=None, max_length=255)
    confirmed_at: datetime | None = Field(default=None, sa_type=DateTime(timezone=True))  # type: ignore
    due_date: datetime | None = Field(default=None, sa_type=DateTime(timezone=True))  # type: ignore


class PdEcrDepartmentTask(PdEcrDepartmentTaskBase, table=True):
    __tablename__ = "pd_ecr_department_task"
    __table_args__ = (
        UniqueConstraint("case_id", "department", name="uq_pd_ecr_dept_task_case_dept"),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    case_id: uuid.UUID = Field(foreign_key="pd_ecr_case.id", index=True, nullable=False)
    created_at: datetime = Field(default_factory=get_datetime_utc, sa_type=DateTime(timezone=True))  # type: ignore
    updated_at: datetime = Field(default_factory=get_datetime_utc, sa_type=DateTime(timezone=True))  # type: ignore


class PdEcrDepartmentVisibility(SQLModel, table=True):
    __tablename__ = "pd_ecr_department_visibility"
    __table_args__ = (
        UniqueConstraint("case_id", "department", name="uq_pd_ecr_dept_visibility_case_dept"),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    case_id: uuid.UUID = Field(foreign_key="pd_ecr_case.id", index=True, nullable=False)
    department: str = Field(index=True, min_length=1, max_length=64)
    visible_to_department: bool = Field(default=True)
    published_by_id: uuid.UUID | None = Field(default=None, foreign_key="user.id", index=True)
    published_at: datetime = Field(default_factory=get_datetime_utc, sa_type=DateTime(timezone=True))  # type: ignore
    created_at: datetime = Field(default_factory=get_datetime_utc, sa_type=DateTime(timezone=True))  # type: ignore
    updated_at: datetime = Field(default_factory=get_datetime_utc, sa_type=DateTime(timezone=True))  # type: ignore


class PdEcrExecutionTaskBase(SQLModel):
    checklist_row_id: str = Field(index=True, min_length=1, max_length=128)
    department: str = Field(index=True, min_length=1, max_length=64)
    description: str = Field(default="", sa_column=Column(Text))
    status: str = Field(default="pending_confirmation", index=True, max_length=32)
    assignee_id: uuid.UUID | None = Field(default=None, foreign_key="user.id", index=True)
    assignee_email: str | None = Field(default=None, index=True, max_length=255)
    assignee_name: str | None = Field(default=None, max_length=255)
    due_date: datetime | None = Field(default=None, sa_type=DateTime(timezone=True))  # type: ignore
    execution_result: str | None = Field(default=None, max_length=64)
    execution_note: str | None = Field(default=None, sa_column=Column(Text))
    evidence_note: str | None = Field(default=None, sa_column=Column(Text))
    completed_by_id: uuid.UUID | None = Field(default=None, foreign_key="user.id", index=True)
    completed_by_name: str | None = Field(default=None, max_length=255)
    completed_at: datetime | None = Field(default=None, sa_type=DateTime(timezone=True))  # type: ignore
    review_comment: str | None = Field(default=None, sa_column=Column(Text))


class PdEcrExecutionTask(PdEcrExecutionTaskBase, table=True):
    __tablename__ = "pd_ecr_execution_task"
    __table_args__ = (
        UniqueConstraint("case_id", "checklist_row_id", name="uq_pd_ecr_execution_task_case_row"),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    case_id: uuid.UUID = Field(foreign_key="pd_ecr_case.id", index=True, nullable=False)
    created_at: datetime = Field(default_factory=get_datetime_utc, sa_type=DateTime(timezone=True))  # type: ignore
    updated_at: datetime = Field(default_factory=get_datetime_utc, sa_type=DateTime(timezone=True))  # type: ignore


class PdEcrLeaderReviewTaskBase(SQLModel):
    department: str = Field(index=True, min_length=1, max_length=64)
    status: str = Field(default="pending", index=True, max_length=32)
    reviewer_id: uuid.UUID | None = Field(default=None, foreign_key="user.id", index=True)
    reviewer_email: str | None = Field(default=None, index=True, max_length=255)
    reviewer_name: str | None = Field(default=None, max_length=255)
    review_comment: str | None = Field(default=None, sa_column=Column(Text))
    signature_name: str | None = Field(default=None, max_length=255)
    reviewed_at: datetime | None = Field(default=None, sa_type=DateTime(timezone=True))  # type: ignore


class PdEcrLeaderReviewTask(PdEcrLeaderReviewTaskBase, table=True):
    __tablename__ = "pd_ecr_leader_review_task"
    __table_args__ = (
        UniqueConstraint("case_id", "department", name="uq_pd_ecr_leader_task_case_dept"),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    case_id: uuid.UUID = Field(foreign_key="pd_ecr_case.id", index=True, nullable=False)
    created_at: datetime = Field(default_factory=get_datetime_utc, sa_type=DateTime(timezone=True))  # type: ignore
    updated_at: datetime = Field(default_factory=get_datetime_utc, sa_type=DateTime(timezone=True))  # type: ignore


# ── Manager approval task (P0: initiator → manager approve → AI generate) ──


class PdEcrApprovalTaskBase(SQLModel):
    """Tracks manager approval for a submitted PD-ECR case."""
    status: str = Field(default="pending", index=True, max_length=32)  # pending | approved | rejected
    approver_id: uuid.UUID | None = Field(default=None, foreign_key="user.id", index=True)
    approver_email: str | None = Field(default=None, max_length=255)
    approver_name: str | None = Field(default=None, max_length=255)
    rejection_reason: str | None = Field(default=None, sa_column=Column(Text))
    approved_at: datetime | None = Field(default=None, sa_type=DateTime(timezone=True))  # type: ignore


class PdEcrApprovalTask(PdEcrApprovalTaskBase, table=True):
    __tablename__ = "pd_ecr_approval_task"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    case_id: uuid.UUID = Field(foreign_key="pd_ecr_case.id", index=True, nullable=False)
    created_at: datetime = Field(default_factory=get_datetime_utc, sa_type=DateTime(timezone=True))  # type: ignore
    updated_at: datetime = Field(default_factory=get_datetime_utc, sa_type=DateTime(timezone=True))  # type: ignore


class PdEcrCommentBase(SQLModel):
    target_type: str = Field(default="case", index=True, max_length=32)
    target_id: str | None = Field(default=None, index=True, max_length=255)
    body: str = Field(sa_column=Column(Text, nullable=False))


class PdEcrComment(PdEcrCommentBase, table=True):
    __tablename__ = "pd_ecr_comment"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    case_id: uuid.UUID = Field(foreign_key="pd_ecr_case.id", index=True, nullable=False)
    author_id: uuid.UUID | None = Field(default=None, foreign_key="user.id", index=True)
    created_at: datetime = Field(default_factory=get_datetime_utc, sa_type=DateTime(timezone=True))  # type: ignore


class PdEcrAttachmentBase(SQLModel):
    filename: str = Field(max_length=500)
    stored_path: str = Field(max_length=1000)
    content_type: str | None = Field(default=None, max_length=255)
    size_bytes: int | None = None
    target_type: str = Field(default="case", max_length=32)
    target_id: str | None = Field(default=None, max_length=255)


class PdEcrAttachment(PdEcrAttachmentBase, table=True):
    __tablename__ = "pd_ecr_attachment"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    case_id: uuid.UUID = Field(foreign_key="pd_ecr_case.id", index=True, nullable=False)
    uploaded_by_id: uuid.UUID | None = Field(default=None, foreign_key="user.id", index=True)
    created_at: datetime = Field(default_factory=get_datetime_utc, sa_type=DateTime(timezone=True))  # type: ignore


class PdEcrVersionBase(SQLModel):
    entity_type: str = Field(index=True, max_length=64)
    entity_id: str = Field(index=True, max_length=255)
    version: int = Field(index=True)
    snapshot: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    diff_metadata: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))


class PdEcrVersion(PdEcrVersionBase, table=True):
    __tablename__ = "pd_ecr_version"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    case_id: uuid.UUID = Field(foreign_key="pd_ecr_case.id", index=True, nullable=False)
    created_by_id: uuid.UUID | None = Field(default=None, foreign_key="user.id", index=True)
    created_at: datetime = Field(default_factory=get_datetime_utc, sa_type=DateTime(timezone=True))  # type: ignore


class PdEcrActivityBase(SQLModel):
    action: str = Field(index=True, max_length=128)
    target_type: str = Field(default="case", index=True, max_length=64)
    target_id: str | None = Field(default=None, index=True, max_length=255)
    message: str | None = Field(default=None, sa_column=Column(Text))
    metadata_json: dict[str, Any] = Field(
        default_factory=dict,
        sa_column=Column("metadata", JSON, nullable=False),
    )


class PdEcrActivity(PdEcrActivityBase, table=True):
    __tablename__ = "pd_ecr_activity"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    case_id: uuid.UUID | None = Field(default=None, foreign_key="pd_ecr_case.id", index=True)
    actor_id: uuid.UUID | None = Field(default=None, foreign_key="user.id", index=True)
    created_at: datetime = Field(default_factory=get_datetime_utc, sa_type=DateTime(timezone=True))  # type: ignore


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


class PdEcrCollaborationSessionBase(SQLModel):
    session_id: str = Field(index=True, max_length=255)
    user_label: str | None = Field(default=None, max_length=255)
    module_id: str | None = Field(default=None, index=True, max_length=128)
    field_path: str | None = Field(default=None, index=True, max_length=255)
    presence: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    last_seen_at: datetime = Field(default_factory=get_datetime_utc, sa_type=DateTime(timezone=True))  # type: ignore


class PdEcrCollaborationSession(PdEcrCollaborationSessionBase, table=True):
    __tablename__ = "pd_ecr_collaboration_session"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    case_id: uuid.UUID = Field(foreign_key="pd_ecr_case.id", index=True, nullable=False)
    user_id: uuid.UUID | None = Field(default=None, foreign_key="user.id", index=True)


class HistoricalSourceDocumentBase(SQLModel):
    source_file: str = Field(index=True, max_length=1000)
    source_path: str = Field(index=True, max_length=1500)
    source_kind: str = Field(default="unknown", index=True, max_length=64)
    content_hash: str | None = Field(default=None, index=True, max_length=128)
    extracted_metadata: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    import_warnings: list[str] = Field(default_factory=list, sa_column=Column(JSON, nullable=False))


class HistoricalSourceDocument(HistoricalSourceDocumentBase, table=True):
    __tablename__ = "historical_source_document"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    case_id: uuid.UUID | None = Field(default=None, foreign_key="pd_ecr_case.id", index=True)
    imported_by_id: uuid.UUID | None = Field(default=None, foreign_key="user.id", index=True)
    imported_at: datetime = Field(default_factory=get_datetime_utc, sa_type=DateTime(timezone=True))  # type: ignore


# ══════════════════════════════════════════════════════════════════════════
# Staged Document — holds AI-parsed content awaiting human review before
# being committed to PdEcrCase + knowledge base.
# ══════════════════════════════════════════════════════════════════════════

class PdEcrStagedDocumentBase(SQLModel):
    status: str = Field(default="pending", index=True, max_length=32)
    original_filename: str = Field(max_length=500)
    original_file_path: str = Field(max_length=1500)
    preview_pdf_path: str | None = Field(default=None, max_length=1500)
    file_type: str = Field(default="unknown", max_length=32)  # pdf / excel / word

    # ── AI-parsed content (user can edit before confirming) ──
    parsed_text: str = Field(default="", sa_column=Column(Text))
    metadata_json: dict[str, Any] = Field(
        default_factory=dict, sa_column=Column(JSON, nullable=False)
    )
    sections_json: list[dict[str, Any]] = Field(
        default_factory=list, sa_column=Column(JSON, nullable=False)
    )
    tables_json: list[dict[str, Any]] = Field(
        default_factory=list, sa_column=Column(JSON, nullable=False)
    )


class PdEcrStagedDocument(PdEcrStagedDocumentBase, table=True):
    __tablename__ = "pd_ecr_staged_document"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    created_by_id: uuid.UUID | None = Field(default=None, foreign_key="user.id", index=True)
    created_at: datetime = Field(default_factory=get_datetime_utc, sa_type=DateTime(timezone=True))  # type: ignore
    updated_at: datetime = Field(default_factory=get_datetime_utc, sa_type=DateTime(timezone=True))  # type: ignore
    confirmed_at: datetime | None = Field(default=None, sa_type=DateTime(timezone=True))  # type: ignore
    confirmed_case_id: uuid.UUID | None = Field(default=None, foreign_key="pd_ecr_case.id", index=True)


# ── Pydantic-only models for the review API ──

class PdEcrStagedDocumentUpdate(SQLModel):
    """Fields the user can edit during review."""
    metadata_json: dict[str, Any] | None = None
    sections_json: list[dict[str, Any]] | None = None
    tables_json: list[dict[str, Any]] | None = None


PdEcrMetadataSpec: dict[str, dict[str, str]] = {
    "case_no":    {"label": "案例编号", "zh": "案例编号"},
    "dc_no":      {"label": "DC No", "zh": "DC编号"},
    "mcr_no":     {"label": "MCR No", "zh": "MCR编号"},
    "date":       {"label": "日期", "zh": "日期"},
    "customer_project": {"label": "Customer Project", "zh": "客户项目"},
    "product_no": {"label": "Product No", "zh": "产品号"},
    "part_no":    {"label": "Part No / Component No", "zh": "零部件号"},
    "change_type": {"label": "Change Type", "zh": "变更类型"},
    "change_source": {"label": "Change Source", "zh": "变更来源"},
    "sample_type": {"label": "Sample Status", "zh": "样件状态"},
    "initiator":  {"label": "Initiator", "zh": "发起人"},
    "reason":     {"label": "Reason for Change", "zh": "变更原因"},
    "change_proposal": {"label": "Change Proposal", "zh": "变更描述"},
    "current_design": {"label": "Current Design", "zh": "当前设计"},
    "remarks":    {"label": "Remarks", "zh": "备注"},
}


class PdEcrCaseCreate(PdEcrCaseBase):
    modules: list[dict[str, Any]] | None = None


class PdEcrCaseUpdate(SQLModel):
    title: str | None = None
    status: str | None = None
    owner_id: uuid.UUID | None = None
    dc_no: str | None = None
    mcr_no: str | None = None
    customer_project: str | None = None
    product_no: str | None = None
    part_no: str | None = None
    change_type: str | None = None
    sample_type: str | None = None
    initiator: str | None = None
    target_close_date: datetime | None = None


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


class PdEcrTaskCreate(PdEcrTaskBase):
    assignee_id: uuid.UUID | None = None


class PdEcrCommentCreate(PdEcrCommentBase):
    pass
