"""add admin notifications

Revision ID: 9f4e2c1a7b31
Revises: 8932d379655b
Create Date: 2026-06-30 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa


revision = "9f4e2c1a7b31"
down_revision = "8932d379655b"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "admin_notifications",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("notification_type", sa.String(length=50), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("message", sa.Text(), nullable=True),
        sa.Column("booking_id", sa.Integer(), nullable=True),
        sa.Column("target_url", sa.String(length=500), nullable=True),
        sa.Column("is_read", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("read_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["booking_id"], ["bookings.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_admin_notifications_booking_id", "admin_notifications", ["booking_id"], unique=False)
    op.create_index("ix_admin_notifications_created_at", "admin_notifications", ["created_at"], unique=False)
    op.create_index("ix_admin_notifications_is_read", "admin_notifications", ["is_read"], unique=False)


def downgrade():
    op.drop_index("ix_admin_notifications_is_read", table_name="admin_notifications")
    op.drop_index("ix_admin_notifications_created_at", table_name="admin_notifications")
    op.drop_index("ix_admin_notifications_booking_id", table_name="admin_notifications")
    op.drop_table("admin_notifications")
