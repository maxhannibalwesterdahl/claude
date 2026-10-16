"""husk på retter og beskeder

Revision ID: 8c2e5d71a0f4
Revises: 4b1f0c2a9d37
Create Date: 2026-10-14 10:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = '8c2e5d71a0f4'
down_revision = '4b1f0c2a9d37'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table('meal_reminder',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('meal_id', sa.Integer(), nullable=False),
    sa.Column('text', sa.String(length=200), nullable=False),
    sa.Column('done', sa.Boolean(), nullable=False),
    sa.Column('sent_on', sa.Date(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['meal_id'], ['plan_meal.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('meal_reminder', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_meal_reminder_meal_id'), ['meal_id'], unique=False)

    op.create_table('push_subscription',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('endpoint', sa.String(length=1000), nullable=False),
    sa.Column('p256dh', sa.String(length=200), nullable=False),
    sa.Column('auth', sa.String(length=100), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['user.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('endpoint')
    )
    with op.batch_alter_table('push_subscription', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_push_subscription_user_id'), ['user_id'], unique=False)


def downgrade() -> None:
    with op.batch_alter_table('push_subscription', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_push_subscription_user_id'))
    op.drop_table('push_subscription')
    with op.batch_alter_table('meal_reminder', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_meal_reminder_meal_id'))
    op.drop_table('meal_reminder')
