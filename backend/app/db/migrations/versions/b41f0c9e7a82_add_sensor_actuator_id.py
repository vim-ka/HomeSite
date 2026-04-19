"""add sensor.actuator_id FK → actuators.id

Revision ID: b41f0c9e7a82
Revises: ad7302268373
Create Date: 2026-04-18 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "b41f0c9e7a82"
down_revision: Union[str, None] = "ad7302268373"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()

    existing_cols = {row[1] for row in conn.execute(sa.text("PRAGMA table_info(sensors)"))}
    if "actuator_id" not in existing_cols:
        with op.batch_alter_table("sensors") as batch_op:
            batch_op.add_column(sa.Column("actuator_id", sa.Integer(), nullable=True))
            batch_op.create_foreign_key(
                "fk_sensors_actuator_id",
                "actuators",
                ["actuator_id"],
                ["id"],
            )

    # Backfill: existing temperature sensors (sensor_type_id=1, the DS18B20s)
    # are wired to the boiler ESP32. Look up its id by mqtt_device_name to be
    # robust against renumbering.
    boiler_id_row = conn.execute(
        sa.text("SELECT id FROM actuators WHERE mqtt_device_name = 'boiler_unit'")
    ).first()
    if boiler_id_row is not None:
        boiler_id = boiler_id_row[0]
        conn.execute(
            sa.text(
                "UPDATE sensors SET actuator_id = :aid "
                "WHERE actuator_id IS NULL AND sensor_type_id = 1"
            ),
            {"aid": boiler_id},
        )


def downgrade() -> None:
    with op.batch_alter_table("sensors") as batch_op:
        batch_op.drop_constraint("fk_sensors_actuator_id", type_="foreignkey")
        batch_op.drop_column("actuator_id")
