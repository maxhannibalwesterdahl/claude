"""Familier: oprettelse og medlemmer. Bruges af kommandolinjen (og testene)."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import Household, HouseholdMember, HouseholdPantry, Ingredient, User


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
