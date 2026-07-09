"""Add section/module_id/uploaded_by_name to PD-ECR attachments

Enables business-classified, module-scoped attachment persistence
(Phase 3: attachments move from frontend localStorage to the backend).

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-07-07 01:00:00.000000

"""

from alembic import op
import sqlalchemy as sa


revision = "b2c3d4e5f6a7"
down_revision = "a1b2c3d4e5f6"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("pd_ecr_attachment") as batch_op:
        batch_op.add_column(
            sa.Column("section", sa.String(length=32), nullable=False, server_default="other")
        )
        batch_op.add_column(
            sa.Column("module_id", sa.String(length=255), nullable=True)
        )
        batch_op.add_column(
            sa.Column("uploaded_by_name", sa.String(length=255), nullable=True)
        )
        batch_op.create_index(
            "ix_pd_ecr_attachment_section", ["section"], unique=False
        )
        batch_op.create_index(
            "ix_pd_ecr_attachment_module_id", ["module_id"], unique=False
        )


def downgrade():
    with op.batch_alter_table("pd_ecr_attachment") as batch_op:
        batch_op.drop_index("ix_pd_ecr_attachment_module_id")
        batch_op.drop_index("ix_pd_ecr_attachment_section")
        batch_op.drop_column("uploaded_by_name")
        batch_op.drop_column("module_id")
        batch_op.drop_column("section")
