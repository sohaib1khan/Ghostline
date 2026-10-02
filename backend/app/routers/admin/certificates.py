"""Certificate settings — super admin only."""

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.models.user import User
from app.security.deps import require_super_admin
from app.security.requests import client_ip
from app.services.audit import write_audit
from app.services.certificates import (
    CERTIFICATE_KEY,
    get_certificate_config,
    save_certificate_config,
)

router = APIRouter(prefix="/admin/certificates", tags=["admin-certificates"])


class CertificateSettingsIn(BaseModel):
    enabled: bool = True
    title: str = Field(default="Certificate of Completion", max_length=120)
    subtitle: str = Field(default="This certifies that", max_length=160)
    body: str = Field(
        default="has successfully completed the {track} learning path.",
        max_length=240,
    )
    signer_name: str = Field(default="Ghostline", max_length=80)
    signer_title: str = Field(default="Typing-first practice", max_length=120)
    footer: str = Field(default="Keep typing. Keep the muscle memory.", max_length=160)


@router.get("")
async def read_certificate_settings(
    _: User = Depends(require_super_admin),
    db: AsyncSession = Depends(get_db),
) -> dict:
    return await get_certificate_config(db)


@router.put("")
async def update_certificate_settings(
    body: CertificateSettingsIn,
    request: Request,
    user: User = Depends(require_super_admin),
    db: AsyncSession = Depends(get_db),
) -> dict:
    saved = await save_certificate_config(db, body.model_dump())
    await write_audit(
        db,
        actor_user_id=user.id,
        action="settings.certificates.update",
        target_type="settings",
        target_id=CERTIFICATE_KEY,
        details={"enabled": saved["enabled"], "title": saved["title"]},
        ip=client_ip(request),
    )
    await db.commit()
    return saved
