"""Add PD-ECR workflow tasks

Revision ID: 2c8d4f6a1b90
Revises: 9d7a4c2e6b18
Create Date: 2026-06-25 00:00:00.000000

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "2c8d4f6a1b90"
down_revision = "9d7a4c2e6b18"
branch_labels = None
depends_on = None


uuid_type = postgresql.UUID(as_uuid=True)


def upgrade():
    op.create_table(
        "pd_ecr_department_task",
        sa.Column("department", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("assignee_id", uuid_type, nullable=True),
        sa.Column("assignee_email", sa.String(length=255), nullable=True),
        sa.Column("assignee_name", sa.String(length=255), nullable=True),
        sa.Column("impact_result", sa.String(length=64), nullable=True),
        sa.Column("impact_remark", sa.Text(), nullable=True),
        sa.Column("action_required", sa.Text(), nullable=True),
        sa.Column("confirmed_by_id", uuid_type, nullable=True),
        sa.Column("confirmed_by_name", sa.String(length=255), nullable=True),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("due_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", uuid_type, nullable=False),
        sa.Column("case_id", uuid_type, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["assignee_id"], ["user.id"]),
        sa.ForeignKeyConstraint(["case_id"], ["pd_ecr_case.id"]),
        sa.ForeignKeyConstraint(["confirmed_by_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("case_id", "department", name="uq_pd_ecr_dept_task_case_dept"),
    )
    for column in (
        "department",
        "status",
        "assignee_id",
        "assignee_email",
        "confirmed_by_id",
        "case_id",
    ):
        op.create_index(
            f"ix_pd_ecr_department_task_{column}",
            "pd_ecr_department_task",
            [column],
            unique=False,
        )

    op.create_table(
        "pd_ecr_leader_review_task",
        sa.Column("department", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("reviewer_id", uuid_type, nullable=True),
        sa.Column("reviewer_email", sa.String(length=255), nullable=True),
        sa.Column("reviewer_name", sa.String(length=255), nullable=True),
        sa.Column("review_comment", sa.Text(), nullable=True),
        sa.Column("signature_name", sa.String(length=255), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", uuid_type, nullable=False),
        sa.Column("case_id", uuid_type, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["case_id"], ["pd_ecr_case.id"]),
        sa.ForeignKeyConstraint(["reviewer_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("case_id", "department", name="uq_pd_ecr_leader_task_case_dept"),
    )
    for column in (
        "department",
        "status",
        "reviewer_id",
        "reviewer_email",
        "case_id",
    ):
        op.create_index(
            f"ix_pd_ecr_leader_review_task_{column}",
            "pd_ecr_leader_review_task",
            [column],
            unique=False,
        )


def downgrade():
    for column in (
        "case_id",
        "reviewer_email",
        "reviewer_id",
        "status",
        "department",
    ):
        op.drop_index(
            f"ix_pd_ecr_leader_review_task_{column}",
            table_name="pd_ecr_leader_review_task",
        )
    op.drop_table("pd_ecr_leader_review_task")

    for column in (
        "case_id",
        "confirmed_by_id",
        "assignee_email",
        "assignee_id",
        "status",
        "department",
    ):
        op.drop_index(
            f"ix_pd_ecr_department_task_{column}",
            table_name="pd_ecr_department_task",
        )
    op.drop_table("pd_ecr_department_task")
