"""Databaseforbindelse og migrationer."""

import logging
import sqlite3
from collections.abc import Iterator
from importlib import resources
from pathlib import Path

from alembic import command
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from .config import local_now


def make_engine(url: str) -> Engine:
    engine = create_engine(url, connect_args={"check_same_thread": False})

    @event.listens_for(engine, "connect")
    def _sqlite_pragmas(dbapi_conn, _record):
        cur = dbapi_conn.cursor()
        cur.execute("PRAGMA foreign_keys = ON")
        cur.execute("PRAGMA journal_mode = WAL")
        cur.close()

    return engine


log = logging.getLogger("madplan")


def alembic_config(url: str, script_location: str | None = None) -> Config:
    cfg = Config()
    cfg.set_main_option("script_location", script_location or str(resources.files("madplan").joinpath("migrations")))
    cfg.set_main_option("sqlalchemy.url", url)
    return cfg


def copy_sqlite(source: Path, target: Path) -> Path:
    """Kopi af en SQLite-fil med SQLites backup-funktion (sikker, mens appen kører)."""
    target.parent.mkdir(parents=True, exist_ok=True)
    src = sqlite3.connect(source)
    dst = sqlite3.connect(target)
    try:
        src.backup(dst)
    finally:
        dst.close()
        src.close()
    return target


def migrate(engine: Engine, *, script_location: str | None = None, backup_dir: Path | None = None) -> bool:
    """Bringer databasen op til nyeste version. Kaldes ved opstart.

    - Før en ændring af en eksisterende database tages en kopi i `backup_dir`.
    - Fremmednøgler slås fra under migrationen. SQLite genopbygger tabeller ved
      ændringer (kopi, DROP, omdøb), og med nøglerne slået til ville DROP
      udløse ON DELETE og fx slette alle ingredienslinjer, når `recipe` ændres.
      Bagefter kontrolleres nøglerne, og migrationen afbrydes, hvis de er brudt.

    Returnerer True, hvis der blev migreret.
    """
    cfg = alembic_config(str(engine.url), script_location)
    head = ScriptDirectory.from_config(cfg).get_current_head()
    with engine.connect() as conn:
        current = MigrationContext.configure(conn).get_current_revision()
        conn.commit()
        if current == head:
            return False
        db_file = engine.url.database
        if backup_dir is not None and current is not None and db_file and Path(db_file).exists():
            stamp = local_now().strftime("%Y%m%d-%H%M%S")
            copy = copy_sqlite(Path(db_file), backup_dir / f"premigrate-{current}-{stamp}.db")
            log.info("kopi før migration: %s", copy)
        conn.exec_driver_sql("PRAGMA foreign_keys = OFF")
        conn.commit()
        try:
            with conn.begin():
                cfg.attributes["connection"] = conn
                command.upgrade(cfg, "head")
            broken = conn.exec_driver_sql("PRAGMA foreign_key_check").fetchall()
            conn.commit()
            if broken:
                raise RuntimeError(f"migrationen brød {len(broken)} fremmednøgler: {broken[:5]}")
        finally:
            conn.exec_driver_sql("PRAGMA foreign_keys = ON")
            conn.commit()
    return True


class Database:
    def __init__(self, engine: Engine):
        self.engine = engine
        self.sessionmaker = sessionmaker(engine, expire_on_commit=False)

    def session(self) -> Iterator[Session]:
        with self.sessionmaker() as s:
            yield s
