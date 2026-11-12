"""user sms

Revision ID: d70d93fe6cff
Revises: d93b5812a710
Create Date: 2026-11-12 10:48:09.726053

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd70d93fe6cff'
down_revision: Union[str, None] = 'd93b5812a710'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # users.sms_categories: comma-separated SMS categories
    op.add_column('users', sa.Column('phone', sa.String(length=16), nullable=True))
    op.add_column('users', sa.Column('sms_categories', sa.String(length=64), server_default='', nullable=False))
    # ### end Alembic commands ###


def downgrade() -> None:
    # users.sms_categories: comma-separated SMS categories
    op.drop_column('users', 'sms_categories')
    op.drop_column('users', 'phone')
    # ### end Alembic commands ###
