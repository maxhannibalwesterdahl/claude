"""Familiens indstillinger: medlemmer, navn, invitationer og eget kodeord.

Familiens admin (rolle `admin`) styrer sin egen familie. Andre familiers medlemmer
og invitationer er som ikke-eksisterende (404). Invitationen er et link, som den
nye åbner og selv vælger brugernavn og kodeord på (flere-familier.md §5).
"""

import logging

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..auth import RateLimiter, hash_password, verify_password
from ..households import INVITE_DAYS, add_member, create_invite, find_invite
from ..models import Household, HouseholdMember, Invite, User, utcnow
from .auth_routes import start_session, user_out
from .deps import AppSettings, CurrentHousehold, CurrentUser, DbSession, client_ip
from .schemas import UserOut

log = logging.getLogger("madplan")
router = APIRouter(prefix="/api")


class MemberOut(BaseModel):
    id: int
    username: str
    role: str
    you: bool


class InviteOut(BaseModel):
    id: int
    role: str
    expires_at: str


class HouseholdView(BaseModel):
    id: int
    name: str
    role: str
    members: list[MemberOut]
    invites: list[InviteOut]


class NewInviteOut(InviteOut):
    # Vises kun her, lige efter oprettelsen. Frontend bygger linket /join/<token>.
    token: str


def _role(session: Session, hh: Household, user: User) -> str:
    return session.scalar(select(HouseholdMember.role).where(
        HouseholdMember.household_id == hh.id, HouseholdMember.user_id == user.id)) or "medlem"


def _require_admin(session: Session, hh: Household, user: User) -> None:
    if _role(session, hh, user) != "admin":
        raise HTTPException(status_code=403, detail="Kun familiens administrator kan det")


def _member(session: Session, hh: Household, user_id: int) -> tuple[User, HouseholdMember]:
    row = session.execute(
        select(User, HouseholdMember).join(HouseholdMember, HouseholdMember.user_id == User.id)
        .where(User.id == user_id, HouseholdMember.household_id == hh.id)
    ).first()
    if row is None:
        raise HTTPException(status_code=404, detail="Brugeren findes ikke")
    return row[0], row[1]


def _view(session: Session, hh: Household, user: User) -> HouseholdView:
    members = session.execute(
        select(User, HouseholdMember.role).join(HouseholdMember, HouseholdMember.user_id == User.id)
        .where(HouseholdMember.household_id == hh.id).order_by(User.username)
    ).all()
    role = _role(session, hh, user)
    invites = []
    if role == "admin":
        invites = [
            InviteOut(id=i.id, role=i.role, expires_at=i.expires_at.isoformat())
            for i in session.scalars(
                select(Invite).where(Invite.household_id == hh.id, Invite.used_at.is_(None), Invite.expires_at > utcnow())
                .order_by(Invite.id))
        ]
    return HouseholdView(
        id=hh.id, name=hh.name, role=role, invites=invites,
        members=[MemberOut(id=u.id, username=u.username, role=r, you=u.id == user.id) for u, r in members],
    )


@router.get("/household")
def get_household(session: DbSession, hh: CurrentHousehold, user: CurrentUser) -> HouseholdView:
    return _view(session, hh, user)


class NameIn(BaseModel):
    name: str = Field(min_length=1, max_length=100)


@router.patch("/household")
def rename(body: NameIn, session: DbSession, hh: CurrentHousehold, user: CurrentUser) -> HouseholdView:
    _require_admin(session, hh, user)
    name = " ".join(body.name.split())
    if not name:
        raise HTTPException(status_code=422, detail="Skriv et navn")
    hh.name = name
    session.commit()
    return _view(session, hh, user)


class InviteIn(BaseModel):
    role: str = Field("medlem", pattern="^(admin|medlem)$")


@router.post("/household/invites", status_code=201)
def new_invite(body: InviteIn, session: DbSession, hh: CurrentHousehold, user: CurrentUser) -> NewInviteOut:
    _require_admin(session, hh, user)
    invite, token = create_invite(session, hh, body.role, user)
    session.commit()
    log.info("%s lavede en invitation til familie %d", user.username, hh.id)
    return NewInviteOut(id=invite.id, role=invite.role, expires_at=invite.expires_at.isoformat(), token=token)


@router.delete("/household/invites/{invite_id}", status_code=204)
def delete_invite(invite_id: int, session: DbSession, hh: CurrentHousehold, user: CurrentUser) -> None:
    _require_admin(session, hh, user)
    invite = session.scalar(select(Invite).where(Invite.id == invite_id, Invite.household_id == hh.id))
    if invite is None:
        raise HTTPException(status_code=404, detail="Invitationen findes ikke")
    session.delete(invite)
    session.commit()


class PasswordIn(BaseModel):
    password: str = Field(max_length=200)


def _hash(password: str) -> str:
    try:
        return hash_password(password)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from None


