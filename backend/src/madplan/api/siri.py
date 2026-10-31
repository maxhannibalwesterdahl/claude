"""Siri: "Tilføj til indkøb" via en genvej i Apples Genveje-app.

Genvejen spørger, hvad der skal på, og sender teksten hertil med brugerens
nøgle (`Authorization: Bearer <nøgle>`). Varerne kommer på listen for næste
uge. Findes den uge ikke, oprettes den i samme rytme som den seneste uge.

Svaret er almindelig tekst, som genvejen lader Siri læse op, også ved fejl.
Nøglen kan kun tilføje varer. Den oprettes og slettes af brugeren selv under
Ryd op > Siri, og kun en hash gemmes.
"""

import hashlib
import re
import secrets
from datetime import date, timedelta

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..config import local_today
from ..models import ApiKey, Household, Plan, User, utcnow
from .deps import CurrentUser, DbSession, current_household
from .plans import _end
from .shopping import add_text

router = APIRouter(prefix="/api")

MAX_KEYS = 10
MAX_ITEMS = 20


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


# --- Nøgler --------------------------------------------------------------------------

class KeyIn(BaseModel):
    name: str = Field("Siri", max_length=50)


class KeyOut(BaseModel):
    id: int
    name: str
    created_at: str
    last_used_at: str | None


class NewKeyOut(KeyOut):
    # Vises kun her, lige efter oprettelsen.
    token: str


def _key_out(k: ApiKey) -> KeyOut:
    return KeyOut(id=k.id, name=k.name, created_at=k.created_at.isoformat(),
                  last_used_at=k.last_used_at.isoformat() if k.last_used_at else None)


@router.get("/me/keys")
def list_keys(session: DbSession, user: CurrentUser) -> list[KeyOut]:
    return [_key_out(k) for k in session.scalars(select(ApiKey).where(ApiKey.user_id == user.id).order_by(ApiKey.id))]


@router.post("/me/keys", status_code=201)
def new_key(body: KeyIn, session: DbSession, user: CurrentUser) -> NewKeyOut:
    if session.scalar(select(func.count()).select_from(ApiKey).where(ApiKey.user_id == user.id)) >= MAX_KEYS:
        raise HTTPException(status_code=409, detail=f"Du har allerede {MAX_KEYS} nøgler. Slet en først.")
    token = "mp_" + secrets.token_urlsafe(32)
    key = ApiKey(user_id=user.id, name=" ".join(body.name.split()) or "Siri", token_hash=_hash(token))
    session.add(key)
    session.commit()
    return NewKeyOut(**_key_out(key).model_dump(), token=token)


@router.delete("/me/keys/{key_id}", status_code=204)
def delete_key(key_id: int, session: DbSession, user: CurrentUser) -> None:
    key = session.scalar(select(ApiKey).where(ApiKey.id == key_id, ApiKey.user_id == user.id))
    if key is None:
        raise HTTPException(status_code=404, detail="Nøglen findes ikke")
    session.delete(key)
    session.commit()


# --- Tilføj fra Siri -----------------------------------------------------------------

class SiriIn(BaseModel):
    text: str = Field("", max_length=1000)


def split_items(text: str) -> list[str]:
    """ "Mælk, æg og 2 pk bleer." -> ["mælk", "æg", "2 pk bleer"]."""
    parts = re.split(r",|;|\s+og\s+", text, flags=re.IGNORECASE)
    items = [" ".join(p.split()).strip(" .!?") for p in parts]
    # Diktering giver stort begyndelsesbogstav ("Mælk"), men ikke forkortelser ("MSG").
    items = [i[0].lower() + i[1:] if i[:2] != i[:2].upper() else i for i in items if i]
    return [i[:200] for i in items][:MAX_ITEMS]


def next_week(session: Session, hh: Household, today: date) -> Plan | None:
    """Ugen efter den igangværende (eller den næste, hvis ingen uge er i gang).

    Findes den ikke, oprettes den i den seneste uges rytme: samme længde og
    startdag, første gang efter i dag. None, hvis familien ingen uger har."""
    plans = session.scalars(select(Plan).where(Plan.household_id == hh.id).order_by(Plan.start_date)).all()
    if not plans:
        return None
    covering = [p for p in plans if p.start_date <= today <= _end(p)]
    after = _end(covering[-1]) if covering else today
    later = [p for p in plans if p.start_date > after]
    if later:
        return later[0]
    last = plans[-1]
    start = last.start_date + timedelta(days=last.days)
    while start <= today:
        start += timedelta(days=last.days)
    plan = Plan(household_id=hh.id, start_date=start, days=last.days)
    session.add(plan)
    session.flush()
    return plan


def _key_user(session: Session, request: Request) -> User | None:
    scheme, _, token = request.headers.get("authorization", "").partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        return None
    key = session.scalar(select(ApiKey).where(ApiKey.token_hash == _hash(token.strip())))
    user = session.get(User, key.user_id) if key else None
    if user is None or user.disabled:
        return None
    key.last_used_at = utcnow()
    return user


def _say(text: str, status: int = 200) -> PlainTextResponse:
    return PlainTextResponse(text, status_code=status)


def _join(words: list[str]) -> str:
    s = words[0] if len(words) == 1 else ", ".join(words[:-1]) + " og " + words[-1]
    return s[:1].upper() + s[1:]


@router.post("/siri/add")
def siri_add(body: SiriIn, request: Request, session: DbSession, today: date | None = None) -> PlainTextResponse:
    user = _key_user(session, request)
    if user is None:
        return _say("Nøglen virker ikke. Lav en ny i Madplan under Ryd op, Siri.", 401)
    try:
        hh = current_household(user, session)
    except HTTPException:
        return _say("Du hører ikke til en familie i Madplan.", 403)
    items = split_items(body.text)
    if not items:
        return _say("Jeg hørte ikke nogen vare.", 422)
    plan = next_week(session, hh, today or local_today())
    if plan is None:
        return _say("Lav først en uge i Madplan.", 409)
    added, already = [], []
    for item in items:
        (added if add_text(session, hh, plan, item, today) else already).append(item)
    session.commit()
    week = f"ugen fra {plan.start_date.day}/{plan.start_date.month}"
    if added and already:
        return _say(f"{_join(added)} er tilføjet til {week}. {_join(already)} stod der allerede.")
    if added:
        return _say(f"{_join(added)} er tilføjet til {week}.")
    return _say(f"{_join(already)} står allerede på listen for {week}.")
