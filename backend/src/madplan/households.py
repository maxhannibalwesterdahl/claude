"""Familier: oprettelse og medlemmer. Bruges af kommandolinjen (og testene)."""

import hashlib
import secrets
from datetime import timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import Household, HouseholdMember, HouseholdPantry, Ingredient, Invite, User, utcnow


def create_household(session: Session, name: str) -> Household:
    """Ny familie med startlistens basisvarer (docs/flere-familier.md §9)."""
    household = Household(name=name.strip())
    session.add(household)
    session.flush()
    session.add_all(
        HouseholdPantry(household_id=household.id, ingredient_id=i)
        for i in session.scalars(select(Ingredient.id).where(Ingredient.pantry.is_(True)))
    )
    return household


def add_member(session: Session, household: Household, user: User, role: str = "medlem") -> HouseholdMember:
    """Brugeren flyttes ikke: en bruger hører til præcis én familie."""
    member = HouseholdMember(household_id=household.id, user_id=user.id, role=role)
    session.add(member)
    session.flush()
    return member


# --- Invitationer ---------------------------------------------------------------------

INVITE_DAYS = 7


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def create_invite(session: Session, household: Household, role: str, created_by: User | None) -> tuple[Invite, str]:
    """Ny invitation. Svarer med den og nøglen i klartekst (kun den hash gemmes)."""
    token = secrets.token_urlsafe(32)
    invite = Invite(
        household_id=household.id, token_hash=_hash(token), role=role,
        created_by=created_by.id if created_by else None,
        expires_at=utcnow() + timedelta(days=INVITE_DAYS),
    )
    session.add(invite)
    session.flush()
    return invite, token


def find_invite(session: Session, token: str) -> Invite | None:
    """Invitationen, hvis nøglen er gyldig: ikke brugt og ikke udløbet."""
    invite = session.scalar(select(Invite).where(Invite.token_hash == _hash(token)))
    if invite is None or invite.used_at is not None:
        return None
    expires = invite.expires_at if invite.expires_at.tzinfo else invite.expires_at.replace(tzinfo=timezone.utc)
    return invite if expires > utcnow() else None
