"""Datamodel. Se docs/SPEC.md §5 for overblikket.

Ændringer kræver en ny Alembic-migration:
    alembic revision --autogenerate -m "beskrivelse"
"""

from datetime import date, datetime, timezone

from sqlalchemy import BigInteger, Boolean, Date, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint, false, true
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "user"

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(50), unique=True)
    password_hash: Mapped[str] = mapped_column(String(200))
    # Øges ved nyt kodeord, så gamle session-cookies holder op med at virke.
    session_version: Mapped[int] = mapped_column(Integer, default=1)
    # Må oprette familier og se alle (docs/flere-familier.md §5a).
    is_system_admin: Mapped[bool] = mapped_column(Boolean, default=False, server_default=false())
    # Spærret af systemadmin: kan ikke logge ind, og cookies holder op med at virke.
    disabled: Mapped[bool] = mapped_column(Boolean, default=False, server_default=false())
    # Tofaktor til admin-siden (krypteret TOTP-hemmelighed, se madplan.totp)
    totp_secret: Mapped[str | None] = mapped_column(String(200))
    totp_enabled: Mapped[bool] = mapped_column(Boolean, default=False, server_default=false())
    totp_last_step: Mapped[int] = mapped_column(BigInteger, default=0, server_default='0')
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


# --- Familier (docs/flere-familier.md) ----------------------------------------------


class Household(Base):
    """En familie. Planer, indkøb og indstillinger hører til én familie."""

    __tablename__ = "household"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class HouseholdMember(Base):
    """Én bruger hører til præcis én familie (user_id er unik)."""

    __tablename__ = "household_member"

    household_id: Mapped[int] = mapped_column(ForeignKey("household.id", ondelete="CASCADE"), primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("user.id", ondelete="CASCADE"), primary_key=True, unique=True)
    # "admin" eller "medlem"
    role: Mapped[str] = mapped_column(String(10), default="medlem")


