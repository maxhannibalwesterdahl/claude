"""familiens tilpasninger af fælles opskrifter

Revision ID: 2d7f1a9c4e58
Revises: 0b6e9c3d7a14
Create Date: 2026-10-17 09:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = '2d7f1a9c4e58'
down_revision = '0b6e9c3d7a14'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table('household_recipe_adjustment',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('household_id', sa.Integer(), nullable=False),
    sa.Column('recipe_id', sa.Integer(), nullable=False),
    sa.Column('line_id', sa.Integer(), nullable=True),
    sa.Column('type', sa.String(length=10), nullable=False),
    sa.Column('value', sa.Text(), nullable=False),
    sa.Column('quantity', sa.Float(), nullable=True),
    sa.ForeignKeyConstraint(['household_id'], ['household.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['line_id'], ['recipe_ingredient.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['recipe_id'], ['recipe.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('household_recipe_adjustment', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_household_recipe_adjustment_household_id'), ['household_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_household_recipe_adjustment_recipe_id'), ['recipe_id'], unique=False)


def downgrade() -> None:
    op.drop_table('household_recipe_adjustment')
