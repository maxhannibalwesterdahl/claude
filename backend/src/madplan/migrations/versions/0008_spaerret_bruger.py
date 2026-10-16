"""spærret bruger

Revision ID: d4a8b2c6e9f1
Revises: c9d1e4f6a7b2
Create Date: 2026-10-16 15:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = 'd4a8b2c6e9f1'
down_revision = 'c9d1e4f6a7b2'
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table('user', schema=None) as batch_op:
        batch_op.add_column(sa.Column('disabled', sa.Boolean(), server_default=sa.false(), nullable=False))


def downgrade() -> None:
    with op.batch_alter_table('user', schema=None) as batch_op:
        batch_op.drop_column('disabled')
