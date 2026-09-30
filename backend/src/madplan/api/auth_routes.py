from fastapi import APIRouter, HTTPException, Request, Response
from sqlalchemy import select

from ..auth import COOKIE, HASH_GATE, SESSION_DAYS, make_session, verify_password
from ..models import User
from .deps import AppSettings, CurrentUser, DbSession, client_ip
from .schemas import LoginIn, UserOut

router = APIRouter(prefix="/api")


@router.post("/login")
def login(body: LoginIn, request: Request, response: Response, session: DbSession, settings: AppSettings) -> UserOut:
    limiter = request.app.state.login_limiter
    ip = client_ip(request)
    if limiter.blocked(ip):
        raise HTTPException(status_code=429, detail="For mange forsøg. Vent et minut.")
    # Tæl forsøget FØR kodeordet tjekkes, så samtidige forsøg også rammer grænsen.
    limiter.failed(ip)
    if not HASH_GATE.acquire(blocking=False):
        raise HTTPException(status_code=429, detail="Mange logger ind lige nu. Prøv igen om lidt.")
    try:
        user = session.scalar(select(User).where(User.username == body.username.strip().lower()))
        ok = verify_password(user.password_hash if user else None, body.password) and user is not None
    finally:
        HASH_GATE.release()
    if not ok:
        raise HTTPException(status_code=401, detail="Forkert brugernavn eller kodeord")
    limiter.succeeded(ip)
    response.set_cookie(
        COOKIE,
        make_session(settings.secret, user.id, user.session_version),
        max_age=SESSION_DAYS * 86400,
        httponly=True,
        secure=request.url.scheme == "https" or "x-forwarded-for" in request.headers,
        samesite="lax",
    )
    return UserOut(id=user.id, username=user.username)


@router.post("/logout", status_code=204)
def logout(response: Response) -> None:
    response.delete_cookie(COOKIE)


@router.get("/me")
def me(user: CurrentUser) -> UserOut:
    return UserOut(id=user.id, username=user.username)
