"""vores samling (household_recipe)

Revision ID: f1c4d8a2b673
Revises: e7b3a1d5c902
Create Date: 2026-10-16 20:00:00.000000

Hver families samling får de opskrifter, familien selv ejer eller har brugt i en plan.
"""

from alembic import op
import sqlalchemy as sa


revision = 'f1c4d8a2b673'
down_revision = 'e7b3a1d5c902'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table('household_recipe',
    sa.Column('household_id', sa.Integer(), nullable=False),
    sa.Column('recipe_id', sa.Integer(), nullable=False),
    sa.Column('favorite', sa.Boolean(), server_default=sa.false(), nullable=False),
    sa.Column('added_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['household_id'], ['household.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['recipe_id'], ['recipe.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('household_id', 'recipe_id')
    )
    with op.batch_alter_table('household_recipe', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_household_recipe_recipe_id'), ['recipe_id'], unique=False)
    op.execute("INSERT OR IGNORE INTO household_recipe (household_id, recipe_id, favorite, added_at) "
               "SELECT created_by_household, id, 0, CURRENT_TIMESTAMP FROM recipe WHERE created_by_household IS NOT NULL")
    op.execute("INSERT OR IGNORE INTO household_recipe (household_id, recipe_id, favorite, added_at) "
               "SELECT DISTINCT plan.household_id, plan_meal.recipe_id, 0, CURRENT_TIMESTAMP "
               "FROM plan_meal JOIN plan ON plan.id = plan_meal.plan_id WHERE plan_meal.recipe_id IS NOT NULL")


def downgrade() -> None:
    op.drop_table('household_recipe')
