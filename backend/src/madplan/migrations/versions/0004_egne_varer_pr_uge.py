"""egne varer pr. uge

Revision ID: 4b1f0c2a9d37
Revises: 6d48ea6937c8
Create Date: 2026-10-09 10:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = '4b1f0c2a9d37'
down_revision = '6d48ea6937c8'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Eksisterende varer får ingen uge og vises derfor på den igangværende.
    with op.batch_alter_table('shopping_extra', schema=None) as batch_op:
        batch_op.add_column(sa.Column('plan_id', sa.Integer(), nullable=True))
        batch_op.create_index(batch_op.f('ix_shopping_extra_plan_id'), ['plan_id'], unique=False)
        batch_op.create_foreign_key(batch_op.f('fk_shopping_extra_plan_id_plan'), 'plan', ['plan_id'], ['id'], ondelete='SET NULL')


def downgrade() -> None:
    with op.batch_alter_table('shopping_extra', schema=None) as batch_op:
        batch_op.drop_constraint(batch_op.f('fk_shopping_extra_plan_id_plan'), type_='foreignkey')
        batch_op.drop_index(batch_op.f('ix_shopping_extra_plan_id'))
        batch_op.drop_column('plan_id')
