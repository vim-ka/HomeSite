"""baseline schema

Revision ID: 0a1b2c3d4e5f
Revises:
Create Date: 2026-09-26 12:00:00.000000

The original schema was created by ``Base.metadata.create_all`` and the first
real migration (ad7302268373) only altered existing tables, so ``alembic
upgrade head`` could not build a database from scratch (e.g. a fresh
PostgreSQL for the SQLite → PG migration).

On an empty database this creates the current schema from the models; the
later migrations then detect that their changes are already in place and skip.
On an existing database (already stamped at a later revision) it never runs.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0a1b2c3d4e5f"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    from app.models import Base

    conn = op.get_bind()
    existing = set(sa.inspect(conn).get_table_names()) - {"alembic_version"}
    if existing:
        # Pre-Alembic database: tables exist, let the following migrations adjust them
        return
    Base.metadata.create_all(bind=conn)


def downgrade() -> None:
    pass
