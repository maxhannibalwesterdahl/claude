"""tofaktor til admin

Revision ID: 0b6e9c3d7a14
Revises: f1c4d8a2b673
Create Date: 2026-10-16 22:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = '0b6e9c3d7a14'
down_revision = 'f1c4d8a2b673'
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table('user', schema=None) as batch_op:
        batch_op.add_column(sa.Column('totp_secret', sa.String(length=200), nullable=True))
        batch_op.add_column(sa.Column('totp_enabled', sa.Boolean(), server_default=sa.false(), nullable=False))
        batch_op.add_column(sa.Column('totp_last_step', sa.BigInteger(), server_default='0', nullable=False))


def downgrade() -> None:
    with op.batch_alter_table('user', schema=None) as batch_op:
        batch_op.drop_column('totp_last_step')
        batch_op.drop_column('totp_enabled')
        batch_op.drop_column('totp_secret')
