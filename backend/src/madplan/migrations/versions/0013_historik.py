"""historik: opskriftsversioner og kataloghistorik

Revision ID: 8a5c2e7b1d36
Revises: 2d7f1a9c4e58
Create Date: 2026-10-17 12:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = '8a5c2e7b1d36'
down_revision = '2d7f1a9c4e58'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table('recipe_version',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('recipe_id', sa.Integer(), nullable=False),
    sa.Column('household_id', sa.Integer(), nullable=True),
    sa.Column('user_id', sa.Integer(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('data', sa.Text(), nullable=False),
    sa.ForeignKeyConstraint(['household_id'], ['household.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['recipe_id'], ['recipe.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['user_id'], ['user.id'], ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('recipe_version', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_recipe_version_recipe_id'), ['recipe_id'], unique=False)
    op.create_table('catalog_change',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=True),
    sa.Column('kind', sa.String(length=20), nullable=False),
    sa.Column('ingredient_id', sa.Integer(), nullable=True),
    sa.Column('summary', sa.String(length=300), nullable=False),
    sa.Column('before', sa.Text(), nullable=False),
    sa.Column('after', sa.Text(), nullable=False),
    sa.Column('undone', sa.Boolean(), server_default=sa.false(), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['user.id'], ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id')
    )


def downgrade() -> None:
    op.drop_table('catalog_change')
    op.drop_table('recipe_version')
