"""faste varer: vare, familien køber hver uge

Revision ID: a1f5c0d2e3b4
Revises: 5e9b3f1c7a20
Create Date: 2026-10-17 12:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = 'a1f5c0d2e3b4'
down_revision = '5e9b3f1c7a20'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table('household_staple',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('household_id', sa.Integer(), nullable=False),
    sa.Column('text', sa.String(length=200), nullable=False),
    sa.Column('quantity', sa.Float(), nullable=True),
    sa.Column('unit', sa.String(length=20), nullable=True),
    sa.Column('item', sa.String(length=200), nullable=False),
    sa.Column('ingredient_id', sa.Integer(), nullable=True),
    sa.Column('position', sa.Integer(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['household_id'], ['household.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['ingredient_id'], ['ingredient.id'], ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('household_staple', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_household_staple_household_id'), ['household_id'], unique=False)


def downgrade() -> None:
    op.drop_table('household_staple')
