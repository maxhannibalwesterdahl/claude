"""Systemadmin: familier, brugere og opskrifter (docs/flere-familier.md §5a).

Siden ligger på /admin (ren HTML, se admin_site/) og er åben på samme adresse som
appen, så den beskyttes ekstra:

- eget login med kort levetid (cookie `madplan_admin`, SameSite=Strict), også selv
  om man er logget ind i appen
- kun brugere med `is_system_admin`; alle andre får 404 på hele /api/admin, så
  ruterne ikke afslører, at de findes
- strammere grænse for loginforsøg, både pr. IP og pr. brugernavn
- alt, admin gør, skrives i loggen (`madplan.admin`)
"""

import logging
from importlib import resources

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from .. import totp
from ..auth import HASH_GATE, RateLimiter, hash_password, make_session, read_session, verify_password
from ..households import add_member, create_household, create_invite, erase_household
from ..history import CannotUndo, ingredient_state, record_change, undo_change
from ..ingredients.matcher import DEPARTMENTS
from ..ingredients.matcher import key as match_key
from ..models import (
    CatalogChange,
    Household,
    HouseholdMember,
    Ingredient,
    IngredientAlias,
    Plan,
    PlanMeal,
    Recipe,
    RecipeIngredient,
    User,
    WishlistItem,
)
from .ingredients import update_catalog
from .schemas import IngredientIn
from .deps import AppSettings, DbSession, client_ip

log = logging.getLogger("madplan.admin")

COOKIE = "madplan_admin"
ADMIN_HOURS = 12
# Fem forsøg pr. 5 minutter pr. IP og pr. brugernavn.
LOGIN_WINDOW = 300.0


def limiter(request: Request) -> RateLimiter:
    lim = getattr(request.app.state, "admin_limiter", None)
    if lim is None:
        lim = request.app.state.admin_limiter = RateLimiter(window=LOGIN_WINDOW)
    return lim


def _secret(settings) -> str:
    # Admin-cookies kan ikke bruges som almindelige cookies og omvendt.
    return settings.secret + ":admin"


def current_admin(request: Request, session: DbSession, settings: AppSettings) -> User:
    found = read_session(_secret(settings), request.cookies.get(COOKIE))
    if found:
        user = session.get(User, found[0])
        if user and user.is_system_admin and not user.disabled and user.session_version == found[1]:
            return user
    raise HTTPException(status_code=404, detail="Findes ikke")


Admin = Depends(current_admin)

# Alt undtagen login kræver admin-session (404 ellers).
router = APIRouter(prefix="/api/admin")
protected = APIRouter(dependencies=[Admin])


class LoginIn(BaseModel):
    username: str = Field(max_length=50)
    password: str = Field(max_length=200)
    # Kode fra authenticator-appen, hvis tofaktor er slået til.
    code: str = Field("", max_length=12)


@router.post("/login")
def login(body: LoginIn, request: Request, response: Response, session: DbSession, settings: AppSettings) -> dict:
    lim = limiter(request)
    name = body.username.strip().lower()
    keys = (f"ip:{client_ip(request)}", f"user:{name}")
    if any(lim.blocked(k) for k in keys):
        raise HTTPException(status_code=429, detail="For mange forsøg. Vent lidt.")
    for k in keys:
        lim.failed(k)
    if not HASH_GATE.acquire(blocking=False):
        raise HTTPException(status_code=429, detail="Mange logger ind lige nu. Prøv igen om lidt.")
    try:
        user = session.scalar(select(User).where(User.username == name))
        ok = verify_password(user.password_hash if user else None, body.password) and user is not None
    finally:
        HASH_GATE.release()
    # Tofaktor: koden tjekkes sammen med kodeordet, så et forkert svar ikke afslører,
    # hvilket af dem der var galt. Et brugt trin kan ikke bruges igen.
    step = None
    if ok and user.is_system_admin and user.totp_enabled and user.totp_secret:
        secret = totp.unseal(_secret(settings), user.totp_secret)
        step = totp.verify(secret, body.code, user.totp_last_step) if secret else None
        ok = step is not None
    # Samme svar, uanset om kodeordet er forkert, eller brugeren ikke er admin.
    if not ok or not user.is_system_admin or user.disabled:
        log.warning("admin-login afvist for %r fra %s", name, keys[0])
        raise HTTPException(status_code=401, detail="Forkert brugernavn, kodeord eller kode")
    for k in keys:
        lim.succeeded(k)
    if step is not None:
        user.totp_last_step = step
        session.commit()
    response.set_cookie(
        COOKIE,
        make_session(_secret(settings), user.id, user.session_version, days=ADMIN_HOURS / 24),
        max_age=ADMIN_HOURS * 3600,
        httponly=True,
        secure=request.url.scheme == "https" or "x-forwarded-for" in request.headers,
        samesite="strict",
    )
    log.info("admin-login: %s", user.username)
    return {"username": user.username}


