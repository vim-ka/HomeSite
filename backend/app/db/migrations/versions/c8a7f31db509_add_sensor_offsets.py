"""add sensor_offsets table

Revision ID: c8a7f31db509
Revises: b41f0c9e7a82
Create Date: 2026-04-18 12:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c8a7f31db509"
down_revision: Union[str, None] = "b41f0c9e7a82"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    existing = {row[0] for row in conn.execute(
        sa.text("SELECT name FROM sqlite_master WHERE type='table'")
    )}
    if "sensor_offsets" in existing:
        return

    op.create_table(
        "sensor_offsets",
        sa.Column("sensor_id", sa.Integer(), nullable=False),
        sa.Column("datatype_id", sa.Integer(), nullable=False),
        sa.Column("value", sa.Float(), nullable=False, server_default="0.0"),
        sa.ForeignKeyConstraint(["sensor_id"], ["sensors.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["datatype_id"], ["sensor_data_types.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("sensor_id", "datatype_id"),
    )


def downgrade() -> None:
    op.drop_table("sensor_offsets")
