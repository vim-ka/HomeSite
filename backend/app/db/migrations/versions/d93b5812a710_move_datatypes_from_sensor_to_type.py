"""move datatypes from sensor to sensor_type

Revision ID: d93b5812a710
Revises: c8a7f31db509
Create Date: 2026-04-18 23:40:00.000000

Normalisation: a sensor's measurable data types are a property of its
hardware type, not of the individual physical sensor. We create a new
``sensor_type_datatype_link`` table, backfill it with the union of
datatype ids across all sensors of each type, and drop the per-sensor
``sensor_datatype_link`` table.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "d93b5812a710"
down_revision: Union[str, None] = "c8a7f31db509"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    existing = {row[0] for row in conn.execute(
        sa.text("SELECT name FROM sqlite_master WHERE type='table'")
    )}

    if "sensor_type_datatype_link" not in existing:
        op.create_table(
            "sensor_type_datatype_link",
            sa.Column("sensor_type_id", sa.Integer(), nullable=False),
            sa.Column("datatype_id", sa.Integer(), nullable=False),
            sa.ForeignKeyConstraint(["sensor_type_id"], ["sensor_types.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["datatype_id"], ["sensor_data_types.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("sensor_type_id", "datatype_id"),
        )

    # Backfill: union of datatype_ids over every sensor of a given type.
    if "sensor_datatype_link" in existing:
        conn.execute(sa.text(
            """
            INSERT OR IGNORE INTO sensor_type_datatype_link (sensor_type_id, datatype_id)
            SELECT DISTINCT s.sensor_type_id, sdl.datatype_id
              FROM sensor_datatype_link sdl
              JOIN sensors s ON s.id = sdl.sensor_id
            """
        ))
        op.drop_table("sensor_datatype_link")


def downgrade() -> None:
    conn = op.get_bind()
    existing = {row[0] for row in conn.execute(
        sa.text("SELECT name FROM sqlite_master WHERE type='table'")
    )}

    if "sensor_datatype_link" not in existing:
        op.create_table(
            "sensor_datatype_link",
            sa.Column("sensor_id", sa.Integer(), nullable=False),
            sa.Column("datatype_id", sa.Integer(), nullable=False),
            sa.ForeignKeyConstraint(["sensor_id"], ["sensors.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["datatype_id"], ["sensor_data_types.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("sensor_id", "datatype_id"),
        )

    # Restore per-sensor rows by expanding the per-type set back to every sensor.
    if "sensor_type_datatype_link" in existing:
        conn.execute(sa.text(
            """
            INSERT OR IGNORE INTO sensor_datatype_link (sensor_id, datatype_id)
            SELECT s.id, stdl.datatype_id
              FROM sensor_type_datatype_link stdl
              JOIN sensors s ON s.sensor_type_id = stdl.sensor_type_id
            """
        ))
        op.drop_table("sensor_type_datatype_link")