@protected.post("/logout", status_code=204)
def logout(response: Response) -> None:
    response.delete_cookie(COOKIE)


@protected.get("/me")
def me(admin: User = Admin) -> dict:
    return {"username": admin.username, "two_factor": admin.totp_enabled}


# --- Tofaktor ----------------------------------------------------------------------------


@protected.post("/2fa/setup")
def two_factor_setup(session: DbSession, settings: AppSettings, admin: User = Admin) -> dict:
    """Ny hemmelighed til en authenticator-app. Slås først til, når en kode er bekræftet."""
    if admin.totp_enabled:
        raise HTTPException(status_code=409, detail="Tofaktor er allerede slået til")
    secret = totp.new_secret()
    admin.totp_secret = totp.seal(_secret(settings), secret)
    session.commit()
    return {"secret": secret, "uri": totp.uri(secret, admin.username)}


class CodeIn(BaseModel):
    code: str = Field(max_length=12)


@protected.post("/2fa/enable", status_code=204)
def two_factor_enable(body: CodeIn, session: DbSession, settings: AppSettings, admin: User = Admin) -> None:
    secret = totp.unseal(_secret(settings), admin.totp_secret) if admin.totp_secret else None
    step = totp.verify(secret, body.code) if secret else None
    if admin.totp_enabled or step is None:
        raise HTTPException(status_code=422, detail="Koden passer ikke. Prøv igen med den nyeste kode")
    admin.totp_enabled, admin.totp_last_step = True, step
    session.commit()
    log.info("%s slog tofaktor til", admin.username)


class DisableIn(BaseModel):
    password: str = Field(max_length=200)
    code: str = Field(max_length=12)


@protected.post("/2fa/disable", status_code=204)
def two_factor_disable(body: DisableIn, session: DbSession, settings: AppSettings, admin: User = Admin) -> None:
    secret = totp.unseal(_secret(settings), admin.totp_secret) if admin.totp_secret else None
    if not verify_password(admin.password_hash, body.password) or not secret or totp.verify(secret, body.code, admin.totp_last_step) is None:
        raise HTTPException(status_code=403, detail="Kodeord eller kode er forkert")
    admin.totp_enabled, admin.totp_secret, admin.totp_last_step = False, None, 0
    session.commit()
    log.info("%s slog tofaktor fra", admin.username)


# --- Familier -----------------------------------------------------------------------


class MemberOut(BaseModel):
    id: int
    username: str
    role: str
    disabled: bool
    is_system_admin: bool


class HouseholdOut(BaseModel):
    id: int
    name: str
    created_at: str
    members: list[MemberOut]
    recipes: int
    plans: int
    last_activity: str | None


def _household_out(session: Session, h: Household) -> HouseholdOut:
    members = session.execute(
        select(User, HouseholdMember.role).join(HouseholdMember, HouseholdMember.user_id == User.id)
        .where(HouseholdMember.household_id == h.id).order_by(User.username)
    ).all()
    last = session.scalar(select(func.max(Plan.created_at)).where(Plan.household_id == h.id))
    return HouseholdOut(
        id=h.id, name=h.name, created_at=h.created_at.isoformat(),
        members=[MemberOut(id=u.id, username=u.username, role=r, disabled=u.disabled,
                           is_system_admin=u.is_system_admin) for u, r in members],
        recipes=session.scalar(select(func.count()).select_from(Recipe).where(Recipe.created_by_household == h.id)) or 0,
        plans=session.scalar(select(func.count()).select_from(Plan).where(Plan.household_id == h.id)) or 0,
        last_activity=last.isoformat() if last else None,
    )


