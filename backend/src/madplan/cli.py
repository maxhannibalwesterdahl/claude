"""Administration fra kommandolinjen. Der er ingen selvregistrering i appen.

    madplan-admin create-user <brugernavn>
    madplan-admin set-password <brugernavn>
    madplan-admin list-users
"""

import argparse
import getpass
import sys

from sqlalchemy import select

from .auth import MIN_PASSWORD, hash_password
from .catalog import sync_seed
from .config import load_settings
from .db import Database, make_engine, migrate
from .models import User


def _ask_password() -> str:
    while True:
        pw = getpass.getpass(f"Kodeord (mindst {MIN_PASSWORD} tegn): ")
        if len(pw) < MIN_PASSWORD:
            print(f"For kort. Mindst {MIN_PASSWORD} tegn.")
            continue
        if getpass.getpass("Gentag kodeord: ") != pw:
            print("Kodeordene er ikke ens.")
            continue
        return pw


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="madplan-admin")
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("create-user", "set-password"):
        sub.add_parser(name).add_argument("username")
    sub.add_parser("list-users")
    args = ap.parse_args(argv)

    settings = load_settings()
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    engine = make_engine(settings.db_url)
    migrate(engine)
    db = Database(engine)
    with db.sessionmaker() as s:
        sync_seed(s)
        if args.cmd == "list-users":
            for u in s.scalars(select(User).order_by(User.username)):
                print(u.username)
            return 0

        username = args.username.strip().lower()
        user = s.scalar(select(User).where(User.username == username))
        if args.cmd == "create-user":
            if user:
                print(f"Brugeren {username} findes allerede.", file=sys.stderr)
                return 1
            s.add(User(username=username, password_hash=hash_password(_ask_password())))
            s.commit()
            print(f"Brugeren {username} er oprettet.")
        else:
            if not user:
                print(f"Brugeren {username} findes ikke.", file=sys.stderr)
                return 1
            user.password_hash = hash_password(_ask_password())
            user.session_version += 1
            s.commit()
            print(f"Nyt kodeord gemt. {username} er logget ud på alle enheder.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
