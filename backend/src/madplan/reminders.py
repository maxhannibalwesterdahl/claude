"""Påmindelser: "Husk kød op af fryseren" på en ret sendes som besked.

Første gang kl. 19 aftenen før retten. Er den ikke krydset af, kommer den igen
kl. 19 dagen efter (på selve dagen). Derefter er retten spist, og der sendes
ikke mere. Højst én besked pr. påmindelse pr. aften.
"""

import asyncio
import logging
from datetime import date, datetime, timedelta
from pathlib import Path

from sqlalchemy import or_, select
from sqlalchemy.orm import Session, selectinload, sessionmaker

from . import push
from .config import local_now
from .models import MealReminder, PlanMeal, PushSubscription, Setting

log = logging.getLogger("madplan")

SEND_HOUR = 19
SUBJECT_KEY = "push_subject"


def in_window(meal_date: date, today: date) -> bool:
    return meal_date - timedelta(days=1) <= today <= meal_date


def written_tonight(reminder: MealReminder, now: datetime) -> None:
    """Skrives påmindelsen efter kl. 19 en aften, hvor den ellers skulle sendes,
    er den lige set: beskeden kommer først næste aften."""
    today = now.date()
    if now.hour >= SEND_HOUR and in_window(reminder.meal.date, today):
        reminder.sent_on = today


def strip_husk(text: str) -> str:
    """"husk kød op" -> "kød op", så beskeden ikke hedder "Husk: husk kød op"."""
    t = text.strip()
    for prefix in ("husk at ", "husk: ", "husk "):
        if t.lower().startswith(prefix):
            return t[len(prefix):].strip() or t
    return t


def message(reminder: MealReminder, today: date) -> dict:
    from .api.plans import meal_title  # undgår en løkke ved import

    meal = reminder.meal
    when = "i morgen" if meal.date > today else "i dag"
    return {
        "title": f"Husk: {strip_husk(reminder.text)}",
        "body": f"{meal_title(meal)} {when}",
        "tag": f"husk-{reminder.id}",
        "url": f"/?dag={meal.date.isoformat()}",
        "reminder_id": reminder.id,
    }


def subject(session: Session) -> str:
    """Kontakt til push-tjenesten: appens egen adresse (gemt, da en telefon meldte sig)."""
    s = session.get(Setting, SUBJECT_KEY)
    return s.value if s else "https://madplan.invalid"


def targets(session: Session) -> list[PushSubscription]:
    return list(session.scalars(select(PushSubscription)))


def send_to(session: Session, subs: list[PushSubscription], msg: dict, key, post) -> bool:
    """Sender til alle telefoner. Telefoner, der har meldt fra, slettes. Svarer True,
    når mindst én har fået beskeden."""
    sub = subject(session)
    delivered = False
    for s in subs:
        status = push.send(push.Target(s.endpoint, s.p256dh, s.auth), msg, key, sub, post=post)
        if status in push.GONE:
            session.delete(s)
        elif 200 <= status < 300:
            delivered = True
    return delivered


def send_due(sm: sessionmaker, data_dir: Path, now: datetime | None = None, post=None) -> int:
    """Sender de påmindelser, der skal ud nu. Svarer med antallet, der blev sendt."""
    now = now or local_now()
    if now.hour < SEND_HOUR:
        return 0
    today = now.date()
    post = post or push.httpx.post
    with sm() as session:
        if not targets(session):
            # Ingen telefoner endnu: påmindelserne venter, så de kan nå frem samme
            # aften, hvis nogen slår beskeder til.
            return 0
        due = session.scalars(
            select(MealReminder)
            .join(PlanMeal)
            .where(
                MealReminder.done.is_(False),
                PlanMeal.date.in_([today, today + timedelta(days=1)]),
                or_(MealReminder.sent_on.is_(None), MealReminder.sent_on != today),
            )
            .options(selectinload(MealReminder.meal).selectinload(PlanMeal.recipe),
                     selectinload(MealReminder.meal).selectinload(PlanMeal.leftover_from))
            .order_by(MealReminder.id)
        ).all()
        if not due:
            return 0
        key = push.load_key(data_dir)
        sent = 0
        for r in due:
            subs = targets(session)
            if not subs:
                break
            # Kom den ikke frem (fx intet net), prøves der igen om lidt.
            if send_to(session, subs, message(r, today), key, post):
                r.sent_on = today
                sent += 1
            session.flush()
        session.commit()
        return sent


async def run_forever(sm: sessionmaker, data_dir: Path, every: float = 60) -> None:
    """Kigger efter påmindelser hvert minut, så længe appen kører."""
    while True:
        await asyncio.sleep(every)
        try:
            n = await asyncio.to_thread(send_due, sm, data_dir)
            if n:
                log.info("sendte %d påmindelse(r)", n)
        except Exception:
            log.exception("påmindelser kunne ikke sendes")
