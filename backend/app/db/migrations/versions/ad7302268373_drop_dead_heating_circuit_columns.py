"""drop_dead_heating_circuit_columns

Revision ID: ad7302268373
Revises:
Create Date: 2026-03-08 21:12:42.981992

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'ad7302268373'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Only columns that actually exist in the DB (the other dead columns were
# in the SQLAlchemy model but never reached the DB via create_all)
COLUMNS_TO_DROP = [
    "supply_sensor_id",
    "return_sensor_id",
    "pressure_sensor_id",
    "pressure_mount_point_id",
]


def upgrade() -> None:
    with op.batch_alter_table("heating_circuits") as batch_op:
        for col in COLUMNS_TO_DROP:
            batch_op.drop_column(col)


def downgrade() -> None:
    with op.batch_alter_table("heating_circuits") as batch_op:
        batch_op.add_column(sa.Column("pressure_mount_point_id", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("pressure_sensor_id", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("return_sensor_id", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("supply_sensor_id", sa.Integer(), nullable=True))
