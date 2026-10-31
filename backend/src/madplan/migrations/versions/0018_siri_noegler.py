"""nøgler til Siri-genvejen

Revision ID: d4a8f3b5c6e7
Revises: c3f7e2a4b5d6
Create Date: 2026-10-31 10:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = 'd4a8f3b5c6e7'
down_revision = 'c3f7e2a4b5d6'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'api_key',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=50), nullable=False),
        sa.Column('token_hash', sa.String(length=64), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('last_used_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['user.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('token_hash'),
    )
    with op.batch_alter_table('api_key', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_api_key_user_id'), ['user_id'], unique=False)


def downgrade() -> None:
    with op.batch_alter_table('api_key', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_api_key_user_id'))
    op.drop_table('api_key')