@router.post("/household/members/{user_id}/password", status_code=204)
def reset_member_password(user_id: int, body: PasswordIn, session: DbSession, hh: CurrentHousehold,
                          user: CurrentUser) -> None:
    """Familiens admin nulstiller et medlems kodeord. Medlemmet logges ud overalt."""
    _require_admin(session, hh, user)
    member, _ = _member(session, hh, user_id)
    if member.is_system_admin and member.id != user.id:
        raise HTTPException(status_code=404, detail="Brugeren findes ikke")
    member.password_hash = _hash(body.password)
    member.session_version += 1
    session.commit()
    log.info("%s nulstillede kodeordet for %r", user.username, member.username)


@router.delete("/household/members/{user_id}", status_code=204)
def remove_member(user_id: int, session: DbSession, hh: CurrentHousehold, user: CurrentUser) -> None:
    _require_admin(session, hh, user)
    member, _ = _member(session, hh, user_id)
    if member.id == user.id:
        raise HTTPException(status_code=422, detail="Du kan ikke fjerne dig selv")
    if member.is_system_admin:
        raise HTTPException(status_code=404, detail="Brugeren findes ikke")
    session.delete(member)
    session.commit()
    log.info("%s fjernede %r fra familie %d", user.username, member.username, hh.id)


class RoleIn(BaseModel):
    role: str = Field(pattern="^(admin|medlem)$")


@router.put("/household/members/{user_id}/role", status_code=204)
def set_role(user_id: int, body: RoleIn, session: DbSession, hh: CurrentHousehold, user: CurrentUser) -> None:
    _require_admin(session, hh, user)
    _, row = _member(session, hh, user_id)
    if row.role == "admin" and body.role == "medlem":
        admins = session.scalar(select(func.count()).select_from(HouseholdMember).where(
            HouseholdMember.household_id == hh.id, HouseholdMember.role == "admin")) or 0
        if admins <= 1:
            raise HTTPException(status_code=422, detail="Familien skal have mindst én administrator")
    row.role = body.role
    session.commit()


class ChangePasswordIn(BaseModel):
    current: str = Field(max_length=200)
    new: str = Field(max_length=200)


@router.post("/me/password")
def change_own_password(body: ChangePasswordIn, request: Request, response: Response, session: DbSession,
                        settings: AppSettings, user: CurrentUser) -> UserOut:
    """Nyt kodeord til sig selv. Andre enheder logges ud; denne får en ny cookie."""
    if not verify_password(user.password_hash, body.current):
        raise HTTPException(status_code=403, detail="Det nuværende kodeord er forkert")
    user.password_hash = _hash(body.new)
    user.session_version += 1
    session.commit()
    start_session(response, request, settings, user)
    return user_out(session, user)


# --- Invitation: åbnes af den nye (ikke logget ind) ---------------------------------------


class InviteInfo(BaseModel):
    household: str
    role: str


def _limited(request: Request) -> None:
    lim = getattr(request.app.state, "invite_limiter", None)
    if lim is None:
        lim = request.app.state.invite_limiter = RateLimiter(limit=20)
    ip = client_ip(request)
    if lim.blocked(ip):
        raise HTTPException(status_code=429, detail="For mange forsøg. Vent et minut.")
    lim.failed(ip)


def _invite(session: Session, token: str) -> tuple[Invite, Household]:
    invite = find_invite(session, token)
    household = session.get(Household, invite.household_id) if invite else None
    if invite is None or household is None:
        raise HTTPException(status_code=404, detail="Invitationen er ugyldig eller udløbet")
    return invite, household


@router.get("/invites/{token}")
def invite_info(token: str, request: Request, session: DbSession) -> InviteInfo:
    _limited(request)
    invite, household = _invite(session, token)
    return InviteInfo(household=household.name, role=invite.role)


class AcceptIn(BaseModel):
    username: str = Field(min_length=1, max_length=50)
    password: str = Field(max_length=200)


@router.post("/invites/{token}/accept", status_code=201)
def accept_invite(token: str, body: AcceptIn, request: Request, response: Response, session: DbSession,
                  settings: AppSettings) -> UserOut:
    _limited(request)
    invite, household = _invite(session, token)
    name = body.username.strip().lower()
    if not name or any(c.isspace() for c in name):
        raise HTTPException(status_code=422, detail="Brugernavnet må ikke være tomt eller have mellemrum")
    if session.scalar(select(User.id).where(User.username == name)):
        raise HTTPException(status_code=409, detail="Brugernavnet er optaget. Vælg et andet")
    user = User(username=name, password_hash=_hash(body.password))
    session.add(user)
    session.flush()
    add_member(session, household, user, invite.role)
    invite.used_by, invite.used_at = user.id, utcnow()
    session.commit()
    start_session(response, request, settings, user)
    return user_out(session, user)
