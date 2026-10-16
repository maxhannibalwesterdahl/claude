"""invitationer til familier

Revision ID: e7b3a1d5c902
Revises: d4a8b2c6e9f1
Create Date: 2026-10-16 18:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = 'e7b3a1d5c902'
down_revision = 'd4a8b2c6e9f1'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table('invite',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('household_id', sa.Integer(), nullable=False),
    sa.Column('token_hash', sa.String(length=64), nullable=False),
    sa.Column('role', sa.String(length=10), nullable=False),
    sa.Column('created_by', sa.Integer(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('used_by', sa.Integer(), nullable=True),
    sa.Column('used_at', sa.DateTime(timezone=True), nullable=True),
    sa.ForeignKeyConstraint(['created_by'], ['user.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['household_id'], ['household.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['used_by'], ['user.id'], ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('token_hash')
    )
    with op.batch_alter_table('invite', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_invite_household_id'), ['household_id'], unique=False)


def downgrade() -> None:
    op.drop_table('invite')
