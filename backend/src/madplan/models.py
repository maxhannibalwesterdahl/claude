"""Datamodel. Se docs/SPEC.md §5 for overblikket.

Ændringer kræver en ny Alembic-migration:
    alembic revision --autogenerate -m "beskrivelse"
"""

from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text
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
