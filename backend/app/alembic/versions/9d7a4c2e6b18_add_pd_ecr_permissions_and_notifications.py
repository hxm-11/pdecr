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
    op.add_column(
        "pd_ecr_module",
        sa.Column("assignee_email", sa.String(length=255), nullable=True),
    )
    op.add_column(
        "pd_ecr_module",
        sa.Column("assignee_name", sa.String(length=255), nullable=True),
    )
    op.add_column(
        "pd_ecr_module",
        sa.Column("department", sa.String(length=255), nullable=True),
    )
    op.add_column(
        "pd_ecr_module",
        sa.Column("due_date", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "pd_ecr_module",
        sa.Column("reminder_policy", sa.JSON(), nullable=True),
    )
    op.add_column(
        "pd_ecr_module",
        sa.Column("last_reminded_at", sa.DateTime(timezone=True), nullable=True),
    )
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
        op.create_index(
            f"ix_pd_ecr_module_{column}",
            "pd_ecr_module",
            [column],
            unique=False,
        )

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
    for column in (
        "module_id",
        "recipient_email",
        "notification_type",
        "status",
        "provider",
        "case_id",
    ):
        op.create_index(
            f"ix_pd_ecr_notification_{column}",
            "pd_ecr_notification",
            [column],
            unique=False,
        )


def downgrade():
    for column in (
        "case_id",
        "provider",
        "status",
        "notification_type",
        "recipient_email",
        "module_id",
    ):
        op.drop_index(f"ix_pd_ecr_notification_{column}", table_name="pd_ecr_notification")
    op.drop_table("pd_ecr_notification")

    for column in ("department", "assignee_email", "assignee_id"):
        op.drop_index(f"ix_pd_ecr_module_{column}", table_name="pd_ecr_module")
    op.drop_constraint(
        "fk_pd_ecr_module_assignee_id_user",
        "pd_ecr_module",
        type_="foreignkey",
    )
    op.drop_column("pd_ecr_module", "last_reminded_at")
    op.drop_column("pd_ecr_module", "reminder_policy")
    op.drop_column("pd_ecr_module", "due_date")
    op.drop_column("pd_ecr_module", "department")
    op.drop_column("pd_ecr_module", "assignee_name")
    op.drop_column("pd_ecr_module", "assignee_email")
    op.drop_column("pd_ecr_module", "assignee_id")
    op.drop_index("ix_user_pd_ecr_role", table_name="user")
    op.drop_column("user", "pd_ecr_role")
