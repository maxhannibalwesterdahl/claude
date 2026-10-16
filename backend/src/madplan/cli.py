"""Administration fra kommandolinjen. Der er ingen selvregistrering i appen.

    madplan-admin create-household <navn>
    madplan-admin list-households
    madplan-admin create-user <brugernavn> [--household <navn eller id>] [--medlem]
    madplan-admin set-password <brugernavn>
    madplan-admin set-system-admin <brugernavn> [--fjern]
    madplan-admin list-users
    madplan-admin backup [--keep 14]
"""

import argparse
import getpass
import sys
from datetime import date
from pathlib import Path

from sqlalchemy import select

from .auth import MIN_PASSWORD, hash_password
from .catalog import sync_seed
from .config import load_settings, local_today
from .db import Database, copy_sqlite, make_engine, migrate
from .households import add_member, create_household
from .models import Household, HouseholdMember, User


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
    sub.add_parser("create-household").add_argument("name")
    sub.add_parser("list-households")
    cu = sub.add_parser("create-user")
    cu.add_argument("username")
    cu.add_argument("--household", help="familiens navn eller id (kan udelades, hvis der kun er én familie)")
    cu.add_argument("--medlem", action="store_true", help="almindeligt medlem i stedet for familie-admin")
    sub.add_parser("set-password").add_argument("username")
    sa = sub.add_parser("set-system-admin")
    sa.add_argument("username")
    sa.add_argument("--fjern", action="store_true", help="fjern systemadmin igen")
    sub.add_parser("list-users")
    sub.add_parser("backup").add_argument("--keep", type=int, default=14, help="antal dage, der gemmes")
    args = ap.parse_args(argv)

    settings = load_settings()
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    if args.cmd == "backup":
        print(backup(settings.data_dir, args.keep))
        return 0
    engine = make_engine(settings.db_url)
    migrate(engine, backup_dir=settings.data_dir / "backups")
    db = Database(engine)
    with db.sessionmaker() as s:
        sync_seed(s)
        if args.cmd == "list-users":
            for u in s.scalars(select(User).order_by(User.username)):
                member = s.get(HouseholdMember, (_household_of(s, u), u.id)) if _household_of(s, u) else None
                household = s.get(Household, member.household_id) if member else None
                flags = (f" [{household.name}, {member.role}]" if member else " [ingen familie]") + (
                    " [systemadmin]" if u.is_system_admin else "")
                print(u.username + flags)
            return 0
        if args.cmd == "list-households":
            for h in s.scalars(select(Household).order_by(Household.id)):
                names = s.scalars(
                    select(User.username).join(HouseholdMember, HouseholdMember.user_id == User.id)
                    .where(HouseholdMember.household_id == h.id).order_by(User.username)
                ).all()
                print(f"{h.id}\t{h.name}\t{', '.join(names)}")
            return 0
        if args.cmd == "create-household":
            h = create_household(s, args.name)
            s.commit()
            print(f"Familien {h.name!r} er oprettet (id {h.id}). Opret en bruger i den med: "
                  f"madplan-admin create-user <brugernavn> --household {h.id}")
            return 0

        username = args.username.strip().lower()
        user = s.scalar(select(User).where(User.username == username))
        if args.cmd == "create-user":
            if user:
                print(f"Brugeren {username} findes allerede.", file=sys.stderr)
                return 1
            household = _find_household(s, args.household)
            if household is None:
                return 1
            new = User(username=username, password_hash=hash_password(_ask_password()))
            s.add(new)
            s.flush()
            add_member(s, household, new, "medlem" if args.medlem else "admin")
            s.commit()
            print(f"Brugeren {username} er oprettet i familien {household.name!r}.")
        elif args.cmd == "set-system-admin":
            if not user:
                print(f"Brugeren {username} findes ikke.", file=sys.stderr)
                return 1
            user.is_system_admin = not args.fjern
            s.commit()
            print(f"{username} er {'ikke længere' if args.fjern else 'nu'} systemadmin.")
        else:
            if not user:
                print(f"Brugeren {username} findes ikke.", file=sys.stderr)
                return 1
            user.password_hash = hash_password(_ask_password())
            user.session_version += 1
            s.commit()
            print(f"Nyt kodeord gemt. {username} er logget ud på alle enheder.")
    return 0


def _household_of(s, user: User) -> int | None:
    return s.scalar(select(HouseholdMember.household_id).where(HouseholdMember.user_id == user.id))


def _find_household(s, ref: str | None) -> Household | None:
    """Familien ud fra navn eller id. Uden angivelse: den eneste familie, hvis der kun er én."""
    households = s.scalars(select(Household).order_by(Household.id)).all()
    if ref is None:
        if len(households) == 1:
            return households[0]
        print("Angiv familien med --household (se madplan-admin list-households).", file=sys.stderr)
        return None
    found = [h for h in households if str(h.id) == ref or h.name.lower() == ref.strip().lower()]
    if len(found) != 1:
        print(f"Familien {ref!r} findes ikke (eller er ikke entydig).", file=sys.stderr)
        return None
    return found[0]


def backup(data_dir: Path, keep: int, today: date | None = None) -> Path:
    """Kopi af databasen til data/backups/madplan-ÅÅÅÅ-MM-DD.db. Sikker, mens
    appen kører (SQLites backup-funktion). Ældre kopier end `keep` slettes."""
    folder = data_dir / "backups"
    folder.mkdir(exist_ok=True)
    target = copy_sqlite(data_dir / "madplan.db", folder / f"madplan-{(today or local_today()).isoformat()}.db")
    for old in sorted(folder.glob("madplan-*.db"))[:-keep]:
        old.unlink()
    return target


if __name__ == "__main__":
    sys.exit(main())
