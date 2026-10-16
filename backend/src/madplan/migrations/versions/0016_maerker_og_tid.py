"""mærker og tid: familiens egne mærker og opskriftens tilberedningstid

Revision ID: b2e6d1f3a4c5
Revises: 5e9b3f1c7a20
Create Date: 2026-10-18 10:00:00.000000

Tid (recipe.total_minutes) hører til den fælles opskrift. Mærker
(household_recipe_tag) er den enkelte families egne ord og slettes, når
opskriften tages ud af samlingen.
"""

from alembic import op
import sqlalchemy as sa


revision = 'b2e6d1f3a4c5'
down_revision = '5e9b3f1c7a20'
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table('recipe', schema=None) as batch_op:
        batch_op.add_column(sa.Column('total_minutes', sa.Integer(), nullable=True))
    op.create_table('household_recipe_tag',
    sa.Column('household_id', sa.Integer(), nullable=False),
    sa.Column('recipe_id', sa.Integer(), nullable=False),
    sa.Column('tag', sa.String(length=40), nullable=False),
    sa.ForeignKeyConstraint(['household_id'], ['household.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['recipe_id'], ['recipe.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('household_id', 'recipe_id', 'tag')
    )
    with op.batch_alter_table('household_recipe_tag', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_household_recipe_tag_household_id_tag'), ['household_id', 'tag'], unique=False)


def downgrade() -> None:
    with op.batch_alter_table('household_recipe_tag', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_household_recipe_tag_household_id_tag'))
    op.drop_table('household_recipe_tag')
    with op.batch_alter_table('recipe', schema=None) as batch_op:
        batch_op.drop_column('total_minutes')
