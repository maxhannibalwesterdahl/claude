"""Databaseforbindelse og migrationer."""

from collections.abc import Iterator
from importlib import resources

from alembic import command
from alembic.config import Config
from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import Session, sessionmaker


def make_engine(url: str) -> Engine:
    engine = create_engine(url, connect_args={"check_same_thread": False})

    @event.listens_for(engine, "connect")
    def _sqlite_pragmas(dbapi_conn, _record):
        cur = dbapi_conn.cursor()
        cur.execute("PRAGMA foreign_keys = ON")
        cur.execute("PRAGMA journal_mode = WAL")
        cur.close()

    return engine


def alembic_config(url: str) -> Config:
    cfg = Config()
    cfg.set_main_option("script_location", str(resources.files("madplan").joinpath("migrations")))
    cfg.set_main_option("sqlalchemy.url", url)
    return cfg


def migrate(engine: Engine) -> None:
    """Bringer databasen op til nyeste version. Kaldes ved opstart."""
    cfg = alembic_config(str(engine.url))
    with engine.begin() as conn:
        cfg.attributes["connection"] = conn
        command.upgrade(cfg, "head")


class Database:
    def __init__(self, engine: Engine):
        self.engine = engine
        self.sessionmaker = sessionmaker(engine, expire_on_commit=False)

    def session(self) -> Iterator[Session]:
        with self.sessionmaker() as s:
            yield s
