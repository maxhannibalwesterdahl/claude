"""husk: egne tidspunkter pr. påmindelse

Revision ID: a3f7c0d9e512
Revises: 8c2e5d71a0f4
Create Date: 2026-10-14 15:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = 'a3f7c0d9e512'
down_revision = '8c2e5d71a0f4'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Eksisterende påmindelser får standardtiderne (tom = standard).
    with op.batch_alter_table('meal_reminder', schema=None) as batch_op:
        batch_op.add_column(sa.Column('first_time', sa.String(length=5), nullable=True))
        batch_op.add_column(sa.Column('again_time', sa.String(length=5), nullable=True))
        batch_op.add_column(sa.Column('again_on', sa.Boolean(), server_default=sa.true(), nullable=False))


def downgrade() -> None:
    with op.batch_alter_table('meal_reminder', schema=None) as batch_op:
        batch_op.drop_column('again_on')
        batch_op.drop_column('again_time')
        batch_op.drop_column('first_time')