def _household(session: Session, household_id: int) -> Household:
    h = session.get(Household, household_id)
    if h is None:
        raise HTTPException(status_code=404, detail="Familien findes ikke")
    return h


def _user(session: Session, user_id: int) -> User:
    u = session.get(User, user_id)
    if u is None:
        raise HTTPException(status_code=404, detail="Brugeren findes ikke")
    return u


@protected.get("/households")
def list_households(session: DbSession) -> list[HouseholdOut]:
    return [_household_out(session, h) for h in session.scalars(select(Household).order_by(Household.name))]


class HouseholdIn(BaseModel):
    name: str = Field(min_length=1, max_length=100)


@protected.post("/households", status_code=201)
def add_household(body: HouseholdIn, session: DbSession, admin: User = Admin) -> HouseholdOut:
    name = " ".join(body.name.split())
    if not name:
        raise HTTPException(status_code=422, detail="Skriv et navn")
    h = create_household(session, name)
    session.commit()
    log.info("%s oprettede familien %r (id %d)", admin.username, h.name, h.id)
    return _household_out(session, h)


@protected.patch("/households/{household_id}")
def rename_household(household_id: int, body: HouseholdIn, session: DbSession, admin: User = Admin) -> HouseholdOut:
    h = _household(session, household_id)
    h.name = " ".join(body.name.split()) or h.name
    session.commit()
    log.info("%s omdøbte familie %d til %r", admin.username, h.id, h.name)
    return _household_out(session, h)


class UserIn(BaseModel):
    username: str = Field(min_length=1, max_length=50)
    password: str = Field(max_length=200)
    role: str = Field("medlem", pattern="^(admin|medlem)$")


def _hash(password: str) -> str:
    try:
        return hash_password(password)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from None


@protected.post("/households/{household_id}/users", status_code=201)
def add_user(household_id: int, body: UserIn, session: DbSession, admin: User = Admin) -> HouseholdOut:
    """Ny bruger i familien (en bruger hører til præcis én familie). Brugernavne er
    unikke på tværs af familier."""
    h = _household(session, household_id)
    name = body.username.strip().lower()
    if not name or any(c.isspace() for c in name):
        raise HTTPException(status_code=422, detail="Brugernavnet må ikke være tomt eller have mellemrum")
    if session.scalar(select(User.id).where(User.username == name)):
        raise HTTPException(status_code=409, detail="Brugernavnet er optaget")
    user = User(username=name, password_hash=_hash(body.password))
    session.add(user)
    session.flush()
    add_member(session, h, user, body.role)
    session.commit()
    log.info("%s oprettede brugeren %r i familie %d (%s)", admin.username, name, h.id, body.role)
    return _household_out(session, h)


class InviteIn(BaseModel):
    role: str = Field("admin", pattern="^(admin|medlem)$")


@protected.post("/households/{household_id}/invites", status_code=201)
def add_invite(household_id: int, body: InviteIn, session: DbSession, admin: User = Admin) -> dict:
    """Invitationslink til en familie (typisk til dens første admin). Gælder i 7 dage;
    nøglen vises kun her."""
    h = _household(session, household_id)
    invite, token = create_invite(session, h, body.role, admin)
    session.commit()
    log.info("%s lavede en invitation til familie %d (%s)", admin.username, h.id, body.role)
    return {"token": token, "path": f"/join/{token}", "expires_at": invite.expires_at.isoformat()}


class PasswordIn(BaseModel):
    password: str = Field(max_length=200)


@protected.post("/users/{user_id}/password", status_code=204)
def reset_password(user_id: int, body: PasswordIn, session: DbSession, admin: User = Admin) -> None:
    """Nyt kodeord. Brugeren logges ud på alle enheder."""
    user = _user(session, user_id)
    user.password_hash = _hash(body.password)
    user.session_version += 1
    session.commit()
    log.info("%s nulstillede kodeordet for %r", admin.username, user.username)


