"""Fælles afhængigheder for ruterne: database, indstillinger og login."""

from collections.abc import Iterator
from typing import Annotated

from fastapi import Depends, HTTPException, Request
from sqlalchemy.orm import Session

from ..auth import COOKIE, read_session
from ..config import Settings
from ..models import User


def get_settings(request: Request) -> Settings:
    return request.app.state.settings


def get_session(request: Request) -> Iterator[Session]:
    yield from request.app.state.db.session()


DbSession = Annotated[Session, Depends(get_session)]
AppSettings = Annotated[Settings, Depends(get_settings)]


def current_user(request: Request, session: DbSession, settings: AppSettings) -> User:
    found = read_session(settings.secret, request.cookies.get(COOKIE))
    if found:
        user = session.get(User, found[0])
        if user and user.session_version == found[1]:
            return user
    raise HTTPException(status_code=401, detail="Ikke logget ind")


CurrentUser = Annotated[User, Depends(current_user)]


def client_ip(request: Request) -> str:
    # Tailscale Funnel sender klientens IP i X-Forwarded-For. Appen kan kun nås
    # gennem Funnel, så headeren kan stoles på.
    fwd = request.headers.get("x-forwarded-for", "")
    return fwd.split(",")[0].strip() or (request.client.host if request.client else "?")
