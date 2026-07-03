"""Add Flowable runtime fields for PD-ECR approvals

Revision ID: 4f7b2c8a91e1
Revises: 2c8d4f6a1b90
Create Date: 2026-07-02 00:00:00.000000

"""

from alembic import op
import sqlalchemy as sa


revision = "4f7b2c8a91e1"
down_revision = "2c8d4f6a1b90"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("pd_ecr_case") as batch_op:
        batch_op.add_column(
            sa.Column("flowable_process_instance_id", sa.String(length=128), nullable=True)
        )
        batch_op.add_column(
            sa.Column("flowable_process_definition_key", sa.String(length=255), nullable=True)
        )
        batch_op.add_column(
            sa.Column("flowable_business_key", sa.String(length=255), nullable=True)
        )
        batch_op.add_column(
            sa.Column("flowable_status", sa.String(length=64), nullable=True)
        )
        batch_op.add_column(
            sa.Column("flowable_last_synced_at", sa.DateTime(timezone=True), nullable=True)
        )
        batch_op.create_index(
            "ix_pd_ecr_case_flowable_process_instance_id",
            ["flowable_process_instance_id"],
            unique=False,
        )
        batch_op.create_index(
            "ix_pd_ecr_case_flowable_business_key",
            ["flowable_business_key"],
            unique=False,
        )

    with op.batch_alter_table("pd_ecr_approval_task") as batch_op:
        batch_op.add_column(
            sa.Column("flowable_task_id", sa.String(length=128), nullable=True)
        )
        batch_op.add_column(
            sa.Column("flowable_task_definition_key", sa.String(length=255), nullable=True)
        )
        batch_op.create_index(
            "ix_pd_ecr_approval_task_flowable_task_id",
            ["flowable_task_id"],
            unique=False,
        )


def downgrade():
    with op.batch_alter_table("pd_ecr_approval_task") as batch_op:
        batch_op.drop_index("ix_pd_ecr_approval_task_flowable_task_id")
        batch_op.drop_column("flowable_task_definition_key")
        batch_op.drop_column("flowable_task_id")

    with op.batch_alter_table("pd_ecr_case") as batch_op:
        batch_op.drop_index("ix_pd_ecr_case_flowable_business_key")
        batch_op.drop_index("ix_pd_ecr_case_flowable_process_instance_id")
        batch_op.drop_column("flowable_last_synced_at")
        batch_op.drop_column("flowable_status")
        batch_op.drop_column("flowable_business_key")
        batch_op.drop_column("flowable_process_definition_key")
        batch_op.drop_column("flowable_process_instance_id")