class DisabledIn(BaseModel):
    disabled: bool


@protected.post("/users/{user_id}/disabled", status_code=204)
def set_disabled(user_id: int, body: DisabledIn, session: DbSession, admin: User = Admin) -> None:
    user = _user(session, user_id)
    if user.id == admin.id:
        raise HTTPException(status_code=422, detail="Du kan ikke spærre dig selv")
    user.disabled = body.disabled
    user.session_version += 1
    session.commit()
    log.info("%s %s %r", admin.username, "spærrede" if body.disabled else "åbnede for", user.username)


@protected.post("/households/{household_id}/disabled", status_code=204)
def set_household_disabled(household_id: int, body: DisabledIn, session: DbSession, admin: User = Admin) -> None:
    """Spær (eller åbn for) alle i familien. Systemadmins røres ikke."""
    h = _household(session, household_id)
    users = session.scalars(
        select(User).join(HouseholdMember, HouseholdMember.user_id == User.id)
        .where(HouseholdMember.household_id == h.id, User.is_system_admin.is_(False))
    ).all()
    for u in users:
        u.disabled = body.disabled
        u.session_version += 1
    session.commit()
    log.info("%s %s familie %d (%d brugere)", admin.username, "spærrede" if body.disabled else "åbnede for", h.id, len(users))


@protected.delete("/users/{user_id}", status_code=204)
def delete_user(user_id: int, session: DbSession, admin: User = Admin) -> None:
    user = _user(session, user_id)
    if user.id == admin.id:
        raise HTTPException(status_code=422, detail="Du kan ikke slette dig selv")
    name = user.username
    session.delete(user)
    session.commit()
    log.info("%s slettede brugeren %r", admin.username, name)


@protected.delete("/households/{household_id}", status_code=204)
def delete_household(household_id: int, session: DbSession, settings: AppSettings, admin: User = Admin) -> None:
    """Sletter familien med alt: planer, indkøb, brugere og opskrifter, ingen andre bruger."""
    h = _household(session, household_id)
    if session.scalar(
        select(func.count()).select_from(HouseholdMember).where(
            HouseholdMember.household_id == h.id, HouseholdMember.user_id == admin.id)
    ):
        raise HTTPException(status_code=422, detail="Du kan ikke slette din egen familie")
    images = erase_household(session, h, settings.image_dir)
    session.commit()
    for image in images:
        (settings.image_dir / image).unlink(missing_ok=True)
    log.info("%s slettede familie %d (%r)", admin.username, household_id, h.name)


# --- Opskrifter ------------------------------------------------------------------------


class RecipeRow(BaseModel):
    id: int
    title: str
    owner_id: int | None
    owner: str | None
    lines: int
    used_in_plans: int
    source_url: str | None
    created_at: str


@protected.get("/recipes")
def list_recipes(session: DbSession) -> list[RecipeRow]:
    lines = dict(session.execute(select(RecipeIngredient.recipe_id, func.count()).group_by(RecipeIngredient.recipe_id)).all())
    used = dict(session.execute(select(PlanMeal.recipe_id, func.count()).where(PlanMeal.recipe_id.is_not(None)).group_by(PlanMeal.recipe_id)).all())
    names = dict(session.execute(select(Household.id, Household.name)).all())
    return [
        RecipeRow(id=r.id, title=r.title, owner_id=r.created_by_household, owner=names.get(r.created_by_household),
                  lines=lines.get(r.id, 0), used_in_plans=used.get(r.id, 0), source_url=r.source_url,
                  created_at=r.created_at.isoformat())
        for r in session.scalars(select(Recipe).order_by(func.lower(Recipe.title)))
    ]


@protected.delete("/recipes/{recipe_id}", status_code=204)
def delete_recipe(recipe_id: int, session: DbSession, settings: AppSettings, admin: User = Admin) -> None:
    recipe = session.get(Recipe, recipe_id)
    if recipe is None:
        raise HTTPException(status_code=404, detail="Opskriften findes ikke")
    title, image = recipe.title, recipe.image_file
    # Ønsker, der peger på opskriften, kan ikke blive stående uden den.
    for w in session.scalars(select(WishlistItem).where(WishlistItem.recipe_id == recipe.id)):
        session.delete(w)
    session.delete(recipe)
    session.commit()
    if image:
        (settings.image_dir / image).unlink(missing_ok=True)
    log.info("%s slettede opskriften %r (id %d)", admin.username, title, recipe_id)


