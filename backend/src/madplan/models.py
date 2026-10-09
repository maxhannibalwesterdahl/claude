"""Datamodel. Se docs/SPEC.md §5 for overblikket.

Ændringer kræver en ny Alembic-migration:
    alembic revision --autogenerate -m "beskrivelse"
"""

from datetime import date, datetime, timezone

from sqlalchemy import BigInteger, Boolean, Date, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
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
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Ingredient(Base):
    """En vare, som den står på indkøbslisten."""

    __tablename__ = "ingredient"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True)
    department: Mapped[str] = mapped_column(String(10))
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
    child_note: Mapped[str] = mapped_column(Text, default="")
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
    """Små indstillinger som JSON, fx afdelingernes rækkefølge."""

    __tablename__ = "setting"

    key: Mapped[str] = mapped_column(String(50), primary_key=True)
    value: Mapped[str] = mapped_column(Text)
