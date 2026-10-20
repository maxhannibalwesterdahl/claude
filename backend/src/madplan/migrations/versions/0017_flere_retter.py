"""flere retter på en dag: barnets ret bliver til ekstra retter

Revision ID: c3f7e2a4b5d6
Revises: b2e6d1f3a4c5
Create Date: 2026-10-20 10:00:00.000000

plan_meal.for_child hedder nu extra. En dag har stadig højst én hovedret,
men et vilkårligt antal ekstra retter. Barnets retter bliver ekstra retter.
"""

from alembic import op
import sqlalchemy as sa


revision = 'c3f7e2a4b5d6'
down_revision = 'b2e6d1f3a4c5'
branch_labels = None
depends_on = None

# Den gamle unikhed (plan_id, date, for_child) blev lavet uden navn i 0002.
NAMES = {"uq": "uq_%(table_name)s_%(column_0_name)s"}


def upgrade() -> None:
    with op.batch_alter_table('plan_meal', schema=None, naming_convention=NAMES) as batch_op:
        batch_op.drop_constraint('uq_plan_meal_plan_id', type_='unique')
        batch_op.alter_column('for_child', new_column_name='extra', existing_type=sa.Boolean(), existing_nullable=False)
    with op.batch_alter_table('plan_meal', schema=None) as batch_op:
        batch_op.create_index('uq_plan_meal_main', ['plan_id', 'date'], unique=True, sqlite_where=sa.text('NOT extra'))


def downgrade() -> None:
    # Kun én ekstra ret pr. dag kan blive til barnets ret. De øvrige slettes.
    op.execute(
        "DELETE FROM plan_meal WHERE extra AND id NOT IN "
        "(SELECT MIN(id) FROM plan_meal WHERE extra GROUP BY plan_id, date)"
    )
    with op.batch_alter_table('plan_meal', schema=None) as batch_op:
        batch_op.drop_index('uq_plan_meal_main')
        batch_op.alter_column('extra', new_column_name='for_child', existing_type=sa.Boolean(), existing_nullable=False)
    with op.batch_alter_table('plan_meal', schema=None) as batch_op:
        batch_op.create_unique_constraint('uq_plan_meal_plan_id', ['plan_id', 'date', 'for_child'])