class Invite(Base):
    """Invitation til en familie (7 dage). Kun en hash af nøglen gemmes; linket vises én gang."""

    __tablename__ = "invite"

    id: Mapped[int] = mapped_column(primary_key=True)
    household_id: Mapped[int] = mapped_column(ForeignKey("household.id", ondelete="CASCADE"), index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    # Rollen, den inviterede får: "admin" eller "medlem"
    role: Mapped[str] = mapped_column(String(10), default="medlem")
    created_by: Mapped[int | None] = mapped_column(ForeignKey("user.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    used_by: Mapped[int | None] = mapped_column(ForeignKey("user.id", ondelete="SET NULL"))
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class HouseholdRecipeAdjustment(Base):
    """Familiens tilpasning af en fælles opskrift, lagt oven på den (flere-familier.md §4).

    type "skip": linjen kommer ikke på listen. "quantity": egen mængde på linjen.
    "extra": ekstra linje (`value` er teksten, fx "1 dåse majs"). "note": familiens egen
    note (`value`), uden linje. Rører aldrig den fælles opskrift.
    """

    __tablename__ = "household_recipe_adjustment"

    id: Mapped[int] = mapped_column(primary_key=True)
    household_id: Mapped[int] = mapped_column(ForeignKey("household.id", ondelete="CASCADE"), index=True)
    recipe_id: Mapped[int] = mapped_column(ForeignKey("recipe.id", ondelete="CASCADE"), index=True)
    line_id: Mapped[int | None] = mapped_column(ForeignKey("recipe_ingredient.id", ondelete="CASCADE"))
    type: Mapped[str] = mapped_column(String(10))
    value: Mapped[str] = mapped_column(Text, default="")
    quantity: Mapped[float | None] = mapped_column(Float)


class HouseholdPantry(Base):
    """Familiens basisvarer (salt, olie, mel …). Erstatter ingredient.pantry."""

    __tablename__ = "household_pantry"

    household_id: Mapped[int] = mapped_column(ForeignKey("household.id", ondelete="CASCADE"), primary_key=True)
    ingredient_id: Mapped[int] = mapped_column(ForeignKey("ingredient.id", ondelete="CASCADE"), primary_key=True)


class HouseholdRecipe(Base):
    """Familiens samling: de fælles opskrifter, familien bruger (og favoritter)."""

    __tablename__ = "household_recipe"

    household_id: Mapped[int] = mapped_column(ForeignKey("household.id", ondelete="CASCADE"), primary_key=True)
    recipe_id: Mapped[int] = mapped_column(ForeignKey("recipe.id", ondelete="CASCADE"), primary_key=True, index=True)
    favorite: Mapped[bool] = mapped_column(Boolean, default=False, server_default=false())
    added_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class HouseholdRecipeNote(Base):
    """Familiens note om barnet på en opskrift. Erstatter recipe.child_note."""

    __tablename__ = "household_recipe_note"

    household_id: Mapped[int] = mapped_column(ForeignKey("household.id", ondelete="CASCADE"), primary_key=True)
    recipe_id: Mapped[int] = mapped_column(ForeignKey("recipe.id", ondelete="CASCADE"), primary_key=True)
    child_note: Mapped[str] = mapped_column(Text, default="")


class HouseholdIngredientPref(Base):
    """Familiens eget valg af vare for et varenavn (lag oven på de fælles aliaser).
    Endnu ikke i brug (trin 7 i docs/flere-familier.md)."""

    __tablename__ = "household_ingredient_pref"
    __table_args__ = (UniqueConstraint("household_id", "key"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    household_id: Mapped[int] = mapped_column(ForeignKey("household.id", ondelete="CASCADE"), index=True)
    # Normaliseret varenavn (matcher.key())
    key: Mapped[str] = mapped_column(String(100))
    ingredient_id: Mapped[int | None] = mapped_column(ForeignKey("ingredient.id", ondelete="CASCADE"))


class HouseholdLineMatch(Base):
    """Familiens egen varekobling for én ingredienslinje i en fælles opskrift.
    Endnu ikke i brug (trin 7 i docs/flere-familier.md)."""

    __tablename__ = "household_line_match"
    __table_args__ = (UniqueConstraint("household_id", "line_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    household_id: Mapped[int] = mapped_column(ForeignKey("household.id", ondelete="CASCADE"), index=True)
    line_id: Mapped[int] = mapped_column(ForeignKey("recipe_ingredient.id", ondelete="CASCADE"))
    ingredient_id: Mapped[int | None] = mapped_column(ForeignKey("ingredient.id", ondelete="SET NULL"))
    match_status: Mapped[str] = mapped_column(String(10), default="bekræftet")


class Ingredient(Base):
    """En vare, som den står på indkøbslisten."""

    __tablename__ = "ingredient"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True)
    department: Mapped[str] = mapped_column(String(10))
    # Startlistens basisvare. Familiens egne basisvarer står i household_pantry.
    pantry: Mapped[bool] = mapped_column(Boolean, default=False)
    grams_per_piece: Mapped[float | None] = mapped_column(Float)
    grams_per_dl: Mapped[float | None] = mapped_column(Float)

    aliases: Mapped[list["IngredientAlias"]] = relationship(
        back_populates="ingredient", cascade="all, delete-orphan"
    )


class IngredientAlias(Base):
    """Et andet navn for en vare. `key` er normaliseret med matcher.key()."""

    __tablename__ = "ingredient_alias"

    id: Mapped[int] = mapped_column(primary_key=True)
    alias: Mapped[str] = mapped_column(String(100))
    key: Mapped[str] = mapped_column(String(100), unique=True)
    ingredient_id: Mapped[int] = mapped_column(ForeignKey("ingredient.id", ondelete="CASCADE"))
    # "seed" fra ingredienser.txt, "user" fra brugerens rettelser.
    source: Mapped[str] = mapped_column(String(10), default="seed")

    ingredient: Mapped[Ingredient] = relationship(back_populates="aliases")


class Recipe(Base):
    __tablename__ = "recipe"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(200))
    source_url: Mapped[str | None] = mapped_column(String(500), unique=True)
    servings: Mapped[int | None] = mapped_column(Integer)
    # Trin adskilt af linjeskift.
    instructions: Mapped[str] = mapped_column(Text, default="")
    image_file: Mapped[str | None] = mapped_column(String(100))
    # Forældet: noten ligger nu pr. familie i household_recipe_note.
    child_note: Mapped[str] = mapped_column(Text, default="")
    # Ejerfamilien: kun den kan rette den fælles opskrift (docs/flere-familier.md §4).
    created_by_household: Mapped[int | None] = mapped_column(
        ForeignKey("household.id", ondelete="SET NULL"), index=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    ingredients: Mapped[list["RecipeIngredient"]] = relationship(
        back_populates="recipe", cascade="all, delete-orphan", order_by="RecipeIngredient.position"
    )


class RecipeIngredient(Base):
    """Én ingredienslinje i en opskrift, både som rå tekst og læst."""

    __tablename__ = "recipe_ingredient"

    id: Mapped[int] = mapped_column(primary_key=True)
    recipe_id: Mapped[int] = mapped_column(ForeignKey("recipe.id", ondelete="CASCADE"), index=True)
    position: Mapped[int] = mapped_column(Integer)
    # Afsnit i opskriften, fx "Kødsovs" og "Bechamel". Tom = intet afsnit.
    group: Mapped[str] = mapped_column(String(100), default="")
    raw: Mapped[str] = mapped_column(String(300))
    quantity: Mapped[float | None] = mapped_column(Float)
    quantity_max: Mapped[float | None] = mapped_column(Float)
    unit: Mapped[str | None] = mapped_column(String(20))
    item: Mapped[str] = mapped_column(String(200))
    note: Mapped[str | None] = mapped_column(String(300))
    ingredient_id: Mapped[int | None] = mapped_column(
        ForeignKey("ingredient.id", ondelete="SET NULL"), index=True
    )
    # "sikker"/"usikker" fra matcheren, "ingen" uden match, "bekræftet" af brugeren.
    match_status: Mapped[str] = mapped_column(String(10), default="ingen")
    is_main: Mapped[bool] = mapped_column(Boolean, default=False)

    recipe: Mapped[Recipe] = relationship(back_populates="ingredients")
    ingredient: Mapped[Ingredient | None] = relationship()


# --- Madplan (fase 2) ---------------------------------------------------------


class Plan(Base):
    """En madplan fra indkøbsdagen og et antal dage frem."""

    __tablename__ = "plan"

    id: Mapped[int] = mapped_column(primary_key=True)
    household_id: Mapped[int] = mapped_column(ForeignKey("household.id", ondelete="CASCADE"), index=True)
    start_date: Mapped[date] = mapped_column(Date, index=True)
    days: Mapped[int] = mapped_column(Integer, default=7)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    meals: Mapped[list["PlanMeal"]] = relationship(
        back_populates="plan", cascade="all, delete-orphan", order_by="PlanMeal.date"
    )
    wishlist: Mapped[list["WishlistItem"]] = relationship(
        back_populates="plan", cascade="all, delete-orphan", order_by="WishlistItem.id"
    )


class PlanMeal(Base):
    """Én ret på én dag. Højst én til husstanden og én til barnet pr. dag."""

    __tablename__ = "plan_meal"
    __table_args__ = (UniqueConstraint("plan_id", "date", "for_child"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    plan_id: Mapped[int] = mapped_column(ForeignKey("plan.id", ondelete="CASCADE"), index=True)
    date: Mapped[date] = mapped_column(Date)
    for_child: Mapped[bool] = mapped_column(Boolean, default=False)
    # "opskrift", "fritekst" eller "rester"
    kind: Mapped[str] = mapped_column(String(10))
    recipe_id: Mapped[int | None] = mapped_column(ForeignKey("recipe.id", ondelete="SET NULL"))
    text: Mapped[str] = mapped_column(String(200), default="")
    multiplier: Mapped[float] = mapped_column(Float, default=1.0)
    # "rester": retten, resterne er fra. "opskrift": retten, den bruger rest fra.
    leftover_from_id: Mapped[int | None] = mapped_column(ForeignKey("plan_meal.id", ondelete="SET NULL"))

    plan: Mapped[Plan] = relationship(back_populates="meals")
    recipe: Mapped[Recipe | None] = relationship()
    leftover_from: Mapped["PlanMeal | None"] = relationship(remote_side=[id])
    line_states: Mapped[list["PlanLineState"]] = relationship(
        back_populates="meal", cascade="all, delete-orphan"
    )
    reminders: Mapped[list["MealReminder"]] = relationship(
        back_populates="meal", cascade="all, delete-orphan", order_by="MealReminder.id"
    )


class PlanLineState(Base):
    """En ingredienslinje i en planlagt ret, der ikke skal købes."""

    __tablename__ = "plan_line_state"
    __table_args__ = (UniqueConstraint("meal_id", "line_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    meal_id: Mapped[int] = mapped_column(ForeignKey("plan_meal.id", ondelete="CASCADE"), index=True)
    line_id: Mapped[int] = mapped_column(ForeignKey("recipe_ingredient.id", ondelete="CASCADE"))
    # "hjemme" (har vi) eller "rest" (dækkes af rest fra en anden dag)
    state: Mapped[str] = mapped_column(String(10))

    meal: Mapped[PlanMeal] = relationship(back_populates="line_states")


class MealReminder(Base):
    """"Husk kød op af fryseren" på en ret. Sendes som besked aftenen før (standard
    kl. 19) og igen på dagen (standard kl. 7), hvis den ikke er krydset af.
    Tidspunkterne kan ændres pr. påmindelse. Følger retten, når den flyttes."""

    __tablename__ = "meal_reminder"

    id: Mapped[int] = mapped_column(primary_key=True)
    meal_id: Mapped[int] = mapped_column(ForeignKey("plan_meal.id", ondelete="CASCADE"), index=True)
    text: Mapped[str] = mapped_column(String(200))
    done: Mapped[bool] = mapped_column(Boolean, default=False)
    # "HH:MM" i dansk tid. Tom = standarden (se madplan.reminders).
    first_time: Mapped[str | None] = mapped_column(String(5))
    again_time: Mapped[str | None] = mapped_column(String(5))
    # Sendes den igen på dagen, hvis den ikke er krydset af?
    again_on: Mapped[bool] = mapped_column(Boolean, default=True, server_default=true())
    # Dagen (dansk tid), beskeden sidst blev sendt. Højst én gang pr. dag.
    sent_on: Mapped[date | None] = mapped_column(Date)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    meal: Mapped[PlanMeal] = relationship(back_populates="reminders")


class WishlistItem(Base):
    """En ret, I gerne vil have i perioden, men ikke har lagt på en dag endnu."""

    __tablename__ = "wishlist_item"

    id: Mapped[int] = mapped_column(primary_key=True)
    plan_id: Mapped[int] = mapped_column(ForeignKey("plan.id", ondelete="CASCADE"), index=True)
    recipe_id: Mapped[int | None] = mapped_column(ForeignKey("recipe.id", ondelete="CASCADE"))
    text: Mapped[str] = mapped_column(String(200), default="")

    plan: Mapped[Plan] = relationship(back_populates="wishlist")
    recipe: Mapped[Recipe | None] = relationship()


# --- Indkøbsliste (fase 3) ------------------------------------------------------


class ShoppingCheck(Base):
    """"Købt" for en række på indkøbslisten. Seneste ændring vinder (updated_ms)."""

    __tablename__ = "shopping_check"
    __table_args__ = (UniqueConstraint("plan_id", "key"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    plan_id: Mapped[int] = mapped_column(ForeignKey("plan.id", ondelete="CASCADE"), index=True)
    # "i:<ingrediens-id>" eller "t:<varenavn>" for linjer uden kendt vare
    key: Mapped[str] = mapped_column(String(120))
    checked: Mapped[bool] = mapped_column(Boolean, default=False)
    # Klientens tidspunkt for ændringen i ms (til synkronisering mellem telefoner)
    updated_ms: Mapped[int] = mapped_column(BigInteger, default=0)


class ShoppingExtra(Base):
    """Egen vare eller "løbet tør". Bliver på listen, til den er købt."""

    __tablename__ = "shopping_extra"

    id: Mapped[int] = mapped_column(primary_key=True)
    household_id: Mapped[int] = mapped_column(ForeignKey("household.id", ondelete="CASCADE"), index=True)
    # Ugen, varen blev skrevet på. Tom = ingen plan (eller planen er slettet).
    plan_id: Mapped[int | None] = mapped_column(ForeignKey("plan.id", ondelete="SET NULL"), index=True)
    text: Mapped[str] = mapped_column(String(200))
    ingredient_id: Mapped[int | None] = mapped_column(ForeignKey("ingredient.id", ondelete="SET NULL"))
    # "egen" eller "løbet tør"
    source: Mapped[str] = mapped_column(String(10), default="egen")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    checked: Mapped[bool] = mapped_column(Boolean, default=False)
    updated_ms: Mapped[int] = mapped_column(BigInteger, default=0)

    ingredient: Mapped[Ingredient | None] = relationship()
    plan: Mapped[Plan | None] = relationship()


class Setting(Base):
    """Små indstillinger som JSON, fx afdelingernes rækkefølge. household_id 0 er
    indstillinger for hele appen (fx push_subject); ellers familiens egne."""

    __tablename__ = "setting"

    household_id: Mapped[int] = mapped_column(Integer, primary_key=True, default=0)
    key: Mapped[str] = mapped_column(String(50), primary_key=True)
    value: Mapped[str] = mapped_column(Text)


# --- Beskeder ---------------------------------------------------------------------


class PushSubscription(Base):
    """En telefon (eller browser), der har sagt ja til beskeder (Web Push)."""

    __tablename__ = "push_subscription"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("user.id", ondelete="CASCADE"), index=True)
    endpoint: Mapped[str] = mapped_column(String(1000), unique=True)
    p256dh: Mapped[str] = mapped_column(String(200))
    auth: Mapped[str] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