# --- Varekatalog ------------------------------------------------------------------------


class AliasOut(BaseModel):
    id: int
    alias: str
    source: str


class CatalogItem(BaseModel):
    id: int
    name: str
    department: str
    grams_per_piece: float | None
    grams_per_dl: float | None
    aliases: list[AliasOut]
    used_in: int


class CatalogOut(BaseModel):
    departments: list[dict]
    items: list[CatalogItem]


def _catalog_item(ing: Ingredient, used: int) -> CatalogItem:
    return CatalogItem(
        id=ing.id, name=ing.name, department=ing.department, grams_per_piece=ing.grams_per_piece,
        grams_per_dl=ing.grams_per_dl, used_in=used,
        aliases=[AliasOut(id=a.id, alias=a.alias, source=a.source) for a in sorted(ing.aliases, key=lambda a: a.alias)],
    )


@protected.get("/ingredients")
def list_catalog(session: DbSession) -> CatalogOut:
    used = dict(session.execute(
        select(RecipeIngredient.ingredient_id, func.count(func.distinct(RecipeIngredient.recipe_id)))
        .group_by(RecipeIngredient.ingredient_id)).all())
    rows = session.scalars(select(Ingredient).options(selectinload(Ingredient.aliases)).order_by(Ingredient.name))
    return CatalogOut(
        departments=[{"code": c, "name": n} for c, n in DEPARTMENTS.items()],
        items=[_catalog_item(i, used.get(i.id, 0)) for i in rows],
    )


@protected.put("/ingredients/{ingredient_id}")
def update_catalog_item(ingredient_id: int, body: IngredientIn, session: DbSession, admin: User = Admin) -> CatalogItem:
    ing = session.get(Ingredient, ingredient_id)
    if ing is None:
        raise HTTPException(status_code=404, detail="Varen findes ikke")
    before = ingredient_state(ing)
    update_catalog(session, ing, body)
    after = ingredient_state(ing)
    if before != after:
        record_change(session, admin.id, "vare", ing.id, f"Rettede {before['name']}"
                      + (f" til {after['name']}" if before["name"] != after["name"] else ""), before, after)
    session.commit()
    log.info("%s rettede varen %r (nu %r)", admin.username, before["name"], ing.name)
    used = session.scalar(select(func.count(func.distinct(RecipeIngredient.recipe_id)))
                          .where(RecipeIngredient.ingredient_id == ing.id)) or 0
    return _catalog_item(ing, used)


@protected.delete("/ingredients/{ingredient_id}", status_code=204)
def delete_catalog_item(ingredient_id: int, session: DbSession, admin: User = Admin) -> None:
    ing = session.get(Ingredient, ingredient_id)
    if ing is None:
        raise HTTPException(status_code=404, detail="Varen findes ikke")
    if session.scalar(select(func.count()).select_from(RecipeIngredient).where(RecipeIngredient.ingredient_id == ing.id)):
        raise HTTPException(status_code=409, detail="Varen bruges i opskrifter og kan ikke slettes")
    name = ing.name
    state = ingredient_state(ing) | {"aliases": [{"alias": a.alias, "key": a.key, "source": a.source} for a in ing.aliases]}
    record_change(session, admin.id, "vare_slettet", ing.id, f"Slettede varen {name}", state)
    session.delete(ing)
    session.commit()
    log.info("%s slettede varen %r", admin.username, name)


@protected.delete("/aliases/{alias_id}", status_code=204)
def delete_alias(alias_id: int, session: DbSession, admin: User = Admin) -> None:
    """Fjern et forkert alias (fx et, en familie har lært af en fejl)."""
    alias = session.get(IngredientAlias, alias_id)
    if alias is None:
        raise HTTPException(status_code=404, detail="Aliaset findes ikke")
    text = alias.alias
    record_change(session, admin.id, "alias_slettet", alias.ingredient_id, f"Fjernede aliaset {text}",
                  {"alias": alias.alias, "key": alias.key, "ingredient_id": alias.ingredient_id, "source": alias.source})
    session.delete(alias)
    session.commit()
    log.info("%s slettede aliaset %r", admin.username, text)


