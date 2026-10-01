"""Login and logout."""

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db import get_db
from app.schemas.auth import LoginIn, SignupIn, SignupOut, UserOut
from app.security.cookies import SESSION_COOKIE, cookies_are_secure, session_cookie_kwargs
from app.security.rate_limit import limiter
from app.security.requests import client_ip, client_user_agent
from app.services.auth import AuthError, authenticate, revoke_session
from app.services.notifications.dispatcher import dispatch_event
from app.services.signup import SIGNUP_MESSAGE, SignupError, signup

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/signup", response_model=SignupOut, status_code=201)
@limiter.limit(lambda: f"{get_settings().rate_limit_signup}/minute")
async def signup_account(
    request: Request,
    payload: SignupIn,
    response: Response,
    db: AsyncSession = Depends(get_db),
) -> SignupOut:
    try:
        message = await signup(
            db,
            first_name=payload.first_name,
            last_name=payload.last_name,
            email=payload.email,
            password=payload.password,
            ip=client_ip(request),
        )
    except SignupError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc
    response.headers["Cache-Control"] = "no-store"
    return SignupOut(message=message or SIGNUP_MESSAGE)


@router.post("/login", response_model=UserOut)
@limiter.limit(lambda: f"{get_settings().rate_limit_login}/minute")
async def login(
    request: Request,
    payload: LoginIn,
    response: Response,
    db: AsyncSession = Depends(get_db),
) -> UserOut:
    try:
        user, raw = await authenticate(
            db,
            email=payload.email,
            password=payload.password,
            ip=client_ip(request),
            user_agent=client_user_agent(request),
        )
    except AuthError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc
    response.set_cookie(SESSION_COOKIE, raw, **session_cookie_kwargs(get_settings()))
    response.headers["Cache-Control"] = "no-store"
    from app.security.roles import is_staff

    if is_staff(user.role):
        await dispatch_event("admin.login", {"email": user.email})
    return UserOut.model_validate(user)


@router.post("/logout", status_code=204)
async def logout(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> Response:
    await revoke_session(db, request.cookies.get(SESSION_COOKIE), client_ip(request))
    response = Response(status_code=204)
    response.delete_cookie(
        SESSION_COOKIE,
        path="/",
        samesite="lax",
        secure=cookies_are_secure(get_settings()),
        httponly=True,
    )
    response.headers["Cache-Control"] = "no-store"
    return response
