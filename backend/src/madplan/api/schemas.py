"""JSON-formater for API'et."""

from typing import Literal

from pydantic import BaseModel, Field, field_validator

MatchStatus = Literal["sikker", "usikker", "ingen", "bekræftet"]


class LoginIn(BaseModel):
    username: str = Field(max_length=50)
    password: str = Field(max_length=200)


class UserOut(BaseModel):
    id: int
    username: str


class IngredientRef(BaseModel):
    id: int
    name: str
    department: str
    pantry: bool


class LineIn(BaseModel):
    """En ingredienslinje. Uden `item` læses `raw` af serveren."""

    id: int | None = None
    raw: str = Field(max_length=300)
    group: str = Field("", max_length=100)
    quantity: float | None = None
    quantity_max: float | None = None
    unit: str | None = Field(None, max_length=20)
    item: str | None = Field(None, max_length=200)
    note: str | None = Field(None, max_length=300)
    ingredient_id: int | None = None
    match_status: MatchStatus = "ingen"
    is_main: bool = False


class LineOut(BaseModel):
    id: int
    raw: str
    group: str
    quantity: float | None
    quantity_max: float | None
    unit: str | None
    item: str
    note: str | None
    ingredient: IngredientRef | None
    match_status: MatchStatus
    is_main: bool


class RecipeIn(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    servings: int | None = Field(None, ge=1, le=100)
    instructions: list[str] = []
    child_note: str = Field("", max_length=2000)
    source_url: str | None = Field(None, max_length=500)
    ingredients: list[LineIn] = []

    @field_validator("source_url")
    @classmethod
    def _http_only(cls, v: str | None) -> str | None:
        # Vises som link i appen. Kun http(s), så fx "javascript:" ikke kan gemmes.
        if v and v.strip() and not v.strip().lower().startswith(("http://", "https://")):
            raise ValueError("Linket skal starte med https://")
        return v


class RecipeOut(BaseModel):
    id: int
    title: str
    servings: int | None
    instructions: list[str]
    child_note: str
    source_url: str | None
    image_url: str | None
    ingredients: list[LineOut]
    warnings: list[str] = []


class RecipeSummary(BaseModel):
    id: int
    title: str
    servings: int | None
    image_url: str | None
    source_host: str | None
    main_ingredients: list[str]
    to_review: int


class ImportIn(BaseModel):
    url: str = Field(max_length=500)


class ParseIn(BaseModel):
    lines: list[str] = Field(max_length=200)


class ParsedOut(BaseModel):
    raw: str
    quantity: float | None
    quantity_max: float | None
    unit: str | None
    item: str
    note: str | None
    ingredient: IngredientRef | None
    match_status: MatchStatus


class IngredientIn(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    department: str
    pantry: bool = False
    grams_per_piece: float | None = Field(None, gt=0)
    grams_per_dl: float | None = Field(None, gt=0)


class IngredientOut(IngredientRef):
    grams_per_piece: float | None
    grams_per_dl: float | None
    aliases: list[str]
    used_in: int


class LineConfirmIn(BaseModel):
    ingredient_id: int


class ReviewLine(BaseModel):
    id: int
    recipe_id: int
    recipe_title: str
    raw: str
    item: str
    unit: str | None
    ingredient: IngredientRef | None
    match_status: MatchStatus
