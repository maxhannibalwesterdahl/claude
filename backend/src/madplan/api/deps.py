"""Fælles afhængigheder for ruterne: database, indstillinger og login."""

from collections.abc import Iterator
from typing import Annotated

from fastapi import Depends, HTTPException, Request
from sqlalchemy.orm import Session

from ..auth import COOKIE, read_session
from ..config import Settings
from sqlalchemy import select

from ..models import Household, HouseholdMember, HouseholdPantry, User


def get_settings(request: Request) -> Settings:
    return request.app.state.settings


def get_session(request: Request) -> Iterator[Session]:
    yield from request.app.state.db.session()


DbSession = Annotated[Session, Depends(get_session)]
AppSettings = Annotated[Settings, Depends(get_settings)]


def current_user(request: Request, session: DbSession, settings: AppSettings) -> User:
    found = read_session(settings.secret, request.cookies.get(COOKIE))
    if found:
        user = session.get(User, found[0])
        if user and not user.disabled and user.session_version == found[1]:
            return user
    raise HTTPException(status_code=401, detail="Ikke logget ind")


CurrentUser = Annotated[User, Depends(current_user)]


def current_household(user: CurrentUser, session: DbSession) -> Household:
    """Brugerens familie. Alle ruter med familiens data bruger den og filtrerer på
    household_id; hører noget til en anden familie, svares 404 (flere-familier.md §6)."""
    household = session.scalar(
        select(Household).join(HouseholdMember, HouseholdMember.household_id == Household.id)
        .where(HouseholdMember.user_id == user.id)
    )
    if household is None:
        raise HTTPException(status_code=403, detail="Brugeren hører ikke til en familie")
    return household


CurrentHousehold = Annotated[Household, Depends(current_household)]


def pantry_ids(session: Session, household_id: int) -> set[int]:
    """Familiens basisvarer (ingredient-id'er)."""
    return set(session.scalars(select(HouseholdPantry.ingredient_id).where(HouseholdPantry.household_id == household_id)))


def client_ip(request: Request) -> str:
    # Tailscale Funnel er den eneste vej ind og sætter klientens IP i
    # X-Forwarded-For. Brug den sidste adresse: den er sat af Tailscale. De
    # forreste kan klienten selv have skrevet og må ikke bruges til at
    # begrænse loginforsøg.
    fwd = [p.strip() for p in request.headers.get("x-forwarded-for", "").split(",") if p.strip()]
    return fwd[-1] if fwd else (request.client.host if request.client else "?")
