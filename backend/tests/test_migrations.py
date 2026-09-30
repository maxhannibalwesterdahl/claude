"""Migrationer må ikke røre data. SQLite genopbygger tabeller ved ændringer,
og med fremmednøgler slået til ville det slette alle ingredienslinjer."""

import shutil
from importlib import resources

from sqlalchemy import func, select, text

from madplan.db import make_engine, migrate
from madplan.models import Recipe, RecipeIngredient

EXTRA = '''"""test: udvid recipe.title"""
from alembic import op
import sqlalchemy as sa

revision = "9999test"
down_revision = "{head}"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("recipe") as b:
        b.alter_column("title", type_=sa.String(300), existing_type=sa.String(200))
    with op.batch_alter_table("ingredient") as b:
        b.alter_column("name", type_=sa.String(150), existing_type=sa.String(100))


def downgrade() -> None:
    pass
'''


def test_batch_migration_keeps_child_rows(tmp_path):
    engine = make_engine(f"sqlite:///{tmp_path / 'madplan.db'}")
    migrate(engine)
    with engine.begin() as c:
        c.execute(text("INSERT INTO ingredient (id, name, department, pantry) VALUES (1, 'løg', 'fg', 0)"))
        c.execute(text("INSERT INTO recipe (id, title, instructions, child_note, created_at, updated_at) "
                       "VALUES (1, 'Suppe', '', '', '2026-01-01', '2026-01-01')"))
        c.execute(text('INSERT INTO recipe_ingredient (recipe_id, position, "group", raw, item, ingredient_id, match_status, is_main) '
                       "VALUES (1, 0, '', '2 løg', 'løg', 1, 'sikker', 0)"))

    # En kopi af migrationsmappen med en ekstra migration, der ændrer recipe og ingredient.
    scripts = tmp_path / "migrations"
    shutil.copytree(str(resources.files("madplan").joinpath("migrations")), scripts)
    from alembic.config import Config
    from alembic.script import ScriptDirectory
    cfg = Config(); cfg.set_main_option("script_location", str(scripts))
    head = ScriptDirectory.from_config(cfg).get_current_head()
    (scripts / "versions" / "9999_test.py").write_text(EXTRA.replace("{head}", head))

    assert migrate(engine, script_location=str(scripts), backup_dir=tmp_path / "backups") is True
    with engine.connect() as c:
        assert c.execute(select(func.count()).select_from(RecipeIngredient)).scalar() == 1
        assert c.execute(select(RecipeIngredient.ingredient_id)).scalar() == 1
        assert c.execute(select(Recipe.title)).scalar() == "Suppe"
        assert c.exec_driver_sql("PRAGMA foreign_keys").scalar() == 1
    # Kopi taget før migrationen.
    assert len(list((tmp_path / "backups").glob("premigrate-*.db"))) == 1
    # Allerede nyeste version: ingen ny migration og ingen ny kopi.
    assert migrate(engine, script_location=str(scripts), backup_dir=tmp_path / "backups") is False
