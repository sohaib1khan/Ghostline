"""The signed-in account."""

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.models.user import User
from app.schemas.auth import PasswordChangeIn, ProfileIn, UserOut
from app.security.cookies import SESSION_COOKIE
from app.security.deps import current_user
from app.security.requests import client_ip
from app.services.profile import ProfileError, change_password, update_profile
from app.services.stats import learner_stats

router = APIRouter(tags=["me"])


@router.get("/me/stats")
async def my_stats(
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    return await learner_stats(db, user)


@router.get("/me", response_model=UserOut)
async def me(user: User = Depends(current_user)) -> UserOut:
    return UserOut.model_validate(user)


@router.patch("/me", response_model=UserOut)
async def patch_me(
    payload: ProfileIn,
    request: Request,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
) -> UserOut:
    updated = await update_profile(
        db,
        user,
        first_name=payload.first_name,
        last_name=payload.last_name,
        ip=client_ip(request),
    )
    return UserOut.model_validate(updated)


@router.post("/me/password", status_code=204)
async def patch_password(
    payload: PasswordChangeIn,
    request: Request,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
) -> Response:
    try:
        await change_password(
            db,
            user,
            current_password=payload.current_password,
            new_password=payload.new_password,
            raw_token=request.cookies.get(SESSION_COOKIE),
            ip=client_ip(request),
        )
    except ProfileError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc
    response = Response(status_code=204)
    response.headers["Cache-Control"] = "no-store"
    return response
