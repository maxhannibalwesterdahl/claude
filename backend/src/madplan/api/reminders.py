"""Husk på en ret ("kød op af fryseren") og tilmelding af telefoner til beskeder."""

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from .. import push
from ..config import local_now
from ..models import MealReminder, PushSubscription, Setting
from ..reminders import SUBJECT_KEY, send_to, written_tonight
from .deps import AppSettings, CurrentUser, DbSession
from .plans import PlanOut, _meal, load_plan, plan_out

router = APIRouter(prefix="/api")


class ReminderIn(BaseModel):
    text: str = Field(max_length=200)


class ReminderPatch(BaseModel):
    done: bool | None = None
    text: str | None = Field(None, max_length=200)


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


def _reminder(session, reminder_id: int) -> MealReminder:
    r = session.get(MealReminder, reminder_id)
    if r is None:
        raise HTTPException(status_code=404, detail="Påmindelsen findes ikke")
    return r


@router.post("/meals/{meal_id}/reminders")
def add_reminder(meal_id: int, body: ReminderIn, session: DbSession, _: CurrentUser) -> PlanOut:
    meal = _meal(session, meal_id)
    r = MealReminder(text=_clean(body.text))
    meal.reminders.append(r)
    written_tonight(r, local_now())
    session.commit()
    return plan_out(load_plan(session, meal.plan_id))


@router.patch("/reminders/{reminder_id}")
def update_reminder(reminder_id: int, body: ReminderPatch, session: DbSession, _: CurrentUser) -> PlanOut:
    r = _reminder(session, reminder_id)
    if body.done is not None:
        r.done = body.done
    if body.text is not None:
        r.text = _clean(body.text)
    session.commit()
    return plan_out(load_plan(session, r.meal.plan_id))


@router.delete("/reminders/{reminder_id}")
def delete_reminder(reminder_id: int, session: DbSession, _: CurrentUser) -> PlanOut:
    r = _reminder(session, reminder_id)
    plan_id = r.meal.plan_id
    session.delete(r)
    session.commit()
    return plan_out(load_plan(session, plan_id))


@router.get("/push/key")
def push_key(settings: AppSettings, _: CurrentUser) -> dict:
    return {"public_key": push.public_key(push.load_key(settings.data_dir))}


@router.post("/push/subscriptions", status_code=204)
def subscribe(body: SubscriptionIn, request: Request, session: DbSession, settings: AppSettings,
              user: CurrentUser) -> None:
    """Telefonen har sagt ja til beskeder. Kaldes igen, hver gang appen åbnes."""
    if not push.allowed_endpoint(body.endpoint):
        raise HTTPException(status_code=422, detail="Telefonens beskedtjeneste kendes ikke")
    sub = session.query(PushSubscription).filter_by(endpoint=body.endpoint).one_or_none()
    if sub is None:
        sub = PushSubscription(endpoint=body.endpoint)
        session.add(sub)
    sub.user_id, sub.p256dh, sub.auth = user.id, body.keys.p256dh, body.keys.auth
    # Push-tjenesterne vil kende afsenderen: appens egen adresse, som browseren
    # sender med (Origin). Bag Tailscale ser serveren ellers kun http.
    origin = request.headers.get("origin", "")
    if origin.startswith("https://"):
        setting = session.get(Setting, SUBJECT_KEY)
        if setting is None:
            session.add(Setting(key=SUBJECT_KEY, value=origin))
        else:
            setting.value = origin
    session.commit()
    if body.hello:
        msg = {"title": "Beskeder er slået til", "body": "Påmindelser kommer kl. 19 dagen før og kl. 7 på dagen.", "tag": "hej", "url": "/"}
        ok = send_to(session, [sub], msg, push.load_key(settings.data_dir), push.httpx.post)
        session.commit()
        if not ok:
            raise HTTPException(status_code=502, detail="Telefonen fik ikke beskeden. Prøv igen om lidt.")
