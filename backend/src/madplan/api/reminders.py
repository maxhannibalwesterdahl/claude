"""Husk på en ret ("kød op af fryseren") og tilmelding af telefoner til beskeder."""

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import select

from .. import push
from ..config import local_now
from ..models import HouseholdMember, MealReminder, Plan, PlanMeal, PushSubscription, Setting
from ..reminders import DEFAULT_AGAIN, DEFAULT_FIRST, SUBJECT_KEY, mark_seen, send_to
from .deps import AppSettings, CurrentHousehold, CurrentUser, DbSession
from .plans import PlanOut, _meal, load_plan, plan_out

router = APIRouter(prefix="/api")


HHMM = r"^([01]\d|2[0-3]):[0-5]\d$"


class ReminderIn(BaseModel):
    text: str = Field(max_length=200)
    # Tom = standarden (kl. 19 aftenen før og kl. 7 på dagen).
    first_time: str | None = Field(None, pattern=HHMM)
    again_time: str | None = Field(None, pattern=HHMM)
    again_on: bool = True


class ReminderPatch(BaseModel):
    done: bool | None = None
    text: str | None = Field(None, max_length=200)
    # null nulstiller til standarden.
    first_time: str | None = Field(None, pattern=HHMM)
    again_time: str | None = Field(None, pattern=HHMM)
    again_on: bool | None = None


class SubscriptionKeys(BaseModel):
    p256dh: str = Field(max_length=200)
    auth: str = Field(max_length=100)


class SubscriptionIn(BaseModel):
    endpoint: str = Field(max_length=1000)
    keys: SubscriptionKeys
    # Send en besked med det samme, så det kan ses, at det virker.
    hello: bool = False


def _clean(text: str) -> str:
    t = " ".join(text.split())
    if not t:
        raise HTTPException(status_code=422, detail="Skriv, hvad I skal huske")
    return t


def _reminder(session, reminder_id: int, hh) -> MealReminder:
    r = session.scalar(
        select(MealReminder).join(PlanMeal).join(Plan)
        .where(MealReminder.id == reminder_id, Plan.household_id == hh.id)
    )
    if r is None:
        raise HTTPException(status_code=404, detail="Påmindelsen findes ikke")
    return r


@router.post("/meals/{meal_id}/reminders")
def add_reminder(meal_id: int, body: ReminderIn, session: DbSession, hh: CurrentHousehold) -> PlanOut:
    meal = _meal(session, meal_id, hh)
    r = MealReminder(
        text=_clean(body.text), again_on=body.again_on,
        first_time=None if body.first_time == DEFAULT_FIRST else body.first_time,
        again_time=None if body.again_time == DEFAULT_AGAIN else body.again_time,
    )
    meal.reminders.append(r)
    mark_seen(r, local_now())
    session.commit()
    return plan_out(load_plan(session, meal.plan_id, hh))


@router.patch("/reminders/{reminder_id}")
def update_reminder(reminder_id: int, body: ReminderPatch, session: DbSession, hh: CurrentHousehold) -> PlanOut:
    r = _reminder(session, reminder_id, hh)
    if body.done is not None:
        r.done = body.done
    if body.text is not None:
        r.text = _clean(body.text)
    changed = False
    if "first_time" in body.model_fields_set:
        r.first_time = None if body.first_time == DEFAULT_FIRST else body.first_time
        changed = True
    if "again_time" in body.model_fields_set:
        r.again_time = None if body.again_time == DEFAULT_AGAIN else body.again_time
        changed = True
    if body.again_on is not None:
        r.again_on = body.again_on
        changed = True
    if changed:
        # Et nyt tidspunkt, der allerede er passeret i dag, sender ikke med det samme.
        mark_seen(r, local_now())
    session.commit()
    return plan_out(load_plan(session, r.meal.plan_id, hh))


@router.delete("/reminders/{reminder_id}")
def delete_reminder(reminder_id: int, session: DbSession, hh: CurrentHousehold) -> PlanOut:
    r = _reminder(session, reminder_id, hh)
    plan_id = r.meal.plan_id
    session.delete(r)
    session.commit()
    return plan_out(load_plan(session, plan_id, hh))


@router.get("/push/key")
def push_key(settings: AppSettings, _: CurrentHousehold) -> dict:
    return {"public_key": push.public_key(push.load_key(settings.data_dir))}


@router.post("/push/subscriptions", status_code=204)
def subscribe(body: SubscriptionIn, request: Request, session: DbSession, settings: AppSettings,
              user: CurrentUser, hh: CurrentHousehold) -> None:
    """Telefonen har sagt ja til beskeder. Kaldes igen, hver gang appen åbnes."""
    if not push.allowed_endpoint(body.endpoint):
        raise HTTPException(status_code=422, detail="Telefonens beskedtjeneste kendes ikke")
    sub = session.query(PushSubscription).filter_by(endpoint=body.endpoint).one_or_none()
    if sub is not None and sub.user_id != user.id:
        # Samme telefon kan skifte bruger i familien, men en anden familie kan ikke
        # overtage et abonnement (så får den den første families påmindelser).
        owner = session.scalar(select(HouseholdMember.household_id).where(HouseholdMember.user_id == sub.user_id))
        if owner != hh.id:
            raise HTTPException(status_code=409, detail="Telefonen er allerede tilmeldt en anden familie")
    if sub is None:
        sub = PushSubscription(endpoint=body.endpoint)
        session.add(sub)
    sub.user_id, sub.p256dh, sub.auth = user.id, body.keys.p256dh, body.keys.auth
    # Push-tjenesterne vil kende afsenderen: appens egen adresse, som browseren
    # sender med (Origin). Bag Tailscale ser serveren ellers kun http.
    origin = request.headers.get("origin", "")
    if origin.startswith("https://"):
        setting = session.get(Setting, (0, SUBJECT_KEY))
        if setting is None:
            session.add(Setting(household_id=0, key=SUBJECT_KEY, value=origin))
        else:
            setting.value = origin
    session.commit()
    if body.hello:
        msg = {"title": "Beskeder er slået til", "body": "Påmindelser kommer kl. 19 dagen før og kl. 7 på dagen.", "tag": "hej", "url": "/"}
        ok = send_to(session, [sub], msg, push.load_key(settings.data_dir), push.httpx.post)
        session.commit()
        if not ok:
            raise HTTPException(status_code=502, detail="Telefonen fik ikke beskeden. Prøv igen om lidt.")
