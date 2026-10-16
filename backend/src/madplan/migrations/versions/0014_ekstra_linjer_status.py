"""ekstra linjer kan have status (har hjemme / rest)

Revision ID: 5e9b3f1c7a20
Revises: 8a5c2e7b1d36
Create Date: 2026-10-17 15:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = '5e9b3f1c7a20'
down_revision = '8a5c2e7b1d36'
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table('plan_line_state', schema=None) as batch_op:
        batch_op.add_column(sa.Column('adjustment_id', sa.Integer(), nullable=True))
        batch_op.alter_column('line_id', existing_type=sa.Integer(), nullable=True)
        batch_op.create_foreign_key(batch_op.f('fk_plan_line_state_adjustment_id_household_recipe_adjustment'),
                                    'household_recipe_adjustment', ['adjustment_id'], ['id'], ondelete='CASCADE')
        batch_op.create_unique_constraint(batch_op.f('uq_plan_line_state_meal_id'), ['meal_id', 'adjustment_id'])


def downgrade() -> None:
    op.execute("DELETE FROM plan_line_state WHERE line_id IS NULL")
    with op.batch_alter_table('plan_line_state', schema=None) as batch_op:
        batch_op.drop_constraint(batch_op.f('uq_plan_line_state_meal_id'), type_='unique')
        batch_op.drop_constraint(batch_op.f('fk_plan_line_state_adjustment_id_household_recipe_adjustment'), type_='foreignkey')
        batch_op.alter_column('line_id', existing_type=sa.Integer(), nullable=False)
        batch_op.drop_column('adjustment_id')
