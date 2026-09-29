"""Read and write app_settings rows."""

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.setting import AppSetting
from app.security.crypto import decrypt_secret, encrypt_secret


async def get_setting(session: AsyncSession, key: str):
    row = await session.scalar(select(AppSetting).where(AppSetting.key == key))
    if row is None:
        return None
    if row.is_secret:
        payload = row.value
        if not isinstance(payload, dict) or "ciphertext" not in payload:
            return None
        return decrypt_secret(payload["ciphertext"])
    return row.value


async def set_setting(session: AsyncSession, key: str, value, *, is_secret: bool = False) -> None:
    stored = {"ciphertext": encrypt_secret(str(value))} if is_secret else value
    row = await session.scalar(select(AppSetting).where(AppSetting.key == key))
    if row is None:
        session.add(AppSetting(key=key, value=stored, is_secret=is_secret))
        return
    row.value = stored
    row.is_secret = is_secret


async def delete_setting(session: AsyncSession, key: str) -> None:
    await session.execute(delete(AppSetting).where(AppSetting.key == key))
