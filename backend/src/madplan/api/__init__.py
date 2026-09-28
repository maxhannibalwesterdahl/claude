"""FastAPI-appen: JSON-API under /api og den byggede frontend på resten."""

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import APIRouter, FastAPI, HTTPException
from fastapi.responses import FileResponse

from ..auth import RateLimiter
from ..catalog import rematch_open_lines, sync_seed
from ..config import Settings, load_settings
from ..db import Database, make_engine, migrate
from . import auth_routes, ingredients, recipes
from .deps import CurrentUser, get_settings  # noqa: F401  (bruges af ruterne)


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or load_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        settings.data_dir.mkdir(parents=True, exist_ok=True)
        engine = make_engine(settings.db_url)
        migrate(engine)
        app.state.db = Database(engine)
        with app.state.db.sessionmaker() as s:
            sync_seed(s)
            rematch_open_lines(s)
            s.commit()
        yield
        engine.dispose()

    app = FastAPI(title="Madplan", docs_url=None, redoc_url=None, openapi_url=None, lifespan=lifespan)
    app.state.settings = settings
    app.state.login_limiter = RateLimiter()
    app.include_router(auth_routes.router)
    app.include_router(recipes.router)
    app.include_router(ingredients.router)
    app.include_router(_images(settings))

    @app.get("/api/health")
    def health() -> dict:
        return {"ok": True}

    @app.api_route("/api/{rest:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE"])
    def api_not_found(rest: str):
        raise HTTPException(status_code=404, detail="Findes ikke")

    if settings.static_dir:
        _mount_frontend(app, settings.static_dir)
    return app


def _images(settings: Settings) -> APIRouter:
    router = APIRouter()

    @router.get("/api/images/{name}")
    def image(name: str, _: CurrentUser) -> FileResponse:
        path = settings.image_dir / name
        if "/" in name or name.startswith(".") or not path.is_file():
            raise HTTPException(status_code=404)
        return FileResponse(path, headers={"Cache-Control": "private, max-age=31536000, immutable"})

    return router


def _mount_frontend(app: FastAPI, root: Path) -> None:
    """Statisk SvelteKit-build. Ukendte stier får index.html (appen router selv)."""
    root = root.resolve()
    index = root / "index.html"

    @app.get("/{path:path}", include_in_schema=False)
    def frontend(path: str) -> FileResponse:
        target = (root / path).resolve()
        if path and target.is_relative_to(root) and target.is_file():
            # Filer under _app/immutable har hash i navnet og ændrer sig aldrig.
            cache = "public, max-age=31536000, immutable" if path.startswith("_app/immutable/") else "no-cache"
            return FileResponse(target, headers={"Cache-Control": cache})
        return FileResponse(index, headers={"Cache-Control": "no-cache"})
