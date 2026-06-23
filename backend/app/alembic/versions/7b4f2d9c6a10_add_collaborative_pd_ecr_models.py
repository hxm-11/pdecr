"""Add collaborative PD-ECR models

Revision ID: 7b4f2d9c6a10
Revises: fe56fa70289e
Create Date: 2026-06-17 10:00:00.000000

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "7b4f2d9c6a10"
down_revision = "fe56fa70289e"
branch_labels = None
depends_on = None


uuid_type = postgresql.UUID(as_uuid=True)


def upgrade():
    op.add_column("user", sa.Column("auth_provider", sa.String(length=32), nullable=True))
    op.add_column("user", sa.Column("external_subject", sa.String(length=255), nullable=True))
    op.add_column("user", sa.Column("department", sa.String(length=255), nullable=True))
    op.add_column("user", sa.Column("display_name", sa.String(length=255), nullable=True))
    op.create_index("ix_user_external_subject", "user", ["external_subject"], unique=False)
    op.execute("UPDATE \"user\" SET auth_provider = 'local' WHERE auth_provider IS NULL")
    op.alter_column("user", "auth_provider", nullable=False)

    op.create_table(
        "pd_ecr_case",
        sa.Column("case_no", sa.String(length=255), nullable=False),
        sa.Column("title", sa.String(length=500), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("source_type", sa.String(length=64), nullable=False),
        sa.Column("is_historical", sa.Boolean(), nullable=False),
        sa.Column("dc_no", sa.String(length=255), nullable=True),
        sa.Column("mcr_no", sa.String(length=255), nullable=True),
        sa.Column("customer_project", sa.String(length=255), nullable=True),
        sa.Column("product_no", sa.String(length=255), nullable=True),
        sa.Column("part_no", sa.String(length=255), nullable=True),
        sa.Column("change_type", sa.String(length=255), nullable=True),
        sa.Column("sample_type", sa.String(length=255), nullable=True),
        sa.Column("initiator", sa.String(length=255), nullable=True),
        sa.Column("target_close_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", uuid_type, nullable=False),
        sa.Column("created_by_id", uuid_type, nullable=True),
        sa.Column("owner_id", uuid_type, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["created_by_id"], ["user.id"]),
        sa.ForeignKeyConstraint(["owner_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("case_no", name="uq_pd_ecr_case_case_no"),
    )
    for column in (
        "case_no",
        "status",
        "source_type",
        "is_historical",
        "dc_no",
        "mcr_no",
        "customer_project",
        "product_no",
        "part_no",
        "change_type",
        "created_by_id",
        "owner_id",
    ):
        op.create_index(f"ix_pd_ecr_case_{column}", "pd_ecr_case", [column], unique=False)

    op.create_table(
        "pd_ecr_module",
        sa.Column("module_id", sa.String(length=128), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("content_json", sa.JSON(), nullable=False),
        sa.Column("content_md", sa.Text(), nullable=True),
        sa.Column("source_cases", sa.JSON(), nullable=False),
        sa.Column("source_files", sa.JSON(), nullable=False),
        sa.Column("needs_human_input", sa.Boolean(), nullable=False),
        sa.Column("status", sa.String(length=64), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("id", uuid_type, nullable=False),
        sa.Column("case_id", uuid_type, nullable=False),
        sa.Column("updated_by_id", uuid_type, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["case_id"], ["pd_ecr_case.id"]),
        sa.ForeignKeyConstraint(["updated_by_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("case_id", "module_id", name="uq_pd_ecr_module_case_module"),
    )
    op.create_index("ix_pd_ecr_module_case_id", "pd_ecr_module", ["case_id"], unique=False)
    op.create_index("ix_pd_ecr_module_module_id", "pd_ecr_module", ["module_id"], unique=False)
    op.create_index("ix_pd_ecr_module_status", "pd_ecr_module", ["status"], unique=False)
    op.create_index("ix_pd_ecr_module_updated_by_id", "pd_ecr_module", ["updated_by_id"], unique=False)

    op.create_table(
        "pd_ecr_task",
        sa.Column("module_id", sa.String(length=128), nullable=True),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("due_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", uuid_type, nullable=False),
        sa.Column("case_id", uuid_type, nullable=False),
        sa.Column("assignee_id", uuid_type, nullable=True),
        sa.Column("created_by_id", uuid_type, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["assignee_id"], ["user.id"]),
        sa.ForeignKeyConstraint(["case_id"], ["pd_ecr_case.id"]),
        sa.ForeignKeyConstraint(["created_by_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    for column in ("module_id", "status", "case_id", "assignee_id", "created_by_id"):
        op.create_index(f"ix_pd_ecr_task_{column}", "pd_ecr_task", [column], unique=False)

    op.create_table(
        "pd_ecr_comment",
        sa.Column("target_type", sa.String(length=32), nullable=False),
        sa.Column("target_id", sa.String(length=255), nullable=True),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("id", uuid_type, nullable=False),
        sa.Column("case_id", uuid_type, nullable=False),
        sa.Column("author_id", uuid_type, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["author_id"], ["user.id"]),
        sa.ForeignKeyConstraint(["case_id"], ["pd_ecr_case.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    for column in ("target_type", "target_id", "case_id", "author_id"):
        op.create_index(f"ix_pd_ecr_comment_{column}", "pd_ecr_comment", [column], unique=False)

    op.create_table(
        "pd_ecr_attachment",
        sa.Column("filename", sa.String(length=500), nullable=False),
        sa.Column("stored_path", sa.String(length=1000), nullable=False),
        sa.Column("content_type", sa.String(length=255), nullable=True),
        sa.Column("size_bytes", sa.Integer(), nullable=True),
        sa.Column("target_type", sa.String(length=32), nullable=False),
        sa.Column("target_id", sa.String(length=255), nullable=True),
        sa.Column("id", uuid_type, nullable=False),
        sa.Column("case_id", uuid_type, nullable=False),
        sa.Column("uploaded_by_id", uuid_type, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["case_id"], ["pd_ecr_case.id"]),
        sa.ForeignKeyConstraint(["uploaded_by_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_pd_ecr_attachment_case_id", "pd_ecr_attachment", ["case_id"], unique=False)
    op.create_index("ix_pd_ecr_attachment_uploaded_by_id", "pd_ecr_attachment", ["uploaded_by_id"], unique=False)

    op.create_table(
        "pd_ecr_version",
        sa.Column("entity_type", sa.String(length=64), nullable=False),
        sa.Column("entity_id", sa.String(length=255), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("snapshot", sa.JSON(), nullable=False),
        sa.Column("diff_metadata", sa.JSON(), nullable=False),
        sa.Column("id", uuid_type, nullable=False),
        sa.Column("case_id", uuid_type, nullable=False),
        sa.Column("created_by_id", uuid_type, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["case_id"], ["pd_ecr_case.id"]),
        sa.ForeignKeyConstraint(["created_by_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    for column in ("entity_type", "entity_id", "version", "case_id", "created_by_id"):
        op.create_index(f"ix_pd_ecr_version_{column}", "pd_ecr_version", [column], unique=False)

    op.create_table(
        "pd_ecr_activity",
        sa.Column("action", sa.String(length=128), nullable=False),
        sa.Column("target_type", sa.String(length=64), nullable=False),
        sa.Column("target_id", sa.String(length=255), nullable=True),
        sa.Column("message", sa.Text(), nullable=True),
        sa.Column("metadata", sa.JSON(), nullable=False),
        sa.Column("id", uuid_type, nullable=False),
        sa.Column("case_id", uuid_type, nullable=True),
        sa.Column("actor_id", uuid_type, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["actor_id"], ["user.id"]),
        sa.ForeignKeyConstraint(["case_id"], ["pd_ecr_case.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    for column in ("action", "target_type", "target_id", "case_id", "actor_id"):
        op.create_index(f"ix_pd_ecr_activity_{column}", "pd_ecr_activity", [column], unique=False)

    op.create_table(
        "pd_ecr_collaboration_session",
        sa.Column("session_id", sa.String(length=255), nullable=False),
        sa.Column("user_label", sa.String(length=255), nullable=True),
        sa.Column("module_id", sa.String(length=128), nullable=True),
        sa.Column("field_path", sa.String(length=255), nullable=True),
        sa.Column("presence", sa.JSON(), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", uuid_type, nullable=False),
        sa.Column("case_id", uuid_type, nullable=False),
        sa.Column("user_id", uuid_type, nullable=True),
        sa.ForeignKeyConstraint(["case_id"], ["pd_ecr_case.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    for column in ("session_id", "module_id", "field_path", "case_id", "user_id"):
        op.create_index(f"ix_pd_ecr_collaboration_session_{column}", "pd_ecr_collaboration_session", [column], unique=False)

    op.create_table(
        "historical_source_document",
        sa.Column("source_file", sa.String(length=1000), nullable=False),
        sa.Column("source_path", sa.String(length=1500), nullable=False),
        sa.Column("source_kind", sa.String(length=64), nullable=False),
        sa.Column("content_hash", sa.String(length=128), nullable=True),
        sa.Column("extracted_metadata", sa.JSON(), nullable=False),
        sa.Column("import_warnings", sa.JSON(), nullable=False),
        sa.Column("id", uuid_type, nullable=False),
        sa.Column("case_id", uuid_type, nullable=True),
        sa.Column("imported_by_id", uuid_type, nullable=True),
        sa.Column("imported_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["case_id"], ["pd_ecr_case.id"]),
        sa.ForeignKeyConstraint(["imported_by_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    for column in ("source_file", "source_path", "source_kind", "content_hash", "case_id", "imported_by_id"):
        op.create_index(f"ix_historical_source_document_{column}", "historical_source_document", [column], unique=False)


def downgrade():
    op.drop_table("historical_source_document")
    op.drop_table("pd_ecr_collaboration_session")
    op.drop_table("pd_ecr_activity")
    op.drop_table("pd_ecr_version")
    op.drop_table("pd_ecr_attachment")
    op.drop_table("pd_ecr_comment")
    op.drop_table("pd_ecr_task")
    op.drop_table("pd_ecr_module")
    op.drop_table("pd_ecr_case")
    op.drop_index("ix_user_external_subject", table_name="user")
    op.drop_column("user", "display_name")
    op.drop_column("user", "department")
    op.drop_column("user", "external_subject")
    op.drop_column("user", "auth_provider")
