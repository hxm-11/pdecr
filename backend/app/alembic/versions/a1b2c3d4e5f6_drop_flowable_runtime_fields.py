"""Drop Flowable runtime fields for PD-ECR approvals

V1 uses the internal state-machine approval only; the external Flowable/Activiti
engine integration was removed, so its runtime columns are dropped.

Revision ID: a1b2c3d4e5f6
Revises: 4f7b2c8a91e1
Create Date: 2026-07-07 00:00:00.000000

"""

from alembic import op
import sqlalchemy as sa


revision = "a1b2c3d4e5f6"
down_revision = "4f7b2c8a91e1"
branch_labels = None
depends_on = None


def upgrade():
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


def downgrade():
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
