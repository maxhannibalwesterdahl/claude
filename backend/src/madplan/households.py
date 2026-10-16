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


# --- Udlevering og sletning (flere-familier.md §8) -------------------------------------------


def export_household(session: Session, household: Household) -> dict:
    """Alt, familien selv har lagt ind, som almindelig JSON. Fælles viden (varekatalog,
    andre familiers opskrifter) er ikke med; opskrifter familien ejer er med i fuld form."""
    from .models import (HouseholdRecipe, HouseholdRecipeNote, HouseholdStaple, Plan, PlanLineState, PlanMeal,
                         Recipe, RecipeIngredient, Setting, ShoppingCheck, ShoppingExtra, WishlistItem)

    hid = household.id
    users = session.execute(
        select(User.username, HouseholdMember.role).join(HouseholdMember, HouseholdMember.user_id == User.id)
        .where(HouseholdMember.household_id == hid).order_by(User.username)
    ).all()
    owned = session.scalars(select(Recipe).where(Recipe.created_by_household == hid).order_by(Recipe.id)).all()
    plans = session.scalars(select(Plan).where(Plan.household_id == hid).order_by(Plan.start_date)).all()
    plan_ids = [p.id for p in plans]
    meals = session.scalars(select(PlanMeal).where(PlanMeal.plan_id.in_(plan_ids))).all() if plan_ids else []
    iso = lambda v: v.isoformat() if v is not None else None  # noqa: E731
    return {
        "family": {"name": household.name, "created_at": iso(household.created_at)},
        "members": [{"username": u, "role": r} for u, r in users],
        "settings": {s.key: s.value for s in session.scalars(select(Setting).where(Setting.household_id == hid))},
        "pantry": sorted(session.scalars(
            select(Ingredient.name).join(HouseholdPantry, HouseholdPantry.ingredient_id == Ingredient.id)
            .where(HouseholdPantry.household_id == hid))),
        "collection": [
            {"recipe_id": r.recipe_id, "title": t, "favorite": r.favorite}
            for r, t in session.execute(
                select(HouseholdRecipe, Recipe.title).join(Recipe, Recipe.id == HouseholdRecipe.recipe_id)
                .where(HouseholdRecipe.household_id == hid).order_by(Recipe.title))
        ],
        "child_notes": [
            {"recipe_id": n.recipe_id, "note": n.child_note}
            for n in session.scalars(select(HouseholdRecipeNote).where(HouseholdRecipeNote.household_id == hid))
            if n.child_note
        ],
        "recipes_owned": [
            {
                "id": r.id, "title": r.title, "servings": r.servings, "source_url": r.source_url,
                "instructions": [s for s in r.instructions.split("\n") if s.strip()], "image_file": r.image_file,
                "ingredients": [{"raw": l.raw, "group": l.group} for l in r.ingredients],
            }
            for r in owned
        ],
        "plans": [
            {
                "start_date": p.start_date.isoformat(), "days": p.days,
                "meals": [
                    {"date": m.date.isoformat(), "for_child": m.for_child, "kind": m.kind, "text": m.text,
                     "recipe_id": m.recipe_id, "multiplier": m.multiplier,
                     "reminders": [{"text": r.text, "done": r.done} for r in m.reminders]}
                    for m in meals if m.plan_id == p.id
                ],
                "wishlist": [{"recipe_id": w.recipe_id, "text": w.text} for w in p.wishlist],
            }
            for p in plans
        ],
        "shopping_extras": [
            {"text": e.text, "source": e.source, "checked": e.checked}
            for e in session.scalars(select(ShoppingExtra).where(ShoppingExtra.household_id == hid))
        ],
        "staples": [
            {"text": s.text, "quantity": s.quantity, "unit": s.unit}
            for s in session.scalars(select(HouseholdStaple).where(HouseholdStaple.household_id == hid)
                                     .order_by(HouseholdStaple.position, HouseholdStaple.id))
        ],
    }


def erase_household(session: Session, household: Household, image_dir) -> list[str]:
    """Sletter familien med alt, den har lagt ind: planer, indkøb, indstillinger, samling,
    noter og brugere (med deres telefoner). Opskrifter, kun familien bruger, slettes
    med billede; opskrifter, andre bruger, bliver som fælles viden uden ejer.
    Svarer med billedfilerne, der kan slettes, når der er committet."""
    from .models import HouseholdRecipe, PlanMeal, Recipe, Setting, WishlistItem, Plan

    hid = household.id
    used_elsewhere = set(session.scalars(select(HouseholdRecipe.recipe_id).where(HouseholdRecipe.household_id != hid)))
    used_elsewhere |= set(session.scalars(
        select(PlanMeal.recipe_id).join(Plan).where(Plan.household_id != hid, PlanMeal.recipe_id.is_not(None))))
    used_elsewhere |= set(session.scalars(
        select(WishlistItem.recipe_id).join(Plan).where(Plan.household_id != hid, WishlistItem.recipe_id.is_not(None))))
    images = []
    for r in session.scalars(select(Recipe).where(Recipe.created_by_household == hid)):
        if r.id not in used_elsewhere:
            if r.image_file:
                images.append(r.image_file)
            session.delete(r)
    user_ids = list(session.scalars(select(HouseholdMember.user_id).where(HouseholdMember.household_id == hid)))
    for s in session.scalars(select(Setting).where(Setting.household_id == hid)):
        session.delete(s)
    for u in session.scalars(select(User).where(User.id.in_(user_ids))):
        session.delete(u)
    session.flush()
    session.delete(household)
    return images
