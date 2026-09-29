"""Alembic-miljø. Kører både fra appen (db.migrate) og fra kommandolinjen:

    cd backend && alembic revision --autogenerate -m "beskrivelse"
"""

from alembic import context
from sqlalchemy import create_engine

from madplan.models import Base

config = context.config
target_metadata = Base.metadata


def run() -> None:
    conn = config.attributes.get("connection")
    if conn is not None:
        _run_with(conn)
        return
    engine = create_engine(config.get_main_option("sqlalchemy.url"))
    with engine.begin() as conn:
        _run_with(conn)


def _run_with(conn) -> None:
    # render_as_batch: SQLite kan ikke ændre kolonner, så Alembic genskaber tabellen.
    context.configure(connection=conn, target_metadata=target_metadata, render_as_batch=True)
    with context.begin_transaction():
        context.run_migrations()


run()
