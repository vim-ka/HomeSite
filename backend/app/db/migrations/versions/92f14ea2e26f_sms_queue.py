"""sms queue

Revision ID: 92f14ea2e26f
Revises: d70d93fe6cff
Create Date: 2026-11-12 11:34:27.010886

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '92f14ea2e26f'
down_revision: Union[str, None] = 'd70d93fe6cff'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # SMS queue: per-(problem, user) state, queue items, merged messages
    op.create_table('sms_message',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('phone', sa.String(length=16), nullable=False),
    sa.Column('text', sa.Text(), nullable=False),
    sa.Column('is_test', sa.Boolean(), nullable=False),
    sa.Column('state', sa.String(length=16), nullable=False),
    sa.Column('items', sa.Integer(), nullable=False),
    sa.Column('attempts', sa.Integer(), nullable=False),
    sa.Column('error', sa.Text(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('ready_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('leased_until', sa.DateTime(timezone=True), nullable=True),
    sa.Column('sent_at', sa.DateTime(timezone=True), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_sms_message_created_at'), 'sms_message', ['created_at'], unique=False)
    op.create_index('ix_sms_message_state_ready', 'sms_message', ['state', 'ready_at'], unique=False)
    op.create_table('sms_item',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('problem', sa.String(length=64), nullable=False),
    sa.Column('code', sa.String(length=64), nullable=False),
    sa.Column('level', sa.String(length=10), nullable=False),
    sa.Column('raised', sa.Boolean(), nullable=False),
    sa.Column('kind', sa.String(length=16), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=True),
    sa.Column('phone', sa.String(length=16), nullable=False),
    sa.Column('text', sa.Text(), nullable=False),
    sa.Column('is_test', sa.Boolean(), nullable=False),
    sa.Column('state', sa.String(length=16), nullable=False),
    sa.Column('message_id', sa.Integer(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('ready_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['message_id'], ['sms_message.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_sms_item_created_at'), 'sms_item', ['created_at'], unique=False)
    op.create_index(op.f('ix_sms_item_message_id'), 'sms_item', ['message_id'], unique=False)
    op.create_index('ix_sms_item_problem_user', 'sms_item', ['problem', 'user_id'], unique=False)
    op.create_index('ix_sms_item_state_ready', 'sms_item', ['state', 'ready_at'], unique=False)
    op.create_table('sms_subscription',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('problem', sa.String(length=64), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('sent', sa.String(length=10), nullable=True),
    sa.Column('seen', sa.String(length=10), nullable=True),
    sa.Column('changes', sa.Integer(), nullable=False),
    sa.Column('episode_start', sa.DateTime(timezone=True), nullable=True),
    sa.Column('last_text', sa.Text(), nullable=False),
    sa.Column('code', sa.String(length=64), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('problem', 'user_id', name='uq_sms_subscription_problem_user')
    )
    op.create_index(op.f('ix_sms_subscription_user_id'), 'sms_subscription', ['user_id'], unique=False)
    # ### end Alembic commands ###


def downgrade() -> None:
    # SMS queue: per-(problem, user) state, queue items, merged messages
    op.drop_index(op.f('ix_sms_subscription_user_id'), table_name='sms_subscription')
    op.drop_table('sms_subscription')
    op.drop_index('ix_sms_item_state_ready', table_name='sms_item')
    op.drop_index('ix_sms_item_problem_user', table_name='sms_item')
    op.drop_index(op.f('ix_sms_item_message_id'), table_name='sms_item')
    op.drop_index(op.f('ix_sms_item_created_at'), table_name='sms_item')
    op.drop_table('sms_item')
    op.drop_index('ix_sms_message_state_ready', table_name='sms_message')
    op.drop_index(op.f('ix_sms_message_created_at'), table_name='sms_message')
    op.drop_table('sms_message')
    # ### end Alembic commands ###
