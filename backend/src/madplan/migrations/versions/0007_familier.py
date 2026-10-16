"""familier (husstande)

Revision ID: c9d1e4f6a7b2
Revises: a3f7c0d9e512
Create Date: 2026-10-16 12:00:00.000000

Se docs/flere-familier.md §9. Findes der data (brugere, planer, opskrifter,
egne varer eller indstillinger), oprettes familie 1 med de nuværende brugere som
admin, og alle data og opskrifter hører til den. ingredient.pantry kopieres til
household_pantry og recipe.child_note til household_recipe_note. De gamle
kolonner bliver stående (de læses ikke mere), så en tilbagerulning ikke mister noget.
"""

from alembic import op
import sqlalchemy as sa


revision = 'c9d1e4f6a7b2'
down_revision = 'a3f7c0d9e512'
branch_labels = None
depends_on = None

HOUSEHOLD = 1
HOUSEHOLD_NAME = "Vores familie"


def _count(conn, table: str) -> int:
    return conn.execute(sa.text(f'SELECT COUNT(*) FROM "{table}"')).scalar() or 0


def upgrade() -> None:
    conn = op.get_bind()
    has_data = any(_count(conn, t) for t in ("user", "plan", "recipe", "shopping_extra", "setting", "push_subscription"))

    op.create_table('household',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('name', sa.String(length=100), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('household_member',
    sa.Column('household_id', sa.Integer(), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('role', sa.String(length=10), nullable=False),
    sa.ForeignKeyConstraint(['household_id'], ['household.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['user_id'], ['user.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('household_id', 'user_id'),
    sa.UniqueConstraint('user_id')
    )
    op.create_table('household_pantry',
    sa.Column('household_id', sa.Integer(), nullable=False),
    sa.Column('ingredient_id', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['household_id'], ['household.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['ingredient_id'], ['ingredient.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('household_id', 'ingredient_id')
    )
    op.create_table('household_recipe_note',
    sa.Column('household_id', sa.Integer(), nullable=False),
    sa.Column('recipe_id', sa.Integer(), nullable=False),
    sa.Column('child_note', sa.Text(), nullable=False),
    sa.ForeignKeyConstraint(['household_id'], ['household.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['recipe_id'], ['recipe.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('household_id', 'recipe_id')
    )
    op.create_table('household_ingredient_pref',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('household_id', sa.Integer(), nullable=False),
    sa.Column('key', sa.String(length=100), nullable=False),
    sa.Column('ingredient_id', sa.Integer(), nullable=True),
    sa.ForeignKeyConstraint(['household_id'], ['household.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['ingredient_id'], ['ingredient.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('household_id', 'key')
    )
    with op.batch_alter_table('household_ingredient_pref', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_household_ingredient_pref_household_id'), ['household_id'], unique=False)
    op.create_table('household_line_match',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('household_id', sa.Integer(), nullable=False),
    sa.Column('line_id', sa.Integer(), nullable=False),
    sa.Column('ingredient_id', sa.Integer(), nullable=True),
    sa.Column('match_status', sa.String(length=10), nullable=False),
    sa.ForeignKeyConstraint(['household_id'], ['household.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['ingredient_id'], ['ingredient.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['line_id'], ['recipe_ingredient.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('household_id', 'line_id')
    )
    with op.batch_alter_table('household_line_match', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_household_line_match_household_id'), ['household_id'], unique=False)

    # Nye kolonner: først tomme, så fyldt ud, og til sidst NOT NULL.
    with op.batch_alter_table('user', schema=None) as batch_op:
        batch_op.add_column(sa.Column('is_system_admin', sa.Boolean(), server_default=sa.false(), nullable=False))
    with op.batch_alter_table('recipe', schema=None) as batch_op:
        batch_op.add_column(sa.Column('created_by_household', sa.Integer(), nullable=True))
        batch_op.create_index(batch_op.f('ix_recipe_created_by_household'), ['created_by_household'], unique=False)
        batch_op.create_foreign_key(batch_op.f('fk_recipe_created_by_household_household'), 'household', ['created_by_household'], ['id'], ondelete='SET NULL')
    for table in ('plan', 'shopping_extra'):
        with op.batch_alter_table(table, schema=None) as batch_op:
            batch_op.add_column(sa.Column('household_id', sa.Integer(), nullable=True))

    # Indstillinger: ny tabel med (household_id, key). 0 = hele appen.
    op.create_table('setting_new',
    sa.Column('household_id', sa.Integer(), nullable=False),
    sa.Column('key', sa.String(length=50), nullable=False),
    sa.Column('value', sa.Text(), nullable=False),
    sa.PrimaryKeyConstraint('household_id', 'key')
    )

    if has_data:
        conn.execute(
            sa.text("INSERT INTO household (id, name, created_at) VALUES (:id, :name, CURRENT_TIMESTAMP)"),
            {"id": HOUSEHOLD, "name": HOUSEHOLD_NAME},
        )
        conn.execute(
            sa.text("INSERT INTO household_member (household_id, user_id, role) "
                    "SELECT :h, id, 'admin' FROM user ORDER BY id"),
            {"h": HOUSEHOLD},
        )
        conn.execute(sa.text("UPDATE plan SET household_id = :h"), {"h": HOUSEHOLD})
        conn.execute(sa.text("UPDATE shopping_extra SET household_id = :h"), {"h": HOUSEHOLD})
        conn.execute(sa.text("UPDATE recipe SET created_by_household = :h"), {"h": HOUSEHOLD})
        conn.execute(
            sa.text("INSERT INTO household_pantry (household_id, ingredient_id) "
                    "SELECT :h, id FROM ingredient WHERE pantry"),
            {"h": HOUSEHOLD},
        )
        conn.execute(
            sa.text("INSERT INTO household_recipe_note (household_id, recipe_id, child_note) "
                    "SELECT :h, id, child_note FROM recipe WHERE child_note IS NOT NULL AND child_note != ''"),
            {"h": HOUSEHOLD},
        )
        conn.execute(
            sa.text("INSERT INTO setting_new (household_id, key, value) "
                    "SELECT CASE WHEN key = 'push_subject' THEN 0 ELSE :h END, key, value FROM setting"),
            {"h": HOUSEHOLD},
        )

    op.drop_table('setting')
    op.rename_table('setting_new', 'setting')

    for table in ('plan', 'shopping_extra'):
        with op.batch_alter_table(table, schema=None) as batch_op:
            batch_op.alter_column('household_id', existing_type=sa.Integer(), nullable=False)
            batch_op.create_index(batch_op.f(f'ix_{table}_household_id'), ['household_id'], unique=False)
            batch_op.create_foreign_key(batch_op.f(f'fk_{table}_household_id_household'), 'household', ['household_id'], ['id'], ondelete='CASCADE')


def downgrade() -> None:
    op.create_table('setting_old',
    sa.Column('key', sa.String(length=50), nullable=False),
    sa.Column('value', sa.Text(), nullable=False),
    sa.PrimaryKeyConstraint('key')
    )
    # Ved flere familier vinder den laveste familie (familie 1).
    op.execute("INSERT INTO setting_old (key, value) SELECT key, value FROM setting "
               "WHERE household_id = (SELECT MIN(household_id) FROM setting s2 WHERE s2.key = setting.key)")
    op.drop_table('setting')
    op.rename_table('setting_old', 'setting')
    for table in ('shopping_extra', 'plan'):
        with op.batch_alter_table(table, schema=None) as batch_op:
            batch_op.drop_constraint(batch_op.f(f'fk_{table}_household_id_household'), type_='foreignkey')
            batch_op.drop_index(batch_op.f(f'ix_{table}_household_id'))
            batch_op.drop_column('household_id')
    with op.batch_alter_table('recipe', schema=None) as batch_op:
        batch_op.drop_constraint(batch_op.f('fk_recipe_created_by_household_household'), type_='foreignkey')
        batch_op.drop_index(batch_op.f('ix_recipe_created_by_household'))
        batch_op.drop_column('created_by_household')
    with op.batch_alter_table('user', schema=None) as batch_op:
        batch_op.drop_column('is_system_admin')
    op.drop_table('household_line_match')
    op.drop_table('household_ingredient_pref')
    op.drop_table('household_recipe_note')
    op.drop_table('household_pantry')
    op.drop_table('household_member')
    op.drop_table('household')