class AliasIn(BaseModel):
    alias: str = Field(min_length=1, max_length=100)


@protected.post("/ingredients/{ingredient_id}/aliases", status_code=201)
def add_alias(ingredient_id: int, body: AliasIn, session: DbSession, admin: User = Admin) -> CatalogItem:
    """Nyt andet navn for en vare ("fløde" -> piskefløde). Må ikke være navnet på en anden vare."""
    ing = session.get(Ingredient, ingredient_id)
    if ing is None:
        raise HTTPException(status_code=404, detail="Varen findes ikke")
    text = " ".join(body.alias.lower().split())
    k = match_key(text)
    if not k:
        raise HTTPException(status_code=422, detail="Skriv et navn")
    clash = next((i for i in session.scalars(select(Ingredient)) if match_key(i.name) == k), None)
    if clash is not None or session.scalar(select(IngredientAlias.id).where(IngredientAlias.key == k)):
        raise HTTPException(status_code=409, detail="Navnet bruges allerede af en vare eller et alias")
    session.add(IngredientAlias(alias=text, key=k, ingredient_id=ing.id, source="user"))
    record_change(session, admin.id, "alias_tilfoejet", ing.id, f"Tilføjede aliaset {text} til {ing.name}",
                  after={"alias": text, "key": k})
    session.commit()
    session.refresh(ing)
    log.info("%s tilføjede aliaset %r til %r", admin.username, text, ing.name)
    used = session.scalar(select(func.count(func.distinct(RecipeIngredient.recipe_id)))
                          .where(RecipeIngredient.ingredient_id == ing.id)) or 0
    return _catalog_item(ing, used)


class ChangeOut(BaseModel):
    id: int
    created_at: str
    by: str | None
    summary: str
    undone: bool


@protected.get("/changes")
def list_changes(session: DbSession) -> list[ChangeOut]:
    """Seneste rettelser i det fælles varekatalog (med fortryd)."""
    rows = session.execute(
        select(CatalogChange, User.username).outerjoin(User, User.id == CatalogChange.user_id)
        .order_by(CatalogChange.id.desc()).limit(100)
    ).all()
    return [ChangeOut(id=c.id, created_at=c.created_at.isoformat(), by=u, summary=c.summary, undone=c.undone) for c, u in rows]


@protected.post("/changes/{change_id}/undo")
def undo(change_id: int, session: DbSession, admin: User = Admin) -> dict:
    change = session.get(CatalogChange, change_id)
    if change is None:
        raise HTTPException(status_code=404, detail="Rettelsen findes ikke")
    try:
        message = undo_change(session, change)
    except CannotUndo as e:
        raise HTTPException(status_code=409, detail=str(e)) from None
    session.commit()
    log.info("%s fortrød rettelse %d: %s", admin.username, change.id, message)
    return {"message": message}


# --- Siden ------------------------------------------------------------------------------

SITE_HEADERS = {
    "Cache-Control": "no-store",
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
    "Content-Security-Policy": "default-src 'none'; script-src 'self'; style-src 'self'; connect-src 'self'; "
                               "img-src 'self' data:; form-action 'none'; frame-ancestors 'none'; base-uri 'none'",
}
FILES = {"": ("index.html", "text/html"), "admin.css": ("admin.css", "text/css"), "admin.js": ("admin.js", "text/javascript")}


site = APIRouter()


@site.get("/admin", include_in_schema=False)
@site.get("/admin/{name:path}", include_in_schema=False)
def admin_site(name: str = "") -> FileResponse:
    """Selve siden er ren HTML/CSS/JS uden data; al data hentes fra /api/admin efter login."""
    entry = FILES.get(name)
    if entry is None:
        raise HTTPException(status_code=404, detail="Findes ikke")
    path = resources.files("madplan").joinpath("admin_site", entry[0])
    return FileResponse(str(path), media_type=entry[1], headers=SITE_HEADERS)


router.include_router(protected)
