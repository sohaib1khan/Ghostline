"""First-run setup."""

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db import get_db
from app.schemas.auth import SetupIn, SetupStatusOut, UserOut
from app.security.rate_limit import limiter
from app.security.requests import client_ip
from app.services.setup import SetupError, admin_exists, create_initial_admin

router = APIRouter(prefix="/setup", tags=["setup"])


@router.get("/status", response_model=SetupStatusOut)
async def setup_status(db: AsyncSession = Depends(get_db)) -> SetupStatusOut:
    return SetupStatusOut(setup_required=not await admin_exists(db))


@router.post("", response_model=UserOut, status_code=201)
@limiter.limit(lambda: f"{get_settings().rate_limit_login}/minute")
async def setup(
    request: Request,
    payload: SetupIn,
    db: AsyncSession = Depends(get_db),
) -> UserOut:
    try:
        user = await create_initial_admin(
            db,
            setup_token=payload.setup_token,
            first_name=payload.first_name,
            last_name=payload.last_name,
            email=payload.email,
            password=payload.password,
            ip=client_ip(request),
        )
    except SetupError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc
    return UserOut.model_validate(user)
